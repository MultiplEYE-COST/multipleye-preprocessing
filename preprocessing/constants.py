"""Constants for MultiplEYE preprocessing pipeline

The variables here are considered fixed.
Parameters in the `config.py` file are considered user-configurable.
"""

import re
from pathlib import Path

import yaml

THIS_REPO = Path(__file__).parent.parent

# USER CONFIGURABLE SETTINGS
# load from .yaml file
user_configs = yaml.safe_load(
    open(THIS_REPO / "multipleye_settings_preprocessing.yaml")
)
DATA_COLLECTION_NAME = user_configs["data_collection_name"]
DATASET_DIR = THIS_REPO / "data" / user_configs["data_collection_name"]

_, LANGUAGE, COUNTRY, CITY, LAB, YEAR = user_configs["data_collection_name"].split("_")

OUTPUT_DIR = THIS_REPO / "preprocessed_data" / user_configs["data_collection_name"]

INCLUDE_PILOTS = user_configs["include_pilots"]
EXCLUDE_SESSIONS = user_configs["exclude_sessions"]
INCLUDE_SESSIONS = user_configs["include_sessions"]

EXPECTED_SAMPLING_RATE_HZ = user_configs["expected_sampling_rate_hz"]

# GENERAL SETTINGS
TRIAL_COLS = ["trial", "stimulus", "page"]

## Folder names
RAW_DATA_FOLDER = Path("raw_data/")
FIXATIONS_FOLDER = Path("fixations/")
SACCADES_FOLDER = Path("saccades/")
SCANPATHS_FOLDER = Path("scanpaths/")

### Psychometric Tests Sessions
PSYCHOMETRIC_TESTS_DIR = DATASET_DIR / "psychometric-tests-sessions"
PSYM_CORE_DATA = PSYCHOMETRIC_TESTS_DIR / "core_data"
PSYM_PARTICIPANT_CONFIGS = (
    PSYM_CORE_DATA / f"participant_configs_{LANGUAGE}_{CITY}_{LAB}"
)

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
MESSAGE_REGEX_NEW = re.compile(r"(?P<message>.*)")
START_RECORDING_REGEX_NEW = re.compile(
    r"(?P<type>start_recording)_(?P<trials>(PRACTICE_)?trial_\d\d?)_stimulus_(?P<stimulus_name>\S*?_\S*?)_(?P<stimulus_id>\d+)_(?P<pages>\S*)"
)
STOP_RECORDING_REGEX_NEW = re.compile(
    r"(?P<type>stop_recording)_(?P<trials>(PRACTICE_)?trial_\d\d?)_stimulus_(?P<stimulus_name>\S*?_\S*?)_(?P<stimulus_id>\d+)_(?P<pages>\S*)"
)
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
        "Eyelink 1000 Plus",
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

MESSAGES = {
    "other_screens": [
        "welcome_screen",
        "informed_consent_screen",
        "start_experiment",
        "stimulus_order_version",
        "showing_instruction_screen",
        "camera_setup_screen",
        "practice_text_starting_screen",
        "transition_screen",
        "final_validation",
        "show_final_screen",
        "optional_break_screen",
        "fixation_trigger:skipped_by_experimenter",
        "fixation_trigger:experimenter_calibration_triggered",
        "recalibration",
        "empty_screen",
        "obligatory_break",
        "optional_break",
    ],
    "break_msgs": [
        "optional_break_duration",
        "optional_break_end",
        "optional_break_",
        "obligatory_break_duration",
        "obligatory_break_endobligatory_break",
    ],
}

BREAK_REGEX = re.compile("|".join(map(re.escape, MESSAGES["break_msgs"])))
OTHER_SCREENS_REGEX = re.compile("|".join(map(re.escape, MESSAGES["other_screens"])))
