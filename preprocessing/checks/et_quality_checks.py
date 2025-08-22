import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Callable, TextIO, Union

import PIL
import matplotlib.pyplot as plt
import pandas as pd
import polars as pl
import pymovements as pm
from matplotlib.patches import Circle

from preprocessing import config
from preprocessing.data_collection.stimulus import Stimulus

ReportFunction = Callable[[str, Any, Union[list, tuple]], None]


def report_to_file_metadata(
        name: str,
        values: Any,
        acceptable_values: Any,
        *,
        report_file: TextIO,
        percentage: bool = False,
) -> None:
    """
    Check if the metadata values are in the acceptable values or within the acceptable range and write a report to file.
    :param name: Name of the metadata value
    :param values: Values of the metadata to check
    :param acceptable_values: Acceptable values or range of acceptable values for the metadata value
    :param report_file: Opened file to write the report to
    :param percentage: If True, the values are converted to percentage
    :return:
    """
    if not isinstance(values, (list, tuple)):
        values = [values]
    result = ""

    if isinstance(acceptable_values, list):  # List of acceptable values
        if all(value in acceptable_values for value in values):
            result = "✅"
    elif isinstance(acceptable_values, tuple):  # Range of acceptable values
        lower, upper = acceptable_values
        if all((lower <= value) and (upper >= value) for value in values):
            result = "✅"
    else:  # Single acceptable value
        if all(value == acceptable_values for value in values):
            result = "✅"

    if percentage:
        values = [f"{value:.6%}" for value in values]
    report_file.write(f"{result} {name}: {', '.join(map(str, values))}\n")


def _report_to_file(message: str, report_file: Path):
    assert isinstance(report_file, Path)
    with open(report_file, "a", encoding="utf-8") as report_file:
        report_file.write(f"{message}\n")
    logging.info(message)


def check_comprehension_question_answers(logfile: pl.DataFrame, stimuli: Stimulus | list[Stimulus],
                                         report_file: Path = None):
    """ compute the number of correct answers for each participant
        params: logfile as polars
        returns nothing"""
    overall_correct_answers = 0
    overall_answers = 0
    for stimulus in stimuli:
        if stimulus.type == "practice":
            continue

        # get the trial number for the stimulus as rating screens don't have an entry in the stimulus_number column
        trial_id = logfile.filter((pl.col("stimulus_number") == f"{stimulus.id}")).item(0,
                                                                                        "trial_number")
        stimulus_frame = logfile.filter(
            (pl.col("trial_number") == f"{trial_id}")
        )
        answers = stimulus_frame.filter(pl.col("message").str.contains("FINAL ANSWER"))
        correct_answers = stimulus_frame.filter(pl.col("message").str.contains("True"))
        overall_correct_answers += len(correct_answers)
        overall_answers += len(answers)
        _report_to_file(f"Correct answers for {stimulus.name}: {len(correct_answers)} out of {len(answers)} answers",
                        report_file)

    _report_to_file(
        f"Overall correct answers: {overall_correct_answers} out of {overall_answers} answers {overall_correct_answers / overall_answers:.2f}",
        report_file)


def check_validations(gaze, report_file):
    for num, validation in enumerate(gaze._metadata["validations"]):
        if validation["validation_score_avg"] < "0.305":
            # print(f"Validation score {validation['validation_score_avg']} too low")
            continue
        else:
            # print(validation["validation_score_avg"], validation["timestamp"])
            bad_val_timestamp = float(validation["timestamp"])
            found_val = False

        for cal in gaze._metadata["calibrations"]:
            cal_timestamp = float(cal["timestamp"])
            if bad_val_timestamp < cal_timestamp < bad_val_timestamp + 200000:
                # print(f"Calibration after validation at timestamp {cal['timestamp']}")
                # sanity.report_to_file(f"Calibration after validation at timestamp {cal['timestamp']}", sanity.report_file)
                index_bad_val = gaze._metadata["validations"].index(validation)
                next_validation = gaze._metadata['validations'][index_bad_val + 1]
                time_between = round((float(next_validation["timestamp"]) - bad_val_timestamp) / 1000, 3)
                # print(f"next validation, {time_between} seconds later with score {next_validation['validation_score_avg']}")
                _report_to_file(
                    f"Calibration after validation at timestamp {cal['timestamp']}.   Next validation, {time_between} seconds later with score {next_validation['validation_score_avg']}",
                    report_file)
                found_val = True
        if not found_val:
            # print(f"No calibration after validation  score {validation['validation_score_avg']}")
            _report_to_file(
                f"No calibration after validation {num + 1}/{len(gaze._metadata['validations'])} at {bad_val_timestamp} with validation score {validation['validation_score_avg']}",
                report_file)


def check_metadata(metadata: dict[str, Any], report: ReportFunction) -> None:
    """
    Check the metadata of the gaze data and write a report to file.
    :param metadata: Metadata report.
    :param report: Function to write the report to file.
    :return:
    """
    date = f"{metadata['time']};     {metadata['day']}.{metadata['month']}.{metadata['year']}"
    report(
        "Date", date, None
    )

    num_calibrations = len(metadata["calibrations"])
    report(
        "Number of calibrations", num_calibrations, config.ACCEPTABLE_NUM_CALIBRATIONS
    )

    validation_scores_avg = [
        float(validation["validation_score_avg"])
        for validation in metadata["validations"]
    ]
    num_validations = len(metadata["validations"])
    report(
        "Number of validations", num_validations, config.ACCEPTABLE_NUM_CALIBRATIONS
    )
    report(
        "AVG validation scores",
        validation_scores_avg,
        config.ACCEPTABLE_AVG_VALIDATION_SCORES,
    )
    validation_scores_max = [
        float(validation["validation_score_max"])
        for validation in metadata["validations"]
    ]
    report(
        "MAX validation scores",
        validation_scores_max,
        config.TRACKED_EYE,
    )
    validation_errors = [
        validation["error"].removesuffix(" ERROR")
        for validation in metadata["validations"]
    ]
    report("Validation errors", validation_errors, config.ACCEPTABLE_VALIDATION_ERRORS)

    tracked_eye = metadata["tracked_eye"]
    report("tracked_eye",
           tracked_eye,
           config.TRACKED_EYE
           )

    validation_eye = [
        (validation["tracked_eye"][0])
        for validation in metadata["validations"]
    ]
    report(
        "Validation tracked Eyes",
        validation_eye,
        tracked_eye,
    )
    data_loss_ratio = metadata["data_loss_ratio"]
    report(
        "Data loss ratio",
        data_loss_ratio,
        config.ACCEPTABLE_DATA_LOSS_RATIOS,
        percentage=True,
    )
    data_loss_ratio_blinks = metadata["data_loss_ratio_blinks"]
    report(
        "Data loss ratio due to blinks",
        data_loss_ratio_blinks,
        config.ACCEPTABLE_DATA_LOSS_RATIOS,
        percentage=True,
    )
    total_recording_duration = metadata["total_recording_duration_ms"] / 60000
    report(
        "Total recording duration",
        total_recording_duration,
        config.ACCEPTABLE_RECORDING_DURATIONS,
    )
    sampling_rate = metadata["sampling_rate"]
    report("Sampling rate",
           sampling_rate,
           config.EXPECTED_SAMPLING_RATE_HZ,
           )


def analyse_eyelink_asc(asc_file: str,
                        session: str,
                        initial_ts: int | None,
                        lab: str,
                        # completed_stimuli: str
                        stimuli_trial_mapping: dict[str, str]):
    start_ts = []
    stop_ts = []
    start_msg = []
    stop_msg = []
    duration_ms = []
    duration_str = []
    trials = []
    pages = []
    status = []
    stimulus_name = []

    output_dir = Path("C://Users/saphi/PycharmProjects/multipleye-preprocessing/preprocessing") / 'reading_times'
    output_dir.mkdir(exist_ok=True)

    # stimuli_trial_mapping = {k: v for k, v in stimuli_trial_mapping.items()}

    with open(asc_file, 'r', encoding='utf8') as f:

        start_regex = re.compile(
            r'MSG\s+(?P<timestamp>\d+)\s+(?P<type>start_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)')
        stop_regex = re.compile(
            r'MSG\s+(?P<timestamp>\d+)\s+(?P<type>stop_recording)_(?P<trial>(PRACTICE_)?trial_\d\d?)_(?P<page>.*)')

        for l in f.readlines():
            if match := start_regex.match(l):
                start_ts.append(match.groupdict()['timestamp'])
                start_msg.append(match.groupdict()['type'])
                trials.append(match.groupdict()['trial'])

                if match.groupdict()['trial'] in stimuli_trial_mapping:
                    stimulus_name.append(stimuli_trial_mapping[match.groupdict()['trial']])

                pages.append(match.groupdict()['page'])
                status.append('reading time')
            elif match := stop_regex.match(l):
                stop_ts.append(match.groupdict()['timestamp'])
                stop_msg.append(match.groupdict()['type'])

    total_reading_duration_ms = 0
    for start, stop in zip(start_ts, stop_ts):
        time_ms = int(stop) - int(start)
        time_str = convert_to_time_str(time_ms)
        duration_ms.append(time_ms)
        duration_str.append(time_str)
        total_reading_duration_ms += time_ms

    print('Total reading duration:', convert_to_time_str(total_reading_duration_ms))

    # calcualte duration between pages
    temp_stop_ts = stop_ts.copy()
    temp_stop_ts.insert(0, initial_ts)
    temp_stop_ts = temp_stop_ts[:-1]

    total_set_up_time_ms = 0
    for stop, start, page, trial in zip(temp_stop_ts, start_ts, pages, trials):
        time_ms = int(start) - int(stop)
        time_str = convert_to_time_str(time_ms)
        duration_ms.append(time_ms)
        duration_str.append(time_str)
        start_msg.append('time inbetween')
        stop_msg.append('time inbetween')
        start_ts.append(stop)
        stop_ts.append(start)
        trials.append(trial)
        total_set_up_time_ms += time_ms

        if trial in stimuli_trial_mapping:
            stimulus_name.append(stimuli_trial_mapping[trial])

        pages.append(page)
        status.append('time before pages and breaks')

    print('Total set up and break time:', convert_to_time_str(total_set_up_time_ms))

    df = pd.DataFrame({
        'start_ts': start_ts,
        'stop_ts': stop_ts,
        'trial': trials,
        'stimulus': stimulus_name,
        'page': pages,
        'type': status,
        'duration_ms': duration_ms,
        'duration-hh:mm:ss': duration_str
    })

    df.to_csv(output_dir / f'times_per_page_pilot_{session}.tsv', sep='\t', index=False, )

    sum_df = df[['stimulus', 'trial', 'type', 'duration_ms']].dropna()
    sum_df['duration_ms'] = sum_df['duration_ms'].astype(float)
    sum_df = sum_df.groupby(by=['stimulus', 'trial', 'type']).sum().reset_index()
    duration = sum_df['duration_ms'].apply(lambda x: convert_to_time_str(x))
    sum_df['duration-hh:mm:ss'] = duration
    sum_df.to_csv(output_dir / f'times_per_page_pilot_{session}.tsv', index=False, sep='\t')

    print('Total exp time: ', convert_to_time_str(total_reading_duration_ms + total_set_up_time_ms))
    print('\n')

    # write total times to csv
    total_times = pd.DataFrame({
        'pilot': session,
        'lab': lab,
        'language': 'en',
        'total_trials': [len(sum_df) / 2],
        'total_pages': [len(df) / 2],
        'total_reading_time': [convert_to_time_str(total_reading_duration_ms)],
        'total_non-reading_time': [convert_to_time_str(total_set_up_time_ms)],
        'total_exp_time': [convert_to_time_str(total_reading_duration_ms + total_set_up_time_ms)]
    })
    if os.path.exists(output_dir / f'total_times.tsv'):
        temp_total_times = pd.read_csv(output_dir / 'total_times.tsv', sep='\t')
        total_times = pd.concat([temp_total_times, total_times], ignore_index=True)

    total_times.to_csv(output_dir / 'total_times.tsv', sep='\t', index=False)


#    total_times.to_excel(output_dir / 'total_times.xlsx', index=False)
#   sum_df.to_excel(output_dir / f'times_per_trial_pilot_{session}.xlsx', index=False)
#  df.to_excel(output_dir / f'times_per_page_pilot_{session}.xlsx', index=False)


def convert_to_time_str(duration_ms: float) -> str:
    seconds = int(duration_ms / 1000) % 60
    minutes = int(duration_ms / (1000 * 60)) % 60
    hours = int(duration_ms / (1000 * 60 * 60)) % 24

    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


if __name__ == '__main__':
    analyse_eyelink_asc(
        Path(
            "C:\\Users\saphi\PycharmProjects\multipleye-preprocessing\data\MultiplEYE_ET_EE_Tartu_1_2025\eye-tracking-sessions\core_dataset\\006_ET_EE_1_ET1\\006etee1.asc"),
        session="006",
        lab='et',
        initial_ts=None,
        stimuli_trial_mapping={
            'PRACTICE_trial_1': 'Enc_WikiMoon',
            'PRACTICE_trial_2': 'Lit_NorthWind',
            'trial_1': 'Lit_Solaris',
            'trial_2': 'Lit_MagicMountain',
            'trial_3': 'Arg_PISACowsMilk',
            'trial_4': 'Lit_BrokenApril',
            'trial_5': 'PopSci_Caveman',
            'trial_6': 'Arg_PISARapaNui',
            'trial_7': 'Ins_HumanRights',
            'trial_8': 'PopSci_MultiplEYE',
            'trial_9': 'Lit_Alchemist',
            'trial_10': 'Ins_LearningMobility',
        }
    )
