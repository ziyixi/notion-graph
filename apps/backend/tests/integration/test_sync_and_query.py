from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.db.models import Edge, Node, SyncCheckpoint, SyncTask
from app.services.graph_query import GraphQueryService
from app.services.sync import TASK_TYPE_PAGE_RECONCILE, SyncService


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    fixture_path = (
        Path(__file__).resolve().parents[1] / "fixtures" / "notion_fixture.json"
    )
    db_path = tmp_path / "test_graph.db"

    return SimpleNamespace(
        notion_root_page_id="root_page",
        notion_use_fixtures=True,
        notion_fixture_path=str(fixture_path),
        notion_token="test-token",
        database_url=f"sqlite:///{db_path}",
        sync_interval_minutes=360,
    )


def _session_factory(database_url: str) -> sessionmaker[Session]:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def test_startup_sync_populates_graph(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)

    sync_service = SyncService(session_factory=session_factory, settings=settings)
    sync_service.run_startup_sync()

    with session_factory() as session:
        node_count = session.scalar(select(func.count(Node.id)))
        edge_count = session.scalar(select(func.count(Edge.id)))
        checkpoint = session.get(SyncCheckpoint, settings.notion_root_page_id)

    assert node_count is not None and node_count > 0
    assert edge_count is not None and edge_count > 0
    assert checkpoint is not None
    assert checkpoint.node_count == node_count


def test_full_sync_is_idempotent(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)

    sync_service = SyncService(session_factory=session_factory, settings=settings)
    sync_service.run_startup_sync()

    with session_factory() as session:
        first_node_ids = {row[0] for row in session.execute(select(Node.id)).all()}
        first_edge_ids = {row[0] for row in session.execute(select(Edge.id)).all()}

    sync_service.run_startup_sync()

    with session_factory() as session:
        second_node_ids = {row[0] for row in session.execute(select(Node.id)).all()}
        second_edge_ids = {row[0] for row in session.execute(select(Edge.id)).all()}

    assert first_node_ids == second_node_ids
    assert first_edge_ids == second_edge_ids


def test_query_service_endpoints_shape(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)

    sync_service = SyncService(session_factory=session_factory, settings=settings)
    sync_service.run_startup_sync()

    with session_factory() as session:
        query_service = GraphQueryService(settings)
        graph = query_service.get_graph(session, mode="full", depth=1, limit=100)
        search = query_service.search_nodes(session, query="alice", limit=10)
        detail = query_service.get_node_detail(session, node_id="alice_page")

    assert len(graph.nodes) > 0
    assert len(graph.edges) > 0
    assert search.total >= 1
    assert detail is not None
    assert detail.node.id == "alice_page"
    assert "structured_relation" in detail.adjacentByRelation


def test_search_total_counts_full_match_set(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)

    sync_service = SyncService(session_factory=session_factory, settings=settings)
    sync_service.run_startup_sync()

    with session_factory() as session:
        query_service = GraphQueryService(settings)
        payload = query_service.search_nodes(session, query="a", limit=1)

    assert len(payload.items) == 1
    assert payload.total >= 1
    assert payload.total >= len(payload.items)


def test_graph_type_filter_limits_nodes_and_edges(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)

    sync_service = SyncService(session_factory=session_factory, settings=settings)
    sync_service.run_startup_sync()

    with session_factory() as session:
        query_service = GraphQueryService(settings)
        payload = query_service.get_graph(
            session, mode="full", depth=1, limit=100, types=["person"]
        )

    assert len(payload.nodes) > 0
    assert all(node.type == "person" for node in payload.nodes)
    node_ids = {node.id for node in payload.nodes}
    assert all(edge.sourceId in node_ids and edge.targetId in node_ids for edge in payload.edges)


def test_enqueue_page_sync_deduplicates_pending_tasks(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)
    sync_service = SyncService(session_factory=session_factory, settings=settings)

    sync_service.enqueue_page_sync("alice_page")
    sync_service.enqueue_page_sync("alice_page")

    with session_factory() as session:
        count = session.scalar(
            select(func.count(SyncTask.id))
            .where(SyncTask.task_type == TASK_TYPE_PAGE_RECONCILE)
            .where(SyncTask.status.in_(["queued", "running"]))
        )

    assert count == 1


def test_page_reconcile_task_runs(tmp_path: Path) -> None:
    settings = _make_settings(tmp_path)
    session_factory = _session_factory(settings.database_url)
    sync_service = SyncService(session_factory=session_factory, settings=settings)

    sync_service.run_startup_sync()
    sync_service.enqueue_page_sync("alice_page")
    sync_service.process_next_task()

    with session_factory() as session:
        task = session.scalar(
            select(SyncTask)
            .where(SyncTask.task_type == TASK_TYPE_PAGE_RECONCILE)
            .order_by(SyncTask.id.desc())
            .limit(1)
        )
        alice = session.get(Node, "alice_page")

    assert task is not None
    assert task.status in {"succeeded", "queued", "running"}
    assert alice is not None
