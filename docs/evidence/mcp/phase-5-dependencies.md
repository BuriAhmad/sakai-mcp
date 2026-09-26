# Phase 5 dependency decisions (2026-09-26)

Status: **PASS for version selection and Python lock/install; Sakai Java build NOT RUN**.

`services/mcp/pyproject.toml` uses Python 3.11–3.14 and exact direct pins. `uv lock` resolved 53 packages and `uv sync --locked` installed 50 packages on Python 3.14.7. `uvx pip-audit --path .venv/lib/python3.14/site-packages` reported **no known vulnerabilities** among installed registry packages; the local `sakai-mcp` package was skipped as unpublished. The lockfile is `services/mcp/uv.lock`. The local `.venv` is ignored and is not evidence or a deploy artifact.

| Purpose | Selected direct pin | Version source |
| --- | --- | --- |
| MCP SDK | `mcp==2.2.0` | [Official PyPI release](https://pypi.org/project/mcp/2.2.0/) and [SDK releases](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0) |
| HTTP client | `httpx==0.28.1` | [Maintainer PyPI package](https://pypi.org/project/httpx/0.28.1/) |
| Settings | `pydantic-settings==2.15.0` | [Maintainer PyPI package](https://pypi.org/project/pydantic-settings/2.15.0/) |
| JWT/JWKS validation | `PyJWT[crypto]==2.15.0` | [Maintainer PyPI package](https://pypi.org/project/PyJWT/2.15.0/) |
| OBO | `msal==1.39.0` | [Microsoft PyPI package](https://pypi.org/project/msal/1.39.0/) and [OBO API documentation](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens) |
| Tests | `pytest==9.1.1`, `pytest-asyncio==1.4.0` | Maintainer PyPI releases; exact versions in lockfile |
| Lint/type check | `ruff==0.16.9`, `mypy==2.3.1` | Maintainer PyPI releases; exact versions in lockfile |

The SDK's [v2 release notes](https://github.com/modelcontextprotocol/python-sdk/releases/tag/v2.2.0) and [protocol guide](https://py.sdk.modelcontextprotocol.io/v2/protocol-versions/) say one `MCPServer` serves the 2026-07-28 revision and legacy 2025-era clients over Streamable HTTP. The [authorization guide](https://py.sdk.modelcontextprotocol.io/v2/run/authorization/) specifies `TokenVerifier` plus `AuthSettings`, protected-resource metadata, and HTTP bearer rejection. The [low-level server guide](https://py.sdk.modelcontextprotocol.io/v2/advanced/low-level-server/) exposes per-request `on_list_tools(ctx, params)`, which is the planned route for dynamic tool exposure. The installed 2.2.0 package confirms `Server(on_list_tools=...)` and `stateless_http` for legacy sessions. OpenTelemetry tracing is included by the SDK; no separate project OpenTelemetry instrumentation is selected yet.

Sakai 25.2 already manages `com.nimbusds:nimbus-jose-jwt` in `apps/sakai/master/pom.xml` and packages it from `apps/sakai/deploy/pom.xml`, so no new Java JWT library is needed. Its inherited **9.37.2** version is affected by [GHSA-xwmg-2g98-w7v9](https://github.com/advisories/GHSA-xwmg-2g98-w7v9), which lists **9.37.4** as patched. The tracked Maven property was raised to 9.37.4, available from [Maven Central](https://central.sonatype.com/artifact/com.nimbusds/nimbus-jose-jwt/9.37.4). Java compilation and dependency tree checks are Phase 7 verification tasks; this phase establishes a patched version before downstream token parsing is implemented.

The exact Entra claim names, audiences, and OBO credential choice are still gated by issued token evidence in Phase 6. No credentials or tokens were written to the repository.
