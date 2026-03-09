from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.metrics import metrics_registry
from app.notion.client import NotionProvider
from app.notion.parser import infer_node_type, parse_block_edges
from app.schemas.domain import GraphEdge, GraphNode


@dataclass
class CrawlResult:
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class NotionCrawler:
    def __init__(self, notion: NotionProvider, root_page_id: str) -> None:
        self.notion = notion
        self.root_page_id = root_page_id

    def crawl(self) -> CrawlResult:
        return self.crawl_from_page(
            start_page_id=self.root_page_id,
            parent_id=None,
            ancestor_ids=[],
            ancestor_titles=[],
            depth=0,
            restrict_edge_targets_to_crawled_nodes=True,
        )

    def crawl_from_page(
        self,
        start_page_id: str,
        parent_id: str | None,
        ancestor_ids: list[str],
        ancestor_titles: list[str],
        depth: int,
        restrict_edge_targets_to_crawled_nodes: bool,
    ) -> CrawlResult:
        nodes: dict[str, GraphNode] = {}
        edges: dict[str, GraphEdge] = {}
        visited: set[str] = set()

        def crawl_page(
            page_id: str,
            parent_id: str | None,
            ancestor_ids: list[str],
            ancestor_titles: list[str],
            depth: int,
        ) -> None:
            if page_id in visited:
                return
            visited.add(page_id)

            page = self.notion.retrieve_page(page_id)
            page_title = _extract_page_title(page)
            children = self._walk_block_tree(page_id)

            extracted_lines: list[str] = []
            child_page_ids: list[str] = []

            for block in children:
                try:
                    parsed = parse_block_edges(page_id, block)
                    extracted_lines.extend(parsed.extracted_text)
                    child_page_ids.extend(parsed.child_page_ids)
                    for edge in parsed.edges:
                        edges[edge.id] = edge
                except Exception:
                    block_type = str(block.get("type", "unknown"))
                    metrics_registry.inc_counter(
                        "notion_graph_parse_failures_total",
                        labels={"block_type": block_type},
                    )

            extracted_text = "\n".join(extracted_lines).strip() or None
            snippet = extracted_text[:280] if extracted_text else None
            node_type = infer_node_type(page_title, ancestor_titles, extracted_lines)
            icon, emoji = _extract_page_icon(page)

            nodes[page_id] = GraphNode(
                id=page_id,
                title=page_title,
                notionUrl=page.get("url", ""),
                type=node_type,
                parentId=parent_id,
                ancestorIds=ancestor_ids,
                ancestorTitles=ancestor_titles,
                depth=depth,
                icon=icon,
                emoji=emoji,
                snippet=snippet,
                tags=[],
                lastEditedTime=page.get("last_edited_time", datetime.now(UTC).isoformat()),
                inTrash=bool(page.get("in_trash", False)),
                extractedText=extracted_text,
            )

            next_ancestor_ids = ancestor_ids + [page_id]
            next_ancestor_titles = ancestor_titles + [page_title]

            for child_page_id in child_page_ids:
                crawl_page(
                    child_page_id,
                    page_id,
                    next_ancestor_ids,
                    next_ancestor_titles,
                    depth + 1,
                )

        crawl_page(start_page_id, parent_id, ancestor_ids, ancestor_titles, depth)

        allowed_node_ids = set(nodes.keys())
        filtered_edges = [
            edge
            for edge in edges.values()
            if edge.sourceId in allowed_node_ids
            and (
                edge.targetId in allowed_node_ids
                if restrict_edge_targets_to_crawled_nodes
                else True
            )
            and edge.sourceId != edge.targetId
        ]

        return CrawlResult(nodes=list(nodes.values()), edges=filtered_edges)

    def _walk_block_tree(self, block_id: str) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []

        def visit(parent_block_id: str) -> None:
            for block in self._list_all_children(parent_block_id):
                collected.append(block)
                if block.get("has_children") and block.get("type") != "child_page":
                    visit(block["id"])

        visit(block_id)
        return collected

    def _list_all_children(self, block_id: str) -> list[dict[str, Any]]:
        all_children: list[dict[str, Any]] = []
        next_cursor: str | None = None

        while True:
            response = self.notion.list_block_children(block_id, start_cursor=next_cursor)
            all_children.extend(response.get("results", []))
            if not response.get("has_more"):
                break
            next_cursor = response.get("next_cursor")
            if not next_cursor:
                break

        return all_children


def _extract_page_title(page: dict[str, Any]) -> str:
    properties = page.get("properties", {})
    for prop in properties.values():
        if prop.get("type") != "title":
            continue
        title_segments = prop.get("title", [])
        parts = [segment.get("plain_text", "") for segment in title_segments]
        title = "".join(parts).strip()
        if title:
            return title

    return page.get("id", "Untitled")


def _extract_page_icon(page: dict[str, Any]) -> tuple[str | None, str | None]:
    icon = page.get("icon")
    if not icon:
        return None, None

    if icon.get("type") == "emoji":
        emoji = icon.get("emoji")
        return emoji, emoji

    if icon.get("type") == "external":
        return icon.get("external", {}).get("url"), None

    if icon.get("type") == "file":
        return icon.get("file", {}).get("url"), None

    return None, None
