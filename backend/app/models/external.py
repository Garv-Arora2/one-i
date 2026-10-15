"""External context attached to an event: public reaction and market data."""

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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class PublicReaction(Base, TimestampMixin):
    """A public post or comment discussing an event.

    Public discussion is supplementary context, never factual authority.
    """

    __tablename__ = "public_reactions"
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_reaction_platform_external"),
        Index("ix_public_reactions_event_platform", "event_id", "platform"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    engagement: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    url: Mapped[str | None] = mapped_column(String(1000))
    # Community/channel name only. No personal account information is stored.
    community: Mapped[str | None] = mapped_column(String(200))
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MarketData(Base, TimestampMixin):
    """A price/volume observation for a security related to an event."""

    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("event_id", "symbol", "timestamp", name="uq_market_point"),
        Index("ix_market_data_event_symbol", "event_id", "symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(
        ForeignKey("events.id", ondelete="CASCADE"), nullable=False
    )
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200))
    is_benchmark: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[float | None] = mapped_column(Float)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
