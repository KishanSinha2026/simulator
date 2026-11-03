from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

write_engine = create_engine(settings.database_url, pool_pre_ping=True)
WriteSessionLocal = sessionmaker(bind=write_engine, autoflush=False, expire_on_commit=False)
tenable_read_engine = create_engine(settings.tenable_database_url or settings.database_url, pool_pre_ping=True)
TenableReadSessionLocal = sessionmaker(bind=tenable_read_engine, autoflush=False, expire_on_commit=False)

# Backwards-compatible name for read-only API code.
SessionLocal = TenableReadSessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

