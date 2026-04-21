import pytest
from preprocessing.utils.data_path_utils import is_valid_pid, is_valid_sid

@pytest.mark.parametrize(
    "pid, expected",
    [
        ("001", True),
        ("123", True),
        ("999", True),
        ("00", False),
        ("0001", False),
        ("abc", False),
        ("12a", False),
        ("", False),
        (" 12", False),
        ("12 ", False),
        ("1.2", False),
        ("-12", False),
        (None, False),
        (123, False),
    ],
)
def test_is_valid_pid(pid: str, expected: bool):
    """Test is_valid_pid function with various inputs."""
    assert is_valid_pid(pid) == expected

@pytest.mark.parametrize(
    "sid, expected",
    [
        ("002_ZH_CH_1_PT2", True),
        ("001_EN_US_Lab1_ET1", True),
        ("999_DE_DE_9_S1", True),
        ("002_zh_CH_1_PT2", False),  # lowercase lang
        ("002_ZH_ch_1_PT2", False),  # lowercase country
        ("002_Z_CH_1_PT2", False),   # too short lang
        ("002_ZH_C_1_PT2", False),   # too short country
        ("002_ZH_CH__PT2", False),   # empty lab
        ("002_ZH_CH_1_", False),     # empty session
        ("02_ZH_CH_1_PT2", False),   # invalid PID
        ("002_ZH_CH_1", False),      # too few parts
        ("002_ZH_CH_1_PT2_Extra", False), # too many parts
        (None, False),
        (123, False),
    ],
)
def test_is_valid_sid(sid: str, expected: bool):
    """Test is_valid_sid function with various inputs."""
    assert is_valid_sid(sid) == expected
