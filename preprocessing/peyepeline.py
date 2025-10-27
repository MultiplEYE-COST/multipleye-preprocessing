import logging
from pathlib import Path

from preprocessing.data_collection.stimulus import LabConfig

import pymovements as pm
import polars as pl


def load_gaze_data(asc_file: Path, lab_config: LabConfig, session_idf: str = '') -> pm.Gaze:
        gaze = pm.gaze.from_asc(
            asc_file,
            patterns=[
                r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_stimulus_(?P<stimulus>[^_]+_[^_]+_\d+)_(?P<screen>.+)",
                r"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_(?P<screen>familiarity_rating_screen_\d+|subject_difficulty_screen)",
                {"pattern": r"stop_recording_", "column": "trial", "value": None},
                {"pattern": r"stop_recording_", "column": "screen", "value": None},
                {
                    "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+_page_\d+",
                    "column": "activity",
                    "value": "reading",
                },
                {
                    "pattern": r"start_recording_(?:PRACTICE_)?trial_\d+_stimulus_[^_]+_[^_]+_\d+_question_\d+",
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
            ],
            trial_columns=["trial", "stimulus", "screen"],
            add_columns={'session': session_idf} if session_idf else None,
        )

        # Filter out data outside of trials
        # TODO: Also report time spent outside of trials
        gaze.frame = gaze.frame.filter(
            pl.col("trial").is_not_null() & pl.col("screen").is_not_null()
        )

        # Extract metadata from stimulus config and ASC file
        # TODO: Uncomment assertions when experiment implementation is fixed (https://www.sr-research.com/support/thread-9129.html)
        gaze.experiment = pm.Experiment(
            sampling_rate=gaze._metadata["sampling_rate"],
            screen_width_px=lab_config.image_resolution[0],
            screen_height_px=lab_config.image_resolution[1],
            screen_width_cm=lab_config.image_size_cm[0],
            screen_height_cm=lab_config.image_size_cm[1],
            distance_cm=lab_config.screen_distance_cm,
        )

        return gaze

def preprocess_gaze_data(
        gaze: pm.Gaze, sg_window_length: int = 50, sg_degree: int = 2
) -> None:
    # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188
    window_length = round(gaze.experiment.sampling_rate / 1000 * sg_window_length)
    if window_length % 2 == 0:  # Must be odd
        window_length += 1
    gaze.pix2deg()
    gaze.pos2vel("savitzky_golay", window_length=window_length, degree=sg_degree)
    gaze.detect("ivt")
    gaze.detect("microsaccades")


    # TODO pm: this is non-intuitive. Why are these properties?
    for property, kwargs, event_name in [
        ("location", dict(position_column="pixel"), "fixation"),
        ("amplitude", dict(), "saccade"),
        ("peak_velocity", dict(), "saccade"),
    ]:
        processor = pm.EventGazeProcessor((property, kwargs))
        new_properties = processor.process(
            gaze.events,
            gaze,
            identifiers=gaze.trial_columns,
            name=event_name,
        )
        join_on = gaze.trial_columns + ["name", "onset", "offset"]
        gaze.events.add_event_properties(new_properties, join_on=join_on)



    # TODO: AOI mapping
