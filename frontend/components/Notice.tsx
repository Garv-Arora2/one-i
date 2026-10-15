import styles from "./Notice.module.css";

export function Notice({
  title,
  children,
}: {
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <div className={styles.notice} role="status">
      <p className={styles.title}>{title}</p>
      {children && <div className={styles.body}>{children}</div>}
    </div>
  );
}

export function DemoLabel() {
  return (
    <span className={styles.demoNotice} aria-label="Sample data">
      <span aria-hidden="true">◎</span>
      Sample data — not real events
    </span>
  );
}
