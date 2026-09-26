from pathlib import Path

import pandas as pd
import polars as pl

from ..utils.logging import get_logger

logger = get_logger()


def remap_space_to_following_word(aoi_file_path: str | Path) -> None:
    """
    By default, white space is mapped to the previous word. This is bad practice as the space is typically read as
    part of the next word in reading direction. This function remaps the space to the next word.

    The file is changed and then rewritten to the same path.

    :param aoi_file_path: path to the AOI file to be remapped
    """
    aoi_df = pd.read_csv(aoi_file_path)

    # Identify rows where the 'word' column is empty and the char is a space
    # then increase the word index of just the space by 1 to match the following word
    # then write the modified dataframe back to the same file
    found_space = False
    for i in range(len(aoi_df) - 1):
        if pd.isna(aoi_df.loc[i, "word"]) and aoi_df.loc[i, "char"] == " ":
            if aoi_df.loc[i, "word_idx"] == 1 and not found_space:
                logger.info(f"Aoi file has already been remapped: {aoi_file_path}")
                return
            aoi_df.loc[i, "word_idx"] = aoi_df.loc[i + 1, "word_idx"]
            aoi_df.loc[i, "word_idx_in_line"] = aoi_df.loc[i + 1, "word_idx_in_line"]
            found_space = True

    logger.debug(f"Remapped space to following word for AOI file: {aoi_file_path}")

    aoi_df.to_csv(aoi_file_path, index=False)


def repair_word_labels(aoi_file_path: str | Path) -> None:
    """
    Ensure consistent word string labels within each word index group.

    This function normalizes the `word` column so that all characters
    belonging to the same (`trial`, `page`, `line_idx`, `word_idx`)
    share an identical word label.

    Specifically:
    - Whitespace-only or empty `word` entries are treated as missing.
    - Missing values are forward- and backward-filled within each
      word group.
    - The `word_idx` column is not modified.

    This is primarily used to assign a proper word label to characters
    such as inter-word spaces that are already associated with a valid
    `word_idx`, ensuring downstream processing operates on consistent
    word-level labels.

    No rows are added or removed, and `word_idx` assignments remain unchanged.

    The file is changed and then rewritten to the same path.


    Parameters
    ----------
    aoi_file_path : Path | str
        Character-level AOI table containing at least:
        - `word_idx`
        - `word`
        - `char_idx_in_line`
        - `trial`, `page`, `line_idx`

    """

    df = pl.read_csv(aoi_file_path)

    group_cols = ["page", "line_idx", "word_idx"]

    df = (
        df.sort(group_cols + ["char_idx_in_line"])
        .with_columns(
            pl.when(pl.col("word").is_null() | (pl.col("word").str.strip_chars() == ""))
            .then(None)
            .otherwise(pl.col("word"))
            .alias("_word_tmp")
        )
        .with_columns(
            pl.col("_word_tmp")
            .forward_fill()
            .backward_fill()
            .over(
                group_cols
            )  # ensures that the label is only propagated within the same word group
            .alias("word")
        )
        .drop("_word_tmp")
    )

    df.write_csv(aoi_file_path)

    logger.debug(f"Filled missing word labels in AOI file: {aoi_file_path}")
