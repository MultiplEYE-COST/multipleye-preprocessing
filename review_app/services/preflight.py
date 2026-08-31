"""Full pipeline preflight check, invoked from the review app.

Creates a ``MultipleyeDataCollection`` (all sessions, no filters) and runs
the pipeline's ``run_preflight_check()``. Results are cached to
``review_data/{dcn}/preflight_result.yaml`` so the DCN overview page
loads instantly — the user clicks "Re-run" to refresh.
"""

import io
from contextlib import redirect_stderr
from datetime import UTC, datetime

import yaml

from ..config import PREPROCESSED_DATA_DIR, RAW_DATA_DIR, review_path

_CACHE_FILENAME = "preflight_result.yaml"


def run_pipeline_preflight(dcn_name: str, *, force: bool = False) -> dict:
    """Run the full pipeline preflight for *dcn_name* and return structured results.

    Parameters
    ----------
    dcn_name : str
        The data-collection name (e.g. ``"MultiplEYE_DA_DK_Aalborg_1_2025"``).
    force : bool
        If True, ignore any cached result and re-run.

    Returns
    -------
    dict with keys:
        status       — ``"pass"`` | ``"warn"`` | ``"fail"`` | ``"error"``
        error_groups — ``{label: [affected-sessions-or-paths]}``
        stderr       — raw warning text captured from stderr
        n_errors     — total error count
        n_sessions   — number of sessions discovered
        run_at       — ISO-8601 timestamp
    """
    cache_path = review_path(dcn_name) / _CACHE_FILENAME
    if not force and cache_path.exists():
        with open(cache_path) as f:
            return yaml.safe_load(f)

    from preprocessing.config import settings as pipe_settings

    _orig_dataset = pipe_settings.DATASET_DIR
    _orig_output = pipe_settings.OUTPUT_DIR
    try:
        pipe_settings.DATASET_DIR = RAW_DATA_DIR / dcn_name
        pipe_settings.OUTPUT_DIR = PREPROCESSED_DATA_DIR / dcn_name
        result = _do_run(dcn_name)
    finally:
        pipe_settings.DATASET_DIR = _orig_dataset
        pipe_settings.OUTPUT_DIR = _orig_output

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w") as f:
        yaml.dump(result, f, default_flow_style=False, sort_keys=False)

    return result


def invalidate_cache(dcn_name: str) -> None:
    """Remove the cached preflight result for *dcn_name*."""
    cache_path = review_path(dcn_name) / _CACHE_FILENAME
    if cache_path.exists():
        cache_path.unlink()


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------


def _do_run(dcn_name: str) -> dict:
    from preprocessing.data_collection import MultipleyeDataCollection

    data_dir = RAW_DATA_DIR / dcn_name
    if not data_dir.exists():
        return {
            "status": "error",
            "error_groups": {"Raw data folder": [f"DCN folder not found: {data_dir}"]},
            "stderr": "",
            "n_errors": 1,
            "n_sessions": 0,
            "run_at": _now_iso(),
        }

    try:
        dc = MultipleyeDataCollection.create_from_data_folder(
            data_dir,
            include_pilots=True,
            excluded_sessions=[],
            included_sessions=[],
        )
    except Exception as exc:
        return {
            "status": "error",
            "error_groups": {"Data collection init": [str(exc)]},
            "stderr": "",
            "n_errors": 1,
            "n_sessions": 0,
            "run_at": _now_iso(),
        }

    n_sessions = len(dc.sessions)

    from preprocessing.checks.preflight import PreflightError, run_preflight_check

    buf = io.StringIO()
    with redirect_stderr(buf):
        try:
            run_preflight_check(dc)
            errors: dict[str, list[str]] = {}
            status = "pass"
        except PreflightError as e:
            errors = dict(e.groups)
            status = "fail"
        except Exception as exc:
            errors = {"Unexpected error": [str(exc)]}
            status = "error"

    stderr_text = buf.getvalue().strip()
    if not errors and stderr_text:
        status = "warn"

    return {
        "status": status,
        "error_groups": errors,
        "stderr": stderr_text or "",
        "n_errors": sum(len(v) for v in errors.values()),
        "n_sessions": n_sessions,
        "run_at": _now_iso(),
    }


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
