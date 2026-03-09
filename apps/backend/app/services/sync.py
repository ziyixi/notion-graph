from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from time import perf_counter

from sqlalchemy import Select, delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.metrics import metrics_registry
from app.db.models import Edge, Node, SyncCheckpoint, SyncTask
from app.notion.client import FixtureNotionClient, RealNotionClient
from app.notion.crawler import NotionCrawler
from app.schemas.domain import GraphEdge, GraphNode
from app.services.runtime_config import EffectiveRuntimeConfig, RuntimeConfigService

logger = logging.getLogger(__name__)

TASK_TYPE_FULL_RECONCILE = "full_reconcile"
TASK_TYPE_PAGE_RECONCILE = "page_reconcile"


class SyncService:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings
        self.runtime_config_service = RuntimeConfigService()

    def enqueue_full_sync(
        self,
        run_at: datetime | None = None,
        source: str = "system",
    ) -> bool:
        now = datetime.now(UTC)
        run_at = run_at or now

        with self.session_factory() as session:
            config = self.runtime_config_service.get_effective_config(session, self.settings)
            if not config.has_minimum_sync_config:
                return False

            pending_task = session.scalar(
                select(SyncTask)
                .where(SyncTask.task_type == TASK_TYPE_FULL_RECONCILE)
                .where(SyncTask.status.in_(["queued", "running"]))
                .limit(1)
            )
            if pending_task:
                return True

            session.add(
                SyncTask(
                    task_type=TASK_TYPE_FULL_RECONCILE,
                    status="queued",
                    run_at=run_at,
                    max_attempts=3,
                    payload={"source": source, "root_page_id": config.notion_root_page_id},
                )
            )
            session.commit()
            return True

    def enqueue_page_sync(
        self,
        page_id: str,
        run_at: datetime | None = None,
        source: str = "webhook",
    ) -> bool:
        now = datetime.now(UTC)
        run_at = run_at or now

        with self.session_factory() as session:
            config = self.runtime_config_service.get_effective_config(session, self.settings)
            if not config.has_minimum_sync_config:
                return False

            pending_tasks = session.scalars(
                select(SyncTask)
                .where(SyncTask.task_type == TASK_TYPE_PAGE_RECONCILE)
                .where(SyncTask.status.in_(["queued", "running"]))
                .limit(300)
            ).all()

            for task in pending_tasks:
                payload = task.payload or {}
                if payload.get("page_id") == page_id:
                    return True

            session.add(
                SyncTask(
                    task_type=TASK_TYPE_PAGE_RECONCILE,
                    status="queued",
                    run_at=run_at,
                    max_attempts=3,
                    payload={
                        "page_id": page_id,
                        "source": source,
                        "root_page_id": config.notion_root_page_id,
                    },
                )
            )
            session.commit()
            return True

    def ensure_periodic_task(self) -> None:
        now = datetime.now(UTC)
        threshold = now - timedelta(minutes=self.settings.sync_interval_minutes)

        with self.session_factory() as session:
            config = self.runtime_config_service.get_effective_config(session, self.settings)
            if not config.has_minimum_sync_config:
                return

            pending_task = session.scalar(
                select(SyncTask)
                .where(SyncTask.task_type == TASK_TYPE_FULL_RECONCILE)
                .where(SyncTask.status.in_(["queued", "running"]))
                .limit(1)
            )
            if pending_task:
                return

            checkpoint = session.get(SyncCheckpoint, config.notion_root_page_id)
            last_full_sync_at = checkpoint.last_full_sync_at if checkpoint else None
            if last_full_sync_at and last_full_sync_at.tzinfo is None:
                last_full_sync_at = last_full_sync_at.replace(tzinfo=UTC)
            if last_full_sync_at is None or last_full_sync_at <= threshold:
                session.add(
                    SyncTask(
                        task_type=TASK_TYPE_FULL_RECONCILE,
                        status="queued",
                        run_at=now,
                        max_attempts=3,
                        payload={"source": "periodic", "root_page_id": config.notion_root_page_id},
                    )
                )
                session.commit()

    def process_next_task(self) -> bool:
        now = datetime.now(UTC)

        with self.session_factory() as session:
            task = session.scalar(
                select(SyncTask)
                .where(SyncTask.status == "queued")
                .where(SyncTask.run_at <= now)
                .order_by(SyncTask.run_at.asc(), SyncTask.id.asc())
                .limit(1)
            )
            if not task:
                return False

            task.status = "running"
            task.started_at = now
            task.attempts += 1
            session.commit()
            task_id = task.id
            task_type = task.task_type
            task_payload = dict(task.payload or {})
            payload_root_page_id = str(task_payload.get("root_page_id", "")).strip()

        started = perf_counter()
        runtime_config: EffectiveRuntimeConfig | None = None
        try:
            with self.session_factory() as session:
                runtime_config = self.runtime_config_service.get_effective_config(
                    session, self.settings
                )
            if not runtime_config.has_minimum_sync_config:
                raise ValueError("Notion runtime configuration is incomplete")

            if task_type == TASK_TYPE_FULL_RECONCILE:
                node_count, edge_count = self._run_full_sync_task(runtime_config)
            elif task_type == TASK_TYPE_PAGE_RECONCILE:
                page_id = str(task_payload.get("page_id", "")).strip()
                node_count, edge_count = self._run_page_sync_task(page_id, runtime_config)
            else:
                raise ValueError(f"Unsupported sync task type: {task_type}")
        except Exception as exc:
            logger.exception("Sync task failed")
            root_page_id_for_checkpoint = payload_root_page_id
            if not root_page_id_for_checkpoint and runtime_config:
                root_page_id_for_checkpoint = runtime_config.notion_root_page_id
            self._mark_task_failed(task_id, str(exc), root_page_id_for_checkpoint)
            metrics_registry.inc_counter(
                "notion_graph_sync_runs_total",
                labels={"task_type": task_type, "status": "failed"},
            )
            metrics_registry.observe_histogram(
                "notion_graph_sync_duration_seconds",
                perf_counter() - started,
                labels={"task_type": task_type},
            )
            return True

        self._mark_task_succeeded(task_id)
        metrics_registry.inc_counter(
            "notion_graph_sync_runs_total",
            labels={"task_type": task_type, "status": "succeeded"},
        )
        metrics_registry.observe_histogram(
            "notion_graph_sync_duration_seconds",
            perf_counter() - started,
            labels={"task_type": task_type},
        )
        metrics_registry.inc_counter(
            "notion_graph_sync_nodes_indexed_total",
            labels={"task_type": task_type},
            amount=float(node_count),
        )
        metrics_registry.inc_counter(
            "notion_graph_sync_edges_indexed_total",
            labels={"task_type": task_type},
            amount=float(edge_count),
        )
        return True

    def run_startup_sync(self) -> None:
        accepted = self.enqueue_full_sync(source="startup")
        if not accepted:
            logger.info("Skipping startup sync because runtime config is incomplete")
            return
        self.process_next_task()

    def get_checkpoint(self) -> SyncCheckpoint | None:
        with self.session_factory() as session:
            config = self.runtime_config_service.get_effective_config(session, self.settings)
            if not config.notion_root_page_id:
                return None
            return session.get(SyncCheckpoint, config.notion_root_page_id)

    def list_recent_tasks(self, limit: int = 20) -> list[SyncTask]:
        with self.session_factory() as session:
            rows = session.scalars(
                select(SyncTask)
                .order_by(SyncTask.created_at.desc(), SyncTask.id.desc())
                .limit(limit)
            ).all()
            return list(rows)

    def _mark_task_succeeded(self, task_id: int) -> None:
        finished_at = datetime.now(UTC)
        with self.session_factory() as session:
            task = session.get(SyncTask, task_id)
            if not task:
                return
            task.status = "succeeded"
            task.finished_at = finished_at
            task.last_error = None
            session.commit()

    def _mark_task_failed(self, task_id: int, error: str, root_page_id: str | None) -> None:
        now = datetime.now(UTC)
        retry_delay = timedelta(seconds=30)

        with self.session_factory() as session:
            task = session.get(SyncTask, task_id)
            if not task:
                return

            if task.attempts < task.max_attempts:
                task.status = "queued"
                task.run_at = now + retry_delay
                task.last_error = error
                task.started_at = None
            else:
                task.status = "failed"
                task.finished_at = now
                task.last_error = error

            if not root_page_id:
                session.commit()
                return

            checkpoint = session.get(SyncCheckpoint, root_page_id)
            if checkpoint:
                checkpoint.status = "failed"
                checkpoint.last_error = error
            else:
                session.add(
                    SyncCheckpoint(
                        root_page_id=root_page_id,
                        status="failed",
                        last_error=error,
                    )
                )

            session.commit()

    def _run_full_sync_task(self, config: EffectiveRuntimeConfig) -> tuple[int, int]:
        checkpoint_time = datetime.now(UTC)
        notion_client = self._build_notion_client(config)
        crawler = NotionCrawler(notion_client, config.notion_root_page_id)
        crawl_result = crawler.crawl()

        with self.session_factory() as session:
            self._replace_graph(
                session,
                root_page_id=config.notion_root_page_id,
                nodes=crawl_result.nodes,
                edges=crawl_result.edges,
            )

            checkpoint = session.get(SyncCheckpoint, config.notion_root_page_id)
            if not checkpoint:
                checkpoint = SyncCheckpoint(root_page_id=config.notion_root_page_id)
                session.add(checkpoint)

            checkpoint.last_full_sync_at = checkpoint_time
            checkpoint.status = "idle"
            checkpoint.last_error = None
            checkpoint.node_count = len(crawl_result.nodes)
            checkpoint.edge_count = len(crawl_result.edges)

            session.commit()
            return (len(crawl_result.nodes), len(crawl_result.edges))

    def _run_page_sync_task(
        self,
        page_id: str,
        config: EffectiveRuntimeConfig,
    ) -> tuple[int, int]:
        if not page_id:
            return self._run_full_sync_task(config)

        with self.session_factory() as session:
            existing_node = session.get(Node, page_id)
            if not existing_node or existing_node.root_page_id != config.notion_root_page_id:
                logger.info(
                    "Page %s not found in local index, falling back to full reconcile",
                    page_id,
                )
                return self._run_full_sync_task(config)

            parent_id = existing_node.parent_id
            ancestor_ids = list(existing_node.ancestor_ids or [])
            ancestor_titles = list(existing_node.ancestor_titles or [])
            depth = existing_node.depth

        notion_client = self._build_notion_client(config)
        crawler = NotionCrawler(notion_client, config.notion_root_page_id)
        crawl_result = crawler.crawl_from_page(
            start_page_id=page_id,
            parent_id=parent_id,
            ancestor_ids=ancestor_ids,
            ancestor_titles=ancestor_titles,
            depth=depth,
            restrict_edge_targets_to_crawled_nodes=False,
        )

        with self.session_factory() as session:
            node_count, edge_count = self._replace_subgraph(
                session=session,
                root_page_id=config.notion_root_page_id,
                start_page_id=page_id,
                nodes=crawl_result.nodes,
                edges=crawl_result.edges,
            )

            checkpoint = session.get(SyncCheckpoint, config.notion_root_page_id)
            if not checkpoint:
                checkpoint = SyncCheckpoint(root_page_id=config.notion_root_page_id)
                session.add(checkpoint)

            checkpoint.status = "idle"
            checkpoint.last_error = None
            checkpoint.node_count = session.scalar(
                select(func.count(Node.id)).where(Node.root_page_id == config.notion_root_page_id)
            ) or 0
            checkpoint.edge_count = session.scalar(
                select(func.count(Edge.id)).where(Edge.root_page_id == config.notion_root_page_id)
            ) or 0

            session.commit()
            return (node_count, edge_count)

    def _build_notion_client(
        self,
        config: EffectiveRuntimeConfig,
    ) -> RealNotionClient | FixtureNotionClient:
        if config.notion_use_fixtures:
            if not config.notion_fixture_path:
                raise ValueError("NOTION_FIXTURE_PATH must be set when NOTION_USE_FIXTURES=true")
            return FixtureNotionClient(config.notion_fixture_path)

        return RealNotionClient(config.notion_token)

    def _replace_graph(
        self,
        session: Session,
        root_page_id: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> None:
        now = datetime.now(UTC)

        session.execute(delete(Edge).where(Edge.root_page_id == root_page_id))
        session.execute(delete(Node).where(Node.root_page_id == root_page_id))

        self._insert_nodes(session, root_page_id=root_page_id, nodes=nodes, synced_at=now)
        self._insert_edges(session, root_page_id=root_page_id, edges=edges, synced_at=now)

    def _replace_subgraph(
        self,
        session: Session,
        root_page_id: str,
        start_page_id: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
    ) -> tuple[int, int]:
        now = datetime.now(UTC)

        existing_nodes = session.scalars(
            select(Node).where(Node.root_page_id == root_page_id)
        ).all()
        old_subtree_ids = {
            node.id
            for node in existing_nodes
            if node.id == start_page_id or start_page_id in (node.ancestor_ids or [])
        }
        stale_node_ids = old_subtree_ids - {node.id for node in nodes}

        if old_subtree_ids:
            session.execute(
                delete(Edge)
                .where(Edge.root_page_id == root_page_id)
                .where(Edge.source_id.in_(old_subtree_ids))
            )

        if stale_node_ids:
            session.execute(
                delete(Edge)
                .where(Edge.root_page_id == root_page_id)
                .where(Edge.target_id.in_(stale_node_ids))
            )

        if old_subtree_ids:
            session.execute(
                delete(Node)
                .where(Node.root_page_id == root_page_id)
                .where(Node.id.in_(old_subtree_ids))
            )

        self._insert_nodes(session, root_page_id=root_page_id, nodes=nodes, synced_at=now)

        existing_outside_ids = {
            node.id
            for node in existing_nodes
            if node.id not in old_subtree_ids and not node.in_trash
        }
        new_ids = {node.id for node in nodes}
        valid_target_ids = existing_outside_ids | new_ids
        filtered_edges = [
            edge
            for edge in edges
            if edge.sourceId in new_ids
            and edge.targetId in valid_target_ids
            and edge.sourceId != edge.targetId
        ]
        self._insert_edges(
            session,
            root_page_id=root_page_id,
            edges=filtered_edges,
            synced_at=now,
        )

        return (len(nodes), len(filtered_edges))

    def _insert_nodes(
        self,
        session: Session,
        root_page_id: str,
        nodes: list[GraphNode],
        synced_at: datetime,
    ) -> None:
        for node in nodes:
            session.add(
                Node(
                    id=node.id,
                    root_page_id=root_page_id,
                    title=node.title,
                    notion_url=node.notionUrl,
                    type=node.type,
                    parent_id=node.parentId,
                    ancestor_ids=node.ancestorIds,
                    ancestor_titles=node.ancestorTitles,
                    depth=node.depth,
                    icon=node.icon,
                    emoji=node.emoji,
                    snippet=node.snippet,
                    tags=node.tags,
                    last_edited_time=node.lastEditedTime,
                    in_trash=node.inTrash,
                    extracted_text=node.extractedText,
                    synced_at=synced_at,
                )
            )

    def _insert_edges(
        self,
        session: Session,
        root_page_id: str,
        edges: list[GraphEdge],
        synced_at: datetime,
    ) -> None:
        for edge in edges:
            session.add(
                Edge(
                    id=edge.id,
                    root_page_id=root_page_id,
                    source_id=edge.sourceId,
                    target_id=edge.targetId,
                    relation_type=edge.relationType,
                    label=edge.label,
                    weight=edge.weight,
                    evidence_page_ids=edge.evidencePageIds,
                    created_from_block_id=edge.createdFromBlockId,
                    synced_at=synced_at,
                )
            )


class SyncMetricsService:
    def __init__(self, session_factory: sessionmaker[Session], settings: Settings) -> None:
        self.session_factory = session_factory
        self.settings = settings

    def queue_counts(self) -> dict[str, int]:
        with self.session_factory() as session:
            stmt: Select[tuple[str, int]] = (
                select(SyncTask.status, func.count(SyncTask.id))
                .group_by(SyncTask.status)
                .order_by(SyncTask.status)
            )
            rows = session.execute(stmt).all()
            return {status: count for status, count in rows}
