from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    root_page_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512))
    notion_url: Mapped[str] = mapped_column(String(2048))
    type: Mapped[str] = mapped_column(String(32), index=True)
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    ancestor_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    ancestor_titles: Mapped[list[str]] = mapped_column(JSON, default=list)
    depth: Mapped[int] = mapped_column(Integer)
    icon: Mapped[str | None] = mapped_column(String(255), nullable=True)
    emoji: Mapped[str | None] = mapped_column(String(64), nullable=True)
    snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_edited_time: Mapped[str] = mapped_column(String(64))
    in_trash: Mapped[bool] = mapped_column(Boolean, default=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    root_page_id: Mapped[str] = mapped_column(String(64), index=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True)
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    relation_type: Mapped[str] = mapped_column(String(64), index=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    evidence_page_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_from_block_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class SyncCheckpoint(Base):
    __tablename__ = "sync_checkpoint"

    root_page_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_full_sync_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="idle")
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    node_count: Mapped[int] = mapped_column(Integer, default=0)
    edge_count: Mapped[int] = mapped_column(Integer, default=0)


class SyncTask(Base):
    __tablename__ = "sync_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_type: Mapped[str] = mapped_column(String(64), default="full_reconcile")
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict[str, str] | None] = mapped_column(JSON, nullable=True, default=dict)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class AppConfig(Base):
    __tablename__ = "app_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    notion_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    notion_root_page_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notion_use_fixtures: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    notion_fixture_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )
