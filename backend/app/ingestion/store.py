"""Persisting normalised ingestion output."""

from __future__ import annotations

import logging
import re

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.base import utcnow
from app.ingestion.default_feeds import DOMAIN_ALIASES, canonical_domain, outlet_name_for
from app.ingestion.normalize import NormalizedArticle
from app.ingestion.providers.base import IngestionReport, RawPricePoint, RawReaction
from app.models import Article, MarketData, PublicReaction, Source

logger = logging.getLogger(__name__)

_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")


def get_or_create_source(
    session: Session, *, name: str, domain: str, source_type: str, is_demo: bool
) -> Source:
    domain = canonical_domain(domain)
    source = session.scalar(select(Source).where(Source.domain == domain))
    display_name = outlet_name_for(domain, name)
    if source is None:
        source = Source(
            name=display_name, domain=domain, source_type=source_type, is_demo=is_demo
        )
        session.add(source)
        session.flush()
        return source
    if display_name and source.name != display_name and not source.is_demo:
        source.name = display_name
    return source


def tidy_sources(session: Session) -> int:
    """Merge alias-domain sources into their outlet and repair stored names.

    Returns how many alias sources were merged away.
    """
    for source in session.scalars(select(Source).where(Source.is_demo.is_(False))).all():
        name = outlet_name_for(source.domain) or _TEMPLATE.sub("", source.name).strip()
        if name and name != source.name:
            source.name = name
    merged = 0
    for alias in session.scalars(select(Source).where(Source.domain.in_(DOMAIN_ALIASES))).all():
        canonical = get_or_create_source(
            session,
            name=alias.name,
            domain=alias.domain,
            source_type=alias.source_type,
            is_demo=alias.is_demo,
        )
        session.execute(
            update(Article).where(Article.source_id == alias.id).values(source_id=canonical.id)
        )
        session.delete(alias)
        merged += 1
    session.flush()
    return merged


def store_articles(session: Session, articles: list[NormalizedArticle]) -> IngestionReport:
    """Insert new articles, skipping ones already stored by URL or fingerprint."""
    report = IngestionReport(fetched=len(articles))
    for article in articles:
        existing = session.scalar(
            select(Article).where(Article.url == article.url)
        ) or session.scalar(
            select(Article).where(
                Article.content_hash == article.content_hash, Article.content_hash != ""
            )
        )
        if existing is not None:
            report.already_present += 1
            continue

        source = get_or_create_source(
            session,
            name=article.source_name,
            domain=article.source_domain,
            source_type=article.source_type,
            is_demo=article.is_demo,
        )
        session.add(
            Article(
                source_id=source.id,
                title=article.title,
                url=article.url,
                content=article.content,
                published_at=article.published_at,
                retrieved_at=utcnow(),
                content_hash=article.content_hash,
                ingest_provider=article.provider,
                is_demo=article.is_demo,
            )
        )
        report.stored += 1
    session.flush()
    return report


def store_reactions(
    session: Session, event_id: int, reactions: list[RawReaction]
) -> IngestionReport:
    report = IngestionReport(fetched=len(reactions))
    for reaction in reactions:
        existing = session.scalar(
            select(PublicReaction).where(
                PublicReaction.platform == reaction.platform,
                PublicReaction.external_id == reaction.external_id,
            )
        )
        if existing is not None:
            report.already_present += 1
            continue
        session.add(
            PublicReaction(
                event_id=event_id,
                platform=reaction.platform,
                external_id=reaction.external_id,
                content=reaction.content,
                published_at=reaction.published_at,
                engagement=reaction.engagement,
                url=reaction.url,
                community=reaction.community,
                is_demo=reaction.is_demo,
            )
        )
        report.stored += 1
    session.flush()
    return report


def store_market_points(
    session: Session, event_id: int, points: list[RawPricePoint]
) -> IngestionReport:
    report = IngestionReport(fetched=len(points))
    for point in points:
        existing = session.scalar(
            select(MarketData).where(
                MarketData.event_id == event_id,
                MarketData.symbol == point.symbol,
                MarketData.timestamp == point.timestamp,
            )
        )
        if existing is not None:
            report.already_present += 1
            continue
        session.add(
            MarketData(
                event_id=event_id,
                symbol=point.symbol,
                name=point.name,
                is_benchmark=point.is_benchmark,
                timestamp=point.timestamp,
                price=point.price,
                volume=point.volume,
                is_demo=point.is_demo,
            )
        )
        report.stored += 1
    session.flush()
    return report
