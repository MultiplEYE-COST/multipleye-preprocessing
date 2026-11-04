"""Fixation drift correction wrapper around pymovements."""

from __future__ import annotations

import polars as pl
import pymovements as pm

from ..config import settings
from ..mapping.aoi import build_combined_text_stimulus

__all__ = ["correct_fixations", "validate_final_fix_dot"]


def validate_final_fix_dot(lab_config: object) -> tuple[float, float, float]:
    """Return the final fixation dot geometry from the stimulus config.

    Parameters
    ----------
    lab_config : object
        Resolved lab configuration for the data collection.

    Returns
    -------
    tuple of float
        Dot center x, center y and radius in pixels.

    Raises
    ------
    ValueError
        If the geometry cannot be derived or the radius is not positive.
    """
    values = (
        getattr(lab_config, "final_fix_dot_x", None),
        getattr(lab_config, "final_fix_dot_y", None),
        getattr(lab_config, "final_fix_dot_radius", None),
    )
    if any(value is None for value in values):
        raise ValueError(
            "Fixation correction could not derive the final fixation dot from the "
            "stimulus config. The config needs IMAGE_WIDTH_PX, IMAGE_HEIGHT_PX, "
            "MIN_MARGIN_LEFT_PX, MIN_MARGIN_RIGHT_PX, FIX_DOT_X, RESOLUTION and "
            "SCREEN_SIZE_CM, or explicit POS_BOTTOM_DOT_X_PX, POS_BOTTOM_DOT_Y_PX "
            "and FIX_DOT_RADIUS."
        )

    x, y, radius = (float(value) for value in values)
    if radius <= 0:
        raise ValueError(f"Final fixation dot radius must be positive, got {radius}.")
    return x, y, radius


def _location_expressions(frame: pl.DataFrame) -> tuple[pl.Expr, pl.Expr]:
    if {"location_x", "location_y"}.issubset(frame.columns):
        return pl.col("location_x"), pl.col("location_y")
    if "location" in frame.columns:
        return (
            pl.col("location").list.get(0),
            pl.col("location").list.get(1),
        )
    raise ValueError(
        "Fixation events need location_x/location_y columns or a location column "
        "to exclude final-dot fixations."
    )


def _text_bounds(
    stimulus: pm.stimulus.TextStimulus,
) -> tuple[float, float, float, float, float]:
    aois = stimulus.aois
    x_min = float(aois["top_left_x"].min())
    y_min = float(aois["top_left_y"].min())
    x_max = float((aois["top_left_x"] + aois["width"]).max())
    y_max = float((aois["top_left_y"] + aois["height"]).max())
    line_height = float(aois["height"].max())
    return x_min, y_min, x_max, y_max, line_height


def _dot_mask(
    frame: pl.DataFrame,
    x: float,
    y: float,
    radius: float,
    text_bounds: tuple[float, float, float, float, float],
) -> pl.Expr:
    location_x, location_y = _location_expressions(frame)
    x_min, y_min, x_max, y_max, line_height = text_bounds

    inside_text = (
        (location_x >= x_min - line_height)
        & (location_x <= x_max + line_height)
        & (location_y >= y_min - line_height)
        & (location_y <= y_max + line_height)
    )
    within_dot = (
        (location_x - x) * (location_x - x) + (location_y - y) * (location_y - y)
    ) <= radius * radius

    return (pl.col("name") == settings.FIXATION) & within_dot & ~inside_text


def _separate_excluded_events(
    gaze: pm.Gaze,
    x: float,
    y: float,
    radius: float,
    stimulus: pm.stimulus.TextStimulus,
) -> pl.DataFrame | None:
    frame = gaze.events.frame
    if frame.is_empty():
        return None

    key_columns = [
        column
        for column in (settings.TRIAL_COL, settings.PAGE_COL)
        if column in stimulus.aois.columns and column in frame.columns
    ]
    if not key_columns:
        raise ValueError(
            "Fixation events and stimulus AOIs need a shared trial or page column."
        )

    text_trials = (
        stimulus.aois.select(key_columns)
        .unique()
        .with_columns(pl.lit(True).alias("__has_text"))
    )
    indexed = frame.with_row_index("__fixation_correction_row").join(
        text_trials,
        on=key_columns,
        how="left",
    )
    has_text = pl.col("__has_text").fill_null(False)
    dot_mask = _dot_mask(indexed, x, y, radius, _text_bounds(stimulus))
    excluded_rows = indexed.filter(~has_text | dot_mask)
    if excluded_rows.is_empty():
        gaze.events.frame = frame
        return None

    gaze.events.frame = indexed.filter(has_text & ~dot_mask).drop("__has_text")
    return excluded_rows.drop("__has_text")


def _restore_excluded_events(gaze: pm.Gaze, excluded_rows: pl.DataFrame | None) -> None:
    if excluded_rows is None:
        return

    corrected = gaze.events.frame
    missing_columns = [
        column for column in corrected.columns if column not in excluded_rows.columns
    ]
    if missing_columns:
        excluded_rows = excluded_rows.with_columns(
            pl.lit(None).cast(corrected.schema[column]).alias(column)
            for column in missing_columns
        )

    combined = pl.concat([corrected, excluded_rows.select(corrected.columns)])
    gaze.events.frame = combined.sort("__fixation_correction_row").drop(
        "__fixation_correction_row"
    )


def correct_fixations(
    gaze: pm.Gaze,
    stimuli: list,
    lab_config: object,
    algorithm: str | list[str] | None = None,
    algorithm_kwargs: dict | None = None,
) -> None:
    """
    Correct the vertical drift of fixation locations for all trials of a session.

    Events on trials without text AOIs, and fixations on the final fixation dot, are
    removed before correction and reinserted unchanged afterwards. Correction therefore
    sees only the real text lines on text trials. The dot geometry is derived from the
    stimulus config. A fixation counts as a dot fixation only when it is both inside the
    dot radius and outside the text AOI bounds. Missing geometry is an error when
    correction is active.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object whose fixation events are corrected in place.
    stimuli : list of Stimulus
        A list of Stimulus objects, each containing ``text_stimulus`` data with defined
        AOIs and trial IDs. Their AOIs are consolidated into a single text stimulus.
    lab_config : object
        Resolved lab configuration with the final fixation dot geometry.
    algorithm : str | list[str] | None, optional
        Drift correction algorithm or list of algorithms. Defaults to
        ``settings.FIXATION_CORRECTION_ALGORITHM``.
    algorithm_kwargs : dict | None, optional
        Additional tuning parameters passed to the drift algorithms. Defaults to
        ``settings.FIXATION_CORRECTION_KWARGS``.

    Notes
    -----
    The ``character_level`` flag is derived from the presence of the configured character
    index column in the AOIs, since pymovements needs to aggregate character-level AOIs
    to word locations for the DTW-based algorithms.
    """
    if algorithm is None:
        algorithm = settings.FIXATION_CORRECTION_ALGORITHM
    if algorithm_kwargs is None:
        algorithm_kwargs = settings.FIXATION_CORRECTION_KWARGS

    dot_x, dot_y, dot_radius = validate_final_fix_dot(lab_config)
    stimulus = build_combined_text_stimulus(stimuli)
    character_level = settings.CHAR_IDX_COL in stimulus.aois.columns

    excluded_rows = _separate_excluded_events(
        gaze,
        dot_x,
        dot_y,
        dot_radius,
        stimulus,
    )
    try:
        gaze.events.correct_fixations(
            stimulus,
            algorithm=algorithm,
            algorithm_kwargs=algorithm_kwargs,
            fixation_name=settings.FIXATION,
            character_level=character_level,
        )
    finally:
        _restore_excluded_events(gaze, excluded_rows)
