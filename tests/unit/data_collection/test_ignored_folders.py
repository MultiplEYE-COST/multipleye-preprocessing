from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from preprocessing.data_collection.multipleye_data_collection import (
    MultipleyeDataCollection,
)


@pytest.fixture
def mock_multipleye_instance():
    """Create a MultipleyeDataCollection instance with minimal initialisation."""
    with patch.object(MultipleyeDataCollection, "__init__", return_value=None):
        instance = MultipleyeDataCollection(
            data_collection_name="test",
            stimulus_language="en",
            country="EE",
            year=2025,
            eye_tracker="eyelink",
            config_file=Path("config"),
            stimulus_dir=Path("stim"),
            lab_number=1,
            city="Tartu",
            data_root=Path("data"),
            lab_configuration=MagicMock(),
            session_folder_regex=r"\d\d\d_EE_EN_1_ET\d",
        )
        instance.sessions = {}
        instance.eye_tracker = "eyelink"
        instance.include_pilots = False
        instance.excluded_sessions = []
        instance.included_sessions = []
        # Provide a mocked logger used by the method under test
        instance.logger = MagicMock()
        return instance


@pytest.mark.parametrize(
    "folder_name, should_warn",
    [
        ("test_sessions", False),
        ("core_sessions", False),
        ("pilot_sessions", False),
        ("unknown_folder", True),
        ("999_EE_EN_1_ET1", False),  # This matches regex, so no "not match" warning
    ],
)
def test_add_recorded_sessions_logging(
    mock_multipleye_instance, folder_name, should_warn
):
    """Test that only non-ignored folders trigger a warning when not matching the regex."""
    instance = mock_multipleye_instance
    data_root = Path("/tmp/fake_data_root")
    regex = r"^\d{3}_EE_EN_1_ET\d$"

    # Mock directory entry for the folder under test
    mock_entry = MagicMock()
    mock_entry.name = folder_name
    mock_entry.is_dir.return_value = True
    mock_entry.path = str(data_root / folder_name)

    # Mock directory entry for a valid session folder to avoid ValueError: No sessions found
    valid_folder_name = "001_EE_EN_1_ET1"
    valid_entry = MagicMock()
    valid_entry.name = valid_folder_name
    valid_entry.is_dir.return_value = True
    valid_entry.path = str(data_root / valid_folder_name)

    with (
        patch("os.scandir", return_value=[mock_entry, valid_entry]),
        patch("pathlib.Path.glob", return_value=[Path("001_EE_EN_1_ET1_test.edf")]),
    ):
        instance.add_recorded_sessions(data_root, regex)

        warning_msg = f"Folder in eye-tracking-sessions {folder_name} does not match the eye-tracking session regex pattern {regex}. Not considered an eye-tracking session."

        if should_warn:
            instance.logger.warning.assert_called_with(warning_msg)
        else:
            # Ensure warning not emitted for ignored or matching folders
            calls = [args[0] for args, _ in instance.logger.warning.call_args_list]
            assert warning_msg not in calls
