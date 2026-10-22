"""Word-level reading measures via the pymovements reading-measure engine."""

import polars as pl
import pymovements as pm

from preprocessing.config import settings
from preprocessing.data_collection.stimulus import Stimulus


def _combined_aois(stimuli: list[Stimulus]) -> pl.DataFrame:
    """Stack the AOIs of all stimuli and tag them with their trial id."""
    all_aois = pl.DataFrame()
    for stimulus in stimuli:
        aoi = stimulus.text_stimulus.aois.with_columns(
            pl.lit(stimulus.trial_id).cast(pl.Utf8).alias(settings.TRIAL_COL)
        )
        all_aois = all_aois.vstack(aoi)
    return all_aois


def calculate_reading_measures(gaze: pm.Gaze, stimuli: list[Stimulus]) -> pl.DataFrame:
    """Compute word-level reading measures from mapped fixations.

    Uses the declarative pymovements reading-measure engine
    (:func:`pymovements.measure.reading.compute_reading_measures`), grouping by
    trial and page.

    Parameters
    ----------
    gaze : pm.Gaze
        Gaze object whose events are already mapped to AOIs.
    stimuli : list[Stimulus]
        Stimuli of the session, providing the AOI tables.

    Returns
    -------
    pl.DataFrame
        One row per word with the reading measures, the ``trial``/``page``
        group columns, ``word_idx``/``word`` and a ``stimulus`` column used for
        saving per-trial files.
    """
    measures = pm.measure.reading.compute_reading_measures(
        gaze.events.frame,
        _combined_aois(stimuli),
        group_columns=[settings.TRIAL_COL, settings.PAGE_COL],
    )
    measures = measures.rename({"word_index": settings.WORD_IDX_COL})

    trial_to_stimulus = {
        stimulus.trial_id: stimulus.full_identifier for stimulus in stimuli
    }
    return measures.with_columns(
        pl.col(settings.TRIAL_COL)
        .replace_strict(trial_to_stimulus, default=None, return_dtype=pl.Utf8)
        .alias(settings.STIMULUS_COL)
    )
