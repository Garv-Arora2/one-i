import styles from "./CoverageRatio.module.css";

export function CoverageRatio({
  n,
  of,
  thin = false,
}: {
  n: number;
  of: number;
  thin?: boolean;
}) {
  const explanation =
    of <= 0
      ? ""
      : thin
        ? `${n} of ${of} outlets ONE I read reported this. That is fewer than half, so coverage of this point is thin — not a claim that anyone hid it.`
        : `${n} of ${of} outlets ONE I read reported this. That is why it is in the crux.`;

  return (
    <span className={styles.ratioWrap} tabIndex={0}>
      <span
        className={styles.ratio}
        data-thin={thin ? "true" : "false"}
      >
        ({n}/{of})
      </span>
      <span className={styles.ratioTip} role="tooltip">
        {explanation}
      </span>
    </span>
  );
}
