"""pEYEpline: API for the MultiplEYE preprocessing pipeline"""

from .answers.collect import collect_session_answers
from .answers.experiment_log_parser import parse_answers_from_logfile
from .answers.msg_parser import parse_answers_from_messages
from .checks.preflight import run_preflight_check
from .events.detect import detect_fixations, detect_saccades
from .events.properties import compute_event_properties
from .io.load import (
    load_gaze_data,
    load_reading_measures,
    load_trial_level_events_data,
    load_trial_level_raw_data,
)
from .io.save import (
    save_events_data,
    save_raw_data,
    save_reading_measures,
    save_scanpaths,
    save_session_metadata,
)
from .mapping.aoi import map_fixations_to_aois
from .metrics.calculate import calculate_reading_measures
from .psychometric_tests.preprocess_psychometric_tests import preprocess_all_sessions
from .scripts.prepare_language_folder import prepare_language_folder
from .scripts.restructure_psycho_tests import fix_psycho_tests_structure
from .signals.preprocess import preprocess_gaze

__all__ = [
    "calculate_reading_measures",
    "collect_session_answers",
    "compute_event_properties",  # needed in API? - not directly used in the preprocessing pipeline
    "detect_fixations",
    "detect_saccades",
    "fix_psycho_tests_structure",
    "load_gaze_data",
    "load_reading_measures",
    "load_trial_level_events_data",
    "load_trial_level_raw_data",
    "map_fixations_to_aois",
    "parse_answers_from_logfile",
    "parse_answers_from_messages",
    "prepare_language_folder",
    "preprocess_all_sessions",
    "preprocess_gaze",
    "run_preflight_check",
    "save_events_data",
    "save_raw_data",
    "save_reading_measures",
    "save_scanpaths",
    "save_session_metadata",
]
