# Coverage Analysis Specification

## Goal
For an event, identify important developments and determine which relevant articles/sources covered them.

## Development representation
Each event contains a chronological set of meaningful developments.

Development candidates can be identified from:
- chronology
- repeated mentions
- important entities/actions
- source agreement
- text similarity

## Coverage
An article is considered covered when there is sufficient textual evidence that it reports the development.

Methods:
- keyword/entity overlap
- TF-IDF
- cosine similarity
- simple rules
- time awareness

If evidence is insufficient, classify as unclear rather than forcing a result.

## Coverage rate
`coverage rate = developments covered / relevant developments`

## User-facing language
Use:
- Covered by
- Not covered by
- Coverage unclear

Never:
- Intentionally omitted
- Lied
- Manipulated

## Timing
Coverage is article-specific and time-aware. An outlet that publishes an update later should not be permanently labeled as having missed the development.

## Evaluation
Create a manually reviewed dataset and evaluate coverage precision, recall, and F1 where practical.
