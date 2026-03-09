import {
  AdminEnqueueResponse,
  AdminSyncStatusResponse,
  GraphResponse,
  NodeDetailResponse,
  SearchResponse,
  SyncTaskItem
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

function adminHeaders(apiKey: string): HeadersInit {
  return {
    "X-Admin-Api-Key": apiKey
  };
}

export async function fetchGraph(): Promise<GraphResponse> {
  return request<GraphResponse>("/api/graph?mode=full");
}

export async function searchNodes(q: string, types?: string[]): Promise<SearchResponse> {
  const params = new URLSearchParams({ q });
  if (types && types.length > 0) {
    params.set("types", types.join(","));
  }
  return request<SearchResponse>(`/api/nodes/search?${params.toString()}`);
}

export async function fetchNodeDetail(nodeId: string): Promise<NodeDetailResponse> {
  return request<NodeDetailResponse>(`/api/nodes/${encodeURIComponent(nodeId)}`);
}

export async function fetchAdminSyncStatus(apiKey: string): Promise<AdminSyncStatusResponse> {
  return request<AdminSyncStatusResponse>("/api/admin/sync/status", {
    headers: adminHeaders(apiKey)
  });
}

export async function fetchAdminSyncTasks(
  apiKey: string,
  limit = 50
): Promise<SyncTaskItem[]> {
  return request<SyncTaskItem[]>(`/api/admin/sync/tasks?limit=${limit}`, {
    headers: adminHeaders(apiKey)
  });
}

export async function enqueueAdminFullSync(apiKey: string): Promise<AdminEnqueueResponse> {
  return request<AdminEnqueueResponse>("/api/admin/sync/full", {
    method: "POST",
    headers: adminHeaders(apiKey)
  });
}

export async function enqueueAdminPageSync(
  apiKey: string,
  pageId: string
): Promise<AdminEnqueueResponse> {
  return request<AdminEnqueueResponse>(`/api/admin/sync/pages/${encodeURIComponent(pageId)}`, {
    method: "POST",
    headers: adminHeaders(apiKey)
  });
}

export async function fetchAdminMetrics(apiKey: string): Promise<string> {
  const response = await fetch(`${API_BASE}/api/admin/metrics`, {
    cache: "no-store",
    headers: adminHeaders(apiKey)
  });
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }
  return response.text();
}
