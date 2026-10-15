"""Health and configuration endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import AppSettings, DbSession
from app.ingestion.registry import build_registry
from app.models import Article, Event

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    environment: str
    database_connected: bool
    events: int = 0
    articles: int = 0
    detail: str | None = None


class ProviderStatusOut(BaseModel):
    name: str
    kind: str
    configured: bool
    detail: str


class SystemStatusResponse(BaseModel):
    environment: str
    providers: list[ProviderStatusOut]
    demo_events: int
    live_events: int
    note: str


@router.get("/health", response_model=HealthResponse)
def health(session: DbSession, settings: AppSettings) -> HealthResponse:
    try:
        events = session.scalar(select(func.count()).select_from(Event)) or 0
        articles = session.scalar(select(func.count()).select_from(Article)) or 0
    except SQLAlchemyError as error:
        return HealthResponse(
            status="degraded",
            environment=settings.environment,
            database_connected=False,
            detail=f"Database unavailable: {error.__class__.__name__}",
        )
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        database_connected=True,
        events=events,
        articles=articles,
    )


@router.get("/status", response_model=SystemStatusResponse)
def system_status(session: DbSession, settings: AppSettings) -> SystemStatusResponse:
    demo = session.scalar(
        select(func.count()).select_from(Event).where(Event.is_demo.is_(True))
    ) or 0
    live = session.scalar(
        select(func.count()).select_from(Event).where(Event.is_demo.is_(False))
    ) or 0
    return SystemStatusResponse(
        environment=settings.environment,
        providers=[
            ProviderStatusOut(**status.__dict__) for status in build_registry(settings).statuses()
        ],
        demo_events=demo,
        live_events=live,
        note="Demo events contain fictional sample data and are stored separately from live data.",
    )
