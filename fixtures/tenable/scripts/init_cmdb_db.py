"""Create the separate CMDB PostgreSQL database if it does not already exist."""
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.config import settings

def main():
    target = make_url(settings.cmdb_database_url)
    database_name = target.database
    admin_url = make_url(settings.database_url).set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            exists = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database_name})
            if not exists:
                safe_name = database_name.replace('"', '""')
                connection.exec_driver_sql(f'CREATE DATABASE "{safe_name}"')
        print(f"CMDB database ready: {database_name}")
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()

