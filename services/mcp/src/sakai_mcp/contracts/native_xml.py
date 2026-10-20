"""Bounded native XML parsing without DTDs or entity expansion."""

from xml.etree import ElementTree as ET

from sakai_mcp.errors import ErrorCode, SakaiError


def xml(data: bytes) -> ET.Element:
    if len(data) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        # Reject alternate encodings and declarations before parsing; ElementTree
        # may otherwise expand internal entities. No DTD/entity input is needed.
        text = data.decode("utf-8-sig")
        if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
            raise ValueError
        root = ET.fromstring(text)
        pending = [(root, 0)]
        count = 0
        while pending:
            element, depth = pending.pop()
            count += 1
            if depth > 32 or count > 20000:
                raise ValueError
            pending.extend((child, depth + 1) for child in element)
        return root
    except (ValueError, UnicodeError, ET.ParseError, RecursionError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None
