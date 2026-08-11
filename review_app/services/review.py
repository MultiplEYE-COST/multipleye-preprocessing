"""Read and write review annotations to a single per-DCN YAML file.

Uses atomic write (tempfile -> os.replace) to prevent file corruption.
Reviews are stored keyed by SID in ``review_data/<DCN>/reviews.yaml``.
"""

import yaml
import os
import tempfile
from datetime import datetime, timezone

from ..models import ReviewAnnotation
from ..config import reviews_file_path


REVIEW_STATUSES = {"unreviewed", "accepted", "flagged", "excluded"}


def _load_all_reviews(dcn_name: str) -> dict[str, dict]:
    path = reviews_file_path(dcn_name)
    if not path.exists():
        return {}
    with open(path) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)
    return data if isinstance(data, dict) else {}


def load_review(dcn_name: str, sid: str) -> ReviewAnnotation:
    """Load the review annotation for a session from the per-DCN reviews file.

    :param dcn_name: Data collection name.
    :param sid: Session identifier.
    :returns: ReviewAnnotation (defaults to unreviewed if file or entry not found).
    """
    all_reviews = _load_all_reviews(dcn_name)
    entry = all_reviews.get(sid, {})
    status = entry.get("status", "unreviewed")
    if status not in REVIEW_STATUSES:
        status = "unreviewed"
    return ReviewAnnotation(
        status=status,
        reviewer=entry.get("reviewer", ""),
        comment=entry.get("comment", ""),
        reviewed_at=entry.get("reviewed_at"),
        type_of_issue=entry.get("type_of_issue", ""),
        needs_reprocessing=entry.get("needs_reprocessing", False),
    )


ISSUE_TYPES = {
    "calibration_validation": "Cal-/Validation",
    "data_loss": "Data loss",
    "incomplete": "Incomplete",
    "see_comment": "See comment",
}


def save_review(
    dcn_name: str,
    sid: str,
    status: str,
    reviewer: str = "",
    comment: str = "",
    type_of_issue: str = "",
    needs_reprocessing: bool = False,
) -> ReviewAnnotation:
    """Save a review annotation to the per-DCN reviews file.

    Uses atomic write (tempfile -> os.replace) to prevent corruption.

    :param dcn_name: Data collection name.
    :param sid: Session identifier.
    :param status: Review status.
    :param reviewer: Reviewer name (auto-set from cookie).
    :param comment: Review comment.
    :param type_of_issue: Optional issue type classification.
    :param needs_reprocessing: Whether the session needs reprocessing.
    :returns: The saved ReviewAnnotation.
    :raises ValueError: If status is not a valid review status.
    """
    if status not in REVIEW_STATUSES:
        raise ValueError(
            f"Invalid review status: {status}. Must be one of {REVIEW_STATUSES}"
        )

    if type_of_issue and type_of_issue not in ISSUE_TYPES:
        raise ValueError(
            f"Invalid issue type: {type_of_issue}. Must be one of {list(ISSUE_TYPES.keys())}"
        )

    reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    annotation = ReviewAnnotation(
        status=status,
        reviewer=reviewer,
        comment=comment,
        reviewed_at=reviewed_at,
        type_of_issue=type_of_issue,
        needs_reprocessing=needs_reprocessing,
    )

    path = reviews_file_path(dcn_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    all_reviews = _load_all_reviews(dcn_name)
    all_reviews[sid] = {
        "status": annotation.status,
        "reviewer": annotation.reviewer,
        "comment": annotation.comment,
        "reviewed_at": annotation.reviewed_at,
        "type_of_issue": annotation.type_of_issue,
        "needs_reprocessing": annotation.needs_reprocessing,
    }

    fd, tmp_path = tempfile.mkstemp(suffix=".yaml", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            yaml.dump(all_reviews, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise

    return annotation
