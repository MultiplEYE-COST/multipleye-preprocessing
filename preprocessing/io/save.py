"""Functions for saving data."""

import json
from pathlib import Path

import polars as pl

import pymovements as pm


def save_raw_data(directory: Path, session: str, data: pm.Gaze) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    new_data = data.clone()

    try:
        new_data.unnest()
    except Warning:
        pass

    trials = new_data.split(by="trial", as_dict=False)

    for trial in trials:
        df = trial.frame
        trial = df["trial"][0]
        stimulus = df["stimulus"][0]
        name = f"{session}_{trial}_{stimulus}_raw_data.csv"
        df = df["time", "pixel_x", "pixel_y", "pupil", "page"]
        df.write_csv(directory / name)


def save_events_data(
    event_type: str,
    directory: Path,
    session: str,
    split_column: str,
    name_columns: list[str],
    file_columns: list[str],
    data: pm.Gaze,
) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    data_copy = data.clone()
    data_copy.events.unnest()

    events = data_copy.events.frame.filter(pl.col("name") == event_type)

    for group in events.partition_by(split_column):
        name = f"{session}"
        for col in name_columns:
            if col not in group.columns:
                raise ValueError(f"Column {col} not found in events data.")
            name += f"_{group[col][0]}"

        name += f"_{event_type}.csv"

        df = group.select(file_columns)
        df.write_csv(directory / name)


def save_scanpaths(directory: Path, session: str, data: pm.Gaze) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    new_data = data.clone()

    try:
        new_data.unnest()
        new_data.events.unnest()
    except Warning:
        # if the columns are already unnested there is a Warning (which interrupts)
        pass

    trials = new_data.events.split(by="trial", as_dict=False)

    for trial in trials:
        df = trial.frame
        # drop all rows where there has been no aoi mapped
        # TODO: what to do about fixations were no aoi is mapped?
        df = df.filter(pl.col("char_idx").is_not_null())
        if df.is_empty():
            continue
        trial = df["trial"][0]
        stimulus = df["stimulus"][0]
        name = f"{session}_{trial}_{stimulus}_scanpath.csv"

        df = df[
            "onset",
            "duration",
            "name",
            "location_x",
            "location_y",
            "char_idx",
            "char",
            "top_left_x",
            "top_left_y",
            "width",
            "height",
            "char_idx_in_line",
            "line_idx",
            "page",
            "word_idx",
            "word_idx_in_line",
            "word",
        ]
        df.write_csv(directory / name)


def save_session_metadata(gaze: pm.Gaze, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)

    metadata = gaze._metadata
    metadata["datetime"] = str(metadata["datetime"])

    # remove validations and calibrations because they are already saved in separate files
    metadata.pop("calibrations", None)
    metadata.pop("validations", None)

    with open(directory / "gaze_metadata.json", "w", encoding="utf8") as f:
        json.dump(metadata, f)

    gaze.save(directory, save_events=False, save_samples=False)

    # both are dfs
    validations = gaze.validations
    calibrations = gaze.calibrations

    validations.write_csv(directory / "validations.tsv", separator="\t")
    calibrations.write_csv(directory / "calibrations.tsv", separator="\t")
