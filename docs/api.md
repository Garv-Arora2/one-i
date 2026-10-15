# ONE I API Specification

## Principles
- REST-oriented
- predictable JSON schemas
- validation at the API boundary
- no direct database access from frontend
- no expensive full-event analysis during normal page requests
- never fabricate missing data

## Event endpoints
`GET /events`
Returns event summaries for the homepage.

`GET /events/{event_id}`
Returns the main event information including crux/context.

`GET /events/{event_id}/timeline`
Returns chronological developments.

`GET /events/{event_id}/coverage`
Returns development-by-source coverage information and derived coverage measurements.

`GET /events/{event_id}/comparisons`
Returns numerical and wording comparisons.

`GET /events/{event_id}/reactions`
Returns public-reaction aggregates and source items where appropriate.

`GET /events/{event_id}/market`
Returns market information when relevant. V2 groundwork: the endpoint exists but the V1 site does not call it.

## Source endpoints
`GET /sources`
Returns tracked sources.

`GET /sources/{source_id}`
Returns source information and relevant coverage.

## Authentication
Google authentication and CAPTCHA are handled through an established provider/integration. Exact routes depend on the chosen implementation.

## Error behavior
Use appropriate HTTP status codes and clear JSON error messages. Missing market/social data should return an explicit unavailable state rather than fabricated values.

## Internal processing
Ingestion and analysis should be scheduled/background processes rather than ordinary user-facing requests whenever possible.

## Versioning
Do not introduce API versioning complexity until there is a real compatibility requirement.
