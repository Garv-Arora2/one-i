import type { WordingPassage } from "./types";

const ASPECT_PRIORITY = [
  "action",
  "responsibility",
  "severity",
  "certainty",
  "evaluation",
] as const;

const STOPWORDS = new Set(
  `
a an the and or but if of to in on for at as by with from into over after before
said says say that this those these was were is are be been being it its they
their them he she we you i not no also than then so such about into during
sunday monday tuesday wednesday thursday friday saturday evening morning afternoon
earlier later today yesterday overnight near close almost still just already
once next year years month months week weeks day days hours hour
  `.trim().split(/\s+/),
);

function tokenize(text: string): string[] {
  return text.toLowerCase().match(/[a-z]+(?:'[a-z]+)?/g) ?? [];
}

function verbish(word: string): number {
  if (/(ed|ing)$/.test(word)) return 3;
  if (word.length > 4 && /(es|s)$/.test(word)) return 2;
  return 1;
}

function othersMissing(
  word: string,
  passage: WordingPassage,
  all: WordingPassage[],
  aspect?: string,
): number {
  const needle = word.toLowerCase();
  return all.filter((other) => {
    if (other.source.id === passage.source.id) return false;
    const pool = aspect
      ? (other.markers[aspect] ?? [])
      : Object.values(other.markers).flat();
    return !pool.some((w) => w.toLowerCase() === needle);
  }).length;
}

/** Words this passage marked that not every other passage also marked. */
export function distinctiveWords(
  passage: WordingPassage,
  all: WordingPassage[],
): string[] {
  const own = new Set(
    Object.values(passage.markers).flat().map((w) => w.toLowerCase()),
  );
  if (own.size === 0) return [];

  const others = all.filter((p) => p.source.id !== passage.source.id);
  if (others.length === 0) return [...own];

  const unique = [...own].filter(
    (word) =>
      !others.every((other) =>
        Object.values(other.markers)
          .flat()
          .some((w) => w.toLowerCase() === word),
      ),
  );
  return unique.length > 0 ? unique : [...own];
}

/**
 * The word this outlet used that the others did not — "attacked" vs "retaliated".
 * Falls back to a distinctive token in the quote when markers are empty.
 */
export function contrastWord(
  passage: WordingPassage,
  all: WordingPassage[],
): string {
  const scored: { word: string; score: number }[] = [];

  for (const aspect of ASPECT_PRIORITY) {
    for (const word of passage.markers[aspect] ?? []) {
      const missing = othersMissing(word, passage, all, aspect);
      scored.push({
        word: word.toLowerCase(),
        score:
          missing * 10 +
          verbish(word.toLowerCase()) +
          (aspect === "action" ? 5 : 0) +
          word.length / 10,
      });
    }
  }

  scored.sort((a, b) => b.score - a.score);
  const bestMarked = scored.find((item) => !STOPWORDS.has(item.word));
  if (bestMarked && (bestMarked.score >= 15 || verbish(bestMarked.word) >= 3)) {
    return bestMarked.word;
  }

  const others = all.filter((p) => p.source.id !== passage.source.id);
  const otherTokens = new Set(others.flatMap((o) => tokenize(o.quoted_text)));
  const own = tokenize(passage.quoted_text).filter(
    (t) => t.length > 3 && !STOPWORDS.has(t),
  );
  const unique = own.filter((t) => !otherTokens.has(t));
  const candidates = (unique.length > 0 ? unique : own)
    .map((word) => ({ word, score: verbish(word) + word.length / 10 }))
    .sort((a, b) => b.score - a.score);

  const fallback = candidates.find((item) => verbish(item.word) >= 2);
  return fallback?.word ?? bestMarked?.word ?? "this wording";
}

export function contrastLabel(words: string[]): string {
  if (words.length === 0) return "This wording";
  return words[0];
}

export function groupByContrastWord(
  passages: WordingPassage[],
): { verb: string; passages: WordingPassage[] }[] {
  const groups = new Map<string, WordingPassage[]>();
  for (const passage of passages) {
    const verb = contrastWord(passage, passages);
    const list = groups.get(verb) ?? [];
    list.push(passage);
    groups.set(verb, list);
  }
  return [...groups.entries()].map(([verb, items]) => ({
    verb,
    passages: items,
  }));
}
