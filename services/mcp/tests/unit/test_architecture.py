"""Enforce the boundaries that make the public interface and implementation navigable."""

import ast
from pathlib import Path

SOURCE = Path(__file__).parents[2] / "src" / "sakai_mcp"


def test_tool_definitions_have_one_home():
    definitions = []
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"tool", "add_tool"}
            ):
                definitions.append(path.relative_to(SOURCE).as_posix())
    assert definitions
    assert set(definitions) == {"mcp/tools.py"}


def test_implementation_layers_do_not_import_protocol_or_skills():
    for path in SOURCE.rglob("*.py"):
        relative = path.relative_to(SOURCE)
        imports = []
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
        for module in imports:
            assert not module.startswith("skills"), (relative, module)
            if relative.parts[0] in {
                "workflows",
                "sakai",
                "grading",
                "security",
                "contracts",
            }:
                assert not module.startswith("sakai_mcp.mcp"), (relative, module)
            if relative.as_posix() == "sakai/transport.py":
                assert not module.startswith(
                    ("sakai_mcp.workflows", "sakai_mcp.sakai.")
                ), (relative, module)
            if relative.parts[0] == "grading":
                assert not module.startswith(
                    (
                        "httpx",
                        "requests",
                        "mcp",
                        "sakai_mcp.sakai",
                        "sakai_mcp.workflows",
                    )
                ), (relative, module)
