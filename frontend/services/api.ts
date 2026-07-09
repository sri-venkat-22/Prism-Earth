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
// bearer token (metadata stays public). A manually-pasted API token is kept in
// localStorage and attached as an Authorization header. It is never bundled at
// build time — NEXT_PUBLIC_* would ship a secret to every visitor.
//
// A signed-in user's *session* is NOT stored here: it lives in an HttpOnly
// cookie the backend sets on /account/login|register (unreadable by JS, so XSS
// cannot steal it). Every request below sends `credentials: "include"` so that
// cookie rides along and also authorizes /fetch and /ask.
const TOKEN_STORAGE_KEY = "terra.api_token";

function readStored(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // storage unavailable (private mode / disabled)
  }
}

function writeStored(key: string, value: string | null): void {
  if (typeof window === "undefined") return;
  try {
    const trimmed = value?.trim();
    if (trimmed) window.localStorage.setItem(key, trimmed);
    else window.localStorage.removeItem(key);
  } catch {
    // storage unavailable — the value just won't persist
  }
}

export function getApiToken(): string | null {
  return readStored(TOKEN_STORAGE_KEY);
}

export function setApiToken(token: string | null): void {
  writeStored(TOKEN_STORAGE_KEY, token);
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

async function send(path: string, init?: RequestInit): Promise<Response> {
  let res: Response;
  const token = getApiToken(); // manually-pasted API token; the session is a cookie
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init?.headers,
      },
      credentials: "include", // send the HttpOnly session cookie cross-origin
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
  return res;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return (await (await send(path, init)).json()) as T;
}

function get<T>(path: string): Promise<T> {
  return request<T>(path);
}

function body(method: string, payload: unknown): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
}

function post<T>(path: string, payload: unknown): Promise<T> {
  return request<T>(path, body("POST", payload));
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

// --------------------------------------------------------------------------- //
// End-user accounts / login (SRS §13.20)                                       //
// --------------------------------------------------------------------------- //
export interface AccountUser {
  id: string;
  email: string;
  organization: string | null;
  created_at: string;
  has_password: boolean;
  google_linked: boolean;
}

export interface AccountToken {
  id: string;
  prefix: string;
  name: string;
  subject: string;
  scopes: string[];
  created_at: string;
  expires_at: string | null;
  last_used_at: string | null;
  revoked: boolean;
  rate_limit_per_minute: number | null;
}

export interface AccountTokenCreated extends AccountToken {
  token: string; // shown only once, at creation
}

export function getAccountConfig(): Promise<{ google_enabled: boolean }> {
  return get<{ google_enabled: boolean }>("/account/config");
}

// Login/register set the session as an HttpOnly cookie (via credentials:include
// in `send`) and return only the user — the token is never handed to JS.
export function registerAccount(input: {
  email: string;
  password: string;
  organization?: string | null;
}): Promise<AccountUser> {
  return post<AccountUser>("/account/register", input);
}

export function loginAccount(input: { email: string; password: string }): Promise<AccountUser> {
  return post<AccountUser>("/account/login", input);
}

export function getMe(): Promise<AccountUser> {
  return get<AccountUser>("/account/me");
}

export function updateMe(input: { organization: string | null }): Promise<AccountUser> {
  return request<AccountUser>("/account/me", body("PATCH", input));
}

export async function deleteMe(): Promise<void> {
  await send("/account/me", { method: "DELETE" });
}

export async function logoutAccount(): Promise<void> {
  await send("/account/logout", { method: "POST" });
}

export async function listMyTokens(): Promise<{ count: number; tokens: AccountToken[] }> {
  return get<{ count: number; tokens: AccountToken[] }>("/account/tokens");
}

export function createMyToken(input: {
  name: string;
  scopes?: string[];
  expires_in_days?: number | null;
}): Promise<AccountTokenCreated> {
  return post<AccountTokenCreated>("/account/tokens", input);
}

export async function revokeMyToken(id: string): Promise<void> {
  await send(`/account/tokens/${encodeURIComponent(id)}`, { method: "DELETE" });
}

/** URL the browser navigates to for "Sign in with Google" (full-page redirect). */
export const GOOGLE_LOGIN_URL = `${API_BASE_URL}/account/google/login`;

export { API_BASE_URL };
