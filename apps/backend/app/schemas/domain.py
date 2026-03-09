from typing import Literal

from pydantic import BaseModel, Field

NodeType = Literal["person", "topic", "project", "artifact", "unknown"]
RelationType = Literal["mention", "link_to_page", "structured_relation", "backlink"]


class GraphNode(BaseModel):
    id: str
    title: str
    notionUrl: str
    type: NodeType = "unknown"
    parentId: str | None = None
    ancestorIds: list[str] = Field(default_factory=list)
    ancestorTitles: list[str] = Field(default_factory=list)
    depth: int
    icon: str | None = None
    emoji: str | None = None
    snippet: str | None = None
    tags: list[str] = Field(default_factory=list)
    lastEditedTime: str
    inTrash: bool = False
    extractedText: str | None = None


class GraphEdge(BaseModel):
    id: str
    sourceId: str
    targetId: str
    relationType: RelationType
    label: str | None = None
    weight: float = 1.0
    evidencePageIds: list[str] = Field(default_factory=list)
    createdFromBlockId: str | None = None
