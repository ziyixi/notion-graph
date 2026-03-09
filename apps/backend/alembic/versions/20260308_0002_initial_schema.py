"""initial schema (squashed)

Revision ID: 20260308_0002
Revises:
Create Date: 2026-03-08
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260308_0002"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "nodes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("root_page_id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("notion_url", sa.String(length=2048), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("parent_id", sa.String(length=64), nullable=True),
        sa.Column("ancestor_ids", sa.JSON(), nullable=False),
        sa.Column("ancestor_titles", sa.JSON(), nullable=False),
        sa.Column("depth", sa.Integer(), nullable=False),
        sa.Column("icon", sa.String(length=255), nullable=True),
        sa.Column("emoji", sa.String(length=64), nullable=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("last_edited_time", sa.String(length=64), nullable=False),
        sa.Column("in_trash", sa.Boolean(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_nodes_parent_id"), "nodes", ["parent_id"], unique=False)
    op.create_index(op.f("ix_nodes_root_page_id"), "nodes", ["root_page_id"], unique=False)
    op.create_index(op.f("ix_nodes_type"), "nodes", ["type"], unique=False)

    op.create_table(
        "edges",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("root_page_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("relation_type", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=True),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("evidence_page_ids", sa.JSON(), nullable=False),
        sa.Column("created_from_block_id", sa.String(length=64), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_edges_relation_type"), "edges", ["relation_type"], unique=False)
    op.create_index(op.f("ix_edges_root_page_id"), "edges", ["root_page_id"], unique=False)
    op.create_index(op.f("ix_edges_source_id"), "edges", ["source_id"], unique=False)
    op.create_index(op.f("ix_edges_target_id"), "edges", ["target_id"], unique=False)

    op.create_table(
        "sync_checkpoint",
        sa.Column("root_page_id", sa.String(length=64), nullable=False),
        sa.Column("last_full_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("node_count", sa.Integer(), nullable=False),
        sa.Column("edge_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("root_page_id"),
    )

    op.create_table(
        "sync_tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sync_tasks_status"), "sync_tasks", ["status"], unique=False)

    op.create_table(
        "app_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("notion_token", sa.Text(), nullable=True),
        sa.Column("notion_root_page_id", sa.String(length=64), nullable=True),
        sa.Column("notion_use_fixtures", sa.Boolean(), nullable=True),
        sa.Column("notion_fixture_path", sa.String(length=2048), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("app_config")

    op.drop_index(op.f("ix_sync_tasks_status"), table_name="sync_tasks")
    op.drop_table("sync_tasks")

    op.drop_table("sync_checkpoint")

    op.drop_index(op.f("ix_edges_target_id"), table_name="edges")
    op.drop_index(op.f("ix_edges_source_id"), table_name="edges")
    op.drop_index(op.f("ix_edges_root_page_id"), table_name="edges")
    op.drop_index(op.f("ix_edges_relation_type"), table_name="edges")
    op.drop_table("edges")

    op.drop_index(op.f("ix_nodes_type"), table_name="nodes")
    op.drop_index(op.f("ix_nodes_root_page_id"), table_name="nodes")
    op.drop_index(op.f("ix_nodes_parent_id"), table_name="nodes")
    op.drop_table("nodes")
