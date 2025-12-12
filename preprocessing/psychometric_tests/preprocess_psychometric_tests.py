"""Utilities to preprocess psychometric test outputs into simple summary metrics.

This module provides small helpers to load raw CSV exports for several common
psychometric tasks and compute concise summaries such as mean reaction time and
accuracy, optionally grouped by condition where applicable.

Covered tasks:
- Lewandowsky WMC battery
- Rapid Automatised Naming (RAN)
- Stroop
- Flanker
- PLAB (Pimsleur Language Aptitude Battery)
- WikiVocab (LexTALE)

Background and task descriptions:
https://github.com/MultiplEYE-COST/MultiplEYE-psychometric-tests#readme
"""

import warnings
from math import nan
from pathlib import Path

from pandas import read_csv, DataFrame
import pandas as pd

from preprocessing.config import PSYCHOMETRIC_TESTS_DIR, PSYM_LWMC_DIR, PSYM_RAN_DIR, \
    PSYM_STROOP_FLANKER_DIR, PSYM_WIKIVOCAB_DIR, PSYM_PLAB_DIR


def preprocess_all_participants(
        test_session_folder: Path = PSYCHOMETRIC_TESTS_DIR) -> Path:
    """Preprocess all participants and write two types of outputs:

    1) Overview CSV (one row per participant) saved directly under the
       psychometric-tests-sessions folder. The filename is descriptive and
       includes the study/session tag (e.g. "SQ_CH_1_PT2"). The overview
       contains only the requested summary metrics:
       - LWMC: scores only (no times)
       - Stroop & Flanker: AccuracyEffect and TREffect only
       - WikiVocab: rt_mean, accuracy, incorrect_correct_score
       - RAN: Reaction time for two trials
       - PLAB: RT mean and accuracy

    2) Per-participant detailed CSV placed in each participant folder with all
       available detailed metrics in a readable, wide format (namespaced
       columns). For example, grouped RT/accuracy for Stroop/Flanker are stored
       as columns like ``Stroop_congruent_rt_mean``.

    Notes:
    - All computations are performed once per participant and then split into
      overview vs. detailed outputs.
    - Returns the path to the written overview CSV.
    """
    # Collect participant folders
    participant_folders = test_session_folder.iterdir()
    participant_folders = [p for p in participant_folders if _is_valid_folder(p)]
    participant_folders = sorted(participant_folders, key=lambda p: p.name)

    overview_rows: list[dict] = []

    def _pid_from_folder(folder: Path) -> str:
        return folder.stem[:3]

    for participant in participant_folders:
        pid = _pid_from_folder(participant)
        # Initialise overview row with participant and per-test calculated flags (0/1)
        overview_row: dict = {
            'participant_id': pid,
            'LWMC_Calculated': 0,
            'RAN_Calculated': 0,
            'Stroop_Calculated': 0,
            'Flanker_Calculated': 0,
            'WikiVocab_Calculated': 0,
            'PLAB_Calculated': 0,
        }

        # Detailed row: single CSV per participant with namespaced, readable columns
        detailed_row: dict = {
            'participant_id': pid,
        }

        # LWMC
        lwmc_dir = participant / PSYM_LWMC_DIR
        if lwmc_dir.exists():
            try:
                res_lwmc = preprocess_lwmc(lwmc_dir)  # dict
                # detailed: all LWMC metrics
                detailed_row.update(res_lwmc)
                # overview: LWMC scores only
                for k in ['LWMC_MU_score', 'LWMC_OS_score', 'LWMC_SS_score',
                          'LWMC_SSTM_score', 'LWMC_Total_score_mean']:
                    if k in res_lwmc:
                        overview_row[k] = res_lwmc[k]
                overview_row['LWMC_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process LWMC test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # RAN
        ran_dir = participant / PSYM_RAN_DIR
        if ran_dir.exists():
            try:
                res_ran = preprocess_ran(ran_dir)
                # both detailed and overview get all RAN metrics
                detailed_row.update(res_ran)
                overview_row.update(res_ran)
                # Mark calculated on successful preprocessing regardless of emptiness
                overview_row['RAN_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process RAN test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # Stroop & Flanker
        sf_dir = participant / PSYM_STROOP_FLANKER_DIR
        if sf_dir.exists():
            try:
                res_stroop = preprocess_stroop(sf_dir)  # DataFrame
                stroop_effects = {
                    'StroopAccuracyEffect':
                        res_stroop['Stroop_incongruent_accuracy'] -
                        res_stroop['Stroop_congruent_accuracy'],
                    'StroopRTEffect':
                        res_stroop['Stroop_incongruent_rt_mean'] -
                        res_stroop['Stroop_congruent_rt_mean'],
                }
                # overview: only effects
                overview_row.update(stroop_effects)
                # detailed: effects + grouped metrics per condition
                detailed_row.update(stroop_effects)
                detailed_row.update(res_stroop)
                overview_row['Stroop_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Stroop test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
            try:
                res_flanker = preprocess_flanker(sf_dir)  # DataFrame
                flanker_effects = {
                    'FlankerAccuracyEffect':
                        res_flanker['Flanker_incongruent_accuracy'] -
                        res_flanker['Flanker_congruent_accuracy'],
                    'FlankerRTEffect':
                        res_flanker['Flanker_incongruent_rt_mean'] -
                        res_flanker['Flanker_congruent_rt_mean'],
                }
                # overview: only effects
                overview_row.update(flanker_effects)
                # detailed: effects + grouped metrics per condition
                detailed_row.update(flanker_effects)
                detailed_row.update(res_flanker)
                overview_row['Flanker_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Flanker test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
                overview_row['Flanker_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Flanker test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # WikiVocab (tuple[rt_mean, accuracy])
        wv_dir = participant / PSYM_WIKIVOCAB_DIR
        if wv_dir.exists():
            try:
                res_wv = preprocess_wikivocab(wv_dir)
                # detailed: all computed fields
                # detailed_row.update({f"WikiVocab_{k}": v for k, v in wv.items()})
                detailed_row.update(res_wv)
                # overview: only selected
                for key in ['WikiVocab_rt_mean', 'WikiVocab_accuracy',
                            'WikiVocab_incorrect_correct_score']:
                    overview_row[key] = res_wv[key]
                overview_row['WikiVocab_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process WikiVocab test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # PLAB (tuple[rt_mean, accuracy])
        plab_dir = participant / PSYM_PLAB_DIR
        if plab_dir.exists():
            try:
                res_plab = preprocess_plab(plab_dir)
                detailed_row.update(res_plab)
                overview_row['PLAB_rt_mean'] = res_plab['PLAB_rt_mean']
                overview_row['PLAB_accuracy'] = res_plab['PLAB_accuracy']
                overview_row['PLAB_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process PLAB test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # Write per-participant detailed CSV inside the participant folder
        try:
            detailed_path = participant / f"psychometric_details_{participant.stem}.csv"
            pd.DataFrame([detailed_row]).to_csv(detailed_path, index=False)
        except Exception as exc:
            warnings.warn(
                f"Failed to write detailed CSV for {participant.stem}: {exc}",
                category=UserWarning,
            )

        overview_rows.append(overview_row)

    # Write overview CSV (wide format) directly into psychometric-tests-sessions folder
    out_path = test_session_folder / f'psychometric_overview_{test_session_folder.parent.stem}.csv'
    df = pd.DataFrame(overview_rows)
    # Ensure columns order: participant_id, then flags, then the rest
    flag_cols = [
        'LWMC_Calculated',
        'RAN_Calculated',
        'Stroop_Calculated',
        'Flanker_Calculated',
        'WikiVocab_Calculated',
        'PLAB_Calculated',
    ]
    for col in flag_cols:
        if col not in df.columns:
            df[col] = 0
    remaining = [c for c in df.columns if c not in (['participant_id'] + flag_cols)]
    df = df[['participant_id'] + flag_cols + remaining]
    df.to_csv(out_path, index=False)

    print(f"Wrote overview: {out_path}")
    return out_path


def _is_valid_folder(folder: Path) -> bool:
    return folder.is_dir() and folder.stem[:3].isdigit() and folder.stem[3] == '_'


def preprocess_stroop(stroop_flanker_dir: Path):
    """Preprocess Stroop test CSVs and return RT and accuracy by stimulus type.

    Extract 'stim_type', 'stroop_key.rt' and 'stroop_key.corr', then compute
    reaction time and accuracy grouped by stimulus type.

    **Stroop**: The Stroop test is a test of cognitive control that measures the ability to inhibit
    automatic responses. The test consists of three parts:
    a color naming task, a word reading task, and a color-word naming task.

    Parameters
    ----------
    stroop_flanker_dir : Path
        Path to the folder containing the participants' stroop and flanker data.

    Returns
    -------
    dict
        A dictionary with keys 'Stroop_incongruent_rt_mean', 'Stroop_incongruent_accuracy',
        'Stroop_incongruent_num_items', 'Stroop_congruent_rt_mean', 'Stroop_congruent_accuracy',
        'Stroop_congruent_num_items', 'Stroop_neutral_rt_mean', 'Stroop_neutral_accuracy',
        and 'Stroop_neutral_num_items'.
    """
    df = _find_one_filetype_with_columns(
        stroop_flanker_dir, ['stim_type', 'stroop_key.rt', 'stroop_key.corr'],
        allow_nan=True
    )
    result_df = _reaction_time_accuracy(
        df,
        reaction_time_col='stroop_key.rt',
        correctness_col='stroop_key.corr',
        group_by_col='stim_type'
    )

    result_dict = {}
    for cond in ['incongruent', 'congruent', 'neutral']:
        for metric in ('rt_mean', 'accuracy', 'num_items'):
            result_dict[f"Stroop_{cond}_{metric}"] = float(result_df.loc[cond, metric])

    return result_dict


def preprocess_flanker(stroop_flanker_dir: Path):
    """Preprocess Flanker test CSVs and return RT and accuracy by stimulus type.

    Extract 'stim_type', 'flanker_key.rt' and 'flanker_key.corr', then compute
    reaction time and accuracy grouped by stimulus type.

    **Flanker**: The Flanker test is a test of cognitive control that measures the ability to
    inhibit irrelevant information.
    The test consists of a series of trials in which participants must respond to a central target
    while ignoring flanking distractors.

    Parameters
    ----------
    stroop_flanker_dir : Path
        Path to the folder containing the participants' stroop and flanker data.

    Returns
    -------
    dict
        A dictionary with keys 'Flanker_incongruent_rt_mean', 'Flanker_incongruent_accuracy',
        'Flanker_incongruent_num_items', 'Flanker_congruent_rt_mean', 'Flanker_congruent_accuracy',
        and 'Flanker_congruent_num_items'.
    """
    df = _find_one_filetype_with_columns(
        stroop_flanker_dir, ['stim_type', 'Flanker_key.rt', 'Flanker_key.corr'],
        allow_nan=True
    )
    result_df = _reaction_time_accuracy(
        df,
        reaction_time_col='Flanker_key.rt',
        correctness_col='Flanker_key.corr',
        group_by_col='stim_type'
    )

    result_dict = {}
    for cond in ['incongruent', 'congruent']:
        for metric in ('rt_mean', 'accuracy', 'num_items'):
            result_dict[f"Flanker_{cond}_{metric}"] = float(result_df.loc[cond, metric])

    return result_dict


def preprocess_lwmc(lwmc_dir: Path):
    """Preprocess Lewandowsky WMC battery and compute task scores.

    Tasks:

    - MU (Memory Update): proportion of items recalled correctly (per-trial mean, then mean over trials).
    - OS (Operation Span): mean of per-trial recall correctness (unweighted by list length).
    - SS (Sentence Span): mean of per-trial recall correctness (unweighted by list length).
    - SSTM (Spatial Short-Term Memory): overall score normalised by 240 from ``SSTM-<id>.dat``.

    Implementation notes:

    - MU/OS/SS data are taken from the CSV export (not the .dat files).
      We compute a trial index from ``base_text_intertrial.started`` and then, for each task,
      compute the mean of the per-trial mean correctness values. This avoids overweighting
      trials with more items.
    - SSTM continues to be read from the original ``.dat`` file.

    Attribution: Scoring concept adapted from Laura Stahlhut's Python implementation (2022)
    of the Lewandowsky WMC battery (wmc-analysis). Reference: Lewandowsky, S., et al. (2010).
    Behavior Research Methods, 42(2), 571–585.

    Returns
    -------
    dict
        Dictionary with keys: 'LWMC_MU_score', 'LWMC_MU_time', 'LWMC_OS_score', 'LWMC_OS_time',
        'LWMC_SS_score', 'LWMC_SS_time', 'LWMC_SSTM_score', and 'LWMC_Total_score_mean'.
    """

    # 1) Load the single WMC CSV that contains the relevant columns
    required_cols = [
        'is_practice',  # Filter out practice trials
        'base_text_intertrial.started',  # Marker to separate trials
        'mu_key_resp_recall.is_correct', 'mu_key_resp_recall.rt',  # MU columns
        'os_key_resp_recall.corr', 'os_key_resp_recall.rt',  # OS columns
        'ss_key_resp_recall.corr', 'ss_key_resp_recall.rt',  # SS columns
    ]
    df = _find_one_filetype_with_columns(lwmc_dir, required_cols, allow_nan=True)

    # Create a trial identifier using the inter-trial text onset markers
    # Each non-NaN in base_text_intertrial.started indicates a new trial boundary.
    df['trial_id'] = df['base_text_intertrial.started'].notna().cumsum()

    df = df[df['is_practice'] == False].copy()  # remove all practice trials
    if df.empty:
        raise ValueError("No non-practice trials found in WMC CSV")

    def _per_trial_mean_then_mean(correctness_col: str, time_col: str,
                                  label: str) -> float:
        if correctness_col not in df.columns:
            raise ValueError(f"Missing column '{correctness_col}' for {label}")
        # Select only rows with a value for the specific task's correctness column
        mask = df[correctness_col].notna()
        if not mask.any():
            raise ValueError(
                f"No valid {label} trials found (no non-NaN entries in {correctness_col})")
        # Use the in-frame 'trial_id' column to avoid index alignment issues
        sub = df.loc[mask, [correctness_col, time_col, 'trial_id']].copy()
        # Ensure correctness is numeric (0/1 or NaN)
        sub[correctness_col] = pd.to_numeric(sub[correctness_col], errors='coerce')
        # Compute mean correctness per trial_id, then mean of these per-trial means
        corr_per_trial = sub.groupby('trial_id', dropna=True)[correctness_col].mean()
        time_per_trial = sub.groupby('trial_id', dropna=True)[time_col].mean()
        if corr_per_trial.empty:
            raise ValueError(f"No valid {label} trials found after grouping")
        return float(corr_per_trial.mean()), float(time_per_trial.mean())

    # 2) Compute MU/OS/SS from CSV columns
    mu_score, mu_time = _per_trial_mean_then_mean('mu_key_resp_recall.is_correct',
                                                  'mu_key_resp_recall.rt', 'MU')
    os_score, os_time = _per_trial_mean_then_mean('os_key_resp_recall.corr',
                                                  'os_key_resp_recall.rt', 'OS')
    ss_score, ss_time = _per_trial_mean_then_mean('ss_key_resp_recall.corr',
                                                  'ss_key_resp_recall.rt', 'SS')

    # 3) SSTM from legacy .dat
    def _participant_id_from_dir(d: Path) -> str:
        stem = d.parent.stem
        if len(stem) < 3 or not stem[:3].isdigit():
            raise ValueError(f"Cannot infer participant id from folder name: {stem}")
        return str(int(stem[:3]))

    pid = _participant_id_from_dir(lwmc_dir)
    sstm_file = lwmc_dir / f"SSTM-{pid}.dat"
    if not sstm_file.exists() or not sstm_file.is_file():
        raise ValueError(f"Missing required WMC file: {sstm_file}")

    def _read_lines(p: Path) -> list[str]:
        try:
            with p.open('r', encoding='utf-8') as fh:
                return fh.readlines()
        except Exception as exc:
            raise ValueError(f"Failed to read WMC file {p}: {exc}") from exc

    sstm_lines = _read_lines(sstm_file)
    if len(sstm_lines) < 2:
        raise ValueError(f"Malformed SSTM file (too few lines): {sstm_file}")
    sstm_tokens = [t for t in sstm_lines[1].rstrip("\n").split(" ") if t != ""]
    if len(sstm_tokens) < 2:
        raise ValueError(f"Malformed SSTM line (too few tokens): {sstm_lines[1]}")
    try:
        sstm_raw = int(sstm_tokens[1])
    except ValueError as exc:
        raise ValueError(f"Invalid SSTM score token: {sstm_tokens[1]}") from exc
    sstm_score = sstm_raw / 240.0

    # 4) Total mean
    total = (mu_score + os_score + ss_score + sstm_score) / 4.0

    return {
        'LWMC_MU_score': mu_score,
        'LWMC_MU_time': mu_time,
        'LWMC_OS_score': os_score,
        'LWMC_OS_time': os_time,
        'LWMC_SS_score': ss_score,
        'LWMC_SS_time': ss_time,
        'LWMC_SSTM_score': sstm_score,
        'LWMC_Total_score_mean': total,
    }


def preprocess_ran(ran_dir: Path):
    """Preprocess RAN task output and return the reaction times for practice and experimental trials.

    Finds the only .csv in the folder and extracts the 'Trial' and 'Reading_Time' columns.
    The audio files and logs are kept untouched.

    **RAN task**:
    The Rapid Automatised Naming (RAN) task is a test of the speed and efficiency of naming digits.
    It is used to assess the speed of processing and
    the ability to quickly retrieve information from memory.

    Parameters
    ----------
    ran_dir : Path
        Path to the folder containing the participants' RAN data.

    Returns
    -------
    dict
        Dictionary with keys 'RAN_practice_rt' and 'RAN_experimental_rt' containing the
        reaction times.

    Raises
    ------
    ValueError
        If not exactly one .csv file is found in the directory.
    """
    df = _find_one_filetype_with_columns(ran_dir, ['Trial', 'Reading_Time'],
                                         allow_nan=False)

    # Extract practice and experimental trial reaction times
    practice_rt = df[df['Trial'] == 1]['Reading_Time']
    experimental_rt = df[df['Trial'] == 2]['Reading_Time']

    return {
        'RAN_practice_rt': float(practice_rt),
        'RAN_experimental_rt': float(experimental_rt)
    }


def preprocess_wikivocab(wv_dir: Path):
    """Preprocess WikiVocab task output and compute mean RT and accuracy.

    LexTALE generalisation:

    - Add num_pseudo_words / num_real_words
    - Incorrect minus correct (number of existing words correct/number of existing words in list) + (number of nonwords correct/nonwords in list)) / 2
    - Percentages correct pseudo / correct / overall

    Extract 'correct_answer', 'real_answer' and 'RT' columns, infer a 'correctness' column,
    and return the mean reaction time and accuracy.

    **WikiVocab**:
    The WikiVocab test is a test of vocabulary knowledge that is based on the Wikipedia corpus.
    It is designed to measure the breadth of an individual's vocabulary knowledge.
    For English, German, Dutch, Chinese, the LexTALE test is also available.

    Parameters
    ----------
    wv_dir : Path
        Path to the folder containing the participants' Wikivocab data.

    Returns
    -------
    dict
        Dictionary containing:

        - WikiVocab_rt_mean: Mean reaction time
        - WikiVocab_accuracy: Overall accuracy
        - WikiVocab_num_pseudo: Number of pseudo words
        - WikiVocab_num_real: Number of real words
        - WikiVocab_incorrect_correct_score: Balanced accuracy score (averaged % correct)
          https://www.lextale.com/scoring.html
        - WikiVocab_pseudo_correct: Fraction of correct pseudo words
        - WikiVocab_real_correct: Fraction of correct real words
        - WikiVocab_overall_correct: Overall fraction correct
    """
    df = _find_one_filetype_with_columns(
        wv_dir, ['correct_answer', 'real_answer', 'RT'], allow_nan=False
    )
    df['correctness'] = df['correct_answer'] == df['real_answer']

    # Calculate additional metrics
    num_pseudo = len(df[df['correct_answer'] == 0])
    num_real = len(df[df['correct_answer'] == 1])

    # Calculate correct fractions
    pseudo_correct = df[(df['correct_answer'] == 0) & (df['correctness'])].shape[
                         0] / num_pseudo if num_pseudo > 0 else float('nan')
    real_correct = df[(df['correct_answer'] == 1) & (df['correctness'])].shape[
                       0] / num_real if num_real > 0 else float('nan')
    overall_correct = df['correctness'].mean()

    # Calculate incorrect_correct score
    incorrect_correct = (real_correct + pseudo_correct) / 2

    rt_acc = _reaction_time_accuracy(df, reaction_time_col='RT',
                                     correctness_col='correctness')

    return {
        'WikiVocab_rt_mean': rt_acc[0],
        'WikiVocab_accuracy': rt_acc[1],
        'WikiVocab_num_items': rt_acc[2],
        'WikiVocab_num_pseudo_words': num_pseudo,
        'WikiVocab_num_real_words': num_real,
        'WikiVocab_incorrect_correct_score': incorrect_correct,
        'WikiVocab_pseudo_correct': pseudo_correct,
        'WikiVocab_real_correct': real_correct,
        'WikiVocab_overall_correct': overall_correct
    }


def preprocess_plab(plab_dir: Path):
    """Preprocess PLAB task output and compute mean RT and overall accuracy.

    Extract the 'correctness' and 'rt' column to calculate the mean and accuracy.

    **PLAB test**: The PLAB test is Pimsleur Language Aptitude Battery test.
    It is a test of language aptitude that is designed to measure an individual's ability to learn
    a foreign language.

    Parameters
    ----------
    plab_dir : Path
        Path to the folder containing the participants' PLAB data.

    Returns
    -------
    dict
        Dictionary with keys 'PLAB_rt_mean', 'PLAB_accuracy', and 'PLAB_num_items'.

    """
    df = _find_one_filetype_with_columns(plab_dir, ['rt', 'correctness'],
                                         allow_nan=True)
    rt_mean, accuracy, num_items = _reaction_time_accuracy(df, reaction_time_col='rt',
                                                           correctness_col='correctness')
    return {
        'PLAB_rt_mean': rt_mean,
        'PLAB_accuracy': accuracy,
        'PLAB_num_items': num_items
    }


def _reaction_time_accuracy(
        df: DataFrame,
        reaction_time_col: str,
        correctness_col: str,
        group_by_col: str | None = None,
        correct_only: bool = False,
) -> DataFrame | tuple[float, float, int]:
    """
    Calculate reaction time mean and accuracy, optionally grouped.

    Parameters
    ----------
    df : DataFrame
        DataFrame containing the reaction time and correctness columns.
    reaction_time_col : str
        Column name for reaction time.
    correctness_col : str
        Column name for correctness/accuracy (values must be 0/1 or booleans; NaN allowed).
    group_by_col : str, optional
        Column name to group by for calculating reaction time and accuracy.
        If this is given, the output is a DataFrame with mean reaction time and accuracy
        grouped by the specified column.
    correct_only : bool, optional
        If True, compute reaction time on correct trials only. For grouped outputs,
        reaction time is averaged over correct trials per group, while accuracy is
        still computed as the mean of the correctness column per group. Default False.

    Returns
    -------
    DataFrame | tuple[float, float, int]
        If ``group_by_col`` is None, returns a tuple of (mean reaction time, accuracy, num_items).
        If ``group_by_col`` is provided, returns a DataFrame indexed by the group values
        with three columns: ``rt_mean``, ``accuracy``, and ``num_items``, where
        num_items shows the number of non-NaN reaction time values per group.

    Raises
    ------
    ValueError
        If required columns are missing, DataFrame is empty, reaction time column
        is not numeric, correctness contains values outside {0,1,True,False,NaN},
        or NaN positions between reaction time and correctness columns do not match.

    Notes
    -----
    - NaN handling: rows with NaN in either reaction time or correctness are
      allowed, but their NaN positions must match to ensure paired calculations.
    - ``correct_only`` applies only to reaction time, accuracy always uses the full
      correctness column within each scope (grouped or ungrouped).
    """
    if not all(col in df.columns for col in [reaction_time_col, correctness_col]):
        raise ValueError(
            f"DataFrame must contain '{reaction_time_col}' and '{correctness_col}' columns."
        )
    # Validate inputs once
    __validate_rt_acc_inputs(df, reaction_time_col, correctness_col)

    # Grouped case: vectorised aggregations
    if group_by_col is not None:
        if group_by_col not in df.columns:
            raise ValueError(
                f"DataFrame must contain group_by column '{group_by_col}'.")

        # Get the grouped data
        grouped = df.groupby(group_by_col, dropna=True)

        # Accuracy per group
        acc = grouped[correctness_col].mean().rename('accuracy')

        # Reaction time per group (optionally only on correct trials)
        if correct_only:
            rt_series = df[df[correctness_col] == 1]
            rt = rt_series.groupby(group_by_col, dropna=True)[reaction_time_col].mean()
        else:
            rt = grouped[reaction_time_col].mean()
        rt = rt.rename('rt_mean')

        # Number of items per group
        num_items = grouped[reaction_time_col].count().rename('num_items')

        return rt.to_frame().join([acc, num_items], how='outer')

    # Ungrouped case
    if correct_only:
        rt_mean = df[df[correctness_col] == 1][reaction_time_col].mean()
    else:
        rt_mean = df[reaction_time_col].mean()
    accuracy = df[correctness_col].mean()
    num_items = df[reaction_time_col].notna().sum()

    return rt_mean, accuracy, num_items


def __validate_rt_acc_inputs(
        df: DataFrame,
        reaction_time_col: str,
        correctness_col: str,
) -> None:
    """Validate inputs for reaction time and accuracy computations.

    Ensures DataFrame is non-empty, NaN positions match between columns,
    reaction time is numeric (allowing NaNs), and correctness contains only
    0/1/True/False/NaN values.
    """
    if df.empty:
        raise ValueError("DataFrame is empty")
    # NaN positions must match between correctness and reaction time
    if df[correctness_col].isna().ne(df[reaction_time_col].isna()).any():
        raise ValueError(
            "NaN positions in correctness and reaction time columns do not match")
    # Reaction time must be numeric dtype (NaNs allowed)
    if df[reaction_time_col].dtype not in ['float64', 'float32', 'int64', 'int32']:
        raise ValueError("Reaction time column contains non-numeric values")
    # Correctness must be boolean-like (0/1/True/False/NaN)
    if not df[correctness_col].isin([0, 1, True, False, nan]).all():
        raise ValueError("Correctness column contains non-boolean values")


def _find_one_filetype_with_columns(folder: Path, columns: list[str],
                                    allow_nan=False) -> DataFrame:
    """Find a single CSV file containing specific columns and return it as DataFrame.

    This function searches a specified folder for CSV files and ensures that exactly one file
    contains all the specified columns. It returns the file as DataFrame with only the
    specified columns.

    Parameters
    ----------
    folder : Path
        Directory to search for the file.
    columns : list[str]
        List of column names that must be present in the CSV.
    allow_nan : bool, optional
        If True, allows NaN values in the ``columns`` asked for. Default is False.

    Returns
    -------
    DataFrame
        DataFrame containing only the specified columns.

    Raises
    ------
    ValueError
        If no CSV files with the required columns or multiple such files are found.
    ValueError
        If NaN values are found in required columns and ``allow_nan`` is False.
    """
    csvs = list(folder.glob("*.csv"))
    if not csvs:
        raise ValueError(f"No .csv files found in {folder}")

    valid_csvs = []
    for csv in csvs:
        # Only read the header to check columns
        try:
            if all(col in read_csv(csv, nrows=0).columns for col in columns):
                valid_csvs.append(csv)
        except UserWarning:
            continue

    if not valid_csvs:
        raise ValueError(f"No .csv files with columns {columns} found in {folder}")
    if len(valid_csvs) > 1:
        raise ValueError(
            f"Multiple .csv files with columns {columns} found in {folder}")

    df = read_csv(valid_csvs[0], usecols=columns)
    if not allow_nan and df.isna().any().any():
        raise ValueError(
            f"NaN values found in required columns {columns} in {valid_csvs[0]}")
    return df
