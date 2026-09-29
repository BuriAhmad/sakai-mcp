"""Validated service configuration. Credentials are loaded by the OBO provider."""

from uuid import UUID

from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid")

    environment: str = "development"
    mcp_public_url: HttpUrl
    sakai_base_url: HttpUrl
    entra_tenant_id: UUID
    mcp_resource_client_id: UUID
    mcp_issuer: HttpUrl
    mcp_audience: str
    sakai_issuer: HttpUrl
    mcp_required_scope: str = "mcp.access"
    mcp_jwks_uri: HttpUrl
    sakai_resource_client_id: UUID
    sakai_audience: str
    sakai_downstream_scope: str = "sakai.mcp.access"
    institutional_id_claim: str = "extn.SakaiEid"
    http_connect_timeout: float = Field(default=2.0, gt=0, le=30)
    http_read_timeout: float = Field(default=10.0, gt=0, le=60)
    page_size_default: int = Field(default=20, ge=1, le=100)
    page_size_max: int = Field(default=50, ge=1, le=100)
    log_level: str = "INFO"

    @property
    def mcp_resource_uri(self) -> str:
        """OAuth identity for the fixed Streamable HTTP endpoint."""
        return f"{str(self.mcp_public_url).rstrip('/')}/mcp"

    @field_validator("mcp_public_url", "sakai_base_url", "mcp_issuer", "sakai_issuer", "mcp_jwks_uri")
    @classmethod
    def require_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https" or value.username or value.password or value.fragment:
            raise ValueError("Service URLs must be HTTPS without credentials or fragments")
        return value

    @field_validator("sakai_base_url")
    @classmethod
    def require_sakai_origin(cls, value: HttpUrl) -> HttpUrl:
        if value.path not in (None, "", "/") or value.query:
            raise ValueError("Sakai base URL must be an HTTPS origin")
        return value

    @field_validator("mcp_public_url")
    @classmethod
    def require_mcp_origin(cls, value: HttpUrl) -> HttpUrl:
        if value.path not in (None, "", "/") or value.query:
            raise ValueError("MCP public URL must be an HTTPS origin")
        return value

    @field_validator("mcp_audience")
    @classmethod
    def require_v2_mcp_audience(cls, value: str, info) -> str:
        client_id = info.data.get("mcp_resource_client_id")
        if client_id is None or value != str(client_id) or value != value.strip():
            raise ValueError("MCP v2 token audience must match the MCP app client ID")
        return value

    @field_validator("sakai_audience")
    @classmethod
    def require_sakai_resource_audience(cls, value: str) -> str:
        if not value.startswith("api://") or not value[6:] or value != value.strip():
            raise ValueError("Sakai audience must be a nonempty api:// resource identifier")
        return value

    @field_validator("mcp_required_scope", "sakai_downstream_scope")
    @classmethod
    def require_scope(cls, value: str) -> str:
        if not value or value != value.strip() or any(char.isspace() for char in value):
            raise ValueError("Expected scope must be one nonempty value")
        return value
