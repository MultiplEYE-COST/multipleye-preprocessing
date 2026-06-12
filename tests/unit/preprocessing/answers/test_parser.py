from pathlib import Path

import pytest

from preprocessing.answers.parser import parse_question_order, construct_question_id


@pytest.mark.parametrize(
    "csv_text,expected_trials,expected_first_row",
    [
        (
            """question_order_version,local_question_1,local_question_2,bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"""
            """6,12,11,21,22,32,31\n""",
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
            """2,12,11,21,22,31,32\n""",
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
def test_parse_question_order(
    tmp_path: Path, csv_text, expected_trials, expected_first_row
):
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
        ("Arg_PISACowsMilk_10", 11, "10111"),
        ("Arg_PISARapaNui_10", 22, "10222"),
        ("Lit_Solaris_7", 31, "7131"),
        ("PopSci_Caveman_3", 12, "3112"),
    ],
)
def test_construct_question_id(stimulus_name, order_code, expected):
    assert construct_question_id(stimulus_name, order_code) == expected


@pytest.mark.parametrize(
    "stimulus_name,order_code,stimulus_id,expected",
    [
        ("Lit_MagicMountain", 11, 6, "6111"),
        ("Lit_Alchemist", 12, 4, "4112"),
        ("Arg_PISACowsMilk", 21, 10, "10121"),
        ("Arg_PISARapaNui", 22, 11, "11222"),
        ("PopSci_Caveman", 31, 12, "12131"),
        ("PopSci_MultiplEYE", 32, 1, "1132"),
    ],
)
def test_construct_question_id_with_stimulus_id(
    stimulus_name, order_code, stimulus_id, expected
):
    assert (
        construct_question_id(stimulus_name, order_code, stimulus_id=stimulus_id)
        == expected
    )


@pytest.mark.parametrize(
    "stimulus_name,order_code,stimulus_id,expected",
    [
        ("Enc_WikiMoon", 11, 13, "13111"),
        ("Enc_WikiMoon", 12, 13, "13112"),
        ("Lit_NorthWind", 21, 7, "7121"),
        ("Lit_NorthWind", 22, 7, "7122"),
    ],
)
def test_construct_question_id_practice(
    stimulus_name, order_code, stimulus_id, expected
):
    """Practice stimuli use the same question_id format as experiment stimuli."""
    assert (
        construct_question_id(stimulus_name, order_code, stimulus_id=stimulus_id)
        == expected
    )
