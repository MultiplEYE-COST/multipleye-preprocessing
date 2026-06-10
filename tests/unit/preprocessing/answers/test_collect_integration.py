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
    # Looking at preprocessing/data_collection/stimulus.py:
    # ComprehensionQuestion has fields: name, id, question, target, distractor_a, distractor_b, distractor_c, image_path, aoi_image_path
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
