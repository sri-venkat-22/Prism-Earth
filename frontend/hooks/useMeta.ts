// React Query hooks for the read-only metadata catalog (SRS §13.5–13.8, §13.16).
// These drive the whole UI: presets, fields, layers, and region availability all
// come from here rather than being hardcoded (SRS §38.5).

import { useQuery } from "@tanstack/react-query";

import {
  type FieldFilters,
  getConnectorsHealth,
  getFields,
  getHealth,
  getLayers,
  getPresets,
  getStates,
  resolveState,
} from "@/services/api";

const CATALOG_STALE = 5 * 60 * 1000; // metadata rarely changes within a session

export function useFields(filters: FieldFilters = {}) {
  return useQuery({
    queryKey: ["meta", "fields", filters],
    queryFn: () => getFields(filters),
    staleTime: CATALOG_STALE,
  });
}

export function useLayers() {
  return useQuery({
    queryKey: ["meta", "layers"],
    queryFn: getLayers,
    staleTime: CATALOG_STALE,
  });
}

export function usePresets() {
  return useQuery({
    queryKey: ["meta", "presets"],
    queryFn: getPresets,
    staleTime: CATALOG_STALE,
  });
}

export function useStates() {
  return useQuery({
    queryKey: ["meta", "states"],
    queryFn: getStates,
    staleTime: CATALOG_STALE,
  });
}

export function useResolveState(name: string, enabled = true) {
  return useQuery({
    queryKey: ["meta", "states", name],
    queryFn: () => resolveState(name),
    enabled: enabled && name.trim().length > 0,
    staleTime: CATALOG_STALE,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    staleTime: 30 * 1000,
    refetchInterval: 60 * 1000,
    retry: false,
  });
}

export function useConnectorsHealth() {
  return useQuery({
    queryKey: ["health", "connectors"],
    queryFn: getConnectorsHealth,
    staleTime: 30 * 1000,
    retry: false,
  });
}
