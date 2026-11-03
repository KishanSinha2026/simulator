from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

class Settings(BaseSettings):
    data: Literal["DB", "API"] = "DB"
    database_url: str = "postgresql+psycopg://vpm360:change-me@localhost:5432/vpm360"
    tenable_database_url: str = ""
    api_base_url: str = "http://localhost:8000"
    tenable_access_key: str = ""
    tenable_secret_key: str = ""
    tenable_source_url: str = ""
    tenable_scan_results_path: str = "/rest/scanResult"
    tenable_analysis_path: str = "/rest/analysis"
    cmdb_base_url: str = "http://localhost:8000"
    cmdb_source_url: str = ""
    cmdb_database_url: str = ""
    cmdb_dataset_id: str = "BMC.ASSET"
    cmdb_username: str = "cmdb-demo"
    cmdb_password: str = "change-this-demo-password"
    cmdb_jwt_secret: str = "change-this-random-signing-key"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
if not settings.cmdb_database_url:
    settings.cmdb_database_url = make_url(settings.database_url).set(database="vpm360_cmdb").render_as_string(hide_password=False)

