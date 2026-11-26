"""UOA importing and mapping of fixations to AOIs."""

import shutil
from pathlib import Path

import polars as pl
import pymovements as pm

from preprocessing.utils.logging import get_logger

from ..utils.fix_multipleye_aoi_files import fix_aoi_file, repair_word_labels_df
from ..utils.text_direction import is_vertical_script

__all__ = [
    "add_custom_uoa",
    "build_combined_text_stimulus",
    "enlarge_aois",
    "map_fixations_to_aois",
    "prepare_aoi_file",
]


def build_combined_text_stimulus(
    stimuli: list,
    script_direction: str = "ltr",
    use_correction_aois: bool = False,
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
    use_correction_aois : bool
        Use ``correction_text_stimulus`` when available. That table keeps the
        default space-delimited units even when the main AOIs use custom UoAs.

    Returns
    -------
    pm.stimulus.TextStimulus
        A text stimulus holding the stacked AOIs of all stimuli.
    """
    from ..config import settings

    all_aois = pl.DataFrame()
    for stimulus in stimuli:
        aoi_source = stimulus.text_stimulus
        if use_correction_aois:
            aoi_source = (
                getattr(stimulus, "correction_text_stimulus", None) or aoi_source
            )
        aoi = aoi_source.aois
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
        word_column="unit_of_analysis",
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


def add_custom_uoa(
    stimuli_folder: Path,
    aoi_file: Path,
    uoa_column_name,
    uoa_idx_column_name,
    uoa_file: Path | None = None,
) -> None:
    """
    Add custom units of analysis to the aoi file and rewrite the file. The units of analysis file should be in the respective stimulus folder.



    How to add it:
    - Merge the custom and the original aoi files on the char and char index as well as the page column!
    - check that all chars listed in both files exactly align. Index and char should be exactly the same.
    - for the questions add the segments to all question images versions and make sure the characters match. Only the coordinates should be different for the options

    Output:
    The AOI file keeps its name and geometry. The default unit columns are replaced
    by the custom unit columns, so ``unit_of_analysis`` and ``unit_of_analysis_idx``
    remain the only analysis columns in every collection.

    If any of the characters do not match, the pipeline will fail. If the UoA file is
    missing, the pipeline warns and keeps the default units. The default-fixed AOI
    files are preserved in the preparation provenance folder.

    """
    logger = get_logger()

    # Import aoi data. The default unit columns are replaced by the custom units,
    # so drop them before the join to avoid duplicate column names.
    aoi_data = pl.read_csv(aoi_file)
    aoi_data = aoi_data.drop(
        "unit_of_analysis",
        "unit_of_analysis_idx",
        "unit_of_analysis_idx_in_line",
        strict=False,
    )
    aoi_data = aoi_data.sort(by=["page", "char_idx"])

    # Import uoa data
    if uoa_file is None:
        uoa_file = stimuli_folder / "custom_units_of_analysis" / aoi_file.name

    if not uoa_file.exists():
        logger.warning(
            f"We could not find a matching uoa file for {aoi_file.name}. Please make "
            f"sure that the uoa file is named exactly as the corresponding aoi file and "
            f"that it is in the stimulus folder in a folder called 'custom_units_of_analysis'."
            f"Using default white-spaced units of analysis for {aoi_file.name}."
        )
        return

    if "questions" in uoa_file.name:
        uoa_data = pl.read_csv(uoa_file)[
            [
                uoa_column_name,
                uoa_idx_column_name,
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
            [uoa_column_name, uoa_idx_column_name, "char", "char_idx", "page"]
        ]

    else:
        uoa_data = pl.read_csv(uoa_file)[
            [uoa_column_name, uoa_idx_column_name, "char", "char_idx", "page"]
        ]

    uoa_data = uoa_data.sort(by=["page", "char_idx"])

    # Ensure that list of characters, character indices and pages matches exactly between files
    key_columns = ["char", "char_idx", "page"]
    uoa_key = uoa_data[key_columns]
    if "questions" in uoa_file.name:
        aoi_key = aoi_data[key_columns].filter(
            aoi_data["question_image_version"] == "question_images_version_1"
        )
    else:
        aoi_key = aoi_data[key_columns]

    try:
        assert aoi_key.equals(uoa_key)
    except AssertionError:
        msg = (
            f"The custom units of analysis file for the corresponding aoi file {aoi_file.name}, contains different characters, character indices or page numbers. "
            f"Please verify that the characters of the stimuli and their corresponding indices and pages match exactly in both files."
        )
        logger.exception(msg)
        raise

    uoa_data = uoa_data.rename(
        {
            uoa_column_name: "unit_of_analysis",
            uoa_idx_column_name: "unit_of_analysis_idx",
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

    # Custom UoA files may repeat inconsistent labels inside a unit. Repair them
    # with the same rule as the default units, using the merged unit indices.
    new_aois = repair_word_labels_df(new_aois)

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
    ]

    if "questions" in aoi_file.name:
        col_order.append("question_image_version")

    new_aois = new_aois[col_order]
    new_aois = new_aois.sort(by=["page", "line_idx", "char_idx"])
    new_aois.write_csv(aoi_file)


def prepare_aoi_file(
    aoi_file: Path,
    custom_uoa_file: Path | None = None,
    uoa_column_name: str | None = None,
    uoa_idx_column_name: str | None = None,
    default_copy_path: Path | None = None,
) -> None:
    """Apply the default fixes and optional custom units to one AOI file in place.

    The function starts from a raw or freshly split AOI file. It never reapplies
    custom units to an already prepared file. ``default_copy_path`` receives the
    default-fixed file before custom units are merged, so fixation correction can
    use a UoA-independent AOI table.
    """
    fix_aoi_file(aoi_file)
    if default_copy_path is not None:
        default_copy_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(aoi_file, default_copy_path)

    if custom_uoa_file is None:
        return
    if not custom_uoa_file.exists():
        get_logger().warning(
            f"Custom UoA file not found for {aoi_file.name}: {custom_uoa_file}. "
            "Keeping the default space-delimited units."
        )
        return

    add_custom_uoa(
        stimuli_folder=aoi_file.parent,
        aoi_file=aoi_file,
        uoa_column_name=uoa_column_name,
        uoa_idx_column_name=uoa_idx_column_name,
        uoa_file=custom_uoa_file,
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
