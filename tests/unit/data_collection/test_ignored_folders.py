import re
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

    # Mock directory entry
    mock_entry = MagicMock()
    mock_entry.name = folder_name
    mock_entry.is_dir.return_value = True
    mock_entry.path = str(data_root / folder_name)

    # If it matches the regex, we need to mock glob to avoid errors in the matching branch
    if re.match(regex, folder_name, re.IGNORECASE):
        # We don't want to test the matching branch here, just ensure it doesn't crash
        # or we can just skip the globbing by making it not a dir for that part if possible
        # but the code calls glob if it matches.
        pass

    with (
        patch("os.scandir", return_value=[mock_entry]),
        patch("builtins.print") as mock_print,
        patch("pathlib.Path.glob", return_value=[Path("fake.edf")]),
    ):  # Mock edf file if matches
        instance.add_recorded_sessions(data_root, regex)

        warning_msg = f"Folder {folder_name} does not match the regex pattern {regex}. Not considered as session."

        if should_warn:
            mock_print.assert_called_with(warning_msg)
        else:
            # Ensure it was NOT called with the warning message
            for call in mock_print.call_args_list:
                assert warning_msg not in call[0][0]
