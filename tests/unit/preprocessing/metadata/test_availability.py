import csv
from pathlib import Path

import pytest

from preprocessing.metadata.availability import (
    AVAILABILITY_COLUMNS,
    AVAILABILITY_REASONS,
    AVAILABILITY_STATES,
    AvailabilityRow,
    build_availability_rows,
    read_availability,
    validate_availability,
    write_availability,
)
from preprocessing.metadata.registry import iter_registry_fields
from preprocessing.metadata.schema import CodebookField, CodebookValidationError


def _field(variable_id: str, view_level: str) -> CodebookField:
    return CodebookField(
        variable_id=variable_id,
        view_level=view_level,
        variable_name=variable_id.split(".", 1)[1],
        feature_label=variable_id,
        description=f"Example field {variable_id}",
        data_type="string",
        semantic_category=view_level,
    )


@pytest.fixture
def fields() -> list[CodebookField]:
    return [
        _field("dataset.data_collection_name", "dataset"),
        _field("session.session_id", "session"),
        _field("trial.trial_id", "trial"),
    ]


def test_availability_contract() -> None:
    assert AVAILABILITY_COLUMNS == ("variable_id", "available", "reason")
    assert AVAILABILITY_STATES == ("true", "false", "not_applicable")
    assert set(AVAILABILITY_REASONS) == {
        "missing_source",
        "optional_test_not_collected",
        "annotation_pending",
        "external",
    }


def test_build_defaults_to_available(fields: list[CodebookField]) -> None:
    rows = build_availability_rows(fields=fields)

    assert rows == [AvailabilityRow(field.variable_id) for field in fields]
    assert {row.available for row in rows} == {"true"}


def test_build_for_registry_uses_all_registered_fields() -> None:
    registered = list(iter_registry_fields())
    rows = build_availability_rows()

    assert [row.variable_id for row in rows] == [
        field.variable_id for field in registered
    ]
    assert {row.available for row in rows} == {"true"}


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("true", AvailabilityRow("session.session_id")),
        (
            ("false", "missing_source"),
            AvailabilityRow("session.session_id", "false", "missing_source"),
        ),
        (
            {"available": "not_applicable", "reason": "optional_test_not_collected"},
            AvailabilityRow(
                "session.session_id", "not_applicable", "optional_test_not_collected"
            ),
        ),
    ],
)
def test_build_normalizes_override_values(
    fields: list[CodebookField],
    value: str | tuple[str, str] | dict[str, str],
    expected: AvailabilityRow,
) -> None:
    rows = build_availability_rows({"session.session_id": value}, fields=fields)

    assert rows[1] == expected
    assert rows[0].available == "true"
    assert rows[2].available == "true"


def test_write_availability(tmp_path: Path, fields: list[CodebookField]) -> None:
    rows = build_availability_rows(
        {"trial.trial_id": ("false", "missing_source")},
        fields=fields,
    )
    destination = tmp_path / "availability.csv"

    written = write_availability(destination, rows)

    assert written == destination
    with destination.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == list(AVAILABILITY_COLUMNS)
        written_rows = list(reader)

    assert written_rows == [row.to_row() for row in rows]
    assert written_rows[-1] == {
        "variable_id": "trial.trial_id",
        "available": "false",
        "reason": "missing_source",
    }
    assert read_availability(destination) == rows


def test_read_availability_rejects_missing_columns(tmp_path: Path) -> None:
    source = tmp_path / "availability.csv"
    source.write_text("variable_id,available\nsession.session_id,true\n")

    with pytest.raises(CodebookValidationError, match="missing columns: reason"):
        read_availability(source)


@pytest.mark.parametrize(
    ("availability", "message"),
    [
        ({"trial.unknown": "true"}, "Unknown field ID: trial.unknown"),
        ({"trial.trial_id": "yes"}, "invalid availability state"),
        ({"trial.trial_id": "false"}, "reason is required"),
        ({"trial.trial_id": "not_applicable"}, "reason is required"),
        (
            {"trial.trial_id": ("false", "unknown_reason")},
            "unknown availability reason",
        ),
        (
            {"trial.trial_id": ("true", "missing_source")},
            "reason must be empty",
        ),
    ],
)
def test_build_rejects_invalid_availability(
    fields: list[CodebookField],
    availability: dict[str, str | tuple[str, str]],
    message: str,
) -> None:
    with pytest.raises(CodebookValidationError, match=message):
        build_availability_rows(availability, fields=fields)


def test_validate_availability_rejects_unknown_and_duplicate_rows(
    fields: list[CodebookField],
) -> None:
    field_ids = [field.variable_id for field in fields]
    rows = [
        AvailabilityRow("trial.unknown"),
        AvailabilityRow("session.session_id"),
        AvailabilityRow("session.session_id"),
    ]

    assert validate_availability(rows, field_ids) == [
        "trial.unknown: unknown field ID",
        "session.session_id: duplicate availability row",
    ]


def test_build_rejects_malformed_tuple(fields: list[CodebookField]) -> None:
    with pytest.raises(ValueError, match="must contain state and reason"):
        build_availability_rows({"trial.trial_id": ("false",)}, fields=fields)
