"""Mapping of fixations to AOIs."""

import polars as pl
import pymovements as pm


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
    from ..config import settings

    all_aois = pl.DataFrame()
    for stimulus in stimuli:
        aoi = stimulus.text_stimulus.aois
        trial = stimulus.trial_id
        aoi = aoi.with_columns(pl.lit(trial).alias(settings.TRIAL_COL))
        all_aois = all_aois.vstack(aoi)

    all_aois = pm.stimulus.TextStimulus(
        all_aois,
        aoi_column=settings.CHAR_IDX_COL,
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column=settings.PAGE_COL,
        trial_column=settings.TRIAL_COL,
    )

    gaze.events.map_to_aois(all_aois, verbose=False)


def enlarge_aois(
    aois: pl.DataFrame,
) -> pl.DataFrame:
    """
    The aois for each char are currently only covering that char. They should be enlarged to cover the part below and
    above until the middle between two lines. The top left y coordinate of the aoi
    should be moved up by half the line spacing and the height should be increased
    by 2x half the space, the spacing in pixel is calculated based on the first line.

    :param aois: pl.DataFrame containing the AOI information with at least the
    columns "page", "line_idx", "top_left_y", and "height", for more info see the respective aoi file.
    Each trial needs to be processed separately!

    :return: the input aois DataFrame with the top left y coordinate of each aoi moved up by
    half the line spacing and the height increased by 2x half the line spacing.
    """

    if aois.is_empty():
        raise ValueError("AOIs DataFrame must not be empty")

    if "trial" in aois.columns:
        raise ValueError(
            "AOIs DataFrame should not contain a 'trial' column. Please process each trial separately."
        )

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

    aois = (
        aois.join(line_level, on=line_keys, how="left")
        .with_columns(
            (pl.col("top_left_y") - pl.col("half_line_spacing")).alias("top_left_y"),
            (pl.col("height") + 2 * pl.col("half_line_spacing")).alias("height"),
        )
        .drop("half_line_spacing")
    )

    return aois
