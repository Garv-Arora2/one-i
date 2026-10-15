# ONE I Architecture

## Architecture goal
Use a simple modular monolith that separates collection, storage, analysis, API delivery, and presentation.

## Stack
Frontend: Next.js + React + TypeScript
Backend: FastAPI + Python
Database: PostgreSQL
Analysis: Python, Pandas, NumPy, classical NLP, simple statistics

## High-level flow
```text
External APIs/RSS
      ↓
Ingestion
      ↓
Cleaning / normalization / deduplication
      ↓
PostgreSQL
      ↓
Analysis
      ↓
Stored analysis results
      ↓
FastAPI
      ↓
Next.js
      ↓
User
```

## Layers

### Frontend
Landing, homepage, event page, interactions, visualizations, authentication UI. No core analysis.

### FastAPI
REST endpoints, request validation, application logic, authentication integration, database access.

### Ingestion
News APIs/RSS, Reddit, YouTube, and market data collection. Preserve source metadata and retrieval time.

### Analysis
Event grouping, development identification, coverage, number comparison, wording comparison, public-reaction aggregation, market calculations (V2 groundwork, not shown in V1).

### PostgreSQL
Persistent source and analysis data.

## Processing
Analysis should happen before a user requests a page whenever practical. Do not fetch and re-analyze an entire event synchronously on every page load.

## Architecture choice
Use a modular monolith. Avoid microservices, Kafka, Kubernetes, vector databases, model-serving infrastructure, or other infrastructure that does not have a clear V1 need.

## Authentication
Use established Google OAuth and CAPTCHA solutions. Do not implement password storage or custom OAuth.
