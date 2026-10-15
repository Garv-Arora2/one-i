"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { PUBLIC_API_BASE_URL, SESSION_CHANGED_EVENT } from "@/lib/api";
import type { SessionResponse } from "@/lib/types";

import { EyeMark } from "./EyeMark";
import styles from "./Masthead.module.css";

function useSession(): SessionResponse | null {
  const [session, setSession] = useState<SessionResponse | null>(null);
  useEffect(() => {
    const load = () =>
      fetch(`${PUBLIC_API_BASE_URL}/auth/me`, { credentials: "include", cache: "no-store" })
        .then((response) => (response.ok ? response.json() : null))
        .then(setSession)
        .catch(() => setSession(null));
    load();
    window.addEventListener(SESSION_CHANGED_EVENT, load);
    return () => window.removeEventListener(SESSION_CHANGED_EVENT, load);
  }, []);
  return session;
}

export function Masthead() {
  const pathname = usePathname();
  const session = useSession();
  const user = session?.authenticated ? session.user : null;
  const accountLabel = user ? (user.name ?? user.email).split(" ")[0] : "Sign in";
  const NAV = [
    { href: "/home",    label: "Front page" },
    { href: "/sources", label: "Sources" },
    { href: "/sign-in", label: user ? "Account" : "Sign in" },
  ];
  const today = new Date().toLocaleDateString("en-GB", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });

  return (
    <header>
      {/* Top bar: date + utility links */}
      <div className={styles.topBar}>
        <div className={styles.topBarInner}>
          <span className={styles.topBarLeft}>{today}</span>
          <nav className={styles.topBarRight} aria-label="Utility">
            <Link href="/sources">Sources</Link>
            <Link
              href="/sign-in"
              className={styles.signIn}
              title={user ? `Signed in as ${user.email}` : undefined}
            >
              {user ? `Signed in · ${accountLabel}` : accountLabel}
            </Link>
          </nav>
        </div>
      </div>

      {/* Brand row */}
      <div className={styles.brand}>
        <div className={styles.brandInner}>
          <Link href="/" className={styles.wordmark}>
            <EyeMark size={22} />
            <span className={styles.wordmarkText}>ONE I</span>
          </Link>
          <span className={styles.tagline}>Coverage examined</span>
        </div>
      </div>

      {/* Section nav */}
      <nav className={styles.nav} aria-label="Sections">
        <div className={styles.navInner}>
          {NAV.map((item) => {
            const active =
              item.href === "/home"
                ? pathname === "/home" ||
                  pathname === "/events" ||
                  pathname.startsWith("/events/")
                : pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`${styles.navLink} ${active ? styles.navActive : ""}`}
              >
                {item.label}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
