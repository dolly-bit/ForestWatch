"""initial schema: jobs and change_events

Revision ID: 0001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("method", sa.String(16), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("n_events", sa.Integer(), nullable=False),
        sa.Column("total_area_ha", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_table(
        "change_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("min_lon", sa.Float(), nullable=False),
        sa.Column("min_lat", sa.Float(), nullable=False),
        sa.Column("max_lon", sa.Float(), nullable=False),
        sa.Column("max_lat", sa.Float(), nullable=False),
        sa.Column("area_ha", sa.Float(), nullable=False),
        sa.Column("n_pixels", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_change_events_job_id", "change_events", ["job_id"])
    op.create_index("ix_change_events_status", "change_events", ["status"])
    op.create_index("ix_change_events_bbox", "change_events", ["min_lon", "min_lat", "max_lon", "max_lat"])


def downgrade() -> None:
    op.drop_table("change_events")
    op.drop_table("jobs")
