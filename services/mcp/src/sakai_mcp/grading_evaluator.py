"""Pure deterministic grading and report formatting; no filesystem or network access."""

import csv
import hashlib
import inspect
import io
import json
import re
from decimal import Decimal
from typing import Any

ENGINE_VERSION = "sakai-mcq-2"


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


def evaluate_mcq(
    config: dict[str, Any],
    context: dict[str, Any],
    roster: list[dict[str, Any]],
    manifest: dict[str, Any],
    files: dict[str, bytes],
) -> list[dict[str, Any]]:
    """Only explicit, supported rules yield scores; incomplete or invalid rows stay null."""
    contract, rules, normalization = (
        config["submission_contract"],
        config["grading"],
        config["normalization"],
    )
    key, alphabet = rules["key"], contract["alphabet"]
    per_correct, maximum = Decimal(rules["per_correct"]), Decimal(rules["max_points"])
    if (
        not key
        or len(key) != contract["answer_count"]
        or any(a not in alphabet for a in key)
        or contract["file_count"] != 1
        or contract["encoding"] != "utf-8"
        or rules["method"] != "deterministic_mcq"
        or rules["negative_marking"] is not False
        or Decimal(rules["per_incorrect"]) != 0
        or not per_correct.is_finite()
        or per_correct < 0
        or not maximum.is_finite()
        or maximum != per_correct * len(key)
        or config["policies"]["late_penalty"] is not None
    ):
        raise ValueError("Unsupported or inconsistent MCQ rules")
    if (
        config["course_id"] != manifest["course_id"]
        or config["assignment_id"] != manifest["assignment_id"]
        or config["assignment_revision"]
        != context["assignment"]["configuration_revision"]
        or context["assignment"]["max_points"] is None
        or Decimal(context["assignment"]["max_points"]) != maximum
        or not context["completeness"]["complete"]
        or not context["supported"]["prepare"]
    ):
        raise ValueError("Grading configuration disagrees with authoritative state")
    provenance = {
        "config_sha256": digest(canonical(config)),
        "manifest_sha256": digest(canonical(manifest)),
        "engine_version": ENGINE_VERSION,
        "engine_sha256": digest(inspect.getsource(evaluate_mcq).encode()),
    }
    artifacts = {a["artifact_id"]: a for a in manifest["artifacts"]}
    if len(artifacts) != len(manifest["artifacts"]):
        raise ValueError("Duplicate artifacts")
    by_submission = {
        r["submission_id"]: r for r in roster if r["submission_id"] is not None
    }
    proposals: list[dict[str, Any]] = []
    for row in manifest["rows"]:
        issues: list[str] = []
        ids, users = row["artifact_ids"], row["sakai_user_ids"]
        source = by_submission.get(row["submission_id"])
        uid = users[0] if len(users) == 1 else None
        if row["status"] != "ready":
            issues.append("incomplete_capture")
        if len(users) != 1:
            issues.append("group_identity_unsupported")
        if len(ids) != 1:
            issues.append("expected_one_txt_file")
        if source is None or source["content_revision"] != row["content_revision"]:
            issues.append("source_revision_changed")
        elif uid not in [s["sakai_user_id"] for s in source["submitters"]]:
            issues.append("source_identity_changed")
        elif source["status"] not in {"submitted", "ungraded_resubmission"}:
            issues.append("source_not_eligible")
        answers = None
        if not issues:
            artifact = artifacts.get(ids[0])
            data = files.get(ids[0])
            if artifact is None or artifact["submission_id"] != row["submission_id"]:
                raise ValueError("Artifact identity mismatch")
            if data is None:
                issues.append("download_failed")
            else:
                if (
                    digest(data) != artifact["sha256"]
                    or len(data) != artifact["size_bytes"]
                ):
                    raise ValueError("Evidence integrity failure")
                name = artifact["original_name"] or ""
                extension = name.rsplit(".", 1)[-1] if "." in name else ""
                if (
                    extension.lower() if normalization["extension_case"] else extension
                ) != "txt":
                    issues.append("wrong_format")
                expected = config["expected_filenames"].get(uid)
                if expected is None and contract["filename"]:
                    issues.append("filename_identity_rule_unresolved")
                elif (
                    expected is not None
                    and name != expected
                    and config["identity"]["filename_mismatch"] != "recoverable"
                ):
                    issues.append("filename_mismatch")
                if data.startswith(b"%PDF") or b"\x00" in data:
                    issues.append("wrong_detected_format")
                try:
                    text = data.decode("utf-8")
                    if text.startswith("\ufeff"):
                        issues.append("unexpected_bom")
                    # Match splitlines semantics but retain at most key-length+1 items.
                    # A malformed newline-heavy file must not allocate millions of strings.
                    answers = (
                        re.split(
                            r"\r\n|[\n\r\v\f\x1c-\x1e\x85\u2028\u2029]",
                            text,
                            maxsplit=len(key),
                        )
                        if text
                        else []
                    )
                    if answers and answers[-1] == "":
                        answers.pop()
                    if normalization["trim_answer_whitespace"]:
                        answers = [a.strip() for a in answers]
                    if normalization["uppercase_answers"]:
                        answers = [a.upper() for a in answers]
                    if len(answers) != len(key):
                        issues.append("wrong_answer_count")
                    if any(a not in alphabet for a in answers):
                        issues.append("invalid_answer")
                    if not answers:
                        issues.append("empty_submission")
                except UnicodeDecodeError:
                    issues.append("unreadable_encoding")
        score, evidence = None, []
        if not issues and answers is not None:
            score = str(
                per_correct * sum(a == k for a, k in zip(answers, key, strict=True))
            )
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
                "sakai_user_id": uid,
                "score": score,
                "max_score": str(maximum),
                "method": "deterministic_mcq",
                "review_status": "review_required" if issues else "proposed",
                "issues": issues,
                "criteria": evidence,
                "content_revision": row["content_revision"],
                "grade_revision": source["grade_revision"] if source else None,
                "late_status": source["late_status"] if source else "unknown",
                **provenance,
            }
        )
    selected = {r["submission_id"] for r in proposals}
    for row in roster:
        if row["submission_id"] is not None and row["submission_id"] in selected:
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
                **provenance,
            }
        )
    return proposals


def report_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    fields = [
        "submission_id",
        "sakai_user_id",
        "score",
        "max_score",
        "review_status",
        "issues",
    ]
    writer.writerow(fields)
    for row in rows:
        values = [row[k] for k in fields[:-1]] + [";".join(row["issues"])]
        writer.writerow(
            [
                "'" + v
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                else v
                for v in values
            ]
        )
    return output.getvalue()
