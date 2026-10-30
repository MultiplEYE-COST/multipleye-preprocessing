"""Tests for the nested participant view YAML."""

from __future__ import annotations

import json
from pathlib import Path

import polars as pl
import pytest
import yaml

from preprocessing import settings
from preprocessing.data_collection.participant_table import (
    write_participants_table,
    write_participants_yaml,
)

PT_ROWS = [
    {
        "session_id": "001_EN_UK_1_PT1",
        "participant_id": "001",
        "LWMC_Done": "1",
        "LWMC_Total_score_mean": "0.62",
        "RAN_Done": "1",
        "RAN_experimental_rt_sec": "0.55",
        "Stroop_Done": "0",
        "StroopRTEffect_sec": "",
        "Flanker_Done": "0",
        "FlankerRTEffect_sec": "",
        "WikiVocab_Done": "0",
        "WikiVocab_accuracy": "",
        "PLAB_Done": "0",
        "PLAB_accuracy": "",
    },
    {
        "session_id": "001_EN_UK_1_PT2",
        "participant_id": "001",
        "LWMC_Done": "0",
        "LWMC_Total_score_mean": "",
        "RAN_Done": "0",
        "RAN_experimental_rt_sec": "",
        "Stroop_Done": "0",
        "StroopRTEffect_sec": "",
        "Flanker_Done": "0",
        "FlankerRTEffect_sec": "",
        "WikiVocab_Done": "1",
        "WikiVocab_accuracy": "0.71",
        "PLAB_Done": "0",
        "PLAB_accuracy": "",
    },
    {
        "session_id": "002_EN_UK_1_PT1",
        "participant_id": "002",
        "LWMC_Done": "0",
        "LWMC_Total_score_mean": "",
        "RAN_Done": "0",
        "RAN_experimental_rt_sec": "",
        "Stroop_Done": "0",
        "StroopRTEffect_sec": "",
        "Flanker_Done": "0",
        "FlankerRTEffect_sec": "",
        "WikiVocab_Done": "0",
        "WikiVocab_accuracy": "",
        "PLAB_Done": "1",
        "PLAB_accuracy": "0.71",
    },
]


class FakeSession:
    def __init__(self, session_id: str, folder: Path, overview: dict):
        self.session_identifier = session_id
        self.session_folder_path = folder
        self._overview = overview

    def create_overview(self, experimenter_doc=None) -> dict:
        return self._overview


def _overview(session_id: str, pid: int) -> dict:
    return {
        "administrative": {
            "session_identifier": session_id,
            "participant_id": pid,
        },
        "calibration_validation": {
            "avg_validation_error_dva": 0.5,
            "num_calibrations": 1,
            "num_validations": 10,
        },
        "data_quality": {
            "session_blink_loss_ratio": 0.01,
            "session_total_data_loss_ratio": 0.02,
        },
        "experiment_procedure": {
            "total_reading_time_s": 300.0,
            "total_session_duration_s": 1800.0,
            "total_question_time_ms": 1000.0,
            "total_rating_time_ms": 500.0,
            "total_break_time_s": 0.0,
            "was_session_interrupted": False,
            "restarted_session_name": "unknown",
        },
        "trials": [
            {"is_practice": False, "stimulus_name": "text_1"},
        ],
    }


def _write_pq(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def participant_setup(tmp_path: Path, monkeypatch) -> tuple[object, Path]:
    dcn = "MultiplEYE_EN_UK_Test_1_2026"
    dataset_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    pt_dir = output_dir / "psychometric_tests"
    pt_dir.mkdir(parents=True)
    dataset_dir.mkdir()

    sessions = {}
    for session_id, pid in (
        ("001_EN_UK_1_ET1", 1),
        ("001_EN_UK_1_ET2", 1),
        ("002_EN_UK_1_ET1", 2),
    ):
        folder = dataset_dir / "eye-tracking-sessions" / session_id
        folder.mkdir(parents=True)
        sessions[session_id] = FakeSession(
            session_id, folder, _overview(session_id, pid)
        )

    _write_pq(
        dataset_dir
        / "eye-tracking-sessions"
        / "001_EN_UK_1_ET1"
        / "001_EN_UK_1_pq_data.json",
        {
            "gender": "female",
            "age": 24,
            "native_language_1": "English",
            "native_language_1_academic_reading_time": "1_to_3_hours",
            "pq_native_language_1_academic_reading_time": "1_to_3_hours",
        },
    )
    _write_pq(
        dataset_dir
        / "eye-tracking-sessions"
        / "002_EN_UK_1_ET1"
        / "002_EN_UK_1_pq_data.json",
        {"gender": "male", "native_language_1": "German"},
    )
    _write_pq(
        dataset_dir / "participant_questionnaire_EN_UK_1" / "003_EN_UK_1_pq_data.json",
        {"gender": "female", "native_language_1": "English"},
    )

    pl.DataFrame(PT_ROWS).write_csv(pt_dir / f"psychometric_results_{dcn}.csv")

    class FakeCollection:
        language = "EN"
        num_sessions = 2
        preflight_warnings = {}
        preflight_errors = {}
        experimenter_doc = None

    collection = FakeCollection()
    collection.sessions = sessions
    for key, value in {
        "_loaded": True,
        "DATASET_DIR": dataset_dir,
        "OUTPUT_DIR": output_dir,
        "PSYCHOMETRIC_TESTS_DIR": pt_dir,
        "DATA_COLLECTION_NAME": dcn,
        "EXCLUDE_SESSIONS": [],
        "INCLUDE_SESSIONS": [],
        "PARTICIPANT_GROUPS": [{"label": "020", "pids": ["001", "002"]}],
    }.items():
        monkeypatch.setitem(settings.__dict__, key, value)
    return collection, output_dir


@pytest.fixture
def participants_payload(participant_setup) -> tuple[dict, Path, Path]:
    collection, output_dir = participant_setup
    csv_path = write_participants_table(collection, output_dir / "participants.csv")
    yaml_path = write_participants_yaml(
        collection, output_dir / "metadata" / "participants.yaml"
    )
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    return payload, csv_path, output_dir


@pytest.fixture
def grouped(participants_payload) -> dict:
    participants = {
        row["participant_id"]: row for row in participants_payload[0]["participants"]
    }
    return participants["020"]


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("source_pids", ["001", "002"]),
        (
            "session_ids",
            ["001_EN_UK_1_ET1", "001_EN_UK_1_ET2", "002_EN_UK_1_ET1"],
        ),
        (
            "psychometric_session_ids",
            ["001_EN_UK_1_PT1", "001_EN_UK_1_PT2", "002_EN_UK_1_PT1"],
        ),
        ("pq_gender", "female"),
        ("pq_age", 24),
        ("pq_native_language_1", "English"),
        ("pq_bi_monolingualism", "monolingual"),
    ],
)
def test_grouped_identity_and_pq(grouped: dict, field: str, expected: object) -> None:
    assert grouped[field] == expected


def test_grouped_language_reading_times(grouped: dict) -> None:
    assert grouped["pq_language_reading_times"] == {
        "native_language_1": {"academic": "1_to_3_hours"}
    }


@pytest.mark.parametrize(
    ("test_name", "expected"),
    [
        ("LWMC", {"LWMC_Done": True, "LWMC_Total_score_mean": 0.62}),
        ("RAN", {"RAN_Done": True, "RAN_experimental_rt_sec": 0.55}),
        ("Stroop", {"Stroop_Done": False}),
        ("WikiVocab", {"WikiVocab_Done": True, "WikiVocab_accuracy": 0.71}),
        ("PLAB", {"PLAB_Done": True, "PLAB_accuracy": 0.71}),
    ],
)
def test_grouped_psychometric_scores(
    grouped: dict, test_name: str, expected: dict
) -> None:
    assert grouped["psychometric_tests"][test_name] == expected


def test_documentation_block(grouped: dict) -> None:
    assert grouped["documentation"] == {
        "participant_csv": "participants.csv",
        "note": "Full tabular participant output for download and manual inspection",
    }


def test_pq_only_participant(participants_payload) -> None:
    participants = {
        row["participant_id"]: row for row in participants_payload[0]["participants"]
    }
    pq_only = participants["003"]

    assert pq_only["source_pids"] == ["003"]
    assert pq_only["session_ids"] == []
    assert pq_only["psychometric_session_ids"] == []
    assert pq_only["pq_native_language_1"] == "English"
    assert "psychometric_tests" not in pq_only


def test_yaml_is_curated_and_csv_keeps_full_table(
    participants_payload, grouped
) -> None:
    _, csv_path, _ = participants_payload
    csv_header = csv_path.read_text(encoding="utf-8").splitlines()[0]

    assert "et_session_ids" in csv_header
    assert "et_trials_completed" in csv_header
    assert "doc_comments" in csv_header
    assert "et_trials_completed" not in grouped
    assert "doc_comments" not in grouped
