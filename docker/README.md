# docker/

Shared Docker assets (SRS §32). Service Dockerfiles live with their service
(`backend/Dockerfile`, `frontend/Dockerfile`); this directory holds supporting
container configuration.

- `postgres/initdb/` — SQL run once on first database init (enables PostGIS).

Future (Phase 8, SRS §32.1, §33): Nginx reverse-proxy config and the
Prometheus/Grafana monitoring stack.
