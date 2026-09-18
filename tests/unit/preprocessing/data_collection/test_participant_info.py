import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from preprocessing import settings
from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
    _bi_monolingualism_from_pq,
    _parse_iso_date,
    _psychometric_dates,
    _psychometric_tests_in_folder,
    _session_date_from_logfile,
)
from preprocessing.data_collection.session import Session


@pytest.mark.parametrize(
    "pq, expected",
    [
        ({"native_language_1": "Chinese"}, "monolingual"),
        ({"native_language_1": "Chinese", "native_language_2": "German"}, "bilingual"),
        (
            {
                "native_language_1": "a",
                "native_language_2": "b",
                "native_language_3": "c",
            },
            "multilingual",
        ),
        ({}, "unknown"),
        ({"native_language_1": "nan"}, "unknown"),
        (
            {"native_language_1": "Chinese", "native_language_2": "Chinese"},
            "monolingual",
        ),
    ],
)
def test_bi_monolingualism_from_pq(pq, expected):
    assert _bi_monolingualism_from_pq(pq) == expected


def test_parse_iso_date():
    assert _parse_iso_date("2025-03-10") == date(2025, 3, 10)
    assert _parse_iso_date("2025-03-10_10-00-00") == date(2025, 3, 10)
    assert _parse_iso_date("not-a-date") is None
    assert _parse_iso_date(None) is None


def test_session_date_from_logfile():
    df = pl.DataFrame({"message": ["header", "*** DATE:2025-03-10"]})
    assert _session_date_from_logfile(df) == date(2025, 3, 10)

    assert _session_date_from_logfile(pl.DataFrame({"message": ["x"]})) is None
    assert _session_date_from_logfile("unknown") is None
    assert _session_date_from_logfile(None) is None


def test_psychometric_dates_and_tests(tmp_path: Path):
    pt = tmp_path / "001_EN_UK_1_PT1"
    (pt / "PLAB").mkdir(parents=True)
    (pt / "RAN").mkdir()
    (pt / "PLAB" / "X_2025-03-10_10-00-00.csv").touch()
    (pt / "RAN" / "X_2025-03-10_10-05-00.csv").touch()

    assert _psychometric_dates(pt) == {date(2025, 3, 10)}
    assert _psychometric_tests_in_folder(pt) == ["PLAB", "RAN"]
    assert _psychometric_dates(None) == set()
    assert _psychometric_tests_in_folder(None) == []


def _make_session(
    sid: str, folder: Path, logfile: pl.DataFrame | None = None
) -> Session:
    sess = Session(
        participant_id=int(sid.split("_")[0]),
        session_identifier=sid,
        is_pilot=False,
        session_folder_path=folder,
        session_file_path=folder / "x.edf",
        session_file_name="x.edf",
    )
    if logfile is not None:
        sess.logfile = logfile
    return sess


def test_assign_participant_info(tmp_path: Path, monkeypatch):
    dcn = "MultiplEYE_EN_UK_London_1_2025"

    # PT folders: PT1 has PLAB (03-10), PT2 has WMC (03-17)
    pt_root = tmp_path / "pt"
    (pt_root / "001_EN_UK_1_PT1" / "PLAB").mkdir(parents=True)
    (pt_root / "001_EN_UK_1_PT1" / "PLAB" / "X_2025-03-10_10-00-00.csv").touch()
    (pt_root / "001_EN_UK_1_PT2" / "WMC").mkdir(parents=True)
    (pt_root / "001_EN_UK_1_PT2" / "WMC" / "X_2025-03-17_10-00-00.csv").touch()

    # psychometric results (per-session table)
    out = tmp_path / "out"
    (out / "psychometric_tests").mkdir(parents=True)
    pl.DataFrame(
        {
            "participant_id": [1],
            "LWMC_Done": [1],
            "LWMC_Total_score_mean": [0.5],
            "PLAB_accuracy": [0.8],
        }
    ).write_csv(out / "psychometric_tests" / f"psychometric_results_{dcn}.csv")

    # sessions + PQ data
    et1_dir = tmp_path / "et" / "001_EN_UK_1_ET1"
    et2_dir = tmp_path / "et" / "001_EN_UK_1_ET2"
    et1_dir.mkdir(parents=True)
    et2_dir.mkdir(parents=True)
    (et1_dir / "001_EN_UK_1_pq_data.json").write_text(
        json.dumps({"gender": "female", "native_language_1": "English"})
    )

    et1 = _make_session(
        "001_EN_UK_1_ET1", et1_dir, pl.DataFrame({"message": ["*** DATE:2025-03-10"]})
    )
    et2 = _make_session(
        "001_EN_UK_1_ET2", et2_dir, pl.DataFrame({"message": ["*** DATE:2025-03-17"]})
    )

    monkeypatch.setitem(settings.__dict__, "PSYCHOMETRIC_TESTS_DIR", pt_root)
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", out)

    dc = object.__new__(MultipleyeDataCollection)
    dc.sessions = {"001_EN_UK_1_ET1": et1, "001_EN_UK_1_ET2": et2}
    dc.data_collection_name = dcn

    dc._assign_participant_info()

    info1 = et1.participant_info
    assert info1["gender"] == "female"
    assert info1["bi_monolingualism"] == "monolingual"
    assert info1["psychometric_tests"] == ["PLAB", "WMC"]
    assert info1["tests_conducted_this_session"] == ["PLAB"]
    assert info1["tests_conducted_separate_session"] == ["WMC"]
    assert info1["has_pt_data_same_day_as_session"] is True
    assert info1["gap_to_previous_session_days"] == "unknown"
    assert info1["gap_to_next_session_days"] == 7
    assert info1["gap_to_psychometric_tests_days"] == 0
    assert info1["psychometric_test_scores"]["LWMC_Total_score_mean"] == 0.5
    assert info1["psychometric_test_scores"]["PLAB_accuracy"] == 0.8

    info2 = et2.participant_info
    assert info2["tests_conducted_this_session"] == ["WMC"]
    assert info2["tests_conducted_separate_session"] == ["PLAB"]
    assert info2["has_pt_data_same_day_as_session"] is True
    assert info2["gap_to_previous_session_days"] == 7
    assert info2["gap_to_next_session_days"] == "unknown"

    assert et1.psychometric_tests_session == "001_EN_UK_1_PT1"
    assert et2.psychometric_tests_session == "001_EN_UK_1_PT2"


def test_assign_participant_info_unknown_without_data(tmp_path: Path, monkeypatch):
    monkeypatch.setitem(
        settings.__dict__, "PSYCHOMETRIC_TESTS_DIR", tmp_path / "missing"
    )
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", tmp_path / "out")

    sess = _make_session("001_EN_UK_1_ET1", tmp_path / "et" / "001_EN_UK_1_ET1")
    (tmp_path / "et" / "001_EN_UK_1_ET1").mkdir(parents=True)

    dc = object.__new__(MultipleyeDataCollection)
    dc.sessions = {"001_EN_UK_1_ET1": sess}
    dc.data_collection_name = "MultiplEYE_EN_UK_London_1_2025"

    dc._assign_participant_info()

    info = sess.participant_info
    assert info["gender"] == "unknown"
    assert info["bi_monolingualism"] == "unknown"
    assert info["psychometric_tests"] == []
    assert info["has_pt_data_same_day_as_session"] is None
    assert info["gap_to_psychometric_tests_days"] == "unknown"
    assert info["psychometric_test_scores"] == "unknown"


def test_session_overview_includes_participant_section():
    sess = Session(
        participant_id=1,
        session_identifier="001_EN_UK_1_ET1",
        is_pilot=False,
        session_folder_path=Path("/tmp"),
        session_file_path=Path("/tmp/x"),
        session_file_name="x",
    )
    sess.participant_info = {"gender": "female", "bi_monolingualism": "monolingual"}

    overview = sess.create_overview()
    assert overview["participant"] == {
        "gender": "female",
        "bi_monolingualism": "monolingual",
    }
