import json
import os
import pickle
import re
from functools import partial
from pathlib import Path
from pprint import pprint
import polars as pl
import re
import tempfile
import pandas as pd
import logging
from pymovements import GazeDataFrame
from tqdm import tqdm

from preprocessing.checks.et_quality_checks import check_validations, plot_gaze, plot_main_sequence, \
    check_comprehension_question_answers, \
    check_metadata, report_to_file_metadata as report_meta
from preprocessing.checks.formal_experiment_checks import check_all_screens_logfile, check_all_screens, \
    check_instructions

from preprocessing.data_collection.data_collection import DataCollection
from preprocessing.plotting.plot import load_data, preprocess
from preprocessing.data_collection.stimulus import LabConfig, Stimulus
from preprocessing.utils.fix_pq_data import remap_wrong_pq_values

STIMULUS_NAMES = [
    "PopSci_MultiplEYE",
    "Ins_HumanRights",
    "Ins_LearningMobility",
    "Lit_Alchemist",
    "Lit_MagicMountain",
    "Lit_Solaris",
    "Lit_BrokenApril",
    "Arg_PISACowsMilk",
    "Arg_PISARapaNui",
    "PopSci_Caveman",
    "Enc_WikiMoon",
    "Lit_NorthWind",
]


class MultipleyeDataCollection(DataCollection):

    def __init__(self,
                 config_file: Path,
                 stimulus_dir: Path,
                 lab_number: int,
                 city: str,
                 data_root: Path,
                 lab_configuration: LabConfig,
                 session_folder_regex: str,
                 # stimuli: list[Stimulus],
                 **kwargs):
        super().__init__(**kwargs)
        self.config_file = config_file
        self.stimulus_dir = stimulus_dir
        self.lab_number = lab_number
        self.city = city
        self.lab_configuration = lab_configuration
        self.data_root = data_root
        self.session_folder_regex = session_folder_regex
        self.different_stimulus_names = kwargs.get('different_stimulus_names', 'all')
        self.psychometric_tests = kwargs.get('psychometric_tests', [])

        if not self.output_dir:
            self.output_dir = self.data_root.parent / 'quality_reports'
            self.output_dir.mkdir(exist_ok=True)

        self.add_recorded_sessions(self.data_root, self.session_folder_regex, convert_to_asc=True)

        if len(self.sessions) == 0:
            raise ValueError(f"No sessions found in {self.data_root}. Please check the session_folder_regex "
                             f"and the data_root.")

        self.parse_participant_data()
        logging.basicConfig()

    @staticmethod
    def _get_stimulus_names(stimulus_dir: Path, stimulus_file: str,
                            col_name_stimulus: str = "stimulus_name") -> list[str]:
        """
        Get the stimulus names from the stimulus file.
        :param stimulus_dir: Directory where stimuli are stored
        :param stimulus_file: File where the stimuli are stored. It should be a csv or xlsx file containing one
        stimulus per row
        :param col_name_stimulus: The name of the column where the stimulus names are indicated
        :return: stimulus names in a list
        """

        stimulus_df_path = (stimulus_dir / stimulus_file)
        assert (stimulus_df_path.exists()), f"File {stimulus_df_path} does not exist"

        if stimulus_df_path.suffix == ".csv":
            stimulus_df = pl.read_csv(stimulus_df_path)
        elif stimulus_df_path.suffix == ".xlsx":
            stimulus_df = pl.read_excel(stimulus_df_path)
        else:
            raise ValueError(f"File {stimulus_df_path} is not a csv or xlsx file")

        stimulus_names = stimulus_df[col_name_stimulus].unique().to_list()
        return stimulus_names

    @staticmethod
    def load_labconfig(stimulus_dir: Path, lang: str,
                       country: str, labnum: int, city: str, year: int, ) -> LabConfig:
        """
        Load the stimuli and lab configuration from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param lang: The language of the stimuli.
        :param country: The country of the stimuli.
        :param labnum: The lab number.
        :param city: The city of the stimuli.
        :param year: The year of the stimuli.

        """
        return LabConfig.load(stimulus_dir, lang, country, labnum, city, year)

    @classmethod
    def create_from_data_folder(cls, data_dir: str,
                                additional_folder: str | None = None,
                                different_stimulus_names: str | None = None,
                                include_pilots: bool = False) -> "MultipleyeDataCollection":
        """
        :param data_dir: str  path to the data folder
        :param additional_folder: if additional sub-folders in the data folder are used,
        e.g. 'core_dataset', test_dataset, pilot_dataset
        :param different_stimulus_names: if the stimulus names are different from the default ones they can be extracted
        from the multipleye_stimuli_experiment_en.xlsx file, at the moment only used for testing purposes
        :param include_pilots: If True, the pilot sessions are included in the data collection.
        :return:
        MultipleyeDataCollection object
        """

        data_dir = Path(data_dir)

        data_folder_name = data_dir.name
        _, stimulus_language, country, city, lab_number, year = data_folder_name.split('_')
        if not data_folder_name.startswith('MultiplEYE'):
            raise ValueError(f"Data collection name {data_folder_name} does not start with 'MultiplEYE'. "
                             f"Please check the folder name.")
        if not year.isdigit() or len(year) != 4:
            raise ValueError(f"Year {year} of the data collection name is not a valid year. "
                             f"It should be a 4 digit number.")
        if not lab_number.isdigit() or len(lab_number) != 1:
            raise ValueError(f"Lab number {lab_number} of the data collection name is not a valid lab number. "
                             f"It should be a 1 digit number.")
        if len(country) != 2 or not country.isalpha():
            raise ValueError(f"Country {country} of the data collection name is not a valid country code. "
                             f"It should be a 2 letter code.")
        if len(city) < 2 or not city.isalpha():
            raise ValueError(f"City {city} of the data collection name is not a valid city name. "
                             f"It should be a string with at least 2 letters.")
        if not stimulus_language.isalpha() or len(stimulus_language) != 2:
            raise ValueError(f"Stimulus language {stimulus_language} of the data collection name is not a valid "
                             f"language code. It should be a 2 letter code.")

        session_folder_regex = r"\d\d\d" + f"_{stimulus_language}_{country}_{lab_number}" + r"_ET\d"

        stimulus_folder_path = data_dir / f'stimuli_{data_folder_name}'
        config_file = (stimulus_folder_path /
                       'config' /
                       f'config_{stimulus_language.lower()}_{country.lower()}_{city}_{lab_number}.py')

        lab_configuration_data = cls.load_labconfig(stimulus_folder_path, stimulus_language,
                                                    country, lab_number, city, year)

        eye_tracker = lab_configuration_data.name_eye_tracker
        psychometric_tests = lab_configuration_data.psychometric_tests

        et_data_path = data_dir / 'eye-tracking-sessions' / additional_folder if additional_folder else data_dir / 'eye-tracking-sessions'

        return cls(
            data_collection_name=data_folder_name,
            stimulus_language=stimulus_language,
            country=country,
            year=int(year),
            eye_tracker=eye_tracker,
            session_folder_regex=session_folder_regex,
            config_file=config_file,
            stimulus_dir=stimulus_folder_path,
            lab_number=int(lab_number),
            city=city,
            data_root=et_data_path,
            lab_configuration=lab_configuration_data,
            different_stimulus_names=different_stimulus_names,
            include_pilots=include_pilots,
            pilot_folder=et_data_path / 'pilot_sessions' if include_pilots else None,
            psychometric_tests=psychometric_tests,
            # stimuli=stimuli
        )

    def _load_session_names(self, session: str | list[str] | None) -> list[str]:
        """
        Get the session names from the data root folder.
        :param session: If a session identifier is specified only the gaze data for this session is loaded.
        :return:
        """
        if not session:
            sessions = [key for key in self.sessions.keys()]
            return sessions
        elif session not in self.sessions:
            raise KeyError(f'Session {session} not found in {self.data_root}.')

        elif isinstance(session, str):
            return [session]
        elif isinstance(session, list):
            return session

    def create_gaze_frame(self, session: str | list[str] = '', overwrite: bool = False) -> None:
        """
        Creates, preprocesses and saves the gaze data for the specified session or all sessions.
        :param session: If a session identifier is specified only the gaze data for this session is loaded.
        :param overwrite: If True the gaze data is overwritten if it already exists.
        :return:
        """
        session_keys = self._load_session_names(session)

        for session_name in tqdm(session_keys, desc="Creating gaze data"):
            gaze_path = self.output_dir / session_name

            # / f"{session_name}_gaze.pkl"
            gaze_path.mkdir(parents=True, exist_ok=True)

            gaze_path = gaze_path / f"{session_name}_gaze.pkl"

            if gaze_path.exists() and not overwrite:
                # make sure gaze path is added if the pkl was created in a previous run
                self.sessions[session_name]['gaze_path'] = gaze_path
                logging.debug(f"Gaze data already exists for {session_name}.")
                return

            self.sessions[session_name]['gaze_path'] = gaze_path

            try:
                gaze = load_data(Path(self.sessions[session_name]['asc_path']), self.lab_configuration,
                                 session_idf=session_name)
            except KeyError:
                raise KeyError(
                    f"Session {session_name} not found in {self.data_root}.")
            except FileNotFoundError:
                raise FileNotFoundError(
                    f"No asc file found for session {session_name}. Please create first.")

            logging.warning(f"Preprocessing gaze data for {session_name}. This might take a while.")

            preprocess(gaze)
            # save and load the gaze dataframe to pickle for later usage
            self.sessions[session_name]['gaze_path'] = gaze_path

            # make sure all dirs haven been created

            with open(gaze_path, "wb") as f:
                pickle.dump(gaze, f)

    # def get_gaze_frame(self, session_identifier: str = '',
    #                    create_if_not_exists: bool = False,
    #                    ) -> GazeDataFrame:
    #     """
    #     Loads and possibly creates the gaze data for the specified session(s).
    #     :param create_if_not_exists: The gaze data will be created and stored if True.
    #     :param session_identifier: If (a) session identifier(s) is/are specified only the gaze data for this session is
    #     loaded. Otherwise, the gaze data for all sessions is loaded.
    #     :return: GazeDataFrame of the session. Comes with metadata on the session.
    #     """
    #
    #     if session_identifier not in self.sessions:
    #         raise KeyError(f'Session {session_identifier} not found in {self.data_root}.')
    #
    #     try:
    #         # check if pkl files are already available
    #         gaze_path = Path(self.output_dir / session_identifier).glob('*.pkl')
    #
    #         if len(list(gaze_path)) == 1:
    #             gaze_path = Path(self.output_dir / session_identifier).glob('*.pkl')
    #             gaze_path = list(gaze_path)[0]
    #             self.sessions[session_identifier]['gaze_path'] = gaze_path
    #             logging.debug(f'Found pkl file for {session_identifier}.')
    #         # elif len(gaze_path_list) > 1:
    #         #    raise FileExistsError(f"More than one pkl file found for {session_identifier}. Please check the {self.output_dir / session_identifier} directory.")
    #         else:
    #             raise FileNotFoundError
    #
    #     except FileNotFoundError:
    #         if create_if_not_exists:
    #             self.create_gaze_frame(session=session_identifier)
    #             gaze_path = self.sessions[session_identifier]['gaze_path']
    #         else:
    #             raise KeyError(f'Gaze frame not created for session {session_identifier}. Please create first.')
    #     #print(gaze_path)
    #     #print(type(gaze_path))
    #     with open(gaze_path, "rb") as f:
    #         #print(f)
    #         gaze = pickle.load(f)
    #
    #     return gaze

    @staticmethod
    def load_stimuli(stimulus_dir: Path, lang: str,
                     country: str, labnum: int,
                     question_version: int,
                     stimulus_names: None | list = None) -> list[Stimulus]:
        """
        Load the stimuli and lab configuration from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param lang: The language of the stimuli.
        :param country: The country of the stimuli.
        :param stimulus_names: The names of the stimuli to load. If None, the predefined stimuli names in the
        global variable STIMULUS_NAMES are used.
        :param question_version: The version of the questions to load. Specifies how the questions are ordered and the
        shuffeling of the answer options.
        when loading the lab configuration, however it does not make sense to have the same stimuli for the whole data
        collection as they are participant dependent.
        """
        stimuli = []
        if stimulus_names is None:
            stimulus_names = STIMULUS_NAMES

        for stimulus_name in stimulus_names:
            stimulus = Stimulus.load(stimulus_dir, lang, country, labnum, stimulus_name, question_version)
            stimuli.append(stimulus)

        return stimuli

    def load_session_dependent_stimuli(self, session_identifier) -> None:
        """
        Get the sessions that were completed in the specified session.
        :param session_identifier:
        """
        self.load_logfiles(session_identifier)

        if self.different_stimulus_names == "split":
            # the last one of these stimuli might not have been completed entirely of the session has been interrupted
            # and split into two sessions. In this case, completed is set to False
            # TODO: write down that the last stimulus might not be completed and therefore has been read twice partially
            stimuli = self.sessions[session_identifier]["completed_stimuli"][
                self.sessions[session_identifier]["completed_stimuli"]['completed'] == True]
            stimulus_names = stimuli["stimulus_name"].to_list()

        elif self.different_stimulus_names == "test":
            stimulus_names = self._get_stimulus_names(self.stimulus_dir,
                                                      f"multipleye_stimuli_experiment_{self.language}.xlsx")
        else:
            stimulus_names = STIMULUS_NAMES
        session_name = session_identifier
        question_order_version = self._extract_question_order_version(session_name)

        self.sessions[session_name]['session_stimuli'] = MultipleyeDataCollection.load_stimuli(
            self.stimulus_dir, self.language, self.country, self.lab_number,
            question_version=question_order_version, stimulus_names=stimulus_names)

        # self.load_logfiles(session_name)

    def create_sanity_check_report(self, sessions: str | list[str] | None = None, plotting: bool = True) -> None:
        """
        Create the sanity checks and reports if for one or multiple sessions.
        :param sessions: Specifies which sessions to create the report for. Default is None which creates the reports
        for all sessions.
        :param plotting: If True, all plots are also created for all the sessions.
        """

        if sessions is None:
            sessions = [session_name for session_name in self.sessions.keys()]
        elif isinstance(sessions, str):
            sessions = [sessions]
        elif isinstance(sessions, list):
            sessions = sessions
        else:
            raise ValueError(f"Sessions should be a string, a list of strings or None. You passed {type(sessions)}.")

        # TODO: check if all session names are available in self.session, before we enter the loop to avoid a key error

        for session_name in (pbar := tqdm(sessions, total=len(sessions))):

            pbar.set_description(
                f'Creating sanity check report for session {session_name}'
            )

            os.makedirs(self.output_dir / session_name, exist_ok=True)

            report_file_path = self.output_dir / session_name / f"{session_name}_report.txt"
            with open(report_file_path, "a+",
                      encoding="utf-8") as report_file:
                self.sessions[session_name]['report_file_path'] = report_file_path
                # set report object
                report = partial(report_meta, report_file=report_file)
                self.load_session_dependent_stimuli(session_name)

                # check_gaze(gaze, report)
                gaze = self.get_gaze_frame(session_name, create_if_not_exists=True)
                check_metadata(gaze._metadata, report)

            self.check_logfiles(session_name)
            self.check_asc_all_screens(session_name, gaze)
            self.check_asc_instructions(session_name)
            self.check_asc_validation(session_name, gaze)
            # self.get_stimulus_order_version_csv(session_name)

            if plotting:
                self.create_plots(session_name, gaze)

    def check_logfiles(self, session_identifier):
        """
        Check the experiment logfile for the specified session.
        :param session_identifier: The session identifier.
        :return:
        """

        report_file = self.output_dir / session_identifier / f"{session_identifier}_report.txt"
        check_comprehension_question_answers(self.sessions[session_identifier]["logfile"],
                                             self.sessions[session_identifier]["session_stimuli"], report_file)

        check_all_screens_logfile(self.sessions[session_identifier]["logfile"],
                                  self.sessions[session_identifier]["session_stimuli"], report_file)

    def create_plots(self, session_identifier, gaze=None):

        logging.info(f" creating plots for {session_identifier}.")

        if not gaze:
            logging.debug(f"Loading gaze data for {session_identifier}.")
            gaze = self.get_gaze_frame(session_identifier, create_if_not_exists=True)

        plot_dir = self.output_dir / session_identifier / f"{session_identifier}_plots"
        plot_dir.mkdir(exist_ok=True)

        plot_main_sequence(gaze.events, plot_dir)

        for stimulus in self.sessions[session_identifier]['session_stimuli']:
            logging.debug(f"Creating plots for {stimulus.name}.")
            plot_gaze(gaze, stimulus, plot_dir)

    def check_asc_instructions(self, session_identifier):
        """
        Check the instructions for the specified session.
        :param session_identifier: The session identifier. eg "005_ET_EE_1_ET1"
        :return:
        """
        logging.debug(f"Checking asc file for {session_identifier} instructions.")
        messages = self._load_messages_for_experimenter_checks(session_identifier)
        report_file = self.output_dir / session_identifier / f"{session_identifier}_report.txt"
        if self.different_stimulus_names == "split":
            split = True
        else:
            split = False
        check_instructions(messages, self.sessions[session_identifier]["session_stimuli"], report_file,
                           self.sessions[session_identifier]["stimuli_order"], split=split)

    def _extract_question_order_version(self, session_identifier: str) -> int:
        """
        Extract the question order and version from the session identifier.
        :param session_identifier: The session identifier.
        :return: The question order version to correctly map participant, stimulus and question order versions.
        """
        session_path = self.sessions[session_identifier]['session_folder_path']
        logfile_path = Path(f'{session_path}/logfiles')
        general_logfile = logfile_path.glob('GENERAL_LOGFILE_*.txt')
        general_logfile = next(general_logfile)
        assert general_logfile.exists(), f"Logfile path {general_logfile} does not exist."

        regex = r"(STIMULUS_ORDER_VERSION_)(?P<question_order_version>\d+)"
        with open(general_logfile, "r", encoding="utf-8") as f:
            text = f.read()
        match = re.search(regex, text)

        if match:
            question_order_version = match.groupdict()['question_order_version']
        else:
            raise ValueError(f"Could not find question order version in {general_logfile}.")
        return question_order_version

    def load_logfiles(self, session_identifier):
        """
        Load the logfiles for the specified session. Stores the logfile and the completed stimuli as a polars DataFrame,
        the order of the stimuli as list, and the version of the question oder as an int.
        :param session_identifier: The session identifier.
        """
        session_path = self.sessions[session_identifier]['session_folder_path']
        logfile_folder = Path(f'{session_path}/logfiles')

        assert logfile_folder.exists(), f"Logfile folder {logfile_folder} does not exist."
        logfile = logfile_folder.glob("EXPERIMENT_*.txt")
        completed_stim_path = logfile_folder / 'completed_stimuli.csv'

        logfiles = list(logfile)

        if len(logfiles) != 1:
            raise ValueError(f"More than one or no logfile found in {logfile_folder}. Please check the logfiles.")

        logfile = pl.read_csv(logfiles[0], separator="\t")
        completed_stimuli = pl.read_csv(completed_stim_path, separator=",")
        question_version = self._extract_question_order_version(session_identifier)

        self.sessions[session_identifier]['logfile'] = logfile
        self.sessions[session_identifier]['completed_stimuli'] = completed_stimuli
        self.sessions[session_identifier]['stimuli_order'] = completed_stimuli["stimulus_id"].to_list()
        self.sessions[session_identifier]['question_order_version'] = question_version
        # return logfile, completed_stimuli, stimuli_order

    def _load_messages_for_experimenter_checks(self, session_identifier: str):
        """
       qick fix for now, should be replaced by the summary experiment frame later on
        """
        regex = r'MSG\s+(?P<timestamp>\d+[.]?\d*)\s+(?P<message>.*)'
        asc_file = self.sessions[session_identifier]['asc_path']
        with open(asc_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
        messages = []
        for line in lines:
            match = re.match(regex, line)
            if match:
                messages.append(match.groupdict())
                if "stimulus_order_version" in line:
                    self.sessions[session_identifier]['stimulus_order_version_asc'] = line
                    print(f"{self.sessions[session_identifier]['question_order_version']}, {line}")
        return messages

    def check_asc_validation(self, session_identifier: str, gaze: GazeDataFrame = None) -> None:
        """
        Check the validations in the asc file for the specified session.
        :param session_identifier: The session identifier.
        :param gaze: If the gaze data has already been created it can be passed as an argument.
        If not it will be created.
        """
        logging.debug(f"Checking Validation for {session_identifier}.")
        messages = self._load_messages_for_experimenter_checks(session_identifier)
        if not messages:
            logging.error(f"No messages found in {session_identifier}.")
        if not gaze:
            logging.debug(f"Loading gaze data for {session_identifier}.")
            gaze = self.get_gaze_frame(session_identifier, create_if_not_exists=True)

        report_file = self.output_dir / session_identifier / f"{session_identifier}_report.txt"
        check_validations(gaze, messages, report_file)

    def check_asc_all_screens(self, session_identifier, gaze=None):
        """
        """
        logging.debug(f"Checking asc file all screens for {session_identifier} all screens.")

        if not gaze:
            logging.debug(f"Loading gaze data for {session_identifier}.")
            gaze = self.get_gaze_frame(session_identifier, create_if_not_exists=True)

        report_file = self.output_dir / session_identifier / f"{session_identifier}_report.txt"
        check_all_screens(gaze, self.sessions[session_identifier]["session_stimuli"], report_file)

    def check_if_psychometric_tests(self, session_identifier: str) -> bool:
        pass

    def preprocess_psychometric_tests(self):
        pass

    def parse_participant_data(self) -> None:
        """
        Load the participant data for all participants.

        """

        participant_data = pd.DataFrame()

        for idx, session in (pbar := tqdm(enumerate(self.sessions), total=len(self.sessions))):
            pbar.set_description(f'Parsing participant data : {session}')

            folder = Path(self.sessions[session]['session_folder_path'])
            id, country, lang, lab, _ = session.split('_')
            pq_file = folder / f'{id}_{country}_{lang}_{lab}_pq_data.json'
            if pq_file.exists():
                with open(pq_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # due to a bug in an earlier version of the experiment, some of the participant data has been lost,
                # and we need to correct it
                if 'native_language_1_academic_reading_time' not in data:
                    data = remap_wrong_pq_values(data)

                data['participant_id'] = id

                participant_data = pd.concat([participant_data, pd.DataFrame(data, index=[idx])], ignore_index=True)

            else:
                logging.warning(f"No participant data found for session {session}. Skipping.")

        # reorder columns such that participant_id is the first column
        cols = participant_data.columns.tolist()
        cols = ['participant_id'] + [col for col in cols if col != 'participant_id']
        participant_data = participant_data[cols]

        participant_data.to_csv(self.data_root.parent / 'participant_data.csv', index=False)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    data_collection_folder = 'MultiplEYE_ET_EE_Tartu_1_2025'

    this_repo = Path().resolve().parent

    data_folder_path = this_repo / "data" / data_collection_folder

    multipleye = MultipleyeDataCollection.create_from_data_folder(str(data_folder_path))
    # multipleye.add_recorded_sessions(data_root= data_folder_path / 'eye-tracking-sessions' / 'core_dataset', convert_to_asc=False, session_folder_regex=r"005_ET_EE_1_ET1")
    # multipleye.create_gaze_frame("005_ET_EE_1_ET1")
    multipleye.create_sanity_check_report(["005_ET_EE_1_ET1", "006_ET_EE_1_ET1"])
    multipleye.create_experiment_frame("005_ET_EE_1_ET1")
