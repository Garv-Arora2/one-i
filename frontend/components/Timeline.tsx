import { formatDateTime } from "@/lib/format";
import type { Development } from "@/lib/types";

import styles from "./Timeline.module.css";

export function Timeline({
  developments,
  sourceCount,
}: {
  developments: Development[];
  sourceCount: number;
}) {
  return (
    <ol className={styles.timeline}>
      {developments.map((dev) => {
        const missed =
          sourceCount > 1 && dev.covered_by_source_count / sourceCount < 0.5;
        const thin = dev.supporting_source_count < 2;
        const descriptionDiffersFromTitle =
          dev.description && dev.description.trim() !== dev.title.trim();

        return (
          <li
            key={dev.id}
            className={styles.item}
            data-thin={thin ? "true" : "false"}
            data-missed={missed ? "true" : "false"}
          >
            <time className={styles.when} dateTime={dev.occurred_at ?? undefined}>
              {formatDateTime(dev.occurred_at)}
            </time>

            <div className={styles.body}>
              {missed && (
                <p className={styles.missedFlag}>Most outlets did not report this</p>
              )}
              <h3 className={styles.itemTitle}>{dev.title}</h3>
              {descriptionDiffersFromTitle && (
                <p className={styles.itemDesc}>{dev.description}</p>
              )}
              <p className={styles.support}>
                Reported by{" "}
                <strong>{dev.covered_by_source_count}</strong> of{" "}
                {sourceCount} sources
                {thin ? " — first found in a single source" : ""}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
