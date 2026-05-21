"""Initial schema: services and deployments tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "services",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("team", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_table(
        "deployments",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "service_name",
            sa.String(100),
            sa.ForeignKey("services.name"),
            nullable=False,
        ),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("environment", sa.String(20), nullable=False),
        sa.Column("commit_sha", sa.String(40), nullable=False),
        sa.Column("deployer", sa.String(100), nullable=False),
        sa.Column("commit_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deployed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default=sa.text("'success'"),
        ),
        sa.Column("failure_detected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recovered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    # Composite index for efficient time-range queries per service
    op.create_index(
        "ix_deployments_service_deployed_at",
        "deployments",
        ["service_name", "deployed_at"],
    )

    # Partial index for failure/recovery lookups
    op.create_index(
        "ix_deployments_failed_status",
        "deployments",
        ["status"],
        postgresql_where=sa.text("status IN ('failed', 'recovered')"),
    )


def downgrade() -> None:
    op.drop_index("ix_deployments_failed_status", table_name="deployments")
    op.drop_index("ix_deployments_service_deployed_at", table_name="deployments")
    op.drop_table("deployments")
    op.drop_table("services")
