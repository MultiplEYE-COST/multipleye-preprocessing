import warnings
from math import nan
from pathlib import Path

from pandas import read_csv, DataFrame, to_numeric
from pandas.core.roperator import rand_

from preprocessing.config import PSYCHOMETRIC_TESTS_DIR, PSYM_LWMC_DIR, PSYM_RAN_DIR, \
    PSYM_STROOP_FLANKER_DIR, PSYM_WIKIVOCAB_DIR, PSYM_PLAB_DIR


def preprocess_all_participants(test_session_folder: Path = PSYCHOMETRIC_TESTS_DIR):
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

        # if (participant / PSYM_LWMC_DIR).exists():
        #     preprocess_lwmc(participant)\

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
            print(f"WikiVocab: {wikivocab_res[0]:.2f} sec, {wikivocab_res[1]*100:.2f} %")


        # if (participant / PSYM_LEXTALE_DIR).exists():
        #     preprocess_lextale(participant)

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
            print(f"PLAB: {plab_res[0]:.2f} sec, {plab_res[1]*100:.2f} %")


def _is_valid_folder(folder: Path) -> bool:
    return folder.is_dir() and folder.stem[:3].isdigit() and folder.stem[3] == '_'


def preprocess_stroop(stroop_flanker_dir: Path):
    """
    
    Extract 'stim_type', 'stroop_key.rt' and 'stroop_key.corr',
    to calculate reaction time and accuracy, grouped by stimulus type.
    
    
    Parameters
    ----------
    stroop_flanker_dir : Path
        Path to the folder containing the participants' stroop and flanker data.
 
    Returns
    -------
    
    """
    df = _find_one_filetype_with_columns(
        stroop_flanker_dir, ['stim_type', 'stroop_key.rt', 'stroop_key.corr']
    )
    return _reaction_time_accuracy(
        df,
        reaction_time_col='stroop_key.rt',
        correctness_col='stroop_key.corr',
        group_by_col='stim_type'
    )


def preprocess_flanker(stroop_flanker_dir: Path):
    """

    Extract 'stim_type', 'flanker_key.rt' and 'flanker_key.corr',
    to calculate reaction time and accuracy, grouped by stimulus type.


    Parameters
    ----------
    stroop_flanker_dir : Path
        Path to the folder containing the participants' stroop and flanker data.

    Returns
    -------

    """
    df = _find_one_filetype_with_columns(
        stroop_flanker_dir, ['stim_type', 'Flanker_key.rt', 'Flanker_key.corr']
    )
    return _reaction_time_accuracy(
        df,
        reaction_time_col='Flanker_key.rt',
        correctness_col='Flanker_key.corr',
        group_by_col='stim_type'
    )


def preprocess_lwmc(lwmc_dir: Path):
    raise NotImplementedError


def preprocess_ran(ran_dir: Path):
    """

    Finds the only .csv in the folder and extracts the 'Trial' and 'Reading_Time' columns.
    The sudio files and logs are kept untouched.

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
    return _find_one_filetype_with_columns(ran_dir, ['Trial', 'Reading_Time'])


def preprocess_wikivocab(wv_dir: Path):
    """

    Extract 'correct_answer', 'real_answer' and 'RT' columns, infer a 'correctness' column,
    and return the mean reaction time and accuracy.

    Parameters
    ----------
    wv_dir : Path
        Path to the folder containing the participants' Wikivocab data.

    Returns
    -------
    tuple[float, float]
        Mean reaction time and accuracy.
    """
    df = _find_one_filetype_with_columns(wv_dir, ['correct_answer', 'real_answer', 'RT'])
    df['correctness'] = df['correct_answer'] == df['real_answer']
    return _reaction_time_accuracy(df, reaction_time_col='RT', correctness_col='correctness')


def preprocess_lextale(lt_dir: Path):
    raise NotImplementedError


def preprocess_plab(plab_dir: Path):
    """

    Extract the 'correctness' and 'rt' column to calculate the mean and accuracy.
    
    
    Parameters
    ----------
    plab_dir : Path
        Path to the folder containing the participants' PLAB data.

    Returns
    -------
    tuple[float, float]
        Mean reaction time and accuracy.

    """
    df = _find_one_filetype_with_columns(plab_dir, ['rt', 'correctness'])
    return _reaction_time_accuracy(df, reaction_time_col='rt', correctness_col='correctness')

def _reaction_time_accuracy(
        df: DataFrame,
        reaction_time_col: str,
        correctness_col: str,
        group_by_col: str | None = None,
        correct_only: bool = False,
) -> DataFrame | tuple[float, float]:
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
    DataFrame | tuple[float, float]
        If ``group_by_col`` is None, returns a tuple of (mean reaction time, accuracy).
        If ``group_by_col`` is provided, returns a DataFrame indexed by the group values
        with two columns: ``rt_mean`` and ``accuracy``.

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

    # Grouped case: vectorized aggregations
    if group_by_col is not None:
        if group_by_col not in df.columns:
            raise ValueError(f"DataFrame must contain group_by column '{group_by_col}'.")

        # Accuracy per group
        acc = (
            df.groupby(group_by_col, dropna=True)[correctness_col]
              .mean()
              .rename('accuracy')
        )

        # Reaction time per group (optionally only on correct trials)
        if correct_only:
            rt_series = df[df[correctness_col] == 1]
        else:
            rt_series = df
        rt = (
            rt_series.groupby(group_by_col, dropna=True)[reaction_time_col]
                     .mean()
                     .rename('rt_mean')
        )

        return rt.to_frame().join(acc, how='outer')

    # Ungrouped case
    if correct_only:
        rt_mean = df[df[correctness_col] == 1][reaction_time_col].mean()
    else:
        rt_mean = df[reaction_time_col].mean()
    accuracy = df[correctness_col].mean()

    return rt_mean, accuracy


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



def _find_one_filetype_with_columns(folder: Path, columns: list[str]) -> DataFrame:
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

    Returns
    -------
    DataFrame
        DataFrame containing only the specified columns.

    Raises
    ------
    ValueError
        If no CSV files with the required columns or multiple such files are found.
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

    return read_csv(valid_csvs[0], usecols=columns)[columns]
