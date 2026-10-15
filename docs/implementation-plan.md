# ONE I Master Implementation Plan

## Objective
Build ONE I V1 as a clean, modular, interview-defensible product.

## Execution rule
Build one phase at a time:
1. Read the relevant docs.
2. Inspect the existing code.
3. Plan the phase.
4. Implement only that phase.
5. Test and verify it.
6. Move on only when the phase is done.

If documentation conflicts, resolve the conflict before continuing.

## Phase 0: Foundation
Set up repository, Next.js, TypeScript, FastAPI, Python environment, PostgreSQL, environment variables, formatting/linting, and basic health checks.

Done when frontend/backend start and database connection is verified.

## Phase 1: Database
Implement the minimum schema from `docs/database.md`, migrations, constraints, and seed data.

Done when a sample event with sources/articles/developments can be stored and retrieved.

## Phase 2: Backend models
Create clear database models and API schemas. Keep database models separate from public API schemas.

## Phase 3: News ingestion
Implement broad news API/RSS ingestion plus controlled source tracking. Normalize, validate, deduplicate, and store articles.

## Phase 4: Event grouping
Use time proximity, entities, TF-IDF, cosine similarity, and simple rules. No LLM/deep learning.

Create a small manually labeled test set.

## Phase 5: Development identification
Create meaningful chronological developments using repeated mentions, entities/actions, chronology, and source agreement.

If automatic identification proves unreliable, simplify the method.

## Phase 6: Coverage
Map articles to developments with explainable matching. Calculate coverage rates. Handle unclear cases explicitly.

## Phase 7: Numbers
Extract numerical observations, match equivalent claims using subject/unit/time/context, and calculate differences.

## Phase 8: Wording
Identify comparable passages and meaningful wording differences. Preserve original wording and surrounding context.

## Phase 9: Crux
Build a structured deterministic Crux from verified event data. No LLM.

## Phase 10: Public reaction
Integrate Reddit/YouTube data, clean/deduplicate, associate with events, and produce simple discussion aggregates.

## Phase 11: Market impact (moved to V2)
Backend groundwork only; not shown in the V1 site. Integrate market data for relevant events. Calculate return, benchmark comparison, and volume changes using predefined windows.

## Phase 12: FastAPI
Expose event, timeline, coverage, comparison, reaction, market, and source endpoints. Serve stored results instead of doing expensive analysis during page requests.

## Phase 13: Authentication
Add Google login + CAPTCHA using established services. Do not implement custom password/OAuth storage.

## Phase 14: Frontend foundation
Implement ONE I design system: typography, spacing, color, responsive behavior, editorial layout primitives, expandable sections.

## Phase 15: Landing
Build the doodle investigator, eye/magnifying glass motif, playful-to-mysterious-to-investigative motion, branding, statement/quote, and entry transition.

## Phase 16: Homepage
Build large lead event + smaller event list. No categories, personalization, or search.

## Phase 17: Event page
Build:
Crux -> Context -> Timeline -> How it was covered -> Wording + Numbers -> Public Reaction -> Sources. (Market impact is planned for V2.)

Use progressive disclosure.

## Phase 18: Neutrality audit
Check colors, badges, ordering, typography, labels, and copy for accidental good/bad outlet signaling.

## Phase 19: Testing
Backend unit tests, API tests, analysis tests, frontend interaction tests, responsive checks, missing-data states.

## Phase 20: End-to-end golden event
Run one complete real event through ingestion -> database -> analysis -> API -> frontend.

## Phase 21: Evaluation
Build a 50-100 article manually reviewed evaluation set for event grouping, developments, coverage, number equivalence, and wording differences. Document failures and limitations.

## Phase 22: UI refinement
Critique the rendered product. Improve hierarchy, spacing, typography, density, readability, responsiveness, and interaction clarity without changing product scope.

## Phase 23: Deployment
Deploy frontend, backend, and PostgreSQL. Configure secrets, environment variables, logging, and production data sources.

## Definition of done
The complete flow works, the core analyses are testable, original sources are accessible, authentication works, the UI follows `docs/design.md`, and all documentation matches the implementation.

## Priority
Correctness -> clarity -> explainability -> maintainability -> visual quality.

Never optimize for technical impressiveness at the expense of defensibility.
