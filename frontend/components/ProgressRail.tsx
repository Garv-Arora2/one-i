"use client";

import { useEffect, useState } from "react";

import styles from "./ProgressRail.module.css";

export interface RailStop {
  id: string;
  label: string;
  accent?: boolean;
}

/**
 * Sticky progress rail for the event page. Tracks which section is in view
 * and highlights the matching stop — both navigation and a sense of progress
 * through the investigation.
 */
export function ProgressRail({ stops }: { stops: RailStop[] }) {
  const [activeId, setActiveId] = useState<string | null>(null);

  useEffect(() => {
    const sections = stops
      .map((s) => document.getElementById(s.id))
      .filter((el): el is HTMLElement => el !== null);
    if (sections.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        // Pick the top-most visible section.
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length > 0) {
          setActiveId(visible[0].target.id);
        }
      },
      { rootMargin: "-15% 0px -60% 0px", threshold: 0 },
    );

    for (const el of sections) observer.observe(el);
    return () => observer.disconnect();
  }, [stops]);

  return (
    <nav className={styles.rail} aria-label="Sections of this investigation">
      <p className={styles.railTitle}>In this investigation</p>
      <ol className={styles.list}>
        {stops.map((stop) => {
          const active = stop.id === activeId;
          return (
            <li key={stop.id}>
              <a
                href={`#${stop.id}`}
                className={[
                  styles.stop,
                  active ? styles.stopActive : "",
                  stop.accent ? styles.stopAccent : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                aria-current={active ? "true" : undefined}
              >
                {stop.label}
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
