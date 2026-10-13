"""Private local grading evidence and deterministic MCQ proposals. No academic writes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID

import httpx
import msal  # type: ignore[import-untyped]

from sakai_mcp.grading_models import Artifact, GetAssignmentSubmissionExportResult


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def payload_hash(
    kind: str, course: str, assignment: str, revision: str, grades: list[dict[str, Any]]
) -> str:
    return digest(
        canonical(
            {
                "kind": kind,
                "course_id": course,
                "assignment_id": assignment,
                "expected_assignment_revision": revision,
                "grades": sorted(
                    grades, key=lambda r: (r["submission_id"], r["sakai_user_id"])
                ),
            }
        )
    )


def private_workspace(root: Path) -> None:
    root = root.absolute()
    for parent in (root, *root.parents):
        if (parent / ".git").exists():
            raise ValueError("Grading workspace must be outside Git checkouts")
        if parent.is_symlink():
            raise ValueError("Workspace ancestors must not be symlinks")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for directory, names, files in os.walk(root, followlinks=False):
        if any((Path(directory) / name).is_symlink() for name in names + files):
            raise ValueError("Workspace contents must not be symlinks")
    if os.name == "posix" and root.stat().st_mode & 0o077:
        raise ValueError("Workspace must be owner-only (mode 0700)")


def safe_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
        raise ValueError("Unsafe identifier")
    return value


def write_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("xb") as output:
        os.chmod(temporary, 0o600)
        output.write(canonical(value) + b"\n")
        output.flush()
        os.fsync(output.fileno())
    temporary.replace(path)


def import_export(
    root: Path, origin: str, course: str, assignment: str, export: str, token: str
) -> None:
    """Credentials stay in this process; tool output contains descriptors only."""
    private_workspace(root)
    safe_id(course)
    safe_id(assignment)
    UUID(export)
    parsed = urlsplit(origin)
    if (
        parsed.scheme != "https"
        or parsed.path not in ("", "/")
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Expected a trusted HTTPS MCP origin")
    origin = origin.rstrip("/")
    # Status/manifest is an MCP tool call; OAuth is the same institution-issued delegated token.
    headers = {
        "Authorization": "Bearer " + token,
        "MCP-Protocol-Version": "2026-07-28",
        "Accept": "application/json, text/event-stream",
    }
    artifacts: list[Artifact] = []
    snapshot: dict[str, Any] | None = None
    with httpx.Client(timeout=60, follow_redirects=False, trust_env=False) as http:
        initialize = http.post(
            origin + "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2026-07-28",
                    "capabilities": {},
                    "clientInfo": {"name": "sakai-grading-importer", "version": "1"},
                },
            },
        )
        initialize.raise_for_status()
        if "mcp-session-id" in initialize.headers:
            headers["Mcp-Session-Id"] = initialize.headers["mcp-session-id"]
        http.post(
            origin + "/mcp",
            headers=headers,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
        ).raise_for_status()
        cursor = None
        seen: set[str] = set()
        while True:
            response = http.post(
                origin + "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {
                        "name": "get_assignment_submission_export",
                        "arguments": {
                            "course_id": course,
                            "assignment_id": assignment,
                            "export_id": export,
                            "cursor": cursor,
                            "limit": 100,
                        },
                    },
                },
            )
            response.raise_for_status()
            message = response.json()
            if "error" in message or message["result"].get("isError"):
                raise ValueError("Export status unavailable; inspect through MCP")
            page = GetAssignmentSubmissionExportResult.model_validate(
                message["result"]["structuredContent"]
            )
            if page.export_id != export or page.status not in {"ready", "partial"}:
                raise ValueError("Export not ready")
            if snapshot is None:
                snapshot = page.model_dump()
            elif (
                page.request_sha256 != snapshot["request_sha256"]
                or page.rows
                != GetAssignmentSubmissionExportResult.model_validate(snapshot).rows
            ):
                raise ValueError("Export manifest changed between pages")
            artifacts.extend(page.artifacts)
            cursor = page.next_cursor
            if cursor is None:
                break
            if cursor in seen:
                raise ValueError("Repeated manifest cursor")
            seen.add(cursor)
        if snapshot is None:
            raise ValueError("No manifest")

        def call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
            response = http.post(
                origin + "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {"name": name, "arguments": arguments},
                },
            )
            response.raise_for_status()
            value = response.json()
            if "error" in value or value["result"].get("isError"):
                raise ValueError("Authoritative grading metadata unavailable")
            return value["result"]["structuredContent"]

        from sakai_mcp.grading_models import (
            GetAssignmentGradingContextResult,
            ListAssignmentSubmissionsResult,
        )

        context = GetAssignmentGradingContextResult.model_validate(
            call(
                "get_assignment_grading_context",
                {"course_id": course, "assignment_id": assignment},
            )
        )
        roster_rows: list[dict[str, Any]] = []
        roster_revision = None
        roster_cursor = None
        while True:
            roster_page = ListAssignmentSubmissionsResult.model_validate(
                call(
                    "list_assignment_submissions",
                    {
                        "course_id": course,
                        "assignment_id": assignment,
                        "cursor": roster_cursor,
                        "limit": 100,
                    },
                )
            )
            if not roster_page.completeness.complete or roster_revision not in (
                None,
                roster_page.snapshot_revision,
            ):
                raise ValueError("Incomplete or changed roster")
            roster_revision = roster_page.snapshot_revision
            roster_rows.extend(r.model_dump() for r in roster_page.items)
            roster_cursor = roster_page.next_cursor
            if roster_cursor is None:
                break
            if len(roster_rows) > 5000:
                raise ValueError("Roster over budget")
        for filename, value in (
            ("context.json", context.model_dump()),
            ("roster.json", roster_rows),
        ):
            file = root / filename
            if file.exists():
                if json.loads(file.read_text()) != value:
                    # Observation timestamps may change but never overwrite recorded academic state.
                    if filename == "context.json":
                        old = json.loads(file.read_text())
                        old.pop("observed_at", None)
                        compare = context.model_dump()
                        compare.pop("observed_at", None)
                        if old != compare:
                            raise ValueError(
                                "Use a new run for changed grading context"
                            )
                    else:
                        raise ValueError("Use a new run for changed roster")
            else:
                write_json(file, value)
        if len({a.artifact_id for a in artifacts}) != len(artifacts):
            raise ValueError("Duplicate artifact identifiers")
        if sum(a.size_bytes for a in artifacts) > 100 * 1024 * 1024:
            raise ValueError("Export over budget")
        local = []
        for artifact in artifacts:
            if artifact.submission_id is None:
                raise ValueError("Submission artifact lacks authoritative identity")
            safe_id(artifact.submission_id)
            UUID(artifact.artifact_id)
            directory = root / "submissions" / "raw" / artifact.submission_id
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)
            if directory.is_symlink() or directory.resolve() != directory.absolute():
                raise ValueError("Unsafe raw directory")
            target = directory / artifact.artifact_id
            if target.exists():
                if (
                    target.is_symlink()
                    or digest(target.read_bytes()) != artifact.sha256
                ):
                    raise ValueError("Existing raw evidence differs")
            else:
                path = "/grading-artifacts/" + "/".join(
                    quote(v, safe="")
                    for v in (course, assignment, export, artifact.artifact_id)
                )
                if artifact.download_path != path:
                    raise ValueError("Untrusted artifact path")
                part = target.with_suffix(".part")
                if part.exists():
                    if part.is_symlink():
                        raise ValueError("Unsafe temporary artifact")
                    part.unlink()  # Per-file retry starts again; source artifact remains immutable.
                count = 0
                sha = hashlib.sha256()
                try:
                    with http.stream(
                        "GET",
                        origin + path,
                        headers={"Authorization": "Bearer " + token},
                    ) as download:
                        download.raise_for_status()
                        if download.headers.get("x-content-sha256") != artifact.sha256:
                            raise ValueError("Artifact header checksum mismatch")
                        with part.open("xb") as output:
                            os.chmod(part, 0o600)
                            for chunk in download.iter_bytes():
                                count += len(chunk)
                                if (
                                    count > artifact.size_bytes
                                    or count > 10 * 1024 * 1024
                                ):
                                    raise ValueError("Artifact size exceeds inventory")
                                output.write(chunk)
                                sha.update(chunk)
                    if (
                        count != artifact.size_bytes
                        or sha.hexdigest() != artifact.sha256
                    ):
                        raise ValueError("Artifact integrity mismatch")
                    os.chmod(part, 0o400)
                    part.replace(target)
                finally:
                    if part.exists():
                        part.unlink()
            local.append(
                artifact.model_dump() | {"raw_path": str(target.relative_to(root))}
            )
        snapshot["artifacts"] = local
        snapshot["course_id"] = course
        snapshot["assignment_id"] = assignment
        manifest = root / "manifest.json"
        if manifest.exists():
            prior = json.loads(manifest.read_text())
            if prior != snapshot:
                raise ValueError("Use a new run directory for changed evidence")
        else:
            write_json(manifest, snapshot)


def grade_mcq(root: Path, config_path: Path) -> list[dict[str, Any]]:
    private_workspace(root)
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    if config["grading"]["method"] != "deterministic_mcq":
        raise ValueError("Unsupported grading procedure")
    contract, rules, normalization = (
        config["submission_contract"],
        config["grading"],
        config["normalization"],
    )
    key = rules["key"]
    alphabet = contract["alphabet"]
    if (
        not key
        or len(key) != contract["answer_count"]
        or any(a not in alphabet for a in key)
    ):
        raise ValueError("Answer key disagrees with contract")
    if (
        contract.get("file_count") != 1
        or contract.get("encoding") != "utf-8"
        or rules.get("negative_marking") is not False
        or Decimal(rules["per_incorrect"]) != 0
    ):
        raise ValueError("Unsupported MCQ rules")
    per_correct = Decimal(rules["per_correct"])
    maximum = Decimal(rules["max_points"])
    if (
        not per_correct.is_finite()
        or per_correct < 0
        or not maximum.is_finite()
        or maximum != per_correct * len(key)
    ):
        raise ValueError("Key points disagree with maximum")
    if config.get("policies", {}).get("late_penalty") is not None:
        raise ValueError(
            "Late penalties require a separately reviewed deterministic rule"
        )
    manifest_bytes = (root / "manifest.json").read_bytes()
    manifest = json.loads(manifest_bytes)
    if (
        config["course_id"] != manifest["course_id"]
        or config["assignment_id"] != manifest["assignment_id"]
    ):
        raise ValueError("Wrong assignment configuration")
    if (root / "context.json").exists():
        context = json.loads((root / "context.json").read_text())
        if (
            config.get("assignment_revision")
            != context["assignment"]["configuration_revision"]
            or Decimal(context["assignment"]["max_points"]) != maximum
        ):
            raise ValueError("Grading plan disagrees with Sakai revision or maximum")
    previous = root / "results" / "proposals.json"
    if previous.exists() and any(
        row["config_sha256"] != digest(config_bytes)
        or row["manifest_sha256"] != digest(manifest_bytes)
        or row["script_sha256"] != digest(Path(__file__).read_bytes())
        for row in json.loads(previous.read_text())
    ):
        raise ValueError("Use a new run for changed grading rules, evidence or script")
    artifacts = {a["artifact_id"]: a for a in manifest["artifacts"]}
    proposals = []
    normalized = root / "submissions" / "normalized"
    normalized.mkdir(mode=0o700, parents=True, exist_ok=True)
    for row in manifest["rows"]:
        issues: list[str] = []
        total = None
        evidence = []
        ids = row["artifact_ids"]
        if row["status"] != "ready":
            issues.append("incomplete_capture")
        if len(row["sakai_user_ids"]) != 1:
            issues.append("group_identity_unsupported")
        if len(ids) != 1:
            issues.append("expected_one_txt_file")
        answers = None
        if not issues:
            artifact = artifacts[ids[0]]
            path = root / artifact["raw_path"]
            if (
                path.is_symlink()
                or not path.resolve().is_relative_to(root.resolve())
                or digest(path.read_bytes()) != artifact["sha256"]
            ):
                raise ValueError("Raw evidence integrity failure")
            name = artifact["original_name"] or ""
            suffix = Path(name).suffix
            if (
                suffix.lower() if normalization.get("extension_case") else suffix
            ) != ".txt":
                issues.append("wrong_format")
            expected_name = config.get("expected_filenames", {}).get(
                row["sakai_user_ids"][0]
            )
            if expected_name is None and contract.get("filename"):
                issues.append("filename_identity_rule_unresolved")
            elif (
                expected_name is not None
                and name != expected_name
                and config.get("identity", {}).get("filename_mismatch") != "recoverable"
            ):
                issues.append("filename_mismatch")
            try:
                data = path.read_bytes()
                if data.startswith(b"%PDF") or b"\x00" in data:
                    issues.append("wrong_detected_format")
                text = data.decode("utf-8")
                if text.startswith("\ufeff"):
                    issues.append("unexpected_bom")
                answers = text.splitlines()
                if normalization.get("trim_answer_whitespace"):
                    answers = [a.strip() for a in answers]
                if normalization.get("uppercase_answers"):
                    answers = [a.upper() for a in answers]
                if len(answers) != len(key):
                    issues.append("wrong_answer_count")
                if any(a not in alphabet for a in answers):
                    issues.append("invalid_answer")
                if not answers:
                    issues.append("empty_submission")
            except UnicodeDecodeError:
                issues.append("unreadable_encoding")
        if not issues and answers is not None:
            total = str(
                per_correct
                * sum(
                    answer == expected
                    for answer, expected in zip(answers, key, strict=True)
                )
            )
            target = normalized / (safe_id(row["submission_id"]) + ".txt")
            normalized_bytes = ("\n".join(answers) + "\n").encode()
            if target.exists():
                if target.is_symlink() or target.read_bytes() != normalized_bytes:
                    raise ValueError("Use a new run for changed normalization")
            else:
                target.write_bytes(normalized_bytes)
                os.chmod(target, 0o600)
            evidence = [
                {
                    "line": i + 1,
                    "answer": a,
                    "correct": a == k,
                    "points": str(per_correct if a == k else Decimal(0)),
                }
                for i, (a, k) in enumerate(zip(answers, key, strict=True))
            ]
        proposals.append(
            {
                "submission_id": row["submission_id"],
                "sakai_user_id": row["sakai_user_ids"][0]
                if len(row["sakai_user_ids"]) == 1
                else None,
                "score": total,
                "max_score": str(maximum),
                "method": "deterministic_mcq",
                "review_status": "review_required" if issues else "proposed",
                "issues": issues,
                "criteria": evidence,
                "content_revision": row["content_revision"],
                "config_sha256": digest(config_bytes),
                "manifest_sha256": digest(manifest_bytes),
                "script_sha256": digest(Path(__file__).read_bytes()),
            }
        )
    if (root / "roster.json").exists():
        roster = json.loads((root / "roster.json").read_text())
        by_submission = {
            row["submission_id"]: row
            for row in roster
            if row["submission_id"] is not None
        }
        for proposal in proposals:
            source = by_submission.get(proposal["submission_id"])
            if (
                source is None
                or source["content_revision"] != proposal["content_revision"]
            ):
                proposal["score"] = None
                proposal["issues"].append("source_revision_changed")
                proposal["review_status"] = "review_required"
            proposal["grade_revision"] = source["grade_revision"] if source else None
            proposal["late_status"] = source["late_status"] if source else "unknown"
        selected_ids = {row["submission_id"] for row in proposals}
        for row in roster:
            if (
                row["submission_id"] in selected_ids
                and row["submission_id"] is not None
            ):
                continue
            proposals.append(
                {
                    "submission_id": row["submission_id"],
                    "sakai_user_id": row["student"]["sakai_user_id"]
                    if row["student"]
                    else None,
                    "score": None,
                    "max_score": str(maximum),
                    "method": None,
                    "review_status": "review_required",
                    "issues": [
                        "missing_submission"
                        if row["submission_id"] is None
                        else "not_selected"
                    ],
                    "criteria": [],
                    "content_revision": row["content_revision"],
                    "grade_revision": row["grade_revision"],
                    "late_status": row["late_status"],
                    "config_sha256": digest(config_bytes),
                    "manifest_sha256": digest(manifest_bytes),
                    "script_sha256": digest(Path(__file__).read_bytes()),
                }
            )
    results = root / "results"
    results.mkdir(mode=0o700, exist_ok=True)
    write_json(results / "proposals.json", proposals)
    for filename, selected in (
        ("marks.csv", proposals),
        ("review-required.csv", [r for r in proposals if r["issues"]]),
    ):
        with (results / filename).open("w", newline="") as stream:
            os.chmod(results / filename, 0o600)
            writer = csv.writer(stream)
            writer.writerow(
                [
                    "submission_id",
                    "sakai_user_id",
                    "score",
                    "max_score",
                    "review_status",
                    "issues",
                ]
            )
            for row in selected:
                values = [
                    row[k]
                    for k in (
                        "submission_id",
                        "sakai_user_id",
                        "score",
                        "max_score",
                        "review_status",
                    )
                ] + [";".join(row["issues"])]
                writer.writerow(
                    [
                        "'" + v
                        if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                        else v
                        for v in values
                    ]
                )
    return proposals


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    grade = sub.add_parser("mcq")
    grade.add_argument("workspace", type=Path)
    grade.add_argument("config", type=Path)
    download = sub.add_parser("import-export")
    download.add_argument("workspace", type=Path)
    download.add_argument("login_config", type=Path)
    download.add_argument("course")
    download.add_argument("assignment")
    download.add_argument("export")
    args = parser.parse_args()
    if args.command == "mcq":
        rows = grade_mcq(args.workspace, args.config)
        print(
            f"Prepared {len(rows)} proposals; {sum(bool(r['issues']) for r in rows)} require review. No grades written."
        )
    else:
        login = json.loads(args.login_config.read_text())
        tenant = str(UUID(login["tenant_id"]))
        client_id = str(UUID(login["client_id"]))
        origin = login["mcp_origin"]
        parsed = urlsplit(origin)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "mcp.smartdigest.app"
            or parsed.path not in ("", "/")
        ):
            raise ValueError(
                "Login configuration must use the institutional MCP origin"
            )
        public = msal.PublicClientApplication(
            client_id, authority="https://login.microsoftonline.com/" + tenant
        )
        token = public.acquire_token_interactive(
            scopes=[origin.rstrip("/") + "/mcp/mcp.access"]
        )
        if "access_token" not in token:
            raise ValueError("Institutional OAuth login failed")
        import_export(
            args.workspace,
            origin,
            args.course,
            args.assignment,
            args.export,
            token["access_token"],
        )
        print("Export imported and checksums verified. No grades written.")


if __name__ == "__main__":
    main()
