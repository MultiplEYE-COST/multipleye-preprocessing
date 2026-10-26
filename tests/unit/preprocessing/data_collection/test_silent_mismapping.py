"""Tests for the missing-participant fallback in stimulus-order loading."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from preprocessing.data_collection.merid_data_collection import MeridDataCollection
from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)

_ASC_PATCH = (
    "preprocessing.data_collection.multipleye_data_collection."
    "extract_stimulus_version_number_from_asc"
)

SID = "001_EN_UK_1_ET1"


def _make_collection(cls, rows: dict):
    obj = object.__new__(cls)
    obj.logger = MagicMock()
    obj.stim_order_versions = pd.DataFrame(rows)
    obj.sessions = {}
    obj.skipped_sessions = {}
    obj.crashed_session_ids = set()
    return obj


def _base_obj(csv: dict):
    return _make_collection(MultipleyeDataCollection, csv)


def test_resolve_by_asc_version(tmp_path, capsys, monkeypatch):
    obj = _base_obj({"participant_id": [999], "version_number": [13], "v": [1]})
    obj.sessions[SID] = SimpleNamespace(asc_path=Path("a.asc"))
    monkeypatch.setattr(_ASC_PATCH, lambda _: 13)

    row = obj._resolve_stim_order_version(SID, "001", 13, asc_available=True)

    assert row["version_number"].iloc[0] == 13
    assert "Participant ID 001 not found" in capsys.readouterr().err


def test_raises_when_asc_and_logfile_disagree(tmp_path, monkeypatch):
    obj = _base_obj({"participant_id": [999], "version_number": [42], "v": [1]})
    obj.sessions[SID] = SimpleNamespace(asc_path=Path("a.asc"))
    monkeypatch.setattr(_ASC_PATCH, lambda _: 42)

    with pytest.raises(ValueError, match="does not match the version"):
        obj._resolve_stim_order_version(SID, "001", 13, asc_available=True)


def test_raises_when_version_missing_from_csv(tmp_path, monkeypatch):
    obj = _base_obj({"participant_id": [999], "version_number": [7], "v": [1]})
    obj.sessions[SID] = SimpleNamespace(asc_path=Path("a.asc"))
    monkeypatch.setattr(_ASC_PATCH, lambda _: 13)

    with pytest.raises(
        ValueError, match="cannot be found in the stimulus order versions"
    ):
        obj._resolve_stim_order_version(SID, "001", 13, asc_available=True)


def test_skipped_session_uses_logfile_version():
    obj = _base_obj({"participant_id": [999], "version_number": [13], "v": [1]})

    row = obj._resolve_stim_order_version(SID, "001", 13, asc_available=False)

    assert row["version_number"].iloc[0] == 13


def test_warning_banner_goes_to_stderr(capsys):
    obj = _base_obj({"participant_id": [1], "version_number": [13]})

    obj._warn_stim_order_missing("001")

    err = capsys.readouterr().err
    assert "WARNING: Participant ID 001 not found" in err
    assert "-" * 20 in err


def test_merid_override_uses_shared_fallback(tmp_path, capsys, monkeypatch):
    obj = _make_collection(
        MeridDataCollection,
        {
            "participant_id": [999],
            "version_number": [13],
            **{f"col{i}": [i] for i in range(8)},
        },
    )
    obj.sessions[SID] = SimpleNamespace(asc_path=Path("a.asc"))
    monkeypatch.setattr(_ASC_PATCH, lambda _: 13)

    stimulus_order = obj._load_session_stimulus_order(SID, logfile_order_version=13)

    assert stimulus_order == [0, 2, 3, 4, 5, 6]
    assert "Participant ID 001 not found" in capsys.readouterr().err
