"use client";

import { useEffect, useRef, useState } from "react";

import styles from "./CoverageScore.module.css";

export interface CoverageScoreInput {
  overallCoverageRate: number | null;
  developmentCount: number;
  thinDevelopmentCount: number;
  numberDiscrepancyCount: number;
}

/**
 * Completeness of *reporting*, not a grade of honesty, bias, or truth.
 *
 *  - Most of the score is the share of developments that were reported.
 *  - Thin rows (reported by fewer than half of outlets) pull it down.
 *  - Unresolved numerical discrepancies pull it down slightly.
 *
 * Public discussion is deliberately excluded: Reddit and YouTube are reaction,
 * not a check on whether the coverage was complete.
 */
export function computeCompleteness(input: CoverageScoreInput): number {
  const coverage = input.overallCoverageRate ?? 0;
  const thinShare =
    input.developmentCount > 0
      ? input.thinDevelopmentCount / input.developmentCount
      : 0;
  const numberDrag = Math.min(0.22, input.numberDiscrepancyCount * 0.045);
  const raw = coverage * 0.78 + (1 - thinShare) * 0.22 - numberDrag;
  return Math.round(100 * Math.max(0, Math.min(1, raw)));
}

export function CoverageScore(input: CoverageScoreInput) {
  const target = computeCompleteness(input);
  const [value, setValue] = useState(0);
  const [visible, setVisible] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.4 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!visible) return;
    const start = performance.now();
    const duration = 1400;
    let frame = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      setValue(Math.round(target * eased));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [visible, target]);

  const radius = 86;
  const circumference = Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;
  const tone =
    value >= 70 ? "high" : value >= 40 ? "mid" : "low";

  return (
    <div ref={rootRef} className={styles.wrap} data-tone={tone}>
      <div className={styles.meter}>
        <svg viewBox="0 0 220 130" className={styles.svg} aria-hidden="true">
          <path
            className={styles.track}
            d="M24 120 A86 86 0 0 1 196 120"
            fill="none"
            strokeWidth="16"
            strokeLinecap="round"
          />
          <path
            className={styles.fill}
            d="M24 120 A86 86 0 0 1 196 120"
            fill="none"
            strokeWidth="16"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className={styles.readout}>
          <span className={styles.num}>{value}</span>
          <span className={styles.of}>/ 100</span>
        </div>
      </div>

      <div className={styles.copy}>
        <p className={styles.kicker}>Coverage completeness</p>
        <h3 className={styles.title}>How much of the identified story made the reports</h3>
        <p className={styles.explain}>
          {value} out of 100. This is the share of developments that were
          reported, reduced where a development was covered by fewer than half
          the outlets, and reduced again where numerical discrepancies remain.
          It is not a bias score, a truth score, or a verdict on any outlet.
          Public discussion is shown above and is not part of this number.
        </p>
        <ul className={styles.legend}>
          <li>
            <strong>Average reporting</strong>{" "}
            {input.overallCoverageRate == null
              ? "not available"
              : `${Math.round(input.overallCoverageRate * 100)}%`}
          </li>
          <li>
            <strong>Thin developments</strong> {input.thinDevelopmentCount} of{" "}
            {input.developmentCount}
          </li>
          <li>
            <strong>Number discrepancies</strong> {input.numberDiscrepancyCount}
          </li>
        </ul>
      </div>
    </div>
  );
}
