import logging
from pathlib import Path

import polars as pl

from preprocessing.data_collection.stimulus import Stimulus


def _report_warning(message: str, report_file: Path):
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")


def _report_information(message: str, report_file: Path):
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")


def check_all_screens_logfile(logfile: pl, stimuli: Stimulus | list[Stimulus], report_file: Path = None):
    """ checking if all screens, where ET data is tracked are present in the log file
    params: logfile as polars
    returns nothing"""

    for stimulus in stimuli:
        # print(f"Checking {stimulus.name} in Logfile")
        trial_id = logfile.filter((pl.col("stimulus_number") == f"{stimulus.id}")).item(0,
                                                                                        "trial_number")  # get the trial number for the stimulus as ratingscreens don't have an entry in the stimulus_number column

        stimulus_frame = logfile.filter(
            (pl.col("trial_number") == f"{trial_id}")
        )
        # print(stimulus_frame)
        # check if all pages are present
        for page in stimulus.pages:
            if f"{page.number}" not in stimulus_frame["page_number"].to_list():
                # print(f"Missing page {stimulus.name} {page.number} in Logfile")
                _report_warning(f" {stimulus.name}: Missing page{page.number} in Logfile", report_file)
        # check if all questions are present
        for question in stimulus.questions:
            if f"{question.id}" not in stimulus_frame["page_number"].to_list() and f"{question.id[1:]}" not in \
                    stimulus_frame["page_number"].to_list():
                # print(f"{stimulus.name}: Missing question_{question.id} in Logfile")
                _report_warning(f"{stimulus.name}: Missing question_{question.id} in Logfile", report_file)
            # print(stimulus_frame["screen"])

        for rating in stimulus.ratings:
            if f"{rating.name}" not in stimulus_frame["page_number"].to_list():
                # print(f"{stimulus.name}: Missing rating screen {rating.name}")
                _report_warning(f"{stimulus.name}: Missing rating screen {rating.name} in Logfile",
                                report_file)


def check_all_screens(gaze, stimuli, report_file):
    """ checking if all screens, where ET data is tracked are present in the gaze data frame, which is based on the ASC file
    it checks for all stimuli, if all pages and questions screens are present;it does not check for valditaion, calibration, instructions, etc.
    """
    for stimulus in stimuli:
        # print(f"Checking {stimulus.name}")
        stimulus_frame = gaze.frame.filter(
            (pl.col("stimulus") == f"{stimulus.name}_{stimulus.id}")
        ).unique("screen")
        # check if all pages are present
        for page in stimulus.pages:
            if f"page_{page.number}" not in stimulus_frame["screen"].to_list():
               # print(f"Missing page {page.number}")
                _report_warning(f"Missing page {page.number} in asc file", report_file)
        # check if all questions are present
        for question in stimulus.questions:
            if f"question_{question.id}" not in stimulus_frame[
                "screen"].to_list() and f"question_{question.id[1:]}" not in stimulus_frame["screen"].to_list():
                _report_warning(f"Missing question_{question.name} in asc file or in experiment frame", report_file)
               # print(stimulus_frame["screen"])

        for rating in stimulus.ratings:
            if f"{rating.name}" not in stimulus_frame["screen"].to_list():
                # print(f"Missing instruction {rating.name}")
                _report_warning(f"Missing rating {rating.name} in asc file", report_file)


# check order in ASC file based on messages
def check_instructions(
        messages: list, completed_stimuli: Stimulus | list,
        report_file: Path,
        stimuli_order: list,
        num_sessions: int,
) -> None:
    """

    :param messages:
    :param completed_stimuli: the stimuli ids that were completed in the experiment
    :param report_file:
    :param stimuli_order: the order of the stimuli as they should appear in the experiment
    :param split:
    :return:
    """
    messages_only = [d.get('message') for d in messages]
    one_time_screens = ['welcome_screen', 'informed_consent_screen', 'start_experiment', 'stimulus_order_version',
                        'showing_instruction_screen_1', 'showing_instruction_screen_2', 'showing_instruction_screen_3',
                        'camera_setup_screen', 'practice_text_starting_screen',
                        'start_recording_PRACTICE_trial_1_stimulus_Enc_WikiMoon_13_page_1',
                        'stop_recording_PRACTICE_trial_1_stimulus_Enc_WikiMoon_13_page_1',
                        'start_recording_PRACTICE_trial_1_stimulus_Enc_WikiMoon_13_page_2',
                        'stop_recording_PRACTICE_trial_1_stimulus_Enc_WikiMoon_13_page_2',
                        'start_recording_PRACTICE_trial_1_stimulus_Enc_WikiMoon_13_page_2',
                        'start_recording_PRACTICE_trial_2_stimulus_Lit_NorthWind_7_page_1',
                        'stop_recording_PRACTICE_trial_2_stimulus_Lit_NorthWind_7_page_1', 'transition_screen',
                        'final_validation', 'show_final_screen', 'obligatory_break', 'obligatory_break_end']

    optional_screens = ['empty_screen', 'optional_break_screen', 'fixation_trigger:skipped_by_experimenter',
                        'fixation_trigger:experimenter_calibration_triggered', 'optional_break',
                        'optional_break_duration', 'obligatory_break', 'recalibration']
    reoccurring_screens = ['showing_subject_difficulty_screen', 'showing_familiarity_rating_screen_1',
                          'showing_familiarity_rating_screen_2']

    def _check_validation_screen(last_index, index_next_stimulus):
        # print(last_index, index_next_stimulus)
        if "validation_before_stimulus" not in messages_only[
                                               last_index:index_next_stimulus] and "final_validation" not in messages_only[
                                                                                                             last_index:index_next_stimulus]:

            _report_warning(f"{stimulus.name}: Missing validation_before_stimulus screen in asc file", report_file)

    def _check_instruction_screens(last_index, index_next_stimulus):
        for instruction in reoccurring_screens:
            if f"{instruction}" not in messages_only[last_index:index_next_stimulus]:
                # print(f"Missing instruction {instruction}")
                _report_warning(f"Missing instruction {instruction} in asc file", report_file)



    # checking the actual order of the stimuli based on the messages in the asc file
    if num_sessions == 1:
        exp_stimuli_order = stimuli_order[2:]  # skip the two  practice trials for complete asc file
    elif num_sessions == 2:
        exp_stimuli_order = stimuli_order[1:]  # skip only one practice trial for merid version

    for trial, stim_id in enumerate(exp_stimuli_order):
        try:
            next_id = exp_stimuli_order[trial + 1]
        except IndexError:
            next_id = None

        current_stimulus = None
        next_stimulus = None
        for stimulus in completed_stimuli:
            if stimulus.id == stim_id:
                current_stimulus = stimulus
            if stimulus.id == next_id:
                next_stimulus = stimulus

        if not current_stimulus:
            raise ValueError(f"Stimulus with id {stim_id} not found in completed_stimuli. Experiment did not run correctly. Please check manually.")

        trial += 1  # trials start with 1 in the experiment

        try:
            index_obligatory_break = messages_only.index("obligatory_break")
        except ValueError as e:
            index_obligatory_break = 0  # hacky for split versions
            #logging.info(f"{e} only acceptable if MERid version")

        pattern = f"_trial_{trial}_stimulus_{current_stimulus.name}_{current_stimulus.id}"
        last_index = messages_only.index(f"start_recording{pattern}_page_1")
        last_timestamp = messages[last_index].get("timestamp")

        # if it is not the last stimulus, check until the next stimulus start
        if next_stimulus:
            try:
                index_next_stimulus = messages_only.index(
                f"start_recording_trial_{trial + 1}_stimulus_{next_stimulus.name}_{next_stimulus.id}_page_1")
            except ValueError:
                breakpoint()

            if index_next_stimulus > index_obligatory_break > last_index:
                break_timestamp = messages[index_obligatory_break].get("timestamp")
                _report_information(
                    f"{trial}: {current_stimulus.name}: {round(((float(break_timestamp) - float(last_timestamp)) / 60000), 2)} minutes",
                    report_file)
                next_timestamp = messages[index_next_stimulus].get("timestamp")
                _report_information(
                    f"obligatory break: {round(((float(next_timestamp) - float(break_timestamp)) / 60000), 2)} minutes",
                    report_file)

            else:
                next_timestamp = messages[index_next_stimulus].get("timestamp")
                _report_information(
                    f"{trial}:  {current_stimulus.name}: {round(((float(next_timestamp) - float(last_timestamp)) / 60000), 2)} minutes",
                    report_file)

        else:
            index_next_stimulus = len(messages_only) - 1
            next_timestamp = messages[index_next_stimulus].get("timestamp")
            # print(next_timestamp)
            # print(round(((float(next_timestamp)-float(last_timestamp))/60000), 2))
            _report_information(
                f"{trial}:  {current_stimulus.name}: {((float(next_timestamp) - float(last_timestamp)) / 60000):.2f} minutes",
                report_file)

        msg_to_find = ["start_recording", "screen_image_onset", "screen_image_offset", "stop_recording"]

        for page in current_stimulus.pages:
            for msg in msg_to_find:
                if msg.startswith("screen"):
                    current_pattern = f"page_{msg}"
                else:
                    current_pattern = f"{msg}{pattern}_page_{page.number}"

                if current_pattern not in messages_only[last_index:index_next_stimulus]:
                    _report_warning(f"{current_stimulus.name}: Missing {current_pattern} Messages in ASC file", report_file)

                else:
                    last_index = messages_only[last_index:index_next_stimulus].index(current_pattern) + last_index

        _check_instruction_screens(last_index, index_next_stimulus)

        for question in current_stimulus.questions:
            for msg in msg_to_find:
                if msg.startswith("screen"):  # get the cleaned questio_id (removed zero at the start, if present)
                    current_pattern = f"question_{msg}"
                else:
                    if question.id.startswith("0"):
                        question_id = question.id[1:]
                    else:
                        question_id = question.id

                    current_pattern = f"{msg}{pattern}_question_{question_id}"

                if current_pattern not in messages_only[last_index:index_next_stimulus]:
                    _report_warning(f"{current_stimulus.name}: Missing {current_pattern} Messages in ASC file", report_file)

        _check_validation_screen(last_index, index_next_stimulus)

        for one_time_screen in one_time_screens:
            if f"{one_time_screen}" not in messages_only:
                found = False
                for message in messages_only:
                    if message.startswith(one_time_screen):
                        # print(f"found it {message}")
                        found = True

                if not found:
                    _report_warning(f"Missing one time screen {one_time_screen} in asc file", report_file)
        # else:
        #    print(f"{one_time_screen} found")

        for optional_screen in optional_screens:

            indices = list(filter(lambda i: messages_only[i] == optional_screen, range(len(messages_only))))
            if indices:
                _report_information(f"{messages[indices[0]]['message']} found {len(indices)} times", report_file)

            for index in indices:
                if optional_screen == "optional_break" or optional_screen == "obligatory_break":
                    msg = messages[index + 2]
                    # TODO: check why these end up in here??
                    if not msg['message'] == 'optional_break_end' and not msg['message'] == 'obligatory_break_end':
                        text = msg['message'].split(' ', )[0]
                        duration = float(msg['message'].split(' ', )[1]) / 1000
                        _report_information(f"{text} lasting {duration:.2f} seconds found at {msg['timestamp']}",
                                            report_file)
                        # print(f"{text} lasting {duration:.2f} seconds found at {msg['timestamp']}")

                else:
                    msg = messages[index]
                    _report_information(f"{msg['message']} found at {msg['timestamp']}", report_file)
                    # print(f"{msg['message']} found at {msg['timestamp']}")






