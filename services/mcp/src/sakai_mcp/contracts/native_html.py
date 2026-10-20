"""Bounded native HTML observations; never execute scripts or follow arbitrary URLs."""

from dataclasses import dataclass, field
from html.parser import HTMLParser

from sakai_mcp.errors import ErrorCode, SakaiError

VOID = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)


@dataclass(repr=False)
class Element:
    tag: str
    attrs: dict[str, str]
    children: list["Element | str"] = field(default_factory=list)

    def text(self) -> str:
        if self.tag in {"script", "style"}:
            return ""
        return "".join(c if isinstance(c, str) else c.text() for c in self.children)

    def find(
        self, *, tag: str | None = None, css: str | None = None, id: str | None = None
    ) -> list["Element"]:
        result = []
        for child in self.children:
            if isinstance(child, Element):
                if (
                    (tag is None or child.tag == tag)
                    and (css is None or css in child.attrs.get("class", "").split())
                    and (id is None or child.attrs.get("id") == id)
                ):
                    result.append(child)
                result.extend(child.find(tag=tag, css=css, id=id))
        return result


class _Html(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Element("root", {})
        self.stack = [self.root]
        self.nodes = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.nodes += 1
        if (
            self.nodes > 20000
            or len(self.stack) > 128
            or len(dict(attrs)) != len(attrs)
        ):
            raise ValueError
        element = Element(tag, {k: v or "" for k, v in attrs})
        self.stack[-1].children.append(element)
        if tag not in VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        # HTML permits omitted end tags. Close only an existing matching ancestor.
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        self.stack[-1].children.append(data)


def html(data: bytes) -> Element:
    if len(data) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        parser = _Html()
        parser.feed(data.decode("utf-8-sig"))
        parser.close()
        return parser.root
    except (UnicodeError, ValueError, RecursionError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def one(elements: list[Element]) -> Element:
    if len(elements) != 1:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    return elements[0]
