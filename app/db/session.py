
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

# SecretStr prevents the configured database URL from being
# accidentally exposed when logging the settings object.
DATABASE_URL = settings.database_url.get_secret_value()

engine = create_engine(
    DATABASE_URL,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    class_=Session,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """Provide a database session and always close it."""
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
