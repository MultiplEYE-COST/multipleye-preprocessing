"""Tests for the conversions utils submodule."""

import time
from datetime import timedelta

import pytest

from preprocessing.utils.conversion import convert_to_time_str


@pytest.mark.parametrize(
    "duration_ms, expected",
    [
        (0, "00:00:00"),  # Edge case: zero duration
        (1000, "00:00:01"),  # Exactly one second
        (60000, "00:01:00"),  # Exactly one minute
        (1000.0, "00:00:01"),  # Exactly one second
        (60000.0, "00:01:00"),  # Exactly one minute
        (127605, "00:02:07"),
        (3600000, "01:00:00"),  # Exactly one hour
        (3661000, "01:01:01"),  # Complex case: 1 hour, 1 minute, 1 second
        # test maximal integer value
        (86399000, "23:59:59"),
        (86399999, "23:59:59"),
        (86399999.999999, "23:59:59"),
    ],
)
def test_valid_durations(duration_ms, expected):
    """Test valid durations for `convert_to_time_str`."""
    assert convert_to_time_str(duration_ms) == expected


@pytest.mark.parametrize(
    "duration_ms, expected_message",
    [
        ("1000", "Duration must be a number: "),
        (None, "Duration must be a number: "),
        ([1000], "Duration must be a number: "),
        (-1, "Duration cannot be negative: "),
        (-1000, "Duration cannot be negative: "),
        (-3600000, "Duration cannot be negative: "),
        (86400000, "Duration overflow: 86400000ms exceeds 24 hours"),
        (96400000, "Duration overflow:"),
    ],
)
def test_invalid_input_types(duration_ms, expected_message):
    """Test that non-numeric inputs and negative values raise ValueError with a message."""
    with pytest.raises(ValueError, match=expected_message):
        convert_to_time_str(duration_ms)


@pytest.mark.parametrize(
    "duration_ms",
    [
        0,
        1000,
        60000,
        127605,
        3600000,
        3661000,
        5000,
        90000,
        7200000,
    ],
)
def test_against_time_library(duration_ms):
    """Test that convert_to_time_str matches time.strftime with timedelta."""
    td = timedelta(milliseconds=duration_ms)
    expected = time.strftime("%H:%M:%S", time.gmtime(td.total_seconds()))
    assert convert_to_time_str(duration_ms) == expected
