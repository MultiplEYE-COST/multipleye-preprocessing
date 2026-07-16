"""Discover data collections (from both raw data/ and preprocessed_data/) and read overviews."""

import yaml

from preprocessing.models import Dcn

from ..config import PREPROCESSED_DATA_DIR, RAW_DATA_DIR
from ..models import DcnSummary, SessionSummary
from .review import load_review
from .session_data import read_overview, compute_checks
from .preflight import run_pipeline_preflight


def _discover_dcn_names() -> set[str]:
    """Collect DCN names from both raw data/ and preprocessed_data/."""
    names: set[str] = set()

    for base in (RAW_DATA_DIR, PREPROCESSED_DATA_DIR):
        if not base.exists():
            continue
        for entry in base.iterdir():
            if not entry.is_dir():
                continue
            try:
                Dcn(entry.name)
                names.add(entry.name)
            except (ValueError, TypeError):
                pass

    return names


def list_dcns() -> list[DcnSummary]:
    dcns: list[DcnSummary] = []
    for dcn_name in sorted(_discover_dcn_names()):
        dcn = Dcn(dcn_name)
        dcns.append(_build_dcn_summary(dcn))
    return dcns


def get_dcn(dcn_name: str) -> DcnSummary | None:
    dcns = list_dcns()
    for d in dcns:
        if d.dcn_name == dcn_name:
            return d
    return None


def _build_dcn_summary(dcn: Dcn) -> DcnSummary:
    dcn_name = str(dcn)
    meta_dir = PREPROCESSED_DATA_DIR / dcn_name / "metadata"
    is_processed = meta_dir.exists() and any(meta_dir.iterdir())
    has_raw_data = (RAW_DATA_DIR / dcn_name).exists()

    sessions = list_sessions(dcn_name) if is_processed else []

    n_reviewed: dict[str, int] = {
        "unreviewed": 0,
        "accepted": 0,
        "flagged": 0,
        "excluded": 0,
    }
    n_pilots = 0
    for s in sessions:
        n_reviewed[s.review_status] = n_reviewed.get(s.review_status, 0) + 1
        if s.is_pilot:
            n_pilots += 1

    preflight_status: str = "pass"
    preflight_detail: dict | None = None
    if has_raw_data or is_processed:
        result = run_pipeline_preflight(dcn_name)
        raw_status = result.get("status", "pass")
        preflight_status = "fail" if raw_status == "error" else raw_status
        preflight_detail = result

    return DcnSummary(
        dcn_name=dcn_name,
        language=dcn.lang,
        country=dcn.country,
        city=dcn.city,
        year=dcn.year,
        n_sessions=len(sessions),
        n_pilots=n_pilots,
        is_processed=is_processed,
        has_raw_data=has_raw_data,
        preflight_status=preflight_status,
        preflight_detail=preflight_detail,
        n_reviewed_unreviewed=n_reviewed.get("unreviewed", 0),
        n_reviewed_accepted=n_reviewed.get("accepted", 0),
        n_reviewed_flagged=n_reviewed.get("flagged", 0),
        n_reviewed_excluded=n_reviewed.get("excluded", 0),
    )


def list_sessions(dcn_name: str) -> list[SessionSummary]:
    from ..config import _METADATA_FOLDER

    meta_base = PREPROCESSED_DATA_DIR / dcn_name / _METADATA_FOLDER
    if not meta_base.exists():
        return []

    sessions: list[SessionSummary] = []
    for entry in sorted(meta_base.iterdir()):
        if not entry.is_dir():
            continue
        sid = entry.name
        summary = _build_session_summary(dcn_name, sid)
        if summary:
            sessions.append(summary)
    return sessions


def _build_session_summary(dcn_name: str, sid: str) -> SessionSummary | None:
    from ..config import metadata_path, quality_thresholds_path

    overview = read_overview(metadata_path(dcn_name, sid) / f"{sid}_overview.yaml")
    if overview is None:
        return None

    pid = overview.get("participant_id", 0)
    is_pilot = overview.get("is_pilot", False)

    thresholds = None
    t_path = quality_thresholds_path(dcn_name)
    if t_path.exists():
        with open(t_path) as f:
            thresholds = yaml.safe_load(f)

    checks = compute_checks(overview, thresholds)
    n_fail = sum(1 for c in checks if c.status == "fail")
    n_warn = sum(1 for c in checks if c.status == "warn")

    review = load_review(dcn_name, sid)
    comment_preview = review.comment.split("\n")[0][:80] if review.comment else ""
    num_completed_trials = overview.get("num_completed_trials")

    return SessionSummary(
        sid=sid,
        pid=pid,
        is_pilot=is_pilot,
        n_flags=n_fail + n_warn,
        n_fail_flags=n_fail,
        n_warn_flags=n_warn,
        review_status=review.status,
        reviewer=review.reviewer,
        comment_preview=comment_preview,
        num_completed_trials=num_completed_trials,
        needs_reprocessing=review.needs_reprocessing,
    )
