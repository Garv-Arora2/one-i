"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Investigator } from "./Investigator";
import styles from "@/app/landing.module.css";

/**
 * The ONE I landing: three beats — playful, mysterious, investigative.
 *
 * Beat 2's headlines are hardcoded demo copy chosen to look like real
 * coverage of the same event. TODO: drive these from an actual wording
 * comparison in the dataset once the API exposes a suitable preview.
 */

/** The eye-as-"I": a magnifying glass whose pupil follows the cursor. */
function TrackingEye({ size }: { size: number }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [offset, setOffset] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;

    function onMove(e: MouseEvent) {
      const rect = el!.getBoundingClientRect();
      const cx = rect.left + rect.width * 0.44;
      const cy = rect.top + rect.height * 0.42;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy) || 1;
      // Cap the pupil travel so it stays inside the iris.
      const cap = 3.5;
      setOffset({
        x: (dx / dist) * Math.min(cap, dist / 40),
        y: (dy / dist) * Math.min(cap, dist / 40),
      });
    }

    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  return (
    <svg
      ref={svgRef}
      width={size}
      height={size}
      viewBox="0 0 48 48"
      role="img"
      aria-label="I"
      fill="none"
      className={styles.eyeWrap}
    >
      <circle cx="21" cy="20" r="15" stroke="currentColor" strokeWidth="2.4" />
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
      />
      <circle
        cx={21 + offset.x}
        cy={20 + offset.y}
        r="4"
        fill="currentColor"
      />
    </svg>
  );
}

/** Small magnifying glass used for the Beat 2 sweep. */
function Magnifier({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" fill="none" className={className} aria-hidden="true">
      <circle cx="21" cy="20" r="15" stroke="currentColor" strokeWidth="3" />
      <path
        d="M32 31 L43 43"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Landing() {
  const [investigatorIn, setInvestigatorIn] = useState(false);
  const [beat2Active, setBeat2Active] = useState(false);
  const beat2Ref = useRef<HTMLElement>(null);

  // Beat 1: investigator slides in shortly after load.
  useEffect(() => {
    const t = setTimeout(() => setInvestigatorIn(true), 400);
    return () => clearTimeout(t);
  }, []);

  // Beat 2: run the magnifier sweep + highlight when the section scrolls in.
  useEffect(() => {
    const el = beat2Ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setBeat2Active(true);
          observer.disconnect();
        }
      },
      { threshold: 0.55 },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  return (
    <div className={styles.landing}>
      {/* ── Beat 1 — playful ─────────────────────────────────────────── */}
      <section className={styles.beat1} aria-label="ONE I">
        <div className={styles.wordmark}>
          <span className={styles.wordmarkText}>ONE</span>
          <TrackingEye size={Math.min(180, 140)} />
        </div>

        <div
          className={`${styles.investigator} ${investigatorIn ? styles.investigatorIn : ""}`}
        >
          <Investigator />
        </div>

        <p className={styles.beat1Sub}>Coverage examined</p>
      </section>

      {/* ── Beat 2 — mysterious ──────────────────────────────────────── */}
      <section
        ref={beat2Ref}
        className={styles.beat2}
        aria-label="Same event, different accounts"
      >
        <div className={styles.beat2Inner}>
          <p className={styles.beat2Kicker}>Same event. Two front pages.</p>

          <div className={styles.headlines}>
            <p className={`${styles.headline} ${styles.headlineLeft}`}>
              <span className={styles.headlineSource}>Outlet A</span>
              Council{" "}
              <span
                className={`${styles.diffWord} ${beat2Active ? styles.diffWordLit : ""}`}
              >
                approves
              </span>{" "}
              housing plan
            </p>

            <span className={styles.headlineDivider} aria-hidden="true" />

            <p className={`${styles.headline} ${styles.headlineRight}`}>
              <span className={styles.headlineSource}>Outlet B</span>
              Residents{" "}
              <span
                className={`${styles.diffWord} ${beat2Active ? styles.diffWordLit : ""}`}
              >
                protest
              </span>{" "}
              housing plan
            </p>

            <Magnifier
              className={`${styles.magnifier} ${beat2Active ? styles.magnifierSweep : ""}`}
            />
          </div>

          <p
            className={`${styles.beat2Note} ${beat2Active ? styles.beat2NoteIn : ""}`}
          >
            Both are true. Each tells a different story.
          </p>
        </div>
      </section>

      {/* ── Beat 3 — investigative ───────────────────────────────────── */}
      <section className={styles.beat3} aria-label="What ONE I does">
        <h1 className={styles.statement}>
          Show the difference.{" "}
          <span className={styles.statementAccent}>Let the user decide.</span>
        </h1>

        <Link href="/home" className={styles.cta}>
          See today&rsquo;s coverage <span aria-hidden="true">→</span>
        </Link>

        <p className={styles.signIn}>
          <Link href="/sign-in">Sign in</Link> if you have an account — not
          required to read.
        </p>
      </section>
    </div>
  );
}
