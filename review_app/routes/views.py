"""One-page collection views and detail pages."""

from __future__ import annotations

import math
from pathlib import Path
from urllib.parse import quote, urlencode

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from ..config import RAW_DATA_DIR
from ..services import codebook_store
from ..services.codebook import VIEW_IDS, Codebook
from ..services.preflight import run_pipeline_preflight
from ..services.review import load_review
from ..services.filters import ViewFilter, apply_filters, parse_filters, search_rows
from ..services.view_data import (
    ViewRow,
    dataset_overview_path,
    find_row,
    load_dataset_overview,
    load_view_rows,
    load_session_overviews,
    related_rows,
)
from ..templating import render

router = APIRouter()

VIEW_TITLES = {
    "dataset": "Dataset",
    "session": "Session",
    "trial": "Trial",
    "participant": "Participant",
    "item": "Item",
}

PAGE_SIZES = {
    "dataset": 10,
    "session": 25,
    "trial": 100,
    "participant": 100,
    "item": 100,
}


def _quote(value: str) -> str:
    return quote(str(value), safe="")


def row_url(dcn_name: str, row: ViewRow) -> str:
    if row.view == "session":
        return f"/dcn/{_quote(dcn_name)}/session/{_quote(row.source_key or row.key)}"
    if row.view == "trial":
        session = row.parents.get("session", "")
        return f"/dcn/{_quote(dcn_name)}/trial/{_quote(session)}/{_quote(row.key)}"
    if row.view == "participant":
        return f"/dcn/{_quote(dcn_name)}/participant/{_quote(row.key)}"
    if row.view == "item":
        return f"/dcn/{_quote(dcn_name)}/item/{_quote(row.key)}"
    return ""


def _row_url_with_return(dcn_name: str, row: ViewRow, return_to: str) -> str:
    url = row_url(dcn_name, row)
    if not url:
        return ""
    return f"{url}?return={quote(return_to, safe='')}"


def _resolve_view(view_id: str) -> str:
    return view_id if view_id in VIEW_IDS else "dataset"


def _resolve_group(codebook: Codebook, view_id: str, requested: str | None) -> str:
    groups = codebook.group_ids_for_view(view_id)
    if requested in groups:
        return requested or ""
    return codebook.best_group_for_view(view_id)


def _query_url(
    dcn_name: str,
    view_id: str,
    group_id: str,
    query: str,
    filters: list[ViewFilter],
    page: int,
) -> str:
    params: list[tuple[str, str]] = []
    if group_id:
        params.append(("group", group_id))
    if query:
        params.append(("q", query))
    for view_filter in filters:
        params.append(("f", view_filter.to_query()))
    if page > 1:
        params.append(("page", str(page)))
    suffix = f"?{urlencode(params)}" if params else ""
    return f"/dcn/{_quote(dcn_name)}/view/{view_id}{suffix}"


def _collection_context(
    dcn_name: str,
    view_id: str,
    group_id: str | None,
    query: str,
    filters: list[ViewFilter],
    page: int,
    include_preflight: bool = False,
) -> dict:
    dcn_path = codebook_store.dcn_path(dcn_name)
    raw_path = RAW_DATA_DIR / dcn_name
    if not dcn_path.exists() and not raw_path.exists():
        raise HTTPException(status_code=404, detail=f"Collection '{dcn_name}' not found")

    codebook = codebook_store.dcn_codebook(dcn_name)
    availability = codebook_store.availability(dcn_name, codebook)
    view_id = _resolve_view(view_id)
    group_id = _resolve_group(codebook, view_id, group_id)

    rows = load_view_rows(dcn_path, view_id, codebook)
    rows = search_rows(rows, query, codebook)
    rows = apply_filters(rows, filters, codebook, dcn_path)

    page_size = PAGE_SIZES.get(view_id, 50)
    total = len(rows)
    page_count = max(1, math.ceil(total / page_size))
    page = min(max(1, page), page_count)
    start = (page - 1) * page_size
    page_rows = rows[start : start + page_size]

    group_options = [
        {
            "group_id": gid,
            "label": codebook.groups[gid].label,
            "selected": gid == group_id,
        }
        for gid in codebook.group_ids_for_view(view_id)
    ]
    current_url = _query_url(dcn_name, view_id, group_id, query, filters, page)
    columns = codebook.columns_for(view_id, group_id)
    filter_fields = codebook.fields_for_view(view_id)
    dataset_overview = load_dataset_overview(dcn_path)
    reviews = {}
    if view_id == "session":
        for row in page_rows:
            reviews[row.key] = load_review(dcn_name, row.source_key or row.key)
    is_processed = bool(load_session_overviews(dcn_path)) or dataset_overview_path(dcn_path).exists()
    preflight = None
    preflight_status = "unknown"
    if include_preflight and (RAW_DATA_DIR / dcn_name).exists():
        preflight = run_pipeline_preflight(dcn_name)
        raw_status = preflight.get("status", "pass")
        preflight_status = "fail" if raw_status == "error" else raw_status

    return {
        "dcn_name": dcn_name,
        "dcn_path": dcn_path,
        "view_id": view_id,
        "view_title": VIEW_TITLES[view_id],
        "view_tabs": [
            {
                "view_id": candidate,
                "title": VIEW_TITLES[candidate],
                "active": candidate == view_id,
                "href": _query_url(
                    dcn_name, candidate, group_id, query, filters, 1
                ),
            }
            for candidate in VIEW_IDS
        ],
        "group_id": group_id,
        "group_options": group_options,
        "columns": columns,
        "rows": page_rows,
        "reviews": reviews,
        "row_url": lambda row: _row_url_with_return(dcn_name, row, current_url),
        "total": total,
        "page": page,
        "page_count": page_count,
        "page_size": page_size,
        "start": start,
        "query": query,
        "filters": filters,
        "filter_fields": filter_fields,
        "availability": availability,
        "codebook": codebook,
        "dataset_overview": dataset_overview,
        "is_processed": is_processed,
        "preflight": preflight,
        "preflight_status": preflight_status,
        "codebook_status": codebook_store.codebook_status(dcn_name),
        "previous_url": _query_url(
            dcn_name, view_id, group_id, query, filters, page - 1
        )
        if page > 1
        else "",
        "next_url": _query_url(
            dcn_name, view_id, group_id, query, filters, page + 1
        )
        if page < page_count
        else "",
        "table_url": f"/dcn/{_quote(dcn_name)}/view/{view_id}/table",
    }


def _request_filters(request: Request) -> list[ViewFilter]:
    return parse_filters(request.query_params.getlist("f"))


@router.get("/dcn/{dcn_name}", response_class=HTMLResponse)
async def collection_page(
    request: Request,
    dcn_name: str,
    view: str = "dataset",
    group: str | None = None,
    q: str = "",
    page: int = 1,
):
    filters = _request_filters(request)
    context = _collection_context(
        dcn_name, view, group, q, filters, page, include_preflight=True
    )
    html = render(
        "views/page.html",
        request=request,
        **context,
    )
    return HTMLResponse(html)


@router.get("/dcn/{dcn_name}/view/{view_id}", response_class=HTMLResponse)
async def collection_view_page(
    request: Request,
    dcn_name: str,
    view_id: str,
    group: str | None = None,
    q: str = "",
    page: int = 1,
):
    filters = _request_filters(request)
    context = _collection_context(
        dcn_name, view_id, group, q, filters, page, include_preflight=True
    )
    html = render(
        "views/page.html",
        request=request,
        **context,
    )
    return HTMLResponse(html)


@router.get("/dcn/{dcn_name}/view/{view_id}/table", response_class=HTMLResponse)
async def collection_table(
    request: Request,
    dcn_name: str,
    view_id: str,
    group: str | None = None,
    q: str = "",
    page: int = 1,
):
    filters = _request_filters(request)
    context = _collection_context(dcn_name, view_id, group, q, filters, page)
    html = render(
        "views/_table.html",
        request=request,
        **context,
    )
    return HTMLResponse(html)


def _detail_context(
    dcn_name: str,
    view_id: str,
    key: str,
    session_key: str | None = None,
    return_to: str = "",
):
    dcn_path = codebook_store.dcn_path(dcn_name)
    if not dcn_path.exists():
        raise HTTPException(status_code=404, detail=f"Collection '{dcn_name}' not found")
    codebook = codebook_store.dcn_codebook(dcn_name)
    availability = codebook_store.availability(dcn_name, codebook)
    row = find_row(dcn_path, view_id, key, codebook, session_key=session_key)
    if row is None:
        raise HTTPException(status_code=404, detail=f"{view_id} '{key}' not found")

    sections: dict[str, list[dict]] = {}
    for field_obj in codebook.fields_for_view(view_id):
        category = codebook.categories.get(field_obj.semantic_category, {})
        category_label = category.get("label") or field_obj.semantic_category or "Other"
        sections.setdefault(category_label, []).append(
            {
                "field": field_obj,
                "value": row.value(field_obj.variable_id),
                "availability": availability.get(field_obj.variable_id),
            }
        )
    for items in sections.values():
        items.sort(key=lambda item: item["field"].feature_label.lower())

    related = _related_rows_for_detail(dcn_path, row, codebook)
    return {
        "dcn_name": dcn_name,
        "view_id": view_id,
        "view_title": VIEW_TITLES[view_id],
        "row": row,
        "sections": dict(sorted(sections.items())),
        "related": related,
        "return_to": return_to,
        "codebook_status": codebook_store.codebook_status(dcn_name),
        "codebook": codebook,
        "availability": availability,
    }


def _related_rows_for_detail(dcn_path: Path, row: ViewRow, codebook: Codebook) -> list[dict]:
    result = []
    seen = set()
    for target_view in VIEW_IDS:
        if target_view == row.view:
            continue
        for candidate in related_rows(dcn_path, row, target_view, codebook):
            identity = (candidate.view, candidate.key, candidate.parents.get("session", ""))
            if identity in seen:
                continue
            seen.add(identity)
            label = candidate.key
            if candidate.view == "trial":
                label = f"{candidate.key} · {candidate.parents.get('session', '')}"
            result.append(
                {
                    "view": candidate.view,
                    "title": VIEW_TITLES[candidate.view],
                    "key": label,
                    "url": row_url(dcn_path.name, candidate),
                }
            )
    return result[:60]


@router.get("/dcn/{dcn_name}/trial/{session_key}/{trial_id}", response_class=HTMLResponse)
async def trial_detail(
    request: Request,
    dcn_name: str,
    session_key: str,
    trial_id: str,
):
    context = _detail_context(
        dcn_name,
        "trial",
        trial_id,
        session_key=session_key,
        return_to=request.query_params.get("return", ""),
    )
    html = render("views/detail.html", request=request, **context)
    return HTMLResponse(html)


@router.get("/dcn/{dcn_name}/participant/{participant_id}", response_class=HTMLResponse)
async def participant_detail(
    request: Request,
    dcn_name: str,
    participant_id: str,
):
    context = _detail_context(
        dcn_name,
        "participant",
        participant_id,
        return_to=request.query_params.get("return", ""),
    )
    html = render("views/detail.html", request=request, **context)
    return HTMLResponse(html)


@router.get("/dcn/{dcn_name}/item/{text_id:path}", response_class=HTMLResponse)
async def item_detail(
    request: Request,
    dcn_name: str,
    text_id: str,
):
    context = _detail_context(
        dcn_name,
        "item",
        text_id,
        return_to=request.query_params.get("return", ""),
    )
    html = render("views/detail.html", request=request, **context)
    return HTMLResponse(html)
