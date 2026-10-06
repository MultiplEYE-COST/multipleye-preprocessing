"""Tests for the per-stimulus reading-time records (regression for mean_rt_per_stim)."""

from pathlib import Path

import pandas as pd

from preprocessing.data_collection.multipleye_data_collection import (
    _build_stimulus_start_end_ts,
)
from preprocessing.data_collection.session import Session


def _sum_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "stimulus": ["a", "a", "b", "b"],
            "trial": ["trial_1", "trial_1", "trial_2", "trial_2"],
            "type": [
                "reading time",
                "time before pages and breaks",
                "reading time",
                "reading time",
            ],
            "duration_ms": [3000.0, 500.0, 1000.0, 1000.0],
            "start_ts": [1000.0, 500.0, 5000.0, 6000.0],
            "stop_ts": [4000.0, 1000.0, 7000.0, 9000.0],
        }
    )


def test_build_stimulus_start_end_ts_keeps_type_and_duration():
    records = _build_stimulus_start_end_ts(_sum_df())

    # "time before pages and breaks" rows are excluded
    assert [r["stimulus"] for r in records] == ["a", "b", "b"]
    for record in records:
        assert record["type"] == "reading time"
        assert "duration_ms" in record
        assert "start_ts" in record
        assert "stop_ts" in record


def test_build_stimulus_start_end_ts_feeds_rt_per_stim():
    """The producer output must drive _compute_rt_per_stim (regression)."""
    sess = Session(
        participant_id=1,
        session_identifier="001_EN_UK_1_ET1",
        is_pilot=False,
        session_folder_path=Path("/tmp"),
        session_file_path=Path("/tmp/x"),
        session_file_name="x",
    )
    sess.stimulus_start_end_ts = _build_stimulus_start_end_ts(_sum_df())

    mean_rt, sd_rt = sess._compute_rt_per_stim()

    # stimulus a -> 3000, stimulus b -> 1000+1000 = 2000
    assert mean_rt == 2500.0
    assert sd_rt == 707.11
