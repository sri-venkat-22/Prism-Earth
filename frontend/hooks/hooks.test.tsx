import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// Mock the transport layer so the hooks are exercised without a live backend.
vi.mock("@/services/api", () => ({
  getFields: vi.fn().mockResolvedValue({ fields: [{ id: "elevation" }] }),
  getLayers: vi.fn().mockResolvedValue({ layers: [] }),
  getPresets: vi.fn().mockResolvedValue({ presets: [] }),
  getStates: vi.fn().mockResolvedValue({ states: [] }),
  resolveState: vi.fn().mockResolvedValue({ state: "telangana" }),
  getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
  getConnectorsHealth: vi.fn().mockResolvedValue({ status: "ok", connectors: [] }),
  postFetch: vi.fn().mockResolvedValue({ fields: {} }),
  postAsk: vi.fn().mockResolvedValue({ answer: "hi", citations: [] }),
}));

import * as api from "@/services/api";
import {
  useConnectorsHealth,
  useFields,
  useHealth,
  useLayers,
  usePresets,
  useResolveState,
  useStates,
} from "@/hooks/useMeta";
import { useAskQuery, useFetchQuery } from "@/hooks/useQueries";

function wrapper() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("metadata query hooks", () => {
  it("useFields fetches and returns catalog fields", async () => {
    const { result } = renderHook(() => useFields({ layer: "terrain" }), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({ fields: [{ id: "elevation" }] });
    expect(api.getFields).toHaveBeenCalledWith({ layer: "terrain" });
  });

  it("useLayers / usePresets / useStates resolve", async () => {
    const layers = renderHook(() => useLayers(), { wrapper: wrapper() });
    const presets = renderHook(() => usePresets(), { wrapper: wrapper() });
    const states = renderHook(() => useStates(), { wrapper: wrapper() });
    await waitFor(() => expect(layers.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(presets.result.current.isSuccess).toBe(true));
    await waitFor(() => expect(states.result.current.isSuccess).toBe(true));
  });

  it("useHealth and useConnectorsHealth resolve", async () => {
    const health = renderHook(() => useHealth(), { wrapper: wrapper() });
    const connectors = renderHook(() => useConnectorsHealth(), { wrapper: wrapper() });
    await waitFor(() => expect(health.result.current.data).toMatchObject({ status: "ok" }));
    await waitFor(() => expect(connectors.result.current.isSuccess).toBe(true));
  });

  it("useResolveState is disabled for a blank name", async () => {
    const { result } = renderHook(() => useResolveState("  "), { wrapper: wrapper() });
    expect(result.current.fetchStatus).toBe("idle");
    expect(api.resolveState).not.toHaveBeenCalled();
  });

  it("useResolveState runs for a real name", async () => {
    const { result } = renderHook(() => useResolveState("telangana"), { wrapper: wrapper() });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.resolveState).toHaveBeenCalledWith("telangana");
  });
});

describe("action mutation hooks", () => {
  it("useFetchQuery posts a fetch payload", async () => {
    const { result } = renderHook(() => useFetchQuery(), { wrapper: wrapper() });
    result.current.mutate({ lat: 17.4, lng: 78.5, preset: "terrain" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.postFetch).toHaveBeenCalledWith({ lat: 17.4, lng: 78.5, preset: "terrain" });
  });

  it("useAskQuery posts an ask payload", async () => {
    const { result } = renderHook(() => useAskQuery(), { wrapper: wrapper() });
    result.current.mutate({ lat: 17.4, lng: 78.5, question: "hi?" });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.postAsk).toHaveBeenCalledWith({ lat: 17.4, lng: 78.5, question: "hi?" });
  });
});
