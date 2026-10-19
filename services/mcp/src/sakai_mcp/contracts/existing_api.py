"""Source-derived Sakai wire observations; not public MCP DTOs or live fixtures.

Extra native fields are discarded. Missing/null/false remain distinct through
model_fields_set. None of these observations establishes native authorization.
"""

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Annotated, Any, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictInt,
    StrictStr,
    ValidationError,
)

from sakai_mcp.errors import ErrorCode, SakaiError

Id = Annotated[StrictStr, Field(min_length=1, max_length=255)]


class WireModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)


class Site(WireModel):
    siteId: Id
    title: StrictStr
    course: StrictBool | None = None
    project: StrictBool | None = None


class Sites(WireModel):
    sites: Annotated[list[Site], Field(max_length=5000)]


class GradeSummary(WireModel):
    id: Annotated[StrictInt, Field(ge=0)]
    name: StrictStr
    siteId: Id
    score: StrictStr | None = Field(default=None, repr=False)
    notGradedYet: StrictBool
    canGrade: StrictBool
    ungraded: Annotated[StrictInt, Field(ge=0)]


class Grades(WireModel):
    grades: Annotated[list[GradeSummary], Field(max_length=10000)]


class Attachment(WireModel):
    ref: StrictStr = Field(repr=False)
    name: StrictStr | None = None
    type: StrictStr | None = None
    # Formatted/localized contentLength is deliberately not coerced to bytes.
    contentLength: StrictStr | None = None


class Submitter(WireModel):
    id: Id = Field(repr=False)
    grade: StrictStr | None = Field(default=None, repr=False)
    overridden: StrictBool | None = None


class Submission(WireModel):
    id: Id = Field(repr=False)
    hydrated: StrictBool
    submitted: StrictBool | None = None
    graded: StrictBool | None = None
    returned: StrictBool | None = None
    draft: StrictBool | None = None
    visible: StrictBool | None = None
    dateSubmittedEpochSeconds: StrictInt | None = None
    grade: StrictStr | None = Field(default=None, repr=False)
    submitters: Annotated[list[Submitter], Field(max_length=1000)] | None = Field(
        default=None, repr=False
    )
    submittedText: StrictStr | None = Field(default=None, repr=False)
    submittedAttachments: Annotated[list[Attachment], Field(max_length=1000)] | None = (
        Field(default=None, repr=False)
    )

    def hydrated_flag(self, name: str) -> bool | None:
        # Only these exact native map fields use "put true, otherwise omit".
        if name not in {"returned", "draft", "graded", "submitted"}:
            raise ValueError("Unsupported omission rule")
        if not self.hydrated:
            return None
        return False if name not in self.model_fields_set else getattr(self, name)


class Assignment(WireModel):
    id: Id
    context: Id
    title: StrictStr
    draft: StrictBool
    # Serializer variants of Instant are not guessed here. Parse only with a
    # fixture-established encoding using instant() below.
    openTime: Any = Field(default=None, repr=False)
    dueTime: Any = Field(default=None, repr=False)
    closeTime: Any = Field(default=None, repr=False)


class Gradable(WireModel):
    gradable: Assignment
    submissions: Annotated[list[Submission], Field(max_length=5000)]
    totalSubmissions: Annotated[StrictInt, Field(ge=0)]


class Coverage(WireModel):
    """Observed gaps are explicit; absence of reasons is not inferred completeness."""

    complete: StrictBool
    reasons: tuple[str, ...]
    source: str
    evidence: str = "source-derived-unexercised"


T = TypeVar("T", bound=WireModel)


def parse(model: type[T], value: Any) -> T:
    try:
        return model.model_validate(value)
    except ValidationError:
        # Pydantic diagnostics may include private payloads. Never propagate them.
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def collection(value: Any, prefix: str, *, max_rows: int = 5000) -> list[Any]:
    """Only explicit EntityBroker array/provider_collection encodings are accepted."""
    rows = value.get(prefix + "_collection") if isinstance(value, dict) else value
    if not isinstance(rows, list) or len(rows) > max_rows:
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    return rows


def course_fields(value: Any) -> list[dict[str, str]]:
    """Normalize rich sites without exposing tools/notifications or claiming access."""
    observed = parse(Sites, value)
    ids = [s.siteId for s in observed.sites]
    if len(set(ids)) != len(ids):
        raise SakaiError(ErrorCode.CONFLICT)
    return sorted(
        (
            {"id": s.siteId, "title": s.title}
            for s in observed.sites
            if s.course is True
        ),
        key=lambda row: (row["title"], row["id"]),
    )


def student_grade_rows(value: Any, site: str) -> list[GradeSummary]:
    """Defensive parsing only; a pre-request student-only scope guard is required."""
    observed = parse(Grades, value)
    if any(g.siteId != site for g in observed.grades):
        raise SakaiError(ErrorCode.CONFLICT)
    if any(g.canGrade for g in observed.grades):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if len({g.id for g in observed.grades}) != len(observed.grades):
        raise SakaiError(ErrorCode.CONFLICT)
    return sorted(observed.grades, key=lambda g: (g.name, g.id))


class InstantEncoding(StrEnum):
    SECONDS = "epoch-seconds"
    MILLISECONDS = "epoch-milliseconds"
    ISO = "iso-offset"
    JAVA_UTC = "java-utc"


def instant(value: Any, encoding: InstantEncoding) -> datetime | None:
    if value is None:
        return None
    try:
        if encoding in {InstantEncoding.SECONDS, InstantEncoding.MILLISECONDS}:
            if type(value) not in {int, float, Decimal}:
                raise ValueError
            number = Decimal(str(value))
            if not number.is_finite():
                raise ValueError
            return datetime.fromtimestamp(
                float(
                    number / (1000 if encoding == InstantEncoding.MILLISECONDS else 1)
                ),
                UTC,
            )
        if not isinstance(value, str):
            raise ValueError
        if encoding == InstantEncoding.JAVA_UTC:
            # Unknown/ambiguous server timezone abbreviations require a measured contract.
            if not value.endswith((" UTC", " GMT")):
                raise ValueError
            return datetime.strptime(value[:-4], "%Y-%m-%d %H:%M:%S").replace(
                tzinfo=UTC
            )
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.astimezone(UTC)
    except (ValueError, OverflowError, InvalidOperation, OSError):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def decimal_score(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        if not isinstance(value, str) or len(value) > 128 or value != value.strip():
            raise ValueError
        parsed = Decimal(value)
        if not parsed.is_finite():
            raise ValueError
        return parsed
    except (ValueError, InvalidOperation):
        raise SakaiError(ErrorCode.INTERNAL_ERROR) from None


def display_score(raw: str, scale: int) -> Decimal:
    """Only use when source explicitly identifies stored units and a known scale."""
    value = decimal_score(raw)
    if (
        value is None
        or type(scale) is not int
        or scale <= 0
        or value != value.to_integral_value()
    ):
        raise SakaiError(ErrorCode.INTERNAL_ERROR)
    return value / Decimal(scale)
