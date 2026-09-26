import pandas as pd
import pytest

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)


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
    stimuli_dir = data_dir / f"stimuli_{collection_name}"
    stimuli_dir.mkdir()
    config_dir = stimuli_dir / "config"
    config_dir.mkdir()

    # Create dummy stimulus order versions file
    df = pd.DataFrame({"participant_id": [1, 2, 3], "version_number": [1, 1, 1]})
    df.to_csv(config_dir / "stimulus_order_versions_EN_UK_1.csv", index=False)

    # Create dummy session folders
    for s_id in ["001_EN_UK_1_ET1", "002_EN_UK_1_ET1", "003_EN_UK_1_ET1"]:
        s_path = et_sessions_dir / s_id
        s_path.mkdir()
        (s_path / "data.edf").touch()

    return data_dir


@pytest.mark.parametrize(
    "included, excluded",
    [
        (["001_EN_UK_1_ET1"], []),  # Only included
        (["001_EN_UK_1_ET1"], {}),
        ([], ["003_EN_UK_1_ET1"]),  # Only excluded
        ({}, ["003_EN_UK_1_ET1"]),
        ([], {"003_EN_UK_1_ET1"}),
        ([], []),  # Both empty
        (["001_EN_UK_1_ET1"], None),  # Excluded None
        (None, ["003_EN_UK_1_ET1"]),  # Included None
        (None, None),  # Both None
    ],
)
def test_create_from_data_folder_valid_session_lists(
    dummy_data_dir, mock_lab_config, included, excluded
):
    """Test that valid session lists (at most one non-empty) work correctly."""
    dc = MultipleyeDataCollection.create_from_data_folder(
        dummy_data_dir, included_sessions=included, excluded_sessions=excluded
    )

    included_sessions = included or []
    excluded_sessions = excluded or []

    if included_sessions:
        assert set(dc.sessions.keys()) == set(included_sessions)
    elif excluded_sessions:
        expected = {"001_EN_UK_1_ET1", "002_EN_UK_1_ET1", "003_EN_UK_1_ET1"} - set(
            excluded_sessions
        )
        assert set(dc.sessions.keys()) == expected
    else:
        assert set(dc.sessions.keys()) == {
            "001_EN_UK_1_ET1",
            "002_EN_UK_1_ET1",
            "003_EN_UK_1_ET1",
        }


def test_create_from_data_folder_both_not_empty_error(dummy_data_dir, mock_lab_config):
    """Test that providing both included and excluded sessions raises a detailed ValueError."""
    included = ["001_EN_UK_1_ET1"]
    excluded = ["003_EN_UK_1_ET1"]

    expected_msg = (
        "Both 'included_sessions' and 'excluded_sessions' are provided and not empty"
    )
    with pytest.raises(ValueError, match=expected_msg):
        MultipleyeDataCollection.create_from_data_folder(
            dummy_data_dir, included_sessions=included, excluded_sessions=excluded
        )


@pytest.mark.parametrize(
    "included, excluded, expected_count",
    [
        (["001_EN_UK_1_ET1", "002_EN_UK_1_ET1"], [], 2),
        ([], ["001_EN_UK_1_ET1"], 2),
        (["non_existent"], [], 0),  # Will raise ValueError because no sessions found
    ],
)
def test_filtering_logic_regression(
    dummy_data_dir, mock_lab_config, included, excluded, expected_count
):
    """Regression test for the filtering logic in add_recorded_sessions."""
    if expected_count == 0:
        with pytest.raises(ValueError, match="No sessions found"):
            MultipleyeDataCollection.create_from_data_folder(
                dummy_data_dir, included_sessions=included, excluded_sessions=excluded
            )
    else:
        dc = MultipleyeDataCollection.create_from_data_folder(
            dummy_data_dir, included_sessions=included, excluded_sessions=excluded
        )
        assert len(dc.sessions) == expected_count
