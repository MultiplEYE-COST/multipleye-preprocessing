"""Constants for MultiplEYE preprocessing pipeline

The variables here are considered fixed.
Parameters in the `config.py` file are considered user-configurable.
"""

from pathlib import Path

# GENERAL SETTINGS
TRIAL_COLS = ["trial", "stimulus", "page"]

### Psychometric Tests Sessions

#### Tests - folder names inside PSYCHOMETRIC_TESTS_DIR folder / per-participant folder after restructuring
PSYM_LWMC_DIR = Path("WMC/")
PSYM_RAN_DIR = Path("RAN/")
PSYM_STROOP_FLANKER_DIR = Path("Stroop_Flanker/")
PSYM_PLAB_DIR = Path("PLAB/")
PSYM_WIKIVOCAB_DIR = Path("WikiVocab/")

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

TRACKED_EYE = ["L", "R", "RIGHT", "LEFT"]
