"""Bounded native form observations. No JavaScript evaluation or HTTP side effects."""

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import parse_qsl, unquote, urljoin, urlsplit

from sakai_mcp.errors import ErrorCode, SakaiError


def native_url(origin: str, base: str, candidate: str, placement: str) -> str:
    """Constrain rendered navigation to the selected native placement and origin."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,255}", placement):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
    if (
        len(candidate) > 8192
        or any(ord(c) <= 32 or ord(c) == 127 for c in candidate)
        or "\\" in candidate
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    try:
        raw_path = urlsplit(candidate).path
    except ValueError:
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None
    if re.search(r"%(?:2f|5c|25)", raw_path, re.IGNORECASE) or any(
        part in {".", ".."} for part in unquote(raw_path).split("/")
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    try:
        expected = urlsplit(origin)
        parsed = urlsplit(urljoin(base, candidate))
        prefix = f"/portal/tool/{placement}"
        if (
            parsed.scheme != "https"
            or expected.scheme != "https"
            or parsed.hostname != expected.hostname
            or (parsed.port or 443) != (expected.port or 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
            or ";" in parsed.path
            or not (parsed.path == prefix or parsed.path.startswith(prefix + "/"))
            or any(
                k.lower() in {"sakai.session", "sessionid", "jsessionid", "oauth_token"}
                for k, _ in parse_qsl(parsed.query, keep_blank_values=True)
            )
        ):
            raise ValueError
    except ValueError:
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None
    return parsed.geturl()


@dataclass(frozen=True)
class NativeForm:
    action: str = field(repr=False)
    controls: tuple[tuple[str, str], ...] = field(repr=False)
    names: frozenset[str] = field(repr=False)
    csrf: str = field(repr=False)

    def values(self, changes: dict[str, str | list[str]]) -> list[tuple[str, str]]:
        if not changes.keys() <= self.names or "sakai_csrf_token" in changes:
            raise SakaiError(ErrorCode.VALIDATION_ERROR)
        result = [(k, v) for k, v in self.controls if k not in changes]
        for key, value in changes.items():
            result.extend(
                (key, v) for v in (value if isinstance(value, list) else [value])
            )
        return result


class _Forms(HTMLParser):
    def __init__(self, selected: str) -> None:
        super().__init__(convert_charrefs=True)
        self.selected = selected
        self.matches = 0
        self.active = False
        self.in_form = False
        self.action = ""
        self.controls: list[tuple[str, str]] = []
        self.names: set[str] = set()
        self.textarea: tuple[str, list[str]] | None = None
        self.select: tuple[str, bool, list[tuple[str, bool]]] | None = None
        self.option: tuple[str | None, bool, list[str]] | None = None
        self.nodes = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.nodes += 1
        if self.nodes > 20000 or len({k for k, _ in attrs}) != len(attrs):
            raise ValueError
        a = dict(attrs)
        if tag == "form":
            if self.in_form:
                raise ValueError
            self.in_form = True
            if a.get("id") == self.selected or a.get("name") == self.selected:
                self.active = True
                self.matches += 1
                if self.matches != 1 or (a.get("method") or "get").lower() != "post":
                    raise ValueError
                if (
                    a.get("enctype", "application/x-www-form-urlencoded")
                    != "application/x-www-form-urlencoded"
                ):
                    raise ValueError
                self.action = a.get("action") or ""
            return
        if not self.active:
            return
        # Disabled container semantics need a specific fixture; never turn such
        # controls into active submissions by ignoring their container.
        if tag in {"fieldset", "optgroup"} and "disabled" in a:
            raise ValueError
        if "disabled" in a:
            if tag == "option":
                self._finish_option()
            return
        name = a.get("name")
        if tag in {"input", "select", "textarea", "button"} and name:
            if len(name) > 255 or any(ord(c) < 32 for c in name):
                raise ValueError
            self.names.add(name)
        if tag == "input" and name:
            kind = (a.get("type") or "text").lower()
            if kind in {"password", "file", "image"}:
                raise ValueError
            if kind not in {"submit", "button", "reset"} and (
                kind not in {"checkbox", "radio"} or "checked" in a
            ):
                self.controls.append(
                    (
                        name,
                        a.get("value")
                        or ("on" if kind in {"checkbox", "radio"} else ""),
                    )
                )
        elif tag == "textarea" and name:
            if self.textarea is not None:
                raise ValueError
            self.textarea = (name, [])
        elif tag == "select" and name:
            if self.select is not None:
                raise ValueError
            self.select = (name, "multiple" in a, [])
        elif tag == "option" and self.select is not None:
            self._finish_option()
            self.option = (a.get("value"), "selected" in a, [])

    def _finish_option(self) -> None:
        if self.option is not None and self.select is not None:
            value, selected, text = self.option
            self.select[2].append(
                (value if value is not None else "".join(text), selected)
            )
            self.option = None

    def handle_data(self, data: str) -> None:
        if self.active and self.textarea is not None:
            self.textarea[1].append(data)
        if self.active and self.option is not None:
            self.option[2].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "form":
            if not self.in_form:
                raise ValueError
            self.in_form = False
        if not self.active:
            return
        if tag == "textarea" and self.textarea is not None:
            name, text = self.textarea
            self.controls.append((name, "".join(text)))
            self.textarea = None
        elif tag == "option":
            self._finish_option()
        elif tag == "select" and self.select is not None:
            self._finish_option()
            name, multiple, options = self.select
            chosen = [v for v, selected in options if selected]
            if not multiple and len(chosen) > 1:
                raise ValueError
            if not multiple and not chosen and options:
                chosen = [options[0][0]]
            self.controls.extend((name, v) for v in chosen)
            self.select = None
        elif tag == "form":
            if self.select is not None or self.textarea is not None:
                raise ValueError
            self.active = False


def native_form(
    data: bytes, selected: str, origin: str, base: str, placement: str
) -> NativeForm:
    if len(data) > 1_000_000:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    try:
        parser = _Forms(selected)
        parser.feed(data.decode("utf-8-sig"))
        parser.close()
        if parser.matches != 1 or parser.active or parser.in_form:
            raise ValueError
        tokens = [v for k, v in parser.controls if k == "sakai_csrf_token"]
        if len(tokens) != 1 or not tokens[0] or len(tokens[0]) > 512:
            raise ValueError
        action = native_url(origin, base, parser.action, placement)
        return NativeForm(
            action, tuple(parser.controls), frozenset(parser.names), tokens[0]
        )
    except (UnicodeError, ValueError, RecursionError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None
