"""SQLite via SQLAlchemy 2.0. Swap `create_engine` URL for PostgreSQL later -
everything else (session handling, models) stays identical."""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

# check_same_thread=False: the pipeline runs in FastAPI BackgroundTasks threads.
engine = create_engine(
    f"sqlite:///{config.DB_PATH}",
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

Base = declarative_base()


def get_db():
    """FastAPI dependency - one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
