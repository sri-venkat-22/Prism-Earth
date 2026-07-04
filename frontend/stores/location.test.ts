import { act } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { useLocationStore } from "@/stores/location";

function reset() {
  act(() => {
    useLocationStore.setState({ coordinate: null, coordinateLabel: null, history: [] });
  });
}

describe("useLocationStore", () => {
  beforeEach(reset);

  it("sets and clears the active coordinate", () => {
    act(() => useLocationStore.getState().setCoordinate({ lat: 17.4, lng: 78.5 }, "Hyderabad"));
    expect(useLocationStore.getState().coordinate).toEqual({ lat: 17.4, lng: 78.5 });
    expect(useLocationStore.getState().coordinateLabel).toBe("Hyderabad");

    act(() => useLocationStore.getState().clearCoordinate());
    expect(useLocationStore.getState().coordinate).toBeNull();
    expect(useLocationStore.getState().coordinateLabel).toBeNull();
  });

  it("prepends history entries with generated id + timestamp", () => {
    act(() =>
      useLocationStore.getState().pushHistory({
        kind: "ask",
        lat: 17.4,
        lng: 78.5,
        label: "solar?",
      }),
    );
    const [entry] = useLocationStore.getState().history;
    expect(entry.kind).toBe("ask");
    expect(entry.id).toMatch(/^ask-/);
    expect(entry.at).toBeGreaterThan(0);
  });

  it("caps history at 12 most-recent entries", () => {
    act(() => {
      for (let i = 0; i < 20; i++) {
        useLocationStore.getState().pushHistory({
          kind: "fetch",
          lat: i,
          lng: i,
          label: `run-${i}`,
        });
      }
    });
    const { history } = useLocationStore.getState();
    expect(history).toHaveLength(12);
    // Most recent first.
    expect(history[0].label).toBe("run-19");
  });

  it("clears history", () => {
    act(() => useLocationStore.getState().pushHistory({ kind: "ask", lat: 0, lng: 0, label: "x" }));
    act(() => useLocationStore.getState().clearHistory());
    expect(useLocationStore.getState().history).toHaveLength(0);
  });
});
