import pymovements as pm
import polars as pl
from pymovements.measure.reading.processing import compute_reading_measures

from preprocessing.data_collection.stimulus import Stimulus
from preprocessing.metrics.reading.words import (
    all_tokens_from_aois,
)
from preprocessing import settings


def calculate_reading_measures(gaze: pm.Gaze, stimuli: list[Stimulus]) -> pl.DataFrame:
    group_columns = [settings.TRIAL_COL, settings.STIMULUS_COL, settings.PAGE_COL]

    only_fix = (
        gaze.events.frame.filter(
            (pl.col("name") == settings.FIXATION)
            & (pl.col(settings.WORD_IDX_COL).is_not_null())
        )
        .with_row_count("fixation_id")
        .sort(group_columns + ["onset"])
    )

    words_only_all_trials = []
    for stim in stimuli:
            aois = stim.text_stimulus.aois
            words_only = all_tokens_from_aois(aois, trial=stim.trial_id)
            words_only = words_only.with_columns(pl.lit(stim.name).alias("stimulus"))
            words_only_all_trials.append(words_only)

    words_df = pl.concat(words_only_all_trials)

    rm_all_trials = []

    for (trial_idx, stim_name, page_idx), fix_df in only_fix.group_by(group_columns):
        page_words = words_df.filter((pl.col(settings.TRIAL_COL) == trial_idx) & (pl.col(settings.STIMULUS_COL) == stim_name) & (pl.col(settings.PAGE_COL) == page_idx))
        rm = compute_reading_measures(
            fixations=fix_df,
            aois=page_words,
            word_index_column=settings.WORD_IDX_COL,
            #to be replaced when words change to unit of analysis
            word_column="words",
        )
        rm = rm.with_columns(
            pl.lit(trial_idx).alias(settings.TRIAL_COL),
            pl.lit(page_idx).alias(settings.PAGE_COL),
            pl.lit(stim_name).alias(settings.STIMULUS_COL),
        )
        rm_all_trials.append(rm)

    rm_df = pl.concat(rm_all_trials)
    #rename word index to original column name
    rm_df = rm_df.rename({"word_index": settings.WORD_IDX_COL})

    #adjust reading measures to original format of preprocessing pipeline
    rm_df = rm_df.with_columns((1-pl.col("Fix")).alias("skipped"))
    
    return rm_df.drop("Fix")
