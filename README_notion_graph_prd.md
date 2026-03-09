# Notion Native Knowledge Graph

Single-file PRD, architecture proposal, and coding plan for a Graphify-inspired knowledge graph built on top of native Notion pages.

---

## 0. Implementation Alignment (March 2026)

This document originally proposed a TypeScript/Fastify + queue/webhook-heavy architecture. The implemented v1 differs in several intentional ways:

1. Backend is **Python** (`FastAPI + SQLAlchemy + Alembic`) rather than Node/Fastify.
2. Persistence is **SQLite** (Docker volume-backed) for v1, not Postgres.
3. Sync freshness now includes **startup full sync + periodic reconciliation + webhook-triggered page reconcile**.
4. Runtime now includes an **admin sync control plane** (protected by `ADMIN_API_KEY`) and an `/admin` dashboard.
5. Deployment model is **two Docker images** (`backend`, `web`) orchestrated by `docker compose`.

When this PRD conflicts with repository code, this alignment section and the “Updated v1” sections below take precedence.

---

## 1. Product Summary

Build a web application that turns a subtree of Notion pages into an interactive, beautiful knowledge graph.

Instead of maintaining a dedicated Notion database for nodes and edges, the system will use native Notion pages and page mentions (`@page` / `link to page`) as the source of truth.

The product should feel visually impressive, fast, and exploratory:

- A full-screen interactive graph
- Clickable nodes that open the original Notion page
- Search with a collapsible sidebar
- Highlighting, filtering, and neighborhood exploration
- Automatic sync from Notion into the graph index
- Optional write APIs for app-managed updates and future bidirectional sync

This design assumes there is **one top-level root page** in Notion that acts as the crawl boundary, but the page hierarchy under that root may be nested to **arbitrary depth**.

---

## 2. Why This Approach

### Decision
Use **native Notion pages as the canonical content model**, not Notion databases, for the MVP.

### Why
This reduces authoring friction:

- Users can create pages naturally in Notion
- Relationships can be authored with `@mentions` or `link to page`
- Content can live in nested page trees instead of rigid tables
- Artifacts/evidence can simply be pages in the same tree

### Key Tradeoff
Without a Notion database, page metadata becomes less structured. That means the app must infer or parse:

- page type
- artifact vs concept vs person vs project
- edge labels / relation semantics
- display grouping

This is acceptable for an MVP if we enforce a few lightweight conventions.

---

## 3. Product Goals

### Primary Goals
1. Visualize a Notion page tree as a knowledge graph.
2. Extract edges from page mentions and page links.
3. Support arbitrary nesting depth under a single root page.
4. Provide a polished React UI with search, filters, and node highlighting.
5. Make every graph node openable in the original Notion page.
6. Keep the graph index fresh via startup full sync plus scheduled reconciliation.
7. Leave room for future bidirectional sync and app-assisted editing.

### Secondary Goals
1. Distinguish nodes such as Person / Topic / Project / Artifact.
2. Support evidence pages and backlinks.
3. Support neighborhood exploration for large graphs.
4. Support multiple visual layouts and saved views later.

### Non-Goals (MVP)
1. Full Notion clone or editor.
2. Perfect semantic extraction from arbitrary prose.
3. Collaborative graph editing outside Notion.
4. Fine-grained graph analytics or graph database querying.
5. Multi-workspace support in v1.

---

## 4. Product Principles

1. **Notion-native authoring**: users should mostly work in Notion, not in a custom admin UI.
2. **Low-ceremony graph building**: `@mention` should already create useful edges.
3. **Beautiful by default**: the graph should feel premium, not like a developer demo.
4. **Deterministic sync**: the app should run repeatable full reconciliations and produce idempotent indexed state.
5. **Root-bounded crawling**: graph scope is explicitly defined by one root page.
6. **Scalable rendering**: the UI must stay responsive as the graph grows.

---

## 5. Scope Assumptions

### Root Boundary
A user chooses one top-level Notion page, referred to here as the **Graph Root**.

All pages under this root, at any nesting depth, are considered graph-eligible.

Example:

```text
Graph Root
├── People
│   ├── Alice
│   └── Bob
├── Topics
│   ├── Machine Learning
│   │   └── Representation Learning
│   └── Seismology
├── Projects
│   └── Project Atlas
└── Artifacts
    ├── Paper A
    └── Meeting Note B
```

The system must not assume all relevant pages are only one level or two levels below the root. It must recursively traverse the entire subtree.

### Authoring Conventions
For MVP, the system will support three relationship sources:

1. `@mentions` inside rich text
2. `/link to page` references
3. Optional structured relation blocks inside a page section such as:

```text
Relations
- works_with → @Bob
- references → @Paper A
- about → @Seismology
```

The first two create unlabeled edges by default.
The third creates labeled edges.

### Page Typing Strategy
Because pages outside databases do not provide rich structured properties, page type will be inferred from a priority stack:

1. Explicit app-managed metadata block if present
2. Template marker block if present
3. Nearest classified ancestor folder/page (e.g. `People`, `Projects`, `Artifacts`)
4. Heuristic fallback

---

## 6. User Stories

### End User
- As a user, I want to connect pages in Notion naturally with `@mentions` and immediately see the connections in a graph.
- As a user, I want to search for a node and see matching results in a collapsible sidebar.
- As a user, I want search results to highlight the matching nodes in the graph.
- As a user, I want clicking a node to open the original Notion page.
- As a user, I want to focus on a node’s local neighborhood instead of the full graph.
- As a user, I want artifact pages to act as evidence connected to people, projects, and topics.

### Admin / Builder
- As an admin, I want to connect one Notion root page and have the app index the entire subtree.
- As an admin, I want scheduled reconciliation to keep the graph reasonably fresh.
- As an admin, I want a full reconciliation job to repair drift or missed events.
- As an admin, I want health visibility via logs/health endpoint.

---

## 7. Functional Requirements

### 7.1 Graph Visualization
The graph view must:

- render nodes and edges smoothly
- support pan, zoom, fit-to-screen, and reset view
- support hover emphasis
- support selection and focus state
- support node size, icon, and color based on inferred type and degree
- support large-graph strategies such as progressive loading or neighborhood mode

### 7.2 Node Interaction
When a user clicks a node, the UI should:

- highlight the node
- highlight adjacent edges and neighbors
- show a details panel or sidebar with:
  - title
  - inferred type
  - short preview/snippet
  - ancestor path
  - outbound links
  - inbound links/backlinks if available
  - “Open in Notion” CTA

Double-click or CTA opens the Notion page in a new tab.

### 7.3 Search
The app must provide:

- fuzzy search by page title
- optional search by alias / tags later
- a collapsible sidebar for results
- result count and keyboard navigation
- node highlight on hover and on select
- optional auto-zoom to selected result

### 7.4 Filtering
The app should support:

- filter by inferred type (Person, Topic, Project, Artifact, etc.)
- filter by depth from selected node
- hide isolated nodes
- minimum degree filter
- relation label filter for structured edges

### 7.5 Sync and Freshness
The app must:

- perform initial full crawl from the Graph Root
- run a full crawl on startup
- support scheduled full reconciliation
- make sync idempotent
- expose health via `/api/health` and logs

### 7.6 Artifacts / Evidence
Artifacts are just pages under the root tree, commonly under an `Artifacts` section.

Artifact pages should:

- appear as graph nodes
- be visually distinct
- support evidence-style relations to concept pages
- optionally expose snippet/preview text in the UI

### 7.7 Future Write Support
MVP should keep write APIs minimal, but the architecture should allow:

- creating pages from the app
- appending relation blocks to pages
- inserting `@mentions`
- creating template-based pages

---

## 8. Information Model

### 8.1 Canonical Source of Truth
**Canonical source:** Notion pages and their content under one root page.

### 8.2 Internal Indexed Model
Even though Notion has no dedicated graph database in this design, the backend should maintain an internal indexed representation.

#### Node
```ts
interface GraphNode {
  id: string;                 // Notion page ID
  title: string;
  notionUrl: string;
  type: "person" | "topic" | "project" | "artifact" | "unknown";
  parentId: string | null;
  ancestorIds: string[];
  depth: number;
  icon?: string | null;
  emoji?: string | null;
  snippet?: string | null;
  tags?: string[];
  lastEditedTime: string;
  inTrash: boolean;
  extractedText?: string;
}
```

#### Edge
```ts
interface GraphEdge {
  id: string;                 // deterministic hash
  sourceId: string;
  targetId: string;
  relationType: "mention" | "link_to_page" | "structured_relation" | "backlink";
  label?: string | null;      // e.g. works_with, references, about
  weight?: number;
  evidencePageIds?: string[];
  createdFromBlockId?: string | null;
}
```

#### Sync State
```ts
interface SyncCheckpoint {
  rootPageId: string;
  lastFullSyncAt?: string;
  lastReconcileAt?: string;
  cursor?: string | null;
  status: "idle" | "syncing" | "degraded" | "failed";
}
```

---

## 9. Content Modeling Rules

### 9.1 Edge Extraction Rules
#### Rule A: `@mention`
If page X mentions page Y in rich text, create edge:

`X -> Y` with relationType = `mention`

#### Rule B: `/link to page`
If page X contains a `link_to_page` block to page Y, create edge:

`X -> Y` with relationType = `link_to_page`

#### Rule C: Structured Relation Section
If page X contains a recognized relation line such as:

`works_with → @Bob`

create edge:

`X -> Bob` with relationType = `structured_relation`, label = `works_with`

### 9.2 Artifact Semantics
An artifact page becomes evidence when:

- it lives under a classified `Artifacts` ancestor, or
- it contains an explicit metadata marker such as `Type: Artifact`

### 9.3 Type Inference
Recommended priority:

1. explicit metadata block
2. page template marker
3. nearest classified ancestor under the root tree
4. regex / heuristic fallback

Examples:

- under `/People/...` => person
- under `/Projects/...` => project
- under `/Artifacts/...` => artifact

---

## 10. UX / UI Requirements

### 10.1 Layout
Recommended layout:

- **Center:** interactive graph canvas
- **Left:** collapsible search/results panel
- **Right:** node details / filters panel
- **Top bar:** root selector, search shortcut, layout switcher, fit/reset controls

### 10.2 Visual Design Goals
The experience should feel closer to a premium knowledge map than to a raw force graph.

Use:

- soft glow / depth / motion
- subtle edge animation for selected paths
- type-based node visuals
- balanced light-theme-first readability with optional dark mode later
- good empty/loading states

### 10.3 Search UX
Search behavior:

- typing opens results panel
- results grouped by type
- hovering a result temporarily highlights the node
- selecting a result centers and zooms the node
- sidebar can be collapsed while keeping the selected node active

### 10.4 Details Panel
The details panel should include:

- title
- Notion icon/emoji if present
- type badge
- ancestor path / breadcrumbs
- short extracted summary
- connected nodes grouped by relation type
- “Open in Notion” button

---

## 11. Technical Architecture

```text
Notion Workspace
   |
   |  (API reads)
   v
Sync Service / Ingestion Layer (Python FastAPI app)
   |
   |  startup full crawl + periodic reconciliation
   v
Internal Graph Index (SQLite)
   |
   |  read-only query API
   v
Next.js Web App
   |
   |  search, filters, graph rendering, node detail panels
   v
End User
```

### Core Components
1. **Crawler**: recursively traverses the root page subtree.
2. **Parser**: extracts page content, mentions, relation blocks, and snippets.
3. **Normalizer**: creates stable node/edge representations.
4. **Indexer**: writes nodes, edges, ancestry, and sync checkpoints.
5. **Sync Scheduler**: enqueues startup sync and periodic reconcile tasks.
6. **API Service**: serves read-only graph/search/detail endpoints and health.
7. **Web UI**: renders the graph and interaction model.

---

## 12. Recommended Tech Stack

### Frontend
- **Next.js + TypeScript** for the app shell and production-ready React architecture
- **Custom CSS design system** for a branded, lightweight UI
- **Sigma.js + Graphology** for high-performance graph rendering and graph data manipulation
- **Native React hooks** for state and data fetching in v1

### Why Sigma.js over React Flow for the core graph
Use **Sigma.js** for the main knowledge graph because it is purpose-built for network graphs and large-scale rendering.

React Flow is excellent for node-based editors and workflow builders, but the primary job here is not diagram authoring — it is high-performance exploration of a network graph.

### Backend
- **Python 3.12**
- **FastAPI** for API and lifecycle management
- **Pydantic** for schema validation/settings
- **SQLAlchemy 2 + Alembic** for persistence and migrations
- **SQLite** for indexed graph storage and sync metadata
- **In-process scheduler + DB-backed sync tasks** (no Redis queue in v1)

### Infra
- **Docker** with separate backend and web images
- **docker compose** for local orchestration
- **GitHub Actions + GHCR** for CI and image release

---

## 13. Why Keep an Internal Database Even If Notion Has No Database

The product should **not** require the user to maintain a Notion database.

However, the backend should still maintain an **internal application database** because it needs to:

- serve fast graph queries
- compute neighborhoods and filters
- store ancestry and crawl state
- persist sync tasks/checkpoints and retries
- recover from missed sync windows or process restarts
- support future write APIs safely

This is an implementation database, not a user-authored Notion database.

---

## 14. Notion Integration Design

### 14.1 Crawl Strategy
The crawl boundary is one root page ID.

Initial sync:
1. start from the root page
2. retrieve root block children
3. recursively walk child blocks
4. whenever a `child_page` block is found, retrieve that page’s children recursively
5. extract mentions, links, structured relations, and snippets
6. build ancestry and depth
7. upsert nodes and edges

### 14.2 Why Root Crawl Instead of Search-Only
Search-only discovery is not enough for canonical indexing because search is not optimized for exhaustive enumeration and may be delayed by indexing.

Therefore:
- use the root page tree as the canonical crawl boundary
- use Notion search only for optional discovery tooling or setup helpers

### 14.3 Incremental Sync
In the implemented v1:
1. enqueue a full sync task on app startup
2. execute a full root crawl and replace indexed nodes/edges deterministically
3. run periodic reconciliation based on `SYNC_INTERVAL_MINUTES`
4. retry failed sync tasks with backoff and mark failures in sync checkpoint state

### 14.4 Scheduled Reconciliation
Run a full subtree reconciliation on a schedule, for example every 6 to 24 hours.

Purpose:
- recover from process restarts or stale local index state
- recover from crawl bugs or partial failures

---

## 15. API Design

### Public App APIs

#### `GET /api/graph`
Returns graph data for the selected scope.

Query params:
- `rootPageId`
- `mode=full|neighborhood`
- `centerNodeId?`
- `depth?`
- `types?`
- `limit?`

Note: v1 uses a single configured root from `NOTION_ROOT_PAGE_ID`; if `rootPageId` is sent it must match.

Response:
```json
{
  "nodes": [],
  "edges": [],
  "meta": {
    "rootPageId": "...",
    "generatedAt": "...",
    "mode": "full"
  }
}
```

#### `GET /api/nodes/search`
Fuzzy search nodes by title.

Query params:
- `q`
- `rootPageId`
- `types?`
- `limit?`

Response:
```json
{
  "items": [],
  "total": 0,
  "tookMs": 0
}
```

#### `GET /api/nodes/{id}`
Returns node detail payload.

Includes:
- basic metadata
- snippet
- ancestor path
- adjacent nodes
- relation breakdown
- notion URL

Response:
```json
{
  "node": {},
  "ancestors": [],
  "adjacentByRelation": {},
  "notionUrl": "https://www.notion.so/..."
}
```

#### `GET /api/nodes/{id}/neighborhood`
Returns a node-centered ego graph.

Query params:
- `depth=1|2|3`
- `limit?`

#### `GET /api/health`
Basic health check.

### Admin / Control Plane APIs

#### `GET /api/admin/sync/status`
Returns checkpoint summary, queue counts, and latest tasks.

#### `GET /api/admin/sync/tasks`
Returns recent sync task history.

#### `POST /api/admin/sync/full`
Queues a full reconcile task immediately.

#### `POST /api/admin/sync/pages/{page_id}`
Queues a page-scoped reconcile task (incremental path).

#### `GET /api/admin/metrics`
Returns Prometheus-style runtime metrics text.

#### `POST /api/webhooks/notion`
Accepts Notion webhook events, verifies signature (if `NOTION_WEBHOOK_SECRET` is set), and queues page reconcile tasks.

### Sync Controls

Sync behavior is runtime-driven:
- startup full sync
- periodic reconciliation (`SYNC_INTERVAL_MINUTES`)
- webhook-driven page reconcile (`POST /api/webhooks/notion`) with full-sync fallback
- admin-triggered reconcile controls:
  - `POST /api/admin/sync/full`
  - `POST /api/admin/sync/pages/{page_id}`
- health visibility via `GET /api/health`

### Future Write APIs
These are not required for MVP, but should fit the architecture.

#### `POST /api/pages`
Create a page under a chosen parent using a template.

#### `POST /api/relations`
Append a structured relation block such as:

`works_with → @Bob`

#### `POST /api/pages/{id}/mentions`
Append a mention or link block into a page.

---

## 16. Sync Semantics and Reliability

### Event Handling Rules
1. Treat each scheduled run as an idempotent reconciliation against Notion source of truth.
2. Use deterministic edge IDs to avoid duplicates.
3. Replace indexed graph state deterministically per sync run.
4. Persist sync checkpoint and task state in the database.
5. Retry transient failures and surface degraded state in health/status signals.

### Failure Handling
- retry transient failures with backoff
- respect Notion rate limits
- mark failed sync tasks and persist last error in sync checkpoint
- expose sync health via API health endpoint and logs

---

## 17. Security and Permissions

### OAuth / Integration Model
Prefer a dedicated Notion integration connected to the workspace or selected pages.

### Required Capabilities
- read content
- read comments (optional later)
- insert content (only if future write APIs are enabled)
- update content (only if future write APIs are enabled)

### Security Rules
- never expose Notion access tokens to the browser
- restrict write endpoints behind auth/admin role
- log sync operations with request IDs

---

## 18. Performance Strategy

### Backend
- cache node detail payloads (optional optimization)
- materialize adjacency lookups in SQLite via indexed tables
- store sync checkpoints and retry state
- chunk crawl work by page/tree traversal
- run sync tasks in process with DB-backed task state

### Frontend
- load a reduced graph first for large roots
- support neighborhood mode for dense graphs
- use level-of-detail rendering strategies later
- debounce search
- keep graph layout stable between interactions when possible

### Layout Strategy
Support at least:
- force-directed layout for exploration
- radial / neighborhood layout for focused views
- optional clustered-by-type layout later

---

## 19. Observability

Track:
- pages indexed
- edges extracted
- sync duration
- parse failures by block type
- API latency
- search latency
- graph payload size

Recommended tooling:
- structured logs
- Sentry
- basic metrics dashboard

---

## 20. Risks and Mitigations

### Risk 1: Weak metadata without databases
**Mitigation:** enforce page templates, ancestor-based typing, and optional metadata blocks.

### Risk 2: Search-based discovery misses pages
**Mitigation:** never rely on search as the canonical enumerator; crawl from the root page tree.

### Risk 3: Scheduler cadence causes stale data windows
**Mitigation:** run startup full sync and reduce reconcile interval for fresher data.

### Risk 4: Very dense graphs become visually noisy
**Mitigation:** neighborhood mode, filters, degree thresholds, clustering, and type-based styling.

### Risk 5: Ambiguous relation semantics from plain `@mentions`
**Mitigation:** treat plain mentions as unlabeled edges and offer an optional structured relation syntax.

---

## 21. MVP Definition

The MVP is complete when the following are true:

1. A user can connect a Notion integration and select one root page.
2. The system can recursively crawl all descendant pages under that root.
3. The system can extract page mentions and page links into graph edges.
4. The UI can render the graph, search nodes, highlight results, and open Notion pages.
5. Startup full sync and periodic reconciliation keep the index fresh.
6. Reconciliation runs are idempotent and recoverable after restart/failure.
7. Artifacts/evidence pages are visually distinct and connected in the graph.
8. Backend and web can run as separate Docker images via `docker compose`.

---

## 22. Suggested Repository Structure

```text
apps/
  backend/              # FastAPI app, crawler/parser, sync scheduler
  web/                  # Next.js frontend
.github/
  workflows/            # CI/test/release workflows
docker-compose.yml      # local orchestration for backend + web
Makefile                # local workflows (setup/test/demo/real)
```

---

## 23. Coding Plan for Codex / Vibe Coding

### Phase 0 — Project Scaffold (Implemented)
Deliverables:
- monorepo with `apps/backend` and `apps/web`
- Dockerfiles and compose setup
- env template strategy for demo and real modes

### Phase 1 — Crawl + Parse + Index (Implemented)
Deliverables:
- recursive root crawler
- edge extraction from mentions, `link_to_page`, and structured relations
- SQLite indexed graph model and migrations

### Phase 2 — Sync Reliability (Implemented)
Deliverables:
- startup full sync
- periodic reconciliation scheduler
- DB-backed sync tasks/checkpoints and retry behavior

### Phase 3 — Query API (Implemented)
Deliverables:
- `GET /api/graph`
- `GET /api/nodes/search`
- `GET /api/nodes/{id}`
- `GET /api/nodes/{id}/neighborhood`
- `GET /api/health`

### Phase 4 — Graph UI (Implemented + Polished)
Deliverables:
- Sigma-based graph explorer
- search panel + details panel
- focus controls (fit/reset/focus selected/clear focus)
- improved node/edge visibility and camera behavior

### Phase 5 — CI/CD (Implemented)
Deliverables:
- GitHub Actions workflow for backend tests and web build
- release images to container registry on main/tag pushes
- maintain Docker-first release flow

### Phase 6 — Future Enhancements
Ideas:
- write APIs for relation/page creation
- multi-root and multi-workspace support
- saved graph views and sharing

---

## 24. Prompt Pack for Codex

### Prompt 1 — Crawl Engine
> Build a Python module that recursively crawls a Notion root page, traverses all descendant child pages at arbitrary depth, extracts page mentions and `link_to_page` references, and emits normalized GraphNode and GraphEdge objects.

### Prompt 2 — API Layer
> Build a FastAPI service with endpoints for `/api/graph`, `/api/nodes/search`, `/api/nodes/{id}`, `/api/nodes/{id}/neighborhood`, and `/api/health` using Pydantic + SQLAlchemy.

### Prompt 3 — Frontend Shell
> Build a Next.js page with a polished graph explorer layout: search sidebar on the left, Sigma.js graph canvas in the center, node details panel on the right, and top controls for fit/reset/focus/filter actions.

### Prompt 4 — Search UX
> Implement fuzzy node search with keyboard navigation, collapsible grouped results, hover highlight, and auto-center on select.

### Prompt 5 — Sync Worker
> Build an in-process Python scheduler that handles startup full crawl, periodic full reconciliation, deterministic edge upserts, and retryable task state persisted in SQLite.

---

## 25. Final Recommendation

Yes — for this no-database approach, the correct mental model is:

- **one root page defines graph scope**
- **all relevant pages live somewhere under that root at arbitrary depth**
- **native Notion pages are the authoring surface**
- **@mentions and page links create edges**
- **the app keeps its own internal indexed graph store for speed and reliability**

This gives you the lowest-friction authoring model while still preserving a scalable technical architecture.

If you later discover that you need stronger metadata, richer typed edges, or cleaner admin workflows, you can add an optional Notion database layer in v2 without throwing away this architecture.

---

## 26. Gap Analysis Snapshot (March 2026)

This snapshot maps key PRD requirements to the current codebase and indicates current closure status.

| Area | PRD Expectation | Current Status |
| --- | --- | --- |
| Search quality | Fuzzy search with result metadata | Implemented: backend now performs scored fuzzy matching and returns `items + total + tookMs` |
| Search UX | Collapsible sidebar + grouped results + keyboard navigation | Implemented: web search panel now supports collapse/expand, grouped-by-type sections, arrow key navigation, and Enter-to-select |
| Graph filters | Type, depth from selected node, hide isolated nodes, minimum degree, structured relation label filter | Implemented in web UI filter bar and applied to rendered graph |
| Graph interactions | Node select/hover focus, fit/reset, clear focus, focus selected | Implemented |
| Read APIs | `/api/graph`, `/api/nodes/search`, `/api/nodes/{id}`, `/api/nodes/{id}/neighborhood`, `/api/health` | Implemented |
| Sync model | Startup full sync + periodic reconcile + idempotent replacement | Implemented |
| CI/CD chain | Unit tests -> integration tests -> web build -> image release | Implemented in one GitHub Actions workflow graph |
| Admin/dashboard/webhook writes | Admin sync control plane and webhook ingest | Implemented: admin APIs + `/admin` dashboard + webhook-driven page reconcile with full-sync fallback |
| Advanced observability stack | Metrics/Sentry dashboards | Implemented baseline: Prometheus-style metrics endpoint + admin metrics view + optional Sentry DSN integration |
