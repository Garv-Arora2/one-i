import Link from "next/link";

export const metadata = {
  title: "Not found",
};

export default function NotFound() {
  return (
    <div
      style={{
        maxWidth: "44rem",
        margin: "0 auto",
        padding: "clamp(3rem, 8vw, 5rem) var(--gutter)",
      }}
    >
      <p className="kicker kicker-accent">Nothing here</p>
      <h1>This page could not be found</h1>
      <p className="standfirst">
        The event or source you asked for is not in ONE I. It may never have
        been gathered, or the address may be wrong.
      </p>
      <p style={{ marginTop: "2rem" }}>
        <Link href="/events" className="button">
          Go to the front page
        </Link>
      </p>
    </div>
  );
}
