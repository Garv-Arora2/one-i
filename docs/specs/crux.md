# Crux Specification

## Goal
Give the reader a concise, evidence-based understanding of what happened.

## Structure
The Crux is built from structured event information:
- what happened
- who
- when
- where
- key developments
- important numbers
- current status

## V1 method
Use deterministic templates/rules over verified structured event data. Do not use an LLM.

A Crux may exceed roughly 200 words only when the event genuinely requires additional structured context.

## Traceability
Every factual component should be traceable to stored event/source information.

## Rules
- Do not invent facts.
- Do not add unsupported interpretation.
- Do not turn source disagreement into a false certainty.
- If an important fact is uncertain, represent the uncertainty.

## Fallback
If the structured data is insufficient for a reliable Crux, show a shorter factual summary rather than generating unsupported prose.
