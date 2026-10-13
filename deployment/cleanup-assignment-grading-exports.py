#!/usr/bin/env python3
"""Remove expired grading export bytes while preserving operation receipts."""

import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import re
import stat
import sys

KEY = re.compile(r"[0-9a-f]{64}\Z")
ARTIFACT = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: cleanup-assignment-grading-exports.py ABSOLUTE_STORAGE_PATH")
    root = Path(sys.argv[1])
    if not root.is_absolute() or root.is_symlink() or not root.is_dir() or root.resolve() != root:
        raise SystemExit("Invalid grading storage directory")
    info = root.stat()
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise SystemExit("Grading storage must belong to the current user with mode 0700")

    expired = removed = skipped = 0
    for directory in root.iterdir():
        if not KEY.fullmatch(directory.name) or directory.is_symlink() or not directory.is_dir():
            continue
        lock = directory / "lock"
        if lock.is_symlink():
            skipped += 1
            continue
        try:
            fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            try:
                fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                record = directory / "record.json"
                if record.is_symlink() or not record.is_file() or record.stat().st_size > 1_000_000:
                    continue
                data = json.loads(record.read_text())
                if not isinstance(data, dict) or not ARTIFACT.fullmatch(str(data.get("export_id", ""))):
                    continue
                expiry = datetime.fromisoformat(str(data["expires_at"]).replace("Z", "+00:00"))
                if expiry.tzinfo is None or expiry > datetime.now(timezone.utc):
                    continue
                expired += 1
                for file in directory.iterdir():
                    if ARTIFACT.fullmatch(file.name) and file.is_file() and not file.is_symlink():
                        file.unlink()
                        removed += 1
            finally:
                os.close(fd)
        except (BlockingIOError, FileNotFoundError, OSError, ValueError, KeyError, json.JSONDecodeError):
            skipped += 1
    print(f"expired_exports={expired} removed_artifacts={removed} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
