import pytest

import preprocessing.events.detect as detect_module
from preprocessing import settings


class _FakeGaze:
    def __init__(self):
        self.detect_calls = []

    def detect(self, method, **kwargs):
        self.detect_calls.append((method, kwargs))


def test_detect_fixations_uses_settings(monkeypatch):
    monkeypatch.setattr(settings, "FIXATION_METHOD", "idt")
    monkeypatch.setattr(settings, "FIXATION_MINIMUM_DURATION_MS", 250)
    monkeypatch.setattr(settings, "FIXATION_DISPERSION_THRESHOLD", 2.5)
    monkeypatch.setattr(settings, "FIXATION_INCLUDE_NAN", True)
    monkeypatch.setattr(detect_module, "compute_event_properties", lambda *a, **k: None)

    gaze = _FakeGaze()
    detect_module.detect_fixations(gaze)

    assert gaze.detect_calls == [
        (
            "idt",
            {
                "minimum_duration": 250,
                "include_nan": True,
                "name": "fixation",
                "dispersion_threshold": 2.5,
            },
        )
    ]


def test_detect_fixations_explicit_args_override_settings(monkeypatch):
    monkeypatch.setattr(settings, "FIXATION_METHOD", "idt")
    monkeypatch.setattr(settings, "FIXATION_MINIMUM_DURATION_MS", 250)
    monkeypatch.setattr(settings, "FIXATION_VELOCITY_THRESHOLD", 35.0)
    monkeypatch.setattr(detect_module, "compute_event_properties", lambda *a, **k: None)

    gaze = _FakeGaze()
    detect_module.detect_fixations(
        gaze, method="ivt", minimum_duration=50, velocity_threshold=15.0
    )

    assert gaze.detect_calls == [
        (
            "ivt",
            {
                "minimum_duration": 50,
                "include_nan": False,
                "name": "fixation",
                "velocity_threshold": 15.0,
            },
        )
    ]


def test_detect_fixations_rejects_unknown_method(monkeypatch):
    monkeypatch.setattr(detect_module, "compute_event_properties", lambda *a, **k: None)

    gaze = _FakeGaze()
    with pytest.raises(ValueError, match="Unsupported fixation detection method"):
        detect_module.detect_fixations(gaze, method="microsaccades")

    assert gaze.detect_calls == []


def test_detect_saccades_uses_settings(monkeypatch):
    monkeypatch.setattr(settings, "SACCADE_METHOD", "microsaccades")
    monkeypatch.setattr(settings, "SACCADE_MINIMUM_DURATION", 8)
    monkeypatch.setattr(settings, "SACCADE_THRESHOLD", "engbert2015")
    monkeypatch.setattr(settings, "SACCADE_THRESHOLD_FACTOR", 7.5)
    monkeypatch.setattr(settings, "SACCADE_MINIMUM_THRESHOLD", 1e-9)
    monkeypatch.setattr(settings, "SACCADE_INCLUDE_NAN", True)
    monkeypatch.setattr(detect_module, "compute_event_properties", lambda *a, **k: None)

    gaze = _FakeGaze()
    detect_module.detect_saccades(gaze)

    assert gaze.detect_calls == [
        (
            "microsaccades",
            {
                "minimum_duration": 8,
                "threshold": "engbert2015",
                "threshold_factor": 7.5,
                "minimum_threshold": 1e-9,
                "include_nan": True,
                "name": "saccade",
            },
        )
    ]


def test_detect_saccades_explicit_args_override_settings(monkeypatch):
    monkeypatch.setattr(settings, "SACCADE_METHOD", "microsaccades")
    monkeypatch.setattr(settings, "SACCADE_MINIMUM_DURATION", 8)
    monkeypatch.setattr(settings, "SACCADE_THRESHOLD", "engbert2015")
    monkeypatch.setattr(settings, "SACCADE_THRESHOLD_FACTOR", 7.5)
    monkeypatch.setattr(settings, "SACCADE_MINIMUM_THRESHOLD", 1e-9)
    monkeypatch.setattr(settings, "SACCADE_INCLUDE_NAN", True)
    monkeypatch.setattr(detect_module, "compute_event_properties", lambda *a, **k: None)

    gaze = _FakeGaze()
    detect_module.detect_saccades(
        gaze,
        minimum_duration=3,
        threshold_factor=4.0,
        threshold=[0.1, 0.2],
        minimum_threshold=1e-8,
        include_nan=False,
    )

    assert gaze.detect_calls == [
        (
            "microsaccades",
            {
                "minimum_duration": 3,
                "threshold": (0.1, 0.2),
                "threshold_factor": 4.0,
                "minimum_threshold": 1e-8,
                "include_nan": False,
                "name": "saccade",
            },
        )
    ]
