"""Ensure all legacy Tenable JSON keys are removed after key renaming."""

from collections.abc import Sequence

from alembic import op

revision: str = "c2d3e4f5a6b7"
down_revision: str | Sequence[str] | None = "b8c2d4e6f0a1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_keys(table_name: str, renames: tuple[tuple[str, str], ...]) -> None:
    removed_keys = " - ".join(f"'{old}'" for old, _ in renames)
    merged_keys = " || ".join(
        "CASE "
        f"WHEN source_payload ? '{old}' OR source_payload ? '{new}' THEN "
        "jsonb_build_object("
        f"'{new}', COALESCE(source_payload -> '{new}', source_payload -> '{old}')"
        ") ELSE '{}'::jsonb END"
        for old, new in renames
    )
    predicates = " OR ".join(
        f"source_payload ? '{old}'" for old, _ in renames
    )
    op.execute(
        f"UPDATE {table_name} SET source_payload = "
        f"((source_payload - {removed_keys}) || ({merged_keys})) "
        f"WHERE source_payload IS NOT NULL AND ({predicates})"
    )


def upgrade() -> None:
    _rename_keys(
        "tenable_findings",
        (
            ("_brd_54_fields", "finding_source_fields"),
            ("_brd_missing_fields", "missing_finding_source_fields"),
            ("_brd_normalization", "normalization_metadata"),
        ),
    )
    _rename_keys("tenable_scans", (("brd_scan_fields", "scan_result_fields"),))


def downgrade() -> None:
    _rename_keys(
        "tenable_scans",
        (("scan_result_fields", "brd_scan_fields"),),
    )
    _rename_keys(
        "tenable_findings",
        (
            ("finding_source_fields", "_brd_54_fields"),
            ("missing_finding_source_fields", "_brd_missing_fields"),
            ("normalization_metadata", "_brd_normalization"),
        ),
    )
