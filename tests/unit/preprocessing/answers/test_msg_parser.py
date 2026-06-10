import polars as pl
import pytest
from preprocessing.answers.msg_parser import parse_answers_from_messages


@pytest.fixture
def single_question_messages():
    return pl.DataFrame(
        {
            "time": [1000, 2000, 2500, 3000, 3001, 3001, 3001, 3005],
            "content": [
                "start_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_distractor_a_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_target_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_final_confirmation",
                "question_screen_image_offset",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_final_answer_given_is_target_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_answer_given_is_correct:True",
                "stop_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111",
            ],
        }
    )


def test_parse_single_question(single_question_messages):
    result = parse_answers_from_messages(single_question_messages)

    assert len(result) == 1
    row = result.row(0, named=True)
    assert row["trial_id"] == "trial_1"
    assert row["stimulus_name"] == "Lit_MagicMountain"
    assert row["stimulus_id"] == "6"
    assert row["question_id"] == "6111"
    assert row["question_onset_ts"] == 1000.0
    assert row["preliminary_keys"] == ["distractor_a_key", "target_key"]
    assert row["preliminary_tss"] == [2000.0, 2500.0]
    assert row["final_confirmation_ts"] == 3000.0
    assert row["image_offset_ts"] == 3001.0
    assert row["final_answer_key"] == "target_key"
    assert row["is_correct"] is True
    assert row["question_stop_ts"] == 3005.0


def test_parse_multiple_questions():
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 3000, 4000, 5000, 6000],
            "content": [
                "start_recording_trial_1_stimulus_Lit_6_question_6111",
                "trial_1_stimulus_Lit_6_question_6111_answer_given_is_correct:True",
                "stop_recording_trial_1_stimulus_Lit_6_question_6111",
                "start_recording_trial_1_stimulus_Lit_6_question_6112",
                "trial_1_stimulus_Lit_6_question_6112_answer_given_is_correct:False",
                "stop_recording_trial_1_stimulus_Lit_6_question_6112",
            ],
        }
    )
    result = parse_answers_from_messages(messages)
    assert len(result) == 2
    assert result[0, "question_id"] == "6111"
    assert result[0, "is_correct"] is True
    assert result[1, "question_id"] == "6112"
    assert result[1, "is_correct"] is False


def test_parse_practice_trial():
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 3000],
            "content": [
                "start_recording_PRACTICE_trial_1_stimulus_Lit_6_question_6111",
                "PRACTICE_trial_1_stimulus_Lit_6_question_6111_answer_given_is_correct:True",
                "stop_recording_PRACTICE_trial_1_stimulus_Lit_6_question_6111",
            ],
        }
    )
    result = parse_answers_from_messages(messages)
    assert len(result) == 1
    assert result[0, "trial_id"] == "PRACTICE_trial_1"


def test_parse_empty_messages():
    result = parse_answers_from_messages(pl.DataFrame())
    assert len(result) == 0
    assert "trial_id" in result.columns


def test_parse_no_answer_messages():
    messages = pl.DataFrame(
        {"time": [1000.0, 2000.0], "content": ["some message", "another message"]}
    )
    result = parse_answers_from_messages(messages)
    assert len(result) == 0


def test_preliminary_no_keys():
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 3000],
            "content": [
                "start_recording_trial_1_stimulus_Lit_6_question_6111",
                "trial_1_stimulus_Lit_6_question_6111_preliminary_answer_final_confirmation",
                "stop_recording_trial_1_stimulus_Lit_6_question_6111",
            ],
        }
    )
    result = parse_answers_from_messages(messages)
    assert result[0, "preliminary_keys"].to_list() == []
    assert result[0, "final_confirmation_ts"] == 2000.0
