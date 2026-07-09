// API client for the Terra public REST surface (SRS §13).
//
// The frontend consumes REST only and contains no business logic (SRS §38.5):
// every endpoint here is a thin transport wrapper that returns exactly what the
// backend sends. Field lists, presets, and region rules are never hardcoded —
// they are discovered from /meta/* at runtime.

import type {
  AskRequest,
  AskResponse,
  ConnectorsHealthResponse,
  ErrorResponse,
  FetchRequest,
  FetchResponse,
  FieldsResponse,
  HealthResponse,
  LayersResponse,
  PresetsResponse,
  RegionResolutionResponse,
  StatesResponse,
} from "@/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

// --------------------------------------------------------------------------- //
// Bearer-token handling (SRS §13.20)                                          //
// --------------------------------------------------------------------------- //
// When the backend runs with auth enabled, POST /fetch and /ask require a
// bearer token (metadata stays public). The token is user-supplied (issued via
// the admin-gated /auth/tokens flow), kept in localStorage, and attached to
// every request. It is never bundled at build time — NEXT_PUBLIC_* would ship
// a secret to every visitor.
const TOKEN_STORAGE_KEY = "terra.api_token";

export function getApiToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null; // storage unavailable (private mode / disabled)
  }
}

export function setApiToken(token: string | null): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = token?.trim();
    if (trimmed) window.localStorage.setItem(TOKEN_STORAGE_KEY, trimmed);
    else window.localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // storage unavailable — the token just won't persist
  }
}

/** A structured error carrying the backend's SRS §28.2 envelope when present. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly correlationId?: string;
  readonly details?: string | null;

  constructor(status: number, message: string, opts?: Partial<ErrorResponse["error"]>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = opts?.code ?? "UNKNOWN";
    this.correlationId = opts?.correlation_id;
    this.details = opts?.details ?? null;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    return new ApiError(res.status, `${res.status} ${res.statusText}`);
  }
  // SRS §28.2 error envelope: { error: { code, message, details, ... } }
  const env = body as Partial<ErrorResponse>;
  if (env?.error?.message) {
    return new ApiError(res.status, env.error.message, env.error);
  }
  // FastAPI validation errors: { detail: [{ msg, loc }] } or { detail: "..." }
  const fastapi = body as { detail?: unknown };
  if (typeof fastapi?.detail === "string") {
    return new ApiError(res.status, fastapi.detail);
  }
  if (Array.isArray(fastapi?.detail)) {
    const first = fastapi.detail[0] as { msg?: string; loc?: unknown[] } | undefined;
    const where = Array.isArray(first?.loc) ? ` (${first.loc.join(".")})` : "";
    return new ApiError(res.status, `${first?.msg ?? "Validation error"}${where}`, {
      code: "VALIDATION_ERROR",
    });
  }
  return new ApiError(res.status, `${res.status} ${res.statusText}`);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  const token = getApiToken();
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch (cause) {
    // Network-level failure (backend down, CORS, DNS). Surface a clear message.
    throw new ApiError(0, "Cannot reach the Terra API. Is the backend running?", {
      code: "NETWORK_ERROR",
    });
  }
  if (!res.ok) {
    throw await parseError(res);
  }
  return (await res.json()) as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --------------------------------------------------------------------------- //
// Metadata catalog & State Registry (SRS §13.5–13.8, §13.23)                  //
// --------------------------------------------------------------------------- //
export interface FieldFilters {
  layer?: string;
  lifecycle?: string;
  available?: boolean;
}

export function getFields(filters: FieldFilters = {}): Promise<FieldsResponse> {
  const q = new URLSearchParams();
  if (filters.layer) q.set("layer", filters.layer);
  if (filters.lifecycle) q.set("lifecycle", filters.lifecycle);
  if (filters.available !== undefined) q.set("available", String(filters.available));
  const qs = q.toString();
  return get<FieldsResponse>(`/meta/fields${qs ? `?${qs}` : ""}`);
}

export function getLayers(): Promise<LayersResponse> {
  return get<LayersResponse>("/meta/layers");
}

export function getPresets(): Promise<PresetsResponse> {
  return get<PresetsResponse>("/meta/presets");
}

export function getStates(): Promise<StatesResponse> {
  return get<StatesResponse>("/meta/states");
}

export function resolveState(name: string): Promise<RegionResolutionResponse> {
  return get<RegionResolutionResponse>(`/meta/states/${encodeURIComponent(name)}`);
}

// --------------------------------------------------------------------------- //
// Deterministic Fetch & Natural-Language Ask (SRS §13.9, §13.13)              //
// --------------------------------------------------------------------------- //
export function postFetch(payload: FetchRequest): Promise<FetchResponse> {
  return post<FetchResponse>("/fetch", payload);
}

export function postAsk(payload: AskRequest): Promise<AskResponse> {
  return post<AskResponse>("/ask", payload);
}

// --------------------------------------------------------------------------- //
// Health (SRS §13.16, §18.12)                                                 //
// --------------------------------------------------------------------------- //
export function getHealth(): Promise<HealthResponse> {
  return get<HealthResponse>("/health");
}

export function getConnectorsHealth(): Promise<ConnectorsHealthResponse> {
  return get<ConnectorsHealthResponse>("/health/connectors");
}

export { API_BASE_URL };
