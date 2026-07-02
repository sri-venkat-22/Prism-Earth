"""Request/response schemas for the auth endpoints (SRS §13.20).

Covers dashboard token management, the device-flow endpoints, and OAuth dynamic
client registration. The OAuth token endpoint itself is form-encoded and returns
the RFC 6749 body directly, so it has no Pydantic response model here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.auth.oauth import DEFAULT_SCOPES


# --------------------------------------------------------------------------- #
# Dashboard API tokens                                                        #
# --------------------------------------------------------------------------- #
class CreateTokenRequest(BaseModel):
    """Admin request to mint a dashboard API token."""

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"name": "cli-laptop", "scopes": ["fetch", "ask"]}]}
    )

    name: str = Field(..., description="Human label for the token")
    subject: str = Field("dashboard", description="Owner/principal the token represents")
    scopes: list[str] = Field(
        default_factory=lambda: sorted(DEFAULT_SCOPES),
        description="Scopes granted (subset of fetch/ask)",
    )
    expires_in_days: int | None = Field(
        None, description="Optional lifetime in days; omit for non-expiring"
    )
    rate_limit_per_minute: int | None = Field(
        None, description="Per-token request budget; omit for the server default"
    )


class TokenInfo(BaseModel):
    """A token's non-secret metadata (list view)."""

    id: str
    prefix: str
    name: str
    subject: str
    scopes: list[str]
    created_at: str
    expires_at: str | None = None
    last_used_at: str | None = None
    revoked: bool = False
    rate_limit_per_minute: int | None = None


class TokenCreatedResponse(TokenInfo):
    """A freshly created token — includes the plaintext secret exactly once."""

    token: str = Field(..., description="The bearer token; shown only at creation")


class TokenListResponse(BaseModel):
    count: int
    tokens: list[TokenInfo]


# --------------------------------------------------------------------------- #
# Device flow (RFC 8628)                                                       #
# --------------------------------------------------------------------------- #
class DeviceCodeRequest(BaseModel):
    scopes: list[str] = Field(default_factory=lambda: sorted(DEFAULT_SCOPES))


class DeviceCodeResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int
    interval: int


class DeviceApproveRequest(BaseModel):
    user_code: str
    subject: str = Field("device-user", description="Principal to bind the minted token to")


class DeviceApproveResponse(BaseModel):
    approved: bool
    user_code: str


# --------------------------------------------------------------------------- #
# OAuth dynamic client registration (RFC 7591)                                #
# --------------------------------------------------------------------------- #
class ClientRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    client_name: str = Field("mcp-client", description="Human-readable client name")
    redirect_uris: list[str] = Field(default_factory=list)
    grant_types: list[str] = Field(default_factory=lambda: ["authorization_code", "refresh_token"])
    scope: str | None = Field(None, description="Space-delimited requested scopes")
    token_endpoint_auth_method: str = Field("none", description="none | client_secret_post")


class ClientRegistrationResponse(BaseModel):
    client_id: str
    client_secret: str | None = None
    client_name: str
    redirect_uris: list[str]
    grant_types: list[str]
    scope: str
    token_endpoint_auth_method: str
