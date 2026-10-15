"""Stored analysis results.

These rows are produced by the analysis pipeline before a user opens an event,
so that page requests only read stored results (see docs/architecture.md).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class Development(Base, TimestampMixin):
    """A meaningful, chronologically placed step within an event."""

    __tablename__ = "developments"
    __table_args__ = (Index("ix_developments_event_time", "event_id", "occurred_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # 0..1, derived from how many distinct sources and articles support it.
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    supporting_article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    supporting_source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    keywords: Mapped[list | None] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    coverage: Mapped[list["Coverage"]] = relationship(
        back_populates="development", cascade="all, delete-orphan"
    )


class Coverage(Base, TimestampMixin):
    """Whether one article reports one development."""

    __tablename__ = "coverage"
    __table_args__ = (
        UniqueConstraint("development_id", "article_id", name="uq_coverage_pair"),
        Index("ix_coverage_article", "article_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    development_id: Mapped[int] = mapped_column(
        ForeignKey("developments.id", ondelete="CASCADE"), nullable=False
    )
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    similarity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # The shared terms that produced the decision, shown to the reader.
    matched_terms: Mapped[list | None] = mapped_column(JSON)

    development: Mapped["Development"] = relationship(back_populates="coverage")


class NumberObservation(Base, TimestampMixin):
    """One numerical claim as reported by one article."""

    __tablename__ = "number_observations"
    __table_args__ = (
        Index("ix_number_observations_article", "article_id"),
        Index("ix_number_observations_group", "event_id", "comparison_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    development_id: Mapped[int | None] = mapped_column(
        ForeignKey("developments.id", ondelete="SET NULL")
    )
    # Human-readable subject, e.g. "people evacuated".
    description: Mapped[str] = mapped_column(String(300), nullable=False)
    reported_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str | None] = mapped_column(String(60))
    value_kind: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    time_period: Mapped[str | None] = mapped_column(String(120))
    # Original sentence, preserved verbatim.
    context: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Only observations sharing this key may be compared.
    comparison_key: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class WordingObservation(Base, TimestampMixin):
    """How one article described a development, preserved verbatim."""

    __tablename__ = "wording_observations"
    __table_args__ = (
        Index("ix_wording_observations_article", "article_id"),
        Index("ix_wording_observations_group", "event_id", "topic"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    development_id: Mapped[int | None] = mapped_column(
        ForeignKey("developments.id", ondelete="SET NULL")
    )
    topic: Mapped[str] = mapped_column(String(300), nullable=False)
    quoted_text: Mapped[str] = mapped_column(Text, nullable=False)
    # Surrounding sentences, so a quote is never shown without its context.
    surrounding_text: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(String(400))
    # Which aspects differ: responsibility / action / severity / certainty / evaluation.
    aspects: Mapped[list | None] = mapped_column(JSON)
    # The exact words that triggered each aspect, for transparency.
    markers: Mapped[dict | None] = mapped_column(JSON)
