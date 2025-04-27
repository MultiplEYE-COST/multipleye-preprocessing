import pytest
import experiment_frame


@pytest.mark.parametrize("filepath, expected", [
    ("tests/test_data_collection.py", "test_data_collection"),
    ("tests/test_experiment_frame.py", "test_experiment_frame"),
])
def test_get_test_file_name(filepath, expected):
    """
    Test the get_test_file_name function.
    """
    result = experiment_frame.get_test_file_name(filepath)
    assert result == expected
