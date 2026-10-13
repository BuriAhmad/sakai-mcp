#!/usr/bin/env bash
set -Eeuo pipefail

# Run on the Sakai VM. Enable only after the submission schema and private
# persistent storage have been prepared and verified.
# Usage: bash -s -- true|false /var/lib/sakai-grading < this-script
if [[ $# -ne 2 || ( "$1" != true && "$1" != false ) ]]; then
  echo 'Usage: configure-assignment-grading-sakai.sh true|false ABSOLUTE_STORAGE_PATH' >&2
  exit 2
fi

sudo python3 - /opt/tomcat/sakai/local.properties "$@" <<'PY'
from pathlib import Path
import os
import shutil
import stat
import sys
import tempfile

properties = Path(sys.argv[1])
enabled, storage_name = sys.argv[2:]
storage = Path(storage_name)
if not storage.is_absolute() or '..' in storage.parts or '\n' in storage_name or '\r' in storage_name:
    raise SystemExit('Storage path must be a clean absolute path')
if not storage.is_dir() or storage.is_symlink() or storage.resolve() != storage:
    raise SystemExit('Storage directory must exist and be canonical')
storage_stat = storage.stat()
if storage_stat.st_uid != __import__('pwd').getpwnam('tomcat').pw_uid or stat.S_IMODE(storage_stat.st_mode) != 0o700:
    raise SystemExit('Storage must be owned by tomcat with mode 0700')
if not properties.is_file():
    raise SystemExit('Sakai local.properties is missing')

begin = '# BEGIN project Sakai assignment grading'
end = '# END project Sakai assignment grading'
source = properties.read_text()
if source.count(begin) != source.count(end) or source.count(begin) > 1:
    raise SystemExit('Grading property markers are inconsistent')
if begin in source:
    first = source.index(begin)
    last = source.index(end, first) + len(end)
    source = source[:first].rstrip('\n') + '\n' + source[last:].lstrip('\n')
block = '\n'.join((begin,
    f'mcp.assignment.grading.enabled={enabled}',
    f'mcp.assignment.grading.storage={storage}',
    end))
updated = source.rstrip() + '\n\n' + block + '\n'
if updated == properties.read_text():
    print('Sakai grading properties already match')
    raise SystemExit(0)

backup = properties.with_name(properties.name + '.pre-grading')
if not backup.exists():
    shutil.copy2(properties, backup)
original = properties.stat()
with tempfile.NamedTemporaryFile(mode='w', dir=properties.parent, prefix='.grading-props-', delete=False) as output:
    output.write(updated)
    temporary = Path(output.name)
os.chmod(temporary, stat.S_IMODE(original.st_mode))
os.chown(temporary, original.st_uid, original.st_gid)
os.replace(temporary, properties)
print('Updated Sakai grading properties; restart through the guarded release')
PY
