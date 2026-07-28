import polars as pl
from pathlib import Path
from unittest.mock import MagicMock

from preprocessing.data_collection.session import Session


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


def _mock_lab_config():
    cfg = MagicMock()
    cfg.screen_resolution = (1920, 1080)
    cfg.screen_size_cm = (52.0, 32.0)
    cfg.screen_distance_cm = 60.0
    cfg.image_resolution = (1322, 980)
    cfg.image_size_cm = (38.0, 28.3)
    cfg.name_eye_tracker = "test"
    cfg.sampling_frequency_hz = 1000.0
    cfg.psychometric_tests = []
    return cfg


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
    sess.pm_gaze_metadata = {
        "tracked_eye": "R",
        "data_loss_ratio": 0.02,
        "mount_configuration": {"mount_type": "Desktop"},
        "pupil_data_type": "AREA",
    }
    sess.lab_config = _mock_lab_config()

    overview = sess.create_overview()

    assert overview["tracked_eye"] == "R"
    assert overview["tracked_eye_consistent"] is True
    assert overview["num_good_validations"] == 1
    assert overview["num_moderate_validations"] == 1
    assert overview["num_bad_validations"] == 1


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
    sess.pm_gaze_metadata = {
        "tracked_eye": "R",
        "data_loss_ratio": 0.01,
        "mount_configuration": {"mount_type": "Desktop"},
        "pupil_data_type": "AREA",
    }
    sess.lab_config = _mock_lab_config()

    overview = sess.create_overview()

    assert overview["tracked_eye"] == "R"
    assert overview["tracked_eye_consistent"] is False
