#!/usr/bin/env python3
"""Read-only source/commit checks for the explicitly separated development lines."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]


def git(*args, cwd=ROOT):
    return subprocess.check_output(['git', *args], cwd=cwd, text=True).strip()


def need(value, message):
    if not value:
        raise ValueError(message)


def changed(a, b, *paths):
    out = git('diff', '--name-only', a, b, '--', *paths)
    return set(out.splitlines()) if out else set()


def verify_current():
    role = json.loads((ROOT / 'docs/mcp/development-lines/role.json').read_text())
    need(git('branch', '--show-current') == role['branch'], 'Wrong development branch')
    need(not git('diff', '--name-only'), 'Uncommitted tracked source changes need review')
    need(not git('diff', '--cached', '--name-only'), 'Staged changes need review')
    need(git('merge-base', '--is-ancestor', role['extraction_anchor'], role['source_anchor']) == '', 'Extraction ancestry differs')
    need(git('merge-base', '--is-ancestor', role['source_anchor'], 'HEAD') == '', 'Source ancestry differs')
    need(changed(role['source_anchor'], 'HEAD') <= set(role['metadata_allowlist']), 'Unreviewed code after source anchor')
    if role['kind'] == 'auth-development':
        need(changed(role['original_baseline'], 'HEAD', 'services/mcp/src') <= set(role.get('legacy_client_auth_paths', [])), 'Original Python business host changed outside declared auth files')
        need(changed(role['original_baseline'], 'HEAD', 'services/mcp/tests') <= {'services/mcp/tests/security/test_native_auth_boundary.py'}, 'Original Python tests/contracts changed')
        need(changed(role['original_baseline'], 'HEAD', 'apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp') <= set(role.get('legacy_native_auth_paths', [])), 'Original native business changed outside declared auth files')
        need(not changed(role['original_baseline'], 'HEAD', 'apps/sakai/assignment/api', 'apps/sakai/assignment/impl'), 'Original Assignment domain changed')
        need((ROOT / 'apps/sakai/mcp-auth/src/main/java/org/sakaiproject/mcpauth/DelegatedCredentialGuard.java').is_file(), 'Auth module absent')
    elif role['kind'] == 'tool-migration-development':
        need(not changed(role['mixed_source'], role['extraction_anchor'], 'services/mcp/src'), 'Migrated Python implementation changed during initial extraction')
        changes = changed(role['mixed_source'], role['extraction_anchor'], 'services/mcp/tests')
        need(changes <= {'services/mcp/tests/security/test_native_auth_boundary.py'}, 'Migrated tests/contracts/evaluator baselines changed')
        changes = changed(role['mixed_source'], role['extraction_anchor'], 'apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp')
        need(changes <= {'apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp/README.md'}, 'Migrated native business implementation changed')
        need(not git('ls-files', 'apps/sakai/mcp-auth'), 'Server auth module leaked into tool line')
        need('sakai-mcp-auth' not in (ROOT / 'apps/sakai/webapi/pom.xml').read_text(), 'Auth build wiring leaked into tool line')
        need('DelegatedCredentialGuard' not in (ROOT / 'apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/WebAppConfiguration.java').read_text(), 'Auth registration leaked into tool line')
        for path in role['restored_native_wiring']:
            expected = subprocess.check_output(['git', 'show', role['original_baseline'] + ':' + path], cwd=ROOT)
            actual = (ROOT / path).read_bytes()
            need(actual == expected, 'Native wiring differs from pre-auth source: ' + path)
        protocol = ROOT / role['client_protocol']['path']
        need(hashlib.sha256(protocol.read_bytes()).hexdigest() == role['client_protocol']['sha256'], 'Client protocol pin changed')
    else:
        raise ValueError('Unknown role')
    print('Development-line source/commit verification passed: ' + role['kind'])
    print('No live/auth acceptance, deployment or proof-failure repair claim.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', action='store_true', help='Verify the calling development line')
    parser.parse_args()
    try:
        verify_current()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')
