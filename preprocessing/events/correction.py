"""Fixation drift correction wrapper around pymovements."""

from __future__ import annotations

import polars as pl
import pymovements as pm

from ..config import settings
from ..mapping.aoi import build_combined_text_stimulus
from ..utils.text_direction import is_vertical_script, normalize_script_direction

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


def _text_bounds_table(
    stimulus: pm.stimulus.TextStimulus,
    key_columns: list[str],
) -> pl.DataFrame:
    aois = stimulus.aois
    return aois.group_by(key_columns).agg(
        pl.col("top_left_x").min().alias("__text_x_min"),
        pl.col("top_left_y").min().alias("__text_y_min"),
        (pl.col("top_left_x") + pl.col("width")).max().alias("__text_x_max"),
        (pl.col("top_left_y") + pl.col("height")).max().alias("__text_y_max"),
        pl.col("height").max().alias("__text_line_height"),
        pl.col("width").max().alias("__text_column_width"),
    )


def _dot_mask(
    frame: pl.DataFrame,
    x: float,
    y: float,
    radius: float,
    *,
    vertical: bool,
) -> pl.Expr:
    location_x, location_y = _location_expressions(frame)
    line_height = pl.col("__text_line_height")
    x_tolerance = pl.col("__text_column_width") if vertical else line_height

    inside_text = (
        (location_x >= pl.col("__text_x_min") - x_tolerance)
        & (location_x <= pl.col("__text_x_max") + x_tolerance)
        & (location_y >= pl.col("__text_y_min") - line_height)
        & (location_y <= pl.col("__text_y_max") + line_height)
    )
    # Gaze positions on the dot can be several dot radii away from its centre.
    # Use the distance from the dot to the text block as a tolerance, while the
    # text bounds guard above prevents real text fixations from being excluded.
    horizontal_gap = pl.max_horizontal(
        (pl.col("__text_x_min") - x).clip(lower_bound=0.0),
        (x - pl.col("__text_x_max")).clip(lower_bound=0.0),
    )
    vertical_gap = pl.max_horizontal(
        (pl.col("__text_y_min") - y).clip(lower_bound=0.0),
        (y - pl.col("__text_y_max")).clip(lower_bound=0.0),
    )
    dot_to_text = pl.max_horizontal(horizontal_gap, vertical_gap)
    dot_reach = pl.max_horizontal(
        pl.lit(radius * 4.0),
        dot_to_text,
    )
    within_dot = (
        (location_x - x) * (location_x - x) + (location_y - y) * (location_y - y)
    ) <= dot_reach * dot_reach

    return (pl.col("name") == settings.FIXATION) & within_dot & ~inside_text


def _separate_excluded_events(
    gaze: pm.Gaze,
    x: float,
    y: float,
    radius: float,
    stimulus: pm.stimulus.TextStimulus,
    *,
    vertical: bool,
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

    text_bounds = _text_bounds_table(stimulus, key_columns)
    indexed = frame.with_row_index("__fixation_correction_row").join(
        text_bounds,
        on=key_columns,
        how="left",
    )
    has_text = pl.col("__text_y_max").is_not_null()
    dot_mask = _dot_mask(indexed, x, y, radius, vertical=vertical)
    excluded_rows = indexed.filter(~has_text | dot_mask)
    if excluded_rows.is_empty():
        gaze.events.frame = frame
        return None

    text_columns = [
        column for column in text_bounds.columns if column not in key_columns
    ]
    gaze.events.frame = indexed.filter(has_text & ~dot_mask).drop(*text_columns)
    return excluded_rows.drop(*text_columns)


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


def _transpose_location_columns(frame: pl.DataFrame) -> pl.DataFrame:
    """Swap the x and y components of all location representations."""
    has_split = {"location_x", "location_y"}.issubset(frame.columns)
    has_list = "location" in frame.columns
    if not has_split and not has_list:
        raise ValueError(
            "Fixation events need location_x/location_y columns or a location column "
            "for top-to-bottom correction."
        )

    if has_split:
        frame = frame.with_columns(
            pl.col("location_y").alias("__fixation_transpose_tmp")
        )
        frame = frame.with_columns(
            pl.col("location_x").alias("location_y"),
            pl.col("__fixation_transpose_tmp").alias("location_x"),
        ).drop("__fixation_transpose_tmp")

    if has_list:
        frame = frame.with_columns(
            pl.concat_list(
                [
                    pl.col("location").list.get(1),
                    pl.col("location").list.get(0),
                ]
            ).alias("location")
        )
    return frame


def _sync_split_locations_from_list(frame: pl.DataFrame) -> pl.DataFrame:
    """Keep split location columns consistent when both representations exist."""
    if (
        {"location_x", "location_y"}.issubset(frame.columns)
        and "location" in frame.columns
        and frame["location"].null_count() < frame.height
    ):
        return frame.with_columns(
            pl.col("location").list.get(0).alias("location_x"),
            pl.col("location").list.get(1).alias("location_y"),
        )
    return frame


def _save_original_locations(
    frame: pl.DataFrame,
) -> tuple[pl.DataFrame, set[str]]:
    """Store original locations before a transposed correction."""
    saved: set[str] = set()
    if {"location_x", "location_y"}.issubset(frame.columns):
        frame = frame.with_columns(
            pl.col("location_x").alias("__fixation_original_x"),
            pl.col("location_y").alias("__fixation_original_y"),
        )
        saved.add("split")
    if "location" in frame.columns:
        frame = frame.with_columns(
            pl.col("location").alias("__fixation_original_location")
        )
        saved.add("list")
    return frame, saved


def _restore_original_locations(
    frame: pl.DataFrame,
    saved: set[str],
) -> pl.DataFrame:
    """Write saved original locations back into the standard bookkeeping columns."""
    expressions = []
    if "split" in saved:
        expressions.extend(
            [
                pl.col("__fixation_original_x").alias("location_x_original"),
                pl.col("__fixation_original_y").alias("location_y_original"),
            ]
        )
    if "list" in saved:
        expressions.append(
            pl.col("__fixation_original_location").alias("location_original")
        )
    frame = frame.with_columns(expressions)
    temporary_columns = [
        column
        for column in (
            "__fixation_original_x",
            "__fixation_original_y",
            "__fixation_original_location",
        )
        if column in frame.columns
    ]
    return frame.drop(*temporary_columns)


def _resolve_direction(
    script_direction: str | None,
    lab_config: object,
) -> str:
    if not isinstance(script_direction, str):
        candidate = getattr(lab_config, "script_direction", None)
        script_direction = candidate if isinstance(candidate, str) else None
    return normalize_script_direction(script_direction)


def correct_fixations(
    gaze: pm.Gaze,
    stimuli: list,
    lab_config: object,
    algorithm: str | list[str] | None = None,
    algorithm_kwargs: dict | None = None,
    script_direction: str | None = None,
) -> None:
    """
    Correct the drift of fixation locations for all trials of a session.

    For horizontal text, the vertical drift is corrected. For top-to-bottom text,
    the coordinates are transposed before correction so that text columns become
    horizontal lines, then the corrected locations are transposed back.

    Events on trials without text AOIs, and fixations on the final fixation dot, are
    removed before correction and reinserted unchanged afterwards. Correction therefore
    sees only the real text lines on text trials. The dot geometry is derived from the
    stimulus config.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze object whose fixation events are corrected in place.
    stimuli : list of Stimulus
        A list of Stimulus objects, each containing ``text_stimulus`` data with defined
        AOIs and trial IDs. Their AOIs are consolidated into a single text stimulus.
    lab_config : object
        Resolved lab configuration with the final fixation dot geometry and script
        direction.
    algorithm : str | list[str] | None, optional
        Drift correction algorithm or list of algorithms. Defaults to
        ``settings.FIXATION_CORRECTION_ALGORITHM``.
    algorithm_kwargs : dict | None, optional
        Additional tuning parameters passed to the drift algorithms. Defaults to
        ``settings.FIXATION_CORRECTION_KWARGS``.
    script_direction : str | None, optional
        Script direction. Defaults to ``lab_config.script_direction``.

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

    direction = _resolve_direction(script_direction, lab_config)
    vertical = is_vertical_script(direction)

    dot_x, dot_y, dot_radius = validate_final_fix_dot(lab_config)
    stimulus = build_combined_text_stimulus(stimuli, use_correction_aois=True)
    character_level = settings.CHAR_IDX_COL in stimulus.aois.columns

    excluded_rows = _separate_excluded_events(
        gaze,
        dot_x,
        dot_y,
        dot_radius,
        stimulus,
        vertical=vertical,
    )
    try:
        if vertical:
            gaze.events.frame, saved_locations = _save_original_locations(
                gaze.events.frame
            )
            gaze.events.frame = _transpose_location_columns(gaze.events.frame)
            transposed_stimulus = build_combined_text_stimulus(
                stimuli,
                script_direction="ttb",
                use_correction_aois=True,
            )
            gaze.events.correct_fixations(
                transposed_stimulus,
                algorithm=algorithm,
                directionality="left-to-right",
                algorithm_kwargs=algorithm_kwargs,
                fixation_name=settings.FIXATION,
                character_level=character_level,
            )
            gaze.events.frame = _sync_split_locations_from_list(gaze.events.frame)
            gaze.events.frame = _transpose_location_columns(gaze.events.frame)
            gaze.events.frame = _restore_original_locations(
                gaze.events.frame,
                saved_locations,
            )
        else:
            directionality = "right-to-left" if direction == "rtl" else "left-to-right"
            gaze.events.correct_fixations(
                stimulus,
                algorithm=algorithm,
                directionality=directionality,
                algorithm_kwargs=algorithm_kwargs,
                fixation_name=settings.FIXATION,
                character_level=character_level,
            )
    finally:
        _restore_excluded_events(gaze, excluded_rows)
