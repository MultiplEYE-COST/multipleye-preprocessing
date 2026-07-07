"""Home page routes — list all data collections."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..services.dcn import list_dcns


router = APIRouter()


@router.get("/")
async def home() -> JSONResponse:
    """List all data collections with review progress.

    Returns JSON for now (templates will be added in Phase 3).
    """
    dcns = list_dcns()
    return JSONResponse([d.model_dump() for d in dcns])
