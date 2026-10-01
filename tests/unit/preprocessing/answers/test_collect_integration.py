from pathlib import Path

import polars as pl
import pytest

from preprocessing.answers.collect import collect_session_answers
from preprocessing.answers.msg_parser import parse_answers_from_messages
from preprocessing.data_collection.stimulus import ComprehensionQuestion, Stimulus


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
        snippet_no=1,
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
        completed_stimuli_ids=[6],
    )

    # Check that it merged correctly
    # 6 questions per trial (as per mock_question_order_csv)
    assert len(result) == 6

    # Check the one we have answers for
    q11 = result.filter(pl.col("question_id") == "6111").row(0, named=True)
    assert q11["stimulus_id"] == 6
    assert q11["confirmation_rt_ms"] == 2000.0  # 3000 - 1000
    assert q11["correct_answer_text"] == "Correct Text 1"
    assert q11["snippet_number"] == 1
    assert q11["condition_number"] == 1
    assert q11["question_order_version"] == 6


def test_decision_rt_from_last_prelim_key(mock_question_order_csv, mock_stimuli):
    """preliminary_rt_ms uses the LAST preliminary key, not the first."""
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 2500, 3000, 3500, 3501],
            "content": [
                "start_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_target_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_distractor_a_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_distractor_b_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_final_confirmation",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_final_answer_given_is_distractor_b_key",
            ],
        }
    )
    parsed = parse_answers_from_messages(messages)
    result = collect_session_answers(
        question_order_csv=mock_question_order_csv,
        stimuli_trial_map={"trial_1": "Lit_MagicMountain_6"},
        stimuli=mock_stimuli,
        parsed_answers=parsed,
    )
    q11 = result.filter(pl.col("question_id") == "6111").row(0, named=True)
    # preliminary_rt_ms = last preliminary key ts (3000) - onset (1000) = 2000
    assert q11["preliminary_rt_ms"] == 2000.0
    # confirmation_rt_ms = final_confirmation_ts (3500) - onset (1000) = 2500
    assert q11["confirmation_rt_ms"] == 2500.0
    # preliminary_answer_keys lists all keys pressed
    assert q11["preliminary_answer_keys"] == [
        "target_key",
        "distractor_a_key",
        "distractor_b_key",
    ]


def test_preliminary_answer_onsets(mock_question_order_csv, mock_stimuli):
    """preliminary_answer_onsets_ms contains onset-relative timestamps."""
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 2500, 3000, 3001],
            "content": [
                "start_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_target_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_distractor_a_key",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_final_confirmation",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_final_answer_given_is_distractor_a_key",
            ],
        }
    )
    parsed = parse_answers_from_messages(messages)
    result = collect_session_answers(
        question_order_csv=mock_question_order_csv,
        stimuli_trial_map={"trial_1": "Lit_MagicMountain_6"},
        stimuli=mock_stimuli,
        parsed_answers=parsed,
    )
    q11 = result.filter(pl.col("question_id") == "6111").row(0, named=True)
    assert q11["preliminary_answer_onsets_ms"] == [1000.0, 1500.0]


def test_space_answer_no_selection(mock_question_order_csv, mock_stimuli):
    """Space-only answer (no key selected) gets final_answer_key='space'."""
    messages = pl.DataFrame(
        {
            "time": [1000, 2000, 2000],
            "content": [
                "start_recording_trial_1_stimulus_Lit_MagicMountain_6_question_6111",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_preliminary_answer_final_confirmation",
                "trial_1_stimulus_Lit_MagicMountain_6_question_6111_answer_given_is_correct:False",
            ],
        }
    )
    parsed = parse_answers_from_messages(messages)
    result = collect_session_answers(
        question_order_csv=mock_question_order_csv,
        stimuli_trial_map={"trial_1": "Lit_MagicMountain_6"},
        stimuli=mock_stimuli,
        parsed_answers=parsed,
    )
    q11 = result.filter(pl.col("question_id") == "6111").row(0, named=True)
    assert q11["final_answer_key"] == "space"
    assert q11["is_correct"] is False  # experiment records is_correct:False
    assert q11["confirmation_rt_ms"] == 1000.0  # 2000 - 1000
    assert q11["preliminary_rt_ms"] is None  # no preliminary keys


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
            snippet_no=1,
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
    q11 = result.filter(pl.col("condition_number") == 1).filter(
        pl.col("question_id") == "4111"
    )
    assert q11[0, "stimulus_id"] == 4
    assert q11[0, "question_id"] == "4111"
    assert q11[0, "correct_answer_key"] == "target_key"
    assert q11[0, "correct_answer_text"] == "Correct"
    assert q11[0, "condition_number"] == 1
    # order_code=12 -> last 2 chars of "04112" = "12" -> question_id = 4112
    q12 = result.filter(pl.col("condition_number") == 1).filter(
        pl.col("question_id") == "4112"
    )
    assert q12[0, "question_id"] == "4112"
    assert q12[0, "correct_answer_key"] == "target_key"
    assert q12[0, "correct_answer_text"] == "Correct"
    assert q12[0, "condition_number"] == 1


# Fixtures


@pytest.fixture
def qcsv(tmp_path):
    """Single-trial question order CSV."""
    p = tmp_path / "question_order_versions.csv"
    p.write_text(
        "question_order_version,local_question_1,local_question_2,"
        "bridging_question_1,bridging_question_2,global_question_1,global_question_2\n"
        "6,11,12,21,22,31,32\n"
    )
    return p


@pytest.fixture
def twoq_stimuli():
    """Stimulus with two questions (order codes 11, 12) for enrichment tests."""
    qs = [
        ComprehensionQuestion(
            name=f"Stim_6_{qid}",
            id=qid,
            snippet_no=1,
            question=f"Q{i}",
            target="Correct A" if i == 1 else "Correct B",
            distractor_a="Wrong A1" if i == 1 else "Wrong A2",
            distractor_b="Wrong B1" if i == 1 else "Wrong B2",
            distractor_c="Wrong C1" if i == 1 else "Wrong C2",
            image_path=Path("img.png"),
            aoi_image_path=Path("aoi.png"),
        )
        for i, qid in enumerate(["11", "21"], start=1)
    ]
    return [
        Stimulus(
            id=6,
            name="TestStim",
            type="experiment",
            pages=[],
            text_stimulus=None,
            questions=qs,
            instructions=[],
            ratings=[],
            trial_id="trial_1",
        )
    ]


def _make_messages(
    trial: str = "trial_1",
    stim_name: str = "TestStim",
    stim_id: str = "6",
    question_id: str = "6111",
    prelim_keys: list[tuple[int, str]] | None = None,
    confirm_ts: int | None = 2500,
    final_key: tuple[int, str] | None = None,
    correct: bool | None = None,
) -> pl.DataFrame:
    """Build a synthetic messages DataFrame for testing."""
    rows = []
    rows.append(
        {
            "time": 1000,
            "content": f"start_recording_{trial}_stimulus_{stim_name}_{stim_id}_question_{question_id}",
        }
    )
    if prelim_keys:
        for ts, key in prelim_keys:
            rows.append(
                {
                    "time": ts,
                    "content": f"{trial}_stimulus_{stim_name}_{stim_id}_question_{question_id}_preliminary_answer_{key}",
                }
            )
    if confirm_ts is not None:
        rows.append(
            {
                "time": confirm_ts,
                "content": f"{trial}_stimulus_{stim_name}_{stim_id}_question_{question_id}_preliminary_answer_final_confirmation",
            }
        )
    if final_key is not None:
        rows.append(
            {
                "time": final_key[0],
                "content": f"{trial}_stimulus_{stim_name}_{stim_id}_question_{question_id}_final_answer_given_is_{final_key[1]}",
            }
        )
    if correct is not None:
        rows.append(
            {
                "time": 9999,
                "content": f"{trial}_stimulus_{stim_name}_{stim_id}_question_{question_id}_answer_given_is_correct:{correct}",
            }
        )
    return pl.DataFrame(rows)


# Column-specific parametrized tests


class TestOutputColumns:
    """Parametrized tests for every output column."""

    # --- slot ---

    def test_slot_names_are_present(self, qcsv):
        df = collect_session_answers(qcsv, {"trial_1": "Stim"})
        assert set(df["slot"].to_list()) == {
            "local_question_1",
            "local_question_2",
            "bridging_question_1",
            "bridging_question_2",
            "global_question_1",
            "global_question_2",
        }

    # --- order_code ---

    @pytest.mark.parametrize(
        "slot_name,expected_condition",
        [
            ("local_question_1", 1),
            ("local_question_2", 1),
            ("bridging_question_1", 2),
            ("bridging_question_2", 2),
            ("global_question_1", 3),
            ("global_question_2", 3),
        ],
    )
    def test_condition_number_by_slot(self, qcsv, slot_name, expected_condition):
        df = collect_session_answers(qcsv, {"trial_1": "Stim"})
        row = df.filter(pl.col("slot") == slot_name).row(0, named=True)
        assert row["condition_number"] == expected_condition
        assert row["question_order_version"] == 6

    # --- answer_source ---

    @pytest.mark.parametrize("source", ["asc", "logfile"])
    def test_answer_source(self, qcsv, twoq_stimuli, source):
        msgs = _make_messages(
            prelim_keys=[(2000, "target_key")],
            final_key=(2600, "target_key"),
            correct=True,
            question_id="6111",
        )
        parsed = parse_answers_from_messages(msgs)
        df = collect_session_answers(
            qcsv,
            {"trial_1": "TestStim"},
            stimuli=twoq_stimuli,
            parsed_answers=parsed,
            source=source,
            completed_stimuli_ids=[6],
        )
        q11 = (
            df.filter(pl.col("condition_number") == 1)
            .filter(pl.col("question_id") == "6111")
            .row(0, named=True)
        )
        assert q11["answer_source"] == source

    # --- answer_text ---

    @pytest.mark.parametrize(
        "key,expected_text",
        [
            ("target_key", "Correct A"),
            ("distractor_a_key", "Wrong A1"),
            ("distractor_b_key", "Wrong B1"),
            ("distractor_c_key", "Wrong C1"),
        ],
    )
    def test_answer_text_resolves_option(self, qcsv, twoq_stimuli, key, expected_text):
        msgs = _make_messages(
            prelim_keys=[(2000, key)],
            final_key=(2600, key),
            correct=(key == "target_key"),
            question_id="6111",
        )
        parsed = parse_answers_from_messages(msgs)
        df = collect_session_answers(
            qcsv,
            {"trial_1": "TestStim"},
            stimuli=twoq_stimuli,
            parsed_answers=parsed,
            completed_stimuli_ids=[6],
        )
        q11 = (
            df.filter(pl.col("condition_number") == 1)
            .filter(pl.col("question_id") == "6111")
            .row(0, named=True)
        )
        assert q11["answer_text"] == expected_text

    def test_answer_text_null_for_space(self, qcsv, twoq_stimuli):
        """answer_text is None when no key was selected (space-only)."""
        msgs = _make_messages(
            confirm_ts=2000,
            correct=False,
            question_id="6111",
        )
        parsed = parse_answers_from_messages(msgs)
        df = collect_session_answers(
            qcsv,
            {"trial_1": "TestStim"},
            stimuli=twoq_stimuli,
            parsed_answers=parsed,
            completed_stimuli_ids=[6],
        )
        q11 = (
            df.filter(pl.col("condition_number") == 1)
            .filter(pl.col("question_id") == "6111")
            .row(0, named=True)
        )
        assert q11["answer_text"] is None

    # --- is_correct ---

    @pytest.mark.parametrize(
        "key,correct,expected",
        [
            pytest.param("target_key", True, True, id="correct_answer"),
            pytest.param("distractor_a_key", False, False, id="wrong_answer"),
            pytest.param("target_key", None, True, id="no_correctness_msg"),
        ],
    )
    def test_is_correct_values(self, qcsv, twoq_stimuli, key, correct, expected):
        msgs = _make_messages(
            prelim_keys=[(2000, key)],
            final_key=(2600, key),
            correct=correct,
            question_id="6111",
        )
        parsed = parse_answers_from_messages(msgs)
        df = collect_session_answers(
            qcsv,
            {"trial_1": "TestStim"},
            stimuli=twoq_stimuli,
            parsed_answers=parsed,
            completed_stimuli_ids=[6],
        )
        q11 = (
            df.filter(pl.col("condition_number") == 1)
            .filter(pl.col("question_id") == "6111")
            .row(0, named=True)
        )
        assert q11["is_correct"] is expected

    # --- trial naming ---

    @pytest.mark.parametrize(
        "trial_key,expected_trial",
        [
            ("trial_1", "trial_1"),
            ("trial_7", "trial_7"),
            (1, "trial_1"),
            (7, "trial_7"),
        ],
    )
    def test_trial_column_naming(self, qcsv, trial_key, expected_trial):
        mapping = {trial_key: "Stim"}
        df = collect_session_answers(qcsv, mapping)
        assert df[0, "trial"] == expected_trial

    def test_trial_column_naming_practice(self, qcsv):
        """Practice trial naming requires answer data (unanswered practice rows are dropped)."""
        msgs = _make_messages(
            trial="PRACTICE_trial_1",
            stim_name="Stim",
            stim_id="1",
            question_id="1111",
            prelim_keys=[(2000, "target_key")],
            final_key=(2600, "target_key"),
            correct=True,
        )
        parsed = parse_answers_from_messages(msgs)
        df = collect_session_answers(
            qcsv,
            {"PRACTICE_trial_1": "Stim"},
            parsed_answers=parsed,
            completed_stimuli_ids=[1],
        )
        assert df.height > 0
        assert df[0, "trial"] == "PRACTICE_trial_1"

    # --- stimulus naming ---

    @pytest.mark.parametrize(
        "stim_name",
        [
            "Lit_MagicMountain_6",
            "Arg_PISACowsMilk_10",
            "Enc_WikiMoon",
        ],
    )
    def test_stimulus_column(self, qcsv, stim_name):
        stim_id = 10 if "PISA" in stim_name else 7 if "Solaris" in stim_name else 13
        df = collect_session_answers(
            qcsv, {"trial_1": stim_name}, completed_stimuli_ids=[stim_id]
        )
        assert df[0, "stimulus"] == stim_name
        assert df[0, "stimulus_id"] == stim_id


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
        snippet_no=1,
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

    assert result.is_empty()  # unanswered practice rows are dropped
    assert out_path.read_text().strip().endswith("answer_source")  # header only
