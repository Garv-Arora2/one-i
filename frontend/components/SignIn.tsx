"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { PUBLIC_API_BASE_URL, SESSION_CHANGED_EVENT } from "@/lib/api";
import type { AuthConfig, SessionResponse } from "@/lib/types";

import { Notice } from "./Notice";
import styles from "./SignIn.module.css";

const GOOGLE_CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID ?? "";
const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY ?? "";
const RECAPTCHA_SITE_KEY = process.env.NEXT_PUBLIC_RECAPTCHA_SITE_KEY ?? "";

interface GoogleIdentityApi {
  accounts: {
    id: {
      initialize: (options: {
        client_id: string;
        callback: (response: { credential: string }) => void;
      }) => void;
      renderButton: (
        element: HTMLElement,
        options: Record<string, string | number>,
      ) => void;
    };
  };
}

declare global {
  interface Window {
    google?: GoogleIdentityApi;
    turnstile?: {
      render: (
        element: HTMLElement,
        options: {
          sitekey: string;
          callback: (token: string) => void;
          "expired-callback"?: () => void;
        },
      ) => string;
    };
    grecaptcha?: {
      ready: (callback: () => void) => void;
      render: (
        element: HTMLElement,
        options: { sitekey: string; callback: (token: string) => void },
      ) => number;
    };
  }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement("script");
    script.src = src;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Could not load ${src}`));
    document.head.appendChild(script);
  });
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${PUBLIC_API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : `Request failed (${response.status})`;
    throw new Error(detail);
  }
  window.dispatchEvent(new Event(SESSION_CHANGED_EVENT));
  return data as T;
}

export function SignIn({ config }: { config: AuthConfig | null }) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const googleSlot = useRef<HTMLDivElement>(null);
  const captchaSlot = useRef<HTMLDivElement>(null);

  const captchaNeeded = Boolean(config?.captcha_configured);
  const captchaReady = !captchaNeeded || Boolean(captchaToken);

  useEffect(() => {
    fetch(`${PUBLIC_API_BASE_URL}/auth/me`, { credentials: "include" })
      .then((response) => response.json())
      .then(setSession)
      .catch(() => setSession({ authenticated: false, user: null }));
  }, []);

  const signInWithGoogle = useCallback(
    async (credential: string) => {
      setBusy(true);
      setError(null);
      try {
        const result = await postJson<SessionResponse>("/auth/google", {
          credential,
          captcha_token: captchaToken,
        });
        setSession(result);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Sign-in failed.");
      } finally {
        setBusy(false);
      }
    },
    [captchaToken],
  );

  // The Google button must re-render whenever the captcha token changes, so the
  // credential callback always closes over a fresh token.
  useEffect(() => {
    if (!config?.google_configured || !GOOGLE_CLIENT_ID) return;
    if (session?.authenticated) return;
    let cancelled = false;

    loadScript("https://accounts.google.com/gsi/client")
      .then(() => {
        if (cancelled || !googleSlot.current) return;
        const identity = window.google;
        if (!identity) return;
        identity.accounts.id.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => void signInWithGoogle(response.credential),
        });
        googleSlot.current.innerHTML = "";
        identity.accounts.id.renderButton(googleSlot.current, {
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "rectangular",
          width: 280,
        });
      })
      .catch(() => setError("Google sign-in could not be loaded."));

    return () => {
      cancelled = true;
    };
  }, [config?.google_configured, session?.authenticated, signInWithGoogle]);

  useEffect(() => {
    if (!captchaNeeded || session?.authenticated) return;
    const provider = config?.captcha_provider;
    let cancelled = false;

    if (provider === "turnstile" && TURNSTILE_SITE_KEY) {
      loadScript(
        "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit",
      )
        .then(() => {
          if (cancelled || !captchaSlot.current || !window.turnstile) return;
          captchaSlot.current.innerHTML = "";
          window.turnstile.render(captchaSlot.current, {
            sitekey: TURNSTILE_SITE_KEY,
            callback: setCaptchaToken,
            "expired-callback": () => setCaptchaToken(null),
          });
        })
        .catch(() => setError("The verification check could not be loaded."));
    } else if (provider === "recaptcha" && RECAPTCHA_SITE_KEY) {
      loadScript("https://www.google.com/recaptcha/api.js?render=explicit")
        .then(() => {
          if (cancelled || !captchaSlot.current || !window.grecaptcha) return;
          window.grecaptcha.ready(() => {
            if (!captchaSlot.current || !window.grecaptcha) return;
            captchaSlot.current.innerHTML = "";
            window.grecaptcha.render(captchaSlot.current, {
              sitekey: RECAPTCHA_SITE_KEY,
              callback: setCaptchaToken,
            });
          });
        })
        .catch(() => setError("The verification check could not be loaded."));
    }

    return () => {
      cancelled = true;
    };
  }, [captchaNeeded, config?.captcha_provider, session?.authenticated]);

  const signOut = async () => {
    setBusy(true);
    try {
      const result = await postJson<SessionResponse>("/auth/logout", {});
      setSession(result);
      setCaptchaToken(null);
    } catch {
      setError("Could not sign out.");
    } finally {
      setBusy(false);
    }
  };

  const devSignIn = async (formData: FormData) => {
    setBusy(true);
    setError(null);
    try {
      const result = await postJson<SessionResponse>("/auth/dev-login", {
        email: String(formData.get("email") ?? ""),
        name: "Local tester",
      });
      setSession(result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  };

  if (!config) {
    return (
      <Notice title="The sign-in service is not responding">
        <p>
          Start the ONE I API with <code>uvicorn app.main:app --reload</code>{" "}
          and reload this page.
        </p>
      </Notice>
    );
  }

  if (session?.authenticated && session.user) {
    return (
      <div className={styles.panel}>
        <p className={styles.signedIn}>
          <span className={styles.signedInName}>
            {session.user.name ?? session.user.email}
          </span>
          Signed in as {session.user.email}
        </p>
        <button
          type="button"
          className="button button-quiet"
          style={{ marginTop: "1rem" }}
          onClick={signOut}
          disabled={busy}
        >
          Sign out
        </button>
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      {captchaNeeded ? (
        <div className={styles.step}>
          <p className={styles.stepLabel}>First, confirm you are a person</p>
          <div ref={captchaSlot} className={styles.slot} />
        </div>
      ) : null}

      <div className={styles.step}>
        <p className={styles.stepLabel}>
          {captchaNeeded ? "Then, continue with Google" : "Continue with Google"}
        </p>
        {config.google_configured && GOOGLE_CLIENT_ID ? (
          <>
            <div
              ref={googleSlot}
              className={styles.slot}
              style={{ opacity: captchaReady ? 1 : 0.45 }}
            />
            {!captchaReady ? (
              <p className={styles.hint}>
                Complete the check above and the Google button becomes usable.
              </p>
            ) : null}
          </>
        ) : (
          <p className={styles.hint}>{config.message}</p>
        )}
      </div>

      {config.dev_bypass_enabled ? (
        <div className={styles.step}>
          <p className={styles.stepLabel}>Local development sign-in</p>
          <form action={devSignIn} className={styles.devForm}>
            <input
              className={styles.devInput}
              type="email"
              name="email"
              required
              placeholder="you@example.com"
              aria-label="Email for local sign-in"
            />
            <button type="submit" className="button" disabled={busy}>
              Sign in locally
            </button>
          </form>
          <p className={styles.hint}>
            Available only because this server runs with the development bypass
            enabled. It is refused in production.
          </p>
        </div>
      ) : null}

      {error ? <p className={styles.error}>{error}</p> : null}
    </div>
  );
}
