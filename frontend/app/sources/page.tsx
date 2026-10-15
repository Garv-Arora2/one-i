import Link from "next/link";

import { DemoLabel, Notice } from "@/components/Notice";
import { api } from "@/lib/api";
import { formatCount } from "@/lib/format";

import styles from "./sources.module.css";

export const metadata = {
  title: "Sources",
};

export const dynamic = "force-dynamic";

export default async function SourcesPage() {
  const data = await api.sources();

  if (!data) {
    return (
      <div className={styles.page}>
        <Notice title="The sources service is not responding">
          <p>
            Start the ONE I API with <code>uvicorn app.main:app --reload</code>{" "}
            and reload this page.
          </p>
        </Notice>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <p className="kicker kicker-red">Coverage overview</p>
      <h1>Sources</h1>
      <p className={`standfirst ${styles.intro}`}>
        Every outlet ONE I has read. These counts describe what has been
        collected, not the quality of a source. A low count usually means less
        has been ingested, not that the outlet is hiding anything.
      </p>

      {data.sources.length === 0 ? (
        <Notice title="No sources have been read yet">
          <p>
            Load the sample dataset with <code>python -m app.cli seed</code>.
          </p>
        </Notice>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th scope="col">Source</th>
                <th scope="col">Kind</th>
                <th scope="col">Articles read</th>
                <th scope="col">Events followed</th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {data.sources.map((source) => (
                <tr key={source.id}>
                  <td className={styles.name}>
                    <Link href={`/sources/${source.id}`}>{source.name}</Link>
                    <span className={styles.domain}>{source.domain}</span>
                  </td>
                  <td className={styles.kind}>
                    {source.source_type.replace("_", " ")}
                  </td>
                  <td className={styles.numeric}>
                    {formatCount(source.article_count)}
                  </td>
                  <td className={styles.numeric}>
                    {formatCount(source.event_count)}
                  </td>
                  <td>{source.is_demo ? <DemoLabel /> : null}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="note" style={{ marginTop: "2rem" }}>
        Open a source to see, event by event, how many of the developments it
        reported. Where the evidence is too thin to decide, ONE I records
        &ldquo;coverage unclear&rdquo; rather than counting it either way.
      </p>
    </div>
  );
}
