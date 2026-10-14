# MCP-only grading migration: local evidence

Date: 14 October 2026. Scope: user-authorized implementation of [the MCP-only architecture](../../SAKAI_GRADING_MCP_RESOURCES.md). Source/package version 0.2.0; SDK and mcp-types remain 2.2.0. This report does not claim deployment or official academic changes. Pre-existing unrelated working-tree edits and the preserved grading-run evidence were retained.

## Implemented

- Removed grading_workspace.py and grading_artifacts.py, including interactive MSAL login, hand-built MCP requests, independent importer HTTP access, local-workspace requirements and the public artifact gateway.
- Added authenticated SDK resource/template integration for current submission/assignment files, immutable captures, manifests and server reports. Dynamic MIME, TextResourceContents/BlobResourceContents, ResourceLink and EmbeddedResource use the installed official SDK. Resource readers verify complete bytes, size/hash, scope, revision, ownership and expiry before delivery. Missing/unsupported links retain explicit metadata reasons.
- Added assignment discovery, server MCQ preparation, durable proposal readback, report resources, canonical grade-payload preparation/validation, and a resource-reading tool for tools-only hosts. All Sakai access uses the existing server's OBO adapter. Default/setup/grading/both catalogs are 5/8/19/22; grading exposes fourteen tools and five templates.
- Reused native capture/private storage and existing approved save/return contracts. Native additions are fixed delegated file/proposal routes and a grading-permission assignment list. Discovery hydrates grading evidence before hashing lazy collections. No database migration, Entra grant or capacity change is introduced.
- Extracted a pure fixed MCQ evaluator with exact decimals, explicit normalization, source identities/revisions, null-score exceptions, config/manifest/evaluator provenance and CSV formula escaping. Parsing is bounded for malformed newline-heavy submissions. Files cap at 10 MiB, captures at 100 MiB, preparations at 500 scoped roster rows and proposal JSON at 900,000 bytes. Byte reads/preparations each have a concurrency cap of two per server/adapter.
- Updated public v2 contracts separately from native v1 DTOs, repository guidance/design/skill and the existing installed grading skill. The installed skill discovers the new capabilities and stops clearly against an older server; it cannot fall back to an importer.

## Checks

**137 Python tests passed on both Python 3.11.14 and 3.14.7.** Ruff passed and mypy checked all 17 source modules successfully. The Python 3.11 run used an isolated temporary environment installed from the unchanged dependency pins and updated locked package metadata.

Protocol tests use the official SDK Client over the actual authenticated ASGI Streamable HTTP application in legacy and 2026-07-28 modes. They exercise resource discovery, ResourceLink metadata, exact text/blob bytes (CRLF/BOM/PDF/ZIP/invalid UTF-8), access revocation, proposal preparation/reconciliation, proposal/report reading, tools-only EmbeddedResource delivery and server payload hashing/native validation without commit. Other cases reject arbitrary URLs/traversal/token queries, checksum mismatch, changed identities, malformed MCQ content, wrong keys/rules and unsupported budgets/gates.

**69 native MCP webapi tests passed**, including 25 grading service tests. Added cases cover current file integrity/revision/permission checks, unsupported URL attachments, private durable proposal ownership/replay/conflict, and grading-only assignment discovery using the hydrated load. The existing native save/return/permission/concurrency/expiry regressions passed. These are local mocks/filesystem tests, not production MySQL or role/UI acceptance.

Commands (Python commands from services/mcp):

```sh
.venv/bin/pytest -q
.venv/bin/ruff check src tests
.venv/bin/mypy src
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml -pl webapi -am -Dtest='Mcp*Test' -Dsurefire.failIfNoSpecifiedTests=false test
uv lock --check --offline --directory services/mcp
./scripts/check-repo-context.sh
git diff --check
```

The skill-creator validator passed using an isolated PyYAML tool dependency; no production dependency was added. Contracts were regenerated from the actual gated SDK catalog. No container build, exact-commit CI scan or deployment is claimed.

## Read-only release preparation

The selected Azure subscription matched 55a5701c-411e-45f1-9829-9c80f526d9eb. Read-only queries showed vm-sakai-dev running, mysql-sakai-dev-55a5701c-uae Ready, and ca-mcp-sakai-dev Running with grading enabled, min/max replicas 0/2. Its current ready revision remained ca-mcp-sakai-dev--0000018 with the previously released digest sha256:5c1079b759f0c1af56dcefbbacee2152296285ca2e8247bec01982ec69a6db4b. These are a dated check, not a permanent inventory. No runtime settings were changed.

Release requires explicit authorization under the root/scoped AGENTS.md and existing release guides. Prepare a pushed exact commit and CI build/scan, verify current native storage/schema prerequisites, deploy the backward-compatible native endpoints, then release the MCP image through its separate guarded workflow. Native deployment restarts Tomcat and causes temporary Sakai downtime. Preserve scaling, OAuth/OBO configuration and official records. Retain previous native/MCP releases for rollback; older installed clients must not invoke the removed importer.

Remaining acceptance: actual intended host resource/binary response limits and approval controls; delegated TA/group/item scope and revoked/expired reads against the live adapter; real durable proposal/report access across replicas/restarts; source-change races and private-record retention/backup policies. PDF/Office/archive contents are original binary evidence; extraction, archive expansion, student-code execution and unsupported academic policies remain outside this fixed MCQ implementation. The 24-hour expiry denies resource access but does not erase historical JSON receipt/configuration records; existing operator retention policies still apply.
