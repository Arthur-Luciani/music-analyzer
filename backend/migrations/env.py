from pathlib import Path
import sys

from alembic import context

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.db.config import Base  # noqa: E402
from app.db import models as db_models  # noqa: F401, E402
from app.settings import settings  # noqa: E402


config = context.config
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = f"sqlite:///{settings.sessions_db_path}"
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from app.db.config import engine  # noqa: E402

    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
