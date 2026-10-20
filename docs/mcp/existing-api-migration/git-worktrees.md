# Independent Sakai development worktrees — 19 October 2026

Both worktrees share Git objects/history and have separate source directories,
indexes and build environments. Neither checkout changes the running environment.
All branch and commit operations here were local; nothing was pushed or deployed.

| Development line | Branch | Worktree | Starting commit |
| --- | --- | --- | --- |
| Original custom native API | `codex/sakai-custom-native-api` | `/Users/burhanahmadkhan/Desktop/sakai-mcp-custom-native` | `208d69ac624910a29a7529934ddcc18bbac853e8` |
| Ongoing existing HTTP/browser migration | `codex/replace-custom-sakai-api` | `/Users/burhanahmadkhan/Desktop/sakai-mcp` | Same original baseline; saved migration source `d447ec4ef8c3e9efb0a768d693c568927eec7044` |

`main` and `origin/main` remain at `208d69ac`; no remote references were changed.
The custom branch is exactly that committed baseline. It includes the original
flat Java controllers and Python `sakai_client.py`, all 23 custom business routes,
setup/grading gates and MCP resources. **It does not include the later uncommitted
restructuring, fixes, support work or migration.** Historical release documents
are dated evidence, not verification of today's runtime.

The migration is still incomplete: eight default tools use existing HTTP, nine
custom routes are retired locally, fourteen remain, and fourteen tools plus all
five resource families still need completion (R01 has partial inline reads).
Only authentication/session integration may be added natively during further
migration. See [current limitations](tool-limitations.md) and the canonical plan;
this Git organization does not change their acceptance gates.

## What is recoverable

The following explicit commits are on the migration branch, in order:

1. `062b2845` — preexisting CLI/SSH support, ignore rules, editor-assistant guidance,
   seeding Skill and historical evidence. Existing bytes were retained, including
   the extra EOF blank line in `scripts/lib/config.sh`. These are preservation
   changes, not newly validated runtime behavior.
2. `b168e8cf` — archived preimplementation source/test/guide/CI checkpoint. Its 170
   explicit paths were reconstructed directly into the index from the private
   18 October archive and checked against `implementation-start.json` hashes;
   the current working files were never overwritten. This includes restructuring
   and four already-present unwired HTTP scaffolds. It is an archival intermediate
   commit, not a fresh independently tested release or a claim of pure refactoring.
   Planning records, private/editor files and subsequent migration are excluded.
3. `d447ec4e` — complete current migration implementation, tests, dependency lock,
   original manifests and research/status evidence (129 explicit paths). Its
   difference from the preceding commit separates migration work from the saved
   preimplementation source. Earlier native source retirements remain recoverable
   from that ancestor and their original private checkpoints.
4. The documentation/verification commit following these records this arrangement.
   Use `git log -4 --oneline` for its final ID. No source implementation changed
   during organization.

Before this work only the flat baseline was committed. The baseline and start
archives remain unchanged, including their deliberate exclusions; they were never
complete runtime backups. The newly committed archived checkpoint improves source
recovery without pretending it existed in the original baseline. Original editor
files, ignored scripts, credentials, runtime data, uploads and build outputs stay
local and are not present in the custom worktree or newly tracked in Git.

An additional owner-only private checkpoint is at:
`/Users/burhanahmadkhan/Downloads/Sakai-Git-Organization-2026-10-19/`.
It contains `files-before.json`, a verified `all-local-files-before.tar.gz` of all
30,887 original files/links outside `.git` (962,080,032 original bytes), initial
Git status/diff/refs and explicit commit path lists. Unlike the original archives,
it includes private/editor/ignored files. Never publish or commit it. The manifest
and archive hashes are in [git-organization.json](git-organization.json).
Local checks can regenerate ignored caches/Maven output; their original bytes are
also in that private archive. Recover individual files only after comparing their
hashes and ensuring newer work will not be overwritten. Never extract over a whole
checkout. The Git object database itself is shared, retained in place and not part
of this filesystem archive.

## Use either line

Open each directory in its own editor window, or change directories:

```sh
# Original native implementation
cd /Users/burhanahmadkhan/Desktop/sakai-mcp-custom-native
git status --short --branch
cd services/mcp
uv sync --locked
uv run --no-sync pytest -q

# Continue the existing HTTP migration
cd /Users/burhanahmadkhan/Desktop/sakai-mcp
git status --short --branch
python3 docs/mcp/existing-api-migration/check_scope.py --verify-progress
cd services/mcp
uv sync --locked
../../scripts/check-mcp.sh
```

There is no need to run `git switch` to use the other line. Git prevents checking
out the same branch in two worktrees; do not force that restriction. Use
`git worktree list` to see the arrangement. Commit work in its own checkout with
reviewed explicit paths. If switching other branches inside either checkout,
first inspect status and separately preserve local/untracked/private files;
never reset or clean to make switching possible. The original four editor files
are intentionally still untracked in the migration directory and unchanged.

Use each worktree's own `.venv`, `uv.lock` and Maven output. Do not share generated
class files, package output, credentials or port-bound local processes between
versions. Both expose the same service routes and default ports if run: select
separate local ports/configurations before starting concurrent processes.
No application service was started for this organization (tests used synthetic
in-process/local-container targets).

## Runtime and data compatibility

Git selection affects source only. Deploying either line requires separate
explicit authorization and the existing native/MCP release procedures. An older
Python caller cannot use native code whose required routes were removed. The
migration also needs its delegated-auth libraries/registrations and supported
existing handlers; source tests do not prove those are deployed. Preserve the
reviewed N1/P0 → accepted P1 → N2 release ordering in migration evidence.

Do not interpret switching back to the custom baseline as a database or storage
rollback. Neither worktree inventories or restores live schema, native revision,
feature properties, delegated sessions, durable journal configuration or records.
Keep submission versions, proposals, exports, receipts, attachments and cleanup
ownership intact. D3 concurrency and D6 durable-store/live acceptance remain open;
the saved source is locally developable, not fully migration-complete or newly
approved for production. No academic records or stored runtime data were changed.

The preexisting CLI support has a known source-level inconsistency retained for
preservation: `ssh-sakai.sh`, `copy-to-sakai.sh` and `open-ssh-access.sh` still
source `azure.sh` although their SSH helpers moved to `ssh.sh`. Do not use those
commands as evidence of operational acceptance; correcting them is separate work.

## Local verification

`--verify-progress` retains the
original 201-path/46-change comparison, frozen contracts, mode/presence checks and
original start/retirement checkpoint hashes. It now also validates the recorded
migration commit ancestry, immutable original manifests and saved source tree.
Only the four explicit organization metadata paths can differ after `d447ec4e`;
new implementation requires a new reviewed preservation record. Phase 0's
`--verify-working-tree` intentionally remains historical and fails on later work.

Fresh checks on 19 October:

| Check | Result |
| --- | --- |
| Custom baseline Python | Locked sync; Ruff lint; mypy (17 source files); **137 tests passed** in its own environment |
| Custom endpoint/caller integrity | All **23** Spring routes exactly match the historical inventory; matching original Python V1/setup/grading/discovery/file/artifact/proposal callers inspected; clean tracked/untracked Git status |
| Migration Python | Locked sync; Ruff lint/format (115 files); mypy (64 source files); **399 tests passed** |
| Migration Java 17 | Focused reactor **96 tests in 19 suites**, zero failures/errors/skips, BUILD SUCCESS |
| Preservation/scope | 201 starting paths, 46 intentional changes, five retirement checkpoints; 22 tools, five resources, 14 active/23 historical routes, four catalogs, eight decisions |
| Immutable archives/manifests | Original baseline archive, start manifest/archive, baseline/start JSON and all five retired-source checkpoints unchanged |
| Complete local preservation | New archive read back against every original file/link; 30,847 original files unchanged in place; two intentional metadata edits and 38 regenerated ignored check outputs; no unexpected changes, every original also retained in archive |
| Shell/repository | Bash syntax (21 scripts/CLI), ShellCheck errors (38 tracked CLI/deployment scripts), repository guidance and final organization diff whitespace passed |

The full local ShellCheck sweep also encountered sixteen **preexisting ignored**
provisioning fragments under `deployment/artifacts/` without shebangs. They were
left untouched and excluded from the tracked-source result above. The original
support commit retains its preexisting extra EOF blank line; the final metadata
commit's diff has no whitespace errors. None of these checks establishes live
acceptance. Docker/image/security scans, Bicep compilation and custom-baseline
Java tests were not rerun for this Git-only task.

Java reproduction (from the migration worktree, Java 17):

```sh
JAVA_HOME=/opt/homebrew/opt/openjdk@17 mvn -f apps/sakai/pom.xml \
  -pl webapi,mcp-auth,announcement/announcement-tool/tool,entitybroker/core-providers -am \
  '-Dtest=Mcp*Test,Delegated*Test,PortalContainerTest,Existing*Test,LoginControllerTests' \
  -Dsurefire.failIfNoSpecifiedTests=false test
```

The local Java log is `/tmp/sakai-git-organization-java.log`; the private
preservation comparison is `files-after-verification.json` in the new private
checkpoint directory. Logs/caches are local evidence only. Final Git state has
an empty index, no tracked modifications, the original four untracked editor
files in the migration worktree, and a clean custom worktree.
