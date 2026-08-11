"""Unit tests for per-session stimulus version folder resolution."""

import pytest
import pandas as pd

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)
from preprocessing import settings


@pytest.fixture
def mock_lab_config(monkeypatch):
    """Fixture to mock MultipleyeDataCollection.load_lab_config."""

    class MockLabConfig:
        def __init__(self):
            self.name_eye_tracker = "EyeLink 1000 Plus"
            self.psychometric_tests = {}

    monkeypatch.setattr(
        MultipleyeDataCollection,
        "load_lab_config",
        lambda *args, **kwargs: MockLabConfig(),
    )


@pytest.fixture
def dummy_data_dir(tmp_path):
    """Fixture to create a dummy data collection folder structure."""
    collection_name = "MultiplEYE_EN_UK_London_1_2025"
    data_dir = tmp_path / collection_name
    data_dir.mkdir()

    et_sessions_dir = data_dir / "eye-tracking-sessions"
    et_sessions_dir.mkdir()
    (data_dir / "psychometric-tests").mkdir()

    # Default stimulus folder
    stimuli_dir = data_dir / f"stimuli_{collection_name}"
    stimuli_dir.mkdir()
    config_dir = stimuli_dir / "config"
    config_dir.mkdir()

    # Versioned stimulus folder
    v2_stimuli_dir = data_dir / f"stimuli_{collection_name}_v2"
    v2_stimuli_dir.mkdir()
    v2_config_dir = v2_stimuli_dir / "config"
    v2_config_dir.mkdir()

    # Dummy stimulus order versions files (different per version)
    df_v1 = pd.DataFrame({"participant_id": [1, 2], "version_number": [1, 1]})
    df_v1.to_csv(config_dir / "stimulus_order_versions_EN_UK_1.csv", index=False)

    df_v2 = pd.DataFrame({"participant_id": [3], "version_number": [2]})
    df_v2.to_csv(v2_config_dir / "stimulus_order_versions_EN_UK_1.csv", index=False)

    # Dummy session folders (3 sessions, pid 003 is in v2)
    for s_id in ["001_EN_UK_1_ET1", "002_EN_UK_1_ET1", "003_EN_UK_1_ET1"]:
        s_path = et_sessions_dir / s_id
        s_path.mkdir()
        (s_path / "data.edf").touch()

    return data_dir


@pytest.fixture
def monkeypatch_settings(monkeypatch):
    """Configure stimulus version settings."""
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_DEFAULT_VERSION", None)
    monkeypatch.setattr(settings, "STIMULUS_VERSIONS_PID_MAP", {"v2": ["003"]})


def test_create_from_data_folder_builds_pid_stimulus_dirs(
    dummy_data_dir, mock_lab_config, monkeypatch_settings
):
    """create_from_data_folder builds a pid -> stimulus_dir map from config."""
    dc = MultipleyeDataCollection.create_from_data_folder(dummy_data_dir)

    assert dc.pid_stimulus_dirs is not None
    assert "003" in dc.pid_stimulus_dirs
    assert (
        dc.pid_stimulus_dirs["003"].name == "stimuli_MultiplEYE_EN_UK_London_1_2025_v2"
    )


def test_create_from_data_folder_no_versions_no_map(dummy_data_dir, mock_lab_config):
    """Without stimulus version config, no pid map is built."""
    dc = MultipleyeDataCollection.create_from_data_folder(dummy_data_dir)
    assert dc.pid_stimulus_dirs is None


def test_resolve_stimulus_dir_maps_pid(
    dummy_data_dir, mock_lab_config, monkeypatch_settings
):
    """_resolve_stimulus_dir returns the versioned dir for a mapped PID."""
    dc = MultipleyeDataCollection.create_from_data_folder(dummy_data_dir)
    v2_dir = dc.pid_stimulus_dirs["003"]
    assert dc._resolve_stimulus_dir("003_EN_UK_1_ET1") == v2_dir


def test_resolve_stimulus_dir_default_for_unmapped(
    dummy_data_dir, mock_lab_config, monkeypatch_settings
):
    """Unmapped PIDs fall back to the default stimulus dir."""
    dc = MultipleyeDataCollection.create_from_data_folder(dummy_data_dir)
    assert dc._resolve_stimulus_dir("001_EN_UK_1_ET1") == dc.stimulus_dir


def test_resolve_stimulus_dir_no_map_uses_default(dummy_data_dir, mock_lab_config):
    """Without a pid map, all sessions use the default stimulus dir."""
    dc = MultipleyeDataCollection.create_from_data_folder(dummy_data_dir)
    assert dc._resolve_stimulus_dir("001_EN_UK_1_ET1") == dc.stimulus_dir
    assert dc._resolve_stimulus_dir("003_EN_UK_1_ET1") == dc.stimulus_dir


def test_load_stim_order_versions_from_versioned_dir(
    dummy_data_dir, mock_lab_config, monkeypatch_settings
):
    """_load_stim_order_versions reads the CSV from the session's version folder."""
    dc = MultipleyeDataCollection.create_from_data_folder(dummy_data_dir)

    # PID 003 is mapped to v2; its version folder CSV only lists pid 3 with version 2
    df = dc._load_stim_order_versions("003_EN_UK_1_ET1")
    assert int(df.iloc[0]["participant_id"]) == 3
    assert int(df.iloc[0]["version_number"]) == 2

    # PID 001 is not mapped; it reads the default folder CSV
    df_default = dc._load_stim_order_versions("001_EN_UK_1_ET1")
    assert int(df_default.iloc[0]["participant_id"]) == 1
