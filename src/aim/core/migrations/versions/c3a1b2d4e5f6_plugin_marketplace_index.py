"""plugin and marketplace index

Revision ID: c3a1b2d4e5f6
Revises: b7e1c0a4d2f3
Create Date: 2026-06-25 16:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel
from alembic import op

revision: str = "c3a1b2d4e5f6"
down_revision: str | None = "b7e1c0a4d2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "marketplaceindex",
        sa.Column("qualified_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("repo_alias", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("marketplace_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("manifest_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("owner_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("owner_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("indexed_at_sha", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("qualified_name"),
    )
    with op.batch_alter_table("marketplaceindex", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_marketplaceindex_marketplace_name"),
            ["marketplace_name"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_marketplaceindex_repo_alias"), ["repo_alias"], unique=False
        )

    op.create_table(
        "pluginindex",
        sa.Column("qualified_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("repo_alias", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("plugin_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("flavor", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("source_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("marketplace_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("version", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("keywords", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("indexed_at_sha", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.PrimaryKeyConstraint("qualified_name"),
    )
    with op.batch_alter_table("pluginindex", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_pluginindex_plugin_name"), ["plugin_name"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_pluginindex_repo_alias"), ["repo_alias"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("pluginindex", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_pluginindex_repo_alias"))
        batch_op.drop_index(batch_op.f("ix_pluginindex_plugin_name"))

    op.drop_table("pluginindex")

    with op.batch_alter_table("marketplaceindex", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_marketplaceindex_repo_alias"))
        batch_op.drop_index(batch_op.f("ix_marketplaceindex_marketplace_name"))

    op.drop_table("marketplaceindex")
