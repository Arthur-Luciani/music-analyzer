"""0003_session_music_identity

Revision ID: 0003_session_music_identity
Revises: 0002_market_midi_catalog
Create Date: 2026-08-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_session_music_identity"
down_revision = "0002_market_midi_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_music_identity",
        sa.Column("session_id", sa.String(), primary_key=True),
        sa.Column("artist_id", sa.Integer(), nullable=True),
        sa.Column("artist_text", sa.String(), nullable=False),
        sa.Column("title_text", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=True),
        sa.Column("track_id", sa.Integer(), nullable=True),
        sa.Column("resolved_midi_file_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["artist_id"], ["market_artists.id"]),
        sa.ForeignKeyConstraint(["track_id"], ["market_tracks.id"]),
        sa.ForeignKeyConstraint(["resolved_midi_file_id"], ["market_midi_files.id"]),
    )


def downgrade() -> None:
    op.drop_table("session_music_identity")
