import json
from pathlib import Path
from typing import Any, Protocol

from notion_client import Client


class NotionProvider(Protocol):
    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        ...

    def list_block_children(self, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        ...


class RealNotionClient:
    def __init__(self, token: str) -> None:
        self.client = Client(auth=token)

    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        return self.client.pages.retrieve(page_id=page_id)

    def list_block_children(self, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {"block_id": block_id, "page_size": 100}
        if start_cursor:
            params["start_cursor"] = start_cursor
        return self.client.blocks.children.list(**params)


class FixtureNotionClient:
    def __init__(self, fixture_path: str) -> None:
        path = Path(fixture_path)
        if not path.exists():
            raise FileNotFoundError(f"Fixture file not found: {fixture_path}")

        payload = json.loads(path.read_text())
        self.pages = payload.get("pages", {})
        self.block_children = payload.get("block_children", {})

    def retrieve_page(self, page_id: str) -> dict[str, Any]:
        if page_id not in self.pages:
            raise KeyError(f"Page {page_id} not found in fixtures")
        return self.pages[page_id]

    def list_block_children(self, block_id: str, start_cursor: str | None = None) -> dict[str, Any]:
        blocks = self.block_children.get(block_id, [])

        if start_cursor is None:
            index = 0
        else:
            index = int(start_cursor)

        next_index = min(index + 100, len(blocks))
        has_more = next_index < len(blocks)

        return {
            "results": blocks[index:next_index],
            "has_more": has_more,
            "next_cursor": str(next_index) if has_more else None,
        }
