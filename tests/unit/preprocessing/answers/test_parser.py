import io
from pathlib import Path

import polars as pl
import pytest

from preprocessing.answers.parser import parse_question_order, construct_question_id


@pytest.mark.parametrize(
    "csv_text,expected_trials,expected_first_row",
    [
        (
            """question_order_version,local_question_1,local_question_2,bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"""
            """6,12,11,21,22,32,31\n"""
            ,
            [1],
            {
                "question_order_version": 6,
                "local_question_1": 12,
                "local_question_2": 11,
                "bridging_question_1": 21,
                "bridging_question_2": 22,
                "global_question_1": 32,
                "global_question_2": 31,
            },
        ),
        (
            """question_order_version,local_question_1,local_question_2,bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"""
            """4,12,11,22,21,31,32\n"""
            """2,12,11,21,22,31,32\n"""
            ,
            [1, 2],
            {
                "question_order_version": 4,
                "local_question_1": 12,
                "local_question_2": 11,
                "bridging_question_1": 22,
                "bridging_question_2": 21,
                "global_question_1": 31,
                "global_question_2": 32,
            },
        ),
    ],
)
def test_parse_question_order(tmp_path: Path, csv_text, expected_trials, expected_first_row):
    p = tmp_path / "question_order_versions.csv"
    p.write_text(csv_text)

    df = parse_question_order(p)
    assert "trial" in df.columns
    assert df.shape[0] == len(expected_trials)
    assert df["trial"].to_list() == expected_trials

    # Check first row values
    for k, v in expected_first_row.items():
        assert df[k][0] == v


@pytest.mark.parametrize(
    "stimulus_name,order_code,expected",
    [
        ("Arg_PISACowsMilk_10", 11, "10211"),
        ("Arg_PISARapaNui_10", 22, "10222"),
        ("Lit_Solaris_7", 31, "7131"),
        ("PopSci_Caveman_3", 12, "3112"),
    ],
)
def test_construct_question_id(stimulus_name, order_code, expected):
    assert construct_question_id(stimulus_name, order_code) == expected
