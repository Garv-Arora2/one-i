"""Core domain tables: users, sources, events, articles.

ONE I is event-centric: the Event is the central object and articles from many
sources attach to it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, utcnow


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Source(Base, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_is_demo", "is_demo"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    domain: Mapped[str] = mapped_column(String(253), unique=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="news_outlet")
    # Demo rows are fictional sample data and are never mixed with live data.
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    articles: Mapped[list["Article"]] = relationship(back_populates="source")


class Event(Base, TimestampMixin):
    __tablename__ = "events"
    __table_args__ = (
        Index("ix_events_event_time", "event_time"),
        Index("ix_events_is_demo", "is_demo"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(220), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(400), nullable=False)
    # Deterministically generated from stored event data (see docs/specs/crux.md).
    crux: Mapped[str | None] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(Text)
    # Structured crux/context parts, each carrying the article ids it came from.
    crux_data: Mapped[dict | None] = mapped_column(JSON)
    event_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(String(200))
    last_analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    articles: Mapped[list["Article"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class Article(Base, TimestampMixin):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("url", name="uq_articles_url"),
        Index("ix_articles_event_published", "event_id", "published_at"),
        Index("ix_articles_content_hash", "content_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL"), index=True
    )
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(600), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    # Normalized fingerprint of title + body, used for duplicate detection.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    ingest_provider: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Similarity of this article to its event centroid, kept for explainability.
    grouping_score: Mapped[float | None] = mapped_column(Float)

    event: Mapped["Event | None"] = relationship(back_populates="articles")
    source: Mapped["Source"] = relationship(back_populates="articles")
