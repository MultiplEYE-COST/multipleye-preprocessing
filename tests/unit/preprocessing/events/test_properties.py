"""Tests for vectorized event property computation."""

import datetime as dt

import numpy as np
import polars as pl
import pymovements as pm
import pytest
from polars.testing import assert_frame_equal

from preprocessing.events.properties import (
    _convert_time_to_ms,
    _property_expression,
    compute_event_properties,
)


def _make_samples(
    n_trials: int = 2,
    events_per_trial: int = 40,
    fixation_length: int = 120,
    saccade_length: int = 8,
    n_velocity_components: int = 2,
) -> pl.DataFrame:
    """Build a synthetic gaze signal with clear fixation and saccade segments."""
    rng = np.random.default_rng(0)
    period = events_per_trial * (fixation_length + saccade_length)
    trial_frames = []

    for trial in range(n_trials):
        x = np.zeros(period)
        y = np.zeros(period)
        vx = np.zeros(period)
        vy = np.zeros(period)
        center_x = center_y = 0.0

        for event in range(events_per_trial):
            start = event * (fixation_length + saccade_length)
            fix_end = start + fixation_length
            x[start:fix_end] = center_x + rng.normal(0, 0.05, fixation_length)
            y[start:fix_end] = center_y + rng.normal(0, 0.05, fixation_length)
            vx[start:fix_end] = rng.normal(0, 1, fixation_length)
            vy[start:fix_end] = rng.normal(0, 1, fixation_length)

            for step in range(saccade_length):
                x[fix_end + step] = center_x + (step + 1) * 0.6
                y[fix_end + step] = center_y + (step + 1) * 0.2
                vx[fix_end + step] = rng.normal(60, 5)
                vy[fix_end + step] = rng.normal(25, 3)

            center_x = x[fix_end + saccade_length - 1]
            center_y = y[fix_end + saccade_length - 1]

        index = np.arange(period)
        frame = pl.DataFrame(
            {
                "time": index.astype(float),
                "trial": np.full(period, f"trial_{trial:02d}"),
                "position_x": x,
                "position_y": y,
                "pixel_x": x * 50,
                "pixel_y": y * 50,
                "velocity_x": vx,
                "velocity_y": vy,
            }
        )
        if n_velocity_components == 1:
            frame = frame.with_columns(
                pl.concat_list(["velocity_x", "velocity_y"]).alias("velocity")
            ).drop(["velocity_x", "velocity_y"])
        trial_frames.append(frame)

    return pl.concat(trial_frames)


def _make_gaze(**sample_kwargs) -> pm.Gaze:
    samples = _make_samples(**sample_kwargs)
    return pm.Gaze(
        samples,
        trial_columns=["trial"],
        position_columns=["position_x", "position_y"],
        pixel_columns=["pixel_x", "pixel_y"],
        velocity_columns=["velocity_x", "velocity_y"],
    )


def _reference_properties(
    gaze: pm.Gaze,
    event_name: str,
    properties: list[tuple[str, dict]],
) -> pl.DataFrame:
    """Compute properties with pymovements' EventSamplesProcessor as reference."""
    join_on = list(gaze.trial_columns) + ["name", "onset", "offset"]
    result = gaze.events.frame.filter(pl.col("name") == event_name).select(join_on)
    for prop_name, kwargs in properties:
        processor = pm.EventSamplesProcessor((prop_name, kwargs))
        new_props = processor.process(
            gaze.events.frame,
            gaze.samples,
            identifiers=gaze.trial_columns,
            name=event_name,
        )
        result = result.join(new_props, on=join_on, how="left", nulls_equal=True)
    return result


def _assert_properties_match(
    gaze: pm.Gaze,
    event_name: str,
    properties: list[tuple[str, dict]],
) -> None:
    join_on = list(gaze.trial_columns) + ["name", "onset", "offset"]
    prop_names = [name for name, _ in properties]
    reference = _reference_properties(gaze, event_name, properties).sort(join_on)
    actual = gaze.events.frame.filter(pl.col("name") == event_name).select(
        join_on + prop_names
    )
    actual = actual.sort(join_on)
    assert_frame_equal(actual, reference, check_exact=False, abs_tol=1e-9)


FIXATION_PROPERTIES = [("location", {"position_column": "pixel"}), ("dispersion", {})]
SACCADE_PROPERTIES = [
    ("amplitude", {}),
    ("peak_velocity", {}),
    ("dispersion", {}),
]


def test_fixation_properties_match_pymovements():
    gaze = _make_gaze()
    gaze.detect("ivt", minimum_duration=100, velocity_threshold=20.0)

    compute_event_properties(gaze, "fixation", FIXATION_PROPERTIES)

    _assert_properties_match(gaze, "fixation", FIXATION_PROPERTIES)


def test_saccade_properties_match_pymovements():
    gaze = _make_gaze()
    gaze.detect("microsaccades", minimum_duration=6, threshold_factor=6.0)

    compute_event_properties(gaze, "saccade", SACCADE_PROPERTIES)

    _assert_properties_match(gaze, "saccade", SACCADE_PROPERTIES)


def test_location_supports_median():
    gaze = _make_gaze()
    gaze.detect("ivt", minimum_duration=100, velocity_threshold=20.0)
    properties = [("location", {"position_column": "pixel", "method": "median"})]

    compute_event_properties(gaze, "fixation", properties)

    _assert_properties_match(gaze, "fixation", properties)


def test_shared_property_updated_per_event_type():
    gaze = _make_gaze()
    gaze.detect("ivt", minimum_duration=100, velocity_threshold=20.0)
    compute_event_properties(gaze, "fixation", FIXATION_PROPERTIES)
    fixation_dispersion = gaze.events.frame.filter(pl.col("name") == "fixation")[
        "dispersion"
    ]

    gaze.detect("microsaccades", minimum_duration=6, threshold_factor=6.0)
    compute_event_properties(gaze, "saccade", SACCADE_PROPERTIES)

    frame = gaze.events.frame
    assert not any(column.endswith("_right") for column in frame.columns)
    assert not any(column.endswith("_new") for column in frame.columns)

    # Fixation dispersion is untouched, saccade dispersion is filled in.
    assert frame.filter(pl.col("name") == "fixation")["dispersion"].equals(
        fixation_dispersion
    )
    assert frame.filter(pl.col("name") == "saccade")["dispersion"].null_count() == 0

    _assert_properties_match(gaze, "fixation", FIXATION_PROPERTIES)
    _assert_properties_match(gaze, "saccade", SACCADE_PROPERTIES)


def test_event_without_samples_gets_null_properties():
    gaze = _make_gaze()
    gaze.detect("ivt", minimum_duration=100, velocity_threshold=20.0)
    n_with_samples = gaze.events.frame.height

    extra_event = pl.DataFrame(
        {
            "trial": ["trial_00"],
            "name": ["fixation"],
            "onset": [dt.timedelta(milliseconds=100_000_000)],
            "offset": [dt.timedelta(milliseconds=100_000_200)],
            "duration": [dt.timedelta(milliseconds=200)],
        },
        schema=gaze.events.frame.schema,
    )
    gaze.events.frame = pl.concat([gaze.events.frame, extra_event])

    compute_event_properties(gaze, "fixation", FIXATION_PROPERTIES)

    events = gaze.events.frame
    assert events.height == n_with_samples + 1

    sample_less = events.filter(pl.col("onset") > dt.timedelta(milliseconds=50_000_000))
    assert sample_less.height == 1
    assert sample_less["location"][0] is None
    assert sample_less["dispersion"][0] is None

    # Events that do have samples still match the reference.
    with_samples = events.filter(
        pl.col("onset") < dt.timedelta(milliseconds=50_000_000)
    )
    reference = _reference_properties(gaze, "fixation", FIXATION_PROPERTIES).filter(
        pl.col("onset") < dt.timedelta(milliseconds=50_000_000)
    )
    columns = ["trial", "name", "onset", "offset", "location", "dispersion"]
    order = ["trial", "name", "onset", "offset"]
    assert_frame_equal(
        with_samples.select(columns).sort(order),
        reference.select(columns).sort(order),
        check_exact=False,
        abs_tol=1e-9,
    )


def test_empty_events_adds_null_columns():
    gaze = _make_gaze()
    gaze.detect("ivt", minimum_duration=100, velocity_threshold=20.0)

    compute_event_properties(gaze, "saccade", SACCADE_PROPERTIES)

    frame = gaze.events.frame
    for prop_name, _ in SACCADE_PROPERTIES:
        assert prop_name in frame.columns
        assert frame[prop_name].null_count() == frame.height


def test_multiple_trial_columns():
    samples = _make_samples().with_columns(pl.lit("page_1").alias("page"))
    gaze = pm.Gaze(
        samples,
        trial_columns=["trial", "page"],
        position_columns=["position_x", "position_y"],
        pixel_columns=["pixel_x", "pixel_y"],
        velocity_columns=["velocity_x", "velocity_y"],
    )
    gaze.detect("ivt", minimum_duration=100, velocity_threshold=20.0)

    compute_event_properties(gaze, "fixation", FIXATION_PROPERTIES)

    _assert_properties_match(gaze, "fixation", FIXATION_PROPERTIES)


def test_unsupported_property_raises():
    with pytest.raises(ValueError, match="Unsupported event property"):
        _property_expression("not_a_property", {})


def test_convert_time_to_ms_handles_duration_and_numeric():
    frame = pl.DataFrame(
        {
            "duration_col": [dt.timedelta(milliseconds=250)],
            "numeric_col": [250.0],
            "int_col": [250],
        }
    )

    converted = _convert_time_to_ms(frame, ["duration_col", "numeric_col", "int_col"])

    assert converted["duration_col"].to_list() == [250.0]
    assert converted["numeric_col"].to_list() == [250.0]
    assert converted["int_col"].to_list() == [250.0]
    assert converted.schema["duration_col"] == pl.Float64
