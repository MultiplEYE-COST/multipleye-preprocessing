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

ReportFunction = Callable[[str, Any, Any], None]


def report_to_file_metadata(
        name: str,
        values: Any,
        acceptable_values: Any,
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

    if not overall_answers == 0:
        _report_to_file(
            f"Overall correct answers: {overall_correct_answers} out of {overall_answers} answers {overall_correct_answers / overall_answers:.2f}",
            report_file)
    else:
        _report_to_file(
            f"Overall correct answers: {overall_correct_answers} out of {overall_answers} answers",
            report_file)


def check_validation_requirements(metadata: dict[str, Any], report_file, stimulus_times):

    # sort validations and calibrations by timestamp, merge into one list
    vals = sorted(metadata["validations"], key=lambda x: float(x["timestamp"]))
    cals = sorted(metadata["calibrations"], key=lambda x: float(x["timestamp"]))

    merged = sorted(vals + cals + stimulus_times, key=lambda x: float(x["timestamp"]))
    bad_tstamp = None
    bad_val = False
    in_stimulus = False
    val_count = 0
    cal_count = 0
    for m in merged:
        if "validation_score_avg" in m:
            val_count += 1
            if bad_val:
                _report_to_file(f"⚠️ No calibration at {m['timestamp']} after BAD validation at timestamp {bad_tstamp}", report_file)
                bad_val = False
            score = float(m["validation_score_avg"])
            if score < 0.305:
                _report_to_file(f"✅ Good validation at {m['timestamp']} with score {m['validation_score_avg']}", report_file)
                bad_val = False
            elif 0.45 > score >= 0.305:
                _report_to_file(f"⚠️ Moderate validation at {m['timestamp']} with score {m['validation_score_avg']}", report_file)
                bad_val = True
                bad_tstamp = int(m["timestamp"])
            elif score >= 0.45:
                _report_to_file(f"❌ BAD Validation at {m['timestamp']} with score {m['validation_score_avg']}", report_file)
                bad_val = True
                bad_tstamp = int(m["timestamp"])
            if in_stimulus:
                _report_to_file(f"⚠️ Validation during stimulus at {m['timestamp']} with score {m['validation_score_avg']}", report_file)

        elif 'message' in m:
            if 'start' in  m['message']:
                in_stimulus = True
                _report_to_file(f'ℹ️ {m["message"]} at {m["timestamp"]}', report_file)
                if bad_val:
                    _report_to_file(f"❌ {m['message']} directly after bad/moderate validation!", report_file)

            if 'end' in m['message']:
                in_stimulus = False
                _report_to_file(f'ℹ️ {m["message"]} at {m["timestamp"]}', report_file)

        else:
            cal_count += 1
            if bad_val:
                bad_val = False
                time_between = round((float(m["timestamp"]) - bad_tstamp) / 1000, 3)
                _report_to_file(f"✅ Calibration at {m['timestamp']} {time_between} seconds after bad/moderate validation", report_file)
            if in_stimulus:
                _report_to_file(f"⚠️ Calibration during stimulus at {m['timestamp']}", report_file)


def check_metadata(metadata: dict[str, Any], report: ReportFunction) -> None:
    """
    Check the metadata of the gaze data and write a report to file.
    :param metadata: Metadata report.
    :param report: Function to write the report to file.
    :return:
    """
    date = f"{metadata['time']};     {metadata['day']}.{metadata['month']}.{metadata['year']}"
    report("Date", date, None)

    num_calibrations = len(metadata["calibrations"])
    report("Number of calibrations", num_calibrations, config.ACCEPTABLE_NUM_CALIBRATIONS)

    validation_scores_avg = [
        float(validation["validation_score_avg"])
        for validation in metadata["validations"]
    ]
    num_validations = len(metadata["validations"])
    report("Number of validations", num_validations, config.ACCEPTABLE_NUM_CALIBRATIONS)
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
