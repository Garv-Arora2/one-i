import type { WordingPassage } from "./types";

import { wordValence, type Lean } from "./wordingLean";

export interface VerbGroup {
  /** The word this side used for the shared aspect; "" when this side used no such word. */
  verb: string;
  passages: WordingPassage[];
  valence: Lean;
  hasWord: boolean;
}

export interface WordingSplit {
  critical: VerbGroup | null;
  favourable: VerbGroup | null;
  /** The wording aspect both columns are contrasting, e.g. "action". */
  aspect: string | null;
  /** One plain sentence naming the two framings — the words are the evidence. */
  framing: string;
}

/**
 * Trivial spelling/tense swaps that must not read as a difference.
 * Mirrors the backend SYNONYM_GROUPS so both sides of the product agree on
 * what counts as "the same word".
 */
const SYNONYMS: [string, string[]][] = [
  ["say", ["said", "stated", "told"]],
  ["big", ["large"]],
  ["major", ["significant", "substantial"]],
  ["minor", ["small", "slight"]],
  ["apologise", ["apologised", "apologized", "apology"]],
  ["criticise", ["criticised", "criticized"]],
  ["begin", ["began", "started", "starts"]],
  ["halt", ["halted", "suspended", "suspend"]],
  ["kill", ["killed", "killing"]],
  ["collapse", ["collapses", "collapsed", "collapsing"]],
  ["deadly", ["fatal"]],
  ["confirm", ["confirmed", "verified"]],
  ["reportedly", ["allegedly"]],
  ["rise", ["increase"]],
  ["fall", ["decrease"]],
];

const SYNONYM_LOOKUP = new Map<string, string>();
for (const [key, words] of SYNONYMS) {
  for (const word of words) SYNONYM_LOOKUP.set(word, key);
}

function synonymKey(word: string): string {
  const lowered = word.toLowerCase();
  return SYNONYM_LOOKUP.get(lowered) ?? lowered;
}

/** Preferred order when several aspects differ: action verbs carry the event. */
const ASPECT_PRIORITY = [
  "action",
  "severity",
  "responsibility",
  "evaluation",
  "certainty",
] as const;

function signature(passage: WordingPassage, aspect: string): string {
  const words = passage.markers[aspect] ?? [];
  if (words.length === 0) return "";
  const keys = [...new Set(words.map(synonymKey))].sort();
  return keys.join("+");
}

/**
 * Two sides of the same development, contrasting the SAME wording aspect:
 * the word each outlet used for one thing (attacked vs retaliated), never
 * two unrelated words from different corners of the quotes. Outlets that
 * used no word of that kind form their own honest side ("without this
 * wording") rather than being hidden or paired against an unrelated word.
 */
export function splitForDifference(
  passages: WordingPassage[],
  differingAspects: string[] = [],
): WordingSplit {
  if (passages.length === 0) {
    return { critical: null, favourable: null, aspect: null, framing: "" };
  }
  const candidates = ASPECT_PRIORITY.filter((aspect) =>
    differingAspects.length > 0 ? differingAspects.includes(aspect) : true,
  );
  const aspects =
    candidates.length > 0
      ? candidates
      : [...new Set(differingAspects)];

  for (const aspect of aspects) {
    const groups = new Map<string, WordingPassage[]>();
    for (const passage of passages) {
      const key = signature(passage, aspect);
      const list = groups.get(key) ?? [];
      list.push(passage);
      groups.set(key, list);
    }
    if (groups.size < 2) continue;

    const columns: VerbGroup[] = [...groups.entries()].map(([key, items]) => {
      // The telling word is the one other groups do NOT share ("warned" in
      // {retaliate, warned} vs {retaliate}) — never the shared word, or both
      // columns end up named "retaliate vs retaliate".
      const keys = key === "" ? [] : key.split("+");
      const rarity = (k: string) =>
        [...groups.keys()].filter((other) =>
          other.split("+").includes(k),
        ).length;
      const telling =
        [...keys].sort((a, b) => rarity(a) - rarity(b) || a.localeCompare(b))[0] ?? "";
      return {
        verb: telling,
        passages: items,
        // Valence comes from the telling word alone. Judging the whole
        // passage lets a shared word ("retaliate" on both sides) paint both
        // columns with one valence.
        valence: key === "" ? "neither" : wordValence(telling),
        hasWord: key !== "",
      };
    });
    // Worded sides before the wordless side; bigger groups first for stability.
    columns.sort(
      (a, b) =>
        Number(b.hasWord) - Number(a.hasWord) ||
        b.passages.length - a.passages.length,
    );

    const harsh = columns.filter((c) => c.valence === "harsh");
    const softer = columns.filter((c) => c.valence === "softer");
    if (harsh.length > 0 && softer.length > 0) {
      return withFraming({ critical: harsh[0], favourable: softer[0], aspect });
    }
    const left =
      harsh[0] ?? softer[0] ?? columns.find((c) => c.hasWord) ?? columns[0];
    const right =
      columns.find((c) => c !== left && (c.valence !== left.valence || !c.hasWord || !left.hasWord)) ??
      columns.find((c) => c !== left) ??
      null;
    if (harsh.length > 0 || softer.length > 0) {
      // One valenced side exists: it keeps its column, the other side is
      // whatever contrasts with it in this same aspect.
      if (harsh.length > 0) {
        return withFraming({ critical: harsh[0], favourable: right, aspect });
      }
      return withFraming({ critical: right, favourable: softer[0], aspect });
    }
    return withFraming({ critical: left, favourable: right, aspect });
  }

  // No aspect separates the passages (synonym maps differ slightly from the
  // backend): show the shared wording as a single column rather than
  // inventing a contrast.
  const focus = aspects[0] ?? "wording";
  const firstWords = passages[0].markers[focus] ?? [];
  const shared = firstWords.length > 0 ? synonymKey(firstWords[0]) : "";
  return withFraming({
    critical: {
      verb: shared,
      passages: [passages[0]],
      valence: shared ? wordValence(shared) : "neither",
      hasWord: shared !== "",
    },
    favourable: null,
    aspect: aspects[0] ?? null,
  });
}

function leadSource(group: VerbGroup): string {
  return group.passages[0]?.source.name ?? "One outlet";
}

/**
 * One plain sentence about the two framings. The words are quoted as
 * evidence; the sentence never declares which framing is right.
 */
function withFraming(split: {
  critical: VerbGroup | null;
  favourable: VerbGroup | null;
  aspect: string | null;
}): WordingSplit {
  const { critical, favourable, aspect } = split;
  const moment = aspect ? `Same ${aspect} moment` : "Same moment";
  let framing = "";
  if (critical && favourable && critical.hasWord && favourable.hasWord) {
    const negative = critical.valence === "harsh" ? critical : favourable.valence === "harsh" ? favourable : null;
    const positive = critical.valence === "softer" ? critical : favourable.valence === "softer" ? favourable : null;
    if (negative && positive) {
      framing =
        `${moment}: ${leadSource(negative)} frames it negatively ` +
        `(\u201c${negative.verb}\u201d), ${leadSource(positive)} frames it positively ` +
        `(\u201c${positive.verb}\u201d).`;
    } else if (positive) {
      const other = positive === critical ? favourable : critical;
      framing =
        `${moment}: ${leadSource(positive)} frames it positively ` +
        `(\u201c${positive.verb}\u201d); ` +
        `${other ? leadSource(other) : "another outlet"} uses a different ` +
        `${aspect ?? "kind of"} word (\u201c${other?.verb}\u201d).`;
    } else if (negative) {
      const other = negative === critical ? favourable : critical;
      framing =
        `${moment}: ${leadSource(negative)} frames it negatively ` +
        `(\u201c${negative.verb}\u201d); ` +
        `${other ? leadSource(other) : "another outlet"} uses a different ` +
        `${aspect ?? "kind of"} word (\u201c${other?.verb}\u201d).`;
    } else {
      framing =
        `${moment}: ${leadSource(critical)} reaches for ` +
        `\u201c${critical.verb}\u201d, ${leadSource(favourable)} reaches for ` +
        `\u201c${favourable.verb}\u201d.`;
    }
  } else if (critical && favourable && (critical.hasWord || favourable.hasWord)) {
    const worded = critical.hasWord ? critical : favourable;
    const wordless = critical.hasWord ? favourable : critical;
    framing =
      `\u201c${worded?.verb}\u201d is how ${worded ? leadSource(worded) : "one outlet"} names it; ` +
      `${wordless ? leadSource(wordless) : "another outlet"} describes the same ` +
      `moment without${aspect ? ` an ${aspect}` : ""} word.`;
  } else if (critical) {
    framing = "Every outlet describes this moment in similar terms.";
  }
  return { critical, favourable, aspect, framing };
}
