"""Bounded RPC/literal contract parsing; CXF invocation remains authentication-gated."""

from dataclasses import dataclass
from xml.etree import ElementTree as ET

from sakai_mcp.errors import ErrorCode, SakaiError

SOAP11 = "http://schemas.xmlsoap.org/soap/envelope/"
SERVICE = "http://webservices.sakaiproject.org/"


def xml(data: bytes) -> ET.Element:
    if len(data) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        # Reject alternate encodings and declarations before parsing; ElementTree
        # may otherwise expand internal entities. No DTD/entity input is needed.
        text = data.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError
        return ET.fromstring(text)
    except (ValueError, UnicodeError, ET.ParseError, RecursionError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def assignment_list_envelope(site: str) -> bytes:
    if not site or len(site) > 255 or any(ord(c) < 32 for c in site):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    envelope = ET.Element(f"{{{SOAP11}}}Envelope")
    body = ET.SubElement(envelope, f"{{{SOAP11}}}Body")
    operation = ET.SubElement(body, f"{{{SERVICE}}}getAssignmentsForContext")
    # The permitted future auth interceptor substitutes this empty credential
    # in memory. Python never acquires or sends a native session identifier.
    ET.SubElement(operation, "sessionid")
    ET.SubElement(operation, "context").text = site
    return ET.tostring(envelope, encoding="utf-8", xml_declaration=True)


def rpc_return(data: bytes, operation: str = "getAssignmentsForContext") -> str:
    if operation != "getAssignmentsForContext":
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    root = xml(data)
    if root.tag != f"{{{SOAP11}}}Envelope":
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    bodies = root.findall(f"{{{SOAP11}}}Body")
    if len(bodies) != 1 or len(bodies[0]) != 1:
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    response = bodies[0][0]
    if response.tag == f"{{{SOAP11}}}Fault":
        raise SakaiError(ErrorCode.DEPENDENCY_UNAVAILABLE)
    if response.tag != f"{{{SERVICE}}}{operation}Response" or len(response) != 1:
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    result = response[0]
    if (
        result.tag not in {"return", f"{{{SERVICE}}}return"}
        or len(result)
        or result.text is None
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    return result.text


@dataclass(frozen=True)
class LeanAssignment:
    id: str
    title: str
    grade_type: int
    open_time: str | None
    due_time: str | None
    close_time: str | None


def lean_assignments(data: bytes) -> tuple[LeanAssignment, ...]:
    root = xml(data)
    if root.tag != "assignments" or len(root) > 5000:
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    result = []
    for child in root:
        attrs = child.attrib
        if (
            child.tag != "assignment"
            or len(child)
            or not attrs.get("id")
            or "title" not in attrs
            or not attrs.get("gradeType", "").isdecimal()
        ):
            raise SakaiError(ErrorCode.INTERNAL_ERROR)
        result.append(
            LeanAssignment(
                attrs["id"],
                attrs["title"],
                int(attrs["gradeType"]),
                attrs.get("openTime"),
                attrs.get("dueTime"),
                attrs.get("closeTime"),
            )
        )
    if len({a.id for a in result}) != len(result):
        raise SakaiError(ErrorCode.CONFLICT)
    return tuple(result)
