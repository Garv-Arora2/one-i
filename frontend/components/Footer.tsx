import Link from "next/link";
import styles from "./Footer.module.css";

export function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <p className={styles.statement}>
          <strong>ONE I</strong> shows what different sources reported about the
          same event, and where those reports differ in numbers, wording, and
          emphasis. It does not score sources or decide what is true.
        </p>
        <nav className={styles.links} aria-label="Footer">
          <Link href="/home">Front page</Link>
          <Link href="/sources">Sources</Link>
          <Link href="/sign-in">Sign in</Link>
        </nav>
      </div>
    </footer>
  );
}
