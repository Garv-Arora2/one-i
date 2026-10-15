"""Event endpoints.

Every response is assembled from stored analysis results.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Path, Query, status

from app.api.deps import DbSession
from app.schemas.events import (
    ComparisonsResponse,
    CoverageResponse,
    EventDetail,
    EventListResponse,
    MarketResponse,
    ReactionsResponse,
    TimelineResponse,
)
from app.services import event_service

router = APIRouter(prefix="/events", tags=["events"])

EventRef = Path(description="Event id or slug", min_length=1, max_length=220)


def _load(session, reference: str):
    event = event_service.get_event(session, reference)
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"No event found for '{reference}'."
        )
    return event


@router.get("", response_model=EventListResponse)
def list_events(
    session: DbSession,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    dataset: Literal["all", "demo", "live"] = Query("all"),
    min_sources: int = Query(
        2, ge=1, le=20, description="Minimum distinct outlets before an event is listed."
    ),
    sort: Literal["sources", "recent", "oldest"] = Query(
        "sources", description="Front-page ordering."
    ),
) -> EventListResponse:
    events, total = event_service.list_events(
        session, dataset=dataset, limit=limit, offset=offset, min_sources=min_sources,
        sort=sort,
    )
    return EventListResponse(events=events, total=total)


@router.get("/{event_ref}", response_model=EventDetail)
def get_event(session: DbSession, event_ref: str = EventRef) -> EventDetail:
    return event_service.build_event_detail(session, _load(session, event_ref))


@router.get("/{event_ref}/timeline", response_model=TimelineResponse)
def get_timeline(session: DbSession, event_ref: str = EventRef) -> TimelineResponse:
    return event_service.build_timeline(session, _load(session, event_ref))


@router.get("/{event_ref}/coverage", response_model=CoverageResponse)
def get_coverage(session: DbSession, event_ref: str = EventRef) -> CoverageResponse:
    return event_service.build_coverage(session, _load(session, event_ref))


@router.get("/{event_ref}/comparisons", response_model=ComparisonsResponse)
def get_comparisons(session: DbSession, event_ref: str = EventRef) -> ComparisonsResponse:
    return event_service.build_comparisons(session, _load(session, event_ref))


@router.get("/{event_ref}/reactions", response_model=ReactionsResponse)
def get_reactions(session: DbSession, event_ref: str = EventRef) -> ReactionsResponse:
    return event_service.build_reactions(session, _load(session, event_ref))


@router.get("/{event_ref}/market", response_model=MarketResponse)
def get_market(session: DbSession, event_ref: str = EventRef) -> MarketResponse:
    return event_service.build_market(session, _load(session, event_ref))
