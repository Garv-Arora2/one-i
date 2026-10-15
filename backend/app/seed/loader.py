"""Loads the fictional demo dataset through the real ingestion and analysis
pipeline, then attaches demo public reaction and market data to the resulting
events.

Grouping, developments, coverage, numbers, wording and the crux are all
computed by the normal code paths, so the demo exercises the actual product
rather than pre-baked results.
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.pipeline import ingest_articles
from app.ingestion.providers.demo import (
    DemoMarketProvider,
    DemoNewsProvider,
    DemoReactionProvider,
    demo_hints_by_url,
)
from app.ingestion.store import store_market_points, store_reactions
from app.models import Article
from app.services.analysis_service import AnalysisReport, rebuild_dataset

logger = logging.getLogger(__name__)


@dataclass
class SeedReport:
    articles_stored: int = 0
    articles_already_present: int = 0
    duplicates: int = 0
    invalid: int = 0
    reactions_stored: int = 0
    market_points_stored: int = 0
    analysis: AnalysisReport = field(default_factory=AnalysisReport)


def event_ids_by_hint(session: Session) -> dict[str, int]:
    """Map each demo event hint to the event holding most of its articles."""
    hints = demo_hints_by_url()
    counts: dict[str, Counter[int]] = defaultdict(Counter)
    for article in session.scalars(select(Article).where(Article.is_demo.is_(True))):
        hint = hints.get(article.url)
        if hint and article.event_id:
            counts[hint][article.event_id] += 1
    return {hint: counter.most_common(1)[0][0] for hint, counter in counts.items() if counter}


def load_demo_data(session: Session) -> SeedReport:
    """Idempotent: running it twice does not duplicate rows."""
    report = SeedReport()

    ingestion = ingest_articles(session, [DemoNewsProvider()], limit_per_provider=500)
    report.articles_stored = ingestion.stored
    report.articles_already_present = ingestion.already_present
    report.duplicates = ingestion.duplicates
    report.invalid = ingestion.invalid

    report.analysis = rebuild_dataset(session, is_demo=True)

    events = event_ids_by_hint(session)
    if not events:
        logger.warning("No demo events were created; skipping reactions and market data.")
        return report

    reactions_by_hint: dict[str, list] = defaultdict(list)
    for hint, reaction in DemoReactionProvider().fetch_all_with_hints():
        reactions_by_hint[hint].append(reaction)
    for hint, reactions in reactions_by_hint.items():
        event_id = events.get(hint)
        if event_id is None:
            continue
        report.reactions_stored += store_reactions(session, event_id, reactions).stored

    points_by_hint: dict[str, list] = defaultdict(list)
    for hint, point in DemoMarketProvider().fetch_all_with_hints():
        points_by_hint[hint].append(point)
    for hint, points in points_by_hint.items():
        event_id = events.get(hint)
        if event_id is None:
            continue
        report.market_points_stored += store_market_points(session, event_id, points).stored

    return report
