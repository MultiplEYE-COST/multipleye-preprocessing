import polars as pl
import pytest
from preprocessing.answers.experiment_log_parser import parse_answers_from_logfile


@pytest.fixture
def synthetic_logfile():
    return pl.DataFrame(
        {
            "timestamp": [40100.0, 40414.0, 40782.0, 40784.0],
            "trial_number": [1, 1, 1, 1],
            "stimulus_number": [8, 8, 8, 8],
            "page_number": [8111, 8111, 8111, 8111],
            "message": [
                "preliminary answer: distractor_b_key",
                "preliminary answer: distractor_b_key",
                "preliminary answer: final_confirmation",
                "FINAL ANSWER: correct answer is 'right', participant's answer is False",
            ],
        }
    )


def test_parse_logfile_single_question(synthetic_logfile):
    stimuli_trial_mapping = {"trial_1": "Toy_Stimulus"}
    with pytest.warns(UserWarning, match="ASC messages are missing or empty"):
        result = parse_answers_from_logfile(synthetic_logfile, stimuli_trial_mapping)

    assert len(result) == 1
    row = result.row(0, named=True)
    assert row["trial_id"] == "trial_1"
    assert row["stimulus_name"] == "Toy_Stimulus"
    assert row["stimulus_id"] == "8"
    assert row["question_id"] == "8111"
    assert row["preliminary_keys"] == ["distractor_b_key", "distractor_b_key"]
    assert row["final_confirmation_ts"] == 40782.0
    assert row["final_answer_key"] == "distractor_b_key"
    assert row["is_correct"] is False
    assert row["question_stop_ts"] == 40784.0


@pytest.mark.filterwarnings(
    r"ignore:ASC messages are missing or.*from the experiment logfile:UserWarning:"
)
def test_parse_logfile_correct_answer():
    logfile = pl.DataFrame(
        {
            "timestamp": [55882.0, 56135.0, 56138.0],
            "trial_number": [1, 1, 1],
            "stimulus_number": [1, 1, 1],
            "page_number": [1111, 1111, 1111],
            "message": [
                "preliminary answer: target_key",
                "preliminary answer: final_confirmation",
                "FINAL ANSWER: correct answer is 'down', participant's answer is True",
            ],
        }
    )
    result = parse_answers_from_logfile(logfile)
    assert result[0, "is_correct"] is True
    assert result[0, "final_answer_key"] == "target_key"


@pytest.mark.filterwarnings(
    r"ignore:ASC messages are missing or.*from the experiment logfile:UserWarning:"
)
def test_parse_logfile_empty():
    result = parse_answers_from_logfile(pl.DataFrame())
    assert len(result) == 0


@pytest.mark.filterwarnings(
    r"ignore:ASC messages are missing or.*from the experiment logfile:UserWarning:"
)
def test_parse_logfile_no_relevant_messages():
    logfile = pl.DataFrame({"timestamp": [1000.0], "message": ["some random message"]})
    # Since columns like trial_number are missing, it might fail or return empty
    # Our implementation handles empty filtered DF
    result = parse_answers_from_logfile(logfile)
    assert len(result) == 0
