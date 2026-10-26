"""Shared JSON fixture provider for simulator integrations."""

import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.providers.base import BaseProvider


class JsonProvider(BaseProvider):
    """Load, query, and update records stored in JSON fixture files."""

    def __init__(self, fixture_name: str) -> None:
        settings = get_settings()

        fixture_root = Path(settings.fixture_dir).resolve()
        requested_path = Path(fixture_name)

        if requested_path.is_absolute():
            raise ValueError(
                "fixture_name must be a relative path within FIXTURE_DIR"
            )

        self.file_path = (
            fixture_root / requested_path
        ).resolve()

        # Prevent paths such as ../../outside.json from escaping
        # the configured fixture directory.
        try:
            self.file_path.relative_to(fixture_root)
        except ValueError as exc:
            raise ValueError(
                "Fixture path must remain inside FIXTURE_DIR"
            ) from exc

        if not self.file_path.name:
            raise ValueError("A fixture filename is required")

    def _read_records(self) -> list[dict[str, Any]]:
        """Read and validate an array of JSON objects."""
        if not self.file_path.exists():
            path_str = str(self.file_path)
            if "\\itsm\\" in path_str or "/itsm/" in path_str:
                alt = Path(path_str.replace("\\itsm\\", "\\istm\\").replace("/itsm/", "/istm/"))
                if alt.exists():
                    self.file_path = alt
            elif "\\istm\\" in path_str or "/istm/" in path_str:
                alt = Path(path_str.replace("\\istm\\", "\\itsm\\").replace("/istm/", "/itsm/"))
                if alt.exists():
                    self.file_path = alt

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Required fixture file was not found: {self.file_path}"
            )

        if not self.file_path.is_file():
            raise ValueError(
                f"Fixture path is not a file: {self.file_path}"
            )

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in fixture file "
                f"{self.file_path} at line {exc.lineno}, "
                f"column {exc.colno}"
            ) from exc

        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Fixture file is not valid UTF-8: {self.file_path}"
            ) from exc

        if not isinstance(data, list):
            raise ValueError(
                f"Fixture must contain a JSON array: {self.file_path}"
            )

        if not all(isinstance(item, dict) for item in data):
            raise ValueError(
                "Every fixture record must be a JSON object: "
                f"{self.file_path}"
            )

        self._validate_record_ids(data)

        return data

    @staticmethod
    def _validate_record_ids(
        records: list[dict[str, Any]],
    ) -> None:
        """Reject missing, blank, or duplicated generic record IDs."""
        seen: set[str] = set()

        for index, record in enumerate(records):
            record_id = record.get("id")

            if record_id is None:
                record_id = record.get("source_id")

            if record_id is None or not str(record_id).strip():
                raise ValueError(
                    f"Fixture record at index {index} has no valid "
                    "'id' or 'source_id'"
                )

            normalized_id = str(record_id)

            if normalized_id in seen:
                raise ValueError(
                    f"Duplicate fixture record ID {normalized_id!r} "
                    f"in {index + 1} or more records"
                )

            seen.add(normalized_id)

    def _write_records(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Write validated records using an atomic file replacement."""
        if not isinstance(records, list):
            raise ValueError("records must be a list")

        if not all(isinstance(item, dict) for item in records):
            raise ValueError(
                "Every record to write must be a JSON object"
            )

        self._validate_record_ids(records)

        if not self.file_path.exists():
            raise FileNotFoundError(
                f"Cannot update a missing fixture file: {self.file_path}"
            )

        temporary_path = self.file_path.with_suffix(
            self.file_path.suffix + ".tmp"
        )

        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(
                    records,
                    file,
                    indent=2,
                    ensure_ascii=False,
                    allow_nan=False,
                )
                file.write("\n")

            temporary_path.replace(self.file_path)

        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def get_by_id(
        self,
        record_id: str,
    ) -> dict[str, Any] | None:
        """Return a record by its generic fixture identifier."""
        if not str(record_id).strip():
            raise ValueError("record_id cannot be blank")

        for record in self._read_records():
            current_id = record.get("id")

            if current_id is None:
                current_id = record.get("source_id")

            if (
                current_id is not None
                and str(current_id) == str(record_id)
            ):
                return record

        return None

    def list_records(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List records using exact-match filters and pagination."""
        if limit < 1:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        records = self._read_records()

        if filters:
            records = [
                record
                for record in records
                if all(
                    record.get(key) == expected
                    for key, expected in filters.items()
                )
            ]

        return records[offset : offset + limit]

    def create_record(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Append a new record after validating its identifier."""
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload must be a non-empty dictionary")

        record = dict(payload)

        record_id = record.get("id")

        if record_id is None:
            record_id = record.get("source_id")

        if record_id is None or not str(record_id).strip():
            raise ValueError(
                "A new record must contain a non-empty 'id' "
                "or 'source_id'"
            )

        record_id = str(record_id)

        records = self._read_records()

        for existing in records:
            existing_id = existing.get("id")

            if existing_id is None:
                existing_id = existing.get("source_id")

            if (
                existing_id is not None
                and str(existing_id) == record_id
            ):
                raise ValueError(
                    f"Record with identifier {record_id!r} already exists"
                )

        records.append(record)
        self._write_records(records)

        return record