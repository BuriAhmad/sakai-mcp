# Assignment grading: preserved CLI run, 14 October 2026

The user requested preservation of the complete successful CLI grading session, including the details hidden behind the terminal's “Show details” controls. The original session recording was located and copied byte-for-byte. This page is its Git-trackable index; the exact transcript and supporting records are in a private local archive.

## Recorded outcome

The archived session records the user's end-to-end grading request at 15:27:10 Asia/Karachi, approval to save at 15:36:57, and separate approval to return at 15:46:51 on 14 October 2026. Its final response at 15:48:22 reports that all 73 approved scores matched direct Sakai readback and that those rows were released and returned, with feedback. Six submissions with format issues and one missing submission remained ungraded. There was no linked Gradebook item.

The return batches contained 40 and 33 rows. The session also records `AMBIGUOUS_WRITE_OUTCOME`, an operation-status `CONFLICT`, and receipts requiring manual reconciliation. It reports resolving the return state through direct grade readback. These errors and reconciliation steps are preserved in the transcript; this run does not establish clean return receipts or close every acceptance gate.

These statements describe the archived session, not a new live environment check. Archiving did not perform any Sakai mutation or Azure runtime change.

## Exact archive

Local directory: [`private-runs/2026-10-14-assignment-grading/`](private-runs/2026-10-14-assignment-grading/README.md), relative to this evidence directory.

| File | Preserved material |
| --- | --- |
| [`session.jsonl`](private-runs/2026-10-14-assignment-grading/session.jsonl) | Original session recording, unchanged: 448 records and 3,821,600 bytes |
| [`transcript.md`](private-runs/2026-10-14-assignment-grading/transcript.md) | Readable chronological messages, all 55 recorded tool calls and 55 outputs, with UTC timestamps and source record numbers |
| [`terminal-paste.txt`](private-runs/2026-10-14-assignment-grading/terminal-paste.txt) | Exact text of the terminal scrollback supplied by the user, including preceding login attempts |
| [`grading-workspace/`](private-runs/2026-10-14-assignment-grading/grading-workspace/) | 189 supporting files copied from the temporary grading workspace, including submissions, plan, scripts, proposals, feedback, exceptions and available receipts/readbacks |
| [`manifest.json`](private-runs/2026-10-14-assignment-grading/manifest.json) | Source provenance, byte counts, event counts and file hashes |
| [`SHA256SUMS`](private-runs/2026-10-14-assignment-grading/SHA256SUMS) | Integrity inventory for all other archive files |

Original session ID: `01a139f2-86a0-78d0-9cc0-053803f2238b`. Recorded client: Codex CLI `0.159.2`. Source recording: `~/.codex/sessions/2026/10/14/rollout-2026-10-14T15-25-57-01a139f2-86a0-78d0-9cc0-053803f2238b.jsonl`. Source grading workspace: `/private/tmp/sakai-grading-cs210-20261014`.

SHA-256 of the unchanged session recording:

```text
1b93e585193591a1eb1f92024d1cff233d42c2bd94f7d07d97d934d7a761be11
```

The private directory is excluded from Git and has owner-only permissions. The root and MCP guides require private grading content, test-user identifiers, credentials and uploaded content to stay out of Git. The exact archive is retained without redacting or rewriting the original recording; credential-store files were not copied. This index contains no student-level grading records.

## Fidelity and retention

The raw JSONL file is the authoritative unchanged recording. The readable transcript adds headings and timestamps while preserving recorded message text, tool inputs and complete recorded output payloads. It does not expand internal reasoning. It cannot restore output truncated before recording, terminal colors/cursor movements, or unrecorded activity. The supplied terminal paste is separate from the full successful session and does not itself contain the whole grading conversation.

The archive now lives outside `/private/tmp`. It survives removal of the original temporary grading workspace, but it remains a local archive: Git commits, pushes and fresh clones do **not** include it. Preserve the entire private directory in a private backup for recovery after machine loss. A clone containing only this index will have unavailable private-file links.

To verify integrity, run from the archive directory:

```sh
shasum -a 256 -c SHA256SUMS
```

See the [13 October release evidence](assignment-grading-release.md) for the deployment baseline and remaining acceptance limits.
