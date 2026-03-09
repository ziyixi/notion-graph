from __future__ import annotations

import re
from collections import defaultdict, deque
from datetime import UTC, datetime
from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import Edge, Node, SyncCheckpoint
from app.schemas.api import (
    GraphMeta,
    GraphResponse,
    NeighborRef,
    NodeDetailResponse,
    SearchItem,
    SearchResponse,
)
from app.schemas.domain import GraphEdge, GraphNode


class GraphQueryService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def get_graph(
        self,
        session: Session,
        mode: str = "full",
        center_node_id: str | None = None,
        depth: int = 1,
        types: list[str] | None = None,
        limit: int = 2000,
    ) -> GraphResponse:
        if mode == "neighborhood":
            node_ids = self._neighborhood_ids(session, center_node_id, depth)
        else:
            stmt = select(Node.id).where(Node.root_page_id == self.settings.notion_root_page_id)
            if types:
                stmt = stmt.where(Node.type.in_(types))
            stmt = stmt.limit(limit)
            node_ids = {row[0] for row in session.execute(stmt).all()}

        if len(node_ids) > limit:
            node_ids = set(list(node_ids)[:limit])

        nodes = self._load_nodes(session, node_ids)
        edges = self._load_edges_for_node_ids(session, node_ids)

        if types:
            allowed_types = set(types)
            nodes = [node for node in nodes if node.type in allowed_types]
            allowed_ids = {node.id for node in nodes}
            edges = [
                edge
                for edge in edges
                if edge.sourceId in allowed_ids and edge.targetId in allowed_ids
            ]

        return GraphResponse(
            nodes=nodes,
            edges=edges,
            meta=GraphMeta(
                rootPageId=self.settings.notion_root_page_id,
                generatedAt=datetime.now(UTC),
                mode=mode,
            ),
        )

    def search_nodes(
        self,
        session: Session,
        query: str,
        limit: int = 20,
        types: list[str] | None = None,
    ) -> SearchResponse:
        started_at = datetime.now(UTC)
        normalized_query = query.strip().lower()
        query_tokens = [token for token in re.split(r"\s+", normalized_query) if token]

        stmt = (
            select(Node)
            .where(Node.root_page_id == self.settings.notion_root_page_id)
            .order_by(Node.title.asc())
        )

        if types:
            stmt = stmt.where(Node.type.in_(types))

        rows = session.scalars(stmt).all()

        scored: list[tuple[float, Node]] = []
        for node in rows:
            title = node.title.lower()
            ratio = SequenceMatcher(None, normalized_query, title).ratio()
            token_hits = sum(1 for token in query_tokens if token in title)
            token_coverage = token_hits / max(len(query_tokens), 1)

            has_match = (
                not normalized_query
                or normalized_query in title
                or token_hits > 0
                or ratio >= 0.42
            )
            if not has_match:
                continue

            exact = 1.0 if title == normalized_query else 0.0
            starts_with = 1.0 if title.startswith(normalized_query) else 0.0
            contains = 1.0 if normalized_query and normalized_query in title else 0.0

            score = (exact * 12.0) + (starts_with * 5.0) + (contains * 3.0) + (
                token_coverage * 2.0
            ) + ratio
            scored.append((score, node))

        scored.sort(key=lambda item: (-item[0], item[1].title.lower()))
        matched_nodes = [node for _, node in scored]
        selected_nodes = matched_nodes[:limit]

        elapsed = datetime.now(UTC) - started_at
        took_ms = int(elapsed.total_seconds() * 1000)

        return SearchResponse(
            items=[
                SearchItem(id=node.id, title=node.title, type=node.type, notionUrl=node.notion_url)
                for node in selected_nodes
            ],
            total=len(matched_nodes),
            tookMs=took_ms,
        )

    def get_node_detail(self, session: Session, node_id: str) -> NodeDetailResponse | None:
        node = session.get(Node, node_id)
        if not node or node.root_page_id != self.settings.notion_root_page_id:
            return None

        ancestors = self._load_nodes(session, set(node.ancestor_ids))

        adjacent_edges = session.scalars(
            select(Edge)
            .where(Edge.root_page_id == self.settings.notion_root_page_id)
            .where(or_(Edge.source_id == node_id, Edge.target_id == node_id))
        ).all()

        neighbor_ids: set[str] = set()
        for edge in adjacent_edges:
            if edge.source_id != node_id:
                neighbor_ids.add(edge.source_id)
            if edge.target_id != node_id:
                neighbor_ids.add(edge.target_id)

        neighbors = {
            item.id: item
            for item in session.scalars(select(Node).where(Node.id.in_(neighbor_ids))).all()
        }

        adjacent_by_relation: dict[str, list[NeighborRef]] = defaultdict(list)
        for edge in adjacent_edges:
            neighbor_id = edge.target_id if edge.source_id == node_id else edge.source_id
            neighbor = neighbors.get(neighbor_id)
            if not neighbor:
                continue
            adjacent_by_relation[edge.relation_type].append(
                NeighborRef(id=neighbor.id, title=neighbor.title, type=neighbor.type)
            )

        return NodeDetailResponse(
            node=self._to_graph_node(node),
            ancestors=ancestors,
            adjacentByRelation=adjacent_by_relation,
            notionUrl=node.notion_url,
        )

    def get_health(self, session: Session) -> tuple[str, datetime | None, str | None]:
        checkpoint = session.get(SyncCheckpoint, self.settings.notion_root_page_id)
        if not checkpoint:
            return "starting", None, None
        return checkpoint.status or "idle", checkpoint.last_full_sync_at, checkpoint.status

    def _load_nodes(self, session: Session, node_ids: set[str]) -> list[GraphNode]:
        if not node_ids:
            return []
        rows = session.scalars(select(Node).where(Node.id.in_(node_ids))).all()
        return [self._to_graph_node(row) for row in rows]

    def _load_edges_for_node_ids(self, session: Session, node_ids: set[str]) -> list[GraphEdge]:
        if not node_ids:
            return []

        rows = session.scalars(
            select(Edge)
            .where(Edge.root_page_id == self.settings.notion_root_page_id)
            .where(Edge.source_id.in_(node_ids))
            .where(Edge.target_id.in_(node_ids))
        ).all()

        return [
            GraphEdge(
                id=edge.id,
                sourceId=edge.source_id,
                targetId=edge.target_id,
                relationType=edge.relation_type,
                label=edge.label,
                weight=edge.weight,
                evidencePageIds=edge.evidence_page_ids or [],
                createdFromBlockId=edge.created_from_block_id,
            )
            for edge in rows
        ]

    def _to_graph_node(self, node: Node) -> GraphNode:
        return GraphNode(
            id=node.id,
            title=node.title,
            notionUrl=node.notion_url,
            type=node.type,
            parentId=node.parent_id,
            ancestorIds=node.ancestor_ids or [],
            ancestorTitles=node.ancestor_titles or [],
            depth=node.depth,
            icon=node.icon,
            emoji=node.emoji,
            snippet=node.snippet,
            tags=node.tags or [],
            lastEditedTime=node.last_edited_time,
            inTrash=node.in_trash,
            extractedText=node.extracted_text,
        )

    def _neighborhood_ids(
        self,
        session: Session,
        center_node_id: str | None,
        depth: int,
    ) -> set[str]:
        if not center_node_id:
            return set()

        edges = session.scalars(
            select(Edge).where(Edge.root_page_id == self.settings.notion_root_page_id)
        ).all()

        adjacency: dict[str, set[str]] = defaultdict(set)
        for edge in edges:
            adjacency[edge.source_id].add(edge.target_id)
            adjacency[edge.target_id].add(edge.source_id)

        visited = {center_node_id}
        queue: deque[tuple[str, int]] = deque([(center_node_id, 0)])

        while queue:
            node_id, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for neighbor in adjacency.get(node_id, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append((neighbor, current_depth + 1))

        return visited
