"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { distinctiveWords } from "@/lib/wordingContrast";
import { splitForDifference, type VerbGroup } from "@/lib/wordingSplit";
import type { WordingComparison, WordingPassage } from "@/lib/types";

import styles from "./Comparisons.module.css";

const ASPECT_CLASS: Record<string, string> = {
  evaluation: styles.hlEval,
  severity: styles.hlSeverity,
  certainty: styles.hlCertainty,
  responsibility: styles.hlResponsibility,
  action: styles.hlAction,
};

function highlight(
  text: string,
  markers: Record<string, string[]>,
  extra: string[] = [],
): React.ReactNode {
  const words = [...new Set([...Object.values(markers).flat(), ...extra])].filter(
    Boolean,
  );
  if (!words.length) return text;

  const aspectOf = new Map<string, string>();
  for (const [aspect, list] of Object.entries(markers)) {
    for (const word of list) aspectOf.set(word.toLowerCase(), aspect);
  }

  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const pattern = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = text.split(pattern);

  return parts.map((part, i) => {
    if (i % 2 !== 1) return part;
    const aspect = aspectOf.get(part.toLowerCase()) ?? "action";
    return (
      <mark key={i} className={ASPECT_CLASS[aspect] ?? styles.highlight}>
        {part}
      </mark>
    );
  });
}

function sideLabel(
  valence: VerbGroup["valence"] | undefined,
  hasWord: boolean,
): string {
  if (!hasWord) return "Without this framing";
  if (valence === "harsh") return "Negative framing";
  if (valence === "softer") return "Positive framing";
  return "Different framing";
}

function VerbColumn({
  verb,
  passages,
  all,
  side,
  valence,
  hasWord,
}: {
  verb: string;
  passages: WordingPassage[];
  all: WordingPassage[];
  side: "critical" | "favourable";
  valence?: VerbGroup["valence"];
  hasWord: boolean;
}) {
  const [showContext, setShowContext] = useState(false);
  const lead = passages[0];
  const extra = hasWord ? distinctiveWords(lead, all) : [];
  const others = passages.slice(1);

  return (
    <div className={`${styles.verbCol} ${side === "critical" ? styles.col_harsh : styles.col_softer}`}>
      <p className={styles.wordColHead}>{sideLabel(valence, hasWord)}</p>
      <span className={styles.passSource}>{lead.source.name}</span>
      <p className={styles.passQuote}>
        &ldquo;{highlight(lead.quoted_text, lead.markers, [verb, ...extra])}&rdquo;
      </p>
      {hasWord ? (
        <p className={styles.tellWord}>
          <span className={styles.tellKicker}>The telling word</span> {verb}
        </p>
      ) : (
        <p className={styles.wordColEmpty}>
          No word of this kind here — the report describes it without one.
        </p>
      )}
      {others.length > 0 && (
        <p className={styles.verbAlso}>
          Also framed this way by {others.map((p) => p.source.name).join(" · ")}
        </p>
      )}
      {showContext && lead.surrounding_text && (
        <p className={styles.passSurrounding}>…{lead.surrounding_text}…</p>
      )}
      <div className={styles.passActions}>
        {lead.surrounding_text && (
          <button
            type="button"
            className={styles.passToggle}
            onClick={() => setShowContext((v) => !v)}
          >
            {showContext ? "Hide context" : "See full sentence"}
          </button>
        )}
        {lead.article_url && (
          <a
            className={styles.passLink}
            href={lead.article_url}
            target="_blank"
            rel="noreferrer noopener"
          >
            Read original ↗
          </a>
        )}
      </div>
    </div>
  );
}

function EmptySide({ side }: { side: "critical" | "favourable" }) {
  return (
    <div className={`${styles.verbCol} ${side === "critical" ? styles.col_harsh : styles.col_softer}`}>
      <p className={styles.wordColHead}>
        {side === "critical" ? "Negative framing" : "Positive framing"}
      </p>
      <p className={styles.wordColEmpty}>
        No contrasting framing of this kind in this pair.
      </p>
    </div>
  );
}

function DifferenceColumn({
  left,
  right,
  aspect,
}: {
  left: VerbGroup | null;
  right: VerbGroup | null;
  aspect: string | null;
}) {
  return (
    <div className={styles.diffCol}>
      <p className={styles.diffKicker}>
        The difference{aspect ? ` · ${aspect}` : ""}
      </p>
      <p className={styles.diffWord}>{left?.verb || "—"}</p>
      <p className={styles.diffVs}>vs</p>
      <p className={styles.diffWord}>{right?.verb || "—"}</p>
    </div>
  );
}

/**
 * Same event, two framings: how each outlet casts one moment, with the
 * telling words quoted as evidence. ONE I does not say which framing is
 * right, and this is not a score of the outlet.
 */
export function WordingComparisons({
  comparisons,
}: {
  comparisons: WordingComparison[];
}) {
  // True framing pairs first: two different words for the same thing read
  // better than a word against silence.
  const ordered = useMemo(() => {
    const splits = comparisons.map((c) =>
      splitForDifference(c.passages, c.differing_aspects),
    );
    return comparisons
      .map((comparison, i) => ({ comparison, split: splits[i] }))
      .sort((a, b) => {
        const aPair =
          (a.split.critical?.hasWord ? 1 : 0) +
          (a.split.favourable?.hasWord ? 1 : 0);
        const bPair =
          (b.split.critical?.hasWord ? 1 : 0) +
          (b.split.favourable?.hasWord ? 1 : 0);
        return bPair - aPair;
      });
  }, [comparisons]);

  const [idx, setIdx] = useState(0);
  const count = ordered.length;

  const prev = useCallback(
    () => setIdx((i) => (i - 1 + count) % count),
    [count],
  );
  const next = useCallback(() => setIdx((i) => (i + 1) % count), [count]);

  useEffect(() => {
    if (count < 2) return;
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement | null;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      if (e.key === "ArrowLeft") prev();
      if (e.key === "ArrowRight") next();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [count, prev, next]);

  const [shownComparisons, setShownComparisons] = useState(comparisons);
  if (shownComparisons !== comparisons) {
    setShownComparisons(comparisons);
    setIdx(0);
  }

  if (count === 0) return null;

  const current = ordered[idx % count];

  return (
    <div>
      <article className={styles.wordBlock} key={`${current.comparison.topic}-${idx}`}>
        <p className={styles.wordHead}>{current.comparison.topic}</p>
        <p className={styles.wordAspects}>
          {current.split.framing} ONE I does not say which framing is right,
          and this is not a score of the outlet.
        </p>

        <div className={styles.wordDiff}>
          {current.split.critical ? (
            <VerbColumn
              verb={current.split.critical.verb}
              passages={current.split.critical.passages}
              all={current.comparison.passages}
              side="critical"
              valence={current.split.critical.valence}
              hasWord={current.split.critical.hasWord}
            />
          ) : (
            <EmptySide side="critical" />
          )}
          <DifferenceColumn left={current.split.critical} right={current.split.favourable} aspect={current.split.aspect} />
          {current.split.favourable ? (
            <VerbColumn
              verb={current.split.favourable.verb}
              passages={current.split.favourable.passages}
              all={current.comparison.passages}
              side="favourable"
              valence={current.split.favourable.valence}
              hasWord={current.split.favourable.hasWord}
            />
          ) : (
            <EmptySide side="favourable" />
          )}
        </div>
      </article>

      {count > 1 && (
        <div className={styles.carouselNav}>
          <button
            type="button"
            className={styles.carouselBtn}
            onClick={prev}
            aria-label="Previous comparison"
          >
            ← Previous
          </button>
          <span className={styles.carouselCounter}>
            {idx + 1} of {count}
          </span>
          <button
            type="button"
            className={styles.carouselBtn}
            onClick={next}
            aria-label="Next comparison"
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
