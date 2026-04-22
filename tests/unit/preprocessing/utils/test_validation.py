import pytest
from preprocessing.utils.data_path_utils import is_valid_pid, is_valid_sid, parse_sid


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


@pytest.mark.parametrize(
    "sid, expected",
    [
        # Standard valid SIDs
        ("002_ZH_CH_1_PT2", True),
        ("001_EN_US_Lab1_ET1", True),
        ("999_DE_DE_9_S1", True),
        # Case sensitivity
        ("002_zh_CH_1_PT2", False),  # lowercase lang
        ("002_ZH_ch_1_PT2", False),  # lowercase country
        # Length constraints
        ("002_Z_CH_1_PT2", False),  # too short lang
        ("002_ZH_C_1_PT2", False),  # too short country
        # Empty parts
        ("002_ZH_CH__PT2", False),  # empty lab
        ("002_ZH_CH_1_", False),  # empty session
        # Invalid PID
        ("02_ZH_CH_1_PT2", False),
        # Not enough parts
        ("002_ZH_CH_1", False),
        # Extended formats (all should be True)
        ("002_ZH_CH_1_PT2_Extra", True),
        ("002_ZH_CH_1_PT1_full_restart", True),
        ("002_ZH_CH_1_PT1_start_after_trial_10", True),
        ("002_ZH_CH_1_PT1_many_underscores_trailing", True),
        # Invalid types
        (None, False),
        (123, False),
    ],
)
def test_is_valid_sid(sid: str, expected: bool):
    """Test is_valid_sid function with various inputs."""
    assert is_valid_sid(sid) == expected


@pytest.mark.parametrize(
    "sid, expected_parts",
    [
        (
            "002_ZH_CH_1_PT2",
            {
                "pid": "002",
                "lang": "ZH",
                "country": "CH",
                "lab": "1",
                "session": "PT2",
                "postfix": "",
                "full_session": "PT2",
                "notes": "",
            },
        ),
        (
            "002_ZH_CH_1_PT1_full_restart",
            {
                "pid": "002",
                "session": "PT1",
                "postfix": "full_restart",
                "full_session": "PT1_full_restart",
                "notes": "Session has been fully restarted.",
            },
        ),
        (
            "002_ZH_CH_1_PT1_start_after_trial_42",
            {
                "pid": "002",
                "session": "PT1",
                "postfix": "start_after_trial_42",
                "full_session": "PT1_start_after_trial_42",
                "notes": "Session has been restarted after trial 42.",
            },
        ),
        (
            "002_ZH_CH_1_PT1_some_extra_info",
            {
                "pid": "002",
                "session": "PT1",
                "postfix": "some_extra_info",
                "full_session": "PT1_some_extra_info",
                "notes": "",
            },
        ),
        (
            "002_ZH_CH_1_PT1_with_many_underscores_here",
            {
                "pid": "002",
                "session": "PT1",
                "postfix": "with_many_underscores_here",
                "full_session": "PT1_with_many_underscores_here",
                "notes": "",
            },
        ),
        (
            "001_EN_GB_Lab1_S1_trailing_",
            {
                "pid": "001",
                "lang": "EN",
                "country": "GB",
                "lab": "Lab1",
                "session": "S1",
                "postfix": "trailing_",
                "full_session": "S1_trailing_",
                "notes": "",
            },
        ),
        (
            "001_EN_GB_Lab1_S1__double_underscore",
            {
                "pid": "001",
                "lang": "EN",
                "country": "GB",
                "lab": "Lab1",
                "session": "S1",
                "postfix": "_double_underscore",
                "full_session": "S1__double_underscore",
                "notes": "",
            },
        ),
        (
            "001_EN_GB_Lab1_S1_start_after_trial_invalid",
            {
                "pid": "001",
                "lang": "EN",
                "country": "GB",
                "lab": "Lab1",
                "session": "S1",
                "postfix": "start_after_trial_invalid",
                "full_session": "S1_start_after_trial_invalid",
                "notes": "",
            },
        ),
    ],
)
def test_parse_sid_valid_cases(sid: str, expected_parts: dict):
    """Test parse_sid with various valid (by design) formats."""
    result = parse_sid(sid)
    assert result is not None
    for key, value in expected_parts.items():
        assert result[key] == value


@pytest.mark.parametrize(
    "invalid_sid",
    [
        "invalid",
        "002_ZH_CH_1",  # Too few parts
        "02_ZH_CH_1_PT2",  # Invalid PID
        "002_zh_CH_1_PT2",  # lowercase lang
        "002_ZH_ch_1_PT2",  # lowercase country
        "002_ZH_CH__PT2",  # empty lab
        "002_ZH_CH_1_",  # empty session
        None,
        123,
    ],
)
def test_parse_sid_invalid_cases(invalid_sid):
    """Test parse_sid returns None for various invalid inputs (resulting in errors)."""
    assert parse_sid(invalid_sid) is None
