"""Swipe mode routes — per-plot Tinder-like swipe review of gaze plots."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..templating import render
from ..services.dcn import get_dcn
from ..services.swipe import (
    swipe_data,
    swipe_stats,
    save_plot_judgment,
    remove_plot_judgment,
    save_plot_comment,
)

router = APIRouter()


@router.get("/dcn/{dcn_name}/swipe")
async def swipe_page(request: Request, dcn_name: str, session: str = ""):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    data = swipe_data(dcn_name)
    html = render(
        "dcn/swipe.html",
        request=request,
        dcn=dcn,
        sessions=data["sessions"],
        stats=data["stats"],
        start_sid=session,
    )
    return HTMLResponse(html)


@router.get("/api/dcn/{dcn_name}/swipe/queue")
async def swipe_queue_api(dcn_name: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    data = swipe_data(dcn_name)
    return JSONResponse(data)


@router.post("/api/dcn/{dcn_name}/swipe/judge")
async def swipe_judge(dcn_name: str, sid: str, plot: str, judgment: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    data = save_plot_judgment(dcn_name, sid, plot, judgment)
    return JSONResponse({"stats": swipe_stats(dcn_name)})


@router.post("/api/dcn/{dcn_name}/swipe/undo")
async def swipe_undo(dcn_name: str, sid: str, plot: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    data = remove_plot_judgment(dcn_name, sid, plot)
    return JSONResponse({"stats": swipe_stats(dcn_name)})


@router.post("/api/dcn/{dcn_name}/swipe/comment")
async def swipe_comment(dcn_name: str, sid: str, plot: str, comment: str = ""):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    data = save_plot_comment(dcn_name, sid, plot, comment)
    return JSONResponse({"stats": swipe_stats(dcn_name)})
