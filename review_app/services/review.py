"""Read and write review annotations to per-session YAML files."""

import yaml
import os
import tempfile
from datetime import datetime, timezone

from ..models import ReviewAnnotation
from ..config import review_file_path


REVIEW_STATUSES = {"unreviewed", "accepted", "flagged", "excluded"}


def load_review(dcn_name: str, sid: str) -> ReviewAnnotation:
    """Load the review annotation for a session.

    :param dcn_name: Data collection name.
    :param sid: Session identifier.
    :returns: ReviewAnnotation (defaults to unreviewed if file not found).
    """
    path = review_file_path(dcn_name, sid)
    if not path.exists():
        return ReviewAnnotation()

    with open(path) as f:
        data = yaml.load(f, Loader=yaml.FullLoader)

    if not data:
        return ReviewAnnotation()

    status = data.get("status", "unreviewed")
    if status not in REVIEW_STATUSES:
        status = "unreviewed"

    return ReviewAnnotation(
        status=status,
        reviewer=data.get("reviewer", ""),
        comment=data.get("comment", ""),
        reviewed_at=data.get("reviewed_at"),
        type_of_issue=data.get("type_of_issue", ""),
        needs_reprocessing=data.get("needs_reprocessing", False),
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
    """Save a review annotation to the per-session YAML file.

    Uses atomic write (tempfile → os.replace) to prevent corruption.

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

    path = review_file_path(dcn_name, sid)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = {
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
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
        os.replace(tmp_path, path)
    except Exception:
        os.unlink(tmp_path)
        raise

    return annotation
