"""Event properties submodule of the preprocessing module."""

from __future__ import annotations

from typing import Any

import polars as pl
import pymovements as pm


def compute_event_properties(
    gaze: pm.Gaze,
    event_name: str,
    properties: list[tuple[str, dict]],
) -> None:
    """
    Compute and add event properties to `gaze.events`.

    The properties are computed in a single vectorized pass instead of the
    per-event loop used by :class:`pymovements.EventSamplesProcessor`. Every
    event is mapped to its samples with one backward as-of join per trial, after
    which all requested properties are aggregated per event with a single
    ``group_by``. This keeps the result identical to pymovements while scaling
    with the number of samples rather than ``events x samples``.

    Properties that already exist on ``gaze.events`` (for example ``dispersion``
    when computing fixation properties before saccade properties) are updated for
    the rows of the current event type and left untouched for all other events.

    Parameters
    ----------
    gaze : pm.Gaze
        Gaze object containing detected events.
    event_name : str
        Event type ('fixation', 'saccade', ...).
    properties : list[tuple[str, dict]]
        Each tuple defines (property_name, kwargs). Supported properties are
        ``location``, ``dispersion``, ``amplitude`` and ``peak_velocity``.
    """
    trial_columns = list(gaze.trial_columns or [])
    join_on = trial_columns + ["name", "onset", "offset"]
    prop_names = [prop_name for prop_name, _ in properties]

    events = gaze.events.frame.filter(pl.col("name") == event_name)

    if events.is_empty():
        result = gaze.events.frame.select(join_on).head(0)
        for prop_name in prop_names:
            result = result.with_columns(pl.lit(None).alias(prop_name))
        gaze.events.frame = _merge_properties(
            gaze.events.frame, result, join_on, prop_names
        )
        return

    keys = events.select(join_on).with_columns(
        pl.int_range(pl.len(), dtype=pl.Int64).alias("_event_id")
    )
    event_bounds = _convert_time_to_ms(keys, ["onset", "offset"])

    samples = _convert_time_to_ms(gaze.samples, ["time"])

    samples = samples.sort(trial_columns + ["time"])
    event_bounds = event_bounds.sort(trial_columns + ["onset"])

    joined = samples.join_asof(
        event_bounds.select(trial_columns + ["onset", "offset", "_event_id"]),
        left_on="time",
        right_on="onset",
        by=trial_columns or None,
        strategy="backward",
        check_sortedness=False,
    )
    joined = joined.filter(
        pl.col("_event_id").is_not_null() & (pl.col("time") <= pl.col("offset"))
    )

    aggregations = [
        _property_expression(prop_name, kwargs) for prop_name, kwargs in properties
    ]
    property_frame = joined.group_by(trial_columns + ["_event_id"]).agg(aggregations)

    result = keys.join(
        property_frame,
        on=trial_columns + ["_event_id"],
        how="left",
    ).select(join_on + prop_names)

    gaze.events.frame = _merge_properties(
        gaze.events.frame, result, join_on, prop_names
    )


def _merge_properties(
    frame: pl.DataFrame,
    result: pl.DataFrame,
    join_on: list[str],
    prop_names: list[str],
) -> pl.DataFrame:
    """Join computed properties onto ``frame``, updating existing columns in place.

    Columns of ``result`` that do not exist in ``frame`` are added. Columns that
    already exist are updated for the rows present in ``result`` (matched by
    ``join_on``) and keep their previous values elsewhere. This avoids the
    ``_right``-suffixed duplicate columns and the resulting null values that a
    plain join would produce when consecutive event types share a property name.
    """
    existing = set(frame.columns)
    colliding = [name for name in prop_names if name in existing]

    merged = frame.join(result, on=join_on, how="left", suffix="_new")

    if colliding:
        merged = merged.with_columns(
            [
                pl.coalesce([pl.col(f"{name}_new"), pl.col(name)]).alias(name)
                for name in colliding
            ]
        ).drop([f"{name}_new" for name in colliding])

    return merged


def _convert_time_to_ms(frame: pl.DataFrame, columns: list[str]) -> pl.DataFrame:
    """Return a copy of ``frame`` with the given ``Duration`` columns as float ms.

    Non-duration columns are cast to ``Float64`` and left otherwise untouched.
    """
    expressions = []
    for column in columns:
        if column not in frame.columns:
            continue
        if isinstance(frame.schema[column], pl.Duration):
            expressions.append(
                (pl.col(column).dt.total_microseconds() / 1000.0)
                .cast(pl.Float64)
                .alias(column)
            )
        else:
            expressions.append(pl.col(column).cast(pl.Float64).alias(column))
    if not expressions:
        return frame
    return frame.with_columns(expressions)


def _property_expression(prop_name: str, kwargs: dict[str, Any]) -> pl.Expr:
    """Build the aggregation expression for a single event property.

    Parameters
    ----------
    prop_name : str
        Name of the property. One of ``location``, ``dispersion``, ``amplitude``
        or ``peak_velocity``.
    kwargs : dict
        Keyword arguments for the property, mirroring the pymovements measures.

    Returns
    -------
    pl.Expr
        An aggregation expression producing a column named ``prop_name``.

    Raises
    ------
    ValueError
        If ``prop_name`` is not a supported property.
    """
    if prop_name == "location":
        position_column = kwargs.get("position_column", "position")
        method = kwargs.get("method", "mean")
        x_position = pl.col(position_column).list.get(0)
        y_position = pl.col(position_column).list.get(1)
        if method == "mean":
            x_component, y_component = x_position.mean(), y_position.mean()
        elif method == "median":
            x_component, y_component = x_position.median(), y_position.median()
        else:
            raise ValueError(
                f"Method '{method}' not supported. "
                "Please choose one of the following: ['mean', 'median']."
            )
        return pl.concat_list([x_component, y_component]).alias("location")

    if prop_name == "dispersion":
        position_column = kwargs.get("position_column", "position")
        x_position = pl.col(position_column).list.get(0)
        y_position = pl.col(position_column).list.get(1)
        return (
            x_position.max() - x_position.min() + y_position.max() - y_position.min()
        ).alias("dispersion")

    if prop_name == "amplitude":
        position_column = kwargs.get("position_column", "position")
        x_position = pl.col(position_column).list.get(0)
        y_position = pl.col(position_column).list.get(1)
        return (
            (
                (x_position.max() - x_position.min()).pow(2)
                + (y_position.max() - y_position.min()).pow(2)
            )
            .sqrt()
            .alias("amplitude")
        )

    if prop_name == "peak_velocity":
        velocity_column = kwargs.get("velocity_column", "velocity")
        x_velocity = pl.col(velocity_column).list.get(0)
        y_velocity = pl.col(velocity_column).list.get(1)
        return ((x_velocity.pow(2) + y_velocity.pow(2)).sqrt().max()).alias(
            "peak_velocity"
        )

    raise ValueError(f"Unsupported event property: '{prop_name}'.")
