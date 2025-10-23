import os
import pickle
import re
import subprocess
import warnings
from pathlib import Path

import numpy as np
from pymovements import GazeDataFrame
from tqdm import tqdm

from preprocessing.data_collection.session import Session

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


class DataCollection:
    data_collection_name: str
    year: int
    country: str
    session_folder_regex: str = ''
    data_root: Path = None
    excluded_sessions: list = []

    def __init__(self,
                 data_collection_name: str,
                 stimulus_language: str,
                 country: str,
                 year: int,
                 eye_tracker: str,
                 **kwargs,
                 ):
        """
        
        :param stimulus_language:
        :param country: 
        :param year:
        :param eye_tracker: 
        """
        self.sessions = {}
        # TODO: in theory this can be multiple languages for the stimuli..
        self.language = stimulus_language
        self.country = country
        self.year = year
        self.data_collection_name = data_collection_name

        self.include_pilots = kwargs.get('include_pilots', False)
        self.output_dir = kwargs.get('output_dir', '')
        self.pilot_folder = kwargs.get('pilot_folder', '')

        for short_name, long_name in EYETRACKER_NAMES.items():
            if eye_tracker in long_name:
                self.eye_tracker = short_name
                self.eye_tracker_name = long_name
                break

        else:
            raise ValueError(f'Eye tracker {eye_tracker} not yet supported. '
                             f'Supported eye trackers are: '
                             f'{np.array([val for k, val in EYETRACKER_NAMES.items()]).flatten()}')

    def __iter__(self):
        for session in sorted(self.sessions):
            yield self.sessions[session]


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
                                raise ValueError(f'More than one file found in folder {item.name} that match the pattern '
                                                 f'{session_file_suffix}. Please specify a more specific pattern and check '
                                                 f'your data.')
                            else:
                                session_file = session_file[0]

                            # TODO: introduce a session object?
                            is_pilot = self.include_pilots and (item in pilots)

                            self.sessions[item.name] = {
                                'session_folder_path': item.path,
                                'session_file_path': session_file,
                                'session_file_name': session_file.name,
                                'session_folder_name': item.name,
                                'session_stimuli': '',
                                'is_pilot': is_pilot,
                            }

                            # check if asc files are already available
                            if not convert_to_asc and self.eye_tracker == 'eyelink':
                                asc_file = Path(item.path).glob('*.asc')
                                if len(list(asc_file)) == 1:
                                    asc_file = list(asc_file)[0]
                                    self.sessions[item.name]['asc_path'] = asc_file
                                    print(f'Found asc file for {item.name}.')

                    else:
                        print(f'Folder {item.name} does not match the regex pattern {session_folder_regex}. '
                              f'Not considered as session.')

                # if there are no session folders then we assume that the root folder contains all data files
                elif item.is_file() and item.name.endswith('.edf'):
                    self.sessions[item.name] = {
                        'session_file_path': item.path,
                        'session_file_name': item.name,
                    }

        if convert_to_asc:
            self.convert_edf_to_asc()

    @eyelink
    def convert_edf_to_asc(self) -> None:

        if not self.sessions:
            raise ValueError('No sessions added. Please add sessions first.')

        # TODO: make sure that edf2asc is installed on the computer
        for session in tqdm(self.sessions, desc='Converting EDF to ASC'):
            path = Path(self.sessions[session]['session_file_path'])

            if not path.with_suffix('.asc').exists():

                subprocess.run(['edf2asc', path])

                asc_path = path.with_suffix('.asc')
                self.sessions[session]['asc_path'] = asc_path
            else:
                asc_path = path.with_suffix('.asc')
                self.sessions[session]['asc_path'] = asc_path
                #print(f'ASC file already exists for {session}.')

    def create_gaze_frame(self, session: str | list[str] = '', overwrite: bool = False) -> None:

        raise NotImplementedError

    def get_gaze_frame(self, session_identifier: str,
                       create_if_not_exists: bool = False,
                       ) -> GazeDataFrame:
        """
        Loads and possibly creates the gaze data for the specified session(s).
        :param create_if_not_exists: The gaze data will be created and stored if True.
        :param session_identifier: The session identifier to load the gaz data for.
        :return:
        """

        if session_identifier not in self.sessions:
            raise KeyError(f'Session {session_identifier} not found in {self.data_root}.')

        try:
            gaze_path = self.sessions[session_identifier]['gaze_path']
        except KeyError:
            if create_if_not_exists:
                self.create_gaze_frame(session=session_identifier)
                gaze_path = self.sessions[session_identifier]['gaze_path']
            else:
                raise KeyError(f'Gaze frame not created for session {session_identifier}. Please create first.')

        with open(gaze_path, "rb") as f:
            gaze = pickle.load(f)

        self.sessions[session_identifier]['metadata'] = gaze._metadata

        return gaze

    # TODO: add method to check whether stimuli are completed

    # TODO: for future: think about how to handle stimuli in the general case


if __name__ == '__main__':
    pass
