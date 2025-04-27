from pathlib import Path
import importlib
import json
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Literal
import PIL
import matplotlib.pyplot as plt
import polars as pl
import pymovements as pm
import re
import tempfile
import logging
from collections import defaultdict


from stimulus import LabConfig, Stimulus, load_stimuli

""" Idea: create temporary asc files, only containing hte current stimulus I want to check if spilt line is defined 
(else whole asc file is preprocessed, do preprocessing and create gaze data frame ans AOIS mappin (currently only possible 
 screen page
 I can then use the first metadata dictonarry create to compar ale the following to it to chech if smapling frequency 
 tracked eye ect are consistent. Create a dictonary with all the messages in it, where the messages are the keys and the values are 
 a list of timestamps, such that i get all the messages and can efficently check if certain messages are in there"""

@dataclass
class ExperimentFrame:
    session_identifier: str
    stimuli: list[Stimulus] # in the right order
    question_order_version: int
    stimuli_order: list[str]
    stimulus_dir: Path | None
    asc_file: Path
    temp_asc: Path | None
    asc_generator: None
    output_dir: None | Path



    @classmethod
    def load_from_multipleye_data_collection(cls,
                                             MultipleyeDataCollection,
                                             session_identifier):
        session = MultipleyeDataCollection.sessions[session_identifier]
        return cls(
            session_identifier=session_identifier,
            stimuli=session["session_stimuli"],
            question_order_version=session["question_order_version"],
            stimuli_order=session["stimuli_order"],
            stimulus_dir=MultipleyeDataCollection.stimulus_dir,
            asc_file=session["asc_path"],
            asc_generator=None,
            temp_asc=None,
            output_dir=MultipleyeDataCollection.output_dir
        )


    def get_tem_asc_file(self):
        if self.asc_generator:
            self.temp_asc = next(self.asc_generator)
            return self.temp_asc
        else:
            logging.INFO("whole asci file is used")
            return self.asc_file

    def split_asc_file (self, split_line: str | None, overwrite: bool = False):
        """instanciete and assignsthe generator  to the class attribute temp_asc
        aslo check if already instancieted"""

        if self.asc_generator == None or overwrite:
            self.asc_generator = self._split_asc_file_generator(split_line)

        self.get_tem_asc_file()


    def _split_asc_file_generator(self, split_line: str | None, REGEX: str | None = r'MSG\s+(?P<timestamp>\d+[.]?\d*)\s+(?P<message>.*)'):
        """Generator that splits asc file at the defined line, or does nothing,
        for every split a temporary asc file is create on which the ET data is extracted and preprocessing performed
        -> return generator object with file paths"""

        if not split_line:
            logging.info("no line split defined, whole asc file is used")
            return

        #split_line = split_line.encode(encoding="ascii")
        num_file = 0
        with open(self.asc_file, mode="r") as asc:
            lines = []
            messages = defaultdict(list)
            for line in asc.readlines():
                logging.info(f'{line}')
                if split_line not in line:
                    lines.append(line)
                    match = re.match(REGEX, line)
                    if match:
                        messages[f"{match.group('message')}"].append(f"{match.group('timestamp')}")
                else:
                    logging.info(f"temp file num {num_file} is create mit line split {split_line} \n {messages}")
                    with tempfile.NamedTemporaryFile(
                            delete=False, mode="w", dir=self.output_dir , suffix=f"asc_file_split_{num_file}",
                            prefix="temp_"
                    ) as f:

                        f.writelines(lines)
                        lines.clear()
                        num_file += 1
                    yield f.name






def load_data(asc_file: Path, lab_config: LabConfig, session_idf: str = '') -> pm.GazeDataFrame:
    stimulus = 1
    regex =f"start_recording_(?P<trial>(?:PRACTICE_)?trial_\d+)_stimulus_(?P<stimulus>[^_]+_[^_]+_{stimulus})_(?P<screen>.+)"
    regex = re.compile(regex)
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
    #TODO: Uncomment assertions when experiment implementation is fixed (https://www.sr-research.com/support/thread-9129.html)
    #assert metadata["resolution"][0] == stimulus_config.IMAGE_WIDTH_PX, f"Image width mismatch: {metadata['resolution'][0]} != {stimulus_config.IMAGE_WIDTH_PX}"
    #assert metadata["resolution"][1] == stimulus_config.IMAGE_HEIGHT_PX, f"Image height mismatch: {metadata['resolution'][1]} != {stimulus_config.IMAGE_HEIGHT_PX}"
    #print(lab_config) #ersten drei sollte es aus asc herauslesen, andere aus lab config
    gaze.experiment = pm.Experiment(
       sampling_rate=gaze._metadata["sampling_rate"],
       screen_width_px=lab_config.screen_resolution[0],
       screen_height_px=lab_config.screen_resolution[1],
       screen_width_cm=lab_config.screen_size_cm[0],
       screen_height_cm=lab_config.screen_size_cm[1],
       distance_cm=lab_config.screen_distance_cm,
    )

    return gaze


def preprocess(
        gaze: pm.GazeDataFrame, sg_window_length: int = 50, sg_degree: int = 2
) -> None:
    # Savitzky-Golay filter as in https://doi.org/10.3758/BRM.42.1.188
    window_length = round(gaze.experiment.sampling_rate / 1000 * sg_window_length)
    if window_length % 2 == 0:  # Must be odd
        window_length += 1
    gaze.pix2deg()
    gaze.pos2vel("savitzky_golay", window_length=window_length, degree=sg_degree)
    gaze.detect("ivt")
    gaze.detect("microsaccades")
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


def main():
    import logging
    from multipleye_data_collection import MultipleyeDataCollection
    logging.basicConfig(level=logging.INFO)
    data_collection_folder = 'MultiplEYE_RU_RU_NewYork_1_2025'

    this_repo = Path().resolve().parent
    data_folder_path = this_repo / "data" / data_collection_folder

    multipleye = MultipleyeDataCollection.create_from_data_folder(str(data_folder_path),
                                                                  additional_folder='pilot_sessions')
    multipleye.load_logfiles("005_RU_RU_1_ET1")

    experiment = ExperimentFrame.load_from_multipleye_data_collection(multipleye, "005_RU_RU_1_ET1")
    experiment.split_asc_file(split_line="stop_recording_")
    logging.info(f"{experiment.temp_asc}")
    gaze = load_data(experiment.temp_asc, multipleye.lab_configuration)
    print(gaze.frame)
    preprocess(gaze)
    print(gaze.events)
if __name__ == "__main__":
    main()