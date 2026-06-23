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
    # Question with order_code (was 11) -> condition_number=1 -> question_id=6111
    q11 = df.filter(pl.col("condition_number") == 1).filter(
        pl.col("question_id") == "6111"
    )
    assert q11[0, "stimulus_id"] == 6
    assert q11[0, "correct_answer_key"] == "target_key"
    assert q11[0, "correct_answer_text"] == "Correct Answer"
    assert q11[0, "question_id"] == "6111"
    assert q11[0, "snippet_number"] == 1
    assert q11[0, "condition_number"] == 1
    # q12 (also condition_number=1) has the same target
    q12 = df.filter(pl.col("condition_number") == 1).filter(
        pl.col("question_id") == "6112"
    )
    assert q12[0, "correct_answer_key"] == "target_key"
    assert q12[0, "correct_answer_text"] == "Correct Answer"
    assert q12[0, "question_id"] == "6112"


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
    # Multi-digit '04111' -> last 2 chars '11' -> condition_number=1 -> question_id=4111
    q11 = df.filter(pl.col("condition_number") == 1).filter(
        pl.col("question_id") == "4111"
    )
    assert q11[0, "stimulus_id"] == 4
    assert q11[0, "correct_answer_key"] == "target_key"
    assert q11[0, "correct_answer_text"] == "Correct Answer"
    assert q11[0, "question_id"] == "4111"
    assert q11[0, "snippet_number"] == 1
    assert q11[0, "condition_number"] == 1
    # answer_text should be null (no parsed_answers provided)
    assert q11[0, "answer_text"] is None


def _expected_middle(stimulus_name: str, order_code: int) -> str:
    """Compute the expected middle digit for a stimulus and order_code."""
    return str(order_code)[1] if "PISA" in stimulus_name else "1"


@pytest.mark.parametrize(
    "stimulus_name",
    [
        "Arg_PISACowsMilk_10",
        "Lit_Solaris_7",
    ],
)
def test_collect_session_answers_builds_rows_and_ids(tmp_path: Path, stimulus_name):
    # Prepare a minimal question_order_versions.csv with one trial
    csv = (
        "question_order_version,local_question_1,local_question_2,bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
        "6,12,11,21,22,32,31\n"
    )
    qcsv = tmp_path / "question_order_versions.csv"
    qcsv.write_text(csv)

    # Provide stimuli mapping for trial 1
    mapping = {"trial_1": stimulus_name}
    stim_id = int(stimulus_name.split("_")[-1])

    out_path = tmp_path / "answers.csv"
    df = collect_session_answers(
        qcsv, mapping, out_path=out_path, completed_stimuli_ids=[stim_id]
    )

    # Expect 6 rows (six question slots) for the one trial
    assert df.shape[0] == 6
    assert set(df["trial"].to_list()) == {"trial_1"}
    assert set(df["stimulus"].to_list()) == {stimulus_name}
    assert set(df["stimulus_id"].to_list()) == {stim_id}

    # Check condition codes covered and IDs well-formed
    conditions = set(df["condition_number"].to_list())
    assert conditions == {1, 2, 3}

    # Verify question_id format: <stim_num>1<order_code>
    stim_num = stimulus_name.split("_")[-1]
    expected_codes = {12, 11, 21, 22, 32, 31}
    found_qids = set(df["question_id"].to_list())
    expected_qids = {f"{stim_num}1{code}" for code in expected_codes}
    assert found_qids == expected_qids

    for row in df.iter_rows(named=True):
        assert row["snippet_number"] == 1
        assert row["condition_number"] in {1, 2, 3}

    # File written and loadable
    assert out_path.exists()
    loaded = pl.read_csv(out_path)
    assert loaded.shape == df.shape
