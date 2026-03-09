from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.domain import GraphEdge, GraphNode


class GraphMeta(BaseModel):
    rootPageId: str
    generatedAt: datetime
    mode: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    meta: GraphMeta


class SearchItem(BaseModel):
    id: str
    title: str
    type: str
    notionUrl: str


class SearchResponse(BaseModel):
    items: list[SearchItem]
    total: int
    tookMs: int


class NeighborRef(BaseModel):
    id: str
    title: str
    type: str


class NodeDetailResponse(BaseModel):
    node: GraphNode
    ancestors: list[GraphNode]
    adjacentByRelation: dict[str, list[NeighborRef]]
    notionUrl: str


class HealthResponse(BaseModel):
    status: str
    rootPageId: str
    lastFullSyncAt: datetime | None = None
    syncStatus: str | None = None


class GraphQueryParams(BaseModel):
    rootPageId: str | None = None
    mode: str = "full"
    centerNodeId: str | None = None
    depth: int = Field(default=1, ge=1, le=3)
    types: str | None = None
    limit: int = Field(default=2000, ge=1, le=10000)


class SearchQueryParams(BaseModel):
    q: str
    rootPageId: str | None = None
    types: str | None = None
    limit: int = Field(default=20, ge=1, le=100)


class SyncTaskItem(BaseModel):
    id: int
    taskType: str
    status: str
    attempts: int
    maxAttempts: int
    runAt: datetime
    startedAt: datetime | None = None
    finishedAt: datetime | None = None
    payload: dict[str, Any] | None = None
    lastError: str | None = None
    createdAt: datetime
    updatedAt: datetime


class AdminSyncStatusResponse(BaseModel):
    rootPageId: str
    checkpointStatus: str
    lastFullSyncAt: datetime | None = None
    lastError: str | None = None
    nodeCount: int = 0
    edgeCount: int = 0
    queueCounts: dict[str, int]
    latestTasks: list[SyncTaskItem]


class AdminEnqueueResponse(BaseModel):
    accepted: bool
    taskType: str
    pageId: str | None = None


class WebhookIngestResponse(BaseModel):
    received: bool
    queuedPageCount: int
    queuedPageIds: list[str]
    fallbackTaskType: str | None = None


class AdminConfigResponse(BaseModel):
    notionRootPageId: str
    hasNotionToken: bool
    notionUseFixtures: bool
    notionFixturePath: str
    configuredViaDb: bool


class AdminConfigUpdateRequest(BaseModel):
    notionToken: str | None = None
    notionRootPageId: str | None = None
    notionUseFixtures: bool | None = None
    notionFixturePath: str | None = None
    clearNotionToken: bool = False
