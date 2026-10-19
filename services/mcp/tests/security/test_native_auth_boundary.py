"""Source-check the permitted native exception; skip outside this repository tree."""

import re
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[4]
NATIVE = ROOT / "apps/sakai"
if not NATIVE.is_dir():
    pytest.skip(
        "native-source audit requires the repository checkout", allow_module_level=True
    )


def test_auth_jar_has_only_identity_session_framework_dependencies_and_no_endpoints():
    module = NATIVE / "mcp-auth"
    permitted = {
        "javax.servlet-api",
        "sakai-kernel-api",
        "sakai-component-manager",
        "sakai-kernel-util",
        "nimbus-jose-jwt",
        "slf4j-api",
    }
    root = ET.parse(module / "pom.xml").getroot()
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    runtime = {
        d.findtext("m:artifactId", namespaces=ns)
        for d in root.findall("m:dependencies/m:dependency", ns)
        if d.findtext("m:scope", namespaces=ns) != "test"
    }
    assert runtime <= permitted
    assert root.findtext("m:properties/m:deploy.target", namespaces=ns) == "shared"
    for path in (module / "src/main/java").rglob("*.java"):
        text = path.read_text()
        for package in [
            "org.sakaiproject.assignment",
            "org.sakaiproject.grading",
            "org.sakaiproject.announcement",
            "org.sakaiproject.calendar",
            "org.sakaiproject.content",
            "java.nio.file",
            "java.sql",
            "javax.persistence",
        ]:
            assert not re.search(
                r"^import\s+" + re.escape(package), text, re.MULTILINE
            ), path
        assert not re.search(
            r"@(RestController|Controller|EntityCustomAction|WebMethod|WebService|Entity|Table)\b",
            text,
        ), path
        assert not re.search(r"extends\s+HttpServlet\s*[{<]", text), path
        assert "pushAdvisor" not in text and "SecurityAdvisor" not in text
    assert "<module>mcp-auth</module>" in (NATIVE / "pom.xml").read_text()


@pytest.mark.parametrize(
    "folder,servlet,forward",
    [
        ("portal/portal-charon/charon", "sakai.portal.charon", False),
        ("assignment/tool", "sakai.assignment.grades", True),
        ("announcement/announcement-tool/tool", "sakai.announcements", True),
        ("gradebookng/tool", "sakai.gradebookng", True),
        ("content/content-tool/tool", "sakai.filepicker", True),
        ("entitybroker/tool", "sakai.entitybroker.direct", False),
    ],
)
def test_context_filters_are_scoped_to_existing_named_servlets_and_ordered(
    folder, servlet, forward
):
    root = ET.parse(NATIVE / folder / "src/webapp/WEB-INF/web.xml").getroot()
    ns = {"w": root.tag[1:].split("}")[0]}
    direct_filters = root.findall("w:filter", ns)
    assert len(direct_filters) == len(root.findall(".//w:filter", ns))
    mappings = []
    for mapping in root.findall("w:filter-mapping", ns):
        name = mapping.findtext("w:filter-name", namespaces=ns).strip()
        target = (mapping.findtext("w:servlet-name", namespaces=ns) or "").strip()
        if name in {"mcp.credentials", "mcp.session"}:
            assert target == servlet
            assert not mapping.findall("w:url-pattern", ns)
            assert {d.text for d in mapping.findall("w:dispatcher", ns)} == (
                {"REQUEST", "FORWARD", "INCLUDE"} if forward else {"REQUEST"}
            )
        if target == servlet:
            mappings.append(name)
    assert (
        mappings.index("mcp.credentials")
        < mappings.index("sakai.request")
        < mappings.index("mcp.session")
    )
    if folder == "entitybroker/tool":
        assert (
            mappings.index("mcp.credentials")
            < mappings.index("oauth.pre")
            < mappings.index("sakai.request")
            < mappings.index("oauth.post")
            < mappings.index("mcp.session")
        )
