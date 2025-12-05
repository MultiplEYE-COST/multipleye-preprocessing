from __future__ import annotations

import math
from pathlib import Path
import sys

import pandas as pd
import pytest
from numpy import float64

from preprocessing.psychometric_tests.preprocess_psychometric_tests import \
    _reaction_time_accuracy, _find_one_filetype_with_columns


@pytest.mark.parametrize(
    "rt_values, correctness_values, error_message",
    [
        ([], [], "DataFrame is empty"),
        ([100, math.nan, 300], [1, 0, math.nan], "NaN positions in correctness and reaction time columns do not match"),
        # mismatch where reaction time has NaN but correctness does not
        ([100, math.nan, 300], [1, 1, 0], "NaN positions in correctness and reaction time columns do not match"),
        (["fast", 200, 300], [1, 0, 1], "Reaction time column contains non-numeric values"),
        (["100", "200", "300"], [1, 0, 1], "Reaction time column contains non-numeric values"),
        ([100, 200, 300], [1, 2, 3], "Correctness column contains non-boolean values"),
        ([100, 200, 300], ["True", "False", "True"], "Correctness column contains non-boolean values"),
    ],
)
def test__reaction_time_accuracy_errors(rt_values, correctness_values, error_message):
    df = pd.DataFrame({"rt": rt_values, "correctness": correctness_values})
    with pytest.raises(ValueError, match=error_message):
        _reaction_time_accuracy(df, "rt", "correctness")


@pytest.mark.parametrize(
    "rt_values, correctness_values, correct_only, expected_rt_mean, expected_acc, expected_num",
    [
        ([100, 200, 300], [1, 0, 1], False, 200.0, 2 / 3, 3),
        ([None, 100, 200, 300], [None, 1, 0, 1], False, 200.0, 2 / 3, 3),
        ([math.nan, 100, 200, 300], [math.nan, 1, 0, 1], False, 200.0, 2 / 3, 3),
        ([float("nan"), 100, 200, 300], [float("nan"), 1, 0, 1], False, 200.0, 2 / 3, 3),
        ([float64("nan"), 100, 200, 300], [float64("nan"), 1, 0, 1], False, 200.0, 2 / 3, 3),
        ([100, 200, 300, float64("nan")], [1, 0, 1, float64("nan")], False, 200.0, 2 / 3, 3),
        ([100, 200, 300], [1, 0, 1], True, 200.0, 2 / 3, 3),
        ([100, 200, 300], [True, False, True], False, 200.0, 2 / 3, 3),
        ([100, 200, 300], [True, True, False], False, 200.0, 2 / 3, 3),
        ([100, 200, 300], [True, True, False], True, 150.0, 2 / 3, 3),
        ([1], [True], False, 1, 1, 1),
        ([1,2,3,4,5], [True, True, True, True, True], False, 3, 1, 5),
    ],
)
def test__reaction_time_accuracy(
        rt_values, correctness_values, correct_only, expected_rt_mean, expected_acc, expected_num
):
    df = pd.DataFrame({"rt": rt_values, "correctness": correctness_values})

    rt_mean, acc, num = _reaction_time_accuracy(
        df, "rt", "correctness", correct_only=correct_only
    )

    if math.isnan(expected_rt_mean):
        assert math.isnan(rt_mean)
    else:
        assert rt_mean == pytest.approx(expected_rt_mean)
    if isinstance(expected_acc, float) and math.isnan(expected_acc):
        assert math.isnan(acc)
    else:
        assert acc == pytest.approx(expected_acc)
    assert num == expected_num


@pytest.mark.parametrize(
    "df_builder, correct_only, expectations",
    [
        # Basic grouping: two groups, mixed correctness
        (
            lambda: pd.DataFrame({
                "cond": ["A", "A", "B", "B"],
                "rt": [1.0, 2.0, 3.0, 4.0],
                "correctness": [1, 0, 1, 1],
            }),
            False,
            {
                ("A", "rt_mean"): 1.5,
                ("A", "accuracy"): 0.5,
                ("B", "rt_mean"): 3.5,
                ("B", "accuracy"): 1.0,
                ("A", "num_items"): 2,
                ("B", "num_items"): 2,
            },
        ),
        # correct_only=True affects only rt_mean
        (
            lambda: pd.DataFrame({
                "cond": ["A", "A", "B", "B"],
                "rt": [1.0, 2.0, 3.0, 4.0],
                "correctness": [1, 0, 1, 1],
            }),
            True,
            {
                ("A", "rt_mean"): 1.0,  # only the correct trial in A
                ("A", "accuracy"): 0.5,
                ("B", "rt_mean"): 3.5,
                ("B", "accuracy"): 1.0,
                ("A", "num_items"): 2,
                ("B", "num_items"): 2,
            },
        ),
        # Group with only incorrect trials: rt_mean becomes NaN when correct_only=True
        (
            lambda: pd.DataFrame({
                "cond": ["A", "B", "C", "C"],
                "rt": [10.0, 20.0, 30.0, 30.0],
                "correctness": [1, 1, 0, 0],
            }),
            True,
            {
                ("A", "rt_mean"): 10.0,
                ("A", "accuracy"): 1.0,
                ("B", "rt_mean"): 20.0,
                ("B", "accuracy"): 1.0,
                ("C", "rt_mean"): math.nan,  # no correct trials in C
                ("C", "accuracy"): 0.0,
                ("A", "num_items"): 1,
                ("B", "num_items"): 1,
                ("C", "num_items"): 2,
            },
        ),
        # Rows with NaN group are excluded from grouped result (dropna=True)
        (
            lambda: pd.DataFrame({
                "cond": ["A", None, "B"],
                "rt": [1.0, 2.0, 3.0],
                "correctness": [1, 1, 0],
            }),
            False,
            {
                ("A", "rt_mean"): 1.0,
                ("A", "accuracy"): 1.0,
                ("B", "rt_mean"): 3.0,
                ("B", "accuracy"): 0.0,
                ("A", "num_items"): 1,
                ("B", "num_items"): 1,
                # No expectation for NaN group – it should not appear
            },
        ),
    ],
)
def test__reaction_time_accuracy_grouped(df_builder, correct_only, expectations):
    df = df_builder()
    res = _reaction_time_accuracy(
        df, reaction_time_col="rt", correctness_col="correctness", group_by_col="cond", correct_only=correct_only
    )
    # Ensure we got a DataFrame with expected columns
    assert list(res.columns) == ["rt_mean", "accuracy", "num_items"]

    # For the NaN-group case, ensure there is no NaN in the index
    assert not any(pd.isna(idx) for idx in res.index)

    for (grp, col), expected in expectations.items():
        val = res.loc[grp, col]
        if isinstance(expected, float) and math.isnan(expected):
            assert math.isnan(val)
        else:
            assert val == pytest.approx(expected)


@pytest.mark.parametrize(
    "group_by_col, expect_error",
    [
        ("cond", False),
        ("missing_col", True),
    ],
)
def test__reaction_time_accuracy_grouped_missing_column(group_by_col, expect_error):
    df = pd.DataFrame({
        "cond": ["A", "B"],
        "rt": [100.0, 200.0],
        "correctness": [1, 0],
    })
    if expect_error:
        with pytest.raises(ValueError, match="group_by column"):
            _reaction_time_accuracy(df, "rt", "correctness", group_by_col=group_by_col)
    else:
        out = _reaction_time_accuracy(df, "rt", "correctness", group_by_col=group_by_col)
        assert list(out.columns) == ["rt_mean", "accuracy", "num_items"]


@pytest.mark.parametrize(
    "files, required_cols, allow_nan, expect_error_msg, check",
    [
        # Single CSV with required columns -> returns DataFrame with only those columns.
        (
            [("ok.csv", "a,b,c\n", "1,2,3\n4,5,6\n")],
            ["a", "c"],
            False,
            None,
            lambda df: (list(df.columns) == ["a", "c"] and df.shape == (2, 2)),
        ),
        # No CSV files -> ValueError
        (
            [],
            ["a"],
            False,
            "No .csv files found",
            None,
        ),
        # CSV present but missing columns -> ValueError starting with "No CSV files with columns"
        (
            [("bad.csv", "x,y\n", "1,2\n")],
            ["a"],
            False,
            "No .csv files with columns",
            None,
        ),
        # Multiple CSVs that both match -> ValueError starting with "Multiple CSV files with columns"
        (
            [("a1.csv", "u,v\n", "1,2\n"), ("a2.csv", "u,v,w\n", "3,4,5\n")],
            ["u", "v"],
            False,
            "Multiple .csv files with columns",
            None,
        ),
        # Header-only CSV that has the required columns -> returns empty DataFrame with those columns
        (
            [("empty.csv", "m,n\n", "")],
            ["m", "n"],
            False,
            None,
            lambda df: (list(df.columns) == ["m", "n"] and df.shape == (0, 2)),
        ),
        # Multiple CSVs that partially match, only one exactly -> returns DataFrame
        (
            [("m1.csv", "u,v\n", "1,2\n"), ("rsa.csv", "u,v,w\n", "3,4,5\n")],
            ["v", "w"],
            False,
            None,
            lambda df: (list(df.columns) == ["v", "w"] and df.shape == (1, 2)),
        ),
        # One CSV with NaN values in required columns, allowed -> no error
        (
            [("nan.csv", "a,b\n", "1,NaN\n")],
            ["a", "b"],
            True,
            None,
            lambda df: (list(df.columns) == ["a", "b"] and df.shape == (1, 2)),
        ),
        # One CSV with NaN values in required columns, not allowed -> raises ValueError
        (
            [("nan.csv", "a,b\n", "1,NaN\n")],
            ["a", "b"],
            False,
            "NaN values found in required columns",
            None,
        ),
    ],
)
def test__find_one_filetype_with_columns(
        tmp_path: Path, make_text_file, files, required_cols, allow_nan, expect_error_msg, check
):
    # Prepare folder with CSVs
    folder = tmp_path / "session"
    folder.mkdir()
    for fname, header, body in files:
        make_text_file(folder / fname, header=header, body=body)

    if expect_error_msg:
        with pytest.raises(ValueError, match=expect_error_msg):
            _find_one_filetype_with_columns(folder, required_cols, allow_nan=allow_nan)
    else:
        df = _find_one_filetype_with_columns(folder, required_cols, allow_nan=allow_nan)
        assert check(df)
