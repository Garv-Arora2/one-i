import { Fragment } from "react";
import Link from "next/link";

import { CoverageFingerprint } from "@/components/CoverageFingerprint";
import { StoryImage } from "@/components/StoryImage";
import { api } from "@/lib/api";
import { formatCount, formatDateTime } from "@/lib/format";
import { MAX_PAGES, MIN_SOURCES, PAGE_SIZE } from "@/lib/publication";
import type { ArticleRef, EventDetail, EventSummary } from "@/lib/types";

import styles from "../front.module.css";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Today's coverage",
};

function eventLocation(event: EventSummary): string {
  return event.location ?? "NEWS";
}

function Meta({ event }: { event: EventSummary }) {
  return (
    <p className={styles.cardMeta}>
      <CoverageFingerprint sourceCount={event.source_count} label={false} />
      {" "}
      {formatCount(event.source_count)} sources · {formatCount(event.article_count)}{" "}
      articles · {formatDateTime(event.event_time)}
    </p>
  );
}

function LeadStory({ event }: { event: EventSummary }) {
  return (
    <article className={styles.leadMain}>
      <Link href={`/events/${event.slug}`} className={styles.imgLink}>
        <StoryImage event={event} size="hero" caption />
      </Link>
      <p className={styles.leadKicker}>{eventLocation(event)}</p>
      <h1 className={styles.leadTitle}>
        <Link href={`/events/${event.slug}`}>{event.title}</Link>
      </h1>
      {event.crux && <p className={styles.leadCrux}>{event.crux}</p>}
      <div className={styles.leadMeta}>
        <CoverageFingerprint sourceCount={event.source_count} />
        <span>
          <span className={styles.leadMetaStrong}>{formatCount(event.article_count)}</span>{" "}
          articles
        </span>
        <span>
          <span className={styles.leadMetaStrong}>{formatCount(event.development_count)}</span>{" "}
          developments
        </span>
        <span>{formatDateTime(event.event_time)}</span>
      </div>
    </article>
  );
}

function DualCard({ event }: { event: EventSummary }) {
  return (
    <article className={styles.dualCard}>
      <Link href={`/events/${event.slug}`} className={styles.imgLink}>
        <StoryImage event={event} size="medium" variant={1} caption />
      </Link>
      <p className={styles.cardKicker}>{eventLocation(event)}</p>
      <h2 className={styles.dualTitle}>
        <Link href={`/events/${event.slug}`}>{event.title}</Link>
      </h2>
      {event.crux && <p className={styles.dualCrux}>{event.crux}</p>}
      <Meta event={event} />
    </article>
  );
}

function CompactRow({ event }: { event: EventSummary }) {
  return (
    <article className={styles.compactRow}>
      <Link href={`/events/${event.slug}`} className={styles.imgLink}>
        <StoryImage event={event} size="thumb" variant={2} />
      </Link>
      <div>
        <span className={styles.cardKicker}>{eventLocation(event)}</span>
        <h3 className={styles.compactTitle}>
          <Link href={`/events/${event.slug}`}>{event.title}</Link>
        </h3>
        {event.crux && <p className={styles.compactStand}>{event.crux}</p>}
        <Meta event={event} />
      </div>
    </article>
  );
}

function ArticleRow({
  article,
  event,
  index,
}: {
  article: ArticleRef;
  event: EventSummary;
  index: number;
}) {  return (
    <article className={styles.articleRow}>
      <Link href={`/events/${event.slug}`} className={styles.imgLink}>
        <StoryImage event={event} size="thumb" variant={index + 3} />
      </Link>
      <div>
        <span className={styles.articleSource}>{article.source.name}</span>
        <h3 className={styles.articleHeadline}>
          <a href={article.url} target="_blank" rel="noreferrer noopener">
            {article.title}
          </a>
        </h3>
        <p className={styles.cardMeta}>
          {eventLocation(event)} · {formatDateTime(article.published_at)}
          {article.title_is_summary && " · Wikipedia’s summary of this report"}
          {" · "}
          <Link href={`/events/${event.slug}`}>Open event</Link>
        </p>
      </div>
    </article>
  );
}

function RankedList({  title,
  events,
}: {
  title: string;
  events: EventSummary[];
}) {
  if (events.length === 0) return null;
  return (
    <section className={styles.rankCol}>
      <h2 className={styles.zoneHead}>{title}</h2>
      <ol className={styles.rankList}>
        {events.map((event, i) => (
          <li key={event.id}>
            <span className={styles.rankNum}>{i + 1}</span>
            <div>
              <Link href={`/events/${event.slug}`}>{event.title}</Link>
              <Meta event={event} />
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/**
 * Outlets append their own brand to a shared wire headline
 * ("…failures | The Advocate", "…offer? - Grenada Chronicle"). Strip those
 * trailing brands so copies of one story collapse to one catalog row.
 */
function headlineKey(title: string): string {
  let key = title.toLowerCase().replace(/\s+/g, " ").trim();
  for (;;) {
    const parts = key.split(/\s+[|\-–—]\s+/);
    if (parts.length < 2) return key;
    const last = parts[parts.length - 1];
    if (last.length > 28 || /[.!?]$/.test(last)) return key;
    parts.pop();
    key = parts.join(" | ");
  }
}

const REPORTS_PER_EVENT = 3;

function Pager({
  page,
  pages,
  total,
  sort,
}: {
  page: number;
  pages: number;
  total: number;
  sort: string;
}) {
  if (pages <= 1) return null;
  const suffix = sort === "sources" ? "" : `&sort=${sort}`;
  const previous = page > 1 ? page - 1 : null;
  const next = page < pages ? page + 1 : null;
  return (
    <nav className={styles.pager} aria-label="Earlier coverage">
      {previous ? (
        <Link href={previous === 1 ? `/home?${suffix.replace(/^&/, "")}` : `/home?page=${previous}${suffix}`}>
          Previous
        </Link>
      ) : (
        <span>Previous</span>
      )}
      <span>
        Page {page} of {pages} · {formatCount(total)} widely reported
      </span>
      {next ? (
        <Link href={`/home?page=${next}${suffix}`}>Next</Link>
      ) : (
        <span>Next</span>
      )}
    </nav>
  );
}

const SORTS = [
  { value: "sources", label: "Most covered" },
  { value: "recent", label: "Most recent" },
  { value: "oldest", label: "Oldest first" },
] as const;

type SortValue = (typeof SORTS)[number]["value"];

function SortControl({ sort }: { sort: SortValue }) {
  return (
    <form className={styles.sortBar} aria-label="Sort events">
      <label htmlFor="sort">Sort</label>
      <select id="sort" name="sort" defaultValue={sort} key={sort}>
        {SORTS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <button type="submit">Apply</button>
    </form>
  );
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; sort?: string }>;
}) {
  const params = await searchParams;
  const requested = Number.parseInt(params.page ?? "1", 10);
  const page = Number.isFinite(requested)
    ? Math.min(MAX_PAGES, Math.max(1, requested))
    : 1;
  const offset = (page - 1) * PAGE_SIZE;
  const sort: SortValue = SORTS.some((option) => option.value === params.sort)
    ? (params.sort as SortValue)
    : "sources";

  const live = await api.events({
    limit: PAGE_SIZE,
    offset,
    dataset: "live",
    minSources: MIN_SOURCES,
    sort,
  });
  const demo =
    page === 1 && live && live.events.length === 0
      ? await api.events({
          limit: PAGE_SIZE,
          dataset: "demo",
          minSources: MIN_SOURCES,
          sort,
        })
      : null;
  const data = live && live.events.length > 0 ? live : demo;
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.min(MAX_PAGES, Math.ceil(total / PAGE_SIZE)));

  if (!data) {
    return (
      <div className={styles.front}>
        <div className={styles.empty}>
          <p className="note">
            The ONE I API is not responding. Start it with{" "}
            <code>python -m uvicorn app.main:app --reload</code> from the{" "}
            <code>backend</code> folder and reload this page.
          </p>
        </div>
      </div>
    );
  }

  if (data.events.length === 0) {
    return (
      <div className={styles.front}>
        <div className={styles.empty}>
          <p className="note">
            No widely reported events yet. ONE I only publishes a story when
            several outlets have covered it with enough shared detail to
            compare. Run <code>python -m app.cli ingest</code> from the{" "}
            <code>backend</code> folder — adding{" "}
            <code>--backfill-days 30</code> walks back through earlier,
            better-reported coverage — or load the sample dataset with{" "}
            <code>python -m app.cli seed-demo</code>.
          </p>
        </div>
      </div>
    );
  }

  const details = (
    await Promise.all(data.events.map((event) => api.event(event.slug)))
  ).filter((d): d is EventDetail => d !== null);

  const [lead, ...rest] = data.events;
  const dual = rest.length > 2 ? rest.slice(0, 2) : [];
  const compact = rest.length > 2 ? rest.slice(2) : [];
  const latest = rest;
  // Original reports: one row per distinct headline per event (syndicated
  // copies collapse), capped per event with a link to the rest.
  const bySlug = new Map(details.map((detail) => [detail.slug, detail]));
  const reportGroups = data.events.flatMap((summary, eventIndex) => {
    const detail = bySlug.get(summary.slug);
    if (!detail) return [];
    const seen = new Set<string>();
    const unique = detail.articles.filter((article) => {
      const key = headlineKey(article.title);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    return [
      {
        summary,
        shown: unique.slice(0, REPORTS_PER_EVENT).map((article, index) => ({
          article,
          index: eventIndex + index,
        })),
        hidden: unique.length - REPORTS_PER_EVENT,
      },
    ];
  });
  const articleCount = reportGroups.reduce((n, g) => n + g.shown.length, 0);

  const mostCovered = [...data.events].sort(
    (a, b) => b.source_count - a.source_count || b.article_count - a.article_count,
  );
  const withReaction = data.events.filter((e) => e.has_reactions);

  return (
    <div className={styles.front}>
      <div className={styles.dateBar}>
        <span>
          {new Date().toLocaleDateString("en-GB", {
            weekday: "long",
            day: "numeric",
            month: "long",
            year: "numeric",
            timeZone: "UTC",
          })}
        </span>
        <span>
          {formatCount(data.total)} widely reported · {formatCount(articleCount)}{" "}
          original reports
        </span>
      </div>
      <p className={styles.zoneLead}>
        Only stories several outlets reported with enough shared detail to
        compare — timeline, coverage and wording all need it. ONE I keeps
        about four pages of that run.
      </p>
      <SortControl sort={sort} />

      {/* 1. Lead + latest */}
      <div className={styles.leadRow}>
        <LeadStory event={lead} />
        <aside className={styles.latest}>
          <h2 className={styles.latestHead}>Latest</h2>
          {(latest.length > 0 ? latest : []).slice(0, 8).map((event) => (
            <CompactRow key={event.id} event={event} />
          ))}
        </aside>
      </div>

      {/* 2. Two-up medium */}
      {dual.length > 0 && (
        <section className={styles.zone}>
          <h2 className={styles.zoneHead}>Also leading</h2>
          <div className={styles.dual}>
            {dual.map((event) => (
              <DualCard key={event.id} event={event} />
            ))}
          </div>
        </section>
      )}

      {/* 3. Compact remainder */}
      {compact.length > 0 && (
        <section className={styles.zone}>
          <h2 className={styles.zoneHead}>More events</h2>
          <div className={styles.compactGrid}>
            {compact.map((event) => (
              <CompactRow key={event.id} event={event} />
            ))}
          </div>
        </section>
      )}

      {/* 4. Original reports catalog */}
      {reportGroups.length > 0 && (
        <section className={styles.zone}>
          <h2 className={styles.zoneHead}>Original reports</h2>
          <details className={styles.reportsToggle}>
          <summary>
            Show {formatCount(articleCount)} headlines as they ran
          </summary>
          <p className={styles.zoneLead}>
            Grouped from the events ONE I is examining. Thumbnails are related
            images, not photographs of the scene.
          </p>
          <div className={styles.articleGrid}>
            {reportGroups.map(({ summary, shown, hidden }) => (
              <Fragment key={summary.id}>
                {shown.map(({ article, index }) => (
                  <ArticleRow
                    key={article.id}
                    article={article}
                    event={summary}
                    index={index}
                  />
                ))}
                {hidden > 0 && (
                  <p className={styles.cardMeta}>
                    <Link href={`/events/${summary.slug}`}>
                      All {hidden + shown.length} original reports on this event →
                    </Link>
                  </p>
                )}
              </Fragment>
            ))}
          </div>
          </details>
        </section>
      )}

      {/* 5. Ranked catalogs */}
      <div className={styles.rankRow}>
        <RankedList title="Most covered" events={mostCovered} />
        <RankedList title="Public discussion" events={withReaction} />
      </div>

      <Pager page={page} pages={pages} total={total} sort={sort} />
    </div>
  );
}
