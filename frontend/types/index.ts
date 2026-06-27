// Shared API types (SRS §13). The frontend consumes REST only and contains no
// business logic (SRS §38.5); these mirror the backend response shapes.

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
