#!/usr/bin/env bash
set -Eeuo pipefail

# Sakai 25.2's docker/tomcat/bin/setenv.sh and master/pom.xml list these Java
# opens. The VM bootstrap already includes some; add the remaining upstream
# options without replacing runtime secrets or other local settings.
TOMCAT_SETENV=${TOMCAT_SETENV:-/opt/tomcat/bin/setenv.sh}
sudo python3 - "$TOMCAT_SETENV" <<'PY'
from pathlib import Path
import shutil
import sys

path = Path(sys.argv[1])
source = path.read_text()
if 'export JAVA_OPTS=' not in source:
    raise SystemExit('Expected JAVA_OPTS in Tomcat setenv.sh')
opens = (
    'jdk.management/com.sun.management.internal',
    'java.base/java.io',
    'java.base/java.util',
    'java.base/java.util.concurrent',
    'java.base/java.util.concurrent.locks',
    'java.base/java.lang',
    'java.base/java.lang.invoke',
    'java.base/java.math',
    'java.base/java.lang.reflect',
    'java.base/java.time',
    'java.base/java.text',
    'java.management/sun.management',
    'java.desktop/java.awt.font',
    'java.desktop/javax.swing.tree',
)
missing = [f'--add-opens={name}=ALL-UNNAMED' for name in opens
           if f'--add-opens={name}=ALL-UNNAMED' not in source]
if missing:
    backup = path.with_name(path.name + '.pre-mcp-java-opens')
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(source.rstrip() + '\nexport JAVA_OPTS="$JAVA_OPTS ' + ' '.join(missing) + '"\n')
    print(f'Added {len(missing)} Sakai 25.2 Java opens; restart Tomcat to apply')
else:
    print('Sakai 25.2 Java opens already present')
PY
