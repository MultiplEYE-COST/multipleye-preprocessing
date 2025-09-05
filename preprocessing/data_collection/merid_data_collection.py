from pathlib import Path
import polars as pl

from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection


class Merid(MultipleyeDataCollection):

    num_sessions = 2


    def load_session_dependent_stimuli(self, session_identifier: str, full_version: bool = False) -> None:
        """
        Get the sessions that were completed in the specified session.
        :param session_identifier: what session to load the stimuli for
        :param full_version: if True, all stimuli are loaded. If False, only a subset of the original stimuli has been used and
        the original Excel file is checked to see which ones.
        """
        self.load_logfiles(session_identifier)

        stimuli = self.sessions[session_identifier]["completed_stimuli"].filter(pl.col("completed") == True)

        stimulus_names = stimuli["stimulus_name"].to_list()

        session_name = session_identifier
        question_order_version = self._extract_question_order_version(session_name)

        self.sessions[session_name]['session_stimuli'] = self.load_stimuli(
            self.stimulus_dir, self.language, self.country, self.lab_number,
            question_order_version, stimulus_names)

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

        p_id = session_identifier.split('_')[0]

        self.sessions[session_identifier]['logfile'] = logfile
        self.sessions[session_identifier]['completed_stimuli'] = completed_stimuli
        self.sessions[session_identifier]['question_order_version'] = question_version

        session_id = int(session_identifier.split('_')[-1].replace('ET', ''))

        if session_id == 1:
            stimulus_order = [self.stim_order_versions[int(p_id)][0]] + self.stim_order_versions[int(p_id)][2:7]
        elif session_id == 2:
            stimulus_order = [self.stim_order_versions[int(p_id)][1]] + self.stim_order_versions[int(p_id)][7:]


        # if the session was crashed, we only take the completed stimuli
        if p_id in self.crashed_session_ids:
            stimulus_order = completed_stimuli.filter(completed_stimuli['completed'] == True)['stimulus_id'].to_list()

        self.sessions[session_identifier]['stimuli_order'] = stimulus_order

