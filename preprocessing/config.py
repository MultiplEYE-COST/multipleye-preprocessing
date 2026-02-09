"""Settings for MultiplEYE preprocessing pipeline.

The variables in this file are considered as user-configurable.
Parameters in the `constants.py` file are considered fixed.
"""

from pathlib import Path

# PREPROCESSING PARAMETERS

## Data folder and structure
BASE_DATA_DIR = Path("~/code/multipleye-preprocessing/data/").expanduser()
DATA_COLLECTION_ID = "MultiplEYE_SQ_CH_Zurich_1_2025"
DATASET_DIR = BASE_DATA_DIR / DATA_COLLECTION_ID
DEFAULT_STIMULI_DIR = DATASET_DIR / f"stimuli_{DATASET_DIR.name}"
### Psychometric Tests Sessions
PSYCHOMETRIC_TESTS_DIR = DATASET_DIR / "psychometric-tests-sessions"
PSYM_CORE_DATA = PSYCHOMETRIC_TESTS_DIR / "core_data"
PSYM_PARTICIPANT_CONFIGS = PSYM_CORE_DATA / "participant_configs_SQ_CH_1"

## Fixation detection (Savitzky-Golay)
SG_WINDOW_LENGTH = 50  # milliseconds
SG_DEGREE = 2

# TODO change this: this depends on the ET device and should be read from the metadata
EXPECTED_SAMPLING_RATE_HZ = 1000  # Hz
