# Prism Earth

**Deterministic, citation-backed geospatial intelligence for India.**

Prism Earth answers questions about any point in India — "Is this area suitable
for a solar farm?", "What is the flood risk here?" — by planning which catalog
fields are needed, deterministically fetching them from real datasets, and
synthesizing a cited answer. Every returned field carries full provenance, and
every synthesized answer cites its sources. Nothing is invented (SRS §1, §38).

## The pipeline

```
Question → Planner → Fetch Engine → Citation Engine → Synthesizer → Cited answer
              │           │                                 │
        selects fields  retrieves values (no AI)       composes answer
```

- **Planner** (SRS §14) — an LLM selects registered catalog fields; it never
  fetches data or answers questions.
- **Fetch Engine** (SRS §15) — deterministic connectors retrieve values in
  parallel. No AI. Partial failures never abort the request.
- **Citation Engine** (SRS §16) — one deduplicated citation per contributing
  dataset.
- **Synthesizer** (SRS §6.5) — composes a natural-language answer from the
  fetched values only.

## What's here

| Guide | Purpose |
| --- | --- |
| [Architecture](architecture.md) | Layered system design and data flow (SRS §8, §11, §12) |
| [Developer Guide](developer-guide.md) | Local setup, tests, adding a connector (SRS §35) |
| [Deployment Guide](deployment.md) | Docker, Nginx, production topology (SRS §33) |
| [Observability](observability.md) | Metrics, tracing, logs, dashboards (SRS §27) |
| [Security](security.md) | Auth, rate limiting, headers, scanning (SRS §29) |
| [API Reference](api.md) | REST endpoints, OpenAPI, Swagger, ReDoc (SRS §13) |
| [Dataset Documentation](datasets.md) | Layers, datasets, provenance (SRS §11, §15) |

## Public surface

- **REST API** — `POST /api/v1/fetch`, `POST /api/v1/ask`, and the public
  `GET /api/v1/meta/*` discovery endpoints.
- **MCP server** — the same capabilities exposed to AI agents (SRS §34).
- **Browser UX** — Ask, Dashboard, Fetch, and Explore, built entirely over the
  public REST APIs.

Version 1 covers the **Telangana** pilot region: 9 layers, 93 fields, 18 presets.
