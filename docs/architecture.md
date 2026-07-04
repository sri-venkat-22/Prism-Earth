# Architecture Guide

This guide describes how Prism Earth is structured (SRS §8, §11, §12) and how a
request flows through the system.

## Principles

Prism Earth follows Clean Architecture and SOLID (SRS §11.2, §35.1): business
logic is separated from infrastructure, the **metadata catalog is the single
source of truth**, and configuration lives in `configs/*.yaml` — never hardcoded.
The deterministic Fetch spine contains no AI; the AI lives only in the Planner
and Synthesizer, which never touch data or citations.

## High-level architecture

```
                ┌─────────────┐        ┌──────────────────────────────┐
  Browser  ───► │  Next.js UI │ ─REST─►│         FastAPI backend       │
  MCP client ─► │  MCP server │        │  ┌────────┐  ┌─────────────┐  │
                └─────────────┘        │  │Planner │  │Fetch Engine │  │
                                       │  └────────┘  └─────┬───────┘  │
                                       │  ┌────────┐        │ connectors│
                                       │  │Synth.  │◄───────┘           │
                                       │  └────────┘                    │
                                       └──────┬───────────────┬────────┘
                                              │               │
                                        PostGIS / GEE       Redis
```

## Backend layers (SRS §11.3)

| Layer | Modules | Responsibility |
| --- | --- | --- |
| API | `app/api/v1/*` | Thin HTTP adapters; validation, auth, rate limiting |
| Orchestration | `app/ask/pipeline.py`, `app/fetchers/orchestrator.py` | Wire the pipeline stages |
| Domain | `app/planners`, `app/synthesizers`, `app/citations`, `app/provenance` | Planning, synthesis, citations, lineage |
| Connectors | `app/connectors/*` | One per layer; deterministic retrieval |
| Metadata | `app/metadata/*` | Catalog, fields, presets, State Registry |
| Infrastructure | `app/core/*`, `app/gee`, `app/config` | DB, Redis, config, logging |
| Cross-cutting | `app/middleware`, `app/observability`, `app/auth` | Correlation, metrics, tracing, security |

## Request flow — `POST /api/v1/ask`

1. **Middleware** assigns a correlation id, records metrics, applies security
   headers, and (for data endpoints) enforces the gateway rate limit.
2. **Auth** (when enabled) validates the bearer token and scope (SRS §13.20).
3. **Planner** turns the question into a catalog-constrained execution plan.
4. **Fetch Engine** runs the plan's fields across connectors in parallel,
   attaching provenance to every field; failures land in `partial_failures`.
5. **Citation Engine** builds one citation per contributing dataset.
6. **Synthesizer** composes the cited answer from the fetched values.
7. The response returns `answer`, `citations`, a full execution `trace`
   (SRS §13.14), and per-field `provenance`.

## Frontend architecture (SRS §12)

The Next.js app consumes only the public REST APIs and contains **no business
logic** (SRS §38.5). Layers: `app/*` pages → `features/*` views →
`components/*` presentational UI, with logic isolated in `lib/`, `services/`,
`stores/` (Zustand), and `hooks/` (React Query). Field lists, presets, and
region rules are always discovered at runtime from `/meta/*`.

## MCP server (SRS §34)

`app/mcp/*` is a thin client over the REST API. AI agents call
`prism_earth_fetch` / `prism_earth_ask`; the server forwards to the same
endpoints, preserving determinism, provenance, and citations.
