"""0001_initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-04-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_counter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_session_counter_singleton"),
    )
    op.execute("INSERT INTO session_counter (id, last_value) VALUES (1, 0)")

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_code", sa.String(), nullable=False, unique=True),
        sa.Column("query", sa.String(), nullable=False),
        sa.Column("selected_track_json", sa.Text(), nullable=True),
        sa.Column("track_title", sa.String(), nullable=True),
        sa.Column("artist", sa.String(), nullable=True),
        sa.Column("target_stems_json", sa.Text(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("stems_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("eta_seconds", sa.Integer(), nullable=True),
        sa.Column("separation_device", sa.String(), nullable=True),
        sa.Column("master_metrics_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_sessions_created_at", "sessions", ["created_at"], unique=False)
    op.create_index("idx_sessions_state", "sessions", ["state"], unique=False)

    op.create_table(
        "session_mix_state",
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("preset", sa.String(), nullable=False),
        sa.Column("format", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=False, server_default=sa.text("'[]'")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "idx_export_jobs_session_created",
        "export_jobs",
        ["session_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "session_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(), nullable=False),
        sa.Column("ts", sa.DateTime(), nullable=False),
        sa.Column("stage", sa.String(), nullable=False),
        sa.Column("level", sa.String(), nullable=False),
        sa.Column("progress", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_session_events_ts", "session_events", ["session_id", "ts"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_session_events_ts", table_name="session_events")
    op.drop_table("session_events")

    op.drop_index("idx_export_jobs_session_created", table_name="export_jobs")
    op.drop_table("export_jobs")

    op.drop_table("session_mix_state")

    op.drop_index("idx_sessions_state", table_name="sessions")
    op.drop_index("idx_sessions_created_at", table_name="sessions")
    op.drop_table("sessions")

    op.drop_table("session_counter")
