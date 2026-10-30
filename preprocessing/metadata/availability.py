"""Per data collection availability overlay for the codebook."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from preprocessing.metadata.registry import iter_registry_fields
from preprocessing.metadata.schema import CodebookField, CodebookValidationError

__all__ = [
    "AVAILABILITY_COLUMNS",
    "AVAILABILITY_REASONS",
    "AVAILABILITY_STATES",
    "AvailabilityRow",
    "AvailabilityValue",
    "build_availability_rows",
    "read_availability",
    "validate_availability",
    "write_availability",
]

AVAILABILITY_COLUMNS = ("variable_id", "available", "reason")

AVAILABILITY_STATES = ("true", "false", "not_applicable")

AVAILABILITY_REASONS = (
    "missing_source",
    "optional_test_not_collected",
    "annotation_pending",
    "external",
)

AvailabilityValue = str | tuple[str, str] | Mapping[str, str]


@dataclass(frozen=True, slots=True)
class AvailabilityRow:
    """One row in ``availability.csv``."""

    variable_id: str
    available: str = "true"
    reason: str = ""

    @classmethod
    def from_row(cls, row: Mapping[str, str]) -> AvailabilityRow:
        """Create an availability row from a CSV row."""
        return cls(
            variable_id=row.get("variable_id", "") or "",
            available=(row.get("available", "") or "true"),
            reason=row.get("reason", "") or "",
        )

    def to_row(self) -> dict[str, str]:
        """Return the availability row as a CSV row."""
        return {
            "variable_id": self.variable_id,
            "available": self.available,
            "reason": self.reason,
        }


def _normalize_entry(variable_id: str, value: AvailabilityValue) -> AvailabilityRow:
    """Normalize a caller supplied availability value into a row."""
    if isinstance(value, str):
        return AvailabilityRow(variable_id=variable_id, available=value)
    if isinstance(value, tuple):
        if len(value) != 2:
            raise ValueError(
                f"{variable_id}: availability tuple must contain state and reason"
            )
        available, reason = value
        return AvailabilityRow(
            variable_id=variable_id, available=available, reason=reason
        )
    if isinstance(value, Mapping):
        available = value.get("available", "true")
        return AvailabilityRow(
            variable_id=variable_id,
            available=available,
            reason=value.get("reason", ""),
        )
    raise TypeError(
        f"{variable_id}: availability value must be a state, a (state, reason) "
        f"tuple or a mapping, not {type(value).__name__}"
    )


def validate_availability(
    rows: Sequence[AvailabilityRow],
    field_ids: Iterable[str],
) -> list[str]:
    """Return validation issues for availability rows.

    Parameters
    ----------
    rows : Sequence[AvailabilityRow]
        Availability rows to validate.
    field_ids : Iterable[str]
        Field identifiers known to the codebook.

    Returns
    -------
    list[str]
        Validation issues. An empty list means the rows are valid.
    """
    issues: list[str] = []
    known_ids = set(field_ids)
    seen_ids: set[str] = set()

    for row in rows:
        label = row.variable_id or "<empty variable_id>"
        if not row.variable_id:
            issues.append("Availability row has an empty variable_id")
            continue
        if row.variable_id not in known_ids:
            issues.append(f"{label}: unknown field ID")
        if row.variable_id in seen_ids:
            issues.append(f"{label}: duplicate availability row")
        seen_ids.add(row.variable_id)

        if row.available not in AVAILABILITY_STATES:
            issues.append(f"{label}: invalid availability state {row.available!r}")
            continue

        if row.available == "true":
            if row.reason:
                issues.append(f"{label}: reason must be empty when available is true")
        elif not row.reason:
            issues.append(
                f"{label}: reason is required when available is {row.available!r}"
            )

        if row.reason and row.reason not in AVAILABILITY_REASONS:
            issues.append(f"{label}: unknown availability reason {row.reason!r}")

    return issues


def build_availability_rows(
    availability: Mapping[str, AvailabilityValue] | None = None,
    fields: Iterable[CodebookField] | None = None,
) -> list[AvailabilityRow]:
    """Build availability rows for registered fields.

    Fields without an entry in ``availability`` default to ``true``. The rows
    follow the order of ``fields``.

    Parameters
    ----------
    availability : Mapping[str, AvailabilityValue], optional
        Entries keyed by ``variable_id``. A value is an availability state, a
        ``(state, reason)`` tuple or a mapping with ``available`` and ``reason``
        keys. Defaults to no overrides, so every field is available.
    fields : Iterable[CodebookField], optional
        Fields to include. Defaults to the field registry.

    Returns
    -------
    list[AvailabilityRow]
        One availability row per field.

    Raises
    ------
    CodebookValidationError
        If an entry references an unknown field, uses an invalid state or
        reason, or omits the reason for an unavailable field.
    ValueError
        If an availability tuple does not contain exactly two values.
    TypeError
        If an availability value has an unsupported type.
    """
    known_fields = list(fields if fields is not None else iter_registry_fields())
    entries = dict(availability or {})
    known_ids = {field.variable_id for field in known_fields}

    unknown_ids = sorted(entries.keys() - known_ids)
    if unknown_ids:
        raise CodebookValidationError(
            [f"Unknown field ID: {variable_id}" for variable_id in unknown_ids]
        )

    rows = [
        (
            _normalize_entry(field.variable_id, entries[field.variable_id])
            if field.variable_id in entries
            else AvailabilityRow(variable_id=field.variable_id)
        )
        for field in known_fields
    ]

    issues = validate_availability(rows, known_ids)
    if issues:
        raise CodebookValidationError(issues)
    return rows


def write_availability(path: Path | str, rows: Iterable[AvailabilityRow]) -> Path:
    """Write availability rows to ``availability.csv``.

    Parameters
    ----------
    path : Path or str
        Destination CSV file path.
    rows : Iterable[AvailabilityRow]
        Availability rows to write.

    Returns
    -------
    Path
        The written CSV path.
    """
    destination = Path(path)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(AVAILABILITY_COLUMNS),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(row.to_row() for row in rows)
    return destination


def read_availability(path: Path | str) -> list[AvailabilityRow]:
    """Read availability rows from ``availability.csv``.

    Parameters
    ----------
    path : Path or str
        Source CSV file path.

    Returns
    -------
    list[AvailabilityRow]
        Availability rows in file order.

    Raises
    ------
    CodebookValidationError
        If the file is missing a required availability column.
    """
    source = Path(path)
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [
            column
            for column in AVAILABILITY_COLUMNS
            if column not in (reader.fieldnames or [])
        ]
        if missing:
            raise CodebookValidationError(
                [f"{source.name} is missing columns: {', '.join(missing)}"]
            )
        return [AvailabilityRow.from_row(row) for row in reader]
