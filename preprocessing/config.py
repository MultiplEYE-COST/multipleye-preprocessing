import math
from pathlib import Path

infinity = math.inf

# GENERAL SETTINGS
TRIAL_COLS = ["trial", "stimulus", "page"]


# PREPROCESSING PARAMETERS

## Data folder and structure
DATA_DIR = Path("~/code/multipleye-preprocessing/data/").expanduser()
DATASET_DIR = DATA_DIR / 'MultiplEYE_SQ_CH_Zurich_1_2025'
### Psychometric Tests Sessions
PSYCHOMETRIC_TESTS_DIR = DATASET_DIR / 'psychometric-tests-sessions'
PSYM_CORE_DATA = PSYCHOMETRIC_TESTS_DIR / 'core_data'
PSYM_PARTICIPANT_CONFIGS = PSYM_CORE_DATA / 'participant_configs_SQ_CH_1'
#### Tests - folder names inside PSYCHOMETRIC_TESTS_DIR folder / per-participant folder after restructuring
PSYM_LWMC_DIR = Path('WMC/')
PSYM_RAN_DIR = Path('RAN/')
PSYM_STROOP_FLANKER_DIR = Path('Stroop_Flanker/')
PSYM_PLAB_DIR = Path('PLAB/')
PSYM_WIKIVOCAB_DIR = Path('WikiVocab/')


## Fixation detection (Savitzky-Golay)
SG_WINDOW_LENGTH = 50  # milliseconds
SG_DEGREE = 2

# SANITY CHECKS
## Acceptable thresholds for sanity checks
ACCEPTABLE_NUM_CALIBRATIONS = [3, 30]
ACCEPTABLE_NUM_VALIDATION = (13, 30)
ACCEPTABLE_AVG_VALIDATION_SCORES = (0.0, 0.8)
ACCEPTABLE_MAX_VALIDATION_SCORES = (0.0, 1.5)
ACCEPTABLE_VALIDATION_ERRORS = ["GOOD"]
ACCEPTABLE_DATA_LOSS_RATIOS = (0.0, 0.10)
ACCEPTABLE_RECORDING_DURATIONS = (600, 7200)  # seconds
ACCEPTABLE_NUM_PRACTICE_TRIALS = 2
ACCEPTABLE_NUM_TRIALS = 10

# TODO change this: this depends in the ET device and should be read from the metadata
EXPECTED_SAMPLING_RATE_HZ = 1000  # Hz

TRACKED_EYE = ["L", "R", "RIGHT", "LEFT"]
