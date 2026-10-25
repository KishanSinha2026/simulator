
import json
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.providers.base import BaseProvider


class JsonProvider(BaseProvider):
    """Load and manipulate simulator records stored in JSON files."""

    def __init__(self, fixture_name: str) -> None:
        settings = get_settings()
        fixture_dir = Path(settings.fixture_dir)

        if not fixture_dir.is_absolute():
            fixture_dir = Path.cwd() / fixture_dir

        self.file_path = fixture_dir / fixture_name
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_records(self) -> list[dict[str, Any]]:
        if not self.file_path.exists():
            return []

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in fixture file: {self.file_path}"
            ) from exc

        if not isinstance(data, list):
            raise ValueError(
                f"Fixture must contain a JSON array: {self.file_path}"
            )

        if not all(isinstance(item, dict) for item in data):
            raise ValueError(
                f"Every fixture record must be a JSON object: {self.file_path}"
            )

        return data

    def _write_records(self, records: list[dict[str, Any]]) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.file_path.with_suffix(
            self.file_path.suffix + ".tmp"
        )

        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False)
            file.write("\n")

        temporary_path.replace(self.file_path)

    def get_by_id(self, record_id: str) -> dict[str, Any] | None:
        for record in self._read_records():
            source_id = record.get("id", record.get("source_id"))
            if source_id is not None and str(source_id) == str(record_id):
                return record

        return None

    def list_records(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
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
        if not payload:
            raise ValueError("payload cannot be empty")

        records = self._read_records()
        record = dict(payload)

        record_id = record.get("id", record.get("source_id"))
        if record_id is not None:
            if any(
                str(existing.get("id", existing.get("source_id")))
                == str(record_id)
                for existing in records
            ):
                raise ValueError(
                    f"Record with identifier {record_id!r} already exists"
                )

        records.append(record)
        self._write_records(records)

        return record
