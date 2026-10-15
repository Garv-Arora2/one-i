"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import auth, events, health, sources
from app.core.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
# httpx logs full request URLs, which include API keys as query parameters.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

settings = get_settings()

app = FastAPI(
    title="ONE I API",
    description=(
        "Event-centric news analysis. Responses present stored evidence and measured "
        "differences; they never contain scores or judgements about outlets."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(events.router)
app.include_router(sources.router)
app.include_router(auth.router)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "The request could not be validated.", "errors": error.errors()},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_: Request, error: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error", exc_info=error)
    return JSONResponse(
        status_code=503,
        content={"detail": "The database is currently unavailable."},
    )


@app.get("/", tags=["system"])
def root() -> dict:
    return {
        "name": "ONE I API",
        "docs": "/docs",
        "principle": "Show the difference. Let the user decide.",
    }
