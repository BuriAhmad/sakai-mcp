"""Source-defined fields overwritten by AssignmentEntityProvider.setGrade."""

from decimal import Decimal

from sakai_mcp.contracts.submissions import WireSubmission
from sakai_mcp.errors import ErrorCode, SakaiError

PROPERTIES = {
    "allow_resubmit_number": "resubmitNumber",
    "allow_resubmit_closeTime": "resubmitDate",
    "allow_extension_closeTime": "extensionDate",
}


def plain(value: str | None) -> str:
    # The native handler trims blanks, removes configured invalid Unicode and
    # may rewrite HTML links. This first subset preserves exact ASCII plain text.
    if value is None or value == "":
        return ""
    if (
        not value.isascii()
        or value != value.strip()
        or any(c in value for c in "<>&")
        or any((ord(c) < 32 and c not in "\r\n\t") or ord(c) == 127 for c in value)
    ):
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    return value


def preserved(row: WireSubmission) -> dict[str, str]:
    if row.properties is None:
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    result = {
        "privateNotes": plain(row.privateNotes),
        "feedbackText": plain(row.feedbackText),
        "feedbackComment": plain(row.feedbackComment),
    }
    for key, name in PROPERTIES.items():
        value = row.properties.get(key)
        if value is None:
            continue
        if not isinstance(value, str) or not value.isascii():
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        if name == "resubmitNumber":
            if value not in {"-1", *map(str, range(11))}:
                raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        elif not value.isdecimal() or not 0 < int(value) <= 253402300799000:
            raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
        result[name] = value
    if ("resubmitNumber" in result) != ("resubmitDate" in result):
        # Sending either missing component deletes or changes the old override.
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    return result


def score(value: str, maximum: str | None) -> None:
    if maximum is None or not Decimal(value).is_finite():
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if Decimal(value) != Decimal(value).to_integral_value():
        raise SakaiError(ErrorCode.UNSUPPORTED_CAPABILITY)
    if not 0 <= Decimal(value) <= Decimal(maximum):
        raise SakaiError(ErrorCode.VALIDATION_ERROR)
