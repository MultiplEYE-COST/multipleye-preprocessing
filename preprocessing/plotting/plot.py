import argparse
import math
from pathlib import Path

import PIL
import matplotlib.pyplot as plt
import polars as pl
import pymovements as pm
from matplotlib.patches import Circle

from preprocessing.data_collection.stimulus import LabConfig, Stimulus, load_stimuli



def plot_gaze(gaze: pm.GazeDataFrame, stimulus: Stimulus, plots_dir: Path) -> None:
    for page in stimulus.pages:
        screen_gaze = gaze.frame.filter(
            (pl.col("stimulus") == f"{stimulus.name}_{stimulus.id}")
            & (pl.col("screen") == f"page_{page.number}")
        ).select(
            pl.col("pixel").list.get(0).alias("pixel_x"),
            pl.col("pixel").list.get(1).alias("pixel_y"),
        )
        page_events = gaze.events.frame.filter(
            (pl.col("stimulus") == f"{stimulus.name}_{stimulus.id}")
            & (pl.col("screen") == f"page_{page.number}")
            & (pl.col("name") == "fixation")
        ).select(
            pl.col("duration"),
            pl.col("location").list.get(0).alias("pixel_x"),
            pl.col("location").list.get(1).alias("pixel_y"),
        )

        fig, ax = plt.subplots()
        stimulus_image = PIL.Image.open(page.image_path)
        ax.imshow(stimulus_image)

        # Plot raw gaze data
        plt.plot(
            screen_gaze["pixel_x"],
            screen_gaze["pixel_y"],
            color="black",
            linewidth=0.5,
            alpha=0.3,
        )

        # Plot fixations
        for row in page_events.iter_rows(named=True):
            fixation = Circle(
                (row["pixel_x"], row["pixel_y"]),
                math.sqrt(row["duration"]),
                color="blue",
                fill=True,
                alpha=0.5,
                zorder=10,
            )
            ax.add_patch(fixation)
        ax.set_xlim((0, gaze.experiment.screen.width_px))
        ax.set_ylim((gaze.experiment.screen.height_px, 0))
        fig.savefig(plots_dir / f"{stimulus.name}_{page.number}.png")
        plt.close(fig)

    for question in stimulus.questions:
        screen_name = (
            f"question_{int(question.id)}"  # Screen names don't have leading zeros
        )
        screen_gaze = gaze.frame.filter(
            (pl.col("stimulus") == f"{stimulus.name}_{stimulus.id}")
            & (pl.col("screen") == screen_name)
        ).select(
            pl.col("pixel").list.get(0).alias("pixel_x"),
            pl.col("pixel").list.get(1).alias("pixel_y"),
        )
        page_events = gaze.events.frame.filter(
            (pl.col("stimulus") == f"{stimulus.name}_{stimulus.id}")
            & (pl.col("screen") == screen_name)
            & (pl.col("name") == "fixation")
        ).select(
            pl.col("duration"),
            pl.col("location").list.get(0).alias("pixel_x"),
            pl.col("location").list.get(1).alias("pixel_y"),
        )

        fig, ax = plt.subplots()
        question_image = PIL.Image.open(question.image_path)
        ax.imshow(question_image)

        # Plot raw gaze data
        plt.plot(
            screen_gaze["pixel_x"],
            screen_gaze["pixel_y"],
            color="black",
            linewidth=0.5,
            alpha=0.3,
        )

        # Plot fixations
        for row in page_events.iter_rows(named=True):
            fixation = Circle(
                (row["pixel_x"], row["pixel_y"]),
                math.sqrt(row["duration"]),
                color="blue",
                fill=True,
                alpha=0.5,
                zorder=10,
            )
            ax.add_patch(fixation)
        ax.set_xlim((0, gaze.experiment.screen.width_px))
        ax.set_ylim((gaze.experiment.screen.height_px, 0))
        fig.savefig(plots_dir / f"{stimulus.name}_q{question.id}.png")
        plt.close(fig)

    for rating in stimulus.ratings:
        screen_name = (
            f"{rating.name}"  # Screen names don't have leading zeros
        )
        screen_gaze = gaze.frame.filter(
            (pl.col("trial") == f"trial_{stimulus.id}")
            & (pl.col("screen") == screen_name)
        ).select(
            pl.col("pixel").list.get(0).alias("pixel_x"),

            pl.col("pixel").list.get(1).alias("pixel_y"),
        )
        page_events = gaze.events.frame.filter(
            (pl.col("stimulus") == f"trial_{stimulus.id}")
            & (pl.col("screen") == screen_name)
            & (pl.col("name") == "fixation")
        ).select(
            pl.col("duration"),
            pl.col("location").list.get(0).alias("pixel_x"),
            pl.col("location").list.get(1).alias("pixel_y"),
        )

        fig, ax = plt.subplots()
        rating_image = PIL.Image.open(rating.image_path)
        ax.imshow(rating_image)

        # Plot raw gaze data
        plt.plot(
            screen_gaze["pixel_x"],
            screen_gaze["pixel_y"],
            color="black",
            linewidth=0.5,
            alpha=0.3,
        )

        # Plot fixations
        for row in page_events.iter_rows(named=True):
            fixation = Circle(
                (row["pixel_x"], row["pixel_y"]),
                math.sqrt(row["duration"]),
                color="blue",
                fill=True,
                alpha=0.5,
                zorder=10,
            )
            ax.add_patch(fixation)
        ax.set_xlim((0, gaze.experiment.screen.width_px))
        ax.set_ylim((gaze.experiment.screen.height_px, 0))
        fig.savefig(plots_dir / f"{stimulus.name}_{stimulus.id}_{rating.name}.png")
        plt.close(fig)


def plot_main_sequence(events: pm.EventDataFrame, plots_dir: Path) -> None:
    pm.plotting.main_sequence_plot(
        events, show=False, savepath=plots_dir / "main_sequence.png"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate plots for a MultiplEYE session"
    )
    parser.add_argument("asc_file", type=Path, help="Path to the ASC file")
    parser.add_argument(
        "stimulus_dir", type=Path, help="Path to the stimulus directory"
    )

    parser.add_argument("--plots-dir", type=Path, required=True, help="Path to save the plots")
    args = parser.parse_args()

    print("Loading data...")
    stimuli, lab_config = load_stimuli(
        args.stimulus_dir,
        "nl",
        "nl",
        1,
    )
    gaze = load_data(
        args.asc_file,
        lab_config,
    )
    print("Preprocessing...")
    preprocess(gaze)
    for stimulus in stimuli:
        print(f"Plotting {stimulus.name}...")
        plot_gaze(gaze, stimulus, args.plots_dir)
