import { CoverageRatio } from "@/components/CoverageRatio";
import type { Development } from "@/lib/types";

import styles from "./MissedFacts.module.css";

/**
 * Developments most outlets did not report. "Not covered" — never
 * "intentionally omitted".
 */
export function MissedFacts({
  developments,
  sourceCount,
}: {
  developments: Development[];
  sourceCount: number;
}) {
  if (sourceCount < 2) return null;

  const missed = developments
    .filter((dev) => dev.covered_by_source_count / sourceCount < 0.5)
    .sort((a, b) => a.covered_by_source_count - b.covered_by_source_count);

  if (missed.length === 0) return null;

  return (
    <aside className={styles.missedBox}>
      <p className={styles.missedKicker}>Most outlets did not report</p>
      <p className={styles.missedLead}>
        These points were in at least one report, but fewer than half of the
        outlets ONE I read carried them. That is not a claim that anyone hid
        them.
      </p>
      <ul className={styles.missedList}>
        {missed.map((dev) => (
          <li key={dev.id}>
            <span
              className={styles.devTip}
              data-full={dev.description || dev.title}
              tabIndex={0}
            >
              {dev.short_title || dev.title}
            </span>
            <CoverageRatio
              n={dev.covered_by_source_count}
              of={sourceCount}
              thin
            />
          </li>
        ))}
      </ul>
    </aside>
  );
}
