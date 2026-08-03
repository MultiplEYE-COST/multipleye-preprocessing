import pymovements as pm
import polars as pl
from pymovements.measure.reading.processing import compute_reading_measures

from preprocessing.data_collection.stimulus import Stimulus
from preprocessing.metrics.reading.fixations import annotate_fixations
from preprocessing.metrics.reading.reading_measures import build_word_level_table
from preprocessing.metrics.reading.words import (
    mark_skipped_tokens,
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

    for stim in stimuli:
        aois = stim.text_stimulus.aois
        words_only = all_tokens_from_aois(aois, trial=stim.trial_id)
        words_only = words_only.with_columns(pl.lit(stim.name).alias(settings.STIMULUS_COL))
        trial_idx = stim.trial_id

        for page in stim.pages:
            page_idx = f"page_{page.number}"
            page_words = words_only.filter(pl.col(settings.PAGE_COL)==page_idx)
            page_fix = only_fix.filter((pl.col(settings.TRIAL_COL)==trial_idx) & (pl.col(settings.PAGE_COL)==page_idx))
            rm = compute_reading_measures(
                fixations=page_fix,
                aois = page_words,
                word_index_column= settings.WORD_IDX_COL,
                word_column = "word"
            )
            rm = rm.with_columns(pl.lit(trial_idx).alias(settings.TRIAL_COL), pl.lit(page_idx).alias(settings.PAGE_COL), pl.lit(stim.name).alias(settings.STIMULUS_COL))
            rm_all_trials.append(rm)

    rm_df = pl.concat(rm_all_trials)
    return rm_df.rename({"word_index":settings.WORD_IDX_COL})