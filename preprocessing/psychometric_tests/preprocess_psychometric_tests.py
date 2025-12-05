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


def preprocess_all_participants_and_print(test_session_folder: Path = PSYCHOMETRIC_TESTS_DIR):
    r"""Preprocess all available participants and tests.

    This script looks into ``test_session_folder`` and iterates over each folder of the pattern
    '\d{3}_.+' (any folder starting with a three-digit number, followed by an underscore.
    """

    participant_folders = test_session_folder.iterdir()
    # Filter for participant folders starting with three digits and underscore
    participant_folders = [folder for folder in participant_folders if _is_valid_folder(folder)]
    # Order
    participant_folders = sorted(participant_folders, key=lambda x: x.name)

    for participant in participant_folders:
        print(f"Participant: {participant.stem}")

        # LWMC (Lewandowsky Working Memory Capacity battery)
        lwmc_dir = participant / PSYM_LWMC_DIR
        if lwmc_dir.exists():
            try:
                lwmc_res = preprocess_lwmc(lwmc_dir)
                print("LWMC:\n", lwmc_res)
            except ValueError as err:
                warnings.warn(
                    f"Failed to process LWMC test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # RAN
        ran_dir = participant / PSYM_RAN_DIR
        if ran_dir.exists():
            print("RAN:\n", preprocess_ran(ran_dir))

        # Stroop & Flanker
        stroop_flanker_dir = participant / PSYM_STROOP_FLANKER_DIR
        if stroop_flanker_dir.exists():
            try:
                stroop_res = preprocess_stroop(stroop_flanker_dir)
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Stroop test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
                continue
            print("Stroop:\n", stroop_res)

            try:
                flanker_res = preprocess_flanker(stroop_flanker_dir)
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Flanker test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
                continue
            print("Flanker:\n", flanker_res)

            # preprocess_flanker(participant)
        wikivocab_dir = participant / PSYM_WIKIVOCAB_DIR
        if wikivocab_dir.exists():
            try:
                wikivocab_res = preprocess_wikivocab(wikivocab_dir)
            except ValueError as err:
                warnings.warn(
                    f"Failed to process WikiVocab test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
                continue
            print(f"WikiVocab: {wikivocab_res}")

        # PLAB
        plab_dir = participant / PSYM_PLAB_DIR
        if plab_dir.exists():
            try:
                plab_res = preprocess_plab(plab_dir)
            except ValueError as err:
                warnings.warn(
                    f"Failed to process PLAB test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
                continue
            print(f"PLAB: {plab_res[0]:.2f} sec, {plab_res[1]*100:.2f} %, {plab_res[2]} words")


def preprocess_all_participants(test_session_folder: Path = PSYCHOMETRIC_TESTS_DIR) -> Path:
    """Preprocess all participants and persist results in a wide, tabular CSV.

    Requirements:
    - One row per participant.
    - One column per returned value (no nested payloads/JSON).
    - Do not compute any new statistics - simply place the function returns into
      descriptive columns as-is.

    Column mapping (values as returned by the respective functions):
    - LWMC -> expand dict keys: LWMC_MU, LWMC_OS, LWMC_SS, LWMC_SSTM, LWMC_Total
    - RAN -> expand DataFrame rows into columns: RAN_Trial{n}_Reading_Time
    - Stroop -> expand dict keys: StroopAccuracyEffect, StroopRTEffect
    - Flanker -> expand dict keys: FlankerAccuracyEffect, FlankerRTEffect
    - WikiVocab -> tuple(rt_mean, accuracy) -> WikiVocab_RT_mean, WikiVocab_Accuracy
    - PLAB -> tuple(rt_mean, accuracy) -> PLAB_RT_mean, PLAB_Accuracy

    The output file overwrites psychometric_results/psychometric_outputs_all.csv
    in the provided test_session_folder.
    """
    # Collect participant folders
    participant_folders = test_session_folder.iterdir()
    participant_folders = [p for p in participant_folders if _is_valid_folder(p)]
    participant_folders = sorted(participant_folders, key=lambda p: p.name)

    rows: list[dict] = []

    def _pid_from_folder(folder: Path) -> str:
        return folder.stem[:3]

    for participant in participant_folders:
        pid = _pid_from_folder(participant)
        # Initialise row with participant and per-test calculated flags (0/1)
        row: dict = {
            'participant_id': pid,
            'LWMC_Calculated': 0,
            'RAN_Calculated': 0,
            'Stroop_Calculated': 0,
            'Flanker_Calculated': 0,
            'WikiVocab_Calculated': 0,
            'PLAB_Calculated': 0,
        }

        # LWMC
        lwmc_dir = participant / PSYM_LWMC_DIR
        if lwmc_dir.exists():
            try:
                res = preprocess_lwmc(lwmc_dir)  # dict
                # place dict keys as columns
                row.update(res)
                row['LWMC_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process LWMC test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # RAN (DataFrame with columns Trial, Reading_Time)
        ran_dir = participant / PSYM_RAN_DIR
        if ran_dir.exists():
            try:
                df_ran = preprocess_ran(ran_dir)
                # Mark calculated on successful preprocessing regardless of emptiness
                row['RAN_Calculated'] = 1
                if isinstance(df_ran, DataFrame) and not df_ran.empty:
                    # For each trial, create a dedicated column
                    for _, r in df_ran.iterrows():
                        try:
                            trial = int(r['Trial'])
                        except Exception:
                            # Fallback to string if not castable
                            trial = r['Trial']
                        col = f"RAN_Trial{trial}_Reading_Time"
                        row[col] = r['Reading_Time']
            except ValueError as err:
                warnings.warn(
                    f"Failed to process RAN test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # Stroop & Flanker
        sf_dir = participant / PSYM_STROOP_FLANKER_DIR
        if sf_dir.exists():
            try:
                stroop_res = preprocess_stroop(sf_dir)  # DataFrame

                # TODO: only return grouped rt mean and corr

                # Ensure both conditions are present
                required = {'congruent', 'incongruent'}
                missing = required.difference(stroop_res.index.astype(str))
                if missing:
                    raise ValueError(
                        f"Missing required stim_type levels for Stroop: {sorted(missing)}"
                    )

                row.update({
                    'StroopAccuracyEffect': float(
                        stroop_res.loc['incongruent', 'accuracy'] - stroop_res.loc['congruent', 'accuracy']
                    ),
                    'StroopRTEffect': float(
                        stroop_res.loc['incongruent', 'rt_mean'] - stroop_res.loc['congruent', 'rt_mean']
                    ),
                })

                row['Stroop_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Stroop test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )
            try:
                flanker_res = preprocess_flanker(sf_dir)  # DataFrame
                # Ensure both conditions are present
                required = {'congruent', 'incongruent'}
                missing = required.difference(flanker_res.index.astype(str))
                if missing:
                    raise ValueError(
                        f"Missing required stim_type levels for Flanker: {sorted(missing)}"
                    )

                row.update({
                    'FlankerAccuracyEffect': float(
                        flanker_res.loc['incongruent', 'accuracy'] - flanker_res.loc['congruent', 'accuracy']
                    ),
                    'FlankerRTEffect': float(
                        flanker_res.loc['incongruent', 'rt_mean'] - flanker_res.loc['congruent', 'rt_mean']
                    ),
                })
                row['Flanker_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process Flanker test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # WikiVocab (tuple[rt_mean, accuracy])
        wv_dir = participant / PSYM_WIKIVOCAB_DIR
        if wv_dir.exists():
            try:
                wv = preprocess_wikivocab(wv_dir)
                if isinstance(wv, tuple) and len(wv) == 2:
                    row['WikiVocab_RT_mean'] = wv[0]
                    row['WikiVocab_Accuracy'] = wv[1]
                row['WikiVocab_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process WikiVocab test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        # PLAB (tuple[rt_mean, accuracy])
        plab_dir = participant / PSYM_PLAB_DIR
        if plab_dir.exists():
            try:
                plab = preprocess_plab(plab_dir)
                if isinstance(plab, tuple) and len(plab) == 2:
                    row['PLAB_RT_mean'] = plab[0]
                    row['PLAB_Accuracy'] = plab[1]
                row['PLAB_Calculated'] = 1
            except ValueError as err:
                warnings.warn(
                    f"Failed to process PLAB test for {participant.stem}: {str(err)}",
                    category=UserWarning,
                )

        rows.append(row)

    # Write CSV (wide format)
    out_dir = test_session_folder / 'psychometric_results'
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'psychometric_outputs_all.csv'
    df = pd.DataFrame(rows)
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

    print(f"Wrote: {out_path}")
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
    DataFrame
        A DataFrame indexed by ``stim_type`` with columns ``rt_mean``, ``accuracy``
        and ``num_items``.
    """
    df = _find_one_filetype_with_columns(
        stroop_flanker_dir, ['stim_type', 'stroop_key.rt', 'stroop_key.corr'], allow_nan=True
    )
    return _reaction_time_accuracy(
        df,
        reaction_time_col='stroop_key.rt',
        correctness_col='stroop_key.corr',
        group_by_col='stim_type'
    )


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
    DataFrame
        A DataFrame indexed by ``stim_type`` with columns ``rt_mean``, ``accuracy``
        and ``num_items``.
    """
    df = _find_one_filetype_with_columns(
        stroop_flanker_dir, ['stim_type', 'Flanker_key.rt', 'Flanker_key.corr'], allow_nan=True
    )
    return _reaction_time_accuracy(
        df,
        reaction_time_col='Flanker_key.rt',
        correctness_col='Flanker_key.corr',
        group_by_col='stim_type'
    )


def preprocess_lwmc(lwmc_dir: Path):
    """Preprocess Lewandowsky WMC battery and compute task scores.

    Tasks:
    - MU (Memory Update): proportion of items recalled correctly across trials.
    - OS (Operation Span): proportion of items recalled in the correct list position.
    - SS (Sentence Span): proportion of items recalled in the correct list position.
    - SSTM (Spatial Short-Term Memory): overall score normalized by 240.

    Scoring logic adapted from Laura Stahlhut's Python implementation (2022) of the
    Lewandowsky WMC battery (see https://github.com/l-stahlhut/wmc-analysis/).
    Reference: Lewandowsky, S., et al. (2010). "A working memory test battery for MATLAB."
    Behavior Research Methods, 42(2), 571–585.

    Notes:
    - Strict behavior: raises ValueError when required files are missing or malformed.
    - No rounding is applied to the returned float values.
    - LWMC_Total includes SSTM in the arithmetic mean (MU, OS, SS, SSTM) — TODO: confirm
      whether SSTM should be included in the mean total.

    Parameters
    ----------
    lwmc_dir : Path
        Participant-specific directory containing WMC `.dat` files.

    Returns
    -------
    dict
        Dictionary with keys: 'LWMC_MU', 'LWMC_OS', 'LWMC_SS', 'LWMC_SSTM', 'LWMC_Total'.
    """

    def _participant_id_from_dir(d: Path) -> str:
        stem = d.parent.stem  # e.g., "010_SQ_CH_1_PT2"
        if len(stem) < 3 or not stem[:3].isdigit():
            raise ValueError(f"Cannot infer participant id from folder name: {stem}")
        # Files use non-zero-padded ids (e.g., MU-10.dat for 010)
        return str(int(stem[:3]))

    def _require_file(path: Path):
        if not path.exists():
            raise ValueError(f"Missing required WMC file: {path}")
        if not path.is_file():
            raise ValueError(f"WMC path is not a file: {path}")

    pid = _participant_id_from_dir(lwmc_dir)

    mu_file = lwmc_dir / f"MU-{pid}.dat"
    os_file = lwmc_dir / f"OS-{pid}.dat"
    ss_file = lwmc_dir / f"SS-{pid}.dat"
    sstm_file = lwmc_dir / f"SSTM-{pid}.dat"

    # Strict presence checks
    for f in (mu_file, os_file, ss_file, sstm_file):
        _require_file(f)

    def _read_lines(p: Path) -> list[str]:
        try:
            with p.open('r', encoding='utf-8') as fh:
                return fh.readlines()
        except Exception as exc:
            raise ValueError(f"Failed to read WMC file {p}: {exc}") from exc

    # MU scoring
    mu_lines = _read_lines(mu_file)
    mu_num = 0
    mu_den = 0
    for line in mu_lines:
        if not line.strip():
            continue
        try:
            vals = [int(x) for x in line.rstrip("\n").split(" ") if x != ""]
        except ValueError as exc:
            raise ValueError(f"Non-integer token in MU file {mu_file}: {line}") from exc
        # correctness flags are at indices 7..11, with -1 padding
        flags = vals[7:12]
        flags = [v for v in flags if v != -1]
        if not flags:
            continue
        # sum positives; denominator is count of valid flags
        mu_num += sum(1 for v in flags if v == 1)
        mu_den += len(flags)
    # If no valid MU flags are present (all entries padded with -1), treat MU as missing
    # instead of aborting the entire LWMC computation. This scenario appears in our data
    # where MU files exist but contain only padding (-1). We proceed with OS/SS/SSTM.
    mu_score = mu_num / mu_den if mu_den > 0 else nan

    # Helper for OS/SS scoring
    def _os_ss_score(lines: list[str], label: str) -> float:
        total_num = 0
        total_den = 0
        for line in lines:
            if not line.strip():
                continue
            parts = [x for x in line.rstrip("\n").split(" ") if x != ""]
            # Expect at least indexes up to typed letters
            if len(parts) < 18:
                # skip placeholder/short lines
                continue
            try:
                max_trial = int(parts[1])
            except ValueError:
                # skip lines with placeholder in trial-length (e.g., '?')
                continue
            if max_trial <= 0:
                continue
            presented = [x for x in parts[2:9] if x != '%']
            typed = [x for x in parts[10:17] if x != '%']
            if not presented:
                continue
            # Count position-correct items up to the shorter of the two lists
            correct = 0
            for a, b in zip(presented, typed):
                if a == b:
                    correct += 1
            total_num += correct
            total_den += max_trial
        if total_den == 0:
            return nan
        return total_num / total_den

    os_score = _os_ss_score(_read_lines(os_file), 'OS')
    ss_score = _os_ss_score(_read_lines(ss_file), 'SS')

    # SSTM scoring (score on 2nd line, 2nd token)
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

    # Compute total over available (non-NaN) task scores. TODO: confirm inclusion of SSTM
    scores = [mu_score, os_score, ss_score, sstm_score]
    valid_scores = [s for s in scores if s == s]  # filter out NaNs
    if not valid_scores:
        raise ValueError("No valid LWMC task scores computed")
    total = sum(valid_scores) / len(valid_scores)

    return {
        'LWMC_MU': mu_score,
        'LWMC_OS': os_score,
        'LWMC_SS': ss_score,
        'LWMC_SSTM': sstm_score,
        'LWMC_Total': total,
    }


def preprocess_ran(ran_dir: Path):
    """Preprocess RAN task output and return the trials with their reading times.

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
    tuple[float, float]
        Mean reaction time and accuracy.

    Raises
    ------
    ValueError
        If not exactly one .csv file is found in the directory.
    """
    return _find_one_filetype_with_columns(ran_dir, ['Trial', 'Reading_Time'], allow_nan=False)


def preprocess_wikivocab(wv_dir: Path):
    """Preprocess WikiVocab task output and compute mean RT and accuracy.

    LexTALE generalisation:

    - Add num_sudo_words / num_real_words 
    - Incorrect minus correct (number of existing words correct/number of existing words in list) + (number of nonwords correct/nonwords in list)) / 2
    - Percentages correct sudo / correct / overall

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

        - rt_mean: Mean reaction time
        - accuracy: Overall accuracy
        - num_sudo: Number of sudo words
        - num_real: Number of real words 
        - incorrect_correct_score: Balanced accuracy score (averaged % correct)
        - sudo_correct: Fraction of correct sudo words
        - real_correct: Fraction of correct real words
        - overall_correct: Overall fraction correct
    """
    df = _find_one_filetype_with_columns(
        wv_dir, ['correct_answer', 'real_answer', 'RT'], allow_nan=False
    )
    df['correctness'] = df['correct_answer'] == df['real_answer']

    # Calculate additional metrics
    num_sudo = len(df[df['correct_answer'] == 0])
    num_real = len(df[df['correct_answer'] == 1])

    # Calculate correct fractions
    sudo_correct = df[(df['correct_answer'] == 0) & (df['correctness'])].shape[0] / num_sudo if num_sudo > 0 else float('nan')
    real_correct = df[(df['correct_answer'] == 1) & (df['correctness'])].shape[0] / num_real if num_real > 0 else float('nan')
    overall_correct = df['correctness'].mean()

    # Calculate incorrect minus correct score
    incorrect_correct = (real_correct + sudo_correct) / 2

    rt_acc = _reaction_time_accuracy(df, reaction_time_col='RT', correctness_col='correctness')

    return {
        'rt_mean': rt_acc[0],
        'accuracy': rt_acc[1],
        'num_items': rt_acc[2],
        'num_sudo_words': num_sudo,
        'num_real_words': num_real,
        'incorrect_correct_score': incorrect_correct,
        'sudo_correct': sudo_correct,
        'real_correct': real_correct,
        'overall_correct': overall_correct
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
    tuple[float, float, int]
        Mean reaction time, accuracy and number of items.

    """
    df = _find_one_filetype_with_columns(plab_dir, ['rt', 'correctness'], allow_nan=True)
    return _reaction_time_accuracy(df, reaction_time_col='rt', correctness_col='correctness')

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
            raise ValueError(f"DataFrame must contain group_by column '{group_by_col}'.")

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
        raise ValueError("NaN positions in correctness and reaction time columns do not match")
    # Reaction time must be numeric dtype (NaNs allowed)
    if df[reaction_time_col].dtype not in ['float64', 'float32', 'int64', 'int32']:
        raise ValueError("Reaction time column contains non-numeric values")
    # Correctness must be boolean-like (0/1/True/False/NaN)
    if not df[correctness_col].isin([0, 1, True, False, nan]).all():
        raise ValueError("Correctness column contains non-boolean values")



def _find_one_filetype_with_columns(folder: Path, columns: list[str], allow_nan=False) -> DataFrame:
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
        raise ValueError(f"Multiple .csv files with columns {columns} found in {folder}")

    df = read_csv(valid_csvs[0], usecols=columns)
    if not allow_nan and df.isna().any().any():
        raise ValueError(f"NaN values found in required columns {columns} in {valid_csvs[0]}")
    return df

