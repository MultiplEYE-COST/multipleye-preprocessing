import polars as pl
import pymovements as pm

from preprocessing.data_collection.stimulus import Stimulus
from preprocessing.metrics.reading.fixations import annotate_fixations
from preprocessing.metrics.reading.reading_measures import build_word_level_table
from preprocessing.metrics.reading.words import (
    all_tokens_from_aois,
    mark_skipped_tokens,
)


def calculate_reading_measures(gaze: pm.Gaze, stimuli: list[Stimulus]) -> pl.DataFrame:
    # create a fixation table
    fixation_table = annotate_fixations(gaze.events.frame)

    words_only_all_trials = []

    for stim in stimuli:
        aois = stim.text_stimulus.aois
        words_only = all_tokens_from_aois(aois, trial=stim.trial_id)
        words_only = words_only.with_columns(
            pl.lit(stim.full_identifier).alias("stimulus")
        )
        words_only_all_trials.append(words_only)

    words_df = pl.concat(words_only_all_trials)

    #  annotate skipped words based on fixation table and all tokens
    words_with_skip = mark_skipped_tokens(words_df, fixation_table)

    # calculate word-level reading measures
    word_level_table = build_word_level_table(
        words=words_with_skip,
        fix=fixation_table,
    )

    return word_level_table
