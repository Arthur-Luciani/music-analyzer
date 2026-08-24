"""0002_market_midi_catalog

Revision ID: 0002_market_midi_catalog
Revises: 0001_initial_schema
Create Date: 2026-08-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_market_midi_catalog"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "market_artists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_norm", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="catalog"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("name_norm", name="uq_market_artists_name_norm"),
    )

    op.create_table(
        "market_tracks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("artist_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("title_norm", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="catalog"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["artist_id"], ["market_artists.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("artist_id", "title_norm", name="uq_market_tracks_artist_title_norm"),
    )
    op.create_index("idx_market_tracks_artist_id", "market_tracks", ["artist_id"], unique=False)

    op.create_table(
        "market_midi_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("relative_path", sa.String(), nullable=False),
        sa.Column("has_drum_track", sa.Boolean(), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("indexed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["track_id"], ["market_tracks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("relative_path", name="uq_market_midi_files_relative_path"),
    )
    op.create_index("idx_market_midi_files_track_id", "market_midi_files", ["track_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_market_midi_files_track_id", table_name="market_midi_files")
    op.drop_table("market_midi_files")

    op.drop_index("idx_market_tracks_artist_id", table_name="market_tracks")
    op.drop_table("market_tracks")

    op.drop_table("market_artists")
