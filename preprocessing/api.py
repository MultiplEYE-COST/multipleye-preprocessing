"""pEYEpline: API for the MultiplEYE preprocessing pipeline"""

from .signals.preprocess import preprocess_gaze
from .events.properties import compute_event_properties
from .events.detect import detect_fixations, detect_saccades
from .mapping.aoi import map_fixations_to_aois
from .io.save import (
    save_raw_data,
    save_events_data,
    save_scanpaths,
    save_session_metadata,
)
from .io.load import (
    load_gaze_data,
    load_trial_level_raw_data,
    load_trial_level_events_data,
)

__all__ = [
    "preprocess_gaze",
    "compute_event_properties",  # needed in API? - not directly used in the preprocessing pipeline
    "detect_fixations",
    "detect_saccades",
    "map_fixations_to_aois",
    "save_raw_data",
    "save_events_data",
    "save_scanpaths",
    "save_session_metadata",
    "load_gaze_data",
    "load_trial_level_raw_data",
    "load_trial_level_events_data",
]
