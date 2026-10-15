"""Tests for the vectorized data-loss helper."""

import polars as pl
import pymovements as pm
import pytest
from polars.testing import assert_frame_equal

from preprocessing.metrics.data_loss import compute_data_loss

SR = 1000.0
PAGE_COLUMNS = ["trial", "stimulus", "page"]
TRIAL_COLUMNS = ["trial", "stimulus"]


def _reference_tables(samples: pl.DataFrame, pixel_column: str = "pixel"):
    """Compute data loss with pymovements as the reference."""
    measure = pm.measure.data_loss(pixel_column, sampling_rate=SR, unit="ratio")
    total = samples.select(measure).item()
    per_page = samples.group_by(PAGE_COLUMNS).agg(measure)
    per_trial = samples.group_by(TRIAL_COLUMNS).agg(measure)
    return total, per_page, per_trial


def _frame(times, pixels, trial="trial_1", stimulus="stim", page="page_1"):
    return pl.DataFrame(
        {
            "trial": [trial] * len(times),
            "stimulus": [stimulus] * len(times),
            "page": [page] * len(times),
            "time": times,
            "pixel": pixels,
        }
    )


CASES = {
    "clean": _frame([0, 1, 2, 3, 4, 5], [[1.0, 2.0]] * 6),
    "time_gap": _frame([0, 1, 2, 5, 6, 9], [[1.0, 2.0]] * 6),
    "null_pixel_row": _frame([0, 1, 2, 3], [[1.0, 2.0], None, [1.0, 2.0], [1.0, 2.0]]),
    "nan_inf_elements": _frame(
        [0, 1, 2, 3],
        [[1.0, 2.0], [float("nan"), 1.0], [float("inf"), 0.0], [1.0, 2.0]],
    ),
    "empty_list_element": _frame([0, 1, 2], [[1.0, 2.0], [], [1.0, 2.0]]),
    "null_component": _frame([0, 1, 2], [[1.0, 2.0], [None, 1.0], [1.0, None]]),
    "longer_components": _frame([0, 1, 2], [[1.0, 2.0, 3.0]] * 3),
}

MULTI_CASE = pl.concat(
    [
        _frame(
            [0, 1, 2, 4],
            [[1.0, 2.0], None, [float("nan"), 0.0], [1.0, 2.0]],
            trial="trial_1",
            stimulus="stimA",
            page="page_1",
        ),
        _frame(
            [10, 12, 13],
            [[1.0, 2.0], [1.0, 2.0], [float("inf"), 1.0]],
            trial="trial_2",
            stimulus="stimB",
            page="page_2",
        ),
    ]
)


@pytest.mark.parametrize("name", list(CASES))
def test_matches_pymovements(name):
    samples = CASES[name]
    total, per_page, per_trial = compute_data_loss(
        samples,
        sampling_rate=SR,
        page_columns=PAGE_COLUMNS,
        trial_columns=TRIAL_COLUMNS,
    )
    ref_total, ref_page, ref_trial = _reference_tables(samples)

    assert total == pytest.approx(ref_total, abs=1e-12)
    assert_frame_equal(
        per_page.sort(PAGE_COLUMNS),
        ref_page.sort(PAGE_COLUMNS),
        check_exact=False,
        abs_tol=1e-12,
    )
    assert_frame_equal(
        per_trial.sort(TRIAL_COLUMNS),
        ref_trial.sort(TRIAL_COLUMNS),
        check_exact=False,
        abs_tol=1e-12,
    )


def test_matches_pymovements_multiple_groups():
    total, per_page, per_trial = compute_data_loss(
        MULTI_CASE,
        sampling_rate=SR,
        page_columns=PAGE_COLUMNS,
        trial_columns=TRIAL_COLUMNS,
    )
    ref_total, ref_page, ref_trial = _reference_tables(MULTI_CASE)

    assert total == pytest.approx(ref_total, abs=1e-12)
    assert_frame_equal(
        per_page.sort(PAGE_COLUMNS),
        ref_page.sort(PAGE_COLUMNS),
        check_exact=False,
        abs_tol=1e-12,
    )
    assert_frame_equal(
        per_trial.sort(TRIAL_COLUMNS),
        ref_trial.sort(TRIAL_COLUMNS),
        check_exact=False,
        abs_tol=1e-12,
    )


def test_output_schema():
    total, per_page, per_trial = compute_data_loss(
        CASES["clean"],
        sampling_rate=SR,
        page_columns=PAGE_COLUMNS,
        trial_columns=TRIAL_COLUMNS,
    )
    assert isinstance(total, float)
    assert per_page.columns == [*PAGE_COLUMNS, "data_loss_ratio"]
    assert per_trial.columns == [*TRIAL_COLUMNS, "data_loss_ratio"]


@pytest.mark.parametrize(
    "pixels",
    [
        [["1", "2"]] * 4,
        [["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"]],
    ],
)
def test_non_float_dtype_falls_back_to_pymovements(pixels):
    samples = _frame([0, 1, 2, 3], pixels)
    total, per_page, per_trial = compute_data_loss(
        samples,
        sampling_rate=SR,
        page_columns=PAGE_COLUMNS,
        trial_columns=TRIAL_COLUMNS,
    )
    ref_total, ref_page, ref_trial = _reference_tables(samples)

    assert total == pytest.approx(ref_total, abs=1e-12)
    assert_frame_equal(
        per_page.sort(PAGE_COLUMNS),
        ref_page.sort(PAGE_COLUMNS),
        check_exact=False,
        abs_tol=1e-12,
    )
    assert_frame_equal(
        per_trial.sort(TRIAL_COLUMNS),
        ref_trial.sort(TRIAL_COLUMNS),
        check_exact=False,
        abs_tol=1e-12,
    )
