import Link from "next/link";
import { notFound } from "next/navigation";

import { CoverageMatrix } from "@/components/CoverageMatrix";
import { CoveragePoll } from "@/components/CoveragePoll";
import { CoverageRatio } from "@/components/CoverageRatio";
import { CoverageScore } from "@/components/CoverageScore";
import { MissedFacts } from "@/components/MissedFacts";
import { NumberComparisons } from "@/components/NumberComparisons";
import { Notice } from "@/components/Notice";
import { ProgressRail, type RailStop } from "@/components/ProgressRail";
import { ReactionPanel } from "@/components/ReactionPanel";
import { Disclosure, Section } from "@/components/Section";
import { StoryImage } from "@/components/StoryImage";
import { Timeline } from "@/components/Timeline";
import { WordingComparisons } from "@/components/WordingComparisons";
import { api } from "@/lib/api";
import { cruxBulletItems } from "@/lib/cruxBullets";
import { formatCount, formatDate, formatDateTime, formatShare } from "@/lib/format";

import styles from "./event.module.css";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const event = await api.event(slug);
  return {
    title: event ? event.title : "Event",
    description: event?.crux ?? undefined,
  };
}

export default async function EventPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const event = await api.event(slug);

  if (!event) notFound();

  const [timeline, coverage, comparisons, reactions] = await Promise.all([
    api.timeline(slug),
    api.coverage(slug),
    api.comparisons(slug),
    api.reactions(slug),
  ]);

  const numberCount = comparisons?.numbers.length ?? 0;
  const numberDiffCount = comparisons?.numbers.filter((n) => !n.sources_agree).length ?? 0;
  const wordingCount = comparisons?.wording.length ?? 0;
  const cruxParts = event.crux_parts.filter(
    (p) => p.label !== "When" && p.label !== "Where",
  );
  const cruxPartsWithoutDevelopments = cruxParts.filter(
    (part) => part.label !== "Key developments",
  );
  const cruxAlreadyListed = new Set(
    cruxPartsWithoutDevelopments.flatMap((part) =>
      cruxBulletItems(part.label, part.text).map((item) => item.trim()),
    ),
  );
  const cruxKeyDevelopments =
    timeline?.developments.filter(
      (dev) => !cruxAlreadyListed.has(dev.title.trim()),
    ) ?? [];

  const thinDevelopmentCount = coverage
    ? coverage.developments.filter((dev) => {
        const cells = coverage.cells.filter((c) => c.development_id === dev.id);
        const applicable = cells.filter((c) => c.status !== "not_applicable");
        const covered = applicable.filter((c) => c.status === "covered").length;
        return applicable.length > 1 && covered / applicable.length < 0.5;
      }).length
    : 0;

  const locationKicker = [event.location, formatDate(event.event_time)]
    .filter(Boolean)
    .join(" · ");

  // Coverage human sentence: "N of M outlets covered the average development."
  const coveredSources = coverage?.sources.filter(
    (s) => s.coverage_rate !== null && s.coverage_rate > 0,
  ).length ?? 0;
  const totalSources = coverage?.sources.length ?? 0;

  const railStops: RailStop[] = [
    { id: "crux", label: "Crux" },
    { id: "context", label: "Context" },
    { id: "timeline", label: "How it unfolded" },
    { id: "coverage", label: "Who covered it" },
    { id: "numbers", label: "The numbers", accent: numberCount > 0 },
    { id: "wording", label: "The word that changed", accent: wordingCount > 0 },
    { id: "reaction", label: "Public response" },
    { id: "sources", label: "Original reports" },
    { id: "your-reading", label: "Your reading" },
  ];

  return (
    <div className={styles.page}>
      {/* Back */}
      <Link href="/home" className={styles.back}>
        ← Front page
      </Link>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <header className={styles.header}>
        <p className={styles.kicker}>{locationKicker || "NEWS"}</p>
        <h1 className={styles.headline}>{event.title}</h1>
        {event.crux && <p className={styles.crux}>{event.crux}</p>}
        <StoryImage event={event} size="hero" caption />

        <div className={styles.headerFacts}>
          {event.location && (
            <div className={styles.fact}>
              <span className={styles.factLabel}>Where</span>
              <span className={styles.factValue}>{event.location}</span>
            </div>
          )}
          {event.event_time && (
            <div className={styles.fact}>
              <span className={styles.factLabel}>When</span>
              <span className={styles.factValue}>{formatDate(event.event_time)}</span>
            </div>
          )}
          <div className={styles.fact}>
            <span className={styles.factLabel}>Articles</span>
            <span className={styles.factValue}>{formatCount(event.article_count)}</span>
          </div>
          {event.is_demo && (
            <div className={styles.fact}>
              <span className={styles.factLabel}>Dataset</span>
              <span className={styles.factValue}>
                <span className="demo-label">Sample data</span>
              </span>
            </div>
          )}
        </div>
      </header>

      {/* ── Stats hero: what the investigation found, at a glance ────── */}
      <div className={styles.statsHero}>
        <div className={styles.statItem}>
          <span className={styles.statNum}>{formatCount(event.source_count)}</span>
          <span className={styles.statLabel}>
            source{event.source_count !== 1 ? "s" : ""} read
          </span>
        </div>
        <div className={styles.statItem}>
          <span className={styles.statNum}>
            {formatCount(event.development_count)}
          </span>
          <span className={styles.statLabel}>
            development{event.development_count !== 1 ? "s" : ""}
          </span>
        </div>
        {coverage?.overall_coverage_rate != null && (
          <div className={styles.statItem}>
            <span className={styles.statNum}>
              {formatShare(coverage.overall_coverage_rate)}
            </span>
            <span className={styles.statLabel}>avg. coverage</span>
          </div>
        )}
        {numberCount > 0 && (
          <a href="#numbers" className={`${styles.statItem} ${styles.statAccent}`}>
            {numberDiffCount > 0 ? (
              <>
                <span className={styles.statNum}>{numberDiffCount}</span>
                <span className={styles.statLabel}>
                  number {numberDiffCount === 1 ? "discrepancy" : "discrepancies"} →
                </span>
              </>
            ) : (
              <>
                <span className={styles.statNum}>{numberCount}</span>
                <span className={styles.statLabel}>
                  {numberCount === 1 ? "figure" : "figures"} all agree →
                </span>
              </>
            )}
          </a>
        )}
        {wordingCount > 0 && (
          <a href="#wording" className={`${styles.statItem} ${styles.statAccent}`}>
            <span className={styles.statNum}>{wordingCount}</span>
            <span className={styles.statLabel}>
              wording {wordingCount === 1 ? "difference" : "differences"} →
            </span>
          </a>
        )}
      </div>

      {/* ── Jump navigation (mobile / quick access) ─────────────────── */}
      <nav className={styles.jump} aria-label="Jump to section">
        <a href="#crux" className={styles.jumpLink}>Crux</a>
        <a href="#context"       className={styles.jumpLink}>Context</a>
        <a href="#timeline"      className={styles.jumpLink}>Timeline</a>
        <a href="#coverage"      className={styles.jumpLink}>Coverage</a>
        {numberCount > 0 && (
          <a href="#numbers" className={`${styles.jumpLink} ${styles.jumpAccent}`}>
            Numbers ({numberCount})
          </a>
        )}
        {wordingCount > 0 && (
          <a href="#wording" className={`${styles.jumpLink} ${styles.jumpAccent}`}>
            The word ({wordingCount})
          </a>
        )}
        <a href="#reaction" className={styles.jumpLink}>Public response</a>
        <a href="#sources" className={styles.jumpLink}>Original reports</a>
        <a href="#your-reading" className={styles.jumpLink}>Your reading</a>
      </nav>

      {/* ── Rail + content two-column layout ────────────────────────── */}
      <div className={styles.railLayout}>
        <ProgressRail stops={railStops} />

        <div className={styles.railContent}>
          {/* ── 1 · Crux ──────────────────────────────────────────── */}
          <Section
            id="crux"
            title="Crux"
            tone="crux"
            lead="The facts ONE I could establish from the reporting. The fraction after a development is how many of the outlets ONE I read reported it — 9/10 means nine of ten did. That is why it is in the crux."
          >
            {cruxPartsWithoutDevelopments.length > 0 || cruxKeyDevelopments.length > 0 ? (
              <ul className={styles.cruxList}>
                {cruxPartsWithoutDevelopments.map((part) => {
                    const items = cruxBulletItems(part.label, part.text);
                    return (
                      <li key={part.label} className={styles.cruxGroup}>
                        <span className={styles.cruxGroupLabel}>{part.label}</span>
                        <ul className={styles.cruxBullets}>
                          {items.map((item) => {
                            const match = timeline?.developments.find(
                              (d) =>
                                d.title.trim() === item.trim() ||
                                (d.description && d.description.trim() === item.trim()),
                            );
                            const n = match?.covered_by_source_count;
                            const of = event.source_count;
                            return (
                              <li key={item}>
                                {item}
                                {n != null && of > 0 && (
                                  <CoverageRatio n={n} of={of} thin={n / of < 0.5} />
                                )}
                              </li>
                            );
                          })}
                        </ul>
                      </li>
                    );
                  })}
                {cruxKeyDevelopments.length > 0 && (
                  <li className={styles.cruxGroup}>
                    <span className={styles.cruxGroupLabel}>Key developments</span>
                    <ul className={styles.cruxBullets}>
                      {cruxKeyDevelopments.map((dev) => {
                        const n = dev.covered_by_source_count;
                        const of = event.source_count;
                        return (
                          <li key={dev.id}>
                            {dev.title}
                            <CoverageRatio
                              n={n}
                              of={of}
                              thin={of > 0 && n / of < 0.5}
                            />
                          </li>
                        );
                      })}
                    </ul>
                  </li>
                )}
              </ul>
            ) : (
              <Notice title="No summary established yet">
                <p>None of the gathered reports shared enough verified detail to build a summary without guessing.</p>
              </Notice>
            )}
          </Section>

          {/* ── 2 · Context ───────────────────────────────────────── */}
          <Section
            id="context"
            title="Context"
            lead="Background established from the reporting itself — not added editorially."
          >
            {event.context ? (
              <>
                <p className={styles.contextBody}>{event.context}</p>
                {event.context_parts.length > 0 && (
                  <Disclosure label="How this was assembled">
                    <ul className={styles.cruxParts}>
                      {event.context_parts.map((part) => (
                        <li key={part.label} className={styles.cruxPart}>
                          <span className={styles.cruxPartLabel}>{part.label}</span>
                          <span className={styles.cruxPartText}>{part.text}</span>
                        </li>
                      ))}
                    </ul>
                  </Disclosure>
                )}
              </>
            ) : (
              <Notice title="No background established">
                <p>The gathered reports did not share enough background to summarise without guessing.</p>
              </Notice>
            )}
          </Section>

          {/* ── 3 · Timeline ──────────────────────────────────────── */}
          <Section
            id="timeline"
            title="How it unfolded"
            aside={
              timeline
                ? `${formatCount(timeline.developments.length)} developments`
                : undefined
            }
            lead="Each step was reported by at least one of the sources ONE I read. The order is chronological by when it was reported."
          >
            {timeline && timeline.developments.length > 0 ? (
              <Timeline
                developments={timeline.developments}
                sourceCount={event.source_count}
              />
            ) : (
              <Notice title="No separate developments identified">
                <p>{timeline?.note ?? "The reporting gathered so far describes the event as a single moment."}</p>
              </Notice>
            )}
          </Section>

          {/* ── 4 · Coverage ──────────────────────────────────────── */}
          <Section
            id="coverage"
            title="Who covered it"
            tone="coverage"
            aside={
              coverage?.overall_coverage_rate != null
                ? `${formatShare(coverage.overall_coverage_rate)} reported on average`
                : undefined
            }
            lead="A source not reporting something does not mean it chose to hide it — it may mean a different focus, deadline, or article length."
          >
            {coverage && coverage.developments.length > 0 ? (
              <>
                <p className={styles.coverageSentence}>
                  {coveredSources} of {totalSources} outlets reported at least
                  one development of this event. The grid below shows exactly
                  who reported what.
                </p>
                {timeline && (
                  <MissedFacts
                    developments={timeline.developments}
                    sourceCount={event.source_count}
                  />
                )}
                <CoverageMatrix coverage={coverage} />
              </>
            ) : (
              <Notice title="Coverage comparison not yet available">
                <p>{coverage?.note ?? "Coverage is shown once ONE I has identified developments and read more than one source."}</p>
              </Notice>
            )}
          </Section>

          {/* ── 5 · Numbers ───────────────────────────────────────── */}
          {numberCount > 0 ? (
            <Section
              id="numbers"
              title={numberDiffCount > 0 ? "Where the numbers differ" : "The numbers"}
              tone="numbers"
              aside={`${formatCount(numberCount)} comparison${numberCount !== 1 ? "s" : ""}, ${formatCount(numberDiffCount)} differ${numberDiffCount === 1 ? "s" : ""}`}
              lead="Only figures that describe the same thing, in the same unit, over the same period are placed side by side. Anything too ambiguous to compare honestly is left out."
            >
              <NumberComparisons comparisons={comparisons!.numbers} />
            </Section>
          ) : (
            <Section id="numbers" title="The numbers">
              <Notice title="No comparable figures found">
                <p>Either the sources did not report the same measurement, or the figures they did report were not close enough in subject and unit to compare honestly.</p>
              </Notice>
            </Section>
          )}

          {/* ── 6 · Wording ───────────────────────────────────────── */}
          {wordingCount > 0 ? (
            <Section
              id="wording"
              title="Same event. Different framing."
              tone="wording"
              aside={`${formatCount(wordingCount)} comparison${wordingCount !== 1 ? "s" : ""}`}
              lead="Each pair shows two framings of the same development — how each outlet casts it, with the telling words quoted as evidence. ONE I does not pick a winner, and this is not a score of the outlet."
            >
              <WordingComparisons comparisons={comparisons!.wording} />
            </Section>
          ) : (
            <Section id="wording" title="Wording comparison">
              <Notice title="No meaningful wording differences found">
                <p>Where sources described the same development, their wording was close enough that showing it side by side would not tell you anything new.</p>
              </Notice>
            </Section>
          )}

          {/* ── 7 · Public response ───────────────────────────────── */}
          <Section
            id="reaction"
            title="Public response"
            tone="reaction"
            lead="The most-liked public comments about this event. This is discussion, not evidence about what happened."
          >
            {reactions ? (
              <ReactionPanel reactions={reactions} />
            ) : (
              <Notice title="Public response data unavailable" />
            )}
          </Section>

          {/* ── 8 · Original reports ──────────────────────────────── */}
          <Section
            id="sources"
            title="Original reports"
            aside={`${formatCount(event.articles.length)} article${event.articles.length !== 1 ? "s" : ""}`}
            lead="Everything above was assembled from these. Read them yourself."
          >
            <details className={styles.reportsToggle}>
            <summary>
              Show all {formatCount(event.articles.length)} reports from{" "}
              {formatCount(new Set(event.articles.map((a) => a.source.id)).size)} outlets
            </summary>
            <table className={styles.articleTable}>
              <thead>
                <tr>
                  <th scope="col">Source</th>
                  <th scope="col">Headline</th>
                  <th scope="col">Published</th>
                </tr>
              </thead>
              <tbody>
                {event.articles.map((article) => (
                  <tr key={article.id}>
                    <td className={styles.articleSource}>
                      <Link href={`/sources/${article.source.id}`}>
                        {article.source.name}
                      </Link>
                    </td>
                    <td className={styles.articleTitle}>
                      <a href={article.url} target="_blank" rel="noreferrer noopener">
                        {article.title} ↗
                      </a>
                      {article.title_is_summary && (
                        <span className={styles.summaryNote}>
                          Wikipedia&rsquo;s summary of this report, not the outlet&rsquo;s headline
                        </span>
                      )}
                    </td>
                    <td className={styles.articleWhen}>
                      {formatDateTime(article.published_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </details>
          </Section>

          {/* ── 10 · Poll + completeness ──────────────────────────── */}
          <Section
            id="your-reading"
            title="Your reading"
            lead="The questions are yours. The meter is a count of how completely the identified developments were reported — not a verdict on anyone."
          >
            <CoveragePoll eventSlug={event.slug} />
            <div style={{ height: "1.75rem" }} />
            <CoverageScore
              overallCoverageRate={coverage?.overall_coverage_rate ?? null}
              developmentCount={coverage?.developments.length ?? event.development_count}
              thinDevelopmentCount={thinDevelopmentCount}
              numberDiscrepancyCount={numberDiffCount}
            />
          </Section>
        </div>
      </div>

      <div style={{ marginBottom: "4rem" }} />
    </div>
  );
}
