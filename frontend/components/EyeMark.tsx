/** The ONE I mark: a magnifying glass containing an eye. */

export function EyeMark({
  size = 28,
  title = "ONE I",
}: {
  size?: number;
  title?: string;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label={title}
      fill="none"
    >
      <circle
        cx="21"
        cy="20"
        r="15"
        stroke="currentColor"
        strokeWidth="2.4"
      />
      <path
        d="M32 31 L43 43"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
      />
      <path
        d="M10 20c3.6-5.6 17.8-5.6 22 0-4.2 5.6-18.4 5.6-22 0Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        fill="var(--marker)"
        fillOpacity="0.35"
      />
      <circle cx="21" cy="20" r="4" fill="currentColor" />
    </svg>
  );
}
