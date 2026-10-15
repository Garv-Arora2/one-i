import { joinWithAnd, sentenceCase } from "@/lib/format";
import type { NumberComparison } from "@/lib/types";

import { NumberSpread } from "./NumberSpread";
import styles from "./Comparisons.module.css";

function differenceStatement(c: NumberComparison): string {
  if (c.sources_agree) return "All sources report the same figure.";

  const size = `${c.difference.toLocaleString("en-GB")} ${c.difference_unit}`;
  if (c.relative_difference_percent === null)
    return `The accounts are ${size} apart.`;

  return `The accounts are ${size} apart — a ${c.relative_difference_percent.toFixed(1)}% spread between the lowest and highest figure reported.`;
}

function AgreementLine({ comparison }: { comparison: NumberComparison }) {
  const first = comparison.observations[0];
  const sourceCount = new Set(comparison.observations.map((o) => o.source.id)).size;
  if (!first) return null;
  return (
    <div>
      <p className={`${styles.diff} ${styles.diffAgree}`}>
        All {sourceCount} outlet{sourceCount !== 1 ? "s" : ""} report{" "}
        {first.formatted_value}.
      </p>
      <details className={styles.agreeDetails}>
        <summary>See how each outlet put it</summary>
        {comparison.observations.map((obs) => (
          <p key={obs.article_id} className={styles.figQuote}>
            &ldquo;{obs.context}&rdquo; — {obs.source.name}{" "}
            <a
              className={styles.figLink}
              href={obs.article_url}
              target="_blank"
              rel="noreferrer noopener"
            >
              Read original ↗
            </a>
          </p>
        ))}
      </details>
    </div>
  );
}

export function NumberComparisons({
  comparisons,
}: {
  comparisons: NumberComparison[];
}) {
  return (
    <div>
      {comparisons.map((c) => {
        const key = `${c.subject}|${c.value_kind}|${c.unit ?? ""}`;
        const disputed = !c.sources_agree && c.observations.length > 1;

        return (
          <article
            key={key}
            className={`${styles.numBlock} ${disputed ? styles.numBlockDisputed : ""}`}
          >
            <p className={styles.numSubject}>{sentenceCase(c.subject)}</p>
            <p className={styles.numMeta}>
              {joinWithAnd(
                [
                  c.time_period ?? null,
                  c.unit ? `measured in ${c.unit}` : null,
                  `${c.observations.length} source${c.observations.length !== 1 ? "s" : ""}`,
                ].filter((x): x is string => Boolean(x)),
              )}
            </p>

            {disputed ? (
              <NumberSpread comparison={c} />
            ) : (
              // Sources agree: one line says so — no 200-vs-200 table.
              <AgreementLine comparison={c} />
            )}

            <p className={`${styles.diff} ${c.sources_agree ? styles.diffAgree : ""}`}>
              {differenceStatement(c)}
            </p>
          </article>
        );
      })}
    </div>
  );
}
