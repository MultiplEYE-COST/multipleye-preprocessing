from types import SimpleNamespace

import polars as pl
import pytest

from preprocessing.data_collection import MultipleyeDataCollection


def _gaze_with_fixation_durations(durations: pl.Series) -> SimpleNamespace:
    events = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_1", "trial_2"],
            "stimulus": ["a", "a", "b"],
            "name": ["fixation", "fixation", "fixation"],
            "duration": durations,
        }
    )
    return SimpleNamespace(
        events=SimpleNamespace(frame=events),
        trial_columns=["trial", "stimulus"],
    )


@pytest.mark.parametrize(
    "durations",
    [
        # pymovements >= 0.29 event durations are Duration.
        pl.Series([1000, 3000, 2000], dtype=pl.Int64).cast(pl.Duration("us")),
        # Older versions and saved data use numeric milliseconds.
        pl.Series([1, 3, 2], dtype=pl.Int64),
    ],
)
def test_check_avg_fix_durations_reports_milliseconds(tmp_path, durations):
    gaze = _gaze_with_fixation_durations(durations)

    report = MultipleyeDataCollection._check_avg_fix_durations(gaze)

    assert all(dtype != pl.Duration for dtype in report.schema.values())
    trial_1 = report.filter(pl.col("trial") == "trial_1").row(0, named=True)
    assert trial_1["mean_fixation_duration_ms"] == 2.0
    assert trial_1["median_fixation_duration_ms"] == 2.0
    assert trial_1["max_fixation_duration_ms"] == 3
    assert trial_1["min_fixation_duration_ms"] == 1
    assert trial_1["sum_fixation_duration_ms"] == 4

    # Regression: Duration columns cannot be written to CSV.
    report.write_csv(tmp_path / "fixation_statistics_per_page.tsv", separator="\t")
