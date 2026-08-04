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
    rm_all_trials = []

    for (trial_idx, stim_name, page_idx), df in only_fix.group_by(group_columns):
        words_only = all_tokens_from_aois(df, trial=trial_idx)
        rm = compute_reading_measures(
            fixations=df,
            aois=words_only,
            word_index_column=settings.WORD_IDX_COL,
            word_column="word",
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
