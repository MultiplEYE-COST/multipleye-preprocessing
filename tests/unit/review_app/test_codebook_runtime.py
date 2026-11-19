"""Tests for codebook loading and YAML path resolution."""

from pathlib import Path

from review_app.services.codebook import (
    REPO_CODEBOOK_DIR,
    availability_for,
    load_availability,
    load_repo_codebook,
    parse_value_labels,
    resolve_yaml_path,
)
from review_app.services.codebook_store import union_codebook


def test_repo_codebook_has_five_views() -> None:
    codebook = load_repo_codebook()
    assert set(codebook.views) == {"dataset", "session", "trial", "participant", "item"}
    assert codebook.fields
    assert codebook.groups
    assert codebook.relations


def test_union_codebook_uses_repo_without_outputs() -> None:
    codebook = union_codebook()
    assert codebook.fields
    assert codebook.views["trial"].key == "trial_id"


def test_resolve_nested_list_path() -> None:
    document = {
        "trials": [
            {"answers": [{"is_correct": True}, {"is_correct": False}]},
            {"answers": [{"is_correct": True}]},
        ]
    }
    assert resolve_yaml_path(document, "trials[].answers[].is_correct") == [
        [True, False],
        [True],
    ]


def test_resolve_keyed_mapping_array_path() -> None:
    document = {
        "processing": {
            "answer_option_shuffling": {
                "sets": {
                    "set_a": {"flagged": True},
                    "set_b": {"flagged": False},
                }
            }
        }
    }
    assert resolve_yaml_path(
        document, "processing.answer_option_shuffling.sets[].flagged"
    ) == [True, False]


def test_resolve_missing_path_is_none() -> None:
    assert resolve_yaml_path({"a": {"b": 1}}, "a.c") is None
    assert resolve_yaml_path({}, "a.b") is None


def test_parse_value_labels() -> None:
    assert parse_value_labels("male=Male | female=Female") == {
        "male": "Male",
        "female": "Female",
    }


def test_columns_for_group_starts_with_key() -> None:
    codebook = load_repo_codebook()
    columns = codebook.columns_for("session", "quality")
    assert columns[0].variable_id == "session.session_identifier"
    assert any(field.variable_id == "session.calibration_validation.calibration_quality" for field in columns)


def test_default_group_for_view_is_available() -> None:
    codebook = load_repo_codebook()
    assert codebook.default_group_for_view("dataset") == "default"
    assert codebook.default_group_for_view("session") in codebook.group_ids_for_view("session")


def test_availability_overlay(tmp_path: Path) -> None:
    codebook = load_repo_codebook()
    dcn = tmp_path / "MultiplEYE_IT_IT_Torino_1_2025"
    codebook_dir = dcn / "codebook"
    codebook_dir.mkdir(parents=True)
    (codebook_dir / "availability.csv").write_text(
        "variable_id,available,reason\n"
        "item.annotation_layers,false,annotation_pending\n",
        encoding="utf-8",
    )
    overlay = load_availability(dcn)
    assert overlay["item.annotation_layers"].is_available is False
    result = availability_for(dcn, codebook)
    assert result["item.annotation_layers"].reason == "annotation_pending"
    assert result["session.session_identifier"].is_available is True


def test_repo_codebook_dir_exists() -> None:
    assert (REPO_CODEBOOK_DIR / "fields.csv").exists()
