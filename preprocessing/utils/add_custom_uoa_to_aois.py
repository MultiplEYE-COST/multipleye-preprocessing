"""
In order to make the MultiplEYE eye-tracking data more meaningful to use for different languages, there is the option
of adding custom units-of-analysis (UOAs) to the areas of interest (AOIs) defined in the stimulus. By default, the
aois are defined as words deliemited by white space and in additional as characters. However, characters are rarely used
for analyses and too small, and in some cases words are not the most meaningful unit of analysis (e.g., in agglutinative
languages). In order to make the naming consistent all word aois will be called "unit-of-analysis" aois, regardless of the
custom definition.
This script:
- loads all MultiplEYE aoi files and renames the columns for publication
- adds custom uoa aois from a provided from custom files for each language
"""
from pathlib import Path

import pandas as pd

from preprocessing import config


def refactor_aoi_file(data_collection_name: str) -> None:
    """
    Refactor the aoi files for a given data collection to have consistent naming conventions.
    If necessary, add the custom uoa aois for the given language.
    :param data_collection_name:
    """

    _, language, country, city, lab, year = data_collection_name.split("_")

    aoi_dir_path = config.DEFAULT_STIMULI_DIR / f"aoi_stimuli_{language.lower()}_{country.lower()}_{lab}"

    aoi_files = Path(aoi_dir_path).glob("*.csv")
    for aoi_file in aoi_files:
        # load the aoi file
        aoi_data = pd.read_csv(aoi_file)

        # rename columns
        aoi_data = aoi_data.rename(
            {
                "word_idx": "unit_of_analysis_idx",
                "word": "unit_of_analysis",
            }
        )

        # save the refactored aoi filed
        aoi_data.write_csv(aoi_file)

    # for a few languages, custom uoa aois are needed
    if language == "ZH":
        _add_custom_uoa_chinese()


def _add_custom_uoa_chinese():
    pass