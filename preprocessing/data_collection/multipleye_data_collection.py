import json
import logging
import os
import re
import subprocess
import warnings
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pymovements as pm
import yaml
from polars.polars import ComputeError
from tqdm import tqdm

from preprocessing.checks.et_quality_checks import \
    check_comprehension_question_answers, \
    check_metadata, report_to_file_metadata as report_meta, check_validation_requirements
from preprocessing.checks.formal_experiment_checks import check_all_screens_logfile, sanity_check_gaze_frame, \
    check_messages
from preprocessing.data_collection.session import Session
from preprocessing.data_collection.stimulus import LabConfig, Stimulus
from preprocessing.plotting.plot import plot_gaze, plot_main_sequence
from preprocessing.psychometric_tests.preprocess_psychometric_tests import preprocess_plab, preprocess_ran, \
    preprocess_stroop, preprocess_flanker, preprocess_wikivocab, preprocess_lwmc
from preprocessing.utils.fix_pq_data import remap_wrong_pq_values
from preprocessing.utils.prepare_language_folder import extract_stimulus_version_number_from_asc

EYETRACKER_NAMES = {
    'eyelink': [
        'EyeLink 1000 Plus',
        'EyeLink II',
        'EyeLink 1000',
        'EyeLink Portable Duo',
    ],
}


def eyelink(method):
    def wrapper(self):
        if self.eye_tracker == 'eyelink':
            return method(self)
        else:
            raise ValueError(f'Function {method.__name__} is only supported for EyeLink data. '
                             f'You are using {self.eye_tracker}')

    return wrapper


class MultipleyeDataCollection:
    stimulus_names = {
        "PopSci_MultiplEYE": 1,
        "Ins_HumanRights": 2,
        "Ins_LearningMobility": 3,
        "Lit_Alchemist": 4,
        "Lit_MagicMountain": 6,
        "Lit_Solaris": 8,
        "Lit_BrokenApril": 9,
        "Arg_PISACowsMilk": 10,
        "Arg_PISARapaNui": 11,
        "PopSci_Caveman": 12,
        "Enc_WikiMoon": 13,
        "Lit_NorthWind": 7,
    }

    participant_data_path: Path | str | None
    crashed_session_ids: list[str] = []
    num_sessions = 1
    overview = {}

    data_collection_name: str
    year: int
    country: str
    session_folder_regex: str = ''
    data_root: Path = None
    excluded_sessions: list = []
    type = 'MultiplEYE'

    # TODO: read instruction excel

    def __init__(self,
                 data_collection_name: str,
                 stimulus_language: str,
                 country: str,
                 year: int,
                 eye_tracker: str,
                 config_file: Path,
                 stimulus_dir: Path,
                 lab_number: int,
                 city: str,
                 data_root: Path,
                 lab_configuration: LabConfig,
                 session_folder_regex: str,
                 # stimuli: list[Stimulus],
                 **kwargs):
        self.sessions: dict[str, Session] = {}
        # TODO: in theory this can be multiple languages for the stimuli..
        self.language = stimulus_language
        self.country = country
        self.year = year
        self.data_collection_name = data_collection_name

        self.include_pilots = kwargs.get('include_pilots', False)
        self.reports_dir = kwargs.get('output_dir', '')
        self.pilot_folder = kwargs.get('pilot_folder', '')
        self.preprocessing_dir = kwargs.get('preprocessing_dir', '')

        for short_name, long_name in EYETRACKER_NAMES.items():
            if eye_tracker in long_name:
                self.eye_tracker = short_name
                self.eye_tracker_name = long_name
                break

        else:
            raise ValueError(f'Eye tracker {eye_tracker} not yet supported. '
                             f'Supported eye trackers are: '
                             f'{np.array([val for k, val in EYETRACKER_NAMES.items()]).flatten()}')
        self.config_file = config_file
        self.stimulus_dir = stimulus_dir
        self.lab_number = lab_number
        self.city = city
        self.lab_configuration = lab_configuration
        self.data_root = data_root
        self.session_folder_regex = session_folder_regex
        self.psychometric_tests = kwargs.get('psychometric_tests', [])

        # load all the manual corrections from the yaml file
        self._load_manual_corrections()

        open(self.data_root.parent / 'preprocessing_logs.txt', 'w').close()

        if not self.reports_dir:
            self.reports_dir = self.data_root.parent / 'quality_reports'
            self.reports_dir.mkdir(exist_ok=True)

        if not self.preprocessing_dir:
            self.preprocessing_dir = self.data_root.parent / 'preprocessing'
            self.preprocessing_dir.mkdir(exist_ok=True)

        self.add_recorded_sessions(
            self.data_root, self.session_folder_regex, convert_to_asc=True)

        if len(self.sessions) == 0:
            raise ValueError(f"No sessions found in {self.data_root}. Please check the session_folder_regex "
                             f"and the data_root.")

        # load stimulus order versions to know what stimulus randomization was used for each participant
        stim_order_versions = self.stimulus_dir / 'config' / \
                              f'stimulus_order_versions_{self.language}_{self.country}_{self.lab_number}.csv'
        stim_order_versions = pd.read_csv(stim_order_versions)
        self.stim_order_versions = stim_order_versions[stim_order_versions['participant_id'].notnull(
        )]

        if self.stim_order_versions.empty:
            warnings.warn(f"Stimulus order version is not updated with participants numbers.\nPlease ask the team to "
                          f"upload the correct stimulus folder that has been used and changed during the experiment.\n"
                          f"Version will be extracted from the asc files.")
            self.stim_order_versions = stim_order_versions

        self.prepare_session_level_information()

        self.overview = self.create_dataset_overview()

    def __repr__(self):
        if not self.overview:
            self.overview = self.create_dataset_overview()

        return "\n".join("{}\t{}".format(k, v) for k, v in self.overview.items())

    # TODO: check these chatgpt functions :D
    def __iter__(self):
        self._iter_keys = sorted(self.sessions)
        self._iter_index = 0
        return self

    def __next__(self):
        if self._iter_index >= len(self._iter_keys):
            raise StopIteration
        key = self._iter_keys[self._iter_index]
        self._iter_index += 1
        return self.sessions[key]

    def __getitem__(self, item):
        return self.sessions[item]

    def add_recorded_sessions(self,
                              data_root: Path,
                              session_folder_regex: str = '',
                              session_file_suffix: str = '',
                              convert_to_asc: bool = False) -> None:
        """

        :param convert_to_asc: If True, the asc files for the recorded sessions are generated. Only works if the eye
        tracker is an Eyelink.
        :param data_root: Specifies the root folder where the data is stored
        :param session_folder_regex: The pattern for the session folder names. It is possible to include infomration in
        regex groups. Those will be parsed directly and stored in the session object.
        Those folders should be in the root folder. If '' then the root folder is assumed to contain all files
        from the sessions.
        :param session_file_suffix: The pattern for the session file names. If no pattern is given, all files in the
        session folder are assumed to be the data files depending on the eye tracker.
        """

        self.data_root = data_root
        self.session_folder_regex = session_folder_regex

        if not session_file_suffix:
            # TODO: add configs for each eye tracker such that we don't always have to loop through all eye trackers
            #  but can write generic code. E.g. self.eye_tracker.session_file_regex
            if self.eye_tracker == 'eyelink':
                session_file_suffix = r'.edf'

        # get a list of all folders in the data folder
        if session_folder_regex:

            items = os.scandir(self.data_root)
            pilots = []
            if self.include_pilots:
                pilots = os.scandir(self.data_root / self.pilot_folder)
                items = list(items) + list(pilots)

            for item in items:
                if item.is_dir():
                    if re.match(session_folder_regex, item.name, re.IGNORECASE):

                        if item.name not in self.excluded_sessions:

                            session_file = list(Path(item.path).glob('*' + session_file_suffix))

                            if len(session_file) == 0:
                                raise ValueError(f'No files found in folder {item.name} that match the pattern '
                                                 f'{session_file_suffix}')

                            elif len(session_file) > 1:
                                raise ValueError(
                                    f'More than one file found in folder {item.name} that match the pattern '
                                    f'{session_file_suffix}. Please specify a more specific pattern and check '
                                    f'your data.')
                            else:
                                session_file = session_file[0]

                            # TODO: introduce a session object?
                            is_pilot = self.include_pilots and (item in pilots)

                            ses = Session(
                                participant_id=int(item.name.split('_')[0]),
                                session_identifier=item.name,
                                session_folder_path=Path(item.path),
                                session_file_path=session_file,
                                session_file_name=session_file.name,
                                is_pilot=is_pilot,
                            )

                            self.sessions[item.name] = ses

                            # check if asc files are already available
                            if not convert_to_asc and self.eye_tracker == 'eyelink':
                                asc_file = Path(item.path).glob('*.asc')
                                if len(list(asc_file)) == 1:
                                    asc_file = list(asc_file)[0]
                                    self.sessions[item.name].asc_path = asc_file
                                    print(f'Found asc file for {item.name}.')

                    else:
                        print(f'Folder {item.name} does not match the regex pattern {session_folder_regex}. '
                              f'Not considered as session.')

        if convert_to_asc:
            self.convert_edf_to_asc()

    @eyelink
    def convert_edf_to_asc(self) -> None:

        if not self.sessions:
            raise ValueError('No sessions added. Please add sessions first.')

        # TODO: make sure that edf2asc is installed on the computer
        for session in tqdm(self.sessions, desc='Converting EDF to ASC'):
            path = Path(self.sessions[session].session_file_path)

            if not path.with_suffix('.asc').exists():

                subprocess.run(['edf2asc', path])

                asc_path = path.with_suffix('.asc')
                self.sessions[session].asc_path = asc_path
            else:
                asc_path = path.with_suffix('.asc')
                self.sessions[session].asc_path = asc_path
                # print(f'ASC file already exists for {session}.')

    @staticmethod
    def load_lab_config(stimulus_dir: Path, lang: str,
                        country: str, labnum: int, city: str, year: int, ) -> LabConfig:
        """
        Load the lab configuration from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param lang: The language of the stimuli.
        :param country: The country of the stimuli.
        :param labnum: The lab number.
        :param city: The city of the stimuli.
        :param year: The year of the stimuli.

        """
        return LabConfig.load(stimulus_dir, lang, country, labnum, city, year)

    @classmethod
    def create_from_data_folder(cls, data_dir: str | Path,
                                additional_folder: str | None = None,
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
        _, stimulus_language, country, city, lab_number, year = data_folder_name.split(
            '_')
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

        session_folder_regex = r"\d\d\d" + \
                               f"_{stimulus_language}_{country}_{lab_number}" + r"_ET\d"

        stimulus_folder_path = data_dir / f'stimuli_{data_folder_name}'
        config_file = (stimulus_folder_path /
                       'config' /
                       f'config_{stimulus_language.lower()}_{country.lower()}_{city}_{lab_number}.py')

        lab_configuration_data = cls.load_lab_config(stimulus_folder_path, stimulus_language,
                                                     country, int(lab_number), city, int(year))

        eye_tracker = lab_configuration_data.name_eye_tracker
        psychometric_tests = lab_configuration_data.psychometric_tests

        et_data_path = data_dir / 'eye-tracking-sessions' / \
                       additional_folder if additional_folder else data_dir / 'eye-tracking-sessions'
        ps_tests_path = data_dir / 'psychometric-tests-sessions' / \
                        additional_folder if additional_folder else data_dir / 'psychometric-tests'

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
            include_pilots=include_pilots,
            pilot_folder=et_data_path / 'pilot_sessions' if include_pilots else None,
            psychometric_tests=psychometric_tests,
            ps_tests_path=ps_tests_path,
        )

    def create_sanity_check_report(
            self,
            gaze: pm.Gaze,
            session_name: str,
            output_dir: Path | str = '',
            plotting: bool = True,
            overwrite: bool = False,

    ) -> None:
        """
        Create the sanity checks and reports if for one or multiple sessions.
        :param output_dir:
        :param gaze:
        :param session_name: Specifies which session to create the report for.
        :param plotting: If True, all plots are also created for all the sessions.
        :param overwrite: If True, the sanity check report is overwritten if it already exists.
        """

        if session_name in self.excluded_sessions:
            logging.info(
                f"Session {session_name} is excluded from the analysis. Skipping sanity check report.")
            return

        if not output_dir:
            output_dir = self.reports_dir

        session_results = output_dir / session_name
        os.makedirs(session_results, exist_ok=True)

        report_file_path = output_dir / \
                           session_name / f"{session_name}_report.txt"
        self.sessions[session_name].sanity_report_path = report_file_path

        if not report_file_path.exists() or overwrite:

            open(report_file_path, "w", encoding="utf-8").close()

            messages = self.sessions[session_name].messages

            if not messages:
                self._write_to_logfile(
                    f"No messages found in asc file of {session_name}.")


            stimuli = self.sessions[session_name].stimuli

            with open(report_file_path, "a+", encoding="utf-8") as report_file:
                # set report object
                report = partial(report_meta, report_file=report_file)
                check_metadata(
                    self.sessions[session_name].pm_gaze_metadata,
                    self.sessions[session_name].calibrations,
                    self.sessions[session_name].validations,
                    report)

            self._check_logfiles(stimuli, session_name)
            self._check_stimuli_gaze_frame(gaze, stimuli, session_name)
            self._check_asc_messages(stimuli, messages, session_name)
            self._check_asc_validation(session_name)
            self._load_psychometric_tests(session_name)
            self._extract_question_answers(stimuli, session_name)
            fix_report = self._check_avg_fix_durations(gaze)

            fix_report.write_csv(
                file=self.reports_dir / session_name / f"fixation_statistics_per_page_{session_name}.tsv",
                separator='\t',
            )

            if plotting:
                self._create_plots(gaze, stimuli, session_name, aoi=True)

    def _load_manual_corrections(self) -> list[str]:
        # read excluded sessions from txt file if it exists in the top data folder
        manual_corrections = self.data_root.parent / \
                             'manual_preprocessing_corrections.yaml'
        if manual_corrections.exists():
            with open(manual_corrections, 'r') as f:
                yaml_dict = yaml.load(f, Loader=yaml.SafeLoader)
                if 'excluded_sessions' in yaml_dict:
                    excluded_sessions = yaml_dict['excluded_sessions']
                    if excluded_sessions:
                        self.excluded_sessions = list(excluded_sessions.keys())
                if 'stimuli_session_mapping' in yaml_dict:
                    self.session_stimulus_mapping = yaml_dict['stimuli_session_mapping']

        else:
            # create the file so that we can write to it later
            with open(manual_corrections, 'w', encoding='utf8') as f:
                yaml.dump({'excluded_sessions': {}}, f)

        return []

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

    def create_dataset_overview(self, path: str | Path = '') -> dict:
        """
        Create an overview of the dataset and save it as a yaml file in the top data folder.
        :return: overview dict
        """

        if not path:
            overview_path = self.data_root.parent / \
                            f"{self.data_collection_name}_overview.yaml"

        else:
            overview_path = path / f"{self.data_collection_name}_overview.yaml"

        num_sessions = len(self.sessions)
        num_pilots = len(
            [session for session in self.sessions if self.sessions[session].is_pilot])

        # TODO: add more, check metadata scheme, add stats like num read pages, total reading time etc.
        overview = {
            'Title': self.data_collection_name,
            'Dataset_type': self.type,
            'Number_of_sessions': num_sessions,
            'Number_of_pilots': num_pilots,
            'Tested_language': self.language,
            'Country': self.country,
            'Year': self.year,
            'Number of eye-tracking (ET) sessions per participant': self.num_sessions,

        }

        with open(overview_path, 'w', encoding='utf8') as f:
            yaml.dump(overview, f)

        return overview

    def create_session_overview(self, session_idf: str, path: str | Path = '') -> dict:
        sess = self.sessions[session_idf]

        if not path:
            overview_path = self.data_root.parent / \
                            f"{session_idf}_overview.yaml"
        else:
            overview_path = path / f"{session_idf}_overview.yaml"

        with open(overview_path, 'w', encoding='utf8') as f:
            yaml.dump(sess.create_overview(), f)

    def prepare_session_level_information(self):
        """
        Load the logfiles and completed stimuli for all sessions. All of this information is needed repeatedly
        in the sanity checks and is therefore loaded once here.
        :return:
        """

        for session in (pbar := tqdm(self.sessions.keys(), total=len(self.sessions))):
            pbar.set_description(f"Preparing session {session}")
            p_id = session.split('_')[0]

            if 'start_after_trial' in session:
                if p_id not in self.crashed_session_ids:
                    self.crashed_session_ids.append(p_id)
                    self._write_to_logfile(
                        f"Session {session} started after a trial. Only the completed stimuli will be considered.")

            self.sessions[session].completed_stimuli_ids, self.sessions[
                session].stimuli_trial_mapping = self._load_session_completed_stimuli(session)
            self.sessions[session].messages = self._parse_asc(session)
            self.sessions[session].logfile = self._load_session_logfile(
                session)
            self.sessions[session].randomization_version = self._load_stimulus_order_version_from_logfile(
                session)
            self.sessions[session].stimulus_order_ids = self._load_session_stimulus_order(
                session, self.sessions[session].randomization_version)

            # TODO: lab config should be changeable for each session
            self.sessions[session].lab_config = self.lab_configuration

            if self.sessions[session].stimulus_order_ids != self.sessions[session].completed_stimuli_ids:
                if not p_id in self.crashed_session_ids:
                    self._write_to_logfile(f"Stimulus order and completed stimuli do not match for session {session}. "
                                           f"Please check the files carefully.")

            self.sessions[session].stimuli = self._load_session_stimuli(self.stimulus_dir, self.language,
                                                                        self.country,
                                                                        self.lab_number,
                                                                        self.sessions[session].randomization_version,
                                                                        session,
                                                                        )

    def _load_session_stimuli(self, stimulus_dir: Path, lang: str,
                              country: str, lab_num: int,
                              stimulus_order_version: int,
                              session_identifier: str,
                              stimulus_names: None | list = None,
                              ) -> list[Stimulus]:
        """
        Load the stimuli from the specified directory.
        :param stimulus_dir: The directory where the stimuli are stored.
        :param lang: The language of the stimuli.
        :param country: The country of the stimuli.
        :param stimulus_names: The names of the stimuli to load. If None, the predefined stimuli names in the
        global variable self.stimulus_names are used.
        :param stimulus_order_version: The version of the questions to load. Specifies how the questions are ordered and the
        shuffling of the answer options.
        :param lab_num: The lab number.

        """
        stimuli = []
        if stimulus_names is None:
            stimulus_names = [name for name, num in self.stimulus_names.items()
                              if num in self.sessions[session_identifier].completed_stimuli_ids]

        for stimulus_name in stimulus_names:
            trial_mapping = self.sessions[session_identifier].stimuli_trial_mapping
            # get the trial id from the mapping, keys are ids and values are strings
            trial_id = [key for key, value in trial_mapping.items() if value == stimulus_name]
            if len(trial_id) == 0:
                raise KeyError(f"Stimulus name {stimulus_name} not found in the trial mapping for session "
                               f"{session_identifier}. Please check the completed_stimuli.csv file.")

            stimulus = Stimulus.load(
                stimulus_dir, lang, country, lab_num, stimulus_name, stimulus_order_version, trial_id[0])
            stimuli.append(stimulus)

        return stimuli

    def _load_stimulus_order_version_from_logfile(self, session_identifier: str) -> int:
        """
        Extract the question order and version from the session identifier.
        :param session_identifier: The session identifier.
        :return: The question order version to correctly map participant, stimulus and question order versions.
        """
        session_path = self.sessions[session_identifier].session_folder_path
        logfile_path = Path(f'{session_path}/logfiles')
        general_logfile = logfile_path.glob('GENERAL_LOGFILE_*.txt')
        general_logfile = next(general_logfile)
        assert general_logfile.exists(
        ), f"Logfile path {general_logfile} does not exist."

        regex = r"(STIMULUS_ORDER_VERSION_)(?P<order_version>\d+)"
        with open(general_logfile, "r", encoding="utf-8") as f:
            text = f.read()
        match = re.search(regex, text)

        if match:
            stimulus_order_version_logfile = int(
                match.groupdict()['order_version'])
        else:
            raise ValueError(
                f"Could not find question order version in {general_logfile}.")

        return stimulus_order_version_logfile

    def _load_session_logfile(self, session_identifier):
        """
        Load the logfiles for the specified session. Stores the logfile and the completed stimuli as a polars DataFrame,
        the order of the stimuli as list, and the version of the question oder as an int.
        :param session_identifier: The session identifier.
        """

        session_path = self.sessions[session_identifier].session_folder_path
        logfile_folder = Path(f'{session_path}/logfiles')

        assert logfile_folder.exists(
        ), f"Logfile folder {logfile_folder} does not exist."
        logfile = logfile_folder.glob("EXPERIMENT_*.txt")

        logfiles = list(logfile)

        if len(logfiles) != 1:
            raise ValueError(
                f"More than one or no logfile found in {logfile_folder}. Please check the logfiles carefully. "
                f"This can happen if the experiment crashed early and was restarted, in that case the earlier logfiles can be deleted.")

        try:
            logfile = pl.read_csv(logfiles[0], separator="\t")
        except ComputeError:
            raise ValueError(f"Could not read logfile {logfiles[0]}. Most probably there is a line break in one of the "
                             f"answer options that is written to the file. Please check manually and remove the line break.")
        return logfile

    def _load_session_completed_stimuli(self, session_identifier):

        session_path = self.sessions[session_identifier].session_folder_path
        logfile_folder = Path(f'{session_path}/logfiles')
        completed_stim_path = logfile_folder / 'completed_stimuli.csv'

        completed_stimuli = pl.read_csv(completed_stim_path, separator=",")

        p_id = session_identifier.split('_')[0]

        # load trial to stimulus mapping
        trial_ids = completed_stimuli['trial_id'].to_list()
        # sometimes there are None values in the trial ids if a session was interrupted. Those are excluded for this step
        if None in trial_ids:
            trial_ids.remove(None)

        for trial in trial_ids:
            if trial == 'PRACTICE_1':
                trial_ids[trial_ids.index(trial)] = 'PRACTICE_trial_1'
            elif trial == 'PRACTICE_2':
                trial_ids[trial_ids.index(trial)] = 'PRACTICE_trial_2'
            else:
                try:
                    trial_ids[trial_ids.index(trial)] = f'trial_{int(trial)}'
                except TypeError:
                    trial_ids = trial_ids
                    pass

        stimulus_names = completed_stimuli['stimulus_name'].to_list()
        stimuli_trial_mapping = {
            str(trial): name for trial, name in zip(trial_ids, stimulus_names)}

        if completed_stimuli['completed'].cast(pl.Utf8).str.contains('restart').any():
            if p_id not in self.crashed_session_ids:
                self.crashed_session_ids.append(p_id)
                self._write_to_logfile(
                    f"Session {session_identifier} has been restarted. Only the completed stimuli will be considered.")
            # delete the last row in the csv if it contains 'restart' in the completed column
            completed_stimuli = completed_stimuli[:-1]

        completed_stimuli = completed_stimuli.cast({'completed': pl.Int8})
        completed_stimuli = completed_stimuli.filter(
            completed_stimuli['completed'] == 1)['stimulus_id'].to_list()

        return completed_stimuli, stimuli_trial_mapping

    def _load_session_stimulus_order(self, session_identifier, logfile_order_version: int) -> list[int]:

        # if the session crashed, only load the stimuli that were actually completed in that session
        p_id = session_identifier.split('_')[0]
        incomplete_order = []
        if p_id in self.crashed_session_ids:
            incomplete_order = self.sessions[session_identifier].completed_stimuli_ids

        # get the entry where the participant id matches
        stim_order_version = self.stim_order_versions[self.stim_order_versions['participant_id'] == int(
            p_id)]
        if len(stim_order_version) == 0:
            self._write_to_logfile(f"Participant ID {p_id} not found in stimulus order versions. Please check the "
                                   f"participant IDs in the stimulus order versions file. It is possible that the team did not "
                                   f"upload the correct stimulus version from the experiment folder. Extracting version "
                                   f"from asc file")
            version = extract_stimulus_version_number_from_asc(self.sessions[session_identifier].asc_path)

            if version == logfile_order_version:
                self._write_to_logfile(
                    f"Stimulus order version in logfile ({logfile_order_version}) does not match the version "
                    f"extracted from the asc file ({version}) for participant ID {p_id}. Using the "
                    f"version from the logfile.")
                stim_order_version = self.stim_order_versions[self.stim_order_versions['version_number'] == version]

            else:
                self._write_to_logfile(
                    f"Stimulus order version in logfile ({logfile_order_version}) does not match the version "
                    f"extracted from the asc file ({version}) for participant ID {p_id}. OR no version found in asc file. "
                    f"Please check the files "
                    f"carefully.")

        if len(stim_order_version) == 1:
            version = stim_order_version['version_number'].values[0]
            if logfile_order_version != version:
                self._write_to_logfile(
                    f"Stimulus order version in logfile ({logfile_order_version}) does not match the version "
                    f"in the stimulus order versions file ({version}) for participant ID {p_id}. Using the "
                    f"version from the logfile.")
            stimulus_order = stim_order_version.drop(
                columns=['version_number', 'participant_id']).values[0].tolist()

            if incomplete_order:
                stimulus_order_copy = stimulus_order.copy()
                incom, comp = 0, 0
                for _ in range(len(stimulus_order)):

                    if len(incomplete_order) == incom:
                        return incomplete_order

                    if incomplete_order[incom] == stimulus_order_copy[comp]:
                        incom += 1
                        comp += 1
                        continue

                    if incomplete_order[incom] != stimulus_order_copy[comp]:
                        stimulus_order_copy.pop(incom)

                    if stimulus_order_copy == incomplete_order:
                        return incomplete_order

                    if len(stimulus_order_copy) < len(incomplete_order):
                        raise ValueError(
                            'Crashed session stimulus order is not a subset of the stimuli order which was '
                            'supposed to be completed.')
                return incomplete_order

            return stimulus_order

        else:
            raise ValueError(f"More than one or no entry found for participant ID {p_id} in stimulus order versions. "
                             f"Please check the stimulus order versions file for duplicates.")


    def _parse_asc(self, session_identifier: str):
        """
       qick fix for now, should be replaced by the summary experiment frame later on, however the extraction of the
       stimulus order version is essential for other code parts, it cannot be removed without further alterations
        """
        regex = re.compile(
            r'MSG\s+(?P<timestamp>\d+[.]?\d*)\s+(?P<message>.*)')
        start_regex = re.compile(
            r'MSG\s+(?P<timestamp>\d+)\s+(?P<type>start_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)')
        stop_regex = re.compile(
            r'MSG\s+(?P<timestamp>\d+)\s+(?P<type>stop_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)')

        other_screens = ['welcome_screen', 'informed_consent_screen', 'start_experiment', 'stimulus_order_version',
                         'showing_instruction_screen',
                         'camera_setup_screen', 'practice_text_starting_screen', 'transition_screen',
                         'final_validation', 'show_final_screen',
                         'optional_break_screen', 'fixation_trigger:skipped_by_experimenter',
                         'fixation_trigger:experimenter_calibration_triggered',
                         'recalibration', 'empty_screen', 'obligatory_break', 'optional_break', ]

        asc_file = self.sessions[session_identifier].asc_path
        stimuli_trial_mapping = self.sessions[session_identifier].stimuli_trial_mapping

        other_screen_appearance = {
            'timestamp': [],
            'screen': [],
        }

        reading_times = {
            'start_ts': [],
            'stop_ts': [],
            'start_msg': [],
            'stop_msg': [],
            'duration_ms': [],
            'duration_str': [],
            'trials': [],
            'pages': [],
            'status': [],
            'stimulus_name': [],
        }

        breaks = {
            'start_ts': [],
            'stop_ts': [],
            'duration_ms': [],
            'type': [],
        }

        messages = []

        initial_ts = 0

        result_folder = self.reports_dir / session_identifier
        os.makedirs(result_folder, exist_ok=True)
        in_break = False

        with open(asc_file, "r", encoding="utf-8") as f:

            for l in f.readlines():

                if match := regex.match(l):
                    messages.append(match.groupdict())
                    msg = match.groupdict()['message']
                    ts = match.groupdict()['timestamp']

                    if not initial_ts:
                        initial_ts = ts

                    for screen in other_screens:
                        if screen in l:
                            other_screen_appearance['screen'].append(msg)
                            other_screen_appearance['timestamp'].append(ts)

                    if msg == 'optional_break' and not in_break:
                        in_break = True
                        breaks['start_ts'].append(ts)
                        breaks['type'].append('optional')
                    elif msg == 'optional_break_end' and in_break:
                        in_break = False
                        breaks['stop_ts'].append(ts)
                    elif msg.split()[0] == 'optional_break_duration:':
                        breaks['duration_ms'].append(msg.split()[1])

                    elif msg == 'obligatory_break' and not in_break:
                        in_break = True
                        breaks['start_ts'].append(ts)
                        breaks['type'].append('obligatory')
                    elif msg == 'obligatory_break_end' and in_break:
                        in_break = False
                        breaks['stop_ts'].append(ts)
                    elif msg.split()[0] == 'obligatory_break_duration:':
                        breaks['duration_ms'].append(msg.split()[1])

                if match := start_regex.match(l):
                    reading_times['start_ts'].append(
                        match.groupdict()['timestamp'])
                    reading_times['start_msg'].append(
                        match.groupdict()['type'])

                    trial = match.groupdict()['trial']
                    # trial = trial.replace('trial_', '')
                    reading_times['trials'].append(trial)

                    if trial in stimuli_trial_mapping:
                        reading_times['stimulus_name'].append(
                            stimuli_trial_mapping[trial])
                    else:
                        reading_times['stimulus_name'].append('unknown')

                    reading_times['pages'].append(match.groupdict()['page'])
                    reading_times['status'].append('reading time')
                elif match := stop_regex.match(l):
                    reading_times['stop_ts'].append(
                        match.groupdict()['timestamp'])
                    reading_times['stop_msg'].append(match.groupdict()['type'])

            self._document_reading_times(
                initial_ts, reading_times, result_folder, session_identifier)

            other_screens_df = pd.DataFrame(other_screen_appearance)
            other_screens_df.to_csv(
                result_folder / f'other_screens_{session_identifier}.tsv', sep='\t', index=False)

            if not in_break:
                breaks_df = pd.DataFrame(breaks)
                breaks_df.to_csv(
                    result_folder / f'breaks_{session_identifier}.tsv', sep='\t', index=False)
            else:
                self._write_to_logfile(f"Session {session_identifier} did not finish a break properly, "
                                       f"missing end message.")

        return messages

    def _document_reading_times(self, initial_ts, reading_times, result_folder, session_identifier):
        """
        TODO: improve this function!! this is terrible and buggy
        :param initial_ts:
        :param reading_times:
        :param result_folder:
        :param session_identifier:
        :return:
        """

        stimuli_trial_mapping = self.sessions[session_identifier].stimuli_trial_mapping
        total_reading_duration_ms = 0

        for start, stop in zip(reading_times['start_ts'], reading_times['stop_ts']):
            time_ms = int(stop) - int(start)
            time_str = convert_to_time_str(time_ms)
            reading_times['duration_ms'].append(time_ms)
            reading_times['duration_str'].append(time_str)
            total_reading_duration_ms += time_ms

        # calculate duration between pages
        temp_stop_ts = reading_times['stop_ts'].copy()
        temp_stop_ts.insert(0, initial_ts)
        temp_stop_ts = temp_stop_ts[:-1]
        total_set_up_time_ms = 0

        for stop, start, page, trial in zip(temp_stop_ts, reading_times['start_ts'], reading_times['pages'],
                                            reading_times['trials']):
            time_ms = int(start) - int(stop)
            time_str = convert_to_time_str(time_ms)
            reading_times['duration_ms'].append(time_ms)
            reading_times['duration_str'].append(time_str)
            reading_times['start_msg'].append('time inbetween')
            reading_times['stop_msg'].append('time inbetween')
            reading_times['start_ts'].append(stop)
            reading_times['stop_ts'].append(start)
            reading_times['trials'].append(trial)
            total_set_up_time_ms += time_ms

            if trial in stimuli_trial_mapping:
                reading_times['stimulus_name'].append(
                    stimuli_trial_mapping[trial])
            else:
                reading_times['stimulus_name'].append('unknown')

            reading_times['pages'].append(page)
            reading_times['status'].append('time before pages and breaks')

        df = pd.DataFrame({
            'start_ts': reading_times['start_ts'],
            'stop_ts': reading_times['stop_ts'],
            'trial': reading_times['trials'],
            'stimulus': reading_times['stimulus_name'],
            'page': reading_times['pages'],
            'type': reading_times['status'],
            'duration_ms': reading_times['duration_ms'],
            'duration-hh:mm:ss': reading_times['duration_str']
        })

        df.to_csv(
            result_folder / f'times_per_page_{session_identifier}.tsv', sep='\t', index=False, )
        sum_df = df[['stimulus', 'trial', 'type',
                     'duration_ms', 'start_ts', 'stop_ts']].dropna()
        sum_df['duration_ms'] = sum_df['duration_ms'].astype(float)
        sum_df = sum_df.groupby(by=['stimulus', 'trial', 'type']).agg(
            {'duration_ms': 'sum', 'start_ts': 'min', 'stop_ts': 'max'}).reset_index()
        duration = sum_df['duration_ms'].apply(
            lambda x: convert_to_time_str(x))
        sum_df['duration-hh:mm:ss'] = duration

        sum_df.to_csv(
            result_folder / f'times_per_stimulus_{session_identifier}.tsv', index=False, sep='\t')

        start_end_per_stimulus = sum_df[['stimulus', 'trial', 'start_ts', 'stop_ts']].dropna()[
            ~sum_df['type'].str.contains('time before')]

        self.sessions[session_identifier].stimulus_start_end_ts = start_end_per_stimulus.to_dict(
            orient='records')

        total_times = pd.DataFrame({
            'session': session_identifier,
            'lab': self.lab_number,
            'language': self.language,
            'total_trials': [len(sum_df) / 2],
            'total_pages': [len(df) / 2],
            'total_reading_time': [convert_to_time_str(total_reading_duration_ms)],
            'total_non-reading_time': [convert_to_time_str(total_set_up_time_ms)],
            'total_exp_time': [convert_to_time_str(total_reading_duration_ms + total_set_up_time_ms)]
        })

        if os.path.exists(self.data_root.parent / f'total_reading_times.tsv'):
            temp_total_times = pd.read_csv(
                self.data_root.parent / 'total_reading_times.tsv', sep='\t')
            if session_identifier not in temp_total_times['session'].tolist():
                total_times = pd.concat(
                    [temp_total_times, total_times], ignore_index=True)

        total_times.to_csv(self.data_root.parent /
                           'total_reading_times.tsv', sep='\t', index=False)


    def _check_asc_validation(self, session_identifier: str) -> None:
        """
        Check the validations in the asc file for the specified session.
        :param session_identifier: The session identifier.
        :param gaze: If the gaze data has already been created it can be passed as an argument.
        If not it will be created.
        """

        # sort stimulus times into list by start and end time
        sorted_stimuli = sorted(
            self.sessions[session_identifier].stimulus_start_end_ts, key=lambda x: float(x['start_ts']))
        sorted_start_end = []
        for stimulus in sorted_stimuli:
            sorted_start_end.append(
                {'message': f'{stimulus["stimulus"]}_start', 'time': float(stimulus['start_ts'])})
            sorted_start_end.append(
                {'message': f'{stimulus["stimulus"]}_end', 'time': float(stimulus['stop_ts'])})

        check_validation_requirements(self.sessions[session_identifier].validations,
                                      self.sessions[session_identifier].calibrations,
                                      self.sessions[session_identifier].sanity_report_path,
                                      sorted_start_end)

    def _check_stimuli_gaze_frame(self, gaze, stimuli, session_identifier):
        """
        """
        logging.debug(
            f"Checking asc file all screens for {session_identifier} all screens.")

        sanity_check_gaze_frame(
            gaze, stimuli, self.sessions[session_identifier].sanity_report_path)

    def _check_asc_messages(self, stimuli, messages, session_identifier: str) -> None:
        """
        Check the instructions for the specified session.
        :param messages:
        :param stimuli:
        :param session_identifier: The session identifier. eg "005_ET_EE_1_ET1"
        """

        p_id = session_identifier.split('_')[0]
        check_messages(messages, stimuli, self.sessions[session_identifier].sanity_report_path,
                       self.sessions[session_identifier].completed_stimuli_ids,
                       restarted=p_id in self.crashed_session_ids)

    def _check_logfiles(self, stimuli, session_identifier):
        """
        Check the experiment logfile for the specified session.
        :param stimuli:
        :param session_identifier: The session identifier.
        :return:
        """

        check_all_screens_logfile(self.sessions[session_identifier].logfile,
                                  stimuli, self.sessions[session_identifier].sanity_report_path)

    @staticmethod
    def _check_avg_fix_durations(gaze: pm.Gaze) -> pl.DataFrame:
        """
        Check the average fixation durations for the specified session.
        :param gaze: Gaze object for this session.
        """

        # for each gaze and page compute the average fixation duration
        fixation_durations_page_avg = (
            gaze.events.frame.filter(pl.col("name") == "fixation")
            .group_by(gaze.trial_columns)
            .agg([
                pl.col("duration").mean().alias("mean_fixation_duration_ms"),
                pl.col("duration").median().alias("median_fixation_duration_ms"),
                pl.col("duration").max().alias("max_fixation_duration_ms"),
                pl.col("duration").min().alias("min_fixation_duration_ms"),
                pl.col("duration").sum().alias("sum_fixation_duration_ms"),
            ])
        )

        # write to file
        return fixation_durations_page_avg


    def _load_psychometric_tests(self, session_identifier: str):
        if self.psychometric_tests:
            for test in self.psychometric_tests:
                test_path = self.data_root.parent / \
                            'psychometric-tests-sessions' / session_identifier
                if not test_path.exists():
                    self._write_to_logfile(
                        f"Psychometric test path {test_path} does not exist for session {session_identifier}.")
                else:
                    if test == 'PLAB':
                        preprocess_plab(path=test_path)
                    elif test == 'RAN':
                        preprocess_ran(path=test_path)
                    elif test == 'Stroop':
                        preprocess_stroop(path=test_path)
                    elif test == 'Flanker':
                        preprocess_flanker(path=test_path)
                    elif test == 'WikiVocab':
                        preprocess_wikivocab(path=test_path)
                    elif test == 'LWMC':
                        preprocess_lwmc(path=test_path)
                    else:
                        self._write_to_logfile(f"Psychometric test {test} not recognized. "
                                               f"Please check the psychometric tests configuration in the lab configuration yaml file.")

    def _extract_question_answers(self, stimuli: list[Stimulus], session_identifier: str) -> None:

        # TODO: Jana

        check_comprehension_question_answers(self.sessions[session_identifier].logfile,
                                             stimuli, self.sessions[session_identifier].sanity_report_path)

    def _create_plots(self, gaze, stimuli, session_identifier, aoi=False):

        plot_dir = self.reports_dir / session_identifier / \
                   f"{session_identifier}_plots"
        plot_dir.mkdir(exist_ok=True)

        plot_main_sequence(gaze.events, plot_dir)

        for stimulus in stimuli:
            plot_gaze(gaze, stimulus, plot_dir, aoi_image=aoi)

    def parse_participant_data(self, path: Path | str) -> None:
        """
        Load the participant data for all participants.
        """

        participant_data = pd.DataFrame()

        for idx, session in (pbar := tqdm(enumerate(self.sessions), total=len(self.sessions))):
            pbar.set_description(f'Parsing participant data : {session}')
            notes = ''
            folder = Path(self.sessions[session].session_folder_path)
            try:
                participant_id, country, lang, lab, session_id = session.split(
                    '_')
            except ValueError:
                if 'start_after_trial_' in session:
                    logging.warning(f'Session {session} has been restarted.')
                    participant_id, country, lang, lab, session_id, _, _, _, trial = session.split(
                        '_')
                    notes = f'Session has been restarted after trial {trial}.'
                elif 'full_restart' in session:
                    logging.warning(f'Session {session} has been fully restarted.')
                    participant_id, country, lang, lab, session_id, _, _, = session.split(
                        '_')
                    notes = f'Session has been fully restarted.'
                else:
                    raise ValueError(
                        f"Session {session} does not match the expected format.")

            pq_file = folder / \
                      f'{participant_id}_{country}_{lang}_{lab}_pq_data.json'
            if pq_file.exists():
                with open(pq_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # due to a bug in an earlier version of the experiment, some of the participant data has been lost,
                # and we need to correct it
                if 'native_language_1_academic_reading_time' not in data:
                    data = remap_wrong_pq_values(data)

                data['participant_id'] = participant_id
                data['notes'] = notes
                data['session'] = session_id

                participant_data = pd.concat(
                    [participant_data, pd.DataFrame(data, index=[idx])], ignore_index=True)

            else:
                logging.warning(
                    f"No participant data found for session {session}. Skipping.")

        # reorder columns such that participant_id is the first column
        if not participant_data.empty:
            cols = participant_data.columns.tolist()
            cols = ['participant_id'] + \
                   [col for col in cols if col != 'participant_id']
            participant_data = participant_data[cols]

            if not path:
                self.participant_data_path = self.data_root.parent / 'participant_data.csv'
            else:
                self.participant_data_path = path

            participant_data.to_csv(
                self.participant_data_path, index=False)

    def _write_to_logfile(self, message: str) -> None:

        log_file = self.data_root.parent / 'preprocessing_logs.txt'
        with open(log_file, 'a', encoding='utf-8') as logs:
            logs.write(message + '\n')


def convert_to_time_str(duration_ms: float) -> str:
    seconds = int(duration_ms / 1000) % 60
    minutes = int(duration_ms / (1000 * 60)) % 60
    hours = int(duration_ms / (1000 * 60 * 60)) % 24

    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    data_collection_folder = 'MultiplEYE_ET_EE_Tartu_1_2025'

    this_repo = Path().resolve().parent

    data_folder_path = this_repo / "data" / data_collection_folder

    multipleye = MultipleyeDataCollection.create_from_data_folder(
        str(data_folder_path))
    # multipleye.add_recorded_sessions(data_root= data_folder_path / 'eye-tracking-sessions' / 'core_dataset', convert_to_asc=False, session_folder_regex=r"005_ET_EE_1_ET1")
    # multipleye.create_gaze_frame("005_ET_EE_1_ET1")
    multipleye.create_sanity_check_report(
        ["005_ET_EE_1_ET1", "006_ET_EE_1_ET1"])
    multipleye.create_experiment_frame("005_ET_EE_1_ET1")
