# Backend (FastAPI)

## Run Locally

```bash
uv sync
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Required Environment Variables

- `NOTION_TOKEN`
- `NOTION_ROOT_PAGE_ID`
- `DATABASE_URL` (default: `sqlite:////data/notion_graph.db`)
- `SYNC_INTERVAL_MINUTES` (default: `360`)
- `SYNC_POLL_SECONDS` (default: `5`)
- `CORS_ORIGINS` (default: `http://localhost:3000`)

Optional fixture mode:

- `NOTION_USE_FIXTURES=true`
- `NOTION_FIXTURE_PATH=/app/tests/fixtures/notion_fixture.json`

## Test

```bash
uv sync --extra dev
uv run pytest
```
