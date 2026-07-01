"""Shared API schemas (SRS §13.4, §13.16, §13.17, §28.2).

These Pydantic v2 models define the platform-wide response envelopes. The error
model mirrors SRS §28.2 / §13.17 exactly. The standard success envelope (§13.4)
is included for forward compatibility; no business endpoints use it in Phase 0.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Error model — SRS §28.2 / §13.17                                            #
# --------------------------------------------------------------------------- #
class ErrorModel(BaseModel):
    """The ``error`` body of a failed response (SRS §28.2)."""

    code: str = Field(..., description="Machine-readable error code, e.g. DATASET_TIMEOUT")
    message: str = Field(..., description="Human-readable error message")
    details: str | None = Field(None, description="Optional additional context (SRS §13.17)")
    correlation_id: str = Field(..., description="Request correlation id for tracing")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


class ErrorResponse(BaseModel):
    """Top-level error envelope (SRS §28.2)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "error": {
                    "code": "DATASET_TIMEOUT",
                    "message": "Climate dataset request timed out.",
                    "details": None,
                    "correlation_id": "REQ-123456",
                    "timestamp": "2026-06-26T10:30:00Z",
                }
            }
        }
    )

    error: ErrorModel


# --------------------------------------------------------------------------- #
# Standard success envelope — SRS §13.4 (forward-compat, unused in Phase 0)   #
# --------------------------------------------------------------------------- #
class StandardResponse(BaseModel):
    """Standard success response envelope (SRS §13.4)."""

    request_id: str = ""
    timestamp: str = ""
    version: str = "v1"
    status: str = "success"
    data: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    partial_failures: list[dict[str, Any]] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Health schemas — SRS §13.16                                                 #
# --------------------------------------------------------------------------- #
class ComponentStatus(BaseModel):
    """Status of a single dependency reported by the health endpoints."""

    status: str = Field(..., description="ok | down | not_configured | not_applicable")
    detail: str | None = None


class HealthResponse(BaseModel):
    """``GET /api/v1/health`` payload (SRS §13.16)."""

    status: str = "ok"
    service: str
    version: str
    environment: str
    timestamp: str
    components: dict[str, ComponentStatus] = Field(default_factory=dict)


class ReadinessResponse(BaseModel):
    """``GET /api/v1/ready`` payload (SRS §13.16)."""

    status: str = Field("ready", description="ready | not_ready")
    timestamp: str
    checks: dict[str, ComponentStatus] = Field(default_factory=dict)


class LivenessResponse(BaseModel):
    """``GET /api/v1/live`` payload (SRS §13.16)."""

    status: str = "alive"
    timestamp: str


class ConnectorHealthObject(BaseModel):
    """Per-connector operational status (SRS §18.12)."""

    name: str = Field(..., description="Connector registry key (SRS §18.10)")
    layer: str = Field(..., description="Domain layer the connector serves (SRS §11.5)")
    status: str = Field(..., description="ok | degraded | down | not_configured")
    servable_fields: int = Field(..., description="Count of fields the connector can retrieve")
    detail: str | None = None


class ConnectorsHealthResponse(BaseModel):
    """``GET /api/v1/health/connectors`` payload (SRS §18.12)."""

    status: str = "ok"
    timestamp: str
    count: int
    connectors: list[ConnectorHealthObject] = Field(default_factory=list)
