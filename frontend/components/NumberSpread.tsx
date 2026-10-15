"use client";

import { useState } from "react";

import type { NumberComparison } from "@/lib/types";

import styles from "./Comparisons.module.css";

/**
 * The same figure from different outlets on a min–max number line.
 * Each dot is one outlet's reported value; hover/tap shows the quote.
 */
export function NumberSpread({ comparison }: { comparison: NumberComparison }) {
  const [activeIdx, setActiveIdx] = useState<number | null>(null);

  const { lowest, highest, observations } = comparison;
  const range = highest - lowest || 1;

  // Group observations that share a value so their dots don't overlap invisibly.
  const positions = observations.map((obs) => ({
    obs,
    pct: ((obs.value - lowest) / range) * 100,
  }));

  return (
    <div className={styles.spread}>
      <div className={styles.spreadTrack}>
        <span className={styles.spreadLine} aria-hidden="true" />
        {positions.map(({ obs, pct }, i) => (
          <button
            key={`${obs.article_id}-${obs.formatted_value}-${i}`}
            type="button"
            className={`${styles.spreadDot} ${activeIdx === i ? styles.spreadDotActive : ""}`}
            style={{ left: `${pct}%` }}
            onClick={() => setActiveIdx(activeIdx === i ? null : i)}
            onMouseEnter={() => setActiveIdx(i)}
            aria-label={`${obs.source.name}: ${obs.formatted_value}`}
          >
            <span className="sr-only">
              {obs.source.name}: {obs.formatted_value}
            </span>
          </button>
        ))}
      </div>

      {/* Min / max labels */}
      <div className={styles.spreadEnds}>
        <span className={styles.spreadEnd}>
          {observations.find((o) => o.value === lowest)?.formatted_value ??
            lowest.toLocaleString("en-GB")}
        </span>
        <span className={styles.spreadEnd}>
          {observations.find((o) => o.value === highest)?.formatted_value ??
            highest.toLocaleString("en-GB")}
        </span>
      </div>

      {/* Active observation detail */}
      {activeIdx !== null && positions[activeIdx] && (
        <div className={styles.spreadDetail}>
          <span className={styles.figSource}>
            {positions[activeIdx].obs.source.name}
          </span>
          <p className={styles.spreadDetailValue}>
            {positions[activeIdx].obs.formatted_value}
          </p>
          <p className={styles.figQuote}>
            &ldquo;{positions[activeIdx].obs.context}&rdquo;
          </p>
          <a
            className={styles.figLink}
            href={positions[activeIdx].obs.article_url}
            target="_blank"
            rel="noreferrer noopener"
          >
            Read original ↗
          </a>
        </div>
      )}

      {activeIdx === null && (
        <p className={styles.spreadHint}>
          Each dot is one outlet&rsquo;s reported figure. Select a dot to see
          the original wording.
        </p>
      )}
    </div>
  );
}
