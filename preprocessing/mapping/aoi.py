"""UOA importing and mapping of fixations to AOIs."""

from pathlib import Path

import polars as pl
import pymovements as pm

from preprocessing.utils.logging import get_logger


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


def add_custom_uoa(
    stimuli_folder: Path,
    aoi_file: Path,
    uoa_column_name,
    uoa_idx_colum_name,
) -> None:
    """
    Add custom units of analysis to the aoi file and rewrite the file. The units of analysis file should be in the respective stimulus folder.



    How to add it:
    - Merge the custom and the original aoi files on the char and char index as well as the page column!
    - check that all chars listed in both files exactly align. Index and char should be exactly the same.
    - for the questions add the segments to all question images versions and make sure the characters match. Only the coordinates should be different for the options

    Output:
    The original aoi files should be exactly the same as before also the file name. The contents of the original "units_of_analysis" columns will be written
    into the "secondary units of analysis" columns

    If any of the characters do not match, the pipeline will fail. If the uoa file is missing, the pipeline will warn and the aoi file remains unchanged.

    """
    logger = get_logger()

    # Import aoi data
    aoi_data = pl.read_csv(aoi_file)
    aoi_data = aoi_data.drop(
        "secondary_unit_of_analysis",
        "secondary_unit_of_analysis_idx",
        "secondary_unit_of_analysis_idx_in_line",
    )
    aoi_data = aoi_data.sort(by=["page", "char_idx"])

    # Import uoa data
    uoa_file = stimuli_folder / "custom_units_of_analysis" / aoi_file.name

    if not uoa_file.exists():
        logger.warning(
            f"We could not find a matching uoa file for {aoi_file.name}. Please make "
            f"sure that the uoa file is named exactly as the corresponding aoi file and "
            f"that it is in your data folder in a folder called 'custom_units_of_analysis'."
            f"Using default white-spaced units of analysis for {aoi_file.name}."
        )
        return

    if "questions" in uoa_file.name:
        uoa_data = pl.read_csv(uoa_file)[
            [
                uoa_column_name,
                uoa_idx_colum_name,
                "char",
                "char_idx",
                "page",
                "question_image_version",
            ]
        ]
        uoa_data = uoa_data.filter(
            uoa_data["question_image_version"] == "question_images_version_1"
        )

        uoa_data = uoa_data[
            [uoa_column_name, uoa_idx_colum_name, "char", "char_idx", "page"]
        ]

    else:
        uoa_data = pl.read_csv(uoa_file)[
            [uoa_column_name, uoa_idx_colum_name, "char", "char_idx", "page"]
        ]

    uoa_data = uoa_data.sort(by=["page", "char_idx"])

    # Ensure that list of characters matches exactly between files
    uoa_chars = list(uoa_data["char"])
    if "questions" in uoa_file.name:
        aoi_chars = list(
            aoi_data["char"].filter(
                aoi_data["question_image_version"] == "question_images_version_1"
            )
        )
    else:
        aoi_chars = list(aoi_data["char"])

    try:
        assert aoi_chars == uoa_chars
    except AssertionError:
        msg = (
            f"The custom units of analysis file for the corresponding aoi file {aoi_file.name}, contains different characters. "
            f"Please verify that the charactters of the stimuli in both files match exactly."
        )
        logger.exception(msg)
        raise

    # Merge the data files. Previous units of analysis become secondary units of analysis
    aoi_data = aoi_data.rename(
        {
            "unit_of_analysis_idx": "secondary_unit_of_analysis_idx",
            "unit_of_analysis": "secondary_unit_of_analysis",
            "unit_of_analysis_idx_in_line": "secondary_unit_of_analysis_idx_in_line",
        }
    )

    uoa_data = uoa_data.rename(
        {
            uoa_column_name: "unit_of_analysis",
            uoa_idx_colum_name: "unit_of_analysis_idx",
        }
    )

    new_aois = aoi_data.join(uoa_data, on=["page", "char_idx", "char"])

    # get the line index of the new units of analysis
    new_aois = new_aois.with_columns(
        pl.col("unit_of_analysis_idx")
        .rank(method="dense")
        .over(["page", "line_idx"])
        .cast(pl.Int64)
        .alias("unit_of_analysis_idx_in_line")
    )

    col_order = [
        "char_idx",
        "char",
        "top_left_x",
        "top_left_y",
        "width",
        "height",
        "char_idx_in_line",
        "line_idx",
        "page",
        "unit_of_analysis_idx",
        "unit_of_analysis_idx_in_line",
        "unit_of_analysis",
        "secondary_unit_of_analysis_idx",
        "secondary_unit_of_analysis_idx_in_line",
        "secondary_unit_of_analysis",
    ]

    if "questions" in aoi_file.name:
        col_order.append("question_image_version")

    new_aois = new_aois[col_order]
    new_aois = new_aois.sort(by=["page", "line_idx", "char_idx"])
    new_aois.write_csv(aoi_file)
