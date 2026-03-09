export type NodeType = "person" | "topic" | "project" | "artifact" | "unknown";

export interface GraphNode {
  id: string;
  title: string;
  notionUrl: string;
  type: NodeType;
  parentId: string | null;
  ancestorIds: string[];
  ancestorTitles: string[];
  depth: number;
  icon?: string | null;
  emoji?: string | null;
  snippet?: string | null;
  tags?: string[];
  lastEditedTime: string;
  inTrash: boolean;
  extractedText?: string | null;
}

export interface GraphEdge {
  id: string;
  sourceId: string;
  targetId: string;
  relationType: "mention" | "link_to_page" | "structured_relation" | "backlink";
  label?: string | null;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  meta: {
    rootPageId: string;
    generatedAt: string;
    mode: string;
  };
}

export interface SearchItem {
  id: string;
  title: string;
  type: NodeType;
  notionUrl: string;
}

export interface SearchResponse {
  items: SearchItem[];
  total: number;
  tookMs: number;
}

export interface NodeDetailResponse {
  node: GraphNode;
  ancestors: GraphNode[];
  adjacentByRelation: Record<string, SearchItem[]>;
  notionUrl: string;
}

export interface SyncTaskItem {
  id: number;
  taskType: string;
  status: string;
  attempts: number;
  maxAttempts: number;
  runAt: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  payload?: Record<string, unknown> | null;
  lastError?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface AdminSyncStatusResponse {
  rootPageId: string;
  checkpointStatus: string;
  lastFullSyncAt?: string | null;
  lastError?: string | null;
  nodeCount: number;
  edgeCount: number;
  queueCounts: Record<string, number>;
  latestTasks: SyncTaskItem[];
}

export interface AdminEnqueueResponse {
  accepted: boolean;
  taskType: string;
  pageId?: string | null;
}

export interface AdminConfigResponse {
  notionRootPageId: string;
  hasNotionToken: boolean;
  notionUseFixtures: boolean;
  notionFixturePath: string;
  configuredViaDb: boolean;
}

export interface AdminConfigUpdateRequest {
  notionToken?: string | null;
  notionRootPageId?: string | null;
  notionUseFixtures?: boolean | null;
  notionFixturePath?: string | null;
  clearNotionToken?: boolean;
}
