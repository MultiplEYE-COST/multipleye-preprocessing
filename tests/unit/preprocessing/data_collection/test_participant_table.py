"""Tests for the participant-level overview table."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import polars as pl

from preprocessing import settings
from preprocessing.data_collection.experimenter_doc import ExperimenterDoc
from preprocessing.data_collection.participant_table import (
    _pq_columns,
    build_participant_table,
)


class FakeSession:
    def __init__(self, session_id: str, folder: Path, overview: dict):
        self.session_identifier = session_id
        self.session_folder_path = folder
        self._overview = overview

    def create_overview(self) -> dict:
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
            "num_completed_trials": 10,
            "total_reading_time_s": 300.0,
            "total_session_duration_s": 1800.0,
            "total_question_time_ms": 1000.0,
            "total_rating_time_ms": 500.0,
            "total_break_time_s": "unknown",
            "was_session_interrupted": False,
            "restarted_session_name": "unknown",
        },
        "trials": [
            {"is_practice": True, "stimulus_name": "practice"},
            {"is_practice": False, "stimulus_name": "text_1"},
            {"is_practice": False, "stimulus_name": "text_2"},
        ],
    }


def _write_pq(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_participant_table_union_grouping_docs_and_unassigned(
    tmp_path: Path, monkeypatch
):
    dcn = "MultiplEYE_EN_UK_Test_1_2026"
    dataset_dir = tmp_path / "data"
    output_dir = tmp_path / "out"
    pt_dir = output_dir / "psychometric_tests"
    pt_dir.mkdir(parents=True)
    dataset_dir.mkdir()

    et_folder = dataset_dir / "eye-tracking-sessions" / "001_EN_UK_1_ET1"
    et_folder.mkdir(parents=True)
    _write_pq(
        et_folder / "001_EN_UK_1_pq_data.json",
        {
            "gender": "female",
            "native_language_1": "English",
            "native_language_2": "German",
            "use_language": "English",
            "dominant_language": "German",
        },
    )

    questionnaire_dir = dataset_dir / "participant_questionnaire_EN_UK_1"
    _write_pq(
        questionnaire_dir / "003_EN_UK_1_pq_data.json",
        {"gender": "male", "native_language_1": "English"},
    )

    pl.DataFrame(
        {
            "session_id": ["001_EN_UK_1_PT1", "002_EN_UK_1_PT1"],
            "participant_id": ["001", "002"],
            "LWMC_Done": ["1", "0"],
            "LWMC_MU_Done": ["1", "0"],
            "LWMC_OS_Done": ["1", "0"],
            "LWMC_SentS_Done": ["1", "0"],
            "LWMC_SSTM_Done": ["0", "0"],
            "RAN_Done": ["1", "0"],
            "Stroop_Done": ["0", "0"],
            "Flanker_Done": ["0", "0"],
            "WikiVocab_Done": ["1", "1"],
            "PLAB_Done": ["0", "0"],
        }
    ).write_csv(pt_dir / f"psychometric_results_{dcn}.csv")

    experimenter_doc = ExperimenterDoc(
        et_frame=pl.DataFrame(
            {
                "participant_id": ["001", "6->7"],
                "session_id": ["001_EN_UK_1_ET1", None],
                "setup_deviation": ["none", "custom setup"],
                "technical_issues": ["", "tracker restart"],
                "interruptions": ["", ""],
                "irritations": ["", ""],
                "abortion": ["", ""],
                "file_issues": ["", ""],
                "comments": ["looks good", "please check"],
                "Stimulus Version": ["v2", ""],
            }
        ),
        et_col_desc=None,
        pt_frame=pl.DataFrame(
            {
                "participant_id": ["001"],
                "session_id": ["001_EN_UK_1_PT1"],
                "comments": ["PT ok"],
            }
        ),
        pt_col_desc=None,
    )

    sessions = {
        "001_EN_UK_1_ET1": FakeSession(
            "001_EN_UK_1_ET1", et_folder, _overview("001_EN_UK_1_ET1", 1)
        )
    }

    class FakeCollection:
        language = "EN"
        preflight_warnings = {"Session completeness": ["001_EN_UK_1_ET1 is incomplete"]}
        preflight_errors = {}

    collection = FakeCollection()
    collection.experimenter_doc = experimenter_doc
    collection.sessions = sessions

    monkeypatch.setitem(settings.__dict__, "_loaded", True)
    monkeypatch.setitem(settings.__dict__, "DATASET_DIR", dataset_dir)
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", output_dir)
    monkeypatch.setitem(settings.__dict__, "PSYCHOMETRIC_TESTS_DIR", pt_dir)
    monkeypatch.setitem(settings.__dict__, "DATA_COLLECTION_NAME", dcn)
    monkeypatch.setitem(settings.__dict__, "EXCLUDE_SESSIONS", [])
    monkeypatch.setitem(settings.__dict__, "INCLUDE_SESSIONS", [])
    monkeypatch.setitem(
        settings.__dict__,
        "PARTICIPANT_GROUPS",
        [{"label": "020", "pids": ["001", "002"]}],
    )

    table = build_participant_table(collection)
    rows = {row["participant_id"]: row for row in table.iter_rows(named=True)}

    assert set(rows) == {"020", "003", "6->7"}

    merged = rows["020"]
    assert merged["pids"] == "001; 002"
    assert merged["et_session_ids"] == "001_EN_UK_1_ET1"
    assert merged["pt_session_ids"] == "001_EN_UK_1_PT1; 002_EN_UK_1_PT1"
    assert merged["et_trials_completed"] == 2
    assert merged["et_trials_total"] == 10
    assert merged["et_trials_practice"] == 1
    assert merged["et_total_break_time_s"] == 0.0
    assert merged["et_stimuli_presented"] == "text_1; text_2"
    assert merged["et_blink_loss_ratio"] == 0.01
    assert merged["pt_tests_status"] == (
        "LWMC:partial(MU,OS,SentS); RAN:done; WikiVocab:done"
    )
    assert merged["pq_gender"] == "female"
    assert merged["pq_native_language_1"] == "English"
    assert merged["pq_bi_monolingualism"] == "bilingual"
    assert merged["doc_comments"] == "looks good | PT ok"
    assert merged["doc_abortion"] == ""
    assert merged["preflight_status"] == "warnings"
    assert merged["preflight_failed"] == "Session completeness"
    assert merged["manual_comments"] == ""

    pq_only = rows["003"]
    assert pq_only["et_session_ids"] == ""
    assert pq_only["pt_tests_status"] == ""
    assert pq_only["pq_native_language_1"] == "English"

    unassigned = rows["6->7"]
    assert unassigned["manual_comments"].startswith("doc sheet PID not parseable")
    assert unassigned["doc_comments"] == "please check"


def test_pq_columns_handle_missing_values():
    result = _pq_columns({"gender": pd.NA, "native_language_1": pd.NA})

    assert result["pq_gender"] is None
    assert result["pq_native_language_1"] is None
