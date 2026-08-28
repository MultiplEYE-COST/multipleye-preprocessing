from pathlib import Path

import pytest
import yaml

from preprocessing.data_collection.session import Session


class DummyTrial:
    def __init__(self, **kwargs):
        self._data = kwargs


def test_from_yaml_parses_lab_config_and_trials_and_calls_load_stimuli(
    tmp_path, monkeypatch
):
    yaml_path = tmp_path / "session.yaml"
    content = {
        "Administrative": {
            "participant_id": 1,
            "language": "English",
            "country": "USA",
            "city": "TestCity",
            "lab_number": 2,
            "session_identifier": "S1",
            "is_pilot": False,
        },
        "Technical_setup": {
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
        "Stimuli": {
            "stimulus_folder_name": "stimuli_folder",
            "randomization_version": 1,
            "completed_stimuli_ids": [1],
            "stimulus_trial_mapping": {"1": "stimA"},
        },
        "Trials": [
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
        "Administrative": {"participant_id": 1, "language": "English"},
        "Trials": [],
    }
    yaml_path.write_text(yaml.safe_dump(content), encoding="utf8")

    with pytest.raises(NameError):
        Session.from_yaml(yaml_path, tmp_path)
