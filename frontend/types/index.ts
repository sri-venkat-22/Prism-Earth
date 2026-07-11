// Shared API types (SRS §13). The frontend consumes REST only and contains no
// business logic (SRS §38.5); these mirror the backend response shapes exactly.
// Nothing here encodes field lists, presets, or region rules — those are always
// discovered at runtime from /meta/*.

// --------------------------------------------------------------------------- //
// Controlled vocabularies (mirror backend StrEnums, SRS §11.4–11.6)           //
// --------------------------------------------------------------------------- //
export type Layer =
  | "terrain"
  | "climate"
  | "land_cover"
  | "natural_hazard"
  | "infrastructure"
  | "utilities"
  | "administrative"
  | "cadastral"
  | "built_environment";

export type Lifecycle = "stable" | "beta" | "planned";

export type Availability = "nationwide" | "region_gated" | "planned";

export type DataType = "float" | "integer" | "string" | "boolean" | "enum" | "geometry";

export type Confidence = "high" | "medium" | "low";

export type NullReason =
  | "data_unavailable"
  | "outside_coverage"
  | "unsupported_state"
  | "not_applicable"
  | "connector_timeout"
  | "dataset_unavailable";

// --------------------------------------------------------------------------- //
// Metadata catalog — GET /meta/fields|layers|presets|states (SRS §13.5–13.8)  //
// --------------------------------------------------------------------------- //
export interface CatalogField {
  id: string;
  name: string;
  description: string;
  layer: Layer;
  lifecycle: Lifecycle;
  available: boolean;
  availability: Availability;
  nullable: boolean;
  null_meaning: string | null;
  source: string;
  source_url: string | null;
  unit: string | null;
  datatype: DataType;
  ttl: string | null;
  interpretation_hint: string;
  connector: string;
  presets: string[];
}

export interface FieldsResponse {
  count: number;
  fields: CatalogField[];
}

export interface LayerObject {
  id: Layer;
  name: string;
  purpose: string;
  connector: string;
  field_count: number;
}

export interface LayersResponse {
  count: number;
  layers: LayerObject[];
}

export interface PresetObject {
  id: string;
  name: string;
  description: string;
  fields: string[];
  layers: Layer[];
  supported_states: string[];
}

export interface PresetsResponse {
  count: number;
  presets: PresetObject[];
}

export interface StateObject {
  slug: string;
  code: string;
  name: string;
  registered: boolean;
  lifecycle: string;
  supported_datasets: string[];
  enabled_fields: string[];
}

export interface StatesResponse {
  count: number;
  states: StateObject[];
}

export interface RegionResolutionResponse {
  query: string;
  supported: boolean;
  state: StateObject | null;
  message: string;
}

// --------------------------------------------------------------------------- //
// Fetch — POST /fetch (SRS §13.9–13.12, §16, §17)                             //
// --------------------------------------------------------------------------- //
export interface FetchRequest {
  lat: number;
  lng: number;
  fields?: string[];
  preset?: string;
}

export interface FieldValue {
  name: string;
  value: unknown | null;
  unit: string | null;
  datatype: DataType;
  confidence: Confidence;
  dataset: string;
  dataset_version: string | null;
  retrieved_at: string;
  ttl: string | null;
  layer: Layer;
  null_meaning: string | null;
}

export interface ProvenanceObject {
  field: string;
  dataset: string;
  dataset_version: string | null;
  source_url: string | null;
  retrieved_at: string;
  ttl: string | null;
  confidence: Confidence;
  null_meaning: string | null;
  reason: string | null;
  /** Present when the value is a Terra derivation from the cited dataset
   * (e.g. our banding of GloFAS return-period depths), not a value the dataset
   * itself publishes. */
  derivation?: string | null;
}

export interface Citation {
  citation_id: string;
  dataset: string;
  provider: string | null;
  source_url: string | null;
  dataset_version: string | null;
  retrieved_at: string;
  ttl: string | null;
  license: string | null;
  field_names: string[];
}

export interface PartialFailure {
  layer: string | null;
  connector: string | null;
  dataset: string | null;
  reason: string;
  retryable: boolean;
}

export interface FetchLocation {
  lat: number;
  lng: number;
  in_pilot_region: boolean;
  state: string | null;
  district: string | null;
  taluk: string | null;
  village: string | null;
  municipality: string | null;
  ward: string | null;
}

export interface ResponseSummary {
  requested: number;
  resolved: number;
  null: number;
  datasets_used: string[];
}

export interface FetchResponse {
  request_id: string;
  timestamp: string;
  location: FetchLocation;
  fields: Record<string, FieldValue>;
  provenance: Record<string, ProvenanceObject>;
  citations: Citation[];
  partial_failures: PartialFailure[];
  summary: ResponseSummary;
}

// --------------------------------------------------------------------------- //
// Ask — POST /ask (SRS §13.13, §13.14)                                        //
// --------------------------------------------------------------------------- //
export interface AskRequest {
  lat: number;
  lng: number;
  question: string;
}

export interface PlannerTrace {
  intent: string;
  presets: string[];
  fields: string[];
  layers: string[];
  connectors: string[];
  planning_reason: string;
  warnings: string[];
  model: string;
  duration_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
}

export interface ConnectorExecution {
  connector: string;
  fields: string[];
  status: string; // ok | failed
  reason: string | null;
}

export interface FetchTrace {
  requested_fields: string[];
  resolved_fields: string[];
  null_fields: string[];
  datasets_used: string[];
  connectors: ConnectorExecution[];
  partial_failures: PartialFailure[];
  duration_ms: number;
}

export interface SynthesizerTrace {
  model: string | null;
  unavailable_fields: string[];
  citations_used: string[];
  duration_ms: number;
  prompt_tokens: number | null;
  completion_tokens: number | null;
}

export interface Trace {
  planner: PlannerTrace;
  fetch: FetchTrace;
  synthesizer: SynthesizerTrace;
  total_duration_ms: number;
}

export interface DataGap {
  field: string;
  reason: string;
}

export interface AskResponse {
  request_id: string;
  timestamp: string;
  location: FetchLocation;
  answer: string;
  confidence: string;
  citations: Citation[];
  fields_used: string[];
  data_gaps: DataGap[];
  trace: Trace;
  provenance: Record<string, ProvenanceObject>;
}

// --------------------------------------------------------------------------- //
// Health — GET /health, /health/connectors (SRS §13.16, §18.12)               //
// --------------------------------------------------------------------------- //
export interface ComponentStatus {
  status: string;
  detail?: string | null;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  environment: string;
  timestamp: string;
  components: Record<string, ComponentStatus>;
}

export interface ConnectorHealthObject {
  name: string;
  layer: string;
  status: string;
  servable_fields: number;
  detail?: string | null;
}

export interface ConnectorsHealthResponse {
  status: string;
  timestamp: string;
  count: number;
  connectors: ConnectorHealthObject[];
}

// --------------------------------------------------------------------------- //
// Error envelope — SRS §28.2 / §13.17                                         //
// --------------------------------------------------------------------------- //
export interface ErrorModel {
  code: string;
  message: string;
  details?: string | null;
  correlation_id: string;
  timestamp: string;
}

export interface ErrorResponse {
  error: ErrorModel;
}
