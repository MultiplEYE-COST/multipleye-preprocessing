import preprocessing.events.drift_algorithms as da
import numpy as np
import polars as pl
import pymovements as pm

from ..config import settings


def _filter_gaze_events(
    events: pl.DataFrame,
    stimulus_name: str,
    page_name: str,
    event_type: str = "fixation",
) -> pl.DataFrame:
    """Filters the gaze events for a specific stimulus, page and event type (e.g. fixation, saccade, etc.)

    Parameters:
        events (pl.DataFrame): The gaze events to filter
        stimulus_name (str): The name of the stimulus to filter for
        page_name (str): The name of the page to filter for
        event_type (str): The type of event to filter for (default is "fixation")

    Returns:
        pl.DataFrame: The filtered gaze events
    """
    return events.frame.filter(
        (pl.col("page") == f"{page_name}")
        & (pl.col("stimulus") == f"{stimulus_name}")
        & (pl.col("name") == f"{event_type}")
    )


def _filter_aois(stimulus, page_name) -> pl.DataFrame:
    """Filters the AOIs for a specific stimulus and page name

    Parameters:
        stimulus: The stimulus to filter the AOIs for
        page_name: The name of the page to filter for

    Returns:
        pl.DataFrame: The filtered AOIs
    """

    return stimulus.text_stimulus.aois.filter((pl.col("page") == f"{page_name}"))


def _get_lines_of_text_form_aois(aois: pl.DataFrame) -> list:
    """Calculates the line positions of the text based on the AOIs. This is necessary for some of the drift correction algorithms to calculate the line positions.

    Parameters:
        aois: The AOIs to calculate the line positions from

    Returns:
        list: The line positions of the text
    """

    return (
        aois.filter(pl.col("line_idx").is_not_null())
        .group_by("line_idx")
        .agg(
            (pl.col("top_left_y") + pl.col("height") / 2)
            .mean()
            .alias("line_center")
        )
        .sort("line_idx")["line_center"]
        .to_list()
    )


def create_corrected_fixations_locations(
    events: pl.DataFrame, aois: pl.DataFrame, algorithm: str = "chain"
):
    """Corrects the fixations based on the specified algorithm and the AOIs.
    The AOIs are necessary to calculate the line positions.

    Parameters:
        events: The gaze events to correct
        aois: The AOIs to use for the correction
        algorithm: The algorithm to use for the correction (default is "chain")
            algorithms available: attach, cluster, compare, merge, regress, segment, split, stretch, warp, slice
            some have additional parameters, e.g. attach has a parameter "threshold" which defines the
            maximum distance to the line for a fixation to be attached to it, default is 50 pixels

    Returns:
        list: The corrected fixation locations
    """

    fixationXY = events.filter(pl.col("name") == "fixation").select(pl.col("location"))
    fixationXY = fixationXY["location"].to_list()
    lines = _get_lines_of_text_form_aois(aois)
    func = getattr(da, algorithm)
    return func(np.array(fixationXY), lines)


def _add_corrected_fixations_to_events(
    original_events: pl.DataFrame,
    corrected_fixations: list,
    algorithm: str,
    events_destination: pl.DataFrame,
) -> pl.DataFrame:
    """Adds the corrected fixations to the gaze events dataframe
    with the appropriate event type name (e.g. fixation_corrected_attach) and returns the updated dataframe.

    Parameters:
        original_events: The original gaze events dataframe with fixations that where corrected
            (used to get the other information of the events, e.g. start and end time, page, stimulus, etc.)
        corrected_fixations: The list of corrected fixation locations
        algorithm: The algorithm that was used to correct the fixations
        events_destination: The destination dataframe to which the corrected fixations should be added

    Returns:
        pl.DataFrame: The updated gaze events dataframe with the corrected fixations added
    """

    for i, event in enumerate(original_events.iter_rows(named=True)):
        new_event = event.copy()
        new_event["location"] = corrected_fixations[i]
        new_event["name"] = f"fixation_corrected_{algorithm}"
        events_destination = events_destination.vstack(pl.DataFrame([new_event]))
    return events_destination


def add_corrected_fixations_for_page(
    stimulus, page, gaze_events: pl.DataFrame, algorithm: str = "chain"
) -> pl.DataFrame:
    """Corrects the fixations based on the specified algorithm and the AOIs and adds them to the events dataframe."""

    stimulus_name = f"{stimulus.name}_{stimulus.id}"
    page_name = f"page_{page.number}"
    events = _filter_gaze_events(gaze_events, stimulus_name, page_name)

    if (
        events.select(
            pl.col("name").str.contains(f"fixation_corrected_{algorithm}").sum()
        ).item()
        > 0
    ):
        raise ValueError(
            f"Fixation corrections with algorithm {algorithm} already exist for {stimulus_name}/{page_name} in the gaze events dataframe, cannot add corrected fixations again without removing the previous ones first. Remove them with the function remove_previous_fixation_corrections(gaze_events, algorithm)"
        )

    aois = _filter_aois(stimulus, page_name)
    corrected_fixations = create_corrected_fixations_locations(events, aois, algorithm)
    gaze_events.frame = _add_corrected_fixations_to_events(
        events, corrected_fixations, algorithm, gaze_events.frame
    )


def add_corrected_fixations(
    sess, gaze_events: pl.DataFrame, algorithm: str = "chain", verbose=0
) -> pl.DataFrame:
    """Adds the corrected fixations for all stimuli and pages in the session to the gaze events dataframe."""

    if (
        gaze_events.frame.select(
            pl.col("name").str.contains(f"fixation_corrected_{algorithm}").sum()
        ).item()
        > 0
    ):
        raise ValueError(
            f"Fixation corrections with algorithm {algorithm} already exist in the gaze events dataframe, cannot add corrected fixations again without removing the previous ones first. Remove them with the function remove_previous_fixation_corrections(gaze_events, algorithm)"
        )

    for stimulus in sess.stimuli:
        if verbose == 1:
            print(stimulus.name)
        for page in stimulus.pages:
            if verbose == 1:
                print(page.number, end=",")
            add_corrected_fixations_for_page(stimulus, page, gaze_events, algorithm)
        if verbose == 1:
            print()


def remove_previous_fixation_corrections(
    gaze_events, algorithm: str = "chain"
) -> pl.DataFrame:
    gaze_events.frame = gaze_events.frame.filter(
        ~pl.col("name").str.contains(f"fixation_corrected_{algorithm}")
    )
    return gaze_events


def correct_fixations(
    gaze: pm.Gaze,
    sess,
    algorithm: str = "chain",
) -> None:
    """Correct fixation locations for vertical line drift.

    Runs the specified drift-correction algorithm (default ``"chain"``) on the
    detected fixations in ``gaze.events`` and replaces the original
    ``fixation`` events with the corrected ones. This ensures that downstream
    AOI mapping and reading measures operate on the corrected locations.

    Parameters
    ----------
    gaze : pm.Gaze
        Gaze object with detected fixations in ``gaze.events``.
    sess : Session
        Session object providing ``stimuli`` and page AOI information.
    algorithm : str, optional
        Drift-correction algorithm to use. Default is ``"chain"``.
    """
    if gaze.events is None or gaze.events.frame is None or gaze.events.frame.is_empty():
        return

    remove_previous_fixation_corrections(gaze.events, algorithm)
    add_corrected_fixations(sess, gaze.events, algorithm, verbose=1)

    corrected_name = f"fixation_corrected_{algorithm}"
    corrected = (
        gaze.events.frame.filter(pl.col("name") == corrected_name)
        .with_columns(pl.lit(settings.FIXATION).alias("name"))
    )

    if corrected.is_empty():
        return

    other_events = gaze.events.frame.filter(
        (pl.col("name") != settings.FIXATION) & (pl.col("name") != corrected_name)
    )
    gaze.events.frame = pl.concat([other_events, corrected], how="vertical")
