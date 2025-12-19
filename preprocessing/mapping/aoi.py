"""Mapping of fixations to AOIs."""
import polars as pl

import pymovements as pm
from ..data_collection.stimulus import Stimulus


def map_fixations_to_aois(
        gaze: pm.Gaze,
        stimuli: list[Stimulus],
) -> None:
    """
    Maps gaze events to areas of interest (AOIs) for each stimulus.

    This function processes a list of stimuli, extracts AOIs from each stimulus,
    and assigns the corresponding trial identifier to them.
    It then consolidates all AOIs into a unified data structure and maps gaze events to these AOIs.

    Parameters
    ----------
    gaze : pm.Gaze
        The gaze data containing events to be mapped to AOIs.
    stimuli : list of Stimulus
        A list of Stimulus objects, each containing ``text_stimulus`` data with defined
        AOIs and trial IDs.

    Returns
    -------
    None
        The function performs mapping in place and does not return any value.
    """
    all_aois = pl.DataFrame()
    for stimulus in stimuli:
        aoi = stimulus.text_stimulus.aois
        trial = stimulus.trial_id
        aoi = aoi.with_columns(pl.lit(trial).alias("trial"))
        all_aois = all_aois.vstack(aoi)

    all_aois = pm.stimulus.TextStimulus(
        all_aois,
        aoi_column="char_idx",
        start_x_column="top_left_x",
        start_y_column="top_left_y",
        width_column="width",
        height_column="height",
        page_column="page",
        trial_column="trial",
    )

    gaze.events.map_to_aois(all_aois, verbose=False)
