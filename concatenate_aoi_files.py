#!/usr/bin/env python3
"""
Concatenate multiple AOI CSV files (with and without 'questions' in filename)
into two separate combined files, preserving the order defined in a stimulus order file.

Example usage:
    python concat_aoi_files_ordered.py \
        --input-folder data/.../aoi_stimuli_sq_ch_1 \
        --order-file data/.../completed_stimuli.csv \
        --output-prefix data/concatenated_aoi
"""

import argparse
from pathlib import Path
import polars as pl


def concat_csv_files(file_list, label_order):
    """Read and concatenate AOI CSV files in the order of label_order."""
    dfs = []
    for stim_name in label_order:
        # find matching AOI file (case-insensitive)
        matches = [f for f in file_list if stim_name.lower() in f.name.lower()]
        if not matches:
            print(f"⚠️  No AOI file found for stimulus: {stim_name}")
            continue
        f = matches[0]
        df = pl.read_csv(f)
        dfs.append(df)
    if not dfs:
        return pl.DataFrame()
    return pl.concat(dfs, how="vertical_relaxed")


def main():
    parser = argparse.ArgumentParser(description="Concatenate AOI CSV files.")
    parser.add_argument(
        "--input-folder", "-i",
        type=Path,
        required=True,
        help="Folder containing AOI CSV files."
    )
    parser.add_argument(
        "--order-file", "-s",
        type=Path,
        required=True,
        help="CSV file (e.g. completed_stimuli.csv) specifying the order of stimuli."
    )
    parser.add_argument(
        "--output-prefix", "-o",
        type=Path,
        required=True,
        help="Output path prefix (without extension)."
    )
    args = parser.parse_args()

    # Read stimulus order file
    order_df = pl.read_csv(args.order_file)
    label_order = [
        name for name in order_df["stimulus_name"].drop_nans().to_list() if isinstance(name, str)
    ]
    print(f"Stimulus order: {label_order}")

    # collect all CSV files
    all_files = sorted(
        f for f in args.input_folder.glob("*.csv")
        if not f.name.startswith("._") and not f.name.startswith(".")
    )

    if not all_files:
        raise FileNotFoundError(f"No CSV files found in {args.input_folder}")

    # separate into 'all' and 'non-questions'
    no_question_files = [
        f for f in all_files if "questions" not in f.name.lower()]

    len_question_files = len(all_files) - len(no_question_files)
    print(
        f"There are total {len(all_files)} AOI files with {len_question_files} of them containing 'questions'.")

    # concatenate
    df_all = concat_csv_files(all_files, label_order)
    df_no_questions = concat_csv_files(no_question_files, label_order)

    # save results
    out_all = args.output_prefix.with_name(
        args.output_prefix.name + "_all.csv")
    out_no_questions = args.output_prefix.with_name(
        args.output_prefix.name + "_no_questions.csv")

    df_all.write_csv(out_all)
    df_no_questions.write_csv(out_no_questions)

    print(f"✅ Saved all AOI data to: {out_all}")
    print(f"✅ Saved non-questions AOI data to: {out_no_questions}")


if __name__ == "__main__":
    main()
