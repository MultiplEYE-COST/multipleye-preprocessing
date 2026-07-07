"""Session-level routes — detail page, review save."""

from fastapi import APIRouter, HTTPException, Query

from ..models import SessionDetail
from ..services.session_data import read_overview, build_session_detail
from ..services.thresholds import load_thresholds
from ..services.review import load_review, save_review
from ..config import session_overview_path


router = APIRouter(prefix="/api/session")


@router.get("/{sid}")
async def session_detail(
    sid: str,
    dcn: str = Query(..., description="Data collection name"),
) -> SessionDetail:
    ov = read_overview(session_overview_path(dcn, sid))
    if ov is None:
        raise HTTPException(
            status_code=404, detail=f"Session '{sid}' not found in DCN '{dcn}'"
        )
    thresholds = load_thresholds(dcn)
    review = load_review(dcn, sid)
    return build_session_detail(ov, review, thresholds, dcn, sid)


@router.post("/{sid}/review")
async def session_review_save(
    sid: str,
    dcn: str = Query(..., description="Data collection name"),
    status: str = Query(default="unreviewed"),
    reviewer: str = Query(default=""),
    comment: str = Query(default=""),
) -> dict:
    annotation = save_review(
        dcn, sid, status=status, reviewer=reviewer, comment=comment
    )
    return annotation.model_dump()
