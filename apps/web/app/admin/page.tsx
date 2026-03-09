"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";

import {
  fetchAdminConfig,
  enqueueAdminFullSync,
  enqueueAdminPageSync,
  fetchAdminMetrics,
  fetchAdminSyncStatus,
  fetchAdminSyncTasks,
  updateAdminConfig
} from "../../lib/api";
import { AdminConfigResponse, AdminSyncStatusResponse, SyncTaskItem } from "../../lib/types";

const AUTO_REFRESH_MS = 10_000;

export default function AdminPage() {
  const [apiKey, setApiKey] = useState("");
  const [pageId, setPageId] = useState("");
  const [config, setConfig] = useState<AdminConfigResponse | null>(null);
  const [rootPageIdInput, setRootPageIdInput] = useState("");
  const [notionTokenInput, setNotionTokenInput] = useState("");
  const [clearStoredToken, setClearStoredToken] = useState(false);
  const [useFixturesInput, setUseFixturesInput] = useState(false);
  const [fixturePathInput, setFixturePathInput] = useState("");
  const [isConfigInitialized, setIsConfigInitialized] = useState(false);
  const [isSavingConfig, setIsSavingConfig] = useState(false);
  const [status, setStatus] = useState<AdminSyncStatusResponse | null>(null);
  const [tasks, setTasks] = useState<SyncTaskItem[]>([]);
  const [metrics, setMetrics] = useState("");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isTriggeringFull, setIsTriggeringFull] = useState(false);
  const [isTriggeringPage, setIsTriggeringPage] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasApiKey = apiKey.trim().length > 0;

  const refreshAll = useCallback(async () => {
    if (!hasApiKey) {
      return;
    }
    setIsRefreshing(true);
    setError(null);
    try {
      const [nextConfig, nextStatus, nextTasks, nextMetrics] = await Promise.all([
        fetchAdminConfig(apiKey),
        fetchAdminSyncStatus(apiKey),
        fetchAdminSyncTasks(apiKey, 80),
        fetchAdminMetrics(apiKey)
      ]);
      setConfig(nextConfig);
      setStatus(nextStatus);
      setTasks(nextTasks);
      setMetrics(nextMetrics);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh admin data");
    } finally {
      setIsRefreshing(false);
    }
  }, [apiKey, hasApiKey]);

  useEffect(() => {
    if (!config || isConfigInitialized) {
      return;
    }
    setRootPageIdInput(config.notionRootPageId);
    setUseFixturesInput(config.notionUseFixtures);
    setFixturePathInput(config.notionFixturePath);
    setNotionTokenInput("");
    setClearStoredToken(false);
    setIsConfigInitialized(true);
  }, [config, isConfigInitialized]);

  useEffect(() => {
    setIsConfigInitialized(false);
  }, [apiKey]);

  useEffect(() => {
    if (!hasApiKey) {
      setConfig(null);
      setStatus(null);
      setTasks([]);
      setMetrics("");
      return;
    }

    refreshAll();
    const timer = window.setInterval(refreshAll, AUTO_REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [hasApiKey, refreshAll]);

  const onTriggerFullSync = async () => {
    if (!hasApiKey) {
      return;
    }
    setIsTriggeringFull(true);
    setError(null);
    try {
      await enqueueAdminFullSync(apiKey);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enqueue full sync");
    } finally {
      setIsTriggeringFull(false);
    }
  };

  const onTriggerPageSync = async (event: FormEvent) => {
    event.preventDefault();
    if (!hasApiKey || !pageId.trim()) {
      return;
    }
    setIsTriggeringPage(true);
    setError(null);
    try {
      await enqueueAdminPageSync(apiKey, pageId.trim());
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to enqueue page sync");
    } finally {
      setIsTriggeringPage(false);
    }
  };

  const onSaveConfig = async (event: FormEvent) => {
    event.preventDefault();
    if (!hasApiKey) {
      return;
    }

    setIsSavingConfig(true);
    setError(null);
    try {
      const updated = await updateAdminConfig(apiKey, {
        notionRootPageId: rootPageIdInput,
        notionToken: notionTokenInput.trim() ? notionTokenInput.trim() : undefined,
        notionUseFixtures: useFixturesInput,
        notionFixturePath: fixturePathInput,
        clearNotionToken: clearStoredToken
      });
      setConfig(updated);
      setRootPageIdInput(updated.notionRootPageId);
      setUseFixturesInput(updated.notionUseFixtures);
      setFixturePathInput(updated.notionFixturePath);
      setNotionTokenInput("");
      setClearStoredToken(false);
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save runtime config");
    } finally {
      setIsSavingConfig(false);
    }
  };

  return (
    <main className="app-shell admin-shell">
      <header className="top-bar">
        <div className="brand-block">
          <p className="eyebrow">Admin Control Plane</p>
          <h1>Runtime Config, Sync & Observability</h1>
          <p className="top-subline">
            Trigger sync jobs, inspect queue/task state, and view live backend metrics.
          </p>
          <div className="top-links">
            <Link href="/">Back to Graph Explorer</Link>
          </div>
        </div>
      </header>

      <section className="admin-key-row">
        <label className="admin-key-input">
          Admin API Key
          <input
            type="password"
            placeholder="Enter ADMIN_API_KEY"
            value={apiKey}
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>
        <button type="button" className="control-button" onClick={refreshAll} disabled={!hasApiKey || isRefreshing}>
          {isRefreshing ? "Refreshing..." : "Refresh"}
        </button>
        <button
          type="button"
          className="control-button"
          onClick={onTriggerFullSync}
          disabled={!hasApiKey || isTriggeringFull}
        >
          {isTriggeringFull ? "Queueing..." : "Queue Full Reconcile"}
        </button>
      </section>

      <section className="admin-page-sync">
        <form onSubmit={onSaveConfig}>
          <label>
            Root Page ID
            <input
              type="text"
              placeholder="Notion root page id"
              value={rootPageIdInput}
              onChange={(event) => setRootPageIdInput(event.target.value)}
              disabled={!hasApiKey}
            />
          </label>
          <label>
            Notion Token (leave blank to keep existing)
            <input
              type="password"
              placeholder="secret_xxx"
              value={notionTokenInput}
              onChange={(event) => setNotionTokenInput(event.target.value)}
              disabled={!hasApiKey}
            />
          </label>
          <label>
            Fixture Path
            <input
              type="text"
              placeholder="/app/tests/fixtures/notion_fixture.json"
              value={fixturePathInput}
              onChange={(event) => setFixturePathInput(event.target.value)}
              disabled={!hasApiKey}
            />
          </label>
          <label className="admin-checkbox">
            <input
              type="checkbox"
              checked={useFixturesInput}
              onChange={(event) => setUseFixturesInput(event.target.checked)}
              disabled={!hasApiKey}
            />
            Use Fixture Notion Client
          </label>
          <label className="admin-checkbox">
            <input
              type="checkbox"
              checked={clearStoredToken}
              onChange={(event) => setClearStoredToken(event.target.checked)}
              disabled={!hasApiKey}
            />
            Clear Stored Notion Token
          </label>
          <button
            type="submit"
            className="control-button"
            disabled={!hasApiKey || isSavingConfig}
          >
            {isSavingConfig ? "Saving..." : "Save Runtime Config"}
          </button>
        </form>
        {config ? (
          <p className="panel-caption">
            Token configured: {config.hasNotionToken ? "yes" : "no"} | Source:{" "}
            {config.configuredViaDb ? "database" : "env fallback"}
          </p>
        ) : null}
      </section>

      <section className="admin-page-sync">
        <form onSubmit={onTriggerPageSync}>
          <label>
            Page ID (incremental reconcile)
            <input
              type="text"
              placeholder="example: alice_page"
              value={pageId}
              onChange={(event) => setPageId(event.target.value)}
            />
          </label>
          <button type="submit" className="control-button" disabled={!hasApiKey || isTriggeringPage}>
            {isTriggeringPage ? "Queueing..." : "Queue Page Reconcile"}
          </button>
        </form>
      </section>

      {error ? <p className="admin-error">{error}</p> : null}

      <div className="admin-grid">
        <section className="admin-card">
          <h2>Sync Status</h2>
          {status ? (
            <>
              <p>
                <strong>Root:</strong> {status.rootPageId}
              </p>
              <p>
                <strong>Checkpoint:</strong> {status.checkpointStatus}
              </p>
              <p>
                <strong>Last Full Sync:</strong> {status.lastFullSyncAt ?? "n/a"}
              </p>
              <p>
                <strong>Indexed:</strong> {status.nodeCount} nodes / {status.edgeCount} edges
              </p>
              {status.lastError ? (
                <p className="admin-error-inline">
                  <strong>Last Error:</strong> {status.lastError}
                </p>
              ) : null}
              <div className="queue-chips">
                {Object.entries(status.queueCounts).map(([name, count]) => (
                  <span key={name} className="queue-chip">
                    {name}: {count}
                  </span>
                ))}
              </div>
            </>
          ) : (
            <p className="panel-caption">Enter an API key to load status.</p>
          )}
        </section>

        <section className="admin-card admin-card-wide">
          <h2>Recent Tasks</h2>
          {tasks.length === 0 ? (
            <p className="panel-caption">No tasks loaded.</p>
          ) : (
            <div className="admin-table-wrap">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Attempts</th>
                    <th>Run At</th>
                    <th>Payload</th>
                  </tr>
                </thead>
                <tbody>
                  {tasks.map((task) => (
                    <tr key={task.id}>
                      <td>{task.id}</td>
                      <td>{task.taskType}</td>
                      <td>{task.status}</td>
                      <td>
                        {task.attempts}/{task.maxAttempts}
                      </td>
                      <td>{task.runAt}</td>
                      <td>{task.payload ? JSON.stringify(task.payload) : "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        <section className="admin-card admin-card-wide">
          <h2>Prometheus Metrics</h2>
          <pre className="metrics-pre">{metrics || "No metrics loaded."}</pre>
        </section>
      </div>
    </main>
  );
}
