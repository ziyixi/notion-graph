import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.domain import GraphEdge

NODE_TYPES = {"person", "topic", "project", "artifact", "unknown"}
ANCESTOR_TYPE_MAP = {
    "people": "person",
    "person": "person",
    "topics": "topic",
    "topic": "topic",
    "projects": "project",
    "project": "project",
    "artifacts": "artifact",
    "artifact": "artifact",
}

EXPLICIT_TYPE_RE = re.compile(r"^\s*type\s*:\s*([A-Za-z_\- ]+)\s*$", re.IGNORECASE)
TEMPLATE_TYPE_RE = re.compile(r"^\s*template\s*:\s*([A-Za-z_\- ]+)\s*$", re.IGNORECASE)
STRUCTURED_REL_RE = re.compile(r"^\s*([\w\-\s]+?)\s*(?:->|→)\s*@?.+$")


@dataclass
class BlockParseResult:
    edges: list[GraphEdge] = field(default_factory=list)
    child_page_ids: list[str] = field(default_factory=list)
    extracted_text: list[str] = field(default_factory=list)


def deterministic_edge_id(
    source_id: str,
    target_id: str,
    relation_type: str,
    label: str | None,
    block_id: str | None,
) -> str:
    digest = hashlib.sha1(
        "|".join(
            [
                source_id,
                target_id,
                relation_type,
                label or "",
                block_id or "",
            ]
        ).encode("utf-8")
    ).hexdigest()
    return digest


def normalize_type(raw: str | None) -> str | None:
    if raw is None:
        return None
    token = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if token in NODE_TYPES:
        return token
    if token.endswith("s") and token[:-1] in NODE_TYPES:
        return token[:-1]
    return None


def infer_node_type(title: str, ancestor_titles: list[str], extracted_lines: list[str]) -> str:
    for line in extracted_lines:
        match = EXPLICIT_TYPE_RE.match(line)
        if match:
            explicit = normalize_type(match.group(1))
            if explicit:
                return explicit

    for line in extracted_lines:
        match = TEMPLATE_TYPE_RE.match(line)
        if match:
            template = normalize_type(match.group(1))
            if template:
                return template

    for ancestor in reversed(ancestor_titles):
        key = ancestor.strip().lower()
        if key in ANCESTOR_TYPE_MAP:
            return ANCESTOR_TYPE_MAP[key]

    title_lower = title.lower()
    if any(token in title_lower for token in ["paper", "report", "meeting", "note", "artifact"]):
        return "artifact"

    return "unknown"


def _block_rich_text(block: dict[str, Any]) -> list[dict[str, Any]]:
    block_type = block.get("type")
    if not block_type:
        return []

    payload = block.get(block_type, {})
    rich_text = payload.get("rich_text", [])
    if isinstance(rich_text, list):
        return rich_text
    return []


def _plain_text_from_rich_text(rich_text: list[dict[str, Any]]) -> str:
    parts = [segment.get("plain_text", "") for segment in rich_text]
    return "".join(parts).strip()


def _mention_page_ids(rich_text: list[dict[str, Any]]) -> list[str]:
    page_ids: list[str] = []
    for segment in rich_text:
        if segment.get("type") != "mention":
            continue
        mention = segment.get("mention", {})
        if mention.get("type") != "page":
            continue
        page_id = mention.get("page", {}).get("id")
        if page_id:
            page_ids.append(page_id)
    return page_ids


def _normalize_label(raw: str) -> str:
    label = re.sub(r"\s+", "_", raw.strip().lower())
    return re.sub(r"[^a-z0-9_\-]", "", label)


def parse_block_edges(source_page_id: str, block: dict[str, Any]) -> BlockParseResult:
    result = BlockParseResult()

    block_id = block.get("id")
    block_type = block.get("type")

    if block_type == "child_page" and block_id:
        result.child_page_ids.append(block_id)

    rich_text = _block_rich_text(block)
    plain_text = _plain_text_from_rich_text(rich_text)
    if plain_text:
        result.extracted_text.append(plain_text)

    mention_page_ids = _mention_page_ids(rich_text)
    structured_target_ids: set[str] = set()

    if plain_text and mention_page_ids:
        match = STRUCTURED_REL_RE.match(plain_text)
        if match:
            label = _normalize_label(match.group(1))
            for target_page_id in mention_page_ids:
                edge_id = deterministic_edge_id(
                    source_page_id,
                    target_page_id,
                    "structured_relation",
                    label,
                    block_id,
                )
                result.edges.append(
                    GraphEdge(
                        id=edge_id,
                        sourceId=source_page_id,
                        targetId=target_page_id,
                        relationType="structured_relation",
                        label=label,
                        createdFromBlockId=block_id,
                    )
                )
                structured_target_ids.add(target_page_id)

    for target_page_id in mention_page_ids:
        if target_page_id in structured_target_ids:
            continue
        edge_id = deterministic_edge_id(source_page_id, target_page_id, "mention", None, block_id)
        result.edges.append(
            GraphEdge(
                id=edge_id,
                sourceId=source_page_id,
                targetId=target_page_id,
                relationType="mention",
                createdFromBlockId=block_id,
            )
        )

    if block_type == "link_to_page":
        page_id = block.get("link_to_page", {}).get("page_id")
        if page_id:
            edge_id = deterministic_edge_id(source_page_id, page_id, "link_to_page", None, block_id)
            result.edges.append(
                GraphEdge(
                    id=edge_id,
                    sourceId=source_page_id,
                    targetId=page_id,
                    relationType="link_to_page",
                    createdFromBlockId=block_id,
                )
            )

    return result
