# ONE I Database Design

## Principle
ONE I is event-centric. The Event is the central domain object.

## Proposed entities

### users
- id
- google_id
- email
- name
- created_at

### events
- id
- title
- crux
- context
- event_time
- created_at
- updated_at

### sources
- id
- name
- domain
- source_type

### articles
- id
- event_id
- source_id
- title
- url
- published_at
- content
- retrieved_at

### developments
- id
- event_id
- title
- description
- occurred_at
- importance

### coverage
- id
- development_id
- article_id
- status

Status should support at least covered and unclear; absence of a coverage record can represent not covered where appropriate.

### number_observations
- id
- article_id
- description
- reported_value
- unit
- context

### wording_observations
- id
- article_id
- topic
- quoted_text
- description

### public_reactions
- id
- event_id
- platform
- content
- published_at
- engagement
- url

### market_data
V2 groundwork: the table exists, but V1 does not display market data.
- id
- event_id
- symbol
- timestamp
- price
- volume

## Relationships
```text
Event
├── Articles ── Source
├── Developments ── Coverage ── Article
├── Number observations ── Article
├── Wording observations ── Article
├── Public reactions
└── Market data
```

## Storage vs calculation
Store raw/important observations. Calculate derived values such as coverage rate, percentage differences, returns, benchmark differences, and reaction aggregates rather than unnecessarily storing duplicate calculations.

## Explicitly not modeled
No bias_score, truth_score, fake_account, intent, propaganda_score, or political_alignment fields.
