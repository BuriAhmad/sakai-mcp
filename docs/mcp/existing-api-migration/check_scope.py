"""Read-only validation of the migration inventory, not architecture/live acceptance."""

import argparse
import ast
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def load(name):
    return json.loads((HERE / name).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def function_exists(path, name):
    tree = ast.parse(path.read_text())
    parts = name.split(".")
    nodes = tree.body
    for part in parts:
        node = next((n for n in nodes if getattr(n, "name", None) == part), None)
        if node is None:
            return False
        nodes = getattr(node, "body", [])
    return True


def current_routes():
    """Extract this inventory's simple Spring mappings; reject unhandled syntax."""
    routes = set()
    base = ROOT / "apps/sakai/webapi/src/main/java/org/sakaiproject/webapi/mcp"
    for path in base.rglob("*Controller.java"):
        text = path.read_text()
        prefix = re.search(r'@RequestMapping\("([^"]+)"\)', text)
        need(prefix is not None, f"Review controller mapping syntax: {path}")
        mappings = list(
            re.finditer(r'@(Get|Post|Put|Patch|Delete)Mapping(?:\("([^"]*)"\))?', text)
        )
        need(
            len(re.findall(r"@\w+Mapping", text)) == len(mappings) + 1,
            f"Review unhandled method mapping: {path}",
        )
        for mapping in mappings:
            # Bare mappings must be immediately followed by another annotation or public.
            tail = text[mapping.end() :].lstrip()
            need(
                tail.startswith(("@", "public")),
                f"Review method mapping arguments: {path}",
            )
            full = "/api" + prefix.group(1) + (mapping.group(2) or "")
            full = full.replace("{siteId}", "{site}").replace(
                "{assignmentId}", "{assignment}"
            )
            route = (mapping.group(1).upper(), full)
            need(route not in routes, f"Duplicate route: {route}")
            routes.add(route)
    return routes


def validate_progress():
    """Compare against the reviewed implementation start without rewriting Phase 0."""
    start, progress = load("implementation-start.json"), load("progress.json")
    expected = set(progress["intentional_preexisting_paths"])
    seen = set()
    retired = {r["path"]: r for r in progress.get("retired_preexisting_paths", [])}
    routes = load("coverage.json")["legacy_routes"]
    need(len(retired) == len(progress.get("retired_preexisting_paths", [])), "Duplicate retirement")
    for path, record in retired.items():
        related = set(record.get("related_route_ids", []))
        need(related <= {r["id"] for r in routes}, "Unknown service retirement dependency")
        relevant = [r for r in routes if r["source"] == path or r["id"] in related]
        need(relevant and all(r["state"] == "retired-local" for r in relevant),
             f"Retirement has an active/unmapped route: {path}")
        need(sha(Path(record["checkpoint"])) == record["sha256"], f"Retired source checkpoint changed: {path}")
        need(not (ROOT / path).exists(), f"Retired path exists: {path}")
    for item in start["files"]:
        path = ROOT / item["path"]
        if item["path"] in retired:
            need(item["present"], "Retirement was not an original source")
            seen.add(item["path"])
            continue
        need(path.is_file() == item["present"], f"Unexpected presence change: {item['path']}")
        if item["present"]:
            changed = sha(path) != item["sha256"]
            need(not changed or item["path"] in expected, f"Unreviewed byte change: {item['path']}")
            need(oct(path.stat().st_mode & 0o777) == item["mode"], f"Mode changed: {item['path']}")
            if changed:
                seen.add(item["path"])
    need(seen == expected, f"Intentional change list differs: {seen ^ expected}")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if head != start["head"]:
        organization = load("git-organization.json")
        checkpoint = organization["migration_source_commit"]
        need(organization["baseline_commit"] == start["head"], "Organization base differs")
        need(organization["migration_branch"] == branch, "Organization branch differs")
        for name, digest in organization["immutable_manifests"].items():
            need(sha(HERE / name) == digest, f"Immutable manifest changed: {name}")
        for ancestor, descendant in ((start["head"], checkpoint), (checkpoint, head)):
            need(subprocess.run(["git", "merge-base", "--is-ancestor", ancestor, descendant],
                                cwd=ROOT, capture_output=True).returncode == 0,
                 "Reviewed checkpoint ancestry differs")
        # Pin the saved source tree. Later metadata commits do not silently approve
        # further implementation changes or alter the original start manifest.
        allowed = set(organization["post_checkpoint_metadata_paths"])
        changes = subprocess.check_output(
            ["git", "diff", "--name-only", checkpoint, head], cwd=ROOT, text=True)
        need(set(changes.splitlines()) <= allowed,
             "Review post-checkpoint source changes in a new preservation record")
        changes = subprocess.check_output(
            ["git", "diff", "--name-only", checkpoint], cwd=ROOT, text=True)
        continuation_name = Path(progress["continuation_record"]).name
        chain = []
        record_names = set()
        while True:
            need(re.fullmatch(r"continuation-[0-9]{4}-[0-9]{2}-[0-9]{2}(?:-[a-z][a-z0-9-]*)?\.json", continuation_name),
                 "Invalid continuation name")
            need(continuation_name not in record_names and len(chain) < 50,
                 "Cyclic or excessive continuation chain")
            record_names.add(continuation_name)
            continuation = load(continuation_name)
            chain.append(continuation)
            previous = continuation.get("previous_record")
            if previous is None:
                need(continuation_name == "continuation-2026-10-19.json",
                     "Continuation root differs")
                break
            need(Path(previous).name == previous, "Invalid prior continuation path")
            need(sha(HERE / previous) == continuation["previous_record_sha256"],
                 "Historical continuation changed")
            continuation_name = previous
        overlay = {}
        review_paths = set()
        for continuation in reversed(chain):
            need(continuation["head"] == head, "Continuation base differs")
            need(continuation["branch"] == branch, "Continuation branch differs")
            private_continuation = Path(continuation["private_checkpoint"])
            for name, digest in continuation["private_hashes"].items():
                need(Path(name).name == name, "Invalid checkpoint filename")
                need(sha(private_continuation / name) == digest, "Continuation checkpoint changed")
            paths = {item["path"] for item in continuation["files"]}
            need(len(paths) == len(continuation["files"]), "Duplicate continuation path")
            review_paths.update(paths)
            for item in continuation["files"]:
                relative = item["path"]
                path = ROOT / relative
                need(path.is_relative_to(ROOT) and ".." not in Path(relative).parts,
                     "Invalid continuation path")
                need(not relative.startswith(("/", "../")), "Invalid continuation path")
                if relative in overlay:
                    original_sha = overlay[relative]["after_sha256"]
                else:
                    original = subprocess.run(["git", "show", f"{head}:{relative}"],
                                              cwd=ROOT, capture_output=True)
                    original_sha = hashlib.sha256(original.stdout).hexdigest() if original.returncode == 0 else None
                need(original_sha == item["before_sha256"],
                     f"Continuation prior bytes differ: {relative}")
                overlay[relative] = item
        for relative, item in overlay.items():
            path = ROOT / relative
            need(path.is_file() == (item["after_sha256"] is not None),
                 f"Continuation presence differs: {relative}")
            if path.is_file():
                need(sha(path) == item["after_sha256"], f"Unreviewed continuation bytes: {relative}")
                need(oct(path.stat().st_mode & 0o777) == item["after_mode"], "Continuation mode differs")
        need(set(changes.splitlines()) <= allowed | review_paths,
             "Working source differs from reviewed migration and continuation checkpoints")
    need(branch == progress["branch"], "Not on the reviewed migration branch")
    need(not subprocess.check_output(["git", "diff", "--cached", "--name-only"], cwd=ROOT), "Review staged changes")
    private = Path(start["private_checkpoint"])
    need(sha(private / "manifest.json") == start["manifest_sha256"], "Starting manifest changed")
    need(sha(private / "working-tree.tar.gz") == start["archive_sha256"], "Starting archive changed")
    print(f"Implementation preservation verified: {len(start['files'])} starting paths, "
          f"{len(expected)} reviewed changes including {len(retired)} checkpointed source retirements; remaining presence/modes unchanged, index empty.")


def validate(verify_working_tree=False, verify_progress=False):
    coverage, baseline = load("coverage.json"), load("baseline.json")
    catalog_path = ROOT / "services/mcp/tests/contracts/catalog.json"
    catalog = json.loads(catalog_path.read_text())
    amendment_path = ROOT / "services/mcp/tests/contracts/local-assessment-catalog-v2.json"
    amendment = json.loads(amendment_path.read_text())
    need(sha(catalog_path) == amendment["historical_catalog_sha256"], "Amended catalog historical pin differs")
    removed = set(amendment["removed_tools"])
    need(removed == {"prepare_assignment_mcq_grades"}, "Review authorized catalog removal")
    current_catalog = {
        key: {**catalog[key], "tools": [name for name in catalog[key]["tools"] if name not in removed]}
        for key in ("00", "10", "01", "11")
    }
    for record in baseline["contracts"]:
        need(sha(ROOT / record["path"]) == record["sha256"], "Frozen contract changed")
    need(
        coverage["plan_sha256"] == baseline["plan"]["current_sha256"],
        "Plan provenance mismatch",
    )
    for key, expected in (("00", 5), ("10", 8), ("01", 18), ("11", 21)):
        need(coverage["catalogs"][key] == current_catalog[key], f"Catalog differs: {key}")
        need(len(current_catalog[key]["tools"]) == expected, f"Tool count differs: {key}")
        need(
            len(catalog[key]["templates"]) == (5 if key[1] == "1" else 0),
            f"Resource count differs: {key}",
        )
    need(
        sha(HERE / "implementation-plan.md") == coverage["canonical_plan"]["sha256"],
        "Current canonical plan hash differs; review and refresh derived provenance",
    )
    need(
        load("browser-flows.json")["plan"]["sha256"] == coverage["canonical_plan"]["sha256"],
        "Browser flow plan provenance differs",
    )
    tools = coverage["tools"]
    need(len(tools) == 21, "Tool coverage must have 21 distinct entries")
    need(
        {t["name"] for t in tools} == set(current_catalog["11"]["tools"]),
        "Tool inventory mismatch",
    )
    resources = coverage["resources"]
    need(len(resources) == 5, "Resource coverage must have five distinct entries")
    need(
        {t["uriTemplate"] for t in resources}
        == {t["uriTemplate"] for t in catalog["11"]["templates"]},
        "Resource inventory mismatch",
    )
    decisions = {d["id"] for d in coverage["decisions"]}
    need(decisions == {f"D{i}" for i in range(1, 9)}, "Decision inventory mismatch")
    routes = coverage["legacy_routes"]
    ids = {r["id"] for r in routes}
    need(len(ids) == len(routes) == 23, "Legacy route inventory mismatch")
    need(
        sum("/grading/" in r["source"] for r in routes) == 15,
        "Grading route inventory mismatch",
    )
    need(
        current_routes() == {(r["method"], r["path"]) for r in routes
                             if r["state"] != "retired-local"},
        "Native routes changed: review coverage and compatibility before retirement",
    )
    consumed = set()
    for item in tools + resources:
        need(bool(item["owner_module"]), f"Missing owner: {item}")
        implementation = ROOT / item.get("implementation", item["owner_module"])
        need(
            function_exists(implementation, item["function"]),
            f"Missing function: {item['function']}",
        )
        need(set(item["legacy_route_ids"]) <= ids, "Unknown route dependency")
        need(set(item["product_decisions"]) <= decisions, "Unknown decision")
        need(bool(item["research_cards"]), "Missing source-research coverage")
        need(bool(item["integration_gates"]), "Missing integration gate")
        historical = set(item.get("historical_legacy_route_ids", []))
        need(historical <= ids, "Unknown historical route dependency")
        retired = {r["id"] for r in routes if r["state"] == "retired-local"}
        need(not set(item["legacy_route_ids"]) & retired, "Active caller of retired route")
        need(historical <= retired, "Historical dependency is still active")
        consumed.update(item["legacy_route_ids"])
        consumed.update(historical)
    retired_tools = coverage.get("retired_public_tools", [])
    need({item["name"] for item in retired_tools} == removed, "Retired public inventory differs")
    for item in retired_tools:
        need(not item["legacy_route_ids"], "Retired tool still has active dependencies")
        historical = set(item["historical_legacy_route_ids"])
        need(historical <= {r["id"] for r in routes if r["state"] == "retired-local"}, "Retired tool depends on active route")
        need((ROOT / item["retirement_evidence"]).is_file(), "Missing tool retirement evidence")
        tree = ast.parse((ROOT / item["registration"]).read_text())
        need(not any(isinstance(n, ast.AsyncFunctionDef) and n.name == item["name"] for n in ast.walk(tree)), "Retired public tool remains registered")
        consumed.update(historical)
    # A replaced caller can leave its native route intentionally retained while
    # regression/compatibility gates are open. Record that state explicitly;
    # never invent a current Python caller or equate retention with retirement.
    retained = coverage.get("retained_compatibility_routes", [])
    retained_ids = {item["id"] for item in retained}
    need(len(retained_ids) == len(retained), "Duplicate compatibility retention")
    active = {r["id"] for r in routes if r["state"] != "retired-local"}
    need(retained_ids <= active, "Compatibility retention must name active source routes")
    need(not retained_ids & consumed, "Retained route still declares a caller")
    for item in retained:
        need(bool(item["reason"]), "Missing compatibility retention reason")
        need((ROOT / item["evidence"]).is_file(), "Missing retention evidence")
    need(consumed | retained_ids == ids, f"Unmapped native routes: {ids - consumed - retained_ids}")
    for item in tools:
        tree = ast.parse((ROOT / item["registration"]).read_text())
        need(
            any(
                isinstance(n, ast.AsyncFunctionDef) and n.name == item["name"]
                for n in ast.walk(tree)
            ),
            f"Missing public registration: {item['name']}",
        )
        need(bool(item["migration_matrix_row"]), "Missing migration matrix row")
    ledger = load("native-change-ledger.json")
    for item in ledger["files"]:
        need(item["group"] in ledger["groups"], f"Unclassified native path: {item}")
        need(
            (ROOT / item["path"]).is_file() == item["present_in_working_tree"],
            f"Native path changed: {item['path']}",
        )
    for path in ledger["storage_configuration_paths"]:
        need((ROOT / path).is_file(), f"Missing preservation dependency: {path}")
    if verify_progress:
        role_path = ROOT / "docs/mcp/development-lines/role.json"
        if role_path.is_file() and json.loads(role_path.read_text())["kind"] == "tool-migration-development":
            import runpy
            checks = runpy.run_path(str(ROOT / "docs/mcp/development-lines/verify_arrangement.py"))
            checks["verify_current"]()
        else:
            validate_progress()
    if verify_working_tree:
        current_head = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        need(current_head == baseline["head"], "HEAD differs from Phase 0 checkpoint")
        for item in baseline["working_tree"]["files"]:
            path = ROOT / item["path"]
            need(path.is_file() == item["present"], f"Presence changed: {item['path']}")
            if item["present"]:
                need(sha(path) == item["sha256"], f"Bytes changed: {item['path']}")
        archive = Path(baseline["checkpoint"]["location"])
        need(sha(archive) == baseline["checkpoint"]["sha256"], "Checkpoint changed")
    print(
        f"Scope verified: {len(tools)} tools (1 intentionally retired), 5 resources, {len(current_routes())} active native routes "
        f"({len(routes)} historical, 15 grading), "
        "4 catalogs, 8 decisions. No runtime or migration-completion claim."
    )
    if verify_working_tree:
        print(
            "All 188 preexisting changed/untracked paths and checkpoint are unchanged."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify-working-tree",
        action="store_true",
        help="Phase 0 only: prove all preexisting dirty files and private archive unchanged",
    )
    parser.add_argument(
        "--verify-progress", action="store_true",
        help="Compare implementation-start bytes with reviewed intentional changes; keep original baseline immutable",
    )
    arguments = parser.parse_args()
    try:
        validate(arguments.verify_working_tree, arguments.verify_progress)
    except (OSError, ValueError, KeyError, SyntaxError) as error:
        parser.exit(1, f"Scope validation failed: {error}\n")
