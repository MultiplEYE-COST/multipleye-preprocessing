"""Swipe mode routes — Tinder-like swipe review of scanpath plots."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..templating import render
from ..services.dcn import get_dcn
from ..services.swipe import (
    swipe_queue,
    save_judgment,
    remove_judgment,
    swipe_stats,
)

router = APIRouter()


@router.get("/dcn/{dcn_name}/swipe")
async def swipe_page(request: Request, dcn_name: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    sessions = swipe_queue(dcn_name)
    stats = swipe_stats(dcn_name)
    html = render(
        "dcn/swipe.html",
        request=request,
        dcn=dcn,
        sessions=sessions,
        stats=stats,
    )
    return HTMLResponse(html)


@router.get("/api/dcn/{dcn_name}/swipe/queue")
async def swipe_queue_api(dcn_name: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    queue = swipe_queue(dcn_name)
    return JSONResponse({"sessions": queue, "stats": swipe_stats(dcn_name)})


@router.post("/api/dcn/{dcn_name}/swipe/judge")
async def swipe_judge(dcn_name: str, sid: str, judgment: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    judgments = save_judgment(dcn_name, sid, judgment)
    return JSONResponse({"judgments": judgments, "stats": swipe_stats(dcn_name)})


@router.post("/api/dcn/{dcn_name}/swipe/undo")
async def swipe_undo(dcn_name: str, sid: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    judgments = remove_judgment(dcn_name, sid)
    return JSONResponse({"judgments": judgments, "stats": swipe_stats(dcn_name)})
