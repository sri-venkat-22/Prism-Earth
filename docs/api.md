# API Reference

Prism Earth exposes a versioned REST API under `/api/v1` (SRS §13). The API is
self-documenting: an OpenAPI 3 spec is generated automatically, with Swagger UI
and ReDoc (SRS §13.22).

| Surface | URL |
| --- | --- |
| OpenAPI spec | `/api/v1/openapi.json` |
| Swagger UI | `/docs` |
| ReDoc | `/redoc` |

Export the spec to a file with `python -m scripts.export_openapi` (writes
`openapi.json`).

## Endpoints

| Method | Path | Auth | Purpose |
| --- | --- | --- | --- |
| GET | `/api/v1/meta/fields` | public | List catalog fields (filterable) |
| GET | `/api/v1/meta/layers` | public | List domain layers |
| GET | `/api/v1/meta/presets` | public | List field-bundle presets |
| GET | `/api/v1/meta/states` | public | List supported states |
| POST | `/api/v1/fetch` | bearer¹ | Deterministic field retrieval |
| POST | `/api/v1/ask` | bearer¹ | Natural-language cited answer |
| GET | `/api/v1/health` | public | Service + dependency health |
| GET | `/api/v1/ready` \| `/live` | public | Readiness / liveness probes |
| GET | `/metrics` | internal | Prometheus metrics |

¹ Only when `PRISM_AUTH_ENABLED=true` (SRS §13.20).

## `POST /api/v1/fetch`

Retrieve raw field values for a coordinate with full provenance. Provide exactly
one of `fields` or `preset`.

```json title="Request"
{ "lat": 17.385, "lng": 78.486, "preset": "terrain" }
```

```json title="Response (abridged)"
{
  "request_id": "REQ-...",
  "location": { "state": "Telangana", "district": "Hyderabad", "in_pilot_region": true },
  "fields": {
    "elevation": {
      "name": "elevation", "value": 542.16, "unit": "m", "datatype": "float",
      "confidence": "high", "dataset": "Copernicus DEM GLO-30", "layer": "terrain"
    }
  },
  "provenance": { "elevation": { "dataset": "Copernicus DEM GLO-30", "source_url": "...", "confidence": "high" } },
  "citations": [ { "citation_id": "CIT-001", "dataset": "Copernicus DEM GLO-30", "field_names": ["elevation"] } ],
  "partial_failures": [],
  "summary": { "requested": 3, "resolved": 3, "null": 0, "datasets_used": ["Copernicus DEM GLO-30"] }
}
```

A connector failing at runtime never aborts the request — the other fields are
returned and the failure appears in `partial_failures` with a `200` (SRS §15.16).

## `POST /api/v1/ask`

Plan → fetch → synthesize a cited answer, with a full execution trace.

```json title="Request"
{ "lat": 17.385, "lng": 78.486, "question": "Is this area suitable for a solar farm?" }
```

The response contains `answer`, `citations`, per-field `provenance`, and a
`trace` (planner intent + fields, fetch execution, synthesizer metadata,
durations — SRS §13.14).

## Error model (SRS §28.2, §13.17)

Every error uses one envelope:

```json
{ "error": { "code": "RATE_LIMIT_EXCEEDED", "message": "...", "correlation_id": "REQ-...", "timestamp": "..." } }
```

| Code | Status | When |
| --- | --- | --- |
| `VALIDATION_ERROR` | 422 | Bad/missing input, out-of-range coordinate, unknown/planned field |
| `NOT_FOUND` / `HTTP_404` | 404 | Unknown preset or route |
| `AUTHENTICATION_ERROR` | 401 | Missing/invalid bearer token |
| `AUTHORIZATION_ERROR` | 403 | Valid token lacking the required scope |
| `RATE_LIMIT_EXCEEDED` | 429 | Over the rate limit (carries `Retry-After`) |
| `PAYLOAD_TOO_LARGE` | 413 | Request body over the size limit |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

## Rate-limit headers

Successful `/fetch` and `/ask` responses advertise `RateLimit-Limit`,
`RateLimit-Remaining`, and `RateLimit-Reset` (seconds to the next window).
