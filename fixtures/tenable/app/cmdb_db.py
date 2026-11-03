from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import settings

cmdb_engine = create_engine(settings.cmdb_database_url, pool_pre_ping=True)
CMDBSession = sessionmaker(bind=cmdb_engine, autoflush=False, expire_on_commit=False)

