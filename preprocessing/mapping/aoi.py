"""Mapping of fixations to AOIs."""

import polars as pl
import pymovements as pm

from ..utils.text_direction import is_vertical_script

__all__ = [
    "build_combined_text_stimulus",
    "enlarge_aois",
    "map_fixations_to_aois",
]


def build_combined_text_stimulus(
    stimuli: list,
    script_direction: str = "ltr",
) -> pm.stimulus.TextStimulus:
    """
    Consolidate the AOIs of all stimuli into a single text stimulus.

    Each stimulus contributes its character-level AOIs with the corresponding trial
    identifier added, so that the resulting stimulus can be used to process all trials
    of a session at once.

    For top-to-bottom text, the AOI geometry is transposed so that columns become
    horizontal lines. This lets the pymovements correction algorithms operate on the
    column axis.

    Parameters
    ----------
    stimuli : list of Stimulus
        A list of Stimulus objects, each containing ``text_stimulus`` data with defined
        AOIs and trial IDs.
    script_direction : str
        Script direction of the data collection. ``"ttb"`` transposes the AOIs.

    Returns
    -------
    pm.stimulus.TextStimulus
        A text stimulus holding the stacked AOIs of all stimuli.
    """
    from ..config import settings

    all_aois = pl.DataFrame()
    for stimulus in stimuli:
        aoi = stimulus.text_stimulus.aois
        trial = stimulus.trial_id
        aoi = aoi.with_columns(pl.lit(trial).alias(settings.TRIAL_COL))
        all_aois = all_aois.vstack(aoi)

    if is_vertical_script(script_direction):
        all_aois = _transpose_aois(all_aois)

    return pm.stimulus.TextStimulus(
        all_aois,
        aoi_column=settings.CHAR_IDX_COL,
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column=settings.PAGE_COL,
        trial_column=settings.TRIAL_COL,
    )


def _transpose_aois(aois: pl.DataFrame) -> pl.DataFrame:
    """Swap the horizontal and vertical AOI geometry columns."""
    required_columns = {"top_left_x", "top_left_y", "width", "height"}
    missing_columns = required_columns.difference(aois.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required AOI columns: {missing_str}")

    other_columns = [
        column for column in aois.columns if column not in required_columns
    ]
    return aois.select(
        *[pl.col(column) for column in other_columns],
        pl.col("top_left_y").alias("top_left_x"),
        pl.col("top_left_x").alias("top_left_y"),
        pl.col("height").alias("width"),
        pl.col("width").alias("height"),
    )


def map_fixations_to_aois(
    gaze: pm.Gaze,
    stimuli: list,
) -> None:
    """
    Maps gaze events to areas of interest (AOIs) for each stimulus.

    This function processes a list of stimuli, extracts AOIs from each stimulus,
    and assigns the corresponding trial identifier to them.
    It then consolidates all AOIs into a unified data structure and maps gaze events to these AOIs.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze data containing events to be mapped to AOIs.
    stimuli : list of Stimulus
        A list of Stimulus objects, each containing ``text_stimulus`` data with defined
        AOIs and trial IDs.

    Returns
    -------
    None
        The function performs mapping in place and does not return any value.
    """
    gaze.events.map_to_aois(build_combined_text_stimulus(stimuli), verbose=False)


def enlarge_aois(
    aois: pl.DataFrame,
    script_direction: str = "ltr",
) -> pl.DataFrame:
    """Enlarge character AOIs to cover the space to neighbouring lines or columns.

    For horizontal text the AOIs are enlarged vertically. For ``"ttb"`` text they are
    enlarged horizontally, because the lines of vertical text are columns.

    Parameters
    ----------
    aois : pl.DataFrame
        Character-level AOIs of one trial. Must contain ``page``, ``line_idx`` and the
        geometry columns for the active axis.
    script_direction : str
        Script direction of the data collection.

    Returns
    -------
    pl.DataFrame
        AOIs with the geometry expanded on the active axis.
    """
    if aois.is_empty():
        raise ValueError("AOIs DataFrame must not be empty")

    if "trial" in aois.columns:
        raise ValueError(
            "AOIs DataFrame should not contain a 'trial' column. Please process each trial separately."
        )

    if is_vertical_script(script_direction):
        return _enlarge_aois_columns(aois)
    return _enlarge_aois_lines(aois)


def _enlarge_aois_lines(aois: pl.DataFrame) -> pl.DataFrame:
    """Enlarge AOIs vertically to cover the space between text lines."""
    required_columns = {"page", "line_idx", "top_left_y", "height"}
    missing_columns = required_columns.difference(aois.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required AOI columns: {missing_str}")

    line_keys = ["page", "line_idx"]

    line_level = (
        aois.group_by(line_keys)
        .agg(
            pl.col("top_left_y").min().alias("line_top_left_y"),
            pl.col("height").max().alias("line_height"),
        )
        .sort(line_keys)
        .with_columns(
            (
                pl.col("line_top_left_y")
                - (
                    pl.col("line_top_left_y").shift(1).over(["page"])
                    + pl.col("line_height").shift(1).over(["page"])
                )
            )
            .fill_null(0.0)
            .clip(lower_bound=0.0)
            .alias("line_spacing")
        )
        .with_columns((pl.col("line_spacing") / 2.0).alias("half_line_spacing"))
        .select(line_keys + ["half_line_spacing"])
    )

    return (
        aois.join(line_level, on=line_keys, how="left")
        .with_columns(
            (pl.col("top_left_y") - pl.col("half_line_spacing")).alias("top_left_y"),
            (pl.col("height") + 2 * pl.col("half_line_spacing")).alias("height"),
        )
        .drop("half_line_spacing")
    )


def _enlarge_aois_columns(aois: pl.DataFrame) -> pl.DataFrame:
    """Enlarge AOIs horizontally to cover the space between text columns.

    Columns are sorted by their physical x position, not by ``line_idx``. This works
    for right-to-left column order, where ``line_idx`` increases while x decreases.
    Adjacent columns are expanded to the midpoint between them so that the full
    inter-column gap is covered.
    """
    required_columns = {"page", "line_idx", "top_left_x", "width"}
    missing_columns = required_columns.difference(aois.columns)
    if missing_columns:
        missing_str = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required AOI columns: {missing_str}")

    line_keys = ["page", "line_idx"]

    line_level = (
        aois.group_by(line_keys)
        .agg(
            pl.col("top_left_x").min().alias("line_left"),
            (pl.col("top_left_x") + pl.col("width")).max().alias("line_right"),
        )
        .sort(["page", "line_left"])
        .with_columns(
            (pl.col("line_right") + pl.col("line_left").shift(-1).over(["page"]))
            .truediv(2.0)
            .alias("boundary_right")
        )
        .with_columns(
            pl.col("boundary_right").shift(1).over(["page"]).alias("boundary_left")
        )
        .with_columns(
            pl.when(pl.col("boundary_left").is_null())
            .then(pl.col("line_left"))
            .otherwise(pl.col("boundary_left"))
            .alias("new_left"),
            pl.when(pl.col("boundary_right").is_null())
            .then(pl.col("line_right"))
            .otherwise(pl.col("boundary_right"))
            .alias("new_right"),
        )
        .select(line_keys + ["new_left", "new_right"])
    )

    return (
        aois.join(line_level, on=line_keys, how="left")
        .with_columns(
            pl.col("new_left").alias("top_left_x"),
            (pl.col("new_right") - pl.col("new_left")).alias("width"),
        )
        .drop("new_left", "new_right")
    )
