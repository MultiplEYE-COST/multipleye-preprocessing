import warnings

from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection


class Merid(MultipleyeDataCollection):

    num_sessions = 2

    def _load_session_stimulus_order(self, session_identifier, logfile_order_version: int):
        # if the session crashed, only load the stimuli that were actually completed in that session
        p_id = session_identifier.split('_')[0]
        session_id = int(session_identifier.strip()[-1])
        incomplete_order = []
        if p_id in self.crashed_session_ids:
            incomplete_order = self.sessions[session_identifier]['completed_stimuli_ids']

        stim_order_version = self.stim_order_versions[self.stim_order_versions['participant_id'] == int(p_id)]
        if len(stim_order_version) == 0:
            raise KeyError(f"Participant ID {p_id} not found in stimulus order versions. Please check the "
                           f"participant IDs in the stimulus order versions file.")
        elif len(stim_order_version) == 1:
            version = stim_order_version['version_number'].values[0]
            if logfile_order_version != version:
                warnings.warn(
                    f"Stimulus order version in logfile ({logfile_order_version}) does not match the version "
                    f"in the stimulus order versions file ({version}) for participant ID {p_id}. Using the "
                    f"version from the logfile.")
            stimulus_order = stim_order_version.drop(columns=['version_number', 'participant_id']).values[
                    0].tolist()

            if session_id == 1:
                stimulus_order = [stimulus_order[0]] + stimulus_order[2:7]
            elif session_id == 2:
                stimulus_order = [stimulus_order[1]] + stimulus_order[7:]

        else:
            raise ValueError(f"More than one entry found for participant ID {p_id} in stimulus order versions. "
                             f"Please check the stimulus order versions file for duplicates.")

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
                    raise ValueError('Crashed session stimulus order is not a subset of the stimuli order which was '
                                     'supposed to be completed.')
            return incomplete_order

        return stimulus_order

    def _load_psychometric_tests(self, session_identifier: str) -> bool:
        raise NotImplementedError

