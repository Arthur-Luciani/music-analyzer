from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
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
