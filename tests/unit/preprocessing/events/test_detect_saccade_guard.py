import logging

import polars as pl
import pytest

import preprocessing.events.detect as detect_module
from preprocessing import settings


class _GuardFakeGaze:
    def __init__(self, samples: pl.DataFrame):
        self.samples = samples
        self.trial_columns = ["trial", "stimulus", "page"]
        self.detect_calls = []

    def detect(self, method, **kwargs):
        self.detect_calls.append((method, kwargs, self.samples.clone()))


@pytest.fixture(autouse=True)
def _settings(monkeypatch):
    monkeypatch.setattr(settings, "SACCADE_METHOD", "microsaccades")
    monkeypatch.setattr(settings, "SACCADE_MINIMUM_DURATION", 6)
    monkeypatch.setattr(settings, "SACCADE_THRESHOLD_FACTOR", 6.0)
    monkeypatch.setattr(
        detect_module,
        "compute_event_properties",
        lambda *args, **kwargs: None,
    )


def _samples(
    trial: list[str],
    page: list[str],
    velocity: list[list[float]],
) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "trial": trial,
            "stimulus": ["stimulus_1"] * len(trial),
            "page": page,
            "velocity": velocity,
            "session": ["001_TEST"] * len(trial),
        }
    )


def test_detect_saccades_skips_one_sample_group(caplog):
    gaze = _GuardFakeGaze(
        _samples(
            trial=["trial_1", "trial_1", "trial_1", "trial_2"],
            page=["page_1", "page_1", "page_1", "subject_difficulty_screen"],
            velocity=[
                [0.1, 0.1],
                [0.2, 0.2],
                [0.3, 0.3],
                [0.5, 0.5],
            ],
        )
    )

    with caplog.at_level(logging.WARNING, logger="preprocessing.events.detect"):
        detect_module.detect_saccades(gaze)

    assert len(gaze.detect_calls) == 1
    method, _, detected_samples = gaze.detect_calls[0]
    assert method == "microsaccades"
    assert detected_samples.height == 3
    assert detected_samples["page"].unique().to_list() == ["page_1"]
    assert gaze.samples.height == 4
    assert "Skipping saccade detection for 1 trial/page group" in caplog.text
    assert "001_TEST" in caplog.text
    assert "subject_difficulty_screen" in caplog.text
    assert "fewer_than_2_valid_samples" in caplog.text


def test_detect_saccades_skips_zero_variance_group(caplog):
    gaze = _GuardFakeGaze(
        _samples(
            trial=["trial_1", "trial_1", "trial_2", "trial_2"],
            page=["page_1", "page_1", "page_2", "page_2"],
            velocity=[
                [0.1, 0.1],
                [0.2, 0.2],
                [0.5, 0.5],
                [0.5, 0.5],
            ],
        )
    )

    with caplog.at_level(logging.WARNING, logger="preprocessing.events.detect"):
        detect_module.detect_saccades(gaze)

    assert len(gaze.detect_calls) == 1
    _, _, detected_samples = gaze.detect_calls[0]
    assert detected_samples.height == 2
    assert detected_samples["page"].unique().to_list() == ["page_1"]
    assert "Skipping saccade detection for 1 trial/page group" in caplog.text
    assert "page_2" in caplog.text
    assert "zero_variance" in caplog.text


def test_detect_saccades_keeps_all_valid_groups():
    gaze = _GuardFakeGaze(
        _samples(
            trial=["trial_1", "trial_1", "trial_2", "trial_2"],
            page=["page_1", "page_1", "page_2", "page_2"],
            velocity=[
                [0.1, 0.1],
                [0.2, 0.2],
                [0.5, 0.5],
                [0.6, 0.6],
            ],
        )
    )

    detect_module.detect_saccades(gaze)

    assert len(gaze.detect_calls) == 1
    _, _, detected_samples = gaze.detect_calls[0]
    assert detected_samples.height == 4
    assert gaze.samples.height == 4


def test_detect_saccades_raises_if_all_groups_are_degenerate():
    gaze = _GuardFakeGaze(
        _samples(
            trial=["trial_1", "trial_2"],
            page=["page_1", "page_2"],
            velocity=[
                [0.1, 0.1],
                [0.5, 0.5],
            ],
        )
    )

    with pytest.raises(ValueError, match="No valid saccade groups remain"):
        detect_module.detect_saccades(gaze)

    assert gaze.detect_calls == []


def test_detect_saccades_restores_samples_when_detection_fails():
    class _RaisingGaze(_GuardFakeGaze):
        def detect(self, method, **kwargs):
            raise RuntimeError("detection failed")

    gaze = _RaisingGaze(
        _samples(
            trial=["trial_1", "trial_1", "trial_2"],
            page=["page_1", "page_1", "page_2"],
            velocity=[
                [0.1, 0.1],
                [0.2, 0.2],
                [0.5, 0.5],
            ],
        )
    )

    with pytest.raises(RuntimeError, match="detection failed"):
        detect_module.detect_saccades(gaze)

    assert gaze.samples.height == 3
