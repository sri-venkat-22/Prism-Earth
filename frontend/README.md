# Prism Earth — Frontend

Next.js (App Router) + TypeScript + Tailwind + ShadCN (SRS §9, §12).
**Phase 6** delivers the full user experience in the browser, consuming only the
public REST APIs. The frontend contains **no business logic** (SRS §38.5): field
lists, presets, and region rules are all discovered at runtime from `/meta/*`.

## Stack (SRS §9)

Next.js 14 · React 18 · TypeScript (strict) · Tailwind CSS · ShadCN UI ·
TanStack React Query · Zustand · Framer Motion · lucide-react.

## Pages (SRS §12.4)

- **`/`** — landing hub with live catalog stats.
- **`/ask`** — natural-language search: cited answer + provenance + visualized
  execution trace (§12.5–12.7).
- **`/fetch`** — coordinate input / deterministic fetch: field values, provenance,
  citations, raw JSON.
- **`/dashboard`** — working location, capabilities, recent activity.
- **`/explore`** — Dataset Explorer (§12.8), Preset Explorer (§12.11), Layer
  visualization, Regional Availability (§12.12).
- **`/system`** — live health + per-connector status (§13.16, §18.12).

## Components (SRS §12.5–12.12)

Execution Visualizer (Planner + Fetch + Synthesizer), Provenance Viewer (real
source · license · retrieval date per field), Raw JSON Viewer, Dataset / Preset
explorers, Regional Availability (greys out region-gated fields outside their
supported states), Layer visualizations, plus loading / error / empty states
(§12.13–12.14), responsive design (§12.15), and accessibility (§12.16).

## Layout (SRS §10)

```
app/          App Router routes (page per §12.4) + layout + providers
components/   shared components; components/ui = ShadCN primitives
features/     feature modules (execution, provenance, explorer, ask, fetch, json, system)
hooks/        React Query hooks (useMeta, useQueries)
services/     API client for /meta/*, /fetch, /ask, /health
stores/       Zustand store (working location + history)
types/        shared TypeScript types mirroring the API
lib/          utilities (cn, formatting, enum→display mappings)
```

## Local development

```bash
npm install
npm run dev          # http://localhost:3000
```

Point the app at a running backend via `NEXT_PUBLIC_API_BASE_URL` (see
`.env.example`; defaults to `http://localhost:8000/api/v1`). The natural-language
`/ask` flow additionally requires the backend LLM to be configured (LiteLLM +
provider key); `/meta/*` and `/fetch` work without it.

## Quality gates

```bash
npm run lint         # next lint (ESLint)
npm run typecheck    # tsc --noEmit
npm run format:check # prettier
npm run build        # next production build
```
