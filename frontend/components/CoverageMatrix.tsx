"use client";

import { useState } from "react";

import {
  COVERAGE_EXPLANATION,
  COVERAGE_LABEL,
  COVERAGE_MARK,
  formatDateTime,
} from "@/lib/format";
import type { CoverageResponse } from "@/lib/types";

import styles from "./CoverageMatrix.module.css";

const ORDER = [
  "covered",
  "unclear",
  "not_covered",
  "not_applicable",
] as const;

export function CoverageMatrix({ coverage }: { coverage: CoverageResponse }) {
  const [selected, setSelected] = useState<{
    developmentId: number;
    sourceId: number;
  } | null>(null);

  const cellFor = (devId: number, srcId: number) =>
    coverage.cells.find(
      (c) => c.development_id === devId && c.source_id === srcId,
    );

  const activeCell       = selected ? cellFor(selected.developmentId, selected.sourceId) : undefined;
  const activeDevelopment = selected ? coverage.developments.find((d) => d.id === selected.developmentId) : undefined;
  const activeSource     = selected ? coverage.sources.find((s) => s.source.id === selected.sourceId)?.source : undefined;

  return (
    <div>
      <div className={styles.wrap}>
        {/* Table */}
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <caption className="sr-only">Which sources reported each development</caption>
            <thead>
              <tr>
                <th scope="col" className={styles.cornerTh}>Development</th>
                {coverage.sources.map((entry) => (
                  <th key={entry.source.id} scope="col">
                    {entry.source.name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {coverage.developments.map((dev) => {
                // A development most outlets did not report gets flagged.
                const devCells = coverage.cells.filter(
                  (c) => c.development_id === dev.id,
                );
                const applicable = devCells.filter(
                  (c) => c.status !== "not_applicable",
                );
                const coveredCount = applicable.filter(
                  (c) => c.status === "covered",
                ).length;
                const poorlyCovered =
                  applicable.length > 1 &&
                  coveredCount / applicable.length < 0.5;

                return (
                <tr
                  key={dev.id}
                  className={poorlyCovered ? styles.rowPoor : undefined}
                >
                  <th scope="row" className={styles.devCell}>
                    {poorlyCovered && (
                      <span
                        className={styles.poorStar}
                        title={`Only ${coveredCount} of ${applicable.length} outlets reported this`}
                      >
                        Most outlets did not report this
                      </span>
                    )}
                    <span
                      className={styles.devTip}
                      data-full={dev.description || dev.title}
                      tabIndex={0}
                    >
                      {dev.short_title || dev.title}
                    </span>
                    <span className={styles.devWhen}>
                      {formatDateTime(dev.occurred_at)}
                    </span>
                  </th>
                  {coverage.sources.map((entry) => {
                    const cell = cellFor(dev.id, entry.source.id);
                    const status = cell?.status ?? "not_covered";
                    const isSel =
                      selected?.developmentId === dev.id &&
                      selected?.sourceId === entry.source.id;
                    return (
                      <td key={entry.source.id} className={styles.cell}>
                        <button
                          type="button"
                          className={`${styles.mark} ${isSel ? styles.markSelected : ""}`}
                          data-status={status}
                          aria-pressed={isSel}
                          title={`${entry.source.name}: ${COVERAGE_LABEL[status]}`}
                          onClick={() =>
                            setSelected(
                              isSel ? null : { developmentId: dev.id, sourceId: entry.source.id },
                            )
                          }
                        >
                          <span aria-hidden="true">{COVERAGE_MARK[status]}</span>
                          <span className="sr-only">
                            {entry.source.name}: {COVERAGE_LABEL[status]}
                          </span>
                        </button>
                      </td>
                    );
                  })}
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        <aside className={styles.panel} aria-live="polite">
          {activeCell && activeDevelopment && activeSource ? (
            <>
              <span className={styles.panelSource}>{activeSource.name}</span>
              <p className={styles.panelStatus}>{COVERAGE_LABEL[activeCell.status]}</p>
              <p className={styles.panelDev}>{activeDevelopment.title}</p>
              <p className={styles.panelExpl}>{COVERAGE_EXPLANATION[activeCell.status]}</p>
              {activeCell.matched_terms.length > 0 && (
                <>
                  <p className={styles.panelExpl} style={{ marginBottom: "0.3rem" }}>
                    Wording in common:
                  </p>
                  <div className={styles.terms}>
                    {activeCell.matched_terms.map((term) => (
                      <span key={term} className={styles.term}>{term}</span>
                    ))}
                  </div>
                </>
              )}
              {activeCell.article_url && (
                <a
                  className={styles.panelLink}
                  href={activeCell.article_url}
                  target="_blank"
                  rel="noreferrer noopener"
                >
                  Read original ↗
                </a>
              )}
            </>
          ) : (
            <p className={styles.panelHint}>
              Select any mark to see what that source published about that
              development and why ONE I read it the way it did.
            </p>
          )}
        </aside>
      </div>

      {/* Legend */}
      <div className={styles.legend}>
        {ORDER.map((status) => (
          <span key={status} className={styles.legendItem}>
            <span className={styles.legendMark} aria-hidden="true">
              {COVERAGE_MARK[status]}
            </span>
            {COVERAGE_LABEL[status]}
          </span>
        ))}
      </div>
    </div>
  );
}
