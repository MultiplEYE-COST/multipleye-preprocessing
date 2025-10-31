import json
from pathlib import Path

from pymovements.stimulus import TextStimulus

from preprocessing.data_collection.stimulus import LabConfig, Stimulus

import pymovements as pm
import polars as pl


def load_gaze_data(
        asc_file: Path,
        lab_config: LabConfig,
        session_idf: str,
        save: bool = False,
        output_dir: str = '',
) -> pm.Gaze:
    """

    :param output_dir:
    :param asc_file:
    :param lab_config:
    :param session_idf:
    :param save:
    :return:
    """

    if save and not output_dir:
        raise ValueError('Please specify an output directory if you want to save the gaze data.')

    output_dir = Path(output_dir)

    trial_cols = ["trial", "stimulus", "screen"]

    # check if gaze already exists, unless we want to save it, in that case, we recreate and save it
    gaze_path = output_dir / f'{session_idf}_samples.csv'

    if gaze_path.exists():
        gaze_frame = pl.read_csv(gaze_path)
        gaze = pm.Gaze(
            gaze_frame,
            trial_columns=trial_cols,
            pixel_columns=['pixel_x', 'pixel_y'],
        )

        # TODO pm I would like to load the metadata automatically (and also save it)
        with open(output_dir / 'gaze_metadata.json', 'r', encoding='utf8') as f:
            gaze_metadata = json.load(f)

        gaze._metadata = gaze_metadata

    else:
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
            trial_columns=trial_cols,
            add_columns={'session': session_idf},
        )

        # Filter out data outside of trials
        # TODO: Also report time spent outside of trials
        gaze.frame = gaze.frame.filter(
            pl.col("trial").is_not_null() & pl.col("screen").is_not_null()
        )

    # Extract metadata from stimulus config and ASC file
    gaze.experiment = pm.Experiment(
        sampling_rate=gaze._metadata["sampling_rate"],
        screen_width_px=lab_config.image_resolution[0],
        screen_height_px=lab_config.image_resolution[1],
        screen_width_cm=lab_config.image_size_cm[0],
        screen_height_cm=lab_config.image_size_cm[1],
        distance_cm=lab_config.screen_distance_cm,
    )

    if save:
        save_gaze_data(gaze, gaze_path, metadata_dir=output_dir)

    return gaze

def save_gaze_data(
        gaze: pm.Gaze,
        gaze_path: Path = '',
        events_path: Path = '',
        metadata_dir: Path = '',
) -> None:



    if gaze_path:
        gaze.save_samples(path=gaze_path)
    if events_path:
        gaze.save_events(path=events_path)
    if metadata_dir:
        # TODO pm: this saves the experiment metadata, but there is a lot more metadata as a gaze property,
        #  this should also be saved
        gaze.save(dirpath=metadata_dir, save_events=False, save_samples=False)

        # TODO pm,
        #  why can I only save the experiment metadata through this strange method?
        metadata = gaze._metadata
        metadata['datetime'] = str(metadata['datetime'])
        # TODO pm: I'd like to save my metadata without having to access a protected argument
        with open(metadata_dir / "gaze_metadata.json", "w", encoding='utf8') as f:
            json.dump(metadata, f)

def preprocess_gaze_data(
        gaze: pm.Gaze,
        sg_window_length: int = 50,
        sg_degree: int = 2,
        save: bool = False,
        output_dir: str | Path = '',
        session_idf: str | Path = '',
) -> None:
    # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188
    window_length = round(gaze.experiment.sampling_rate / 1000 * sg_window_length)

    if window_length % 2 == 0:  # Must be odd
        window_length += 1

    gaze.pix2deg()
    gaze.pos2vel("savitzky_golay", window_length=window_length, degree=sg_degree)

    # TODO pm: I think the problem here is that is is not clear what ivt is.. it is very hidden, what happens
    #  and for people that are not familiar with ET preprocessing, they also cannot learn anything as it says not
    #  explicitely that this is about fixations
    gaze.detect("ivt")
    gaze.detect("microsaccades")

    # TODO pm: this is non-intuitive. Why are these properties?
    for property, kwargs, event_name in [
        ("location", dict(position_column="pixel"), "fixation"),
        ("amplitude", dict(), "saccade"),
        ("peak_velocity", dict(), "saccade"),
        ("dispersion", dict(), "saccade"),
        ("dispersion", dict(), "fixation"),
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

    # TODO pm, I cannot save it if I don't do this.. can we somehow integrate this (lower priority..);
    #  but I cannot save it anyways, it still complains that it is unnested, also it is really not
    #  straightforward that I have to unnest gaze and events separately...
    gaze.unnest()
    gaze.events.unnest()

    if save:
        events_file = Path(output_dir) / f"{session_idf}_events.csv"
        save_gaze_data(gaze, metadata_dir=Path(output_dir), events_path=events_file)


def map_fixations_to_aois(
        gaze: pm.Gaze,
        session_idf: str,
        stimuli: list[Stimulus],
        save: bool = False,
        output_dir: str = '',
):
    all_stimuli = pl.DataFrame()
    for stimulus in stimuli:
        text = stimulus.text_stimulus.aois
        all_stimuli = all_stimuli.vstack(text)

    # TODO pm very ugly work around. I'd like to be able to map to aois for each stimulus separately
    #  https://github.com/pymovements/pymovements/issues/1125
    all_stimuli = TextStimulus(
        all_stimuli,
        aoi_column="char_idx",
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column="page",
    )

    # aoi mapping does not work if there are saccades in the file.. because then the
    gaze.events.frame = gaze.events.fixations
    gaze.events.map_to_aois(all_stimuli)

    if save:
        path = Path(output_dir) / f"{session_idf}_scanpath.csv"
        save_gaze_data(events_path=path, gaze=gaze)


def generate_scanpaths():
    pass
