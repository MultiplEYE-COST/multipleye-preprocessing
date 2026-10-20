import math
from pathlib import Path

import matplotlib

# Batch pipeline: always render with the non-interactive Agg backend. The
# GUI backend (e.g. macosx) adds significant overhead and can interfere with
# headless/server runs.
matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import PIL
import polars as pl
import pymovements as pm
from matplotlib.patches import Circle

from ..config import settings
from ..data_collection.stimulus import Stimulus

_SAMPLE_COLUMNS = ["pixel_x", "pixel_y"]
_EVENT_COLUMNS = ["duration", "location_x", "location_y"]


def build_page_frames(gaze: pm.Gaze):
    """Clone/unnest the gaze once and index samples and fixations by page.

    Returns the prepared gaze clone plus two dicts mapping
    ``(stimulus_name, page_name)`` to the samples/fixations of that page. This
    lets the per-page plotting look frames up instead of scanning the full
    session once per page and per stimulus.
    """
    data = gaze.clone()
    data.unnest(["pixel", "position", "velocity"])

    samples = data.samples.select(
        [settings.STIMULUS_COL, settings.PAGE_COL, *_SAMPLE_COLUMNS]
    )
    events = data.events.frame.filter(pl.col("name") == settings.FIXATION).select(
        [settings.STIMULUS_COL, settings.PAGE_COL, *_EVENT_COLUMNS]
    )

    samples_by_key = {
        key: frame
        for key, frame in samples.partition_by(
            [settings.STIMULUS_COL, settings.PAGE_COL],
            as_dict=True,
            include_key=False,
        ).items()
    }
    events_by_key = {
        key: frame
        for key, frame in events.partition_by(
            [settings.STIMULUS_COL, settings.PAGE_COL],
            as_dict=True,
            include_key=False,
        ).items()
    }
    return data, samples_by_key, events_by_key


def _lookup(key_frames, frame, key, columns, name=None):
    """Return the rows for ``key`` from a pre-indexed dict or by filtering."""
    if key_frames is not None:
        result = key_frames.get(key)
        if result is None:
            return pl.DataFrame({column: [] for column in columns})
        return result
    selection = (pl.col(settings.STIMULUS_COL) == key[0]) & (
        pl.col(settings.PAGE_COL) == key[1]
    )
    if name is not None:
        selection = selection & (pl.col("name") == name)
    return frame.filter(selection).select(columns)


def plot_gaze(
    gaze: pm.Gaze,
    stimulus: Stimulus,
    plots_dir: Path,
    duration_ms_in_cm: float = 0.03,
    aoi_image: bool = False,
    data: pm.Gaze | None = None,
    samples_by_key: dict | None = None,
    events_by_key: dict | None = None,
) -> None:
    if data is None:
        data = gaze.clone()
        data.unnest(["pixel", "position", "velocity"])

    # pixels per centimeter on this screen
    px_per_cm = data.experiment.screen.width_px / data.experiment.screen.width_cm

    for page in stimulus.pages:
        key = (
            f"{stimulus.name}_{stimulus.id}",
            f"{settings.PAGE_PREFIX}{page.number}",
        )
        page_samples = _lookup(samples_by_key, data.samples, key, _SAMPLE_COLUMNS)
        page_events = _lookup(
            events_by_key,
            data.events.frame,
            key,
            _EVENT_COLUMNS,
            name=settings.FIXATION,
        )

        fig, ax = plt.subplots()
        use_aoi = aoi_image or settings.PLOT_AOI_OVERLAY
        aoi_path = None
        if use_aoi:
            if page.aoi_image_path.exists():
                aoi_path = page.aoi_image_path
            else:
                # Fallback: try original data folder if it is not the same as output dir
                relative_aoi_path = page.aoi_image_path.relative_to(settings.OUTPUT_DIR)
                original_aoi_path = settings.DATASET_DIR / relative_aoi_path
                if original_aoi_path.exists():
                    aoi_path = original_aoi_path

        if aoi_path:
            stimulus_image = PIL.Image.open(aoi_path)
        else:
            stimulus_image = PIL.Image.open(page.image_path)
        ax.imshow(stimulus_image)

        # Plot raw gaze data
        plt.plot(
            page_samples["pixel_x"],
            page_samples["pixel_y"],
            color="black",
            linewidth=0.5,
            alpha=0.3,
        )

        # Plot fixations, make the rad scaled by the resolution
        for row in page_events.iter_rows(named=True):
            radius = math.sqrt(row["duration"]) * px_per_cm * duration_ms_in_cm

            fixation = Circle(
                (row["location_x"], row["location_y"]),
                radius,
                color="blue",
                fill=True,
                alpha=0.5,
                zorder=10,
            )
            ax.add_patch(fixation)
        ax.set_xlim((0, data.experiment.screen.width_px))
        ax.set_ylim((data.experiment.screen.height_px, 0))
        fig.savefig(plots_dir / f"{stimulus.name}_{page.number}.png")
        plt.close(fig)

    for question in stimulus.questions:
        screen_name = f"{settings.QUESTION_PREFIX}{int(question.id)}"  # Screen names don't have leading zeros
        key = (f"{stimulus.name}_{stimulus.id}", screen_name)
        page_samples = _lookup(samples_by_key, data.samples, key, _SAMPLE_COLUMNS)
        page_events = _lookup(
            events_by_key,
            data.events.frame,
            key,
            _EVENT_COLUMNS,
            name=settings.FIXATION,
        )

        fig, ax = plt.subplots()
        use_aoi = aoi_image or settings.PLOT_AOI_OVERLAY
        aoi_path = None
        if use_aoi:
            if question.aoi_image_path.exists():
                aoi_path = question.aoi_image_path
            else:
                # Fallback: try original data folder if it is not the same as output dir
                relative_aoi_path = question.aoi_image_path.relative_to(
                    settings.OUTPUT_DIR
                )
                original_aoi_path = settings.DATASET_DIR / relative_aoi_path
                if original_aoi_path.exists():
                    aoi_path = original_aoi_path

        if aoi_path:
            question_image = PIL.Image.open(aoi_path)
        else:
            question_image = PIL.Image.open(question.image_path)
        ax.imshow(question_image)

        # Plot raw gaze data
        plt.plot(
            page_samples["pixel_x"],
            page_samples["pixel_y"],
            color="black",
            linewidth=0.5,
            alpha=0.3,
        )

        # Plot fixations
        for row in page_events.iter_rows(named=True):
            radius = math.sqrt(row["duration"]) * px_per_cm * duration_ms_in_cm

            fixation = Circle(
                (row["location_x"], row["location_y"]),
                radius,
                color="blue",
                fill=True,
                alpha=0.5,
                zorder=10,
            )
            ax.add_patch(fixation)
        ax.set_xlim((0, data.experiment.screen.width_px))
        ax.set_ylim((data.experiment.screen.height_px, 0))
        fig.savefig(plots_dir / f"{stimulus.name}_q{question.id}.png")
        plt.close(fig)

    for rating in stimulus.ratings:
        screen_name = f"{rating.name}"  # Screen names don't have leading zeros
        page_samples = data.samples.filter(
            (pl.col(settings.TRIAL_COL) == f"trial_{stimulus.id}")
            & (pl.col(settings.PAGE_COL) == screen_name)
        ).select(
            pl.col("pixel_x"),
            pl.col("pixel_y"),
        )
        page_events = data.events.frame.filter(
            (pl.col(settings.STIMULUS_COL) == f"trial_{stimulus.id}")
            & (pl.col(settings.PAGE_COL) == screen_name)
            & (pl.col("name") == settings.FIXATION)
        ).select(
            pl.col("duration"),
            pl.col("location_x"),
            pl.col("location_y"),
        )

        fig, ax = plt.subplots()
        rating_image = PIL.Image.open(rating.image_path)
        ax.imshow(rating_image)

        # Plot raw gaze data
        plt.plot(
            page_samples["pixel_x"],
            page_samples["pixel_y"],
            color="black",
            linewidth=0.5,
            alpha=0.3,
        )

        # Plot fixations
        for row in page_events.iter_rows(named=True):
            radius = math.sqrt(row["duration"]) * px_per_cm * duration_ms_in_cm

            fixation = Circle(
                (row["location_x"], row["location_y"]),
                radius,
                color="blue",
                fill=True,
                alpha=0.5,
                zorder=10,
            )
            ax.add_patch(fixation)
        ax.set_xlim((0, data.experiment.screen.width_px))
        ax.set_ylim((data.experiment.screen.height_px, 0))
        fig.savefig(plots_dir / f"{stimulus.name}_{stimulus.id}_{rating.name}.png")
        plt.close(fig)


def plot_main_sequence(events: pm.Events, plots_dir: Path) -> None:
    pm.plotting.main_sequence_plot(
        events,
        savepath=plots_dir / "main_sequence.png",
    )
