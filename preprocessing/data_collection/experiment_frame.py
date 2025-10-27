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

SPLITS: {"page": "stop_recording",
         "trial": "TRIAL_VAR stimulus_name"}
""" Idea: create temporary asc files, only containing hte current stimulus I want to check if spilt line is defined 
(else whole asc file is preprocessed, do preprocessing and create gaze data frame ans AOIS mappin (currently only possible 
 screen page
 I can then use the first metadata dictonary create to compare all the following to it to chech if smapling frequency 
 tracked eye ect are consistent. Create a dictonary with all the messages in it, where the messages are the keys and the values are 
 a list of timestamps, such that i get all the messages and can efficently check if certain messages are in there
 independent from logfile
 only necessary, stimulus folder and edf file"""


@dataclass
class ExperimentFrame:
    session_identifier: str
    stimuli: list[Stimulus]  # in the right order
    question_order_version: int
    stimuli_order: list[str]
    stimulus_dir: Path | None
    asc_file: Path
    temp_asc: Path | None
    asc_generator: None
    output_dir: None | Path
    lab_configuration: None | LabConfig
    display_cord: [""]
    current_stimuli_id: None | int
    split_experiment: bool


    @classmethod
    def load_from_multipleye_data_collection(cls,
                                             MultipleyeDataCollection,
                                             session_identifier):

        session = MultipleyeDataCollection.sessions[session_identifier]
        MultipleyeDataCollection.load_session_dependent_stimuli(session_identifier)
        return cls(
            session_identifier=session_identifier,
            stimuli=session["session_stimuli"],
            question_order_version=session["question_order_version"],
            stimuli_order=session["stimuli_order"],
            stimulus_dir=MultipleyeDataCollection.stimulus_dir,
            asc_file=session["asc_path"],
            asc_generator=None,
            temp_asc=None,
            output_dir=MultipleyeDataCollection.reports_dir,
            lab_configuration=MultipleyeDataCollection.lab_configuration,
            display_cord=[""],
            current_stimuli_id=session["stimuli_order"][0],
            split_experiment=False
        )

    def get_next_tem_asc_file(self):
        """get to the next split of the asc file returns the path to the temporary file"""
        if self.asc_generator:
            self.temp_asc = next(self.asc_generator)
            return self.temp_asc
        else:
            logging.INFO("whole asci file is used")
            return self.asc_file

    def get_temp_asc_file(self):
        """return filepath of current asc file split"""
        if self.temp_asc:
            return self.temp_asc

        logging.info(f"asc file was not split, returning file path to whole asc file")
        return self.asc_file


    def split_asc_file(self, split_line: str | None = "stop_recording_", overwrite: bool = False):
        """instanciete and assign the generator  to the class attribute temp_asc
        also check if already instancieted"""

        if self.asc_generator == None or overwrite:

            self.asc_generator = self._split_asc_file_generator(split_line)

        self.get_next_tem_asc_file()


    def _split_asc_file_generator(self, split_line: str | None,
                                  REGEX: str | None = r'MSG\s+(?P<timestamp>\d+[.]?\d*)\s+(?P<message>.*)'):
        """Generator that splits asc file at the defined line, or does nothing,
        for every split a temporary asc file is create on which the ET data is extracted and preprocessing performed
        -> return generator object with file paths"""

        if not split_line:
            logging.info("no line split defined, whole asc file is used")
            return

        # split_line = split_line.encode(encoding="ascii")
        num_file = 0

        with open(self.asc_file, mode="r") as asc:
            lines = []
            messages = defaultdict(list)
            for line in asc.readlines():
                if split_line not in line:
                    lines.append(line)
                    match = re.match(REGEX, line)
                    if match:
                        messages[f"{match.group('message')}"].append(f"{match.group('timestamp')}")
                        if "DISPLAY_COORDS" in line:
                            if match.group('message') not in self.display_cord[0]:
                                self.display_cord.append(line)
                                if len(self.display_cord) > 2:
                                    logging.error(f"multiple screen resoultions found {self.display_cord}")
                        if "stimulus_order_version" in line:
                            self.stimulus_order_version_asc = line # in the future this should be used to get the stimulus order versio instead of the multipleye methode

                else:
                    lines.append(line)
                    logging.info(f"temp file num {num_file} is create mit line split {line} \n {messages}")
                    with tempfile.NamedTemporaryFile(
                            delete=False, mode="w", dir=self.output_dir, suffix=f"asc_file_split_{num_file}",
                            prefix="temp_", encoding="utf8"
                    ) as f:

                        f.writelines(self.display_cord + lines)
                        lines.clear()
                        num_file += 1
                    yield f.name
    def __str__(self):
        return f"{type(self)} for {self.session_identifier} stimulus"
    def load_data(self, asc_file: Path, lab_config: LabConfig, session_idf: str = '') -> pm.GazeDataFrame:


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
        # assert metadata["resolution"][0] == stimulus_config.IMAGE_WIDTH_PX, f"Image width mismatch: {metadata['resolution'][0]} != {stimulus_config.IMAGE_WIDTH_PX}"
        # assert metadata["resolution"][1] == stimulus_config.IMAGE_HEIGHT_PX, f"Image height mismatch: {metadata['resolution'][1]} != {stimulus_config.IMAGE_HEIGHT_PX}"
        # print(lab_config) #ersten drei sollte es aus asc herauslesen, andere aus lab config
        gaze.experiment = pm.Experiment(
            sampling_rate=gaze._metadata["sampling_rate"],
            screen_width_px=lab_config.image_resolution[0],
            screen_height_px=lab_config.image_resolution[1],
            screen_width_cm=lab_config.screen_size_cm[0],
            screen_height_cm=lab_config.screen_size_cm[1],
            distance_cm=lab_config.screen_distance_cm,
        )
        self.gaze = gaze
        print(gaze._metadata)
        return gaze

    def preprocess(self,
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

    def aois_mapping(self, gaze, Stimulus):
        """ does not work yet properly, due to odditis in pymovement, andreas is working on it"""
        gaze.events.frame = gaze.events.frame.filter(pl.col("name") == "fixation") # only keeping fixations (saccades are also generated but will break code if kept in frame)
        gaze.events.map_aois(Stimulus.text_stimulus)
        print(gaze.events)

    def _create_experiment_summary(self, events):
        df = events.frame
        durations = df.group_by("name").agg(pl.col("duration").sum())
        num_fix_and_sac = df.group_by("name").len()

        self.summary_dict[self.current_stimuli_id].update({'number of fixations' :num_fix_and_sac.rows_by_key(key="name").pop("fixation")})
        self.summary_dict[self.current_stimuli_id].update({'number of saccades' :num_fix_and_sac.rows_by_key(key="name").pop("saccade")})
    def create_experiment_summary(self):
        self.split_asc_file()

        self.summary_dict = {k: val for k, val in self.__dict__.items() if not str(hex(id(val))) in str(val)}
        for asc_parts in self.asc_generator:
            gaze = self.load_data(self.temp_asc, self.lab_configuration)
            self.summary_dict[self.current_stimuli_id] = gaze._metadata
            #self.preprocess(gaze)
            #self._create_experiment_summary(gaze.events)



def main():
    import logging
    from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection
    logging.basicConfig(level=logging.INFO)
    data_collection_folder = 'MultiplEYE_RU_RU_NewYork_1_2025'

    this_repo = Path().resolve().parent
    data_folder_path = this_repo / "data" / data_collection_folder

    multipleye = MultipleyeDataCollection.create_from_data_folder(str(data_folder_path),
                                                                  additional_folder='pilot_sessions')
    multipleye.load_session_logfile("005_RU_RU_1_ET1")

    experiment = ExperimentFrame.load_from_multipleye_data_collection(multipleye, "005_RU_RU_1_ET1")
    experiment.create_experiment_summary()

   # experiment.split_asc_file(split_line="stop_recording_")
  #logging.info(f"{experiment.temp_asc}")
  #gaze = experiment.load_data(experiment.temp_asc, multipleye.lab_configuration)
  #print(gaze.frame)
  ##experiment.preprocess(gaze)
  ##print(gaze.events)
  #print(experiment.temp_asc)
  #experiment.get_next_tem_asc_file()
  #gaze2 = experiment.load_data(experiment.temp_asc, multipleye.lab_configuration)
  #
  #print(gaze2.frame)
  ##experiment.preprocess(gaze2)
  ##print(gaze2.events)


if __name__ == "__main__":
    main()
