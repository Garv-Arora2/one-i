"""Operational command line for ONE I.

    python -m app.cli migrate        apply database migrations
    python -m app.cli seed-demo      load the fictional demo dataset
    python -m app.cli ingest         fetch public RSS, enrich bodies, analyse
    python -m app.cli enrich         fetch full article text for thin live rows
    python -m app.cli analyze        rebuild stored analysis results
    python -m app.cli reactions      collect YouTube comments for live events
    python -m app.cli update         routine refresh (run daily): all of the above
    python -m app.cli providers      show which external services are configured
    python -m app.cli reset-demo     remove every demo row
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.session import session_scope
from app.ingestion.dedupe import deduplicate
from app.ingestion.enrich import enrich_articles
from app.ingestion.normalize import normalize_batch
from app.ingestion.pipeline import ingest_articles
from app.ingestion.providers.currentevents import CurrentEventsProvider
from app.ingestion.providers.gdelt import GdeltNewsProvider
from app.ingestion.registry import build_registry
from app.ingestion.store import store_articles, tidy_sources
from app.models import Article, Event, MarketData, PublicReaction, Source
from app.seed.loader import load_demo_data
from app.services.analysis_service import rebuild_dataset
from app.services.reaction_service import refresh_live_reactions

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


def cmd_migrate(_: argparse.Namespace) -> int:
    command.upgrade(_alembic_config(), "head")
    print(f"Database migrated: {get_settings().database_url}")
    return 0


def cmd_seed_demo(_: argparse.Namespace) -> int:
    with session_scope() as session:
        report = load_demo_data(session)
    print(
        "Demo dataset loaded (fictional sample data).\n"
        f"  articles stored: {report.articles_stored} "
        f"(already present: {report.articles_already_present}, "
        f"duplicates: {report.duplicates}, rejected: {report.invalid})\n"
        f"  events: {report.analysis.events}\n"
        f"  developments: {report.analysis.developments}\n"
        f"  coverage rows: {report.analysis.coverage_rows}\n"
        f"  number observations: {report.analysis.number_observations}\n"
        f"  wording observations: {report.analysis.wording_observations}\n"
        f"  public reactions: {report.reactions_stored}\n"
        f"  market points: {report.market_points_stored}"
    )
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    registry = build_registry()
    providers = registry.configured_news()
    if not providers:
        print(
            "No news provider is configured. Set RSS_FEEDS and/or NEWS_API_KEY, "
            "or run 'python -m app.cli seed-demo' for the fictional dataset."
        )
        return 1
    with session_scope() as session:
        report = ingest_articles(
            session, providers, query=args.query, limit_per_provider=args.limit
        )
    print(
        f"Fetched {report.fetched}, stored {report.stored}, "
        f"already present {report.already_present}, duplicates {report.duplicates}, "
        f"rejected {report.invalid}"
    )
    for error in report.errors:
        print(f"  provider error: {error}")
    if args.backfill_days and not args.query:
        _backfill_history(args.backfill_days, args.chunk_days, args.limit)
    if args.history_days and not args.query:
        _ingest_history(args.history_days)
    if not args.no_enrich:
        with session_scope() as session:
            enrichment = enrich_articles(session, is_demo=False, limit=max(args.limit * 2, 80))
        print(
            f"Enriched bodies: updated {enrichment.updated} of {enrichment.considered} "
            f"thin articles (page refused/failed {enrichment.failed}, "
            f"still thin {enrichment.skipped_thin_page}, "
            f"non-English {enrichment.skipped_non_english})"
        )
    if args.no_analyze:
        return 0
    with session_scope() as session:
        analysis = rebuild_dataset(session, is_demo=False)
    print(
        f"Analysed live dataset: {analysis.events} events, "
        f"{analysis.developments} developments, {analysis.coverage_rows} coverage rows, "
        f"{analysis.number_observations} number observations, "
        f"{analysis.wording_observations} wording observations"
    )
    _refresh_reactions(refresh=False)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    """The routine refresh: new reporting in, events re-analysed, comments added.

    Only events that clear the publication threshold (several outlets, enough
    shared developments) reach the front page, so a thinly reported story
    waits in storage until more outlets cover it.
    """
    from datetime import timedelta

    from app.db.base import utcnow
    from app.ingestion.enrich import scrub_repeated_sentences

    registry = build_registry()
    with session_scope() as session:
        report = ingest_articles(
            session, registry.configured_news(), limit_per_provider=args.limit
        )
    print(
        f"Fetched {report.fetched}, stored {report.stored} new "
        f"(already present {report.already_present}, rejected {report.invalid})"
    )
    for error in report.errors:
        print(f"  provider error: {error}")

    since = utcnow() - timedelta(days=args.days)
    with session_scope() as session:
        recent_ids = set(
            session.scalars(
                select(Article.id).where(
                    Article.is_demo.is_(False), Article.retrieved_at >= since
                )
            )
        )
    with session_scope() as session:
        enrichment = enrich_articles(session, is_demo=False, only_ids=recent_ids)
    print(
        f"Outlet text fetched for {enrichment.updated} of {enrichment.considered} new articles "
        f"(refused/failed {enrichment.failed})"
    )
    with session_scope() as session:
        _, removed = scrub_repeated_sentences(session, is_demo=False)
    if removed:
        print(f"Removed {removed} repeated site-navigation sentences")

    with session_scope() as session:
        tidy_sources(session)
        analysis = rebuild_dataset(session, is_demo=False)
    print(
        f"Published {analysis.events} events ({analysis.developments} developments, "
        f"{analysis.number_observations} figures, {analysis.wording_observations} quoted passages); "
        f"{len(analysis.skipped_events)} stories held back as too thinly reported"
    )
    _refresh_reactions(refresh=False)
    return 0


def _backfill_history(days: int, chunk_days: int, limit: int) -> None:
    """Walk backwards through GDELT week by week for well-reported stories.

    Recent feeds alone often carry only one outlet per story. Backfill tops
    the database up with earlier, multiply-reported coverage so the
    publication threshold has something to work with.
    """
    registry = build_registry()
    gdelt_providers = [
        provider
        for provider in registry.news
        if isinstance(provider, GdeltNewsProvider) and provider.is_configured()
    ]
    if not gdelt_providers:
        print("Backfill skipped: GDELT inlet is not enabled.")
        return
    provider = gdelt_providers[0]
    queries = provider.queries
    for start, end in provider.backfill_windows(days, chunk_days):
        for query in queries:
            try:
                raw = provider.fetch_range(query, start, end, limit=limit)
            except Exception as error:
                print(f"  backfill error ({query}): {error}")
                continue
            normalized, rejected = normalize_batch(raw)
            unique, duplicates = deduplicate(normalized)
            with session_scope() as session:
                stored = store_articles(session, unique)
            print(
                f"  backfill {start.date()}..{end.date()} [{query}]: "
                f"fetched {len(raw)}, stored {stored.stored}, "
                f"already present {stored.already_present}, "
                f"duplicates {len(duplicates)}, rejected {len(rejected)}"
            )


def _ingest_history(days: int) -> None:
    """Pull Wikipedia daily current-events archives back N days.

    Each cited source URL becomes a raw article, so well-reported stories
    arrive with several outlets attached — exactly what the homepage,
    coverage, number and wording comparisons need.
    """
    provider = CurrentEventsProvider(days=days)
    raw = provider.fetch_history(days)
    normalized, rejected = normalize_batch(raw)
    unique, duplicates = deduplicate(normalized)
    with session_scope() as session:
        stored = store_articles(session, unique)
    print(
        f"  history ({days} days): fetched {len(raw)}, stored {stored.stored}, "
        f"already present {stored.already_present}, "
        f"duplicates {len(duplicates)}, rejected {len(rejected)}"
    )


def cmd_repair_bodies(args: argparse.Namespace) -> int:
    from sqlalchemy import select

    from app.ingestion.enrich import enrich_articles, repair_chrome_bodies
    from app.models import Article

    with session_scope() as session:
        reset_ids = set(repair_chrome_bodies(session, is_demo=False))
        stub_ids = set(
            session.scalars(
                select(Article.id).where(
                    Article.is_demo == False,  # noqa: E712
                    Article.content == Article.title,
                )
            )
        )
    target = reset_ids | stub_ids
    print(
        f"Reset {len(reset_ids)} chrome-poisoned bodies; "
        f"{len(target)} title-only stubs to re-enrich"
    )
    if target and not args.no_enrich:
        with session_scope() as session:
            enrichment = enrich_articles(session, is_demo=False, only_ids=target)
        print(
            f"Re-enriched: updated {enrichment.updated} of {enrichment.considered} "
            f"(failed {enrichment.failed}, still thin {enrichment.skipped_thin_page}, "
            f"non-English {enrichment.skipped_non_english})"
        )
    return 0


def cmd_scrub_repeats(args: argparse.Namespace) -> int:
    from app.ingestion.enrich import scrub_repeated_sentences

    with session_scope() as session:
        changed, removed = scrub_repeated_sentences(session, is_demo=False)
    print(
        f"Scrubbed {removed} repeated sentences from {changed} bodies "
        f"(sentences seen in 3+ long bodies)"
    )
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    with session_scope() as session:
        enrichment = enrich_articles(session, is_demo=False, limit=args.limit)
    print(
        f"Enriched bodies: updated {enrichment.updated} of {enrichment.considered} "
        f"thin articles (page refused/failed {enrichment.failed}, "
        f"still thin {enrichment.skipped_thin_page}, "
        f"non-English {enrichment.skipped_non_english})"
    )
    if args.no_analyze:
        return 0
    with session_scope() as session:
        analysis = rebuild_dataset(session, is_demo=False)
    print(
        f"Analysed live dataset: {analysis.events} events, "
        f"{analysis.developments} developments, {analysis.coverage_rows} coverage rows, "
        f"{analysis.number_observations} number observations, "
        f"{analysis.wording_observations} wording observations"
    )
    _refresh_reactions(refresh=False)
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    with session_scope() as session:
        if not args.demo:
            tidy_sources(session)
        report = rebuild_dataset(session, is_demo=args.demo)
    dataset = "demo" if args.demo else "live"
    print(
        f"Analysed {dataset} dataset: {report.events} events, "
        f"{report.developments} developments, {report.coverage_rows} coverage rows, "
        f"{report.number_observations} number observations, "
        f"{report.wording_observations} wording observations"
    )
    if not args.demo:
        _refresh_reactions(refresh=False)
    return 0


def _refresh_reactions(refresh: bool, verbose: bool = False) -> None:
    providers = build_registry().configured_reactions()
    if not providers:
        print("Public reaction skipped: set YOUTUBE_API_KEY (and/or Reddit keys) to collect it.")
        return
    with session_scope() as session:
        report = refresh_live_reactions(session, providers, refresh=refresh)
    print(
        f"Public reaction: searched {report.events_searched} of {report.events_considered} "
        f"events (already collected {report.events_skipped}), stored {report.stored} comments"
    )
    if verbose:
        for event_id, query in report.queries.items():
            print(f"  event {event_id}: \"{query}\"")
    for error in report.errors:
        print(f"  reaction error: {error}")


def cmd_copy_db(args: argparse.Namespace) -> int:
    """Copy every row from one database into another (e.g. SQLite -> PostgreSQL).

    The target must already be migrated (DATABASE_URL=<target> python -m
    app.cli migrate) and empty, so nothing is silently merged or overwritten.
    """
    from sqlalchemy import create_engine, func, insert, text

    import app.models  # noqa: F401  (registers every table on Base.metadata)
    from app.db.base import Base

    source = create_engine(args.source, future=True)
    target = create_engine(args.target, future=True)
    tables = Base.metadata.sorted_tables
    with source.connect() as src, target.begin() as dst:
        occupied = [
            table.name
            for table in tables
            if dst.execute(select(func.count()).select_from(table)).scalar()
        ]
        if occupied:
            print(f"Target is not empty ({', '.join(occupied)}); nothing copied.")
            return 1
        for table in tables:
            rows = [dict(row) for row in src.execute(select(table)).mappings()]
            for start in range(0, len(rows), 1000):
                dst.execute(insert(table), rows[start : start + 1000])
            print(f"  {table.name}: {len(rows)} rows")
        if target.dialect.name == "postgresql":
            for table in tables:
                if "id" in table.c:
                    dst.execute(
                        text(
                            f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                            f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"
                        )
                    )
    print("Copy complete.")
    return 0


def cmd_reactions(args: argparse.Namespace) -> int:
    _refresh_reactions(refresh=args.refresh, verbose=True)
    return 0


def cmd_providers(_: argparse.Namespace) -> int:
    settings = get_settings()
    print(f"Environment: {settings.environment}")
    print(f"Database: {settings.database_url.split('@')[-1]}")
    for status in build_registry(settings).statuses():
        state = "configured" if status.configured else "not configured"
        print(f"  [{status.kind}] {status.name}: {state} - {status.detail}")
    print(
        f"  [auth] google: "
        f"{'configured' if settings.google_auth_configured else 'not configured'}"
    )
    print(
        f"  [auth] captcha ({settings.captcha_provider}): "
        f"{'configured' if settings.captcha_configured else 'not configured'}"
    )
    return 0


def cmd_reset_demo(_: argparse.Namespace) -> int:
    with session_scope() as session:
        event_ids = list(session.scalars(select(Event.id).where(Event.is_demo.is_(True))))
        if event_ids:
            session.execute(delete(PublicReaction).where(PublicReaction.event_id.in_(event_ids)))
            session.execute(delete(MarketData).where(MarketData.event_id.in_(event_ids)))
        session.execute(delete(Article).where(Article.is_demo.is_(True)))
        session.execute(delete(Event).where(Event.is_demo.is_(True)))
        session.execute(delete(Source).where(Source.is_demo.is_(True)))
    print("Demo rows removed.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="one-i", description=__doc__)
    parser.add_argument("--verbose", action="store_true", help="enable debug logging")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("migrate", help="apply database migrations").set_defaults(
        handler=cmd_migrate
    )
    subparsers.add_parser("seed-demo", help="load the fictional demo dataset").set_defaults(
        handler=cmd_seed_demo
    )
    subparsers.add_parser("providers", help="show external provider status").set_defaults(
        handler=cmd_providers
    )
    subparsers.add_parser("reset-demo", help="delete all demo rows").set_defaults(
        handler=cmd_reset_demo
    )

    ingest = subparsers.add_parser("ingest", help="run live news ingestion")
    ingest.add_argument("--query", default=None, help="optional search term")
    ingest.add_argument("--limit", type=int, default=120, help="articles per provider")
    ingest.add_argument(
        "--backfill-days",
        type=int,
        default=0,
        help="also walk back this many days through GDELT (weekly chunks) "
        "when recent news is too thinly reported; ignored with --query",
    )
    ingest.add_argument(
        "--chunk-days",
        type=int,
        default=7,
        help="days per backfill window",
    )
    ingest.add_argument(
        "--history-days",
        type=int,
        default=0,
        help="also pull Wikipedia daily current-events archives back this many "
        "days for multiply-reported world stories; ignored with --query",
    )
    ingest.add_argument(
        "--no-enrich",
        action="store_true",
        help="skip fetching full article bodies from each URL",
    )
    ingest.add_argument(
        "--no-analyze",
        action="store_true",
        help="store articles without regrouping live events",
    )
    ingest.set_defaults(handler=cmd_ingest)

    enrich = subparsers.add_parser(
        "enrich", help="fetch full article text for thin live rows, then analyse"
    )
    enrich.add_argument("--limit", type=int, default=200, help="articles to consider")
    enrich.add_argument(
        "--no-analyze",
        action="store_true",
        help="update bodies without regrouping live events",
    )
    enrich.set_defaults(handler=cmd_enrich)

    repair = subparsers.add_parser(
        "repair-bodies",
        help="reset site-chrome-poisoned bodies to stubs so enrich re-fetches them",
    )
    repair.add_argument(
        "--no-enrich",
        action="store_true",
        help="reset without re-fetching bodies",
    )
    repair.set_defaults(handler=cmd_repair_bodies)

    scrub = subparsers.add_parser(
        "scrub-repeats",
        help="remove outlet-rail sentences repeated across many bodies, then report",
    )
    scrub.set_defaults(handler=cmd_scrub_repeats)

    analyze = subparsers.add_parser("analyze", help="rebuild stored analysis results")
    group = analyze.add_mutually_exclusive_group()
    group.add_argument("--demo", dest="demo", action="store_true", help="analyse demo data")
    group.add_argument("--live", dest="demo", action="store_false", help="analyse live data")
    analyze.set_defaults(handler=cmd_analyze, demo=False)

    update = subparsers.add_parser(
        "update",
        help="routine refresh: fetch news, fetch outlet text, re-analyse, collect comments",
    )
    update.add_argument("--limit", type=int, default=120, help="articles per provider")
    update.add_argument(
        "--days",
        type=int,
        default=2,
        help="fetch outlet text for articles retrieved in the last N days",
    )
    update.set_defaults(handler=cmd_update)

    copy_db = subparsers.add_parser(
        "copy-db", help="copy all rows into an empty, migrated database (e.g. SQLite -> PostgreSQL)"
    )
    copy_db.add_argument("--source", required=True, help="SQLAlchemy URL to copy from")
    copy_db.add_argument("--target", required=True, help="SQLAlchemy URL to copy into")
    copy_db.set_defaults(handler=cmd_copy_db)

    reactions = subparsers.add_parser(
        "reactions",
        help="collect YouTube comments (and Reddit posts when configured) for live events",
    )
    reactions.add_argument(
        "--refresh",
        action="store_true",
        help="re-collect events that already have comments (uses more API quota)",
    )
    reactions.set_defaults(handler=cmd_reactions)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    # httpx logs full request URLs, which include API keys as query parameters.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return int(args.handler(args))


if __name__ == "__main__":
    sys.exit(main())
