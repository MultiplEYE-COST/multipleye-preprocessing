"""Unit tests for the data_path_utils module."""

from pathlib import Path

import pytest
from preprocessing.utils.data_path_utils import pid_from_session


@pytest.mark.parametrize(
    "folder, expected",
    [
        (Path("/data/project/001_session"), "001"),
        (Path("/data/project/002_session_other"), "002"),
        ("003_session_id", "003"),
        ("004_session", "004"),
        (Path("/data/project/123.ext"), "123"),
        (Path("/data/project/./..//001/"), "001"),  # resolve to normalize paths
        (Path("data/project/005_session"), "005"),  # relative path without leading /
        (Path("006_session_name"), "006"),  # relative path single level
        (Path("./007_local_session"), "007"),  # current directory relative path
        (Path("../008_parent_session"), "008"),  # parent directory relative path
        (Path("project/sub/009_nested"), "009"),  # nested relative path
        ("010_string_relative", "010"),  # string without path separators
    ],
)
def test_pid_from_session_valid_inputs(folder, expected):
    """
    Test valid inputs for pid_from_session to ensure correct PID extraction.
    """
    result = pid_from_session(folder)
    assert result == expected


@pytest.mark.parametrize(
    "folder",
    [
        Path("/data/project/.001_hidden_folder"),
        Path("/data/project/abc123"),
        Path("/data/project/"),
        "only_two",
        Path(""),
        "",
        Path("folder/011_session/subfolder"),
        "data/project/005_session",  # when passing a string, folders are not allowed
    ],
)
def test_pid_from_session_value_error(folder):
    """
    Test pid_from_session raises ValueError for PIDs that are not exactly three digits,
    or for invalid string inputs containing path separators.
    """
    with pytest.raises(ValueError):
        pid_from_session(folder)


@pytest.mark.parametrize("invalid_folder", [123, None, type])
def test_pid_from_session_type_error(invalid_folder):
    """
    Test pid_from_session for handling incorrect input types.
    """
    with pytest.raises(TypeError):
        pid_from_session(invalid_folder)
