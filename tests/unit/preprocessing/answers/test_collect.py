from pathlib import Path

import polars as pl
import pytest

from preprocessing.answers.collect import collect_session_answers


@pytest.mark.parametrize(
    "stimulus_name,pisa_middle",
    [
        ("Arg_PISACowsMilk_10", "2"),
        ("Lit_Solaris_7", "1"),
    ],
)
def test_collect_session_answers_builds_rows_and_ids(tmp_path: Path, stimulus_name, pisa_middle):
    # Prepare a minimal question_order_versions.csv with one trial
    csv = (
        "question_order_version,local_question_1,local_question_2,bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
        "6,12,11,21,22,32,31\n"
    )
    qcsv = tmp_path / "question_order_versions.csv"
    qcsv.write_text(csv)

    # Provide stimuli mapping for trial 1
    mapping = {"trial_1": stimulus_name}

    out_path = tmp_path / "answers.csv"
    df = collect_session_answers(qcsv, mapping, out_path=out_path)

    # Expect 6 rows (six question slots) for the one trial
    assert df.shape[0] == 6
    assert set(df["trial"].to_list()) == {"trial_1"}
    assert set(df["stimulus"].to_list()) == {stimulus_name}

    # Check order codes covered and IDs well-formed
    codes = set(df["order_code"].to_list())
    assert codes == {12, 11, 21, 22, 32, 31}

    # Verify question_id format: <stim_num><middle><order_code>
    stim_num = stimulus_name.split("_")[-1]
    for row in df.iter_rows(named=True):
        oc = int(row["order_code"])
        assert row["question_id"].startswith(stim_num + pisa_middle)
        assert row["question_id"].endswith(str(oc))

    # File written and loadable
    assert out_path.exists()
    loaded = pl.read_csv(out_path)
    assert loaded.shape == df.shape
