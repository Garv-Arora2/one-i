/**
 * The ONE I doodle investigator: a hand-drawn figure holding a magnifying
 * glass with an eye inside it. Class names are passed in so the landing page
 * owns the motion.
 */

export function Investigator({
  className,
  glassClassName,
  pupilClassName,
  trailClassName,
}: {
  className?: string;
  glassClassName?: string;
  pupilClassName?: string;
  trailClassName?: string;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 340 380"
      role="img"
      aria-label="An investigator looking through a magnifying glass with an eye inside it"
      fill="none"
      stroke="currentColor"
      strokeWidth="3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {/* footprints leading in */}
      <g className={trailClassName} stroke="var(--rule-strong)" strokeWidth="2.5">
        <path d="M18 348c6-3 12-3 17 0" />
        <path d="M44 332c6-3 12-3 17 0" />
        <path d="M70 350c6-3 12-3 17 0" />
      </g>

      {/* hat */}
      <path d="M96 96c18-8 90-8 108 0" />
      <path d="M118 96c-2-26 4-44 32-46 28 2 34 20 32 46" />
      <path d="M120 78c20 6 40 6 60 0" stroke="var(--accent)" />

      {/* head and collar */}
      <circle cx="150" cy="122" r="27" />
      <path d="M128 140c14 10 30 10 44 0" />

      {/* coat */}
      <path d="M110 200c0-42 16-56 40-58 24 2 40 16 40 58l4 78h-88Z" />
      <path d="M150 146v74" />
      <path d="M126 206h-8" stroke="var(--rule-strong)" />

      {/* legs */}
      <path d="M130 278l-5 62" />
      <path d="M172 278l6 62" />
      <path d="M116 340h20" />
      <path d="M170 340h20" />

      {/* arm reaching for the glass */}
      <path d="M188 172c26 4 44 18 54 30" />

      {/* magnifying glass with an eye inside */}
      <g className={glassClassName}>
        <path d="M240 250l-22 26" strokeWidth="8" stroke="var(--ink-soft)" />
        <circle cx="262" cy="222" r="42" strokeWidth="4" />
        <path
          d="M228 222c10-15 58-15 68 0-10 15-58 15-68 0Z"
          fill="var(--marker)"
          fillOpacity="0.28"
          strokeWidth="2.6"
        />
        <circle className={pupilClassName} cx="262" cy="222" r="10" fill="currentColor" stroke="none" />
        <path d="M238 196c6-6 14-9 22-10" strokeWidth="2" stroke="var(--rule-strong)" />
      </g>
    </svg>
  );
}
