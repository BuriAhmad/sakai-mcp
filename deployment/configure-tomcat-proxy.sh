#!/usr/bin/env bash
set -Eeuo pipefail

# Run on the Sakai VM. Trust forwarded scheme information only from the local
# Nginx proxy; never expose Tomcat's HTTP connector on the VM network.
TOMCAT_SERVER_XML=${TOMCAT_SERVER_XML:-/opt/tomcat/conf/server.xml}
sudo python3 - "$TOMCAT_SERVER_XML" <<'PY'
from pathlib import Path
import re
import shutil
import sys

path = Path(sys.argv[1])
source = path.read_text()
connector = re.compile(r'<Connector\s+port="8080"\s+([^>]*?)>', re.DOTALL)
matches = list(connector.finditer(source))
if len(matches) != 1:
    raise SystemExit('Expected exactly one HTTP connector on port 8080')
tag = matches[0].group(0)
if 'address=' in tag and 'address="127.0.0.1"' not in tag:
    raise SystemExit('HTTP connector already has an unexpected bind address')
if 'address=' not in tag:
    tag = tag.replace('port="8080"', 'port="8080" address="127.0.0.1"', 1)
if 'URIEncoding=' not in tag:
    tag = tag.replace('port="8080"', 'port="8080" URIEncoding="UTF-8"', 1)
updated = source[:matches[0].start()] + tag + source[matches[0].end():]

valve = ('<Valve className="org.apache.catalina.valves.RemoteIpValve" '
         'internalProxies="127\\.\\d{1,3}\\.\\d{1,3}\\.\\d{1,3}|::1|0:0:0:0:0:0:0:1" '
         'remoteIpHeader="x-forwarded-for" protocolHeader="x-forwarded-proto" />')
if 'org.apache.catalina.valves.RemoteIpValve' not in updated:
    if updated.count('</Engine>') != 1:
        raise SystemExit('Expected exactly one Tomcat Engine element')
    updated = updated.replace('</Engine>', '  ' + valve + '\n    </Engine>', 1)
elif updated.count('org.apache.catalina.valves.RemoteIpValve') != 1:
    raise SystemExit('Expected at most one RemoteIpValve')

if updated != source:
    backup = path.with_name(path.name + '.pre-mcp-proxy')
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(updated)
    print(f'Updated {path}; restart Tomcat to apply')
else:
    print(f'{path} already has the local proxy configuration')
PY
