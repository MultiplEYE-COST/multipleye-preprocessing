"""pEYEpline: API for the MultiplEYE preprocessing pipeline"""

from .metrics.calculate import calculate_reading_measures
from .signals.preprocess import preprocess_gaze
from .events.properties import compute_event_properties
from .events.detect import detect_fixations, detect_saccades
from .mapping.aoi import map_fixations_to_aois
from .io.save import (
    save_raw_data,
    save_events_data,
    save_scanpaths,
    save_session_metadata,
    save_reading_measures,
)
from .io.load import (
    load_gaze_data,
    load_trial_level_raw_data,
    load_trial_level_events_data,
    load_reading_measures,
)
from .answers.msg_parser import parse_answers_from_messages
from .answers.experiment_log_parser import parse_answers_from_logfile
from .answers.collect import collect_session_answers
from .checks.preflight import run_preflight_check

from .scripts.prepare_language_folder import prepare_language_folder
from .scripts.restructure_psycho_tests import fix_psycho_tests_structure

__all__ = [
    "prepare_language_folder",
    "fix_psycho_tests_structure",
    "preprocess_gaze",
    "compute_event_properties",  # needed in API? - not directly used in the preprocessing pipeline
    "calculate_reading_measures",
    "detect_fixations",
    "detect_saccades",
    "map_fixations_to_aois",
    "save_raw_data",
    "save_events_data",
    "save_scanpaths",
    "save_session_metadata",
    "save_reading_measures",
    "load_gaze_data",
    "load_trial_level_raw_data",
    "load_trial_level_events_data",
    "load_reading_measures",
    "parse_answers_from_messages",
    "parse_answers_from_logfile",
    "collect_session_answers",
    "run_preflight_check",
]
