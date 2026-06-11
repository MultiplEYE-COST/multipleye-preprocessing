import polars as pl
import pytest
from pathlib import Path
from preprocessing.answers.collect import collect_session_answers
from preprocessing.answers.msg_parser import parse_answers_from_messages
from preprocessing.data_collection.stimulus import Stimulus, ComprehensionQuestion


@pytest.fixture
def mock_question_order_csv(tmp_path):
    csv_path = tmp_path / "question_order_versions.csv"
    content = "question_order_version,local_question_1,local_question_2,bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
    content += "6,11,12,21,22,31,32\n"
    csv_path.write_text(content)
    return csv_path


@pytest.fixture
def mock_stimuli():
    q1 = ComprehensionQuestion(
        name="Lit_MagicMountain_6_11",
        id="11",
        question="Q1",
        target="Correct Text 1",
        distractor_a="Wrong 1",
        distractor_b="Wrong 2",
        distractor_c="Wrong 3",
        image_path=Path("fake_img.png"),
        aoi_image_path=Path("fake_aoi.png"),
    )
    stim1 = Stimulus(
        id=6,
        name="Lit_MagicMountain_6",
        type="experiment",
        pages=[],
        text_stimulus=None,
        questions=[q1],
        instructions=[],
        ratings=[],
        trial_id="trial_1",
    )
    return [stim1]


def test_collect_session_answers_integration(mock_question_order_csv, mock_stimuli):
    stimuli_trial_mapping = {"trial_1": "Lit_MagicMountain_6"}

    # Synthetic messages
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 3000],
            "content": [
                "start_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_target_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_final_confirmation",
            ],
        }
    )

    parsed_answers = parse_answers_from_messages(messages)

    result = collect_session_answers(
        question_order_csv=mock_question_order_csv,
        stimuli_trial_map=stimuli_trial_mapping,
        stimuli=mock_stimuli,
        parsed_answers=parsed_answers,
    )

    # Check that it merged correctly
    # 6 questions per trial (as per mock_question_order_csv)
    assert len(result) == 6

    # Check the one we have answers for
    q11 = result.filter(pl.col("question_id") == "6111")
    assert len(q11) == 1
    assert q11[0, "final_rt_ms"] == 2000.0  # 3000 - 1000
    assert q11[0, "correct_answer_text"] == "Correct Text 1"
    assert q11[0, "answer_changed"] is False


def test_multidigit_qid_enrichment(tmp_path):
    """Enrichment works when ComprehensionQuestion.id has multi-digit format like '04111'."""
    qcsv = tmp_path / "question_order_versions.csv"
    qcsv.write_text(
        "question_order_version,local_question_1,local_question_2,"
        "bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
        "1,11,12,21,22,31,32\n"
    )
    out_path = tmp_path / "answers.csv"
    mapping = {"trial_1": "Lit_Alchemist_4"}

    # Use multi-digit q.id as seen in real MultiplEYE data (item_id like "Lit_Alchemist_4_04111")
    qs = [
        ComprehensionQuestion(
            name=f"Lit_Alchemist_4_0411{i}",
            id=f"0411{i}",
            question=f"Q{i}",
            target="Correct",
            distractor_a=f"WrongA{i}",
            distractor_b=f"WrongB{i}",
            distractor_c=f"WrongC{i}",
            image_path=Path("img.png"),
            aoi_image_path=Path("aoi.png"),
        )
        for i in range(1, 3)  # q.id = "04111", "04112"
    ]
    stimuli = [
        Stimulus(
            id=4,
            name="Lit_Alchemist_4",
            type="experiment",
            pages=[],
            text_stimulus=None,
            questions=qs,
            instructions=[],
            ratings=[],
            trial_id="trial_1",
        )
    ]

    result = collect_session_answers(
        qcsv, mapping, stimuli=stimuli, out_path=out_path, completed_stimuli_ids=[4]
    )

    assert len(result) == 6
    # order_code=11 -> last 2 chars of "04111" = "11" -> question_id = 4111
    q11 = result.filter(pl.col("order_code") == 11)
    assert q11[0, "question_id"] == "4111"
    assert q11[0, "correct_answer_key"] == "target_key"
    assert q11[0, "correct_answer_text"] == "Correct"
    # order_code=12 -> last 2 chars of "04112" = "12" -> question_id = 4112
    q12 = result.filter(pl.col("order_code") == 12)
    assert q12[0, "question_id"] == "4112"
    assert q12[0, "correct_answer_key"] == "target_key"
    assert q12[0, "correct_answer_text"] == "Correct"


def test_practice_trial_answers(tmp_path):
    """Practice trials are handled correctly with PRACTICE_trial naming."""
    qcsv = tmp_path / "question_order_versions.csv"
    qcsv.write_text(
        "question_order_version,local_question_1,local_question_2,"
        "bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
        "1,11,12,21,22,31,32\n"
    )
    out_path = tmp_path / "answers.csv"
    mapping = {"PRACTICE_trial_1": "Enc_WikiMoon"}
    q1 = ComprehensionQuestion(
        name="Enc_WikiMoon_13_11",
        id="11",
        question="Q",
        target="Correct",
        distractor_a="A",
        distractor_b="B",
        distractor_c="C",
        image_path=Path("img.png"),
        aoi_image_path=Path("aoi.png"),
    )
    stimuli = [
        Stimulus(
            id=13,
            name="Enc_WikiMoon",
            type="practice",
            pages=[],
            text_stimulus=None,
            questions=[q1],
            instructions=[],
            ratings=[],
            trial_id="PRACTICE_trial_1",
        )
    ]
    result = collect_session_answers(
        qcsv, mapping, stimuli=stimuli, out_path=out_path, completed_stimuli_ids=[13]
    )

    assert len(result) == 6
    assert result[0, "trial"] == "PRACTICE_trial_1"
    assert result[0, "stimulus"] == "Enc_WikiMoon"
    q11 = result.filter(pl.col("order_code") == 11)
    assert q11[0, "correct_answer_text"] == "Correct"
