from pathlib import Path

import polars as pl
import pytest

from preprocessing.answers.collect import collect_session_answers
from preprocessing.data_collection.stimulus import Stimulus, ComprehensionQuestion


@pytest.fixture
def mock_question_csv(tmp_path):
    csv = (
        "question_order_version,local_question_1,local_question_2,"
        "bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
        "6,11,12,21,22,31,32\n"
    )
    p = tmp_path / "question_order_versions.csv"
    p.write_text(csv)
    return p


def _make_stimulus(
    stim_id: int,
    name: str,
    trial_id: str,
    q_ids: list[str],
) -> list[Stimulus]:
    questions = []
    for i, qid in enumerate(q_ids, start=1):
        q = ComprehensionQuestion(
            name=f"{name}_{stim_id}_{qid}",
            id=qid,
            question=f"Question {i}",
            target="Correct Answer",
            distractor_a="Wrong A",
            distractor_b="Wrong B",
            distractor_c="Wrong C",
            image_path=Path("img.png"),
            aoi_image_path=Path("aoi.png"),
        )
        questions.append(q)
    return [
        Stimulus(
            id=stim_id,
            name=name,
            type="experiment",
            pages=[],
            text_stimulus=None,
            questions=questions,
            instructions=[],
            ratings=[],
            trial_id=trial_id,
        )
    ]


def test_collect_enrichment_simple_qid(mock_question_csv):
    """Enrichment works with 2-digit q.id (toy data format)."""
    stimuli = _make_stimulus(
        stim_id=6,
        name="Lit_MagicMountain_6",
        trial_id="trial_1",
        q_ids=["11", "12"],
    )
    mapping = {"trial_1": "Lit_MagicMountain_6"}
    df = collect_session_answers(
        mock_question_csv, mapping, stimuli=stimuli, completed_stimuli_ids=[6]
    )

    assert len(df) == 6
    # Question with order_code=11 -> question_id=6111
    q11 = df.filter(pl.col("order_code") == 11)
    assert q11[0, "correct_answer_key"] == "target_key"
    assert q11[0, "correct_answer_text"] == "Correct Answer"
    # q12 has the same target
    q12 = df.filter(pl.col("order_code") == 12)
    assert q12[0, "correct_answer_key"] == "target_key"
    assert q12[0, "correct_answer_text"] == "Correct Answer"


def test_collect_enrichment_multidigit_qid(mock_question_csv):
    """Enrichment works with multi-digit q.id like '04111' (real data format)."""
    stimuli = _make_stimulus(
        stim_id=4,
        name="Lit_Alchemist_4",
        trial_id="trial_1",
        q_ids=["04111", "04112"],
    )
    mapping = {"trial_1": "Lit_Alchemist_4"}
    df = collect_session_answers(
        mock_question_csv, mapping, stimuli=stimuli, completed_stimuli_ids=[4]
    )

    assert len(df) == 6
    # Multi-digit '04111' -> last 2 chars '11' -> order_code=11 -> question_id=4111
    q11 = df.filter(pl.col("order_code") == 11)
    assert q11[0, "correct_answer_key"] == "target_key"
    assert q11[0, "correct_answer_text"] == "Correct Answer"
    # answer_text should be null (no parsed_answers provided)
    assert q11[0, "answer_text"] is None


@pytest.mark.parametrize(
    "stimulus_name,pisa_middle",
    [
        ("Arg_PISACowsMilk_10", "2"),
        ("Lit_Solaris_7", "1"),
    ],
)
def test_collect_session_answers_builds_rows_and_ids(
    tmp_path: Path, stimulus_name, pisa_middle
):
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
