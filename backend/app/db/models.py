from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db.config import Base


class SessionORM(Base):
	__tablename__ = "sessions"

	id = Column(String, primary_key=True)
	session_code = Column(String, nullable=False, unique=True)
	query = Column(String, nullable=False)
	selected_track_json = Column(Text, nullable=True)
	track_title = Column(String, nullable=True)
	artist = Column(String, nullable=True)
	target_stems_json = Column(Text, nullable=False)
	state = Column(String, nullable=False)
	progress = Column(Integer, nullable=False, default=0)
	message = Column(String, nullable=False)
	stems_json = Column(Text, nullable=True)
	error = Column(Text, nullable=True)
	eta_seconds = Column(Integer, nullable=True)
	separation_device = Column(String, nullable=True)
	master_metrics_json = Column(Text, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	mix_states = relationship("SessionMixStateORM", back_populates="session", cascade="all, delete-orphan")
	exports = relationship("ExportJobORM", back_populates="session", cascade="all, delete-orphan")
	events = relationship("SessionEventORM", back_populates="session", cascade="all, delete-orphan")

	__table_args__ = (
		Index("idx_sessions_created_at", "created_at"),
		Index("idx_sessions_state", "state"),
	)


class SessionMixStateORM(Base):
	__tablename__ = "session_mix_state"

	session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True)
	payload_json = Column(Text, nullable=False)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	session = relationship("SessionORM", back_populates="mix_states")


class ExportJobORM(Base):
	__tablename__ = "export_jobs"

	id = Column(String, primary_key=True)
	session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
	preset = Column(String, nullable=False)
	format = Column(String, nullable=False)
	state = Column(String, nullable=False)
	progress = Column(Integer, nullable=False, default=0)
	output_json = Column(Text, nullable=False, default="[]")
	error = Column(Text, nullable=True)
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
	updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

	session = relationship("SessionORM", back_populates="exports")

	__table_args__ = (
		Index("idx_export_jobs_session_created", "session_id", "created_at"),
	)


class SessionEventORM(Base):
	__tablename__ = "session_events"

	id = Column(Integer, primary_key=True, autoincrement=True)
	session_id = Column(String, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
	ts = Column(DateTime, nullable=False, default=datetime.utcnow)
	stage = Column(String, nullable=False)
	level = Column(String, nullable=False)
	progress = Column(Integer, nullable=False, default=0)
	message = Column(String, nullable=False)

	session = relationship("SessionORM", back_populates="events")

	__table_args__ = (
		Index("idx_session_events_ts", "session_id", "ts"),
	)


class MarketArtistORM(Base):
	"""Um artista/banda do catálogo de MIDI de mercado. `source='catalog'` vem
	do dataset importado (ver scripts/setup_market_midi.py); `source='user_created'`
	é criado sob demanda quando um usuário confirma um artista que não existe
	no catálogo (ver plano do wizard de identidade musical)."""
	__tablename__ = "market_artists"

	id = Column(Integer, primary_key=True, autoincrement=True)
	name = Column(String, nullable=False)
	name_norm = Column(String, nullable=False, unique=True)
	source = Column(String, nullable=False, default="catalog")
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

	tracks = relationship("MarketTrackORM", back_populates="artist", cascade="all, delete-orphan")


class MarketTrackORM(Base):
	"""Uma música de um artista do catálogo. N:1 com `MarketMidiFileORM` —
	uma música pode ter mais de um arquivo MIDI candidato (variações de
	título/transcrição do mesmo dataset), o vencedor é decidido por
	alinhamento DTW em tempo de match (ver match_market_midi.py)."""
	__tablename__ = "market_tracks"

	id = Column(Integer, primary_key=True, autoincrement=True)
	artist_id = Column(Integer, ForeignKey("market_artists.id", ondelete="CASCADE"), nullable=False)
	title = Column(String, nullable=False)
	title_norm = Column(String, nullable=False)
	source = Column(String, nullable=False, default="catalog")
	created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

	artist = relationship("MarketArtistORM", back_populates="tracks")
	midi_files = relationship("MarketMidiFileORM", back_populates="track", cascade="all, delete-orphan")

	__table_args__ = (
		UniqueConstraint("artist_id", "title_norm", name="uq_market_tracks_artist_title_norm"),
		Index("idx_market_tracks_artist_id", "artist_id"),
	)


class MarketMidiFileORM(Base):
	"""Um arquivo MIDI físico candidato para uma `MarketTrackORM`.
	`has_drum_track`/`duration_seconds` ficam nulos até a primeira vez que
	o arquivo é lido durante um match (cache preguiçoso — ver
	match_market_midi.py); depois disso não é reprocessado a cada sessão."""
	__tablename__ = "market_midi_files"

	id = Column(Integer, primary_key=True, autoincrement=True)
	track_id = Column(Integer, ForeignKey("market_tracks.id", ondelete="CASCADE"), nullable=False)
	relative_path = Column(String, nullable=False, unique=True)
	has_drum_track = Column(Boolean, nullable=True)
	duration_seconds = Column(Float, nullable=True)
	indexed_at = Column(DateTime, nullable=False, default=datetime.utcnow)

	track = relationship("MarketTrackORM", back_populates="midi_files")

	__table_args__ = (
		Index("idx_market_midi_files_track_id", "track_id"),
	)
