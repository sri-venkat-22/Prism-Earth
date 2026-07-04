// Vitest global setup: register jest-dom matchers and reset persisted state.
import "@testing-library/jest-dom/vitest";

import { afterEach, beforeEach } from "vitest";

// Each test starts from a clean localStorage so the persisted Zustand store
// (prism-earth-location) never leaks state between tests.
beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  window.localStorage.clear();
});
