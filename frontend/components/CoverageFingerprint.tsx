import styles from "./CoverageFingerprint.module.css";

/**
 * Coverage fingerprint: one dot per outlet that read this event.
 * Pure observable fact — "N outlets read this." No judgment implied.
 */
export function CoverageFingerprint({
  sourceCount,
  label = true,
}: {
  sourceCount: number;
  label?: boolean;
}) {
  if (sourceCount <= 0) return null;
  const dots = Array.from({ length: Math.min(sourceCount, 12) });

  return (
    <span
      className={styles.fingerprint}
      title={`${sourceCount} outlet${sourceCount !== 1 ? "s" : ""} read this event`}
    >
      <span className={styles.dots} aria-hidden="true">
        {dots.map((_, i) => (
          <span key={i} className={styles.dot} />
        ))}
        {sourceCount > 12 && <span className={styles.more}>+{sourceCount - 12}</span>}
      </span>
      {label && (
        <span className={styles.label}>
          {sourceCount} outlet{sourceCount !== 1 ? "s" : ""}
        </span>
      )}
    </span>
  );
}
