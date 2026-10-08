#!/usr/bin/env bash
set -Eeuo pipefail

# Run on the VM through the existing ./sakai shell path before an exact-commit
# release. Values are non-secret Entra metadata obtained from issued tokens.
# Usage: bash -s -- true TENANT ISSUER AUDIENCE SCOPE JWKS_URI [ASSIGNMENT_SETUP] < this-script
if [[ $# -lt 6 || $# -gt 7 ]]; then
  echo 'Usage: configure-mcp-sakai.sh true|false TENANT ISSUER AUDIENCE SCOPE JWKS_URI [true|false]' >&2
  exit 2
fi

sudo python3 - /opt/tomcat/sakai/local.properties "$@" <<'PY'
from pathlib import Path
import os
import re
import shutil
import sys
import tempfile

path = Path(sys.argv[1])
enabled, tenant, issuer, audience, scope, jwks_uri = sys.argv[2:8]
assignment_enabled = sys.argv[8] if len(sys.argv) == 9 else None
if assignment_enabled is not None and assignment_enabled not in ('true', 'false'):
    raise SystemExit('Assignment setup flag must be true or false')
if enabled not in ('true', 'false'):
    raise SystemExit('MCP enable flag must be true or false')
if not re.fullmatch(r'[0-9a-fA-F-]{36}', tenant):
    raise SystemExit('Invalid Entra tenant ID')
if not issuer.startswith('https://') or not jwks_uri.startswith('https://'):
    raise SystemExit('Issuer and JWKS URI must use HTTPS')
if not audience.startswith('api://') or scope != 'sakai.mcp.access':
    raise SystemExit('Unexpected downstream audience or scope')
for value in (tenant, issuer, audience, scope, jwks_uri):
    if any(c in value for c in '\r\n\\') or value != value.strip():
        raise SystemExit('Invalid MCP configuration value')
if not path.is_file():
    raise SystemExit('Sakai local.properties is missing')

begin = '# BEGIN project Sakai MCP integration'
end = '# END project Sakai MCP integration'
source = path.read_text()
if assignment_enabled is None:
    previous_flags = re.findall(r'^mcp\.assignment\.setup\.enabled=(true|false)$', source, re.MULTILINE)
    if len(previous_flags) > 1:
        raise SystemExit('Duplicate assignment setup properties')
    assignment_enabled = previous_flags[0] if previous_flags else 'false'
if source.count(begin) != source.count(end) or source.count(begin) > 1:
    raise SystemExit('MCP property block markers are inconsistent')
if begin in source:
    first = source.index(begin)
    last = source.index(end, first) + len(end)
    prefix = source[:first].rstrip('\n')
    suffix = source[last:].lstrip('\n')
    source = prefix + ('\n' if suffix else '') + suffix
block = '\n'.join((begin,
    f'mcp.integration.enabled={enabled}',
    f'mcp.integration.tenant={tenant}',
    f'mcp.integration.issuer={issuer}',
    f'mcp.integration.audience={audience}',
    f'mcp.integration.scope={scope}',
    f'mcp.integration.jwksUri={jwks_uri}',
    f'mcp.assignment.setup.enabled={assignment_enabled}',
    end))
updated = source.rstrip() + '\n\n' + block + '\n'
if updated == path.read_text():
    print('Sakai MCP properties already match')
    raise SystemExit(0)
backup = path.with_name(path.name + '.pre-mcp')
if not backup.exists():
    shutil.copy2(path, backup)
stat = path.stat()
with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.mcp-props-', delete=False) as output:
    output.write(updated)
    name = output.name
os.chmod(name, stat.st_mode & 0o777)
os.chown(name, stat.st_uid, stat.st_gid)
os.replace(name, path)
print('Updated Sakai MCP properties; use the guarded exact-commit release to restart Tomcat')
PY
