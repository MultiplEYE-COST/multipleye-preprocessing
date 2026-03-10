from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import pytest
from numpy import float64

from preprocessing.psychometric_tests.preprocess_psychometric_tests import (
    _reaction_time_accuracy,
    _find_one_filetype_with_columns,
    preprocess_stroop,
    preprocess_flanker,
    preprocess_plab,
    preprocess_ran,
    preprocess_wikivocab,
    preprocess_lwmc,
)


@pytest.mark.parametrize(
    "rt_values, correctness_values, error_message",
    [
        ([], [], "DataFrame is empty"),
        (
            [100, math.nan, 300],
            [1, 0, math.nan],
            "NaN positions in correctness and reaction time columns do not match",
        ),
        # mismatch where reaction time has NaN but correctness does not
        (
            [100, math.nan, 300],
            [1, 1, 0],
            "NaN positions in correctness and reaction time columns do not match",
        ),
        (
            ["fast", 200, 300],
            [1, 0, 1],
            "Reaction time column contains non-numeric values",
        ),
        (
            ["100", "200", "300"],
            [1, 0, 1],
            "Reaction time column contains non-numeric values",
        ),
        ([100, 200, 300], [1, 2, 3], "Correctness column contains non-boolean values"),
        (
            [100, 200, 300],
            ["True", "False", "True"],
            "Correctness column contains non-boolean values",
        ),
    ],
)
def test__reaction_time_accuracy_errors(rt_values, correctness_values, error_message):
    df = pd.DataFrame({"rt": rt_values, "correctness": correctness_values})
    with pytest.raises(ValueError, match=error_message):
        _reaction_time_accuracy(df, "rt", "correctness")


@pytest.mark.parametrize(
    "rt_values, correctness_values, correct_only, expected_rt_mean_sec, expected_acc, expected_num",
    [
        ([100, 200, 300], [1, 0, 1], False, 200.0, 2 / 3, 3),
        ([None, 100, 200, 300], [None, 1, 0, 1], False, 200.0, 2 / 3, 3),
        ([math.nan, 100, 200, 300], [math.nan, 1, 0, 1], False, 200.0, 2 / 3, 3),
        (
            [float("nan"), 100, 200, 300],
            [float("nan"), 1, 0, 1],
            False,
            200.0,
            2 / 3,
            3,
        ),
        (
            [float64("nan"), 100, 200, 300],
            [float64("nan"), 1, 0, 1],
            False,
            200.0,
            2 / 3,
            3,
        ),
        (
            [100, 200, 300, float64("nan")],
            [1, 0, 1, float64("nan")],
            False,
            200.0,
            2 / 3,
            3,
        ),
        ([100, 200, 300], [1, 0, 1], True, 200.0, 2 / 3, 3),
        ([100, 200, 300], [True, False, True], False, 200.0, 2 / 3, 3),
        ([100, 200, 300], [True, True, False], False, 200.0, 2 / 3, 3),
        ([100, 200, 300], [True, True, False], True, 150.0, 2 / 3, 3),
        ([1], [True], False, 1, 1, 1),
        ([1, 2, 3, 4, 5], [True, True, True, True, True], False, 3, 1, 5),
    ],
)
def test__reaction_time_accuracy(
    rt_values,
    correctness_values,
    correct_only,
    expected_rt_mean_sec,
    expected_acc,
    expected_num,
):
    df = pd.DataFrame({"rt": rt_values, "correctness": correctness_values})

    rt_mean, acc, num = _reaction_time_accuracy(
        df, "rt", "correctness", correct_only=correct_only
    )

    if math.isnan(expected_rt_mean_sec):
        assert math.isnan(rt_mean)
    else:
        assert rt_mean == pytest.approx(expected_rt_mean_sec)
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
            lambda: pd.DataFrame(
                {
                    "cond": ["A", "A", "B", "B"],
                    "rt": [1.0, 2.0, 3.0, 4.0],
                    "correctness": [1, 0, 1, 1],
                }
            ),
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
            lambda: pd.DataFrame(
                {
                    "cond": ["A", "A", "B", "B"],
                    "rt": [1.0, 2.0, 3.0, 4.0],
                    "correctness": [1, 0, 1, 1],
                }
            ),
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
            lambda: pd.DataFrame(
                {
                    "cond": ["A", "B", "C", "C"],
                    "rt": [10.0, 20.0, 30.0, 30.0],
                    "correctness": [1, 1, 0, 0],
                }
            ),
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
            lambda: pd.DataFrame(
                {
                    "cond": ["A", None, "B"],
                    "rt": [1.0, 2.0, 3.0],
                    "correctness": [1, 1, 0],
                }
            ),
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
        df,
        reaction_time_col="rt",
        correctness_col="correctness",
        group_by_col="cond",
        correct_only=correct_only,
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
    df = pd.DataFrame(
        {
            "cond": ["A", "B"],
            "rt": [100.0, 200.0],
            "correctness": [1, 0],
        }
    )
    if expect_error:
        with pytest.raises(ValueError, match="group_by column"):
            _reaction_time_accuracy(df, "rt", "correctness", group_by_col=group_by_col)
    else:
        out = _reaction_time_accuracy(
            df, "rt", "correctness", group_by_col=group_by_col
        )
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
    tmp_path: Path,
    make_text_file,
    files,
    required_cols,
    allow_nan,
    expect_error_msg,
    check,
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


@pytest.mark.parametrize(
    "rows, expected",
    [
        # Three groups present (congruent, incongruent, neutral)
        (
            [
                ("congruent", 100, 1),
                ("incongruent", 200, 0),
                ("neutral", 150, 1),
            ],
            {
                "Stroop_congruent_rt_mean_sec": 100.0,
                "Stroop_congruent_accuracy": 1.0,
                "Stroop_congruent_num_items": 1,
                "Stroop_incongruent_rt_mean_sec": 200.0,
                "Stroop_incongruent_accuracy": 0.0,
                "Stroop_incongruent_num_items": 1,
                "Stroop_neutral_rt_mean_sec": 150.0,
                "Stroop_neutral_accuracy": 1.0,
                "Stroop_neutral_num_items": 1,
            },
        ),
        # Multiple per group (use canonical labels congruent/incongruent/neutral)
        (
            [
                ("congruent", 100, 1),
                ("congruent", 200, 0),
                ("incongruent", 300, 1),
                ("incongruent", 500, 1),
                ("neutral", 250, 1),
            ],
            {
                "Stroop_congruent_rt_mean_sec": 150.0,
                "Stroop_congruent_accuracy": 0.5,
                "Stroop_congruent_num_items": 2,
                "Stroop_incongruent_rt_mean_sec": 400.0,
                "Stroop_incongruent_accuracy": 1.0,
                "Stroop_incongruent_num_items": 2,
                "Stroop_neutral_rt_mean_sec": 250.0,
                "Stroop_neutral_accuracy": 1.0,
                "Stroop_neutral_num_items": 1,
            },
        ),
    ],
)
def test_preprocess_stroop_basic(tmp_path: Path, make_text_file, rows, expected):
    folder = tmp_path / "session" / "SF"
    header = "stim_type,stroop_key.rt,stroop_key.corr\n"
    body = "".join(f"{s},{rt},{corr}\n" for s, rt, corr in rows)
    make_text_file(folder / "stroop.csv", header=header, body=body)

    res = preprocess_stroop(folder)
    # res is a dict with namespaced keys
    for key, exp in expected.items():
        val = res[key]
        if isinstance(exp, float):
            assert val == pytest.approx(exp)
        else:
            assert val == exp


@pytest.mark.parametrize(
    "header, body, error_msg",
    [
        # Missing required columns
        ("stim_type,rt,corr\n", "A,100,1\n", "No .csv files with columns"),
        # NaN mismatch between rt and corr -> validation error
        (
            "stim_type,stroop_key.rt,stroop_key.corr\n",
            "A,,1\n",
            "NaN positions in correctness and reaction time columns do not match",
        ),
        # Non-numeric rt
        (
            "stim_type,stroop_key.rt,stroop_key.corr\n",
            "A,fast,1\n",
            "Reaction time column contains non-numeric values",
        ),
    ],
)
def test_preprocess_stroop_errors(
    tmp_path: Path, make_text_file, header, body, error_msg
):
    folder = tmp_path / "p1" / "SF"
    make_text_file(folder / "data.csv", header=header, body=body)
    if error_msg.startswith("No .csv files with columns"):
        with pytest.raises(ValueError, match="No .csv files with columns"):
            preprocess_stroop(folder)
    else:
        with pytest.raises(ValueError, match=error_msg):
            preprocess_stroop(folder)


@pytest.mark.parametrize(
    "rows, expected",
    [
        (
            [("congruent", 100, 1), ("incongruent", 300, 0), ("congruent", 200, 1)],
            {
                "Flanker_congruent_rt_mean_sec": 150.0,
                "Flanker_congruent_accuracy": 1.0,
                "Flanker_congruent_num_items": 2,
                "Flanker_incongruent_rt_mean_sec": 300.0,
                "Flanker_incongruent_accuracy": 0.0,
                "Flanker_incongruent_num_items": 1,
            },
        ),
    ],
)
def test_preprocess_flanker_basic(tmp_path: Path, make_text_file, rows, expected):
    folder = tmp_path / "session" / "SF"
    header = "stim_type,Flanker_key.rt,Flanker_key.corr\n"
    body = "".join(f"{s},{rt},{corr}\n" for s, rt, corr in rows)
    make_text_file(folder / "flanker.csv", header=header, body=body)

    res = preprocess_flanker(folder)
    # res is a dict with namespaced keys
    for key, exp in expected.items():
        val = res[key]
        if isinstance(exp, float):
            assert val == pytest.approx(exp)
        else:
            assert val == exp


@pytest.mark.parametrize(
    "header, body, error_msg",
    [
        ("stim_type,rt,corr\n", "A,100,1\n", "No .csv files with columns"),
        (
            "stim_type,Flanker_key.rt,Flanker_key.corr\n",
            "A,,1\n",
            "NaN positions in correctness and reaction time columns do not match",
        ),
        (
            "stim_type,Flanker_key.rt,Flanker_key.corr\n",
            "A,slow,1\n",
            "Reaction time column contains non-numeric values",
        ),
    ],
)
def test_preprocess_flanker_errors(
    tmp_path: Path, make_text_file, header, body, error_msg
):
    folder = tmp_path / "p2" / "SF"
    make_text_file(folder / "data.csv", header=header, body=body)
    if error_msg.startswith("No .csv files with columns"):
        with pytest.raises(ValueError, match="No .csv files with columns"):
            preprocess_flanker(folder)
    else:
        with pytest.raises(ValueError, match=error_msg):
            preprocess_flanker(folder)


@pytest.mark.parametrize(
    "rows, expected",
    [
        ([(100, 1), (200, 0), (300, 1)], (200.0, 2 / 3, 3)),
        ([(1, 1)], (1.0, 1.0, 1)),
    ],
)
def test_preprocess_plab_basic(tmp_path: Path, make_text_file, rows, expected):
    folder = tmp_path / "session" / "PLAB"
    header = "rt,correctness\n"
    body = "".join(f"{rt},{corr}\n" for rt, corr in rows)
    make_text_file(folder / "plab.csv", header=header, body=body)
    out = preprocess_plab(folder)
    assert out["PLAB_rt_mean_sec"] == pytest.approx(expected[0])
    assert out["PLAB_accuracy"] == pytest.approx(expected[1])
    assert out["PLAB_num_items"] == expected[2]


@pytest.mark.parametrize(
    "header, body, error_msg",
    [
        ("rt,corr\n", "100,1\n", "No .csv files with columns"),
        (
            "rt,correctness\n",
            ",1\n",
            "NaN positions in correctness and reaction time columns do not match",
        ),
        (
            "rt,correctness\n",
            "fast,1\n",
            "Reaction time column contains non-numeric values",
        ),
    ],
)
def test_preprocess_plab_errors(
    tmp_path: Path, make_text_file, header, body, error_msg
):
    folder = tmp_path / "p3" / "PLAB"
    make_text_file(folder / "plab.csv", header=header, body=body)
    if error_msg.startswith("No .csv files with columns"):
        with pytest.raises(ValueError, match="No .csv files with columns"):
            preprocess_plab(folder)
    else:
        with pytest.raises(ValueError, match=error_msg):
            preprocess_plab(folder)


def test_preprocess_ran_basic(tmp_path: Path, make_text_file):
    folder = tmp_path / "session" / "RAN"
    header = "Trial,Reading_Time\n"
    body = "1,2.5\n2,3.5\n"
    make_text_file(folder / "ran.csv", header=header, body=body)
    out = preprocess_ran(folder)
    assert set(out.keys()) == {"RAN_practice_rt_sec", "RAN_experimental_rt_sec"}
    assert out["RAN_practice_rt_sec"] == pytest.approx(2.5)
    assert out["RAN_experimental_rt_sec"] == pytest.approx(3.5)


@pytest.mark.parametrize(
    "header, body, error_msg",
    [
        ("Trial,RT\n", "1,2\n", "No .csv files with columns"),
        ("Trial,Reading_Time\n", "1,\n", "NaN values found in required columns"),
        # Multiple files with required columns
        ("Trial,Reading_Time\n", "1,2\n", "Multiple .csv files with columns"),
    ],
)
def test_preprocess_ran_errors(tmp_path: Path, make_text_file, header, body, error_msg):
    folder = tmp_path / "p4" / "RAN"
    # Create one or two files depending on error
    make_text_file(folder / "ran1.csv", header=header, body=body)
    if error_msg.startswith("Multiple"):
        make_text_file(folder / "ran2.csv", header=header, body=body)
    with pytest.raises(ValueError, match=error_msg):
        preprocess_ran(folder)


@pytest.mark.parametrize(
    "rows, expected",
    [
        (
            # 4 rows, 2 real (1) and 2 pseudo (0)
            [
                (1, 1, 100),  # correct real
                (1, 0, 200),  # incorrect real
                (0, 0, 300),  # correct pseudo
                (0, 1, 400),  # incorrect pseudo
            ],
            {
                "WikiVocab_rt_mean_sec": 250.0,
                "WikiVocab_accuracy": 0.5,
                "WikiVocab_num_items": 4,
                "WikiVocab_num_pseudo_words": 2,
                "WikiVocab_num_real_words": 2,
                "WikiVocab_incorrect_correct_score": 0.5,
                "WikiVocab_pseudo_correct": 0.5,
                "WikiVocab_real_correct": 0.5,
            },
        ),
        (
            # Only pseudo words (no real words)
            [
                (0, 0, 100),
                (0, 1, 200),
            ],
            {
                "WikiVocab_rt_mean_sec": 150.0,
                "WikiVocab_accuracy": 0.5,
                "WikiVocab_num_items": 2,
                "WikiVocab_num_pseudo_words": 2,
                "WikiVocab_num_real_words": 0,
                "WikiVocab_incorrect_correct_score": math.nan,
                "WikiVocab_pseudo_correct": 0.5,
                "WikiVocab_real_correct": math.nan,
            },
        ),
    ],
)
def test_preprocess_wikivocab_basic(tmp_path: Path, make_text_file, rows, expected):
    folder = tmp_path / "session" / "WV"
    header = "correct_answer,real_answer,RT\n"
    body = "".join(f"{c},{r},{rt}\n" for c, r, rt in rows)
    make_text_file(folder / "wv.csv", header=header, body=body)

    out = preprocess_wikivocab(folder)
    for key, exp in expected.items():
        val = out[key]
        if isinstance(exp, float) and math.isnan(exp):
            assert math.isnan(val)
        elif isinstance(exp, float):
            assert val == pytest.approx(exp)
        else:
            assert val == exp


@pytest.mark.parametrize(
    "header, body, error_msg",
    [
        ("c,real_answer,RT\n", "1,1,100\n", "No .csv files with columns"),
        (
            "correct_answer,real_answer,RT\n",
            "1,1,\n",
            "NaN values found in required columns",
        ),
        # Non-numeric RT should raise a validation error
        (
            "correct_answer,real_answer,RT\n",
            "1,1,fast\n",
            "Reaction time column contains non-numeric values",
        ),
    ],
)
def test_preprocess_wikivocab_errors(
    tmp_path: Path, make_text_file, header, body, error_msg
):
    folder = tmp_path / "p5" / "WV"
    make_text_file(folder / "wv.csv", header=header, body=body)
    if (
        error_msg.startswith("No .csv files with columns")
        or error_msg.startswith("NaN values found")
        or error_msg.startswith("Reaction time column contains")
    ):
        with pytest.raises(ValueError, match=error_msg):
            preprocess_wikivocab(folder)
    else:
        # In this case, CSV loads but reaction time accuracy validation triggers
        with pytest.raises(ValueError):
            preprocess_wikivocab(folder)


def _make_wmc_csv(folder: Path, make_text_file):
    header = (
        "is_practice,base_text_intertrial.started,"
        "mu_key_resp_recall.is_correct,mu_key_resp_recall.rt,"
        "os_key_resp_recall.corr,os_key_resp_recall.rt,"
        "ss_key_resp_recall.corr,ss_key_resp_recall.rt\n"
    )
    body = "".join(
        [
            # Trial 1
            "False,1,1,100,1,10,0,5\n",
            "False,,0,200,,,1,15\n",
            # Trial 2
            "False,2,1,300,0,30,1,25\n",
            "False,,1,400,,,0,35\n",
        ]
    )
    make_text_file(folder / "wmc.csv", header=header, body=body)


def _make_sstm_file(lwmc_dir: Path, make_text_file, pid: str = "1", token: str = "120"):
    # File must be named SSTM-<pid>.dat, where pid is int(stem[:3]) of parent folder
    make_text_file(lwmc_dir / f"SSTM-{pid}.dat", body=f"header\nScore {token}\n")


def test_preprocess_lwmc_basic(tmp_path: Path, make_text_file):
    # Create folder structure: <tmp>/<participant>/WMC
    participant = tmp_path / "001_AB"  # stem[:3] -> "001" -> pid "1"
    lwmc_dir = participant / "WMC"
    lwmc_dir.mkdir(parents=True)

    _make_wmc_csv(lwmc_dir, make_text_file)
    _make_sstm_file(lwmc_dir, make_text_file, pid="1", token="120")

    out = preprocess_lwmc(lwmc_dir)

    assert out["LWMC_MU_score"] == pytest.approx(0.75)
    assert out["LWMC_MU_time_sec"] == pytest.approx(250.0)
    assert out["LWMC_OS_score"] == pytest.approx(0.5)
    assert out["LWMC_OS_time_sec"] == pytest.approx(20.0)
    assert out["LWMC_SS_score"] == pytest.approx(0.5)
    assert out["LWMC_SS_time_sec"] == pytest.approx(20.0)
    assert out["LWMC_SSTM_score"] == pytest.approx(0.5)
    assert out["LWMC_Total_score_mean"] == pytest.approx((0.75 + 0.5 + 0.5 + 0.5) / 4)


@pytest.mark.parametrize(
    "prep, error_msg",
    [
        # All practice -> no non-practice trials
        (
            lambda d, mk: mk(
                d / "wmc.csv",
                header=(
                    "is_practice,base_text_intertrial.started,"
                    "mu_key_resp_recall.is_correct,mu_key_resp_recall.rt,"
                    "os_key_resp_recall.corr,os_key_resp_recall.rt,"
                    "ss_key_resp_recall.corr,ss_key_resp_recall.rt\n"
                ),
                body="""True,1,1,100,1,10,1,5\nTrue,,1,100,1,10,1,5\n""",
            ),
            "No non-practice trials found",
        ),
        # Missing SSTM file
        (
            lambda d, mk: _make_wmc_csv(d, mk),
            "Missing required WMC file",
        ),
        # Malformed SSTM: too few lines
        (
            lambda d, mk: (
                _make_wmc_csv(d, mk),
                mk(d / "SSTM-1.dat", body="only one line\n"),
            ),
            "Malformed SSTM file",
        ),
        # Malformed SSTM: too few tokens
        (
            lambda d, mk: (
                _make_wmc_csv(d, mk),
                mk(d / "SSTM-1.dat", body="h\n\n"),
            ),
            "Malformed SSTM line",
        ),
        # Malformed SSTM: invalid token
        (
            lambda d, mk: (
                _make_wmc_csv(d, mk),
                mk(d / "SSTM-1.dat", body="h\nScore abc\n"),
            ),
            "Invalid SSTM score token",
        ),
        # No valid MU trials (all NaN in MU correctness)
        (
            lambda d, mk: mk(
                d / "wmc.csv",
                header=(
                    "is_practice,base_text_intertrial.started,"
                    "mu_key_resp_recall.is_correct,mu_key_resp_recall.rt,"
                    "os_key_resp_recall.corr,os_key_resp_recall.rt,"
                    "ss_key_resp_recall.corr,ss_key_resp_recall.rt\n"
                ),
                body=("False,1,,100,1,10,1,5\nFalse,,,200,,,1,15\n"),
            ),
            "No valid MU trials found",
        ),
        # Cannot infer participant id (parent stem without 3 leading digits)
        (
            lambda d, mk: _make_wmc_csv(d, mk),
            "Cannot infer participant id",
        ),
    ],
)
def test_preprocess_lwmc_errors(tmp_path: Path, make_text_file, prep, error_msg):
    # Intentionally choose a parent without three leading digits to trigger id error in one case
    participant = tmp_path / "XXY"  # no leading digits
    lwmc_dir = participant / "WMC"
    lwmc_dir.mkdir(parents=True)

    prep(lwmc_dir, make_text_file)

    if "Cannot infer participant id" in error_msg:
        with pytest.raises(ValueError, match=error_msg):
            preprocess_lwmc(lwmc_dir)
    else:
        # For other cases, use a valid participant id so pid derivation works
        participant_ok = tmp_path / "001_OK"
        lwmc_ok = participant_ok / "WMC"
        lwmc_ok.mkdir(parents=True)
        # Copy the prepared csv if present
        src_csv = lwmc_dir / "wmc.csv"
        if src_csv.exists():
            text = src_csv.read_text()
            make_text_file(lwmc_ok / "wmc.csv", body=text)
        # If a prepared SSTM file exists in the source, copy its contents to the valid folder
        src_sstm = lwmc_dir / "SSTM-1.dat"
        if src_sstm.exists():
            sstm_text = src_sstm.read_text()
            make_text_file(lwmc_ok / "SSTM-1.dat", body=sstm_text)
        # Now run and expect error
        with pytest.raises(ValueError, match=error_msg):
            preprocess_lwmc(lwmc_ok)
