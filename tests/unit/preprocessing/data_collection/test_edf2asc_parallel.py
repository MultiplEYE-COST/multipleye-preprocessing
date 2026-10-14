"""Tests for parallel EDF to ASC conversion."""

import logging
import subprocess
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from preprocessing.config import settings
from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)

WORKERS = "EDF2ASC_WORKERS"


def _make_collection(tmp_path: Path, session_names: list[str]):
    collection = object.__new__(MultipleyeDataCollection)
    collection.eye_tracker = "eyelink"
    collection.logger = logging.getLogger("test")
    collection.skipped_sessions = {}
    collection.sessions = {}
    for name in session_names:
        edf = tmp_path / f"{name}.edf"
        edf.write_text("edf")
        collection.sessions[name] = SimpleNamespace(
            session_file_path=edf,
            asc_path=None,
        )
    return collection


@pytest.fixture(autouse=True)
def _settings(tmp_path, monkeypatch):
    monkeypatch.setitem(settings.__dict__, "OUTPUT_DIR", tmp_path / "out")
    monkeypatch.setattr(settings, "ASC_FOLDER", Path("asc/"))
    monkeypatch.setattr(settings, "FORCE_RECONVERT_ASC", False)
    monkeypatch.setattr(settings, WORKERS, 2)
    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.shutil.which",
        lambda name: "/usr/bin/edf2asc",
    )


def test_converts_sessions_in_parallel(tmp_path, monkeypatch):
    collection = _make_collection(tmp_path, ["s1", "s2", "s3"])

    lock = threading.Lock()
    state = {"current": 0, "peak": 0}

    def fake_run(cmd, **kwargs):
        assert cmd[0] == "edf2asc"
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        Path(cmd[-1]).with_suffix(".asc").write_text("asc")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
        fake_run,
    )

    collection.convert_edf_to_asc()

    assert state["peak"] >= 2, "conversions did not run concurrently"
    assert set(collection.sessions) == {"s1", "s2", "s3"}
    assert collection.skipped_sessions == {}
    for name in ("s1", "s2", "s3"):
        asc = collection.sessions[name].asc_path
        assert asc == settings.OUTPUT_DIR / "asc" / name / f"{name}.asc"
        assert asc.read_text() == "asc"


def test_failed_conversion_goes_to_skipped_sessions(tmp_path, monkeypatch):
    collection = _make_collection(tmp_path, ["ok", "broken"])

    def fake_run(cmd, **kwargs):
        # Only produce an ASC for the "ok" file.
        if Path(cmd[-1]).stem == "ok":
            Path(cmd[-1]).with_suffix(".asc").write_text("asc")
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
        fake_run,
    )

    collection.convert_edf_to_asc()

    assert set(collection.sessions) == {"ok"}
    assert set(collection.skipped_sessions) == {"broken"}


def test_existing_asc_is_not_reconverted(tmp_path, monkeypatch):
    output_asc = settings.OUTPUT_DIR / "asc" / "s1" / "s1.asc"
    output_asc.parent.mkdir(parents=True)
    output_asc.write_text("existing")

    collection = _make_collection(tmp_path, ["s1"])
    calls = []

    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
        lambda cmd, **kwargs: calls.append(cmd),
    )

    collection.convert_edf_to_asc()

    assert calls == []
    assert collection.sessions["s1"].asc_path == output_asc
    assert output_asc.read_text() == "existing"
