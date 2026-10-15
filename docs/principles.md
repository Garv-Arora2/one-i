# Engineering principles

## Mission
ONE I is an event-centric news-reading and media-accountability platform. It presents the crux, context, timeline, source coverage, numerical differences, wording differences, and public reaction so the reader can judge coverage for themselves.

## Non-negotiable principle
**Show the difference. Let the user decide.**

Never claim that an outlet is biased, dishonest, intentionally misleading, or intentionally omitting information unless a separately approved methodology can establish that claim. Prefer observable evidence over interpretation.

## V1 scope
In scope:
- Crux and context
- Timeline
- Numerical differences
- Wording/framing differences
- Event coverage: covered by / not covered by
- Simple media coverage overview
- Most-liked relevant public comments (YouTube, Reddit)
- Original source links
- Google sign-in, with optional CAPTCHA

Deliberately out of scope:
- language-model analysis
- bias scores
- fake-account or coordinated-manipulation detection
- intent or propaganda detection
- political ideology classification
- custom deep-learning systems
- microservices or infrastructure the product does not need

If a feature cannot be explained and defended simply, it is simplified or removed.

## Stack
- Frontend: Next.js, React, TypeScript
- Backend: FastAPI, Python
- Database: PostgreSQL
- Analysis: Pandas, NumPy, scikit-learn, classical NLP and statistics

Prefer deterministic rules, TF-IDF, cosine similarity, entity/keyword matching, and straightforward statistical calculations.

## Architecture
A modular monolith.

```
External sources -> ingestion -> cleaning/normalisation -> PostgreSQL
  -> analysis -> stored results -> FastAPI -> Next.js -> reader
```

The frontend never accesses PostgreSQL directly and never performs core analysis.

## Data integrity
Preserve source, article, URL, publication time, retrieval time, and original values and text. Keep raw data separate from processed data and analysis results. Never fabricate missing information.

## Coverage
Use simple, explainable matching. When evidence is insufficient, say "Coverage unclear" rather than forcing a yes/no decision. Use "Not covered", never "Intentionally omitted".

## Numbers
Only compare numerical claims whose subject, unit, time period, and context match. Casualty figures also keep who was affected (civilians, soldiers, children) and whether the figure is a single incident or a running war total.

## Wording
Compare passages that refer to the same development. Preserve the source's actual wording. Focus on meaningful differences in action, responsibility, severity, certainty, or evaluation, never a generic sentiment or bias score.

## Public reaction
Reddit and YouTube are public discussion, not factual authority. Show only the most-liked comments that are about the event.

## Market impact (V2)
Not shown in V1. The backend groundwork (price data, return and benchmark calculations) is kept for V2. When it returns: show it only when relevant, use price return, benchmark comparison and volume, and never claim causation from timing alone.

## UI
An investigative editorial publication with a playful, curious identity. No SaaS dashboard aesthetics: no neon, gradients, glassmorphism, bento grids, decorative blobs, icon spam, or animation spam.

- Landing: playful -> mysterious -> investigative, with the doodle investigator and the eye/magnifying glass.
- Front page: editorial, a large lead story plus smaller events; no categories, personalisation, or search.
- Event page: an investigation with progressive disclosure.

Use plain language in the UI and avoid unnecessary technical terms.

## Working rules
- Read the relevant spec and the existing code before changing anything.
- Make the smallest change that satisfies the spec; do not invent requirements.
- Each phase is implemented, tested, and verified before the next one starts.
- If documents conflict, resolve the conflict explicitly rather than silently choosing a new design.

## Testing
Test core data processing, coverage, numerical comparison, wording comparison, API behaviour, and important UI states.

## Final rule
Prefer a simple, reliable, measurable, maintainable solution over a technically impressive one that cannot be defended.
