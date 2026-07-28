"""Swipe mode routes — per-plot Tinder-like swipe review of gaze plots."""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from ..templating import render
from ..services.dcn import get_dcn
from ..services.swipe import (
    swipe_data,
    swipe_stats,
    save_plot_judgment as _save_plot_judgment_sync,
    remove_plot_judgment as _remove_plot_judgment_sync,
    save_plot_comment as _save_plot_comment_sync,
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
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, _save_plot_judgment_sync, dcn_name, sid, plot, judgment
    )
    stats = await loop.run_in_executor(None, swipe_stats, dcn_name)
    return JSONResponse({"stats": stats})


@router.post("/api/dcn/{dcn_name}/swipe/undo")
async def swipe_undo(dcn_name: str, sid: str, plot: str):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _remove_plot_judgment_sync, dcn_name, sid, plot)
    stats = await loop.run_in_executor(None, swipe_stats, dcn_name)
    return JSONResponse({"stats": stats})


@router.post("/api/dcn/{dcn_name}/swipe/comment")
async def swipe_comment(dcn_name: str, sid: str, plot: str, comment: str = ""):
    dcn = get_dcn(dcn_name)
    if dcn is None:
        raise HTTPException(status_code=404, detail=f"DCN '{dcn_name}' not found")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, _save_plot_comment_sync, dcn_name, sid, plot, comment
    )
    stats = await loop.run_in_executor(None, swipe_stats, dcn_name)
    return JSONResponse({"stats": stats})
