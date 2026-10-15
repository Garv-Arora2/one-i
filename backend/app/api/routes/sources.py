"""Source endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, status

from app.api.deps import DbSession
from app.models import Source
from app.schemas.sources import SourceDetail, SourceListResponse
from app.services import event_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=SourceListResponse)
def list_sources(session: DbSession) -> SourceListResponse:
    sources = event_service.list_sources(session)
    return SourceListResponse(sources=sources, total=len(sources))


@router.get("/{source_id}", response_model=SourceDetail)
def get_source(session: DbSession, source_id: int = Path(ge=1)) -> SourceDetail:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No source with id {source_id}."
        )
    return event_service.build_source_detail(session, source)
