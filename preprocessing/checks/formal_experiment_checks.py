from pathlib import Path

import polars as pl

from preprocessing.data_collection.stimulus import Stimulus

OME_TIME_SCREENS = ['welcome_screen', 'informed_consent_screen', 'start_experiment', 'stimulus_order_version',
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

OPTIONAL_SCREENS = ['optional_break_screen', 'fixation_trigger:skipped_by_experimenter',
                    'fixation_trigger:experimenter_calibration_triggered', 'optional_break',
                    'obligatory_break', 'recalibration']

RATING_SCREENS = ['showing_subject_difficulty_screen', 'showing_familiarity_rating_screen_1',
                  'showing_familiarity_rating_screen_2']


def _report_warning(message: str, report_file: Path):
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")


def _report_information(message: str, report_file: Path):
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")


def check_all_screens_logfile(logfile: pl, stimuli: Stimulus | list[Stimulus], report_file: Path = None):
    """
    checking if all screens, where ET data is tracked are present in the log file
    :param: logfile as polars dataframe
    :param: stimuli as list of Stimulus objects
    :param: report_file as Path object where to write the report
    """

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


def sanity_check_gaze_frame(gaze, stimuli, report_file):
    """
    checking if all screens, where ET data is tracked are present in the gaze data frame, which is based on the ASC file
    it checks for all stimuli, if all pages and questions screens are present;it does not check for valditaion, calibration, instructions, etc.
    """
    for stimulus in stimuli:
        # print(f"Checking {stimulus.name}")
        stimulus_frame = gaze.frame.filter(
            (pl.col("stimulus") == f"{stimulus.name}_{stimulus.id}")
        ).unique("page")
        # check if all pages are present
        for page in stimulus.pages:
            if f"page_{page.number}" not in stimulus_frame["page"].to_list():
                # print(f"Missing page {page.number}")
                _report_warning(f"Missing page {page.number} in asc file", report_file)
        # check if all questions are present
        for question in stimulus.questions:
            if f"question_{question.id}" not in stimulus_frame[
                "page"].to_list() and f"question_{question.id[1:]}" not in stimulus_frame["page"].to_list():
                _report_warning(f"Missing question_{question.name} in asc file or in experiment frame", report_file)
            # print(stimulus_frame["screen"])

        for rating in stimulus.ratings:
            if f"{rating.name}" not in stimulus_frame["page"].to_list():
                # print(f"Missing instruction {rating.name}")
                _report_warning(f"Missing rating {rating.name} in asc file", report_file)


# check order in ASC file based on messages
def check_messages(
        messages: list, stimuli: Stimulus | list,
        report_file: Path,
        stimuli_order: list,
        restarted: bool = False,
) -> None:
    """

    :param restarted:
    :param messages:
    :param stimuli: the stimuli ids that were completed in the experiment
    :param report_file:
    :param stimuli_order: the order of the stimuli as they appear in the experiment
    :return:
    """
    messages_only = [d.get('message') for d in messages]

    # checking the actual order of the stimuli based on the messages in the asc file
    if 13 in stimuli_order:
        stimuli_order.remove(13)  # remove the practice trials from the order

    if 7 in stimuli_order:
        stimuli_order.remove(7)

    trial = 0
    for stim_id in stimuli_order:
        try:
            next_id = stimuli_order[trial + 1]
        except IndexError:
            next_id = None

        current_stimulus = None
        next_stimulus = None
        for stimulus in stimuli:
            if stimulus.id == stim_id:
                current_stimulus = stimulus
            if stimulus.id == next_id:
                next_stimulus = stimulus

        if not current_stimulus:
            raise ValueError(f"Stimulus with id {stim_id} not found in stimuli. "
                             f"Experiment did not run correctly. Please check manually.")

        trial += 1  # trials start with 1 in the experiment
        updated_trial = trial

        try:
            index_obligatory_break = messages_only.index("obligatory_break")
        except ValueError:
            index_obligatory_break = 0  # hacky for split versions

        pattern = f"_trial_{trial}_stimulus_{current_stimulus.name}_{current_stimulus.id}"
        try:
            last_msg_index = messages_only.index(f"start_recording{pattern}_page_1")
        except ValueError as e:
            # if the session has been restarted, there might be a mismatch between trial numbers and stimulus ids
            if restarted:
                while updated_trial <= 12:
                    updated_trial += 1
                    pattern = f"_trial_{updated_trial}_stimulus_{current_stimulus.name}_{current_stimulus.id}"
                    pattern = f"start_recording{pattern}_page_1"
                    if pattern in messages_only:
                        last_msg_index = messages_only.index(pattern)
                        break
                else:
                    raise e
            else:
                raise e

        last_msg_timestamp = messages[last_msg_index].get("timestamp")

        # if it is not the last stimulus, check until the next stimulus start
        if next_stimulus:
            index_next_stimulus = messages_only.index(
                f"start_recording_trial_{updated_trial + 1}_stimulus_{next_stimulus.name}_{next_stimulus.id}_page_1")
        else:
            index_next_stimulus = len(messages_only) - 1

        trial_messages_only = messages_only[last_msg_index:index_next_stimulus]

        _extract_reading_time(current_stimulus.name, index_obligatory_break, last_msg_index,
                              last_msg_timestamp, messages, index_next_stimulus,
                              report_file, updated_trial)

        msg_to_find = ["start_recording", "screen_image_onset", "screen_image_offset", "stop_recording"]

        for page in current_stimulus.pages:
            for msg in msg_to_find:
                if msg.startswith("screen"):
                    current_pattern = f"page_{msg}"
                else:
                    current_pattern = f"{msg}{pattern}_page_{page.number}"

                if current_pattern not in trial_messages_only:
                    _report_warning(f"{current_stimulus.name}: Missing {current_pattern} Messages in ASC file",
                                    report_file)

                else:
                    last_msg_index = trial_messages_only.index(current_pattern) + last_msg_index

        _check_rating_screens(trial_messages_only, report_file)

        _check_question_screens(current_stimulus, trial_messages_only, msg_to_find,
                                pattern, report_file)

        _check_validation_screen(trial_messages_only, report_file, current_stimulus.name)

    # final check for the optional and one time screens which are stimulus independent
    _check_one_time_screens(messages_only, report_file)
    _check_optional_screens(messages, messages_only, report_file)


def _check_optional_screens(messages, messages_only, report_file):
    for optional_screen in OPTIONAL_SCREENS:

        indices = list(filter(lambda i: messages_only[i] == optional_screen, range(len(messages_only))))
        if indices:
            _report_information(f"{messages[indices[0]]['message']} found {len(indices)} times", report_file)

            for index in indices:
                if optional_screen == "optional_break" or optional_screen == "obligatory_break":
                    # if it is a break, there should be two messages following the first message. If it is not there,
                    # the session was probably interrupted or there was another error
                    temp_index = index
                    while temp_index <= (index + 10):
                        temp_index += 1
                        if temp_index < len(messages):
                            msg = messages[temp_index]
                            if 'optional_break_duration' in msg['message'] or 'obligatory_break_duration' in msg[
                                'message']:
                                text = msg['message'].split(' ', )[0]
                                duration = float(msg['message'].split(' ', )[1]) / 1000
                                _report_information(
                                    f"{text} lasting {duration:.2f} seconds found at {msg['timestamp']}",
                                    report_file)
                                break
                    else:
                        _report_warning(
                            f"{optional_screen} found at {messages[index]['timestamp']} but no duration found",
                            report_file)

                else:
                    msg = messages[index]
                    _report_information(f"{msg['message']} found at {msg['timestamp']}", report_file)
                    # print(f"{msg['message']} found at {msg['timestamp']}")
        else:
            _report_information(f"{optional_screen} not found", report_file)


def _check_one_time_screens(messages_only: list[str], report_file: Path):
    """
    Checking if all one time screens are present in the asc file. Ignore if they are present.
    :param messages_only:
    :param report_file:
    """
    for one_time_screen in OME_TIME_SCREENS:
        if f"{one_time_screen}" not in messages_only:
            found = False
            for message in messages_only:
                if message.startswith(one_time_screen):
                    found = True

            if not found:
                _report_warning(f"Missing one time screen {one_time_screen} in asc file", report_file)


def _check_question_screens(current_stimulus, messages, msg_to_find, pattern, report_file):
    for question in current_stimulus.questions:
        for msg in msg_to_find:
            if msg.startswith("screen"):  # get the cleaned question_id (removed zero at the start, if present)
                current_pattern = f"question_{msg}"
            else:
                current_pattern = f"{msg}{pattern}_question_{int(question.id)}"

            if current_pattern not in messages:
                _report_warning(f"{current_stimulus.name}: Missing {current_pattern} Messages in ASC file", report_file)


def _extract_reading_time(stimulus_name, index_obligatory_break, last_msg_index, last_msg_timestamp, messages,
                          index_next, report_file, trial):
    # if there was an obligatory break in between two trials, check the time for the break and the time for the stimulus
    if index_next > index_obligatory_break > last_msg_index:
        break_timestamp = messages[index_obligatory_break].get("timestamp")

        trial_duration = round(((float(break_timestamp) - float(last_msg_timestamp)) / 60000), 2)
        _report_information(f"{trial}: {stimulus_name}: {trial_duration} minutes",
                            report_file)

        next_timestamp = messages[index_next].get("timestamp")

        break_duration = round(((float(next_timestamp) - float(break_timestamp)) / 60000), 2)
        _report_information(
            f"obligatory break: {break_duration} minutes",
            report_file
        )

    else:
        next_timestamp = messages[index_next].get("timestamp")
        trial_duration = round(((float(next_timestamp) - float(last_msg_timestamp)) / 60000), 2)
        _report_information(
            f"{trial}:  {stimulus_name}: {trial_duration} minutes",
            report_file)


def _check_validation_screen(messages, file, stimulus_name):
    # print(last_index, index_next_stimulus)
    if "validation_before_stimulus" not in messages and "final_validation" not in messages:
        _report_warning(f"{stimulus_name}: Missing validation_before_stimulus screen in asc file", file)


def _check_rating_screens(messages, file):
    for rating in RATING_SCREENS:
        if f"{rating}" not in messages:
            # print(f"Missing instruction {instruction}")
            _report_warning(f"Missing rating {rating} in asc file", file)
