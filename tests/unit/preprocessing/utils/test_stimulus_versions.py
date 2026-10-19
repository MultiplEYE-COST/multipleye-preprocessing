"""Tests for the shared stimulus content version helpers."""

from pathlib import Path

import pytest

from preprocessing import settings
from preprocessing.utils.stimulus_versions import (
    configured_version_suffixes,
    default_version_suffix,
    stimulus_folder_name,
    version_dir,
    version_suffix_for_pid,
)

DCN = "MultiplEYE_EN_UK_London_1_2025"


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_DEFAULT_VERSION", None)
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_PID_MAP", {})


@pytest.mark.parametrize(
    "default_version, pid_map, expected",
    [
        (None, {}, [None]),
        (None, {"v1": ["002"]}, [None, "v1"]),
        (None, {"v1": ["002"], "v2": ["003"]}, [None, "v1", "v2"]),
        ("v2", {"v1": ["002"]}, ["v2", "v1"]),
        ("v2", {}, ["v2"]),
    ],
)
def test_configured_version_suffixes(monkeypatch, default_version, pid_map, expected):
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_DEFAULT_VERSION", default_version)
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_PID_MAP", pid_map)
    assert configured_version_suffixes() == expected


def test_default_version_suffix(monkeypatch):
    assert default_version_suffix() is None
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_DEFAULT_VERSION", "v2")
    assert default_version_suffix() == "v2"


def test_version_suffix_for_pid_mapped(monkeypatch):
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_PID_MAP", {"v1": ["002", "005"]})
    assert version_suffix_for_pid("002") == "v1"
    assert version_suffix_for_pid("005") == "v1"


def test_version_suffix_for_pid_unmapped_uses_default(monkeypatch):
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_PID_MAP", {"v1": ["002"]})
    assert version_suffix_for_pid("009") is None
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_DEFAULT_VERSION", "v2")
    assert version_suffix_for_pid("009") == "v2"


def test_stimulus_folder_name():
    assert stimulus_folder_name(DCN, None) == f"stimuli_{DCN}"
    assert stimulus_folder_name(DCN, "v1") == f"stimuli_{DCN}_v1"


def test_version_dir(tmp_path):
    base = tmp_path / f"stimuli_{DCN}"
    assert version_dir(base, None) == base
    assert version_dir(base, "v1") == tmp_path / f"stimuli_{DCN}_v1"
    assert isinstance(version_dir(base, "v1"), Path)
