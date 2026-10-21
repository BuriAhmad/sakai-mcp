"""Strict A14 fields from the existing native model/EntityBroker codec."""

from datetime import UTC, datetime

from pydantic import Field, StrictBool, StrictInt, StrictStr

from sakai_mcp.contracts.existing_api import Id, WireModel, parse
from sakai_mcp.errors import ErrorCode, SakaiError


class RawAssignmentState(WireModel):
    id: Id
    context: Id
    scaleFactor: StrictInt = Field(ge=1)
    maxGradePoint: StrictInt = Field(ge=0)
    releaseGrades: StrictBool
    deleted: StrictBool
    draft: StrictBool
    isGroup: StrictBool
    title: StrictStr = Field(max_length=65535)
    instructions: StrictStr | None = Field(max_length=65535)
    allowPeerAssessment: StrictBool
    contentReview: StrictBool
    groups: list[Id] = Field(max_length=5000)
    attachments: list[StrictStr] = Field(max_length=20)
    visibleDate: "NativeInstant | None"
    openDate: "NativeInstant | None"
    dueDate: "NativeInstant | None"
    closeDate: "NativeInstant | None"
    properties: dict[str, StrictStr] = Field(max_length=1000, repr=False)


class NativeInstant(WireModel):
    epochSecond: StrictInt
    nano: StrictInt = Field(ge=0, le=999999999)

    def stamp(self) -> str:
        try:
            base = datetime.fromtimestamp(self.epochSecond, UTC).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        except (ValueError, OverflowError, OSError):
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY) from None
        return (
            base + (("." + f"{self.nano:09d}".rstrip("0")) if self.nano else "") + "Z"
        )


RawAssignmentState.model_rebuild()


def raw_assignment_state(
    value: object, site: str, assignment: str
) -> RawAssignmentState:
    if not isinstance(value, dict) or not isinstance(value.get("assignment"), dict):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if value.get("context") != site or value.get("assignmentId") != assignment:
        raise SakaiError(ErrorCode.CONFLICT)
    raw = parse(RawAssignmentState, value["assignment"])
    if raw.context != site or raw.id != assignment:
        raise SakaiError(ErrorCode.CONFLICT)
    return raw
