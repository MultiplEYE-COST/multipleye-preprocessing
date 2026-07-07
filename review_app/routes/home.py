"""Home page — list all data collections."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..templating import render
from ..config import PREPROCESSED_DATA_DIR
from ..services.dcn import list_dcns


router = APIRouter()


@router.get("/")
async def home(request: Request):
    dcns = list_dcns()
    html = render(
        "home.html",
        request=request,
        dcns=dcns,
        preprocessed_dir=str(PREPROCESSED_DATA_DIR),
        now="",
    )
    return HTMLResponse(html)
