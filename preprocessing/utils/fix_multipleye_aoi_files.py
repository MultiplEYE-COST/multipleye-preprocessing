from pathlib import Path

import pandas as pd

from ..utils.logging import get_logger

logger = get_logger(__name__)


def remap_space_to_following_word(aoi_file_path: str | Path) -> None:
    aoi_df = pd.read_csv(aoi_file_path)

    # Identify rows where the 'word' column is empty and the char is a space
    # then increase the word index of just the space by 1 to match the following word
    # then write the modified dataframe back to the same file
    found_space = False
    for i in range(len(aoi_df) - 1):
        if pd.isna(aoi_df.loc[i, "word"]) and aoi_df.loc[i, "char"] == " ":
            if aoi_df.loc[i, "word_idx"] == 1 and not found_space:
                print("not chaning aoi file")
                logger.info(f"Aoi file has already been remapped: {aoi_file_path}")
                return
            aoi_df.loc[i, "word_idx"] = aoi_df.loc[i + 1, "word_idx"]
            aoi_df.loc[i, "word_idx_in_line"] = aoi_df.loc[i + 1, "word_idx_in_line"]
            found_space = True

    logger.info(f"Remapped space to following word for AOI file: {aoi_file_path}")

    aoi_df.to_csv(aoi_file_path, index=False)
