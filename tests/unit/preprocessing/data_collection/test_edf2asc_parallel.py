"""Tests for parallel, staging-dir based EDF to ASC conversion."""

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


def _staging_leftovers() -> list[Path]:
    out = settings.OUTPUT_DIR
    return list(out.glob("**/.edf2asc-*")) if out.exists() else []


def _write_asc_for(cmd, content: str = "asc") -> None:
    """Emulate `edf2asc -y -c -p <dir> <edf>` by writing into the -p directory."""
    staging_dir = Path(cmd[cmd.index("-p") + 1])
    edf = Path(cmd[-1])
    (staging_dir / f"{edf.stem}.asc").write_text(content)


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
    calls = []

    def fake_run(cmd, **kwargs):
        assert "-c" in cmd
        assert "-p" in cmd
        calls.append(cmd)
        with lock:
            state["current"] += 1
            state["peak"] = max(state["peak"], state["current"])
        time.sleep(0.05)
        with lock:
            state["current"] -= 1
        _write_asc_for(cmd)
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
        # Nothing was written next to the .edf.
        assert (
            not collection.sessions[name].session_file_path.with_suffix(".asc").exists()
        )
    assert _staging_leftovers() == []


def test_failed_conversion_goes_to_skipped_sessions_and_leaves_nothing(
    tmp_path, monkeypatch
):
    collection = _make_collection(tmp_path, ["ok", "broken"])

    def fake_run(cmd, **kwargs):
        if Path(cmd[-1]).stem == "ok":
            _write_asc_for(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(
        "preprocessing.data_collection.multipleye_data_collection.subprocess.run",
        fake_run,
    )

    collection.convert_edf_to_asc()

    assert set(collection.sessions) == {"ok"}
    assert set(collection.skipped_sessions) == {"broken"}
    # No partial ASC for the failed session and no staging directories left.
    assert not (settings.OUTPUT_DIR / "asc" / "broken" / "broken.asc").exists()
    assert _staging_leftovers() == []


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
    assert _staging_leftovers() == []
