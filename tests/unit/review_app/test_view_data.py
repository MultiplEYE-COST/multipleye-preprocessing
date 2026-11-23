"""Tests for loading the five views from processed collection YAML."""

import shutil
from pathlib import Path

import yaml

from review_app.services.codebook import load_repo_codebook
from review_app.services.filters import apply_filters, parse_filters
from review_app.services.view_data import (
    load_all_view_rows,
    load_dataset_overview,
    load_items,
    load_participants,
    load_session_overviews,
    load_view_rows,
)

DCN = "MultiplEYE_IT_IT_Torino_1_2025"
SID = "007_IT_IT_1_ET1"


def _write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _build_collection(tmp_path: Path) -> Path:
    dcn = tmp_path / DCN
    dcn.mkdir()
    _write_yaml(
        dcn / f"{DCN}_overview.yaml",
        {
            "administrative": {
                "title": DCN,
                "country": "IT",
                "tested_language": "IT",
                "number_of_sessions": 1,
            },
            "data_quality": {"mean_comprehension_score": 0.8},
        },
    )
    _write_yaml(
        dcn / "metadata" / SID / f"{SID}_overview.yaml",
        {
            "administrative": {
                "participant_id": "007",
                "session_identifier": SID,
                "is_pilot": False,
            },
            "calibration_validation": {
                "avg_validation_error_dva": 0.25,
                "calibration_quality": "GOOD",
            },
            "comprehension": {"avg_comprehension_score": 0.8},
            "trials": [
                {
                    "trial_id": "trial_1",
                    "trial_number": 1,
                    "text_id": "Lit_MagicMountain_it",
                    "comprehension_score": 0.67,
                    "is_practice": False,
                    "answers": [
                        {"question_id": "1", "is_correct": True},
                        {"question_id": "2", "is_correct": False},
                    ],
                }
            ],
        },
    )
    _write_yaml(
        dcn / "metadata" / "participants.yaml",
        {
            "participants": [
                {
                    "participant_id": "007",
                    "session_ids": [SID],
                    "pq_age": 40,
                    "pq_gender": "male",
                }
            ]
        },
    )
    _write_yaml(
        dcn / "metadata" / "items.yaml",
        {
            "items": [
                {
                    "data_collection_name": DCN,
                    "text_id": "Lit_MagicMountain_it",
                    "num_words": 1012,
                    "questions": [{"question_id": "1", "condition": "local"}],
                }
            ]
        },
    )
    return dcn


def test_load_dataset_and_sessions(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    codebook = load_repo_codebook()
    dataset = load_view_rows(dcn, "dataset", codebook)
    assert len(dataset) == 1
    assert dataset[0].key == DCN
    assert dataset[0].value("dataset.administrative.country") == "IT"

    sessions = load_view_rows(dcn, "session", codebook)
    assert len(sessions) == 1
    assert sessions[0].key == SID
    assert sessions[0].parents["dataset"] == DCN
    assert sessions[0].value("session.administrative.participant_id") == "007"


def test_load_trials_with_answers(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    codebook = load_repo_codebook()
    trials = load_view_rows(dcn, "trial", codebook)
    assert len(trials) == 1
    assert trials[0].key == "trial_1"
    assert trials[0].parents == {
        "dataset": DCN,
        "session": SID,
        "participant": "007",
    }
    assert trials[0].value("trial.comprehension_score") == 0.67
    assert trials[0].value("trial.answers.is_correct") == [True, False]


def test_integer_session_participant_resolves_to_participant_key(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    sid = SID
    overview_path = dcn / "metadata" / sid / f"{sid}_overview.yaml"
    overview = yaml.safe_load(overview_path.read_text())
    overview["administrative"]["participant_id"] = 7
    _write_yaml(overview_path, overview)

    codebook = load_repo_codebook()
    sessions = load_view_rows(dcn, "session", codebook)
    assert sessions[0].parents["participant"] == "007"


def test_load_participants_and_items(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    codebook = load_repo_codebook()
    participants = load_view_rows(dcn, "participant", codebook)
    assert len(participants) == 1
    assert participants[0].key == "007"
    assert participants[0].value("participant.pq_age") == 40

    items = load_view_rows(dcn, "item", codebook)
    assert len(items) == 1
    assert items[0].key == "Lit_MagicMountain_it"
    assert items[0].value("item.num_words") == 1012


def test_source_readers(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    assert load_dataset_overview(dcn)["administrative"]["country"] == "IT"
    assert load_session_overviews(dcn)[0][0] == SID
    assert load_participants(dcn)[0]["participant_id"] == "007"
    assert load_items(dcn)[0]["text_id"] == "Lit_MagicMountain_it"


def test_participant_and_trial_relations(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    codebook = load_repo_codebook()
    participants = load_view_rows(dcn, "participant", codebook)
    trials = load_view_rows(dcn, "trial", codebook)

    participant_filter = parse_filters(["participant.participant_id:eq:007"])
    assert len(apply_filters(trials, participant_filter, codebook, dcn)) == 1

    age_filter = parse_filters(["participant.pq_age:gt:30"])
    assert len(apply_filters(trials, age_filter, codebook, dcn)) == 1

    trial_filter = parse_filters(["trial.is_practice:eq:false"])
    assert len(apply_filters(participants, trial_filter, codebook, dcn)) == 1


def test_load_all_view_rows_spans_collections(tmp_path: Path) -> None:
    first = _build_collection(tmp_path)
    second = tmp_path / "MultiplEYE_KL_DK_Copenhagen_1_2026"
    shutil.copytree(first, second)
    old_overview = second / f"{first.name}_overview.yaml"
    overview_path = second / f"{second.name}_overview.yaml"
    old_overview.rename(overview_path)
    overview = yaml.safe_load(overview_path.read_text())
    overview["administrative"]["title"] = second.name
    _write_yaml(overview_path, overview)

    codebook = load_repo_codebook()
    datasets = load_all_view_rows(tmp_path, "dataset", codebook)
    sessions = load_all_view_rows(tmp_path, "session", codebook)
    assert {row.key for row in datasets} == {first.name, second.name}
    assert len(sessions) == 2
    assert {row.dcn_name for row in sessions} == {first.name, second.name}


def test_same_view_trial_filter_does_not_cross_sessions(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    second = "009_IT_IT_1_ET1"
    _write_yaml(
        dcn / "metadata" / second / f"{second}_overview.yaml",
        {
            "administrative": {
                "participant_id": 9,
                "session_identifier": second,
                "is_pilot": False,
            },
            "trials": [
                {
                    "trial_id": "trial_1",
                    "trial_number": 1,
                    "text_id": "Lit_Solaris_it",
                    "comprehension_score": 0.1,
                    "is_practice": False,
                }
            ],
        },
    )
    codebook = load_repo_codebook()
    trials = load_view_rows(dcn, "trial", codebook)
    assert len(trials) == 2

    high_score = parse_filters(["trial.comprehension_score:gt:0.5"])
    assert len(apply_filters(trials, high_score, codebook, dcn)) == 1


def test_list_filter_uses_membership(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    codebook = load_repo_codebook()
    participants = load_view_rows(dcn, "participant", codebook)
    session_filter = parse_filters([f"participant.session_ids:eq:{SID}"])
    assert len(apply_filters(participants, session_filter, codebook, dcn)) == 1


def test_filter_ancestor_and_descendant(tmp_path: Path) -> None:
    dcn = _build_collection(tmp_path)
    codebook = load_repo_codebook()
    sessions = load_view_rows(dcn, "session", codebook)

    country_filter = parse_filters(["dataset.administrative.country:eq:IT"])
    assert len(apply_filters(sessions, country_filter, codebook, dcn)) == 1

    wrong_country = parse_filters(["dataset.administrative.country:eq:FR"])
    assert apply_filters(sessions, wrong_country, codebook, dcn) == []

    trial_filter = parse_filters(["trial.comprehension_score:gt:0.5"])
    assert len(apply_filters(sessions, trial_filter, codebook, dcn)) == 1

    trials = load_view_rows(dcn, "trial", codebook)
    session_filter = parse_filters([f"session.session_identifier:eq:{SID}"])
    assert len(apply_filters(trials, session_filter, codebook, dcn)) == 1
