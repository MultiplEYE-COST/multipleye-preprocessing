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
