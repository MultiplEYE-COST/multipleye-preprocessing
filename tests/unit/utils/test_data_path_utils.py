from __future__ import annotations

import pytest

from preprocessing.utils.data_path_utils import check_data_collection_exists


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
