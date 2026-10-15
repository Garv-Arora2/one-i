"use client";

import { useMemo, useState, useSyncExternalStore } from "react";

import styles from "./CoveragePoll.module.css";

const QUESTIONS = [
  {
    id: "complete",
    prompt: "From what you’ve read here, how complete does the coverage look?",
    options: [
      { id: "most", label: "Most of the story is in the reports" },
      { id: "thin", label: "Some important parts look thin" },
      { id: "unsure", label: "Hard to tell from this" },
    ],
  },
  {
    id: "agree",
    prompt: "Do you agree with how the reports described this event?",
    options: [
      { id: "yes", label: "Yes" },
      { id: "partly", label: "Partly — the emphasis differs" },
      { id: "no", label: "No" },
    ],
  },
  {
    id: "public",
    prompt: "Does the public discussion match what the reports said?",
    options: [
      { id: "match", label: "Mostly the same ground" },
      { id: "else", label: "People are talking about different things" },
      { id: "unsure", label: "Not sure" },
    ],
  },
] as const;

type Answers = Record<string, string>;

const noSubscription = () => () => {};

function readStored(storageKey: string): string | null {
  try {
    return localStorage.getItem(storageKey);
  } catch {
    return null;
  }
}

function parseAnswers(raw: string | null): Answers {
  if (!raw) return {};
  try {
    return JSON.parse(raw) as Answers;
  } catch {
    return {};
  }
}

export function CoveragePoll({ eventSlug }: { eventSlug: string }) {
  const storageKey = `one-i-poll:${eventSlug}`;
  const storedRaw = useSyncExternalStore(
    noSubscription,
    () => readStored(storageKey),
    () => null,
  );
  const stored = useMemo(() => parseAnswers(storedRaw), [storedRaw]);
  const [draft, setDraft] = useState<Answers>({});
  const [justSubmitted, setJustSubmitted] = useState(false);
  const answers: Answers = { ...stored, ...draft };
  const submitted = justSubmitted || Object.keys(stored).length === QUESTIONS.length;

  function choose(questionId: string, optionId: string) {
    if (submitted) return;
    setDraft((prev) => ({ ...prev, [questionId]: optionId }));
  }

  function submit() {
    if (QUESTIONS.some((q) => !answers[q.id])) return;
    try {
      localStorage.setItem(storageKey, JSON.stringify(answers));
    } catch {
      /* ignore */
    }
    setJustSubmitted(true);
  }

  const ready = QUESTIONS.every((q) => answers[q.id]);

  return (
    <div className={styles.wrap}>
      <p className={styles.kicker}>Your reading</p>
      <h3 className={styles.title}>What do you make of this coverage?</h3>
      <p className={styles.note}>
        Three questions, your answers only. They stay on this device. ONE I
        does not score the outlets from your vote.
      </p>

      {QUESTIONS.map((q) => (
        <fieldset key={q.id} className={styles.q} disabled={submitted}>
          <legend className={styles.prompt}>{q.prompt}</legend>
          <div className={styles.options}>
            {q.options.map((opt) => {
              const on = answers[q.id] === opt.id;
              return (
                <button
                  key={opt.id}
                  type="button"
                  className={`${styles.opt} ${on ? styles.optOn : ""}`}
                  aria-pressed={on}
                  onClick={() => choose(q.id, opt.id)}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </fieldset>
      ))}

      {!submitted ? (
        <button
          type="button"
          className={styles.submit}
          disabled={!ready}
          onClick={submit}
        >
          Record my reading
        </button>
      ) : (
        <p className={styles.thanks}>
          Recorded on this device. Reload the page and the answers will still
          be here — they are not sent to ONE I.
        </p>
      )}
    </div>
  );
}
