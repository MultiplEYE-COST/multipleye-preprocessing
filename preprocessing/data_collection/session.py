from dataclasses import dataclass

from preprocessing.data_collection.trial import Trial


@dataclass
class Session:

    participant_id: int
    session_id: int
    stimulus_version: int
    stimulus_order: list[int]
    session_name = str
    question_order = dict[str, list[str]]
    session_folder_path = str
    completed_stimuli = list[str]
    logfile = str
    interrupted = bool
    total_reading_time = float
    avg_comprehension_score = float
    total_session_duration = float
    obligatory_break_made = bool
    num_optional_breaks_made = int
    total_break_time = float
    avg_calibration_error = float
    num_calibrations = int
    avg_validation_error = float


    trials = list[Trial]


