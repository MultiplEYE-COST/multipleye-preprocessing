import pytest
from preprocessing.utils.data_path_utils import is_valid_pid


@pytest.mark.parametrize(
    "pid, expected",
    [
        # Valid PIDs
        ("001", True),
        ("123", True),
        ("999", True),
        # Invalid lengths
        ("0", False),
        ("00", False),
        ("0001", False),
        # Non-numeric
        ("abc", False),
        ("12a", False),
        ("1.2", False),
        ("-12", False),
        # Whitespace
        ("", False),
        (" 12", False),
        ("12 ", False),
        # Types
        (None, False),
        (123, False),
    ],
)
def test_is_valid_pid(pid: str, expected: bool):
    """Test is_valid_pid function with various inputs."""
    assert is_valid_pid(pid) == expected
