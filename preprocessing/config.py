from __future__ import annotations

import logging
import os
import re
import warnings
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class Settings:
    """Settings for MultiplEYE preprocessing pipeline."""

    def __init__(self) -> None:
        # These settings can be overridden by a YAML file.

        #: Name of the data collection (e.g., 'ME_EN_UK_LON_LAB1_2025').
        self.DATA_COLLECTION_NAME: str | None = None

        #: Whether to include sessions from the pilot folder.
        self.INCLUDE_PILOTS: bool = False

        #: List of session identifiers to explicitly exclude from processing.
        self.EXCLUDE_SESSIONS: list[str] = []

        #: List of session identifiers to explicitly include. If not empty, only these are processed.
        self.INCLUDE_SESSIONS: list[str] = []

        #: The expected sampling rate of the eye tracker in Hertz.
        self.EXPECTED_SAMPLING_RATE_HZ: int = 1000

        # --- FOLDER AND FILE NAMES ---

        #: Columns that uniquely identify a trial.
        self.TRIAL_COLS = ["trial", "stimulus", "page"]

        #: Subfolder name for raw data.
        self.RAW_DATA_FOLDER = Path("raw_data/")

        #: Subfolder name for fixation data.
        self.FIXATIONS_FOLDER = Path("fixations/")

        #: Subfolder name for saccade data.
        self.SACCADES_FOLDER = Path("saccades/")

        #: Subfolder name for scanpath data.
        self.SCANPATHS_FOLDER = Path("scanpaths/")

        #: Column name for the trial identifier.
        self.TRIAL_COL = "trial"

        #: Column name for the page identifier.
        self.PAGE_COL = "page"

        #: Column name for the stimulus identifier.
        self.STIMULUS_COL = "stimulus"

        #: Column name for the word index.
        self.WORD_IDX_COL = "word_idx"

        #: Column name for the character index.
        self.CHAR_IDX_COL = "char_idx"

        # --- SANITY CHECK THRESHOLDS ---

        #: Acceptable range [min, max] for the number of calibrations in a session.
        self.ACCEPTABLE_NUM_CALIBRATIONS = [3, 30]

        #: Acceptable range (min, max) for the number of validations in a session.
        self.ACCEPTABLE_NUM_VALIDATION = (13, 30)

        #: Acceptable range (min, max) for average validation accuracy scores.
        self.ACCEPTABLE_AVG_VALIDATION_SCORES = (0.0, 0.8)

        #: Acceptable range (min, max) for maximum validation accuracy scores.
        self.ACCEPTABLE_MAX_VALIDATION_SCORES = (0.0, 1.5)

        #: List of acceptable validation error strings.
        self.ACCEPTABLE_VALIDATION_ERRORS = ["GOOD"]

        #: Acceptable range (min, max) for data loss ratio (0.0 to 1.0).
        self.ACCEPTABLE_DATA_LOSS_RATIOS = (0.0, 0.10)

        #: Acceptable range (min, max) for recording duration in seconds.
        self.ACCEPTABLE_RECORDING_DURATIONS = (600, 7200)

        #: Expected number of practice trials.
        self.ACCEPTABLE_NUM_PRACTICE_TRIALS = 2

        #: Expected minimum number of experimental trials.
        self.ACCEPTABLE_NUM_TRIALS = 10

        # --- DATA CHARACTERISTICS ---

        #: Labels used for eye tracking.
        self.TRACKED_EYE = ["L", "R", "RIGHT", "LEFT"]

        #: Event name for fixations.
        self.FIXATION = "fixation"

        #: Event name for saccades.
        self.SACCADE = "saccade"

        # --- REGULAR EXPRESSIONS ---

        #: Regex to parse generic messages from eye tracker logs.
        self.MESSAGE_REGEX = re.compile(
            r"MSG\s+(?P<timestamp>\d+[.]?\d*)\s+(?P<message>.*)"
        )

        #: Regex to identify the start of a recording for a trial/page.
        self.START_RECORDING_REGEX = re.compile(
            r"MSG\s+(?P<timestamp>\d+)\s+(?P<type>start_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)"
        )

        #: Regex to identify the stop of a recording for a trial/page.
        self.STOP_RECORDING_REGEX = re.compile(
            r"MSG\s+(?P<timestamp>\d+)\s+(?P<type>stop_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)"
        )

        #: Glob pattern for raw data files.
        self.RAW_DATA_FILE_GLOB = "*_raw_data.csv"

        #: Glob pattern for event data files.
        self.EVENT_DATA_FILE_GLOB = "*_{event_type}.csv"

        #: Regex to extract the stimulus order version from ASC files.
        self.STIMULUS_ORDER_VERSION_REGEX = re.compile(
            r"MSG\s+\d+\s+stimulus_order_version:\s+(?P<version_num>\d\d?\d?)\n"
        )

        #: Regex to extract stimulus order version from logfiles.
        self.LOGFILE_ORDER_VERSION_REGEX = re.compile(
            r"(STIMULUS_ORDER_VERSION_)(?P<order_version>\d+)"
        )

        #: Regex to extract trial and stimulus info from raw data file names.
        self.RAW_DATA_FILENAME_REGEX = r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_raw_data"

        #: Regex to extract trial and stimulus info from event data file names.
        self.EVENT_DATA_FILENAME_REGEX = r".+_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_{event_type}.csv"

        # --- HARDWARE AND STIMULI MAPPINGS ---

        #: Mapping of eye tracker brands to known model names.
        self.EYETRACKER_NAMES = {
            "eyelink": [
                "EyeLink 1000 Plus",
                "EyeLink II",
                "EyeLink 1000",
                "EyeLink Portable Duo",
            ],
        }

        #: Mapping of stimulus names to internal numeric IDs.
        self.STIMULUS_NAME_MAPPING = {
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

        # --- PSYCHOMETRIC TEST DIRECTORIES ---

        #: Subfolder name for Working Memory Capacity tests.
        self.PSYM_LWMC_DIR = Path("WMC/")

        #: Subfolder name for Rapid Automatized Naming tests.
        self.PSYM_RAN_DIR = Path("RAN/")

        #: Subfolder name for Stroop and Flanker tests.
        self.PSYM_STROOP_FLANKER_DIR = Path("Stroop_Flanker/")

        #: Subfolder name for PLAB tests.
        self.PSYM_PLAB_DIR = Path("PLAB/")

        #: Subfolder name for WikiVocab tests.
        self.PSYM_WIKIVOCAB_DIR = Path("WikiVocab/")

        # --- GAZE PATTERNS AND EVENT PROPERTIES ---

        #: Patterns used by pymovements to parse ASC files and assign columns.
        self.GAZE_PATTERNS = [
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_stimulus_(?P<stimulus>[^_]+_[^_]+_\d+(\.0)?)_(?P<page>.+)",
            r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<page>familiarity_rating_screen_\d+|subject_difficulty_screen)",
            {"pattern": r"stop_recording_", "column": "trial", "value": None},
            {"pattern": r"stop_recording_", "column": "page", "value": None},
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+(\.0)?_page_\d+",
                "column": "activity",
                "value": "reading",
            },
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+(\.0)?_question_\d+",
                "column": "activity",
                "value": "question",
            },
            {
                "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_(familiarity_rating_screen_\d+|subject_difficulty_screen)",
                "column": "activity",
                "value": "rating",
            },
            {"pattern": r"stop_recording_", "column": "activity", "value": None},
            {
                "pattern": r"start_recording_PRACTICE_trial_",
                "column": "practice",
                "value": True,
            },
            {
                "pattern": r"start_recording_trial_",
                "column": "practice",
                "value": False,
            },
            {"pattern": r"stop_recording_", "column": "practice", "value": None},
        ]

        #: Properties to compute for each event type.
        self.EVENT_PROPERTIES = {
            self.FIXATION: [
                ("location", {"position_column": "pixel"}),
                ("dispersion", {}),
            ],
            self.SACCADE: [
                ("amplitude", {}),
                ("peak_velocity", {}),
                ("dispersion", {}),
            ],
        }

        self._loaded = False
        self._loading = False
        self._repo_root = Path(__file__).parent.parent
        self._initialized = True

    @property
    def THIS_REPO(self) -> Path:
        return self._repo_root

    def _ensure_loaded(self) -> None:
        if not self._loaded and not self._loading:
            self.load()

    def load(self, path: str | Path | None = None) -> None:
        """Load settings from various sources with defined precedence."""
        self._loading = True
        try:
            if path:
                self.load_from_yaml(path)
                return

            env_path = os.getenv("MULTIPLEYE_CONFIG")
            if env_path:
                self.load_from_yaml(env_path)
                return

            cwd_default = Path.cwd() / "multipleye_settings_preprocessing.yaml"
            if cwd_default.exists():
                self.load_from_yaml(cwd_default)
                return

            legacy_path = self._repo_root / "multipleye_settings_preprocessing.yaml"
            if legacy_path.exists():
                warnings.warn(
                    f"Loading config from legacy path: {legacy_path}. "
                    "This behavior is deprecated and will be removed in a future release. "
                    "Please move your config to the current working directory or specify it via "
                    "--config_path or MULTIPLEYE_CONFIG env var.",
                    DeprecationWarning,
                    stacklevel=2,
                )
                self.load_from_yaml(legacy_path)
                return

            self._loaded = True
        finally:
            self._loading = False

    def load_from_yaml(self, path: str | Path) -> None:
        """Load settings from a YAML file."""
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        logger.info(f"Loading config from: {path}")

        with open(path, "r") as f:
            user_configs = yaml.safe_load(f)

        if user_configs:
            self.update(user_configs)

        self._validate()
        self._loaded = True

    def update(self, config_dict: dict[str, Any]) -> None:
        """Update settings from a dictionary."""
        for key, value in config_dict.items():
            upper_key = key.upper()
            if upper_key in self.__dict__:
                setattr(self, upper_key, value)
            else:
                # Allow setting new attributes or lowercase if they exist
                setattr(self, key, value)

    def _validate(self) -> None:
        """Validate required settings."""
        if self._loading:  # Skip validation during initial loading of parts
            return
        if not self.DATA_COLLECTION_NAME:
            raise ValueError("DATA_COLLECTION_NAME is required in settings.")

    def __setattr__(self, name: str, value: Any) -> None:
        if not name.startswith("_"):
            # Check if this is an initial set (in __init__) or a later change
            if hasattr(self, name):
                old_value = getattr(self, name)
                if old_value != value:
                    logger.info(f"Changing setting {name}: {old_value} -> {value}")
            else:
                # If we are not in _loading and not in __init__, it's a new attribute, using a flag
                if hasattr(self, "_initialized") and self._initialized:
                    logger.info(f"Setting new attribute {name}: {value}")

        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        # Avoid recursion for private attributes
        if name.startswith("_"):
            raise AttributeError(name)

        # For legacy compatibility and to ensure loading
        if name in [
            "DATASET_DIR",
            "OUTPUT_DIR",
            "LANGUAGE",
            "COUNTRY",
            "CITY",
            "LAB",
            "YEAR",
            "PSYCHOMETRIC_TESTS_DIR",
            "PSYM_CORE_DATA",
            "PSYM_PARTICIPANT_CONFIGS",
        ]:
            self._ensure_loaded()
            if self.DATA_COLLECTION_NAME is None:
                # If we are here and it's None, it means no config was found
                raise ValueError(
                    "Settings not initialized: DATA_COLLECTION_NAME is None. "
                    "Please load a config file."
                )

            parts = self.DATA_COLLECTION_NAME.split("_")
            if len(parts) < 6:
                language = parts[1] if len(parts) > 1 else ""
                country = parts[2] if len(parts) > 2 else ""
                lab = parts[4] if len(parts) > 4 else ""
            else:
                _, language, country, _, lab, _ = parts

            if name == "DATASET_DIR":
                return self._repo_root / "data" / self.DATA_COLLECTION_NAME
            if name == "OUTPUT_DIR":
                return self._repo_root / "preprocessed_data" / self.DATA_COLLECTION_NAME
            if name == "LANGUAGE":
                return language
            if name == "COUNTRY":
                return country
            if name == "CITY":
                return parts[3] if len(parts) > 3 else ""
            if name == "LAB":
                return lab
            if name == "YEAR":
                return parts[5] if len(parts) > 5 else ""
            if name == "PSYCHOMETRIC_TESTS_DIR":
                return (
                    self._repo_root / "data" / self.DATA_COLLECTION_NAME
                ) / "psychometric-tests-sessions"
            if name == "PSYM_CORE_DATA":
                return (
                    (self._repo_root / "data" / self.DATA_COLLECTION_NAME)
                    / "psychometric-tests-sessions"
                    / "core_data"
                )
            if name == "PSYM_PARTICIPANT_CONFIGS":
                return (
                    (self._repo_root / "data" / self.DATA_COLLECTION_NAME)
                    / "psychometric-tests-sessions"
                    / "core_data"
                    / f"participant_configs_{language}_{country}_{lab}"
                )

        self._ensure_loaded()

        # uppercase for case-insensitivity, check in __dict__
        upper_name = name.upper()
        if upper_name in self.__dict__:
            return self.__dict__[upper_name]

        if name in self.__dict__:
            return self.__dict__[name]

        raise AttributeError(
            f"'{type(self).__name__}' object has no attribute '{name}'"
        )


settings = Settings()
