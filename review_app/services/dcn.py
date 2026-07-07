"""Discover data collections and read overview YAMLs."""

import yaml

from preprocessing.models import Dcn

from ..config import (
    PREPROCESSED_DATA_DIR,
    metadata_path,
    quality_thresholds_path,
)
from ..models import DcnSummary, SessionSummary
from .review import load_review
from .session_data import read_overview, compute_checks


def list_dcns() -> list[DcnSummary]:
    """List all data collections in the preprocessed data directory.

    :returns: List of DcnSummary for each discovered data collection.
    """
    if not PREPROCESSED_DATA_DIR.exists():
        return []

    dcns: list[DcnSummary] = []
    for entry in sorted(PREPROCESSED_DATA_DIR.iterdir()):
        if not entry.is_dir():
            continue
        try:
            dcn = Dcn(entry.name)
        except (ValueError, TypeError):
            continue
        dcns.append(_build_dcn_summary(dcn))

    return dcns


def get_dcn(dcn_name: str) -> DcnSummary | None:
    """Get a single data collection's summary.

    :param dcn_name: Data collection name.
    :returns: DcnSummary or None if not found.
    """
    dcns = list_dcns()
    for d in dcns:
        if d.dcn_name == dcn_name:
            return d
    return None


def _build_dcn_summary(dcn: Dcn) -> DcnSummary:
    dcn_name = str(dcn)
    is_processed = quality_thresholds_path(dcn_name).exists()
    sessions = list_sessions(dcn_name)

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

    return DcnSummary(
        dcn_name=dcn_name,
        language=dcn.lang,
        country=dcn.country,
        year=dcn.year,
        n_sessions=len(sessions),
        n_pilots=n_pilots,
        is_processed=is_processed,
        n_reviewed_unreviewed=n_reviewed.get("unreviewed", 0),
        n_reviewed_accepted=n_reviewed.get("accepted", 0),
        n_reviewed_flagged=n_reviewed.get("flagged", 0),
        n_reviewed_excluded=n_reviewed.get("excluded", 0),
    )


def list_sessions(dcn_name: str) -> list[SessionSummary]:
    """List all sessions in a data collection with review status.

    Scans the metadata/ folder for session overview YAMLs.

    :param dcn_name: Data collection name.
    :returns: List of SessionSummary.
    """
    from ..config import PREPROCESSED_DATA_DIR

    meta_base = PREPROCESSED_DATA_DIR / dcn_name / "metadata"

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

    return SessionSummary(
        sid=sid,
        pid=pid,
        is_pilot=is_pilot,
        n_flags=n_fail + n_warn,
        n_fail_flags=n_fail,
        n_warn_flags=n_warn,
        review_status=review.status,
        reviewer=review.reviewer,
    )
