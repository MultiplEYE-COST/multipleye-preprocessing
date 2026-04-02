from __future__ import annotations

import os
from pathlib import Path

import pytest

from preprocessing.utils.data_path_utils import check_data_collection_exists
from preprocessing.utils.data_path_utils import pid_from_session


@pytest.mark.parametrize(
    "folder, expected_pid",
    [
        ("001_session", "001"),
        (Path("042_session"), "042"),
        ("123", "123"),
        (Path("999"), "999"),
    ],
)
def test_pid_from_session_valid(folder, expected_pid):
    """Test pid_from_session with valid inputs."""
    assert pid_from_session(folder) == expected_pid


@pytest.mark.parametrize(
    "folder, expected_error, error_msg",
    [
        (123, TypeError, "folder must be of type Path or str."),
        (
            "abc_session",
            ValueError,
            "PID must be exactly three digits (possibly zero-padded), got 'abc' from 'abc_session'.",
        ),
        (
            "12_session",
            ValueError,
            "PID must be exactly three digits (possibly zero-padded), got '12_' from '12_session'.",
        ),
        (
            Path("ab_session"),
            ValueError,
            "PID must be exactly three digits (possibly zero-padded), got 'ab_' from 'ab_session'.",
        ),
    ],
)
def test_pid_from_session_invalid_format(folder, expected_error, error_msg):
    """Test pid_from_session with invalid formats."""
    with pytest.raises(expected_error) as excinfo:
        pid_from_session(folder)
    assert str(excinfo.value) == error_msg


@pytest.mark.parametrize(
    "folder",
    [
        "session" + os.sep + "001",
    ],
)
def test_pid_from_session_path_separator(folder):
    """Test pid_from_session with string containing path separators."""
    # Only run if os.sep is actually in the folder string (which it should be from param)
    with pytest.raises(ValueError) as excinfo:
        pid_from_session(folder)
    assert (
        "String input must be a simple session identifier without path separators"
        in str(excinfo.value)
    )


def test_check_data_collection_exists_success(tmp_path):
    """Test check_data_collection_exists when the folder exists and has data."""
    data_collection_name = "MultiplEYE_Test"
    data_folder = tmp_path / data_collection_name
    data_folder.mkdir()
    (data_folder / "some_data.txt").touch()

    result = check_data_collection_exists(data_collection_name, tmp_path)
    assert result == data_folder


def test_check_data_collection_exists_failure(tmp_path):
    """Test check_data_collection_exists when the folder does not exist."""
    data_collection_name = "NonExistent"

    with pytest.raises(FileNotFoundError) as excinfo:
        check_data_collection_exists(data_collection_name, tmp_path)

    assert (
        f"The data collection folder '{data_collection_name}' was not found in '{tmp_path}'"
        in str(excinfo.value)
    )
    assert "Please check if 'data_collection_name' is correctly set" in str(
        excinfo.value
    )


@pytest.mark.parametrize(
    "files_to_create, expected_error, expected_msg_part",
    [
        ([], FileNotFoundError, "exists but appears to be empty"),
        (
            ["preprocessing_logs.txt"],
            FileNotFoundError,
            "exists but appears to be empty (or only contains log files)",
        ),
        ([".DS_Store"], FileNotFoundError, "exists but appears to be empty"),
        (["data_file.csv"], None, None),
    ],
    ids=[
        "empty_folder",
        "only_logs",
        "only_hidden_files",
        "meaningful_data",
    ],
)
def test_check_data_collection_exists_empty_or_only_logs(
    tmp_path,
    files_to_create,
    expected_error,
    expected_msg_part,
):
    """Test check_data_collection_exists when folder is empty or only contains logs."""
    data_collection_name = "TestCollection"
    data_folder = tmp_path / data_collection_name
    data_folder.mkdir()

    for file_name in files_to_create:
        (data_folder / file_name).touch()

    if expected_error:
        with pytest.raises(expected_error) as excinfo:
            check_data_collection_exists(data_collection_name, tmp_path)
        assert expected_msg_part in str(excinfo.value)
    else:
        result = check_data_collection_exists(data_collection_name, tmp_path)
        assert result == data_folder
