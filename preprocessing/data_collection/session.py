from dataclasses import dataclass, field, asdict
from pathlib import Path

from preprocessing.data_collection.stimulus import Stimulus, LabConfig
from preprocessing.data_collection.trial import Trial


@dataclass
class Session:

    # general info
    participant_id: int

    session_identifier: str
    is_pilot: bool

    # paths and files
    session_folder_path: Path
    session_file_path: Path
    session_file_name: str
    asc_path: Path = field(default='unknown', init=False)

    # stimuli
    stimuli: list[Stimulus] = field(default='unknown', init=False)
    randomization_version: int = field(default='unknown', init=False)
    stimulus_folder_name: str = field(default='unknown', init=False)
    completed_stimuli_ids: list[int] = field(default='unknown', init=False)
    question_order: dict[str, list[str]] = field(default='unknown', init=False)
    stimulus_order_ids: list[int] = field(default='unknown', init=False)
    messages: list[dict[str, str]] = field(default='unknown', init=False)
    stimuli_trial_mapping: dict[str, str] = field(default='unknown', init=False)
    stimulus_start_end_ts: dict[str, list[str]] = field(default='unknown', init=False)

    logfile: str = field(default='unknown', init=False)
    interrupted: bool = field(default='unknown', init=False)
    lab_config: LabConfig = field(default='unknown', init=False)


    # stats
    total_reading_time: float = field(default='unknown', init=False)
    total_session_duration: float = field(default='unknown', init=False)
    obligatory_break_made: bool = field(default='unknown', init=False)
    num_optional_breaks_made: int = field(default='unknown', init=False)
    total_break_time: float = field(default='unknown', init=False)

    # calibrations & validations
    avg_comprehension_score: float = field(default='unknown', init=False)
    avg_calibration_error: float = field(default='unknown', init=False)
    num_calibrations: int = field(default='unknown', init=False)
    avg_validation_error: float = field(default='unknown', init=False)

    # sanity report
    sanity_report_path: Path = field(default='unknown', init=False)

    # preprocessing pm
    pm_gaze_path: Path = field(default='unknown', init=False)
    pm_gaze_metadata: dict = field(default='unknown', init=False)



    trials = list[Trial]

    def __iter__(self):
        for trial in self.trials:
            yield trial


    def __repr__(self):
        dict_repr = asdict(self)
        dict_repr.pop('stimuli')
        dict_repr.pop('logfile')
        dict_repr.pop('messages')

        # TODO: configure paths to be excluded from repr (i.e. make them relative and remove
        #  the user specific part
        # dict_repr.pop('trials')
        return dict_repr




