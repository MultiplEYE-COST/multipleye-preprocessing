"""Tests for stimulus-order version detection used for question-image copying."""

from pathlib import Path

import pytest

from preprocessing.config import settings
from preprocessing.scripts.prepare_language_folder import _get_used_stimulus_versions

ASC_VERSION_LINE = "MSG\t1133572 stimulus_order_version: 13\n"
LOGFILE_VERSION_TEXT = "4678.7\t*** STIMULUS_ORDER_VERSION_7\n"


@pytest.fixture(autouse=True)
def _settings(tmp_path, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(settings, "ASC_FOLDER", Path("asc/"))
    monkeypatch.setattr(settings, "INCLUDE_SESSIONS", [])
    monkeypatch.setattr(settings, "EXCLUDE_SESSIONS", [])
    monkeypatch.setattr(settings, "INCLUDE_PILOTS", False)


def _session(sessions_dir, sid, *, logfile=None, asc=None, output_asc=None):
    folder = sessions_dir / sid
    (folder / "logfiles").mkdir(parents=True)
    if logfile is not None:
        (folder / "logfiles" / "GENERAL_LOGFILE_1.txt").write_text(logfile)
    if asc is not None:
        (folder / f"{sid}.asc").write_text(asc)
    if output_asc is not None:
        out = settings.OUTPUT_DIR / settings.ASC_FOLDER / sid
        out.mkdir(parents=True)
        (out / f"{sid}.asc").write_text(output_asc)
    return folder


def test_logfile_is_detected(tmp_path):
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", logfile=LOGFILE_VERSION_TEXT)
    assert _get_used_stimulus_versions(sessions) == {7}


def test_raw_asc_fallback(tmp_path):
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", asc=ASC_VERSION_LINE)
    assert _get_used_stimulus_versions(sessions) == {13}


def test_output_asc_fallback(tmp_path):
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", output_asc=ASC_VERSION_LINE)
    assert _get_used_stimulus_versions(sessions) == {13}


def test_logfile_preferred_over_asc(tmp_path):
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", logfile=LOGFILE_VERSION_TEXT, asc=ASC_VERSION_LINE)
    assert _get_used_stimulus_versions(sessions) == {7}


def test_no_version_source_is_empty(tmp_path):
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X")
    assert _get_used_stimulus_versions(sessions) == set()


def test_union_including_pilot_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "INCLUDE_PILOTS", True)
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", logfile=LOGFILE_VERSION_TEXT)
    _session(
        sessions / "pilot_sessions",
        "002_X",
        logfile="x\t*** STIMULUS_ORDER_VERSION_9\n",
    )
    assert _get_used_stimulus_versions(sessions) == {7, 9}


def test_pilots_excluded_when_not_included(tmp_path):
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", logfile=LOGFILE_VERSION_TEXT)
    _session(
        sessions / "pilot_sessions",
        "002_X",
        logfile="x\t*** STIMULUS_ORDER_VERSION_9\n",
    )
    assert _get_used_stimulus_versions(sessions) == {7}


def test_excluded_session_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EXCLUDE_SESSIONS", ["002_X"])
    sessions = tmp_path / "sessions"
    _session(sessions, "001_X", logfile=LOGFILE_VERSION_TEXT)
    _session(sessions, "002_X", logfile="x\t*** STIMULUS_ORDER_VERSION_9\n")
    assert _get_used_stimulus_versions(sessions) == {7}
