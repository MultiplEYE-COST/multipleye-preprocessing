from pathlib import Path

import polars as pl

from preprocessing import settings
from preprocessing.checks.et_quality_checks import (
    check_metadata,
    check_validation_requirements,
)


def _validations_df(
    rows: list[tuple[int, float]],
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "time": [t for t, _ in rows],
            "accuracy_avg": [a for _, a in rows],
            "accuracy_max": [a for _, a in rows],
            "eye": ["R"] * len(rows),
        }
    )


def _calibrations_df(times: list[int]) -> pl.DataFrame:
    return pl.DataFrame({"time": times})


def _as_duration_us(frame: pl.DataFrame, column: str = "time") -> pl.DataFrame:
    """Return ``frame`` with ``column`` stored as pymovements-style Duration."""
    return frame.with_columns(
        (pl.col(column).cast(pl.Int64) * 1000).cast(pl.Duration("us"))
    )


def test_check_metadata_num_validations_uses_validation_range(monkeypatch):
    """Number of validations must be checked against ACCEPTABLE_NUM_VALIDATION."""
    monkeypatch.setattr(settings, "ACCEPTABLE_NUM_CALIBRATIONS", [3, 30])
    monkeypatch.setattr(settings, "ACCEPTABLE_NUM_VALIDATION", [13, 30])

    metadata = {
        "time": 100,
        "day": 1,
        "month": 1,
        "year": 2026,
        "tracked_eye": ["R"],
        "total_recording_duration_ms": 60000,
        "sampling_rate": 1000,
    }
    validations = _validations_df([(100, 0.1), (200, 0.2), (300, 0.3)])
    calibrations = _calibrations_df([50])

    calls: list[tuple] = []

    def report(name, values, acceptable_values, **kwargs):
        calls.append((name, values, acceptable_values))

    check_metadata(metadata, calibrations, validations, report)

    num_validations_call = next(c for c in calls if c[0] == "Number of validations")
    assert num_validations_call[1] == 3
    assert num_validations_call[2] == [13, 30]


def test_check_validation_requirements_uses_settings_thresholds(
    tmp_path: Path, monkeypatch
):
    """Validation classification must use settings thresholds, not hardcoded values."""
    monkeypatch.setattr(settings, "SINGLE_VALIDATION_GOOD_MAX", 0.2)
    monkeypatch.setattr(settings, "SINGLE_VALIDATION_MODERATE_MAX", 0.6)

    # 0.5 is BAD under the old hardcoded 0.45 threshold, MODERATE under the patched settings.
    validations = _validations_df([(1500, 0.5)])
    calibrations = _calibrations_df([])
    stimulus_times = [
        {"time": 1000, "message": "start_Recording_trial_1"},
        {"time": 2000, "message": "end_Recording_trial_1"},
    ]
    report_file = tmp_path / "report.md"

    check_validation_requirements(
        validations, calibrations, report_file, stimulus_times
    )

    text = report_file.read_text()
    assert "Moderate validation at 1500 with score 0.5" in text
    assert "BAD Validation at 1500" not in text


def test_check_validation_requirements_skips_aborted_validations(
    tmp_path: Path,
):
    """Aborted validations carry no accuracy and must not be scored."""
    validations = pl.DataFrame(
        {
            "time": [1500, 2000],
            "accuracy_avg": [0.1, None],
            "accuracy_max": [0.2, None],
            "eye": ["R", "R"],
            "grade": ["GOOD", "ABORTED"],
        }
    )
    calibrations = _calibrations_df([])
    stimulus_times = [
        {"time": 1000, "message": "start_Recording_trial_1"},
        {"time": 3000, "message": "end_Recording_trial_1"},
    ]
    report_file = tmp_path / "report.md"

    check_validation_requirements(
        validations, calibrations, report_file, stimulus_times
    )

    text = report_file.read_text()
    assert "- Good validations: 1/1" in text


def test_check_metadata_skips_aborted_validation_scores():
    """Aborted validations (null accuracy) must not break score reporting."""
    metadata = {
        "time": 100,
        "day": 1,
        "month": 1,
        "year": 2026,
        "tracked_eye": ["R"],
        "total_recording_duration_ms": 60000,
        "sampling_rate": 1000,
    }
    validations = pl.DataFrame(
        {
            "time": [100, 200],
            "accuracy_avg": [0.1, None],
            "accuracy_max": [0.2, None],
            "eye": ["R", "R"],
            "grade": ["GOOD", "ABORTED"],
        }
    )
    calibrations = _calibrations_df([50])

    calls: list[tuple] = []

    def report(name, values, acceptable_values, **kwargs):
        calls.append((name, values, acceptable_values))

    check_metadata(metadata, calibrations, validations, report)

    avg_call = next(c for c in calls if c[0] == "AVG validation scores")
    assert avg_call[1] == [0.1]


def test_check_validation_requirements_handles_duration_time_columns(
    tmp_path: Path, monkeypatch
):
    """Validations/calibrations may carry pymovements Duration time columns."""
    monkeypatch.setattr(settings, "SINGLE_VALIDATION_GOOD_MAX", 0.2)
    monkeypatch.setattr(settings, "SINGLE_VALIDATION_MODERATE_MAX", 0.6)

    validations = _as_duration_us(_validations_df([(1500, 0.5)]))
    calibrations = _as_duration_us(_calibrations_df([]))
    stimulus_times = [
        {"time": 1000, "message": "start_Recording_trial_1"},
        {"time": 2000, "message": "end_Recording_trial_1"},
    ]
    report_file = tmp_path / "report.md"

    check_validation_requirements(
        validations, calibrations, report_file, stimulus_times
    )

    text = report_file.read_text()
    assert "Moderate validation at 1500 with score 0.5" in text


def test_check_validation_requirements_default_boundaries(tmp_path: Path, monkeypatch):
    """Good/Moderate/BAD classification matches the default settings thresholds."""
    monkeypatch.setattr(settings, "SINGLE_VALIDATION_GOOD_MAX", 0.305)
    monkeypatch.setattr(settings, "SINGLE_VALIDATION_MODERATE_MAX", 0.45)

    validations = _validations_df([(100, 0.1), (200, 0.4), (300, 0.6)])
    calibrations = _calibrations_df([])
    stimulus_times = [
        {"time": 5000, "message": "start_Recording_trial_1"},
        {"time": 6000, "message": "end_Recording_trial_1"},
    ]
    report_file = tmp_path / "report.md"

    check_validation_requirements(
        validations, calibrations, report_file, stimulus_times
    )

    text = report_file.read_text()
    assert "- Good validations: 1/3" in text
    assert "- Moderate validations: 1/3" in text
    assert "- Bad validations: 1/3" in text
