"""UOA importing and mapping of fixations to AOIs."""

import polars as pl
import pymovements as pm
import difflib
from pathlib import Path
from preprocessing import settings


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



def add_custom_aois(aoi_file: Path, language: str) -> None:
    """
    Will call a language specific function which adds the custom aois for this language, if they are available and
    supported.
    :param aoi_file: Path to the AOI file
    :param language: The language of the data collection.
    :return:
    """

    if language == "ZH":
        _add_custom_uoa(aoi_file, "segment", "segment_idx")
    elif language == "KL":
        # for KL currently, the questions are not supported
        if not "question" in aoi_file.name:
            custom_name = aoi_file.stem + "_morph.csv"
            _add_custom_uoa(aoi_file, "morph_token", "morph_idx", custom_name)
    else:
        raise Warning(
            f"You requested adding custom units of analysis to the aoi files. Currently, your language {language} "
            "is not supported. Please contact the maintainers to add your language."
        )


def _add_custom_uoa(
    aoi_file: Path, uoa_column_name, uoa_idx_colum_name, custom_file_name: str = ""
) -> None:
    """
    The custom units of analysis can be added as follows for ZH:
    - They are in a directory called "custom_units_of_analysis" in the data folder
    - The aoi files for the questions are named and structured the same as the original question aoi files.
        - They contain an additional segment and segment_idx column
        - As the text on all pages is for all question versions is the same, only question_images_version_1 is annotated
    - The stimuli text aoi files are name like this: Lit_Alchemist_zh_seg_pages.csv. The first part can be replaced
    by the respective stimulus name
        - They contain an additional word and word_idx column

    How to add it:
    - Merge the custom and the original aoi files on the char and char index as well as the page column!
    - check that all chars listed in both files exactly align. Index and char should be exactly the same.
    - ensure the segment contains the actual characters that it annotates, and that the running segment index is correct
    - for the questions add the segments to all question images versions and make sure the characters match. Only the coordinates should be different for the options

    Output:
    The original aoi files should be exactly the same as before also the file name, but they should contain two additional columns:
        - unit_of_analysis
        - unit_of_analysis_idx

    If there is a word column already in there: rename to secondary_unit_of_analysis and word_idx to secondary_unit_of_analysis_idx.
    The characters and character indices should stay exactly the same.

    If any of the characters and segment characters do not match, it will be reported.

    """

    if custom_file_name:
        uoa_file = settings.DATASET_DIR / "custom_units_of_analysis" / custom_file_name
    else:
        uoa_file = settings.DATASET_DIR / "custom_units_of_analysis" / aoi_file.name

    if not uoa_file.exists():
        raise FileNotFoundError(
            f"We could not find a matching uoa file for {aoi_file.name}. Please make "
            f"sure that the uoa file is named exactly as the corresponding aoi file and "
            f"that it is in your data folder in a folder called 'custom_units_of_analysis'."
        )

    if "questions" in uoa_file.name:
        uoa_data = pd.read_csv(uoa_file, dtype={uoa_column_name: str})[
            [
                uoa_column_name,
                uoa_idx_colum_name,
                "char",
                "char_idx",
                "page",
                "question_image_version",
            ]
        ]
        uoa_data = uoa_data[
            uoa_data["question_image_version"] == "question_images_version_1"
        ]

        uoa_data = uoa_data[
            [uoa_column_name, uoa_idx_colum_name, "char", "char_idx", "page"]
        ]

    else:
        uoa_data = pd.read_csv(uoa_file, dtype={uoa_column_name: str})[
            [uoa_column_name, uoa_idx_colum_name, "char", "char_idx", "page"]
        ]

    aoi_data = pd.read_csv(aoi_file, dtype={uoa_column_name: str})

    uoa_data = uoa_data.sort_values(by=["page"], ascending=False).reset_index()
    aoi_data = aoi_data.sort_values(by=["page"], ascending=False).reset_index()

    uoa_chars = uoa_data["char"].tolist()

    if "questions" in uoa_file.name:
        aoi_chars = aoi_data[
            aoi_data["question_image_version"] == "question_images_version_1"
        ]["char"].tolist()
    else:
        aoi_chars = aoi_data["char"].tolist()

    if len(uoa_data) != len(aoi_data):
        for line in difflib.unified_diff(aoi_chars, uoa_chars, lineterm=""):
            print(line)

    # check that the char and char_idx column match
    try:
        assert aoi_chars == uoa_chars
    except AssertionError:
        raise AssertionError(
            f"There is a mismatch in the character columns of {uoa_file.name} and it original aoi file. "
            f"They do not contain the same characters."
        )

    # join the segment and segment idx on page and char idx
    new_aois = aoi_data.merge(uoa_data, on=["page", "char_idx", "char"])

    # rename columns
    new_aois = new_aois.rename(
        {
            "unit_of_analysis_idx": "secondary_unit_of_analysis_idx",
            "unit_of_analysis": "secondary_unit_of_analysis",
            "unit_of_analysis_idx_in_line": "secondary_unit_of_analysis_idx_in_line",
            uoa_column_name: "unit_of_analysis",
            uoa_idx_colum_name: "unit_of_analysis_idx",
        },
        axis="columns",
    )

    # get the line index of the segments
    new_aois["unit_of_analysis_idx_in_line"] = (
        new_aois.groupby(["page", "line_idx"])["unit_of_analysis_idx"]
        .rank(method="dense")
        .astype(pd.Int64Dtype())
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
        "unit_of_analysis",
        "unit_of_analysis_idx",
        "unit_of_analysis_idx_in_line",
        "secondary_unit_of_analysis_idx",
        "secondary_unit_of_analysis_idx_in_line",
        "secondary_unit_of_analysis",
    ]

    new_aois = new_aois[col_order]
    new_aois.sort_values(by=["page", "line_idx", "char_idx"], inplace=True)
    new_aois.to_csv(aoi_file, index=False)