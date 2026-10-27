"""SQLAlchemy model package.

Import model modules here so their tables are registered with
Base.metadata for application use and Alembic metadata discovery.
"""

from app.models import audit, cmdb, itsm, satellite, sccm, squad1, tenable
from app.models.itsm import (
    ITSMChange,
    ITSMChangeHistory,
    ITSMWorklog,
)
from app.models.sccm import (
    SCCMCollection,
    SCCMDeployment,
    SCCMDeploymentAssetDetail,
    SCCMDeploymentRun,
    SCCMDevice,
)
from app.models.squad1 import Squad1Vulnerability

__all__ = [
    "audit",
    "cmdb",
    "itsm",
    "satellite",
    "sccm",
    "squad1",
    "tenable",
    "ITSMChange",
    "ITSMChangeHistory",
    "ITSMWorklog",
    "SCCMCollection",
    "SCCMDeployment",
    "SCCMDeploymentAssetDetail",
    "SCCMDeploymentRun",
    "SCCMDevice",
    "Squad1Vulnerability",
]