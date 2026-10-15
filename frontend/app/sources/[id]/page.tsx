import Link from "next/link";
import { notFound } from "next/navigation";

import { DemoLabel, Notice } from "@/components/Notice";
import { api } from "@/lib/api";
import { formatCount, formatDate, formatShare } from "@/lib/format";

import styles from "../sources.module.css";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const source = await api.source(id);
  return { title: source ? source.name : "Source" };
}

export default async function SourcePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const source = await api.source(id);

  if (!source) {
    notFound();
  }

  return (
    <div className={styles.page}>
      <Link href="/sources" className={styles.back}>
        ← All sources
      </Link>

      <div className={styles.detailHead}>
        <p className="kicker kicker-red">Coverage record</p>
        <h1>
          {source.name} {source.is_demo ? <DemoLabel /> : null}
        </h1>
        <p className="meta" style={{ marginTop: "0.35rem" }}>
          {source.source_type.replace("_", " ")} · what this outlet reported,
          event by event. A record, not a grade.
        </p>
        <div className={styles.detailFacts}>
          <div className={styles.detailFact}>
            <span className={styles.detailFactLabel}>Domain</span>
            <span className={styles.detailFactValue}>{source.domain}</span>
          </div>
          <div className={styles.detailFact}>
            <span className={styles.detailFactLabel}>Articles read</span>
            <span className={styles.detailFactValue}>
              {formatCount(source.article_count)}
            </span>
          </div>
          <div className={styles.detailFact}>
            <span className={styles.detailFactLabel}>Events followed</span>
            <span className={styles.detailFactValue}>
              {formatCount(source.event_count)}
            </span>
          </div>
        </div>
      </div>

      {source.events.length === 0 ? (
        <Notice title="No analysed events yet for this source">
          <p>Nothing from this source has been grouped into an event.</p>
        </Notice>
      ) : (
        <div className={styles.tableWrap}>
          <h2 style={{ fontSize: "1.2rem", marginBottom: "0.75rem" }}>
            What they covered
          </h2>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Event</th>
                <th scope="col">When</th>
                <th scope="col">Articles</th>
                <th scope="col">Reported</th>
                <th scope="col">Unclear</th>
                <th scope="col">Not reported</th>
                <th scope="col">Share reported</th>
              </tr>
            </thead>
            <tbody>
              {source.events.map((event) => (
                <tr key={event.event_id}>
                  <td className={styles.name}>
                    <Link href={`/events/${event.event_slug}`}>
                      {event.event_title}
                    </Link>
                  </td>
                  <td className={styles.numeric}>
                    {formatDate(event.event_time)}
                  </td>
                  <td className={styles.numeric}>
                    {formatCount(event.article_count)}
                  </td>
                  <td className={styles.numeric}>{formatCount(event.covered)}</td>
                  <td className={styles.numeric}>{formatCount(event.unclear)}</td>
                  <td className={styles.numeric}>
                    {formatCount(event.not_covered)}
                  </td>
                  <td className={styles.numeric}>
                    {formatShare(event.coverage_rate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="note" style={{ marginTop: "2rem" }}>
        Developments published after an article went out are left out of that
        article&apos;s count entirely: a report cannot mention something that
        had not happened yet.
      </p>
    </div>
  );
}
