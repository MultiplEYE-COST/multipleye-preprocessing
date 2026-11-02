"""Tests for the codebook value vocabulary."""

from __future__ import annotations

from preprocessing.metadata.registry import iter_registry_fields
from preprocessing.metadata.schema import CodebookField
from preprocessing.metadata.vocabulary import (
    BOOLEAN_ALLOWED_VALUES,
    apply_vocabulary,
    parse_value_labels,
)
from preprocessing.utils.pq_normalisation.codebook import CODEBOOK


def _field(**overrides: object) -> CodebookField:
    values = {
        "variable_id": "trial.example",
        "view_level": "trial",
        "variable_name": "example",
        "feature_label": "Example",
        "description": "Example field",
        "data_type": "number",
        "semantic_category": "administrative",
    }
    values.update(overrides)
    return CodebookField(**values)


def test_boolean_fields_get_true_false() -> None:
    field = apply_vocabulary(_field(data_type="boolean"))

    assert field.allowed_values == BOOLEAN_ALLOWED_VALUES
    assert field.value_labels == "true=True | false=False"


def test_unit_is_derived_from_the_name_suffix() -> None:
    field = apply_vocabulary(_field(variable_name="total_duration_ms"))

    assert field.unit == "ms"


def test_explicit_unit_is_kept() -> None:
    field = apply_vocabulary(_field(variable_name="total_duration_ms", unit="s"))

    assert field.unit == "s"


def test_year_unit_is_derived_for_ages() -> None:
    field = apply_vocabulary(
        _field(
            variable_id="participant.pq_age",
            view_level="participant",
            variable_name="pq_age",
        )
    )

    assert field.unit == "year"


def test_dimensionless_fields_keep_an_empty_unit() -> None:
    field = apply_vocabulary(_field(variable_name="data_loss_ratio"))

    assert field.unit == ""


def test_every_registered_boolean_declares_allowed_values() -> None:
    for field in iter_registry_fields():
        if field.data_type != "boolean":
            continue
        assert field.allowed_values == BOOLEAN_ALLOWED_VALUES, field.variable_id
        assert field.value_labels, field.variable_id


def test_every_allowed_value_list_has_matching_labels() -> None:
    for field in iter_registry_fields():
        if not field.allowed_values:
            continue
        labels = parse_value_labels(field.value_labels)
        assert labels is not None, field.variable_id
        assert set(labels) == set(field.allowed_values.split(",")), field.variable_id


def test_participant_questionnaire_fields_use_canonical_codes() -> None:
    expected = {
        "participant.pq_gender": "gender",
        "participant.pq_level_education": "level_education",
        "participant.pq_socio_economic_status": "socio_economic_status",
        "participant.pq_childhood_languages": "childhood_languages",
        "participant.pq_eyewear": "eyewear",
        "participant.pq_alcohol_yesterday": "alcohol",
        "participant.pq_alcohol_today": "alcohol",
    }
    fields = {field.variable_id: field for field in iter_registry_fields()}

    for variable_id, question in expected.items():
        codes = [
            code["code"] if isinstance(code, dict) else code
            for code in CODEBOOK["fields"][question]["codes"]
        ]
        assert fields[variable_id].allowed_values == ",".join(codes), variable_id


def test_language_fields_have_no_fixed_value_list() -> None:
    fields = {field.variable_id: field for field in iter_registry_fields()}

    assert fields["participant.pq_native_language_1"].allowed_values == ""
    assert fields["participant.pq_use_language"].allowed_values == ""
