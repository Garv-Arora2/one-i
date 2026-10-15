# Public Reaction Specification

## Goal
Give a compact view of what people are discussing around an event.

Sources:
- Reddit
- YouTube

Public reaction is supplementary context, not factual authority.

## Pipeline
API -> collect -> clean -> deduplicate -> associate with event -> relevance filter -> rank by likes -> display.

## Stored information
- platform
- event
- text/title
- published time
- engagement where available
- original URL

## V1 output
The most-liked comments (up to six) that are about the event. A comment is
shown only when it:
- is readable English of at least four words,
- contains no link,
- shares at least one meaningful word (four letters or more) with the event's
  headline or summary.

No sentiment, tone or topic analysis is shown in V1.

## Rules
- Popularity does not establish truth.
- Do not infer fake accounts.
- Do not implement bot/coordinated manipulation detection.
- Do not expose unnecessary private user information.
- Link back to public source content where appropriate.

If API limitations make this feature disproportionately difficult, it must not block the core ONE I product.
