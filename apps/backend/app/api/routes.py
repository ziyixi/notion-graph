import json

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.metrics import metrics_registry
from app.db.models import SyncCheckpoint, SyncTask
from app.db.session import SessionLocal, get_session
from app.notion.webhook import extract_page_ids_from_webhook, verify_webhook_signature
from app.schemas.api import (
    AdminEnqueueResponse,
    AdminSyncStatusResponse,
    GraphResponse,
    HealthResponse,
    NodeDetailResponse,
    SearchResponse,
    SyncTaskItem,
    WebhookIngestResponse,
)
from app.services.graph_query import GraphQueryService
from app.services.sync import (
    TASK_TYPE_FULL_RECONCILE,
    TASK_TYPE_PAGE_RECONCILE,
    SyncMetricsService,
    SyncService,
)

router = APIRouter(prefix="/api")


def _split_types(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _validate_root(settings: Settings, root_page_id: str | None) -> None:
    if root_page_id and root_page_id != settings.notion_root_page_id:
        raise HTTPException(
            status_code=400,
            detail="rootPageId must match configured NOTION_ROOT_PAGE_ID",
        )


def _require_admin(
    settings: Settings = Depends(get_settings),
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-Api-Key"),
) -> None:
    if not settings.admin_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin control plane is disabled. Set ADMIN_API_KEY to enable it.",
        )
    if x_admin_api_key != settings.admin_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin API key",
        )


def _to_sync_task_item(task: SyncTask) -> SyncTaskItem:
    return SyncTaskItem(
        id=task.id,
        taskType=task.task_type,
        status=task.status,
        attempts=task.attempts,
        maxAttempts=task.max_attempts,
        runAt=task.run_at,
        startedAt=task.started_at,
        finishedAt=task.finished_at,
        payload=task.payload,
        lastError=task.last_error,
        createdAt=task.created_at,
        updatedAt=task.updated_at,
    )


@router.get("/graph", response_model=GraphResponse)
def get_graph(
    mode: str = Query(default="full", pattern="^(full|neighborhood)$"),
    root_page_id: str | None = Query(default=None, alias="rootPageId"),
    center_node_id: str | None = Query(default=None, alias="centerNodeId"),
    depth: int = Query(default=1, ge=1, le=3),
    types: str | None = Query(default=None),
    limit: int = Query(default=2000, ge=1, le=10000),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> GraphResponse:
    _validate_root(settings, root_page_id)

    if mode == "neighborhood" and not center_node_id:
        raise HTTPException(
            status_code=400,
            detail="centerNodeId is required for neighborhood mode",
        )

    service = GraphQueryService(settings)
    return service.get_graph(
        session=session,
        mode=mode,
        center_node_id=center_node_id,
        depth=depth,
        types=_split_types(types),
        limit=limit,
    )


@router.get("/nodes/search", response_model=SearchResponse)
def search_nodes(
    q: str = Query(..., min_length=1),
    root_page_id: str | None = Query(default=None, alias="rootPageId"),
    types: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SearchResponse:
    _validate_root(settings, root_page_id)
    service = GraphQueryService(settings)
    return service.search_nodes(session=session, query=q, limit=limit, types=_split_types(types))


@router.get("/nodes/{node_id}", response_model=NodeDetailResponse)
def get_node_detail(
    node_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> NodeDetailResponse:
    service = GraphQueryService(settings)
    payload = service.get_node_detail(session=session, node_id=node_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return payload


@router.get("/nodes/{node_id}/neighborhood", response_model=GraphResponse)
def get_neighborhood(
    node_id: str,
    depth: int = Query(default=1, ge=1, le=3),
    limit: int = Query(default=500, ge=1, le=5000),
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> GraphResponse:
    service = GraphQueryService(settings)
    return service.get_graph(
        session=session,
        mode="neighborhood",
        center_node_id=node_id,
        depth=depth,
        types=None,
        limit=limit,
    )


@router.get("/health", response_model=HealthResponse)
def get_health(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> HealthResponse:
    service = GraphQueryService(settings)
    status, last_full_sync_at, sync_status = service.get_health(session=session)
    return HealthResponse(
        status="ok" if status in {"idle", "running"} else "degraded",
        rootPageId=settings.notion_root_page_id,
        lastFullSyncAt=last_full_sync_at,
        syncStatus=sync_status,
    )


@router.get(
    "/admin/sync/status",
    response_model=AdminSyncStatusResponse,
    dependencies=[Depends(_require_admin)],
)
def get_admin_sync_status(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdminSyncStatusResponse:
    checkpoint = session.get(SyncCheckpoint, settings.notion_root_page_id)
    queue_counts = SyncMetricsService(
        session_factory=SessionLocal, settings=settings
    ).queue_counts()
    tasks = session.scalars(
        select(SyncTask).order_by(SyncTask.created_at.desc(), SyncTask.id.desc()).limit(20)
    ).all()

    return AdminSyncStatusResponse(
        rootPageId=settings.notion_root_page_id,
        checkpointStatus=checkpoint.status if checkpoint else "starting",
        lastFullSyncAt=checkpoint.last_full_sync_at if checkpoint else None,
        lastError=checkpoint.last_error if checkpoint else None,
        nodeCount=checkpoint.node_count if checkpoint else 0,
        edgeCount=checkpoint.edge_count if checkpoint else 0,
        queueCounts=queue_counts,
        latestTasks=[_to_sync_task_item(task) for task in tasks],
    )


@router.get(
    "/admin/sync/tasks",
    response_model=list[SyncTaskItem],
    dependencies=[Depends(_require_admin)],
)
def get_admin_sync_tasks(
    limit: int = Query(default=50, ge=1, le=200),
    settings: Settings = Depends(get_settings),
) -> list[SyncTaskItem]:
    service = SyncService(session_factory=SessionLocal, settings=settings)
    tasks = service.list_recent_tasks(limit=limit)
    return [_to_sync_task_item(task) for task in tasks]


@router.post(
    "/admin/sync/full",
    response_model=AdminEnqueueResponse,
    dependencies=[Depends(_require_admin)],
)
def enqueue_full_sync(
    settings: Settings = Depends(get_settings),
) -> AdminEnqueueResponse:
    SyncService(session_factory=SessionLocal, settings=settings).enqueue_full_sync(source="admin")
    return AdminEnqueueResponse(accepted=True, taskType=TASK_TYPE_FULL_RECONCILE)


@router.post(
    "/admin/sync/pages/{page_id}",
    response_model=AdminEnqueueResponse,
    dependencies=[Depends(_require_admin)],
)
def enqueue_page_sync(
    page_id: str,
    settings: Settings = Depends(get_settings),
) -> AdminEnqueueResponse:
    SyncService(session_factory=SessionLocal, settings=settings).enqueue_page_sync(
        page_id=page_id,
        source="admin",
    )
    return AdminEnqueueResponse(accepted=True, taskType=TASK_TYPE_PAGE_RECONCILE, pageId=page_id)


@router.get(
    "/admin/metrics",
    response_class=PlainTextResponse,
    dependencies=[Depends(_require_admin)],
)
def get_admin_metrics(settings: Settings = Depends(get_settings)) -> PlainTextResponse:
    queue_counts = SyncMetricsService(
        session_factory=SessionLocal, settings=settings
    ).queue_counts()
    payload = metrics_registry.render_prometheus()
    if queue_counts:
        queue_lines = ["# TYPE notion_graph_sync_tasks_queue gauge"]
        for status_name, count in sorted(queue_counts.items()):
            queue_lines.append(
                f'notion_graph_sync_tasks_queue{{status="{status_name}"}} {count}'
            )
        payload = payload + "\n".join(queue_lines) + "\n"

    return PlainTextResponse(payload)


@router.post("/webhooks/notion", response_model=WebhookIngestResponse)
async def ingest_notion_webhook(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> WebhookIngestResponse:
    body = await request.body()
    signature_header = request.headers.get("x-notion-signature") or request.headers.get(
        "notion-signature"
    )
    timestamp_header = (
        request.headers.get("x-notion-request-timestamp")
        or request.headers.get("notion-request-timestamp")
        or request.headers.get("x-notion-timestamp")
    )

    is_verified = verify_webhook_signature(
        secret=settings.notion_webhook_secret,
        body=body,
        signature_header=signature_header,
        timestamp_header=timestamp_header,
    )
    if not is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature",
        )

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook payload: {exc}") from exc

    page_ids = extract_page_ids_from_webhook(payload)
    sync_service = SyncService(session_factory=SessionLocal, settings=settings)

    if page_ids:
        for page_id in page_ids:
            sync_service.enqueue_page_sync(page_id=page_id, source="webhook")
        return WebhookIngestResponse(
            received=True,
            queuedPageCount=len(page_ids),
            queuedPageIds=page_ids,
            fallbackTaskType=None,
        )

    sync_service.enqueue_full_sync(source="webhook_fallback")
    return WebhookIngestResponse(
        received=True,
        queuedPageCount=0,
        queuedPageIds=[],
        fallbackTaskType=TASK_TYPE_FULL_RECONCILE,
    )
