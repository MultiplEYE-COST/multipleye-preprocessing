from pathlib import Path
from unittest.mock import patch

import polars as pl

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
        name_eye_tracker="test",
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


def test_create_overview_includes_new_fields() -> None:
    validations = pl.DataFrame(
        {
            "time": [100.0, 200.0, 300.0],
            "accuracy_avg": [0.2, 0.35, 0.5],
            "accuracy_max": [0.3, 0.4, 0.6],
            "eye": ["right", "right", "right"],
        }
    )
    calibrations = pl.DataFrame({"time": [50.0, 150.0]})
    sess = _make_session()
    sess.validations = validations
    sess.calibrations = calibrations
    _seed_metadata(sess)

    overview = sess.create_overview()

    tracking = overview["Tracking"]
    assert tracking["tracked_eye"] == "R"
    assert tracking["tracked_eye_consistent"] is True
    cal = overview["Calibration_validation"]
    assert cal["num_good_validations"] == 1
    assert cal["num_moderate_validations"] == 1
    assert cal["num_bad_validations"] == 1
    dq = overview["Data_quality"]
    assert "total_data_loss_ratio" in dq
    assert dq["total_data_loss_ratio"] is None
    assert "blink_loss_ratio" in dq
    assert dq["blink_loss_ratio"] is None


def test_create_overview_includes_measure_based_data_loss() -> None:
    sess = _make_session()
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )
    _seed_metadata(sess)
    sess._measure_total_data_loss_ratio = 0.015
    sess._measure_blink_loss_ratio = 0.008

    overview = sess.create_overview()

    dq = overview["Data_quality"]
    assert dq["total_data_loss_ratio"] == 0.015
    assert dq["blink_loss_ratio"] == 0.008


def test_tracked_eye_inconsistent_when_eye_changes() -> None:
    validations = pl.DataFrame(
        {
            "time": [100.0, 200.0],
            "accuracy_avg": [0.2, 0.2],
            "accuracy_max": [0.3, 0.3],
            "eye": ["right", "left"],
        }
    )
    calibrations = pl.DataFrame({"time": [50.0]})
    sess = _make_session()
    sess.validations = validations
    sess.calibrations = calibrations
    _seed_metadata(sess)

    overview = sess.create_overview()

    tracking = overview["Tracking"]
    assert tracking["tracked_eye"] == "R"
    assert tracking["tracked_eye_consistent"] is False


def test_sections_are_present() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )

    overview = sess.create_overview()

    assert list(overview.keys()) == [
        "Administrative",
        "Technical_setup",
        "Tracking",
        "Calibration_validation",
        "Data_quality",
        "Experiment_procedure",
        "Comprehension",
        "Data_formats",
    ]


def test_technical_setup_from_lab_config() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )

    overview = sess.create_overview()
    tech = overview["Technical_setup"]

    assert tech["Eye_tracker_name"] == "test"
    assert tech["Sampling_frequency_hz"] == 1000.0
    assert tech["Mount_type"] == "Desktop"
    assert tech["Head_stabilization"] == "stabilized"
    assert tech["Eyes_recorded"] == "binocular / monocular"
    assert tech["Pupil_data_type"] == "AREA"
    assert tech["Screen_resolution_width_px"] == 1920
    assert tech["Screen_resolution_height_px"] == 1080
    assert tech["Screen_distance_cm"] == 60.0
    assert tech["Image_size_width_cm"] == 38.0


def test_avg_validation_error_computed_from_validations() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0, 200.0, 300.0],
            "accuracy_avg": [0.2, 0.3, 0.4],
            "accuracy_max": [0.3, 0.4, 0.5],
            "eye": ["right", "right", "right"],
        }
    )

    overview = sess.create_overview()
    cal = overview["Calibration_validation"]

    assert cal["avg_validation_error"] == 0.3
    assert cal["num_calibrations"] == 1
    assert cal["num_validations"] == 3


def test_comprehension_scores_read_from_answers_csv(tmp_path: Path) -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )

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
        comp = overview["Comprehension"]

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
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )
    sess.messages = pl.DataFrame(
        {"time": [1000.0, 2000.0, 60000.0], "content": ["a", "b", "c"]}
    )

    overview = sess.create_overview()
    proc = overview["Experiment_procedure"]

    assert proc["total_session_duration"] == 59.0


def test_reading_time_from_stimulus_start_end_ts() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )
    sess.stimulus_start_end_ts = [
        {"stimulus": "a", "trial": "trial_1", "start_ts": 1000.0, "stop_ts": 4000.0},
        {"stimulus": "b", "trial": "trial_2", "start_ts": 5000.0, "stop_ts": 7000.0},
    ]

    overview = sess.create_overview()
    proc = overview["Experiment_procedure"]

    assert proc["total_reading_time"] == 5.0


def test_data_formats_section() -> None:
    sess = _make_session()
    _seed_metadata(sess)
    sess.calibrations = pl.DataFrame({"time": [50.0]})
    sess.validations = pl.DataFrame(
        {
            "time": [100.0],
            "accuracy_avg": [0.2],
            "accuracy_max": [0.3],
            "eye": ["right"],
        }
    )
    sess.raw_data = True
    sess.reading_measures = True

    overview = sess.create_overview()
    formats = overview["Data_formats"]

    assert formats["raw_data"] is True
    assert formats["fixations"] is False
    assert formats["reading_measures"] is True
    assert formats["answers"] is False
