"""Tests for cross-source completeness checks."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import polars as pl

from preprocessing import settings
from preprocessing.checks.preflight import _check_cross_source_completeness
from preprocessing.data_collection.completeness import (
    actual_tests_from_pt_rows,
    cross_source_status,
    expected_tests_from_configs,
    read_sheet_expectations,
)
from preprocessing.data_collection.experimenter_doc import ExperimenterDoc


def _group(label: str, pids: set[str]):
    return SimpleNamespace(label=label, pids=pids, sessions=None)


def _pt_row(pid: str, **flags) -> dict:
    row = {"participant_id": pid, "session_id": f"{pid}_EN_UK_1_PT1"}
    for key in (
        "LWMC_Done",
        "LWMC_MU_Done",
        "LWMC_OS_Done",
        "LWMC_SentS_Done",
        "LWMC_SSTM_Done",
        "RAN_Done",
        "Stroop_Done",
        "Flanker_Done",
        "WikiVocab_Done",
        "PLAB_Done",
    ):
        row[key] = 0
    row.update(flags)
    return row


def test_read_sheet_expectations():
    doc = ExperimenterDoc(
        et_frame=pl.DataFrame(
            {
                "participant_id": ["001", "002", "6->7"],
                "session_id": ["001_EN_UK_1_ET1", None, None],
                "abortion": ["No", "participant cancelled", "No"],
            }
        ),
        et_col_desc=None,
        pt_frame=pl.DataFrame(
            {
                "participant_id": ["001"],
                "session_id": [None],
                "test": ["WMC; Stroop-Flanker; PLAB"],
            }
        ),
        pt_col_desc=None,
    )

    expectations = read_sheet_expectations(doc)

    assert len(expectations) == 3
    et1 = next(e for e in expectations if e.pid == "001" and e.session_type == "ET")
    assert et1.session_id == "001_EN_UK_1_ET1"
    assert et1.aborted is False
    et2 = next(e for e in expectations if e.pid == "002")
    assert et2.aborted is True
    pt = next(e for e in expectations if e.session_type == "PT")
    assert pt.tests == {"WMC", "Stroop_Flanker", "PLAB"}
    assert read_sheet_expectations(None) == []


def test_expected_tests_from_configs(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "002_EN_UK_1_PT1.yaml").write_text(
        "participant_id: 2\nplab: true\nran: true\nwmc: false\n",
        encoding="utf-8",
    )
    monkeypatch.setitem(settings.__dict__, "_loaded", True)
    monkeypatch.setitem(settings.__dict__, "PSYM_PARTICIPANT_CONFIGS", config_dir)
    monkeypatch.setitem(settings.__dict__, "PSYCHOMETRIC_TESTS_DIR", tmp_path / "pt")

    expected = expected_tests_from_configs()

    assert expected == {"002": {"PLAB", "RAN"}}


def test_actual_tests_from_pt_rows():
    rows = [
        _pt_row("001", LWMC_MU_Done=1, LWMC_OS_Done=1, RAN_Done=1, Stroop_Done=1),
        _pt_row("001", PLAB_Done=1),
    ]

    actual = actual_tests_from_pt_rows(rows)

    assert actual == {"001": {"WMC", "RAN", "Stroop_Flanker", "PLAB"}}


def test_cross_source_status_sheet_and_data_mismatches():
    et_sessions = {"001_EN_UK_1_ET1": "001"}
    pt_rows = [_pt_row("001", LWMC_Done=1, PLAB_Done=1)]
    expectations = [
        SimpleNamespace(
            pid="001", session_type="ET", session_id=None, aborted=False, tests=set()
        ),
        SimpleNamespace(
            pid="001",
            session_type="PT",
            session_id=None,
            aborted=False,
            tests={"WMC", "RAN"},
        ),
    ]

    status = cross_source_status(
        _group("001", {"001"}),
        et_sessions,
        pt_rows,
        {"001"},
        expectations,
        {"001": {"WMC"}},
        actual_tests_from_pt_rows(pt_rows),
        num_sessions=1,
    )

    assert status["expected_session_ids"] == "ET; PT"
    assert status["missing_session_ids"] == ""
    assert status["missing_sources"] == ""
    assert status["missing_sheet"] == ""
    assert status["pt_tests_expected"] == "RAN; WMC"
    assert status["pt_tests_missing"] == "RAN"


def test_cross_source_status_missing_et_and_missing_sheet():
    expectations = [
        SimpleNamespace(
            pid="002", session_type="ET", session_id=None, aborted=False, tests=set()
        )
    ]

    missing = cross_source_status(
        _group("002", {"002"}),
        {},
        [],
        set(),
        expectations,
        {},
        {},
        num_sessions=1,
    )
    assert missing["missing_sources"] == "ET"
    assert missing["missing_session_ids"] == "ET"

    data_only = cross_source_status(
        _group("003", {"003"}),
        {},
        [],
        {"003"},
        [],
        {},
        {},
        num_sessions=1,
    )
    assert data_only["missing_sheet"] == "PQ"


def test_cross_source_status_aborted_and_pt_only():
    aborted = cross_source_status(
        _group("004", {"004"}),
        {},
        [],
        set(),
        [
            SimpleNamespace(
                pid="004",
                session_type="ET",
                session_id=None,
                aborted=True,
                tests=set(),
            )
        ],
        {},
        {},
        num_sessions=1,
    )
    assert aborted["missing_sources"] == ""

    pt_only = cross_source_status(
        _group("005", {"005"}),
        {},
        [_pt_row("005", PLAB_Done=1)],
        {"005"},
        [
            SimpleNamespace(
                pid="005",
                session_type="PT",
                session_id=None,
                aborted=False,
                tests={"PLAB"},
            )
        ],
        {},
        {"005": {"PLAB"}},
        num_sessions=1,
    )
    assert pt_only["missing_sources"] == ""
    assert pt_only["missing_sheet"] == ""


def test_cross_source_status_num_sessions_secondary():
    status = cross_source_status(
        _group("006", {"006"}),
        {"006_EN_UK_1_ET1": "006"},
        [],
        {"006"},
        [],
        {},
        {},
        num_sessions=2,
    )

    assert status["missing_sources"] == "ET"


def test_preflight_cross_source_warning(tmp_path: Path, monkeypatch):
    dataset_dir = tmp_path / "data"
    dataset_dir.mkdir()
    pt_dir = tmp_path / "pt"
    (pt_dir / "002_EN_UK_1_PT1" / "PLAB").mkdir(parents=True)

    doc = ExperimenterDoc(
        et_frame=pl.DataFrame(
            {
                "participant_id": ["002"],
                "session_id": [None],
                "abortion": ["No"],
            }
        ),
        et_col_desc=None,
        pt_frame=pl.DataFrame(
            {
                "participant_id": ["002"],
                "session_id": [None],
                "test": ["PLAB"],
            }
        ),
        pt_col_desc=None,
    )

    class FakeCollection:
        sessions = {}
        experimenter_doc = doc
        num_sessions = 1

    monkeypatch.setitem(settings.__dict__, "_loaded", True)
    monkeypatch.setitem(settings.__dict__, "DATASET_DIR", dataset_dir)
    monkeypatch.setitem(settings.__dict__, "PSYCHOMETRIC_TESTS_DIR", pt_dir)
    monkeypatch.setitem(settings.__dict__, "PSYM_PARTICIPANT_CONFIGS", tmp_path / "c")
    monkeypatch.setitem(settings.__dict__, "EXCLUDE_SESSIONS", [])
    monkeypatch.setitem(settings.__dict__, "INCLUDE_SESSIONS", [])

    warnings: dict[str, list[str]] = {}
    _check_cross_source_completeness(FakeCollection(), warnings)

    messages = "\n".join(warnings["Cross-source completeness"])
    assert "002" in messages
    assert "missing sources: ET" in messages
