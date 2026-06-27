# Prism Earth — Frontend

Next.js (App Router) + TypeScript + Tailwind + ShadCN shell (SRS §9, §12).
**Phase 0** ships one placeholder page and the project scaffold only — pages,
components, and the API client are built in Phase 6. The frontend consumes the
backend REST APIs and contains **no business logic** (SRS §38.5).

## Stack

Next.js 14 · React 18 · TypeScript (strict) · Tailwind CSS · ShadCN UI. React
Query, Zustand, and Framer Motion are installed and ready for Phase 6.

## Layout (SRS §10)

```
app/          App Router routes + layout (placeholder page)
components/   reusable components; components/ui = ShadCN primitives
features/     feature modules (Phase 6)
hooks/        React hooks (Phase 6)
services/     API client (health call only in Phase 0)
stores/       Zustand stores (Phase 6)
types/        shared TypeScript types
styles/       additional stylesheets (globals live in app/globals.css)
lib/          utilities (cn)
```

## Local development

```bash
npm install
npm run dev          # http://localhost:3000
```

## Quality gates

```bash
npm run lint         # next lint (ESLint)
npm run typecheck    # tsc --noEmit
npm run format:check # prettier
```

Configure the backend URL via `NEXT_PUBLIC_API_BASE_URL` (see `.env.example`).
