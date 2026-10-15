/** Formatting helpers. Reader-facing language, no technical vocabulary. */

import type { CoverageStatus } from "./types";

const DATE = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "long",
  year: "numeric",
  timeZone: "UTC",
});

const DATE_TIME = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
});

export function formatDate(value: string | null | undefined): string {
  if (!value) return "Date not recorded";
  return DATE.format(new Date(value));
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "Time not recorded";
  return `${DATE_TIME.format(new Date(value))} UTC`;
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
): string {
  if (value === null || value === undefined) return "not available";
  return `${value > 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

export function formatShare(value: number | null | undefined): string {
  if (value === null || value === undefined) return "not available";
  return `${Math.round(value * 100)}%`;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return "not available";
  return new Intl.NumberFormat("en-GB").format(value);
}

/** Reader-facing wording for a coverage state. Never accusatory. */
export const COVERAGE_LABEL: Record<CoverageStatus, string> = {
  covered: "Reported",
  unclear: "Coverage unclear",
  not_covered: "Not reported",
  not_applicable: "Published earlier",
};

export const COVERAGE_EXPLANATION: Record<CoverageStatus, string> = {
  covered: "This source reported this development.",
  unclear:
    "There is not enough overlap to say either way, so ONE I does not decide for you.",
  not_covered:
    "This development was not found in what this source published about the event.",
  not_applicable:
    "This article was published before this development happened, so it could not have reported it.",
};

/** Tick/cross marks; colour is applied in the matrix CSS. */
export const COVERAGE_MARK: Record<CoverageStatus, string> = {
  covered: "✓",
  unclear: "?",
  not_covered: "✕",
  not_applicable: "–",
};

export const ASPECT_LABEL: Record<string, string> = {
  responsibility: "who is held responsible",
  action: "what was done",
  severity: "how serious it sounds",
  certainty: "how certain it sounds",
  evaluation: "how it is judged",
};

/** Sentence-cases a phrase for display without altering the words. */
export function sentenceCase(value: string): string {
  if (!value) return value;
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export function joinWithAnd(items: string[]): string {
  if (items.length === 0) return "";
  if (items.length === 1) return items[0];
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export function platformLabel(platform: string): string {
  if (platform === "reddit") return "Reddit";
  if (platform === "youtube") return "YouTube";
  return platform;
}
