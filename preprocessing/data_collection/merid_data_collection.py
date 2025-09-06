from pathlib import Path
import polars as pl

from preprocessing.data_collection.multipleye_data_collection import MultipleyeDataCollection


class Merid(MultipleyeDataCollection):

    num_sessions = 2

    def _load_session_stimulus_order(self, session_identifier):
        # if the session crashed, only load the stimuli that were actually completed in that session
        p_id = session_identifier.split('_')[0]
        session_id = int(session_identifier.strip()[-1])
        if p_id in self.crashed_session_ids:
            return self.sessions[session_identifier]['completed_stimuli']
        else:
            try:
                stimulus_order = self.stim_order_versions[int(p_id)]
                if session_id == 1:
                    stimulus_order = [stimulus_order[0]] + stimulus_order[2:7]
                elif session_id == 2:
                    stimulus_order = [stimulus_order[1]] + stimulus_order[7:]

            except KeyError:
                raise KeyError(f"Participant ID {p_id} not found in stimulus order versions. Please check the "
                               f"participant IDs in the stimulus order versions file.")

        return stimulus_order

