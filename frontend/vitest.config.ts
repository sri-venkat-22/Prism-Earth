/// <reference types="vitest" />
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const rootDir = dirname(fileURLToPath(import.meta.url));

// Vitest unit/component tests (SRS §30.2 Table 7 — Frontend = Vitest).
//
// Coverage is scoped to the layers where unit testing is the right tool: the
// logic layers (lib / services / stores / hooks) and the reusable presentational
// components under test. Pages (app/**) and heavy feature views (features/**,
// map canvas) hold no business logic (SRS §38.5) and are validated end-to-end by
// Playwright instead (§36.1), so they are excluded from this gate.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": rootDir },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: [resolve(rootDir, "tests/setup.ts")],
    include: ["{lib,services,stores,hooks,components}/**/*.{test,spec}.{ts,tsx}"],
    coverage: {
      provider: "v8",
      reporter: ["text-summary", "html", "lcov"],
      include: [
        "lib/**",
        "services/**",
        "stores/**",
        "hooks/**",
        "components/badges.tsx",
        "components/stat-tile.tsx",
      ],
      thresholds: { lines: 70, statements: 70, functions: 70, branches: 60 },
    },
  },
});
