import styles from "./Section.module.css";

export function Section({
  id,
  title,
  aside,
  lead,
  tone,
  children,
}: {
  id: string;
  title: string;
  aside?: React.ReactNode;
  lead?: React.ReactNode;
  tone?: "crux" | "coverage" | "numbers" | "wording" | "reaction";
  children: React.ReactNode;
}) {
  return (
    <section
      id={id}
      className={`${styles.section} ${tone ? styles[`tone_${tone}`] : ""}`}
    >
      <div className={styles.head}>
        <h2 className={styles.title}>{title}</h2>
        {aside ? <p className={styles.aside}>{aside}</p> : null}
      </div>
      {lead ? <p className={styles.lead}>{lead}</p> : null}
      <div>{children}</div>
    </section>
  );
}

export function Disclosure({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <details className={styles.details}>
      <summary className={styles.summary}>{label}</summary>
      <div className={styles.detailBody}>{children}</div>
    </details>
  );
}
