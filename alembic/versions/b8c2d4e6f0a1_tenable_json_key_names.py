"""Rename internal Tenable JSON keys to source-oriented names."""

from collections.abc import Sequence

from alembic import op

revision: str = "b8c2d4e6f0a1"
down_revision: str | Sequence[str] | None = "d14c7a90b2e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _rename_keys(table_name: str, renames: tuple[tuple[str, str], ...]) -> None:
    """Rename JSONB keys while preserving any already-migrated value."""
    json_expr = "source_payload"
    predicates: list[str] = []

    for old_key, new_key in renames:
        predicates.append(f"source_payload ? '{old_key}'")
        json_expr = (
            f"({json_expr} - '{old_key}') || "
            "CASE "
            f"WHEN source_payload ? '{old_key}' THEN "
            "jsonb_build_object("
            f"'{new_key}', COALESCE(source_payload -> '{new_key}', "
            f"source_payload -> '{old_key}')"
            ") ELSE '{}'::jsonb END"
        )

    op.execute(
        f"UPDATE {table_name} SET source_payload = {json_expr} "
        "WHERE source_payload IS NOT NULL AND ("
        + " OR ".join(predicates)
        + ")"
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
    _rename_keys(
        "tenable_scans",
        (("brd_scan_fields", "scan_result_fields"),),
    )


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
