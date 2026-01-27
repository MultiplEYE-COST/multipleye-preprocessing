"""Constants for MultiplEYE preprocessing pipeline

The variables here are considered fixed.
Parameters in the `config.py` file are considered user-configurable.
"""

import re
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

# Event/type strings
FIXATION = "fixation"
SACCADE = "saccade"

# Regular Expressions
MESSAGE_REGEX = re.compile(r"MSG\s+(?P<timestamp>\d+[.]?\d*)\s+(?P<message>.*)")
START_RECORDING_REGEX = re.compile(
    r"MSG\s+(?P<timestamp>\d+)\s+(?P<type>start_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)"
)
STOP_RECORDING_REGEX = re.compile(
    r"MSG\s+(?P<timestamp>\d+)\s+(?P<type>stop_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)"
)

# Data collection
EYETRACKER_NAMES = {
    "eyelink": [
        "EyeLink 1000 Plus",
        "EyeLink II",
        "EyeLink 1000",
        "EyeLink Portable Duo",
    ],
}
STIMULUS_NAME_MAPPING = {
    "PopSci_MultiplEYE": 1,
    "Ins_HumanRights": 2,
    "Ins_LearningMobility": 3,
    "Lit_Alchemist": 4,
    "Lit_MagicMountain": 6,
    "Lit_Solaris": 8,
    "Lit_BrokenApril": 9,
    "Arg_PISACowsMilk": 10,
    "Arg_PISARapaNui": 11,
    "PopSci_Caveman": 12,
    "Enc_WikiMoon": 13,
    "Lit_NorthWind": 7,
}
