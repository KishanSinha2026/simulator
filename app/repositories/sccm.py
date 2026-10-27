"""Database repositories for SCCM 2509 devices, collections, deployments, and runs."""

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.sccm import (
    SCCMCollection,
    SCCMDeployment,
    SCCMDeploymentAssetDetail,
    SCCMDeploymentRun,
    SCCMDevice,
)
from app.repositories.base import BaseRepository


class SCCMDeviceRepository(BaseRepository[SCCMDevice]):
    """Database operations for SCCM devices/resources."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SCCMDevice)

    def get_by_resource_id(self, resource_id: str) -> SCCMDevice | None:
        """Find device by external ResourceID."""
        statement = select(SCCMDevice).where(
            SCCMDevice.resource_id == resource_id.strip()
        )
        return self.db.scalars(statement).first()

    def list_by_collection(
        self,
        collection_id: str,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[SCCMDevice]:
        """Find devices belonging to a target collection."""
        statement = (
            select(SCCMDevice)
            .where(SCCMDevice.collection_id == collection_id.strip())
            .order_by(SCCMDevice.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(statement).all())


class SCCMCollectionRepository(BaseRepository[SCCMCollection]):
    """Database operations for SCCM device collections."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SCCMCollection)

    def get_by_collection_id(self, collection_id: str) -> SCCMCollection | None:
        """Find collection by external CollectionID."""
        statement = select(SCCMCollection).where(
            SCCMCollection.collection_id == collection_id.strip()
        )
        return self.db.scalars(statement).first()


class SCCMDeploymentRepository(BaseRepository[SCCMDeployment]):
    """Database operations for SCCM software update group deployments."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SCCMDeployment)

    def get_by_assignment_id(self, assignment_id: str) -> SCCMDeployment | None:
        """Find deployment policy by external AssignmentID."""
        statement = select(SCCMDeployment).where(
            SCCMDeployment.assignment_id == assignment_id.strip()
        )
        return self.db.scalars(statement).first()


class SCCMDeploymentRunRepository(BaseRepository[SCCMDeploymentRun]):
    """Database operations for guarded SCCM patch execution runs."""

    def __init__(self, db: Session) -> None:
        super().__init__(db, SCCMDeploymentRun)

    def get_by_run_id(self, run_id: str) -> SCCMDeploymentRun | None:
        """Find deployment run by unique run_id with pre-loaded asset details."""
        statement = (
            select(SCCMDeploymentRun)
            .options(joinedload(SCCMDeploymentRun.asset_details))
            .where(SCCMDeploymentRun.run_id == run_id.strip())
        )
        return self.db.scalars(statement).first()

    def get_by_id_with_details(self, run_id_int: int) -> SCCMDeploymentRun | None:
        """Find deployment run by primary key with pre-loaded asset details."""
        statement = (
            select(SCCMDeploymentRun)
            .options(joinedload(SCCMDeploymentRun.asset_details))
            .where(SCCMDeploymentRun.id == run_id_int)
        )
        return self.db.scalars(statement).first()
