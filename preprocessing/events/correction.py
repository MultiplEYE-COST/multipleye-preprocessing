"""Fixation drift correction wrapper around pymovements."""

from __future__ import annotations

import polars as pl
import pymovements as pm

from ..config import settings
from ..mapping.aoi import build_combined_text_stimulus

__all__ = ["correct_fixations", "validate_final_fix_dot"]

_FINAL_DOT_KEYS = (
    ("final_fix_dot_x", "FINAL_FIX_DOT_X"),
    ("final_fix_dot_y", "FINAL_FIX_DOT_Y"),
    ("final_fix_dot_radius", "FINAL_FIX_DOT_RADIUS"),
)


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
        If any final-dot key is missing or the radius is not positive.
    """
    missing = [
        config_key
        for attribute, config_key in _FINAL_DOT_KEYS
        if getattr(lab_config, attribute, None) is None
    ]
    if missing:
        raise ValueError(
            "Fixation correction requires final-dot metadata in the stimulus config. "
            f"Missing: {', '.join(missing)}. Add these keys to config_*.py. "
            "The final dot is not read from the AOI files."
        )

    x = float(lab_config.final_fix_dot_x)
    y = float(lab_config.final_fix_dot_y)
    radius = float(lab_config.final_fix_dot_radius)
    if radius <= 0:
        raise ValueError(
            "FINAL_FIX_DOT_RADIUS must be positive, "
            f"got {radius} in the stimulus config."
        )
    return x, y, radius


def _dot_mask(frame: pl.DataFrame, x: float, y: float, radius: float) -> pl.Expr:
    if {"location_x", "location_y"}.issubset(frame.columns):
        dx = pl.col("location_x") - x
        dy = pl.col("location_y") - y
    elif "location" in frame.columns:
        dx = pl.col("location").list.get(0) - x
        dy = pl.col("location").list.get(1) - y
    else:
        raise ValueError(
            "Fixation events need location_x/location_y columns or a location column "
            "to exclude final-dot fixations."
        )
    return (pl.col("name") == settings.FIXATION) & (
        (dx * dx + dy * dy) <= radius * radius
    )


def _separate_dot_fixations(
    gaze: pm.Gaze,
    x: float,
    y: float,
    radius: float,
) -> pl.DataFrame | None:
    frame = gaze.events.frame
    if frame.is_empty():
        return None

    indexed = frame.with_row_index("__fixation_correction_row")
    dot_mask = _dot_mask(indexed, x, y, radius)
    dot_rows = indexed.filter(dot_mask)
    if dot_rows.is_empty():
        return None

    gaze.events.frame = indexed.filter(~dot_mask)
    return dot_rows


def _restore_dot_fixations(gaze: pm.Gaze, dot_rows: pl.DataFrame | None) -> None:
    if dot_rows is None:
        return

    corrected = gaze.events.frame
    missing_columns = [
        column for column in corrected.columns if column not in dot_rows.columns
    ]
    if missing_columns:
        dot_rows = dot_rows.with_columns(
            pl.lit(None).cast(corrected.schema[column]).alias(column)
            for column in missing_columns
        )

    combined = pl.concat([corrected, dot_rows.select(corrected.columns)])
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

    Fixations on the final fixation dot are removed before correction and reinserted
    unchanged afterwards. Correction therefore sees only the real text lines. The dot
    must be declared in the stimulus config with ``FINAL_FIX_DOT_X``,
    ``FINAL_FIX_DOT_Y`` and ``FINAL_FIX_DOT_RADIUS``. Missing dot metadata is an error
    when correction is active.

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

    dot_rows = _separate_dot_fixations(gaze, dot_x, dot_y, dot_radius)
    try:
        gaze.events.correct_fixations(
            stimulus,
            algorithm=algorithm,
            algorithm_kwargs=algorithm_kwargs,
            fixation_name=settings.FIXATION,
            character_level=character_level,
        )
    finally:
        _restore_dot_fixations(gaze, dot_rows)
