# Market Impact Specification

> **Status: V2.** Not shown in V1. The backend keeps the groundwork (the
> `market_data` table, the `/events/{id}/market` endpoint and the return and
> benchmark calculations), but the site does not display it.

## Goal
For relevant events, show observed market movement around the event.

## When shown
Only when:
- the event has a clear connection to a public security/company
- reliable market data exists
- event timing is sufficiently clear

## Data
- symbol
- timestamp
- price
- volume
- benchmark price/volume where relevant

## Calculations
Basic return:
`(ending price - starting price) / starting price * 100`

Benchmark comparison:
`security return - benchmark return`

Volume can be compared with a predefined recent baseline.

## Event window
Use predefined windows rather than choosing a window after seeing the result.

## User-facing presentation
Show:
- security movement
- benchmark movement
- volume change
- simple price chart

## Causality rule
Do not state that the event caused the price movement solely because the movement occurred after publication.

Use language such as:
"Company X fell 6.2% during the selected period."

## V1 boundary
No price prediction, trading strategy, portfolio optimization, high-frequency analysis, or sophisticated causal inference.
