"""Tests for threshold comparison logic."""

import pytest
from review_app.services.thresholds import compare, check_value


class TestCompare:
    @pytest.mark.parametrize(
        ("value", "threshold", "expected"),
        [
            (5, [0, 10], "pass"),
            (0, [0, 10], "pass"),
            (10, [0, 10], "pass"),
            (-5, [0, 10], "fail"),
            (20, [0, 10], "fail"),
            (10.5, [0, 10], "warn"),
            (-0.5, [0, 10], "warn"),
            (5, None, "pass"),
            ("GOOD", ["GOOD"], "pass"),
            ("BAD", ["GOOD"], "fail"),
            (0.2, 0.3, "pass"),
            (0.5, 0.3, "fail"),
            (0.32, 0.3, "warn"),
            ("Desktop", "Desktop", "pass"),
            ("Tower", "Desktop", "fail"),
            ("foo", [0, 10], "pass"),
        ],
    )
    def test_compare(self, value, threshold, expected) -> None:
        assert compare(value, threshold) == expected


class TestCheckValue:
    def test_with_thresholds_dict(self) -> None:
        thresholds = {"num_calibrations": [3, 30]}
        spec, status = check_value("num_calibrations", 5, thresholds)
        assert status == "pass"
        assert spec == [3, 30]

    def test_missing_key(self) -> None:
        thresholds = {"num_calibrations": [3, 30]}
        spec, status = check_value("unknown_field", 5, thresholds)
        assert status == "pass"
        assert spec is None

    def test_none_thresholds(self) -> None:
        spec, status = check_value("anything", 5, None)
        assert status == "pass"
        assert spec is None

    def test_range_warn_boundary(self) -> None:
        """Within 10% of [min, max] boundary should warn."""
        thresholds = {"num_completed_trials": [6, 12]}
        # 5.4 is within 10% of 6 (margin = 0.6)
        spec54, status54 = check_value("num_completed_trials", 5.4, thresholds)
        assert status54 == "warn"

    def test_range_as_minimum_threshold(self) -> None:
        """num_completed_trials uses [6, 12] as a 'minimum' threshold:
        4 should fail, 6 should pass, 12 should pass."""
        thresholds = {"num_completed_trials": [6, 12]}
        spec4, status4 = check_value("num_completed_trials", 4, thresholds)
        assert status4 == "fail"
        spec6, status6 = check_value("num_completed_trials", 6, thresholds)
        assert status6 == "pass"
        spec12, status12 = check_value("num_completed_trials", 12, thresholds)
        assert status12 == "pass"
