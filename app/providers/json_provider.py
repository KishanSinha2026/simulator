"""Shared JSON fixture provider for simulator integrations with caching and idempotency."""

from __future__ import annotations

import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from app.core.config import get_settings
from app.providers.base import BaseProvider


# Thread-safe global cache for parsed fixture records: path -> (mtime, records)
_FIXTURE_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_FIXTURE_LOCK = RLock()


class JsonProvider(BaseProvider):
    """Load, query, and update records stored in JSON fixture files with idempotency and caching."""

    def __init__(self, fixture_name: str) -> None:
        settings = get_settings()

        fixture_root = Path(settings.fixture_dir).resolve()
        requested_path = Path(fixture_name)

        if requested_path.is_absolute():
            raise ValueError(
                "fixture_name must be a relative path within FIXTURE_DIR"
            )

        self.file_path = (fixture_root / requested_path).resolve()

        # Prevent paths such as ../../outside.json from escaping
        try:
            self.file_path.relative_to(fixture_root)
        except ValueError as exc:
            raise ValueError(
                "Fixture path must remain inside FIXTURE_DIR"
            ) from exc

        if not self.file_path.name:
            raise ValueError("A fixture filename is required")

    def _resolve_existing_path(self) -> Path:
        """Resolve fixture path, including itsm/istm aliases if necessary."""
        if not self.file_path.exists():
            path_str = str(self.file_path)
            if "\\itsm\\" in path_str or "/itsm/" in path_str:
                alt = Path(path_str.replace("\\itsm\\", "\\istm\\").replace("/itsm/", "/istm/"))
                if alt.exists():
                    self.file_path = alt
            elif "\\istm\\" in path_str or "/istm/" in path_str:
                alt = Path(path_str.replace("\\istm\\", "\\itsm\\").replace("/itsm/", "/itsm/"))
                if alt.exists():
                    self.file_path = alt

        return self.file_path

    @staticmethod
    def _extract_record_id(record: dict[str, Any]) -> str | None:
        """Extract primary or natural identifier from a record."""
        for key in (
            "id",
            "source_id",
            "source_finding_id",
            "source_instance_id",
            "source_change_id",
            "source_host_id",
            "source_template_id",
            "source_scan_id",
            "source_worklog_id",
        ):
            val = record.get(key)
            if val is not None and str(val).strip():
                return str(val).strip()
        return None

    def _read_records(self) -> list[dict[str, Any]]:
        """Read and validate an array of JSON objects with mtime-based memory caching."""
        target_path = self._resolve_existing_path()

        if not target_path.exists():
            raise FileNotFoundError(
                f"Required fixture file was not found: {target_path}"
            )

        if not target_path.is_file():
            raise ValueError(
                f"Fixture path is not a file: {target_path}"
            )

        cache_key = str(target_path)
        current_mtime = target_path.stat().st_mtime

        with _FIXTURE_LOCK:
            if cache_key in _FIXTURE_CACHE:
                cached_mtime, cached_records = _FIXTURE_CACHE[cache_key]
                if cached_mtime == current_mtime:
                    # Return shallow copy to protect cached structure while maintaining speed
                    return [dict(item) for item in cached_records]

        try:
            with target_path.open("r", encoding="utf-8") as file:
                data = json.load(file)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid JSON in fixture file "
                f"{target_path} at line {exc.lineno}, column {exc.colno}"
            ) from exc

        except UnicodeDecodeError as exc:
            raise ValueError(
                f"Fixture file is not valid UTF-8: {target_path}"
            ) from exc

        if not isinstance(data, list):
            raise ValueError(
                f"Fixture must contain a JSON array: {target_path}"
            )

        if not all(isinstance(item, dict) for item in data):
            raise ValueError(
                f"Every fixture record must be a JSON object: {target_path}"
            )

        # Idempotently deduplicate any duplicated records by their identifier
        deduped_records = self._deduplicate_records(data)

        with _FIXTURE_LOCK:
            _FIXTURE_CACHE[cache_key] = (current_mtime, [dict(item) for item in deduped_records])

        return [dict(item) for item in deduped_records]

    @classmethod
    def _deduplicate_records(
        cls,
        records: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Idempotently deduplicate records by identifier, keeping latest record."""
        seen_keys: dict[str, dict[str, Any]] = {}
        unkeyed: list[dict[str, Any]] = []

        for record in records:
            rec_id = cls._extract_record_id(record)
            if rec_id is not None:
                # Upsert/merge record into dictionary
                if rec_id in seen_keys:
                    seen_keys[rec_id].update(record)
                else:
                    seen_keys[rec_id] = dict(record)
            else:
                unkeyed.append(record)

        return list(seen_keys.values()) + unkeyed

    def _write_records(
        self,
        records: list[dict[str, Any]],
    ) -> None:
        """Write records using an atomic file replacement and invalidate cache."""
        if not isinstance(records, list):
            raise ValueError("records must be a list")

        if not all(isinstance(item, dict) for item in records):
            raise ValueError("Every record to write must be a JSON object")

        target_path = self._resolve_existing_path()

        if not target_path.exists():
            raise FileNotFoundError(
                f"Cannot update a missing fixture file: {target_path}"
            )

        # Deduplicate before writing
        clean_records = self._deduplicate_records(records)

        temporary_path = target_path.with_suffix(target_path.suffix + ".tmp")

        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                # Use compact format for large datasets (>1000 items) to optimize I/O and memory
                if len(clean_records) > 1000:
                    json.dump(
                        clean_records,
                        file,
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                else:
                    json.dump(
                        clean_records,
                        file,
                        indent=2,
                        ensure_ascii=False,
                        allow_nan=False,
                    )
                file.write("\n")

            temporary_path.replace(target_path)

            # Update cache with fresh write
            with _FIXTURE_LOCK:
                _FIXTURE_CACHE[str(target_path)] = (
                    target_path.stat().st_mtime,
                    [dict(item) for item in clean_records],
                )

        finally:
            if temporary_path.exists():
                try:
                    temporary_path.unlink()
                except OSError:
                    pass

    def get_by_id(
        self,
        record_id: str,
    ) -> dict[str, Any] | None:
        """Return a record by its generic or business identifier."""
        if not str(record_id).strip():
            raise ValueError("record_id cannot be blank")

        search_id = str(record_id).strip()

        for record in self._read_records():
            rec_id = self._extract_record_id(record)
            if rec_id is not None and rec_id == search_id:
                return record

        return None

    def list_records(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """List records using exact-match filters and pagination up to 50k."""
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
        """Idempotently insert or update a record in the JSON fixture."""
        if not isinstance(payload, dict) or not payload:
            raise ValueError("payload must be a non-empty dictionary")

        record = dict(payload)
        record_id = self._extract_record_id(record)

        if record_id is None:
            raise ValueError(
                "A record must contain an identifier (e.g. 'id' or 'source_id')"
            )

        records = self._read_records()
        matched = False

        for i, existing in enumerate(records):
            existing_id = self._extract_record_id(existing)
            if existing_id is not None and existing_id == record_id:
                # Idempotent update
                records[i].update(record)
                matched = True
                break

        if not matched:
            records.append(record)

        self._write_records(records)
        return record

    def upsert_records(
        self,
        payloads: list[dict[str, Any]],
    ) -> int:
        """Batch upsert thousands of records idempotently in a single file operation."""
        if not payloads:
            return 0

        records = self._read_records()
        index_by_id: dict[str, int] = {}

        for i, existing in enumerate(records):
            eid = self._extract_record_id(existing)
            if eid:
                index_by_id[eid] = i

        upserted_count = 0
        for item in payloads:
            if not isinstance(item, dict):
                continue
            item_id = self._extract_record_id(item)
            if not item_id:
                continue

            if item_id in index_by_id:
                records[index_by_id[item_id]].update(item)
            else:
                index_by_id[item_id] = len(records)
                records.append(dict(item))
            upserted_count += 1

        self._write_records(records)
        return upserted_count