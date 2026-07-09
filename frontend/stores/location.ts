// Shared client state (SRS §9 Zustand, §12.3). Holds the coordinate the user is
// working with so it persists as they move between the Ask, Fetch, and Dashboard
// pages, plus a lightweight history of recent runs. This is UI state only — it
// carries no business logic and no catalog knowledge (SRS §38.5).

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface Coordinate {
  lat: number;
  lng: number;
}

export type RunKind = "ask" | "fetch";

export interface HistoryEntry {
  id: string;
  kind: RunKind;
  lat: number;
  lng: number;
  /** The question (ask) or preset/field summary (fetch). */
  label: string;
  at: number;
}

interface LocationState {
  coordinate: Coordinate | null;
  /** A human label for the current coordinate, e.g. a named example. */
  coordinateLabel: string | null;
  history: HistoryEntry[];
  setCoordinate: (coord: Coordinate, label?: string | null) => void;
  clearCoordinate: () => void;
  pushHistory: (entry: Omit<HistoryEntry, "id" | "at">) => void;
  clearHistory: () => void;
}

const HISTORY_LIMIT = 12;

export const useLocationStore = create<LocationState>()(
  persist(
    (set) => ({
      coordinate: null,
      coordinateLabel: null,
      setCoordinate: (coordinate, coordinateLabel = null) => set({ coordinate, coordinateLabel }),
      clearCoordinate: () => set({ coordinate: null, coordinateLabel: null }),
      history: [],
      pushHistory: (entry) =>
        set((state) => {
          const item: HistoryEntry = {
            ...entry,
            id: `${entry.kind}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
            at: Date.now(),
          };
          return { history: [item, ...state.history].slice(0, HISTORY_LIMIT) };
        }),
      clearHistory: () => set({ history: [] }),
    }),
    { name: "terra-location" },
  ),
);
