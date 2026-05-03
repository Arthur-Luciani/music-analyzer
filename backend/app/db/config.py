from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.settings import settings

Base = declarative_base()


def get_engine():
    db_url = f"sqlite:///{settings.sessions_db_path}"
    return create_engine(
        db_url,
        connect_args={"timeout": 30, "check_same_thread": False},
        echo=False,
    )


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_session():
    """Dependency injection for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
