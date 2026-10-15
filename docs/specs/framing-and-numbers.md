# Wording and Numbers Specification

## Numbers

### Goal
Show meaningful differences between equivalent numerical claims.

Store:
- value
- unit
- subject
- time period/context
- source
- article

Only compare claims when subject, unit, time period, and context sufficiently match.

Distinguish percentage points from percentage change.

Example:
Source A: 30%
Source B: 20%
Difference: 10 percentage points

Never compare unrelated numbers merely because the numeric value or unit is the same.

## Wording

### Goal
Identify materially different descriptions of the same development.

Prioritize differences involving:
- responsibility
- action
- severity
- certainty
- evaluation

Example:
Source A: "Government admitted responsibility."
Source B: "Government responded to allegations."
Source C: "Government mishandled the situation."

The system should preserve the actual source wording and show enough surrounding context to avoid misleading extraction.

## Method
- clean text
- identify entities and important sentences
- group passages around the same development
- extract important verbs/adjectives/phrases
- compare wording with similarity and simple linguistic rules
- display only meaningful differences

Trivial synonyms should not be flagged.

## What not to do
Do not assign outlet-wide bias scores, political labels, intent, or moral judgments.

## Evaluation
Use manually reviewed examples of meaningful differences, trivial differences, and unrelated passages.
