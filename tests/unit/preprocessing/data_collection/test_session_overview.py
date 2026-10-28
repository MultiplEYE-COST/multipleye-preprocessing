import contextlib
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

from preprocessing.data_collection.experimenter_doc import ExperimenterDoc
from preprocessing.data_collection.session import Session
from preprocessing.data_collection.stimulus import LabConfig


def _make_session(overrides: dict | None = None) -> Session:
    fields = {
        "participant_id": 1,
        "session_identifier": "001_EN_UK_1_ET1",
        "is_pilot": False,
        "session_folder_path": Path("/tmp"),
        "session_file_path": Path("/tmp/test.log"),
        "session_file_name": "test.log",
        **(overrides or {}),
    }
    return Session(**fields)


def _mock_lab_config() -> LabConfig:
    return LabConfig(
        screen_resolution=(1920, 1080),
        screen_size_cm=(52.0, 32.0),
        screen_distance_cm=60.0,
        image_resolution=(1322, 980),
        image_size_cm=(38.0, 28.3),
        name_eye_tracker="Eyelink 1000-Plus",
        sampling_frequency_hz=1000.0,
        psychometric_tests=[],
    )


def _seed_metadata(sess: Session) -> None:
    sess.pm_gaze_metadata = {
        "tracked_eye": "R",
        "data_loss_ratio": 0.02,
        "mount_configuration": {
            "mount_type": "Desktop",
            "head_stabilization": "stabilized",
            "eyes_recorded": "binocular / monocular",
        },
        "pupil_data_type": "AREA",
    }
    sess.lab_config = _mock_lab_config()


def _validations(accuracy: list[float | None] | None = None) -> pl.DataFrame:
    accuracy = accuracy if accuracy is not None else [0.2, 0.35, 0.5]
    return pl.DataFrame(
        {
            "time": list(range(100, 100 + len(accuracy))),
            "accuracy_avg": accuracy,
            "accuracy_max": [0.3] * len(accuracy),
            "eye": ["right"] * len(accuracy),
        }
    )


def _calibrations() -> pl.DataFrame:
    return pl.DataFrame({"time": [50.0, 150.0]})


def _sess_with_validation_data() -> Session:
    sess = _make_session()
    _seed_metadata(sess)
    sess.validations = _validations()
    sess.calibrations = _calibrations()
    return sess


def test_create_overview_includes_new_fields() -> None:
    sess = _sess_with_validation_data()

    overview = sess.create_overview()

    tracking = overview["tracking"]
    assert tracking["tracked_eye"] == "R"
    assert tracking["tracked_eye_consistent"] is True
    cal = overview["calibration_validation"]
    assert cal["calibration_quality"] == "unknown"
    assert cal["validation_quality"] == "unknown"
    assert cal["final_validation_score_dva"] == "unknown"
    assert cal["num_aborted_validations"] == 0
    assert cal["num_good_validations"] == 1
    assert cal["num_moderate_validations"] == 1
    assert cal["num_bad_validations"] == 1
    dq = overview["data_quality"]
    assert "session_total_data_loss_ratio" in dq
    assert dq["session_total_data_loss_ratio"] is None
    assert "session_blink_loss_ratio" in dq
    assert dq["session_blink_loss_ratio"] is None


def test_create_overview_includes_stimulus_content_version() -> None:
    sess = _make_session()
    sess.stimulus_content_version = "v1"

    overview = sess.create_overview()

    assert overview["experiment_procedure"]["stimulus_content_version"] == "v1"


def test_create_overview_stimulus_content_version_defaults_to_unknown() -> None:
    sess = _make_session()

    overview = sess.create_overview()

    assert overview["experiment_procedure"]["stimulus_content_version"] == "unknown"


def test_create_overview_includes_measure_based_data_loss() -> None:
    sess = _sess_with_validation_data()
    sess._measure_total_data_loss_ratio = 0.015
    sess._measure_blink_loss_ratio = 0.008

    overview = sess.create_overview()

    dq = overview["data_quality"]
    assert dq["session_total_data_loss_ratio"] == 0.015
    assert dq["session_blink_loss_ratio"] == 0.008


def test_tracked_eye_inconsistent_when_eye_changes() -> None:
    validations = _validations()
    validations = validations.with_columns(pl.lit("left").alias("eye"))
    sess = _make_session()
    sess.validations = validations
    sess.calibrations = _calibrations()
    _seed_metadata(sess)

    overview = sess.create_overview()

    tracking = overview["tracking"]
    assert tracking["tracked_eye"] == "R"
    assert tracking["tracked_eye_consistent"] is False


def test_sections_are_present() -> None:
    sess = _sess_with_validation_data()

    overview = sess.create_overview()

    assert list(overview.keys()) == [
        "administrative",
        "participant",
        "technical_setup",
        "tracking",
        "calibration_validation",
        "data_quality",
        "experiment_procedure",
        "trials",
        "comprehension",
        "data_formats",
    ]


def test_technical_setup_from_lab_config() -> None:
    sess = _sess_with_validation_data()

    overview = sess.create_overview()
    tech = overview["technical_setup"]

    assert tech["eye_tracker_name"] == "EyeLink 1000 Plus"
    assert tech["sampling_frequency_hz"] == 1000.0
    assert tech["mount_type"] == "Desktop"
    assert tech["head_stabilization"] == "stabilized"
    assert tech["eyes_recorded"] == "binocular / monocular"
    assert tech["pupil_data_type"] == "AREA"
    assert tech["screen_resolution_width_px"] == 1920
    assert tech["screen_resolution_height_px"] == 1080
    assert tech["screen_distance_cm"] == 60.0
    assert tech["image_size_width_cm"] == 38.0


def test_avg_validation_error_computed_from_validations() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = _validations([0.2, 0.3, 0.4])

    overview = sess.create_overview()
    cal = overview["calibration_validation"]

    assert cal["avg_validation_error_dva"] == 0.3
    assert cal["num_calibrations"] == 1
    assert cal["num_validations"] == 3


def test_comprehension_scores_read_from_answers_csv(tmp_path: Path) -> None:
    sess = _sess_with_validation_data()

    answers = pl.DataFrame(
        {
            "trial": ["trial_1"] * 6,
            "condition_number": [1, 1, 2, 2, 3, 3],
            "is_correct": [True, False, True, True, False, True],
        }
    )
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    answers.write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == 0.667
    assert comp["avg_comprehension_score_local"] == 0.5
    assert comp["avg_comprehension_score_bridging"] == 1.0
    assert comp["avg_comprehension_score_global"] == 0.5


class _FakeSid:
    def __init__(self, answers_dir: Path):
        self._answers_dir = answers_dir

    @property
    def answers_dir(self) -> Path:
        return self._answers_dir

    def __str__(self) -> str:
        return "001_EN_UK_1_ET1"


def test_session_duration_from_messages() -> None:
    sess = _sess_with_validation_data()
    sess.messages = pl.DataFrame(
        {"time": [1000.0, 2000.0, 60000.0], "content": ["a", "b", "c"]}
    )

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_session_duration_s"] == 59.0


def test_reading_time_from_stimulus_start_end_ts() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
        {"stimulus": "b", "trial": "trial_2", "start_ts": 5000.0, "stop_ts": 7000.0},
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_reading_time_s"] == 5.0


def test_stimulus_order_ids_with_names() -> None:
    from types import SimpleNamespace

    sess = _sess_with_validation_data()
    sess.stimuli = [
        SimpleNamespace(id=1, name="Lit_MagicMountain", trial_id="trial_1"),
        SimpleNamespace(id=2, name="Lit_Alchemist", trial_id="trial_2"),
        SimpleNamespace(id=3, name="Enc_WikiMoon", trial_id="trial_3"),
    ]
    sess.stimulus_order_ids = [3, 1, 2]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["stimulus_order_ids_with_names"] == [
        {"stimulus_id": 3, "stimulus_name": "Enc_WikiMoon", "trial": "trial_3"},
        {"stimulus_id": 1, "stimulus_name": "Lit_MagicMountain", "trial": "trial_1"},
        {"stimulus_id": 2, "stimulus_name": "Lit_Alchemist", "trial": "trial_2"},
    ]


def test_stimulus_order_ids_with_names_unknown_without_stimuli() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_order_ids = [1, 2, 3]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["stimulus_order_ids_with_names"] == "unknown"


def test_mean_rt_per_stim_from_stimulus_start_end_ts() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {
            "stimulus": "a",
            "trial": "trial_1",
            "type": "reading time",
            "duration_ms": 3000.0,
        },
        {
            "stimulus": "a",
            "trial": "trial_1",
            "type": "reading time",
            "duration_ms": 1000.0,
        },
        {
            "stimulus": "b",
            "trial": "trial_2",
            "type": "reading time",
            "duration_ms": 2000.0,
        },
        {
            "stimulus": "a",
            "trial": "trial_1",
            "type": "time before pages and breaks",
            "duration_ms": 500.0,
        },
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["mean_rt_per_stim_ms"] == 3000.0
    assert proc["sd_rt_per_stim_ms"] == 1414.21


def test_mean_rt_per_stim_unknown_without_reading_time() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {
            "stimulus": "a",
            "trial": "trial_1",
            "type": "time before pages and breaks",
            "duration_ms": 500.0,
        },
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["mean_rt_per_stim_ms"] == "unknown"
    assert proc["sd_rt_per_stim_ms"] == "unknown"


def test_compute_total_question_time_excludes_practice() -> None:
    from preprocessing.data_collection.trial import Trial

    sess = _make_session()
    sess.trials = [
        Trial(
            trial_number=1,
            stimulus_id=1,
            stimulus_name="a",
            is_practice=False,
            num_questions=2,
            comprehension_score=0.5,
            comprehension_question_time_ms=1200.0,
            reading_time_ms=1000.0,
        ),
        Trial(
            trial_number=0,
            stimulus_id=0,
            stimulus_name="p",
            is_practice=True,
            num_questions=1,
            comprehension_score=0.0,
            comprehension_question_time_ms=500.0,
            reading_time_ms=100.0,
        ),
        Trial(
            trial_number=2,
            stimulus_id=2,
            stimulus_name="b",
            is_practice=False,
            num_questions=2,
            comprehension_score=1.0,
            comprehension_question_time_ms=800.0,
            reading_time_ms=1000.0,
        ),
    ]

    assert sess._compute_total_question_time() == 2000.0


def test_compute_total_question_time_unknown_without_trials() -> None:
    sess = _make_session()
    assert sess._compute_total_question_time() == "unknown"


def test_rating_stats_from_logfile() -> None:
    sess = _sess_with_validation_data()
    sess.logfile = pl.DataFrame(
        {
            "page_number": [
                "familiarity_rating_screen_1",
                "familiarity_rating_screen_2",
                "subject_difficulty_screen",
                "familiarity_rating_screen_1",
            ],
            "key_pressed": ["option_2", "option_4", "option_3", "option_5"],
            "screen_onset_timestamp": ["1000.0", "2000.0", "3000.0", "5000.0"],
            "timestamp": [2500.0, 2250.0, 3800.0, 6000.0],
        }
    )

    proc = sess.create_overview()["experiment_procedure"]

    assert proc["familiarity_1"] == 3.5
    assert proc["familiarity_2"] == 4.0
    assert proc["subjective_difficulty"] == 3.0
    assert proc["total_rating_time_ms"] == 3550.0


def test_rating_stats_unknown_without_logfile() -> None:
    sess = _sess_with_validation_data()
    proc = sess.create_overview()["experiment_procedure"]

    assert proc["familiarity_1"] == "unknown"
    assert proc["familiarity_2"] == "unknown"
    assert proc["subjective_difficulty"] == "unknown"
    assert proc["total_rating_time_ms"] == "unknown"


def test_restarted_session_name() -> None:
    sess = _make_session(
        overrides={"session_identifier": "041_KL_DK_1_ET1_start_after_trial_1"}
    )
    _seed_metadata(sess)

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["was_session_interrupted"] is True
    assert proc["restarted_session_name"] == "041_KL_DK_1_ET1"


def test_restarted_session_name_absent_for_normal_session() -> None:
    sess = _sess_with_validation_data()

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["was_session_interrupted"] is False
    assert proc["restarted_session_name"] == "unknown"


def test_data_formats_section() -> None:
    sess = _sess_with_validation_data()

    overview = sess.create_overview()
    formats = overview["data_formats"]

    assert formats["raw_data"] is True
    assert formats["fixations"] is True
    assert formats["saccades"] is True
    assert formats["reading_measures"] is True
    assert formats["answers"] is True


def test_technical_setup_unknown_eye_tracker_is_none() -> None:
    sess = _sess_with_validation_data()
    sess.lab_config = LabConfig(
        screen_resolution=(1920, 1080),
        screen_size_cm=(52.0, 32.0),
        screen_distance_cm=60.0,
        image_resolution=(1322, 980),
        image_size_cm=(38.0, 28.3),
        name_eye_tracker="test",
        sampling_frequency_hz=1000.0,
        psychometric_tests=[],
    )

    tech = sess.create_overview()["technical_setup"]

    assert tech["eye_tracker_name"] is None


def test_data_formats_can_be_disabled_for_other_pipelines() -> None:
    sess = _sess_with_validation_data()
    sess.fixations = False
    sess.saccades = False

    overview = sess.create_overview()
    formats = overview["data_formats"]

    assert formats["fixations"] is False
    assert formats["saccades"] is False
    assert formats["raw_data"] is True


# --- Branch coverage: unprocessed / edge-case sessions ---


def test_unprocessed_session_defaults() -> None:
    """A session with no data populated should not crash and report defaults."""
    sess = _make_session()

    overview = sess.create_overview()

    assert overview["tracking"]["tracked_eye"] == "unknown"
    assert overview["technical_setup"]["eye_tracker_name"] is None
    assert overview["calibration_validation"]["avg_validation_error_dva"] == "unknown"
    assert overview["calibration_validation"]["num_calibrations"] == 7
    assert overview["comprehension"]["avg_comprehension_score"] == "unknown"
    assert overview["experiment_procedure"]["total_session_duration_s"] == "unknown"
    assert overview["experiment_procedure"]["total_reading_time_s"] == "unknown"


def test_metadata_not_a_dict() -> None:
    sess = _make_session()
    sess.pm_gaze_metadata = "unknown"

    overview = sess.create_overview()

    assert overview["administrative"]["year_of_data_collection"] == "unknown"
    assert overview["technical_setup"]["mount_type"] is None


def test_mount_configuration_not_a_dict() -> None:
    sess = _make_session()
    sess.pm_gaze_metadata = {
        "tracked_eye": "R",
        "mount_configuration": "unknown",
        "pupil_data_type": "AREA",
    }

    overview = sess.create_overview()
    tech = overview["technical_setup"]

    assert tech["mount_type"] is None
    assert tech["eyes_recorded"] is None


def test_technical_setup_without_lab_config() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.lab_config = "unknown"

    overview = sess.create_overview()
    tech = overview["technical_setup"]

    assert tech["eye_tracker_name"] is None
    assert tech["sampling_frequency_hz"] is None
    assert tech["screen_resolution_width_px"] is None


def test_validations_without_accuracy_column() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = _calibrations()
    sess.validations = pl.DataFrame({"time": [100.0, 200.0]})

    overview = sess.create_overview()
    cal = overview["calibration_validation"]

    assert cal["avg_validation_error_dva"] == "unknown"
    assert cal["num_validations"] == 2


def test_validations_with_null_accuracy() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = _calibrations()
    sess.validations = _validations([None, None])

    overview = sess.create_overview()
    cal = overview["calibration_validation"]

    assert cal["avg_validation_error_dva"] == "unknown"


def test_calibrations_with_accuracy_column() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.validations = _validations()
    sess.calibrations = pl.DataFrame(
        {
            "time": [50.0, 150.0],
            "num_points": [9, 9],
            "eye": ["right", "right"],
            "tracking_mode": ["CR", "CR"],
            "accuracy_avg": [0.1, 0.3],
        }
    )

    overview = sess.create_overview()
    cal = overview["calibration_validation"]

    assert cal["avg_calibration_error_dva"] == 0.2


def test_calibrations_with_null_accuracy() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.validations = _validations()
    sess.calibrations = pl.DataFrame(
        {
            "time": [50.0, 150.0],
            "num_points": [9, 9],
            "eye": ["right", "right"],
            "tracking_mode": ["CR", "CR"],
            "accuracy_avg": [None, None],
        }
    )

    overview = sess.create_overview()
    cal = overview["calibration_validation"]

    assert cal["avg_calibration_error_dva"] == "unknown"


def test_answers_csv_unreadable(tmp_path: Path, monkeypatch) -> None:
    sess = _sess_with_validation_data()
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    (answers_dir / "001_EN_UK_1_ET1_answers.csv").write_text("garbage")

    def _raise(*args, **kwargs):
        from polars.exceptions import ComputeError

        raise ComputeError("cannot parse")

    monkeypatch.setattr("preprocessing.data_collection.session.pl.read_csv", _raise)

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == "unknown"


def test_answers_csv_all_null_is_correct(tmp_path: Path) -> None:
    sess = _sess_with_validation_data()
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    answers = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "condition_number": [1, 2],
            "is_correct": [None, None],
        }
    )
    answers.write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == "unknown"
    assert comp["avg_comprehension_score_local"] == "unknown"


def test_answers_csv_without_one_condition(tmp_path: Path) -> None:
    sess = _sess_with_validation_data()
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    answers = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "condition_number": [1, 1],
            "is_correct": [True, False],
        }
    )
    answers.write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == 0.5
    assert comp["avg_comprehension_score_local"] == 0.5
    assert comp["avg_comprehension_score_bridging"] == "unknown"
    assert comp["avg_comprehension_score_global"] == "unknown"


def test_answers_csv_missing_is_correct(tmp_path: Path) -> None:
    sess = _sess_with_validation_data()
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    answers = pl.DataFrame({"trial": ["trial_1"], "condition_number": [1]})
    answers.write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == "unknown"


def test_answers_csv_practice_only(tmp_path: Path) -> None:
    sess = _sess_with_validation_data()
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    answers = pl.DataFrame(
        {
            "trial": ["PRACTICE_trial_1"],
            "condition_number": [1],
            "is_correct": [True],
        }
    )
    answers.write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == "unknown"


def test_answers_csv_without_condition_number(tmp_path: Path) -> None:
    sess = _sess_with_validation_data()
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    answers = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "is_correct": [True, False],
        }
    )
    answers.write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        overview = sess.create_overview()
        comp = overview["comprehension"]

    assert comp["avg_comprehension_score"] == 0.5
    assert comp["avg_comprehension_score_local"] == "unknown"


def test_session_duration_without_time_column() -> None:
    sess = _sess_with_validation_data()
    sess.messages = pl.DataFrame({"content": ["a", "b"]})

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_session_duration_s"] == "unknown"


def test_session_duration_with_null_timestamps() -> None:
    sess = _sess_with_validation_data()
    sess.messages = pl.DataFrame({"time": [None, None], "content": ["a", "b"]})

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_session_duration_s"] == "unknown"


def test_reading_time_malformed_entries() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
        {"stimulus": "b", "trial": "trial_2"},
        "garbage",
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_reading_time_s"] == 3.0


def test_reading_time_non_positive_total() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 4000.0, "stop_ts": 1000.0},
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_reading_time_s"] == "unknown"


def test_reading_time_clamps_negative_spans() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
        {"stimulus": "b", "trial": "trial_2", "start_ts": 9000.0, "stop_ts": 5000.0},
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_reading_time_s"] == 3.0


def test_reading_time_by_trial_clamps_negative_spans() -> None:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
        {"stimulus": "b", "trial": "trial_1", "start_ts": 9000.0, "stop_ts": 5000.0},
    ]

    assert sess._reading_time_by_trial() == {"trial_1": 3000.0}


def test_reading_time_already_set() -> None:
    sess = _sess_with_validation_data()
    sess.total_reading_time = 42.0
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
    ]

    overview = sess.create_overview()
    proc = overview["experiment_procedure"]

    assert proc["total_reading_time_s"] == 42.0


# --- Trial building ---


def _write_answers(
    tmp_path: Path,
    rows: list[dict],
) -> Path:
    """Write an answers CSV and return the comp_answers dir for the fake sid."""
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    pl.DataFrame(rows).write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")
    return answers_dir


def _trial_sess(answers_dir: Path) -> Session:
    sess = _sess_with_validation_data()
    sess.stimulus_start_end_ts = [
        {
            "stimulus": "Lit_MagicMountain",
            "trial": "trial_1",
            "start_ts": 1000.0,
            "stop_ts": 4000.0,
        },
        {
            "stimulus": "Lit_Alchemist",
            "trial": "trial_2",
            "start_ts": 5000.0,
            "stop_ts": 8000.0,
        },
        {
            "stimulus": "Enc_WikiMoon",
            "trial": "PRACTICE_trial_1",
            "start_ts": 100.0,
            "stop_ts": 500.0,
        },
    ]
    return sess


_ANSWERS_ROWS = [
    {
        "trial": "trial_1",
        "stimulus": "Lit_MagicMountain",
        "stimulus_id": 3,
        "is_correct": True,
        "confirmation_rt_ms": 1000.0,
    },
    {
        "trial": "trial_1",
        "stimulus": "Lit_MagicMountain",
        "stimulus_id": 3,
        "is_correct": False,
        "confirmation_rt_ms": 2000.0,
    },
    {
        "trial": "trial_2",
        "stimulus": "Lit_Alchemist",
        "stimulus_id": 4,
        "is_correct": True,
        "confirmation_rt_ms": 1500.0,
    },
    {
        "trial": "PRACTICE_trial_1",
        "stimulus": "Enc_WikiMoon",
        "stimulus_id": 13,
        "is_correct": True,
        "confirmation_rt_ms": 500.0,
    },
]


@pytest.mark.parametrize(
    (
        "trial_number",
        "is_practice",
        "stimulus_name",
        "num_questions",
        "comprehension_score",
        "question_time_ms",
        "reading_time_ms",
    ),
    [
        (1, False, "Lit_MagicMountain", 2, 0.5, 3000.0, 3000.0),
        (2, False, "Lit_Alchemist", 1, 1.0, 1500.0, 3000.0),
        (1, True, "Enc_WikiMoon", 1, 1.0, 500.0, 400.0),
    ],
)
def test_trials_computed_from_answers_and_reading_times(
    tmp_path: Path,
    trial_number: int,
    is_practice: bool,
    stimulus_name: str,
    num_questions: int,
    comprehension_score: float,
    question_time_ms: float,
    reading_time_ms: float,
) -> None:
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    trial = next(
        t
        for t in trials
        if t["trial_number"] == trial_number and t["is_practice"] == is_practice
    )
    assert trial["stimulus_name"] == stimulus_name
    assert trial["num_questions"] == num_questions
    assert trial["comprehension_score"] == comprehension_score
    assert trial["comprehension_question_time_ms"] == question_time_ms
    assert trial["reading_time_ms"] == reading_time_ms


@pytest.mark.parametrize(
    ("answers_setup",),
    [
        ("missing",),
        ("unreadable",),
    ],
)
def test_trials_unknown_without_usable_answers(
    tmp_path: Path,
    answers_setup: str,
) -> None:
    sess = _sess_with_validation_data()

    def _patched_sid(path: Path):
        return _FakeSid(path)

    if answers_setup == "missing":
        answers_dir = tmp_path / "nonexistent"
    else:
        answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
        answers_dir.mkdir(parents=True)
        (answers_dir / "001_EN_UK_1_ET1_answers.csv").write_text("garbage")

    def _raise(*args, **kwargs):
        from polars.exceptions import ComputeError

        raise ComputeError("cannot parse")

    patches = [
        patch.object(
            Session,
            "sid",
            property(lambda self: _patched_sid(answers_dir)),
        )
    ]
    if answers_setup == "unreadable":
        patches.insert(
            0, patch("preprocessing.data_collection.session.pl.read_csv", _raise)
        )

    with contextlib.ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        trials = sess.create_overview()["trials"]

    assert trials == "unknown"


def test_trials_skip_group_with_missing_stimulus_id(tmp_path: Path) -> None:
    """A trial whose representative row has no stimulus_id is skipped, not crashed."""
    answers_dir = _write_answers(
        tmp_path,
        [
            {
                "trial": "trial_1",
                "stimulus": "Lit_MagicMountain",
                "stimulus_id": 3,
                "is_correct": True,
            },
            {
                "trial": "trial_2",
                "stimulus": "Unknown_Stim_2",
                "stimulus_id": None,
                "is_correct": True,
            },
        ],
    )
    sess = _trial_sess(answers_dir)

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    assert isinstance(trials, list)
    assert [t["trial_number"] for t in trials] == [1]
    assert trials[0]["stimulus_id"] == 3


def test_trials_include_extended_fields(tmp_path: Path) -> None:
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)
    sess.validations = pl.DataFrame(
        {
            "time": [50.0, 700.0, 4500.0],
            "accuracy_avg": [0.2, 0.4, 0.6],
        }
    )
    sess._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2", "PRACTICE_trial_1"],
            "stimulus": ["Lit_MagicMountain", "Lit_Alchemist", "Enc_WikiMoon"],
            "data_loss_ratio": [0.01, 0.02, 0.03],
        }
    )
    sess._per_trial_blink_loss = pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2", "PRACTICE_trial_1"],
            "stimulus": ["Lit_MagicMountain", "Lit_Alchemist", "Enc_WikiMoon"],
            "blink_loss_ratio": [0.1, 0.2, 0.3],
            "blink_duration_ms": [100.0, 200.0, 300.0],
            "trial_duration_ms": [3000.0, 3000.0, 400.0],
        }
    )

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    assert isinstance(trials, list)
    expected_fields = {
        "trial_number",
        "stimulus_id",
        "stimulus_name",
        "is_practice",
        "num_questions",
        "comprehension_score",
        "comprehension_question_time_ms",
        "reading_time_ms",
        "trial_duration_ms",
        "data_loss_ratio",
        "blink_ratio",
        "validation_before_start_dva",
    }
    for trial in trials:
        assert expected_fields.issubset(trial)

    by_key = {(t["trial_number"], t["is_practice"]): t for t in trials}
    assert by_key[(1, False)]["trial_duration_ms"] == 3000.0
    assert by_key[(2, False)]["trial_duration_ms"] == 3000.0
    assert by_key[(1, True)]["trial_duration_ms"] == 400.0
    assert by_key[(1, False)]["data_loss_ratio"] == 0.01
    assert by_key[(2, False)]["data_loss_ratio"] == 0.02
    assert by_key[(1, True)]["data_loss_ratio"] == 0.03
    assert by_key[(1, False)]["blink_ratio"] == 0.1
    assert by_key[(2, False)]["blink_ratio"] == 0.2
    assert by_key[(1, True)]["blink_ratio"] == 0.3
    assert by_key[(1, False)]["validation_before_start_dva"] == 0.4
    assert by_key[(2, False)]["validation_before_start_dva"] == 0.6
    assert by_key[(1, True)]["validation_before_start_dva"] == 0.2


def test_trials_extended_fields_unknown_without_sources(tmp_path: Path) -> None:
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)
    sess.stimulus_start_end_ts = "unknown"

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    assert isinstance(trials, list)
    for trial in trials:
        assert trial["trial_duration_ms"] == "unknown"
        assert trial["data_loss_ratio"] == "unknown"
        assert trial["blink_ratio"] == "unknown"
        assert trial["validation_before_start_dva"] == "unknown"


def test_practice_trial_extended_fields_use_matching_entry(tmp_path: Path) -> None:
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)
    sess.validations = pl.DataFrame({"time": [50.0], "accuracy_avg": [0.35]})
    sess._per_trial_data_loss = pl.DataFrame(
        {
            "trial": ["PRACTICE_trial_1"],
            "stimulus": ["Enc_WikiMoon"],
            "data_loss_ratio": [0.25],
        }
    )

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    practice = next(t for t in trials if t["is_practice"])
    experiment = next(t for t in trials if not t["is_practice"])

    assert practice["trial_duration_ms"] == 400.0
    assert practice["data_loss_ratio"] == 0.25
    assert practice["blink_ratio"] == "unknown"
    assert practice["validation_before_start_dva"] == 0.35
    assert experiment["trial_duration_ms"] == 3000.0
    assert experiment["data_loss_ratio"] == "unknown"
    assert experiment["validation_before_start_dva"] == "unknown"


def test_trials_extended_fields_from_sanity_check_tsv(tmp_path: Path) -> None:
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)
    report = (
        tmp_path / "sanity_checks" / "001_EN_UK_1_ET1" / "001_EN_UK_1_ET1_EN_report.md"
    )
    report.parent.mkdir(parents=True)
    pl.DataFrame(
        {
            "trial": ["trial_1", "trial_2"],
            "stimulus": ["Lit_MagicMountain", "Lit_Alchemist"],
            "data_loss_ratio": [0.04, 0.05],
            "blink_loss_ratio": [0.06, 0.07],
            "blink_duration_ms": [100.0, 200.0],
            "trial_duration_ms": [3000.0, 3000.0],
        }
    ).write_csv(
        report.parent / "per_trial_data_loss_001_EN_UK_1_ET1.tsv", separator="\t"
    )
    sess.sanity_report_path = report

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    by_key = {(t["trial_number"], t["is_practice"]): t for t in trials}
    assert by_key[(1, False)]["data_loss_ratio"] == 0.04
    assert by_key[(1, False)]["blink_ratio"] == 0.06
    assert by_key[(2, False)]["data_loss_ratio"] == 0.05
    assert by_key[(2, False)]["blink_ratio"] == 0.07
    assert by_key[(1, True)]["data_loss_ratio"] == "unknown"
    assert by_key[(1, True)]["blink_ratio"] == "unknown"


def test_validation_before_start_requires_inter_trial_interval() -> None:
    """A stale validation from before the previous trial is not reused."""
    sess = _make_session()
    sess.stimulus_start_end_ts = [
        {"trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
        {"trial": "trial_2", "start_ts": 5000.0, "stop_ts": 8000.0},
    ]
    # The only validation happens during trial 1.
    sess.validations = pl.DataFrame({"time": [3000.0], "accuracy_avg": [0.3]})

    scores = sess._validation_before_trial_start(sess._trial_time_spans())

    assert scores == {}


def test_trials_unknown_for_empty_answers(tmp_path: Path) -> None:
    answers_dir = tmp_path / "comp_answers" / "001_EN_UK_1_ET1"
    answers_dir.mkdir(parents=True)
    pl.DataFrame(
        schema={
            "trial": pl.Utf8,
            "stimulus": pl.Utf8,
            "stimulus_id": pl.Int64,
            "is_correct": pl.Boolean,
        }
    ).write_csv(answers_dir / "001_EN_UK_1_ET1_answers.csv")
    sess = _trial_sess(answers_dir)

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    assert trials == "unknown"


def test_calibration_quality_aggregation(tmp_path: Path) -> None:
    asc = tmp_path / "session.asc"
    sess = _make_session()
    sess.asc_path = asc

    asc.write_text(
        "MSG\t1 !CAL CALIBRATION HV9 L LEFT    GOOD \n"
        "MSG\t2 !CAL CALIBRATION HV9 R RIGHT   GOOD \n",
        encoding="utf-8",
    )
    assert sess._compute_calibration_quality() == "GOOD"

    asc.write_text("MSG\t1 !CAL CALIBRATION HV9 R RIGHT  FAILED\n", encoding="utf-8")
    assert sess._compute_calibration_quality() == "FAILED"

    asc.write_text(
        "MSG\t1 !CAL CALIBRATION HV9 L LEFT  GOOD\n"
        "MSG\t2 !CAL CALIBRATION HV9 R RIGHT FAILED\n",
        encoding="utf-8",
    )
    assert sess._compute_calibration_quality() == "MIXED"


def test_calibration_quality_unknown_without_asc(tmp_path: Path) -> None:
    sess = _make_session()
    assert sess._compute_calibration_quality() == "unknown"

    sess.asc_path = tmp_path / "missing.asc"
    assert sess._compute_calibration_quality() == "unknown"


def test_overview_includes_calibration_quality(tmp_path: Path) -> None:
    asc = tmp_path / "session.asc"
    asc.write_text("MSG\t1 !CAL CALIBRATION HV9 L LEFT GOOD\n", encoding="utf-8")

    sess = _sess_with_validation_data()
    sess.asc_path = asc
    cal = sess.create_overview()["calibration_validation"]

    assert cal["calibration_quality"] == "GOOD"


def _eyelink_filters_from_asc(tmp_path: Path, content: str) -> dict[str, list[int]]:
    asc = tmp_path / "session.asc"
    asc.write_text(content, encoding="utf-8")
    sess = _make_session()
    sess.asc_path = asc
    return sess.create_overview()["technical_setup"]["eyelink_filters"]


def test_eyelink_filters_deduplicates_repeated_values(tmp_path: Path) -> None:
    filters = _eyelink_filters_from_asc(
        tmp_path,
        "EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2\n"
        "SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2\n"
        "EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2\n"
        "SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2\n",
    )

    assert filters == {"events": [2], "samples": [2]}


def test_eyelink_filters_sorts_distinct_values(tmp_path: Path) -> None:
    filters = _eyelink_filters_from_asc(
        tmp_path,
        "EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2\n"
        "SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t1\n"
        "EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t1\n"
        "SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t0\n",
    )

    assert filters == {"events": [1, 2], "samples": [0, 1]}


def test_eyelink_filters_empty_without_asc(tmp_path: Path) -> None:
    expected = {"events": [], "samples": []}
    sess = _make_session()

    assert sess.create_overview()["technical_setup"]["eyelink_filters"] == expected

    sess.asc_path = tmp_path / "missing.asc"
    assert sess.create_overview()["technical_setup"]["eyelink_filters"] == expected


def test_eyelink_filters_empty_without_filter_lines(tmp_path: Path) -> None:
    filters = _eyelink_filters_from_asc(
        tmp_path,
        "EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\n"
        "SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\n"
        "START\t1000\tLEFT\tSAMPLES\tEVENTS\n",
    )

    assert filters == {"events": [], "samples": []}


def test_eyelink_filters_malformed_value_does_not_crash(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("WARNING"):
        filters = _eyelink_filters_from_asc(
            tmp_path,
            "EVENTS\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\t2\n"
            "SAMPLES\tGAZE\tRIGHT\tRATE\t1000.00\tTRACKING\tCR\tFILTER\ttwo\n",
        )

    assert filters == {"events": [2], "samples": []}
    assert "FILTER value 'two'" in caplog.text


def test_quality_fields_from_messages() -> None:
    sess = _sess_with_validation_data()
    sess.asc_path = "unknown"
    sess.messages = pl.DataFrame(
        {
            "time": [1, 2, 3, 4, 5],
            "content": [
                "!CAL CALIBRATION HV9 L LEFT GOOD",
                "!CAL CALIBRATION HV9 R RIGHT FAILED",
                "!CAL VALIDATION HV9 L LEFT GOOD ERROR 0.13 avg. 0.60 max",
                "!CAL VALIDATION HV9 R RIGHT POOR ERROR 0.66 avg. 3.03 max",
                "!CAL VALIDATION L ABORTED",
            ],
        }
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["calibration_quality"] == "MIXED"
    assert cal["validation_quality"] == "POOR"
    assert cal["num_aborted_validations"] == 1


def test_validation_quality_all_aborted() -> None:
    sess = _sess_with_validation_data()
    sess.asc_path = "unknown"
    sess.messages = pl.DataFrame(
        {
            "time": [1, 2],
            "content": [
                "!CAL VALIDATION L ABORTED",
                "!CAL VALIDATION R ABORTED",
            ],
        }
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["validation_quality"] == "ABORTED"
    assert cal["num_aborted_validations"] == 2


def test_validation_quality_unknown_without_quality_lines() -> None:
    sess = _sess_with_validation_data()
    sess.asc_path = "unknown"

    cal = sess.create_overview()["calibration_validation"]

    assert cal["validation_quality"] == "unknown"
    assert cal["num_aborted_validations"] == 0


def test_quality_lines_fall_back_to_asc(tmp_path: Path) -> None:
    asc = tmp_path / "session.asc"
    asc.write_text(
        "MSG\t1 !CAL CALIBRATION HV9 L LEFT GOOD\n"
        "MSG\t2 !CAL VALIDATION HV9 L LEFT FAIR ERROR 0.63 avg. 1.59 max\n",
        encoding="utf-8",
    )

    sess = _sess_with_validation_data()
    sess.asc_path = asc
    sess.messages = pl.DataFrame(
        {"time": [1], "content": ["start_recording_trial_1"]},
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["calibration_quality"] == "GOOD"
    assert cal["validation_quality"] == "FAIR"


# --- Final validation score ---


def _final_validation_session(
    *,
    message_time: float | None = 450.0,
    final_trial_stop: float = 400.0,
    validation_times: list[float] | None = None,
    accuracy: list[float | None] | None = None,
    calibration_times: list[float] | None = None,
) -> Session:
    """Build a session with an experiment trial, final_validation, and validations."""
    sess = _make_session()
    _seed_metadata(sess)
    sess.stimulus_start_end_ts = [
        {
            "stimulus": "practice",
            "trial": "PRACTICE_trial_1",
            "start_ts": 50.0,
            "stop_ts": 100.0,
        },
        {"stimulus": "a", "trial": "trial_1", "start_ts": 200.0, "stop_ts": 300.0},
        {
            "stimulus": "b",
            "trial": "trial_2",
            "start_ts": 320.0,
            "stop_ts": final_trial_stop,
        },
    ]

    times = [600.0]
    contents = ["show_final_screen"]
    if message_time is not None:
        times.insert(0, message_time)
        contents.insert(0, "final_validation")
    sess.messages = pl.DataFrame({"time": times, "content": contents})

    if validation_times is not None:
        accuracy = accuracy if accuracy is not None else [0.5] * len(validation_times)
        sess.validations = pl.DataFrame(
            {
                "time": validation_times,
                "accuracy_avg": accuracy,
                "accuracy_max": [0.7] * len(validation_times),
                "eye": ["right"] * len(validation_times),
            }
        )

    sess.calibrations = pl.DataFrame({"time": calibration_times or [50.0]})
    return sess


def test_final_validation_score_after_final_trial() -> None:
    sess = _final_validation_session(
        message_time=450.0,
        final_trial_stop=400.0,
        validation_times=[300.0, 480.0],
        accuracy=[0.9, 0.57],
        calibration_times=[50.0],
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == 0.57


def test_final_validation_score_averages_eyes_of_final_validation() -> None:
    sess = _final_validation_session(
        message_time=450.0,
        validation_times=[480.0, 480.0],
        accuracy=[0.5, 0.7],
    )
    sess.validations = sess.validations.with_columns(
        pl.Series("eye", ["left", "right"])
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == 0.6


def test_final_validation_score_unknown_without_final_validation_message() -> None:
    sess = _final_validation_session(
        message_time=None,
        validation_times=[480.0],
        accuracy=[0.57],
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == "unknown"


def test_final_validation_score_unknown_with_calibration_between() -> None:
    sess = _final_validation_session(
        message_time=450.0,
        final_trial_stop=400.0,
        validation_times=[480.0],
        accuracy=[0.57],
        calibration_times=[50.0, 420.0],
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == "unknown"


def test_final_validation_score_unknown_without_validations() -> None:
    sess = _final_validation_session(message_time=450.0, validation_times=None)

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == "unknown"


def test_final_validation_score_unknown_without_validation_score() -> None:
    sess = _final_validation_session(
        message_time=450.0,
        validation_times=[480.0],
        accuracy=[None],
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == "unknown"


def test_final_validation_score_unknown_when_validation_precedes_message() -> None:
    sess = _final_validation_session(
        message_time=450.0,
        validation_times=[300.0],
        accuracy=[0.57],
    )

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == "unknown"


def test_final_validation_score_unknown_without_final_trial_end() -> None:
    sess = _final_validation_session(
        message_time=450.0,
        validation_times=[480.0],
        accuracy=[0.57],
    )
    sess.stimulus_start_end_ts = "unknown"

    cal = sess.create_overview()["calibration_validation"]

    assert cal["final_validation_score_dva"] == "unknown"


# --- Mount short name ---


def test_mount_short_name_present() -> None:
    sess = _sess_with_validation_data()
    sess.pm_gaze_metadata["mount_configuration"]["short_name"] = "BTABLER"

    tech = sess.create_overview()["technical_setup"]

    assert tech["mount_short_name"] == "BTABLER"
    assert tech["mount_type"] == "Desktop"


def test_mount_short_name_absent() -> None:
    sess = _sess_with_validation_data()

    tech = sess.create_overview()["technical_setup"]

    assert tech["mount_short_name"] is None


# --- Dominant eye ---


def _doc(rows: list[dict]) -> ExperimenterDoc:
    return ExperimenterDoc(pl.DataFrame(rows), None, None, None)


def _dominant_eye_row(**overrides) -> dict:
    row = {
        "session_id": "001_EN_UK_1_ET1",
        "participant_id": 1,
        "dominant_eye_test": "yes",
        "dominant_eye": "left",
        "tracked_eye": "monocular right eye",
    }
    row.update(overrides)
    return row


def test_dominant_eye_full_sid_match() -> None:
    sess = _make_session()
    doc = _doc([_dominant_eye_row(dominant_eye="right")])

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "right"
    assert tech["dominant_eye_test"] is True


@pytest.mark.parametrize("sheet_session_id", ["1", "ET1", "et1"])
def test_dominant_eye_short_sid_match(sheet_session_id: str) -> None:
    sess = _make_session()
    doc = _doc([_dominant_eye_row(session_id=sheet_session_id)])

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "left"
    assert tech["dominant_eye_test"] is True


def test_dominant_eye_participant_fallback_when_session_id_missing() -> None:
    sess = _make_session()
    doc = _doc(
        [
            _dominant_eye_row(
                session_id=None,
                participant_id=1,
                dominant_eye="right",
            )
        ]
    )

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "right"
    assert tech["dominant_eye_test"] is True


def test_dominant_eye_case_and_whitespace_normalization() -> None:
    sess = _make_session()
    doc = _doc(
        [
            _dominant_eye_row(
                session_id="  001_en_uk_1_et1  ",
                dominant_eye="  LEFT  ",
                dominant_eye_test=" YES ",
            )
        ]
    )

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "left"
    assert tech["dominant_eye_test"] is True


def test_dominant_eye_both_normalization() -> None:
    sess = _make_session()
    doc = _doc([_dominant_eye_row(dominant_eye="Binocular")])

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "both"


def test_dominant_eye_short_sid_requires_matching_participant() -> None:
    sess = _make_session()
    doc = _doc([_dominant_eye_row(session_id="1", participant_id=2)])

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


def test_dominant_eye_missing_values_are_unknown() -> None:
    sess = _make_session()
    doc = _doc(
        [
            _dominant_eye_row(
                dominant_eye=None,
                dominant_eye_test=None,
            )
        ]
    )

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


def test_dominant_eye_missing_sheet_is_unknown() -> None:
    sess = _make_session()

    tech = sess.create_overview()["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


def test_dominant_eye_missing_column_is_unknown() -> None:
    sess = _make_session()
    doc = _doc([{"session_id": "001_EN_UK_1_ET1", "participant_id": 1}])

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


def test_dominant_eye_duplicate_rows_warn_and_disagree_are_unknown() -> None:
    sess = _make_session()
    doc = _doc(
        [
            _dominant_eye_row(dominant_eye="left", dominant_eye_test="yes"),
            _dominant_eye_row(dominant_eye="right", dominant_eye_test="no"),
        ]
    )

    with pytest.warns(UserWarning, match="2 rows for session"):
        tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


def test_dominant_eye_duplicate_agreeing_rows_warn_and_use_value() -> None:
    sess = _make_session()
    doc = _doc(
        [
            _dominant_eye_row(dominant_eye="right", dominant_eye_test="yes"),
            _dominant_eye_row(dominant_eye="right", dominant_eye_test="yes"),
        ]
    )

    with pytest.warns(UserWarning, match="2 rows for session"):
        tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "right"
    assert tech["dominant_eye_test"] is True


def test_dominant_eye_duplicate_missing_and_value_are_unknown() -> None:
    sess = _make_session()
    doc = _doc(
        [
            _dominant_eye_row(dominant_eye="left", dominant_eye_test="yes"),
            _dominant_eye_row(dominant_eye=None, dominant_eye_test=None),
        ]
    )

    with pytest.warns(UserWarning, match="2 rows for session"):
        tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


@pytest.mark.parametrize(
    ("sheet_value", "expected"),
    [("yes", True), ("Yes", True), ("no", False), ("No", False)],
)
def test_dominant_eye_test_yes_no(sheet_value: str, expected: bool) -> None:
    sess = _make_session()
    doc = _doc([_dominant_eye_row(dominant_eye_test=sheet_value)])

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye_test"] is expected
    if not expected:
        assert tech["dominant_eye"] == "unknown"


def test_dominant_eye_not_inferred_from_tracked_eye() -> None:
    sess = _sess_with_validation_data()
    assert sess.pm_gaze_metadata["tracked_eye"] == "R"
    doc = _doc(
        [
            _dominant_eye_row(
                dominant_eye=None,
                dominant_eye_test=None,
                tracked_eye="monocular right eye",
            )
        ]
    )

    tech = sess.create_overview(doc)["technical_setup"]

    assert tech["dominant_eye"] == "unknown"
    assert tech["dominant_eye_test"] == "unknown"


def _question_order_csv(session_path: Path, versions: list[int] | None = None) -> None:
    logfiles = session_path / "logfiles"
    logfiles.mkdir(parents=True)
    versions = versions or [6, 7, 8]
    rows = [
        (
            "question_order_version,local_question_1,local_question_2,"
            "bridging_question_1,bridging_question_2,"
            "global_question_1,global_question_2"
        )
    ]
    for index, version in enumerate(versions):
        rows.append(f"{version},12,11,21,22,{32 - index},31")
    (logfiles / "question_order_versions.csv").write_text(
        "\n".join(rows) + "\n",
        encoding="utf-8",
    )


def _question_order_trials(tmp_path: Path, versions: list[int] | None = None):
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)
    sess.session_folder_path = tmp_path
    sess.stimuli_trial_mapping = {
        "PRACTICE_trial_1": "Enc_WikiMoon",
        "trial_1": "Lit_MagicMountain",
        "trial_2": "Lit_Alchemist",
    }
    _question_order_csv(tmp_path, versions)
    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]
    return {(t["trial_number"], t["is_practice"]): t for t in trials}


def test_question_order_is_attached_to_trials(tmp_path: Path) -> None:
    by_key = _question_order_trials(tmp_path)

    assert by_key[(1, False)]["question_order_version"] == 7
    assert by_key[(1, False)]["question_order"] == {
        "local": [12, 11],
        "bridging": [21, 22],
        "global": [31, 31],
    }
    assert by_key[(1, True)]["question_order_version"] == 6


def test_question_order_missing_csv_is_none_on_trials(tmp_path: Path) -> None:
    answers_dir = _write_answers(tmp_path, _ANSWERS_ROWS)
    sess = _trial_sess(answers_dir)
    sess.session_folder_path = tmp_path
    sess.stimuli_trial_mapping = {
        "PRACTICE_trial_1": "Enc_WikiMoon",
        "trial_1": "Lit_MagicMountain",
        "trial_2": "Lit_Alchemist",
    }

    with patch.object(
        Session,
        "sid",
        property(lambda self: _FakeSid(answers_dir)),
    ):
        trials = sess.create_overview()["trials"]

    assert all(trial["question_order"] is None for trial in trials)
    assert all(trial["question_order_version"] is None for trial in trials)


def test_question_order_partial_records_do_not_drop_trials(tmp_path: Path) -> None:
    by_key = _question_order_trials(tmp_path, versions=[6])

    assert len(by_key) == 3
    assert by_key[(1, True)]["question_order_version"] == 6
    assert by_key[(1, False)]["question_order"] is None
    assert by_key[(2, False)]["question_order"] is None


def test_break_fields_from_messages() -> None:
    sess = _make_session()
    sess.messages = pl.DataFrame(
        {
            "time": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0],
            "content": [
                "optional_break",
                "optional_break_end",
                "optional_break_duration: 1500",
                "optional_break",
                "optional_break_end",
                "obligatory_break",
                "obligatory_break_duration: 2500",
            ],
        }
    )

    proc = sess.create_overview()["experiment_procedure"]

    assert proc["obligatory_break_made"] is True
    assert proc["num_optional_breaks_made"] == 2
    assert proc["total_break_time_s"] == 4.0


def test_break_fields_no_breaks_in_messages() -> None:
    sess = _make_session()
    sess.messages = pl.DataFrame({"time": [1.0], "content": ["reading starts"]})

    proc = sess.create_overview()["experiment_procedure"]

    assert proc["obligatory_break_made"] is False
    assert proc["num_optional_breaks_made"] == 0
    assert proc["total_break_time_s"] == 0.0


def test_break_fields_without_messages_are_unknown() -> None:
    sess = _make_session()

    proc = sess.create_overview()["experiment_procedure"]

    assert proc["obligatory_break_made"] == "unknown"
    assert proc["num_optional_breaks_made"] == "unknown"
    assert proc["total_break_time_s"] == "unknown"


def test_break_fields_without_duration_are_unknown() -> None:
    sess = _make_session()
    sess.messages = pl.DataFrame({"time": [1.0], "content": ["obligatory_break"]})

    proc = sess.create_overview()["experiment_procedure"]

    assert proc["obligatory_break_made"] is True
    assert proc["total_break_time_s"] == "unknown"


def test_dominant_eye_kept_when_it_differs_from_tracked_eye() -> None:
    sess = _sess_with_validation_data()
    doc = _doc([_dominant_eye_row(dominant_eye="left")])

    overview = sess.create_overview(doc)

    assert overview["technical_setup"]["dominant_eye"] == "left"
    assert overview["tracking"]["tracked_eye"] == "R"
