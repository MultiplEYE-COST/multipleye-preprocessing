"""Tests for type-aware view filter operators."""

from review_app.services.codebook import load_repo_codebook
from review_app.services.filters import operators_for_field, value_options


def test_numeric_field_operators() -> None:
    codebook = load_repo_codebook()
    field = codebook.field("session.comprehension.avg_comprehension_score")
    assert field is not None
    assert operators_for_field(field) == ("eq", "ne", "gt", "ge", "lt", "le")


def test_categorical_field_operators_and_values() -> None:
    codebook = load_repo_codebook()
    field = codebook.field("session.calibration_validation.calibration_quality")
    assert field is not None
    assert operators_for_field(field) == ("eq", "ne")
    labels = {option["value"] for option in value_options(field)}
    assert "GOOD" in labels or labels


def test_boolean_field_operators_and_values() -> None:
    codebook = load_repo_codebook()
    field = codebook.field("session.administrative.is_pilot")
    assert field is not None
    assert operators_for_field(field) == ("eq", "ne")
    assert {option["value"] for option in value_options(field)} == {"true", "false"}


def test_string_field_operators() -> None:
    codebook = load_repo_codebook()
    field = codebook.field("session.session_identifier")
    assert field is not None
    assert operators_for_field(field) == ("eq", "ne", "contains")
