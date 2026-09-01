from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import yaml

from preprocessing.data_collection.session import Session
from preprocessing.data_collection.stimulus import LabConfig
from preprocessing.data_collection.trial import Trial


def _make_session():
    return Session(
        participant_id=1,
        language="en",
        country="US",
        city="Nowhere",
        lab_number=1,
        session_identifier="S1",
        is_pilot=False,
        lab_config=SimpleNamespace(sampling_frequency_hz=500),
    )


def test_from_yaml_parses_lab_config_and_trials_and_calls_load_stimuli(
    tmp_path, monkeypatch
):
    yaml_path = tmp_path / "session.yaml"
    content = {
        "administrative": {
            "participant_id": 1,
            "language": "English",
            "country": "USA",
            "city": "TestCity",
            "lab_number": 2,
            "session_identifier": "S1",
            "is_pilot": False,
        },
        "technical_setup": {
            "screen_resolution_width_px": 1920,
            "screen_resolution_height_px": 1080,
            "screen_size_width_cm": 47.5,
            "screen_size_height_cm": 26.7,
            "screen_distance_cm": 60,
            "image_resolution_width_px": 800,
            "image_resolution_height_px": 600,
            "image_size_width_cm": 20,
            "image_size_height_cm": 15,
            "eye_tracker_name": "TestTracker",
            "mount_type": "desktop",
            "head_stabilization": "chinrest",
            "eyes_recorded": "monocular",
        },
        "stimuli": {
            "stimulus_folder_name": "stimuli_folder",
            "randomization_version": 1,
            "completed_stimuli_ids": [1],
            "stimulus_trial_mapping": {"1": "stimA"},
        },
        "trials": [
            {
                "trial_number": 1,
                "stimulus_id": 1,
                "status": "completed",
                "comprehension_question_time_ms": 100535.0,
                "comprehension_score": 0.333,
                "is_practice": "false",
                "num_questions": 6,
                "reading_time_ms": 212147.0,
                "stimulus_name": "StimA",
            }
        ],
    }
    yaml_path.write_text(yaml.safe_dump(content), encoding="utf8")
    # avoid having to load actual stimuli

    stimuli = None

    def fake_load(self, p):
        nonlocal stimuli
        stimuli = p

    monkeypatch.setattr(Session, "load_session_stimuli", fake_load)

    session = Session.from_yaml(yaml_path, tmp_path)

    assert stimuli is not None
    assert session.lab_config.name_eye_tracker == "TestTracker"
    assert session.session_identifier == "S1"
    assert session.mount_type == "desktop"
    assert isinstance(session.trials, list)
    assert session.dataset_dir == Path(tmp_path)


def test_from_yaml_without_technical_setup_raises(tmp_path):
    yaml_path = tmp_path / "session_no_tech.yaml"
    content = {
        "administrative": {"participant_id": 1, "language": "English"},
        "trials": [],
    }
    yaml_path.write_text(yaml.safe_dump(content), encoding="utf8")

    with pytest.raises(NameError):
        Session.from_yaml(yaml_path, tmp_path)


def test_add_and_get_pm_metadata_full():
    s = _make_session()
    metadata = {
        "day": "01",
        "month": "02",
        "year": "2023",
        "time": "12:00:00",
        "tracked_eye": "left",
        "pupil_data_type": "diameter",
        "total_recording_duration_ms": "12345.6",
        "data_loss_ratio_blinks": 0.1,
        "data_loss_ratio": 0.2,
        "mount_configuration": {
            "mount_type": "chin",
            "head_stabilization": "chinrest",
            "eyes_recorded": "both",
        },
    }

    s.add_pm_metadata(metadata)

    # check fields set on the session
    assert s.recording_day_eyelink == "01"
    assert s.recording_month_eyelink == "02"
    assert s.recording_year_eyelink == "2023"
    assert s.recording_start_time_eyelink_hh_mm_ss == "12:00:00"
    assert s.tracked_eye == "left"
    assert s.pupil_data_type == "diameter"
    assert s.total_recording_duration_ms == float("12345.6")
    assert s.pm_blink_data_loss == 0.1
    assert s.pm_data_loss == 0.2
    assert s.mount_type == "chin"
    assert s.head_stabilization == "chinrest"
    assert s.eyes_recorded == "both"

    # check get_pm_metadata output
    md = s.get_pm_metadata()
    assert md["day"] == "01"
    assert md["month"] == "02"
    assert md["year"] == "2023"
    assert md["time"] == "12:00:00"
    assert md["tracked_eye"] == "left"
    assert md["total_recording_duration_ms"] == float("12345.6")
    assert md["sampling_rate"] == 500
    assert md["data_loss_ratio"] == 0.2
    assert md["data_loss_ratio_blinks"] == 0.1


def test_add_pm_metadata_non_dict():
    s = _make_session()
    s.recording_day_eyelink = "day"

    s.add_pm_metadata(None)

    assert s.recording_day_eyelink == "day"
    assert s.recording_month_eyelink == "unknown"


def test_session_yaml_round_trip(tmp_path: Path):
    session = Session(
        participant_id=18,
        language="SwissGerman",
        country="Switzerland",
        city="Basel",
        lab_number=1,
        session_identifier="003_BL_CH_1_ET1",
        is_pilot=False,
        lab_config=LabConfig(
            screen_resolution=(1920, 1080),
            screen_size_cm=(53.0, 30.0),
            screen_distance_cm=60.0,
            image_resolution=(1024, 768),
            image_size_cm=(30.0, 22.5),
            name_eye_tracker="EyeLink 1000 Plus",
        ),
        trials=[
            Trial(
                trial_number=1,
                stimulus_id=1,
                stimulus_name="EmBebbiSyJazz",
                is_practice=False,
                num_questions=3,
                comprehension_score=0.667,
                comprehension_question_time_ms=2500.0,
                reading_time_ms=12000.0,
                status="completed",
            )
        ],
        stimulus_folder_name="stimuli_v1",
        completed_stimuli_ids=[1],
        stimulus_order_ids=[1],
        stimulus_trial_mapping={"TRIAL_1": "EmBebbiSyJazz"},
        mount_type="desktop",
        head_stabilization="stabilized",
        eyes_recorded="monocular",
    )

    overview = session.create_overview()

    yaml_file = tmp_path / "session.yaml"
    with open(yaml_file, "w", encoding="utf8") as f:
        yaml.safe_dump(overview, f, sort_keys=False)

    with patch.object(
        Session, "load_session_stimuli", return_value=None
    ) as mocked_load:
        loaded = Session.from_yaml(yaml_file=yaml_file, dataset_dir=tmp_path)

    mocked_load.assert_called_once_with(tmp_path / session.stimulus_folder_name)

    assert loaded.participant_id == session.participant_id
    assert loaded.session_identifier == session.session_identifier
    assert loaded.language == session.language
    assert loaded.country == session.country
    assert loaded.city == session.city
    assert loaded.lab_number == session.lab_number
    assert loaded.stimulus_folder_name == session.stimulus_folder_name
    assert loaded.stimulus_trial_mapping == session.stimulus_trial_mapping
    assert loaded.mount_type == session.mount_type
    assert loaded.head_stabilization == session.head_stabilization
    assert loaded.eyes_recorded == session.eyes_recorded

    assert loaded.lab_config.name_eye_tracker == session.lab_config.name_eye_tracker
    assert loaded.lab_config.screen_resolution == session.lab_config.screen_resolution
    assert loaded.lab_config.screen_size_cm == session.lab_config.screen_size_cm
    assert loaded.lab_config.image_resolution == session.lab_config.image_resolution
    assert loaded.lab_config.image_size_cm == session.lab_config.image_size_cm

    assert isinstance(loaded.trials, list)
    assert len(loaded.trials) == 1
    assert loaded.trials[0].trial_number == 1
    assert loaded.trials[0].stimulus_name == "EmBebbiSyJazz"
    assert loaded.trials[0].status == "completed"
