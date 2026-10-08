"""Bounded assignment setup contracts. No student grades or submissions are returned."""

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    @field_validator("*", mode="after")
    @classmethod
    def valid_metadata(cls, value, info: ValidationInfo):
        name = info.field_name or ""
        stamps = {
            "visible_at",
            "open_at",
            "due_at",
            "close_at",
            "start_at",
            "end_at",
            "observed_at",
            "verified_at",
            "window_start",
            "window_end",
            "until",
        }
        if isinstance(value, str) and name in stamps:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None or "T" not in value or value.endswith("-00:00"):
                raise ValueError("Expected known RFC3339 offset")
        if isinstance(value, str) and name == "due_on":
            date.fromisoformat(value)
        if (
            isinstance(value, str)
            and (name.endswith(("_id", "_reference")) or name in {"external_id", "external_app"})
            and (not value or len(value) > 255)
        ):
            raise ValueError("Invalid reference length")
        return value


class Category(Contract):
    id: Annotated[str, Field(min_length=1, max_length=255)]
    name: Annotated[str, Field(min_length=1, max_length=255)]
    weight_percent: Annotated[float, Field(ge=0, le=100)] | None
    equal_weight_items: bool
    drop_lowest: Annotated[int, Field(ge=0)]
    drop_highest: Annotated[int, Field(ge=0)]
    keep_highest: Annotated[int, Field(ge=0)]
    extra_credit: bool
    drop_keep_enabled: bool


class GradebookItem(Contract):
    id: Annotated[str, Field(min_length=1, max_length=255)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    max_points: Annotated[float, Field(gt=0)] | None
    due_on: str | None
    category_id: str | None
    released: bool
    counted: bool
    extra_credit: bool
    externally_maintained: bool
    external_id: str | None
    external_app: str | None
    gradable_reference: str | None


class CalendarEvent(Contract):
    id: Annotated[str, Field(min_length=1, max_length=255)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    start_at: str
    end_at: str
    type: Annotated[str, Field(min_length=1, max_length=100)]
    assignment_id: str | None
    owner_tool_id: str | None


class Resubmission(Contract):
    count: Annotated[int, Field(ge=-1)]
    until: str | None


class GradebookLink(Contract):
    gradebook_item_id: str | None
    external_id: str | None
    category_id: str | None
    mode: Literal["none", "new_external", "existing", "unknown"]
    status: Literal["not_requested", "linked", "missing", "mismatch", "unknown"]
    released: bool | None
    counted: bool | None


class CalendarLink(Contract):
    event_id: str | None
    calendar_reference: str | None
    status: Literal["not_requested", "linked", "missing", "mismatch", "unknown"]


class Assignment(Contract):
    id: Annotated[str, Field(min_length=1, max_length=255)]
    title: Annotated[str, Field(min_length=1, max_length=200)]
    revision: Annotated[str, Field(min_length=1, max_length=256)]
    status: Literal["draft", "posted_future", "open", "closed"]
    draft: bool
    deleted: bool
    visible_at: str | None
    open_at: str | None
    due_at: str | None
    close_at: str | None
    max_points: Annotated[float, Field(gt=0)] | None
    grading_type: Literal[
        "none", "ungraded", "letter", "points", "pass_fail", "check", "unknown"
    ]
    submission_type: Literal[
        "none",
        "text_only",
        "attachments_only",
        "text_and_attachments",
        "non_electronic",
        "single_attachment",
        "external_tool",
        "video",
        "unknown",
    ]
    resubmission: Resubmission
    attachment_resource_refs: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=255)]], Field(max_length=20)
    ]
    release_grades: bool
    audience: Literal["site", "groups", "unknown"]
    group_submission: bool
    gradebook_link: GradebookLink
    calendar_link: CalendarLink
    native_announcement_id: str | None
    instructions_sha256: Annotated[str, Field(pattern="^[0-9a-f]{64}$")]
    timezone: str | None


class AssessmentContextCourse(Contract):
    id: Annotated[str, Field(min_length=1, max_length=255)]
    title: Annotated[str, Field(min_length=1, max_length=255)]
    timezone: str | None
    timezone_source: Literal[
        "site_policy", "user_preference", "server_default", "unknown"
    ]


class AssessmentContextCapabilities(Contract):
    create_site_assignment: bool
    revise_assignment: bool
    edit_gradebook_items: bool
    read_calendar: bool
    add_calendar_event: bool
    create_announcement: bool


class AssessmentContextSectionsAssignments(Contract):
    status: Literal["complete", "permission_scoped", "unavailable"]
    reason: str | None


class AssessmentContextSectionsGradebook(Contract):
    status: Literal["complete", "permission_scoped", "unavailable"]
    reason: str | None


class AssessmentContextSectionsCalendar(Contract):
    status: Literal["complete", "permission_scoped", "unavailable"]
    reason: str | None


class AssessmentContextSections(Contract):
    assignments: AssessmentContextSectionsAssignments
    gradebook: AssessmentContextSectionsGradebook
    calendar: AssessmentContextSectionsCalendar


class AssessmentContextGradebook(Contract):
    available: bool
    reason: str | None
    group_gradebooks_enabled: bool
    category_mode: Literal["none", "categories", "weighted_categories"] | None
    grade_entry_type: Literal["points", "percentage", "letter", "unknown"] | None
    display_released_items: bool | None
    course_grade_displayed: bool | None
    categories: Annotated[list[Category], Field(max_length=500)]
    items: Annotated[list[GradebookItem], Field(max_length=500)]


class AssessmentContextCalendar(Contract):
    scope: Literal["site_main"]
    window_start: str
    window_end: str
    events: Annotated[list[CalendarEvent], Field(max_length=500)]


class AssessmentContext(Contract):
    @model_validator(mode="after")
    def consistent_completeness(self):
        if self.complete and any(
            section.status != "complete"
            for section in [
                self.sections.assignments,
                self.sections.gradebook,
                self.sections.calendar,
            ]
        ):
            raise ValueError("Permission-scoped data cannot be complete")
        return self

    course: AssessmentContextCourse
    observed_at: str
    capabilities: AssessmentContextCapabilities
    complete: bool
    sections: AssessmentContextSections
    assignments: Annotated[list[Assignment], Field(max_length=500)]
    gradebook: AssessmentContextGradebook
    calendar: AssessmentContextCalendar
    warnings: list[Annotated[str, Field(min_length=1, max_length=1000)]]


class SetupResultFailure(Contract):
    code: Literal["PARTIAL_SUCCESS"]
    stage: Annotated[str, Field(min_length=1, max_length=100)]
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    retry_safe: bool


class SetupResult(Contract):
    outcome: Literal["complete", "partial", "unchanged"]
    course_id: Annotated[str, Field(min_length=1, max_length=255)]
    assignment: Assignment | None
    gradebook: GradebookLink
    calendar: CalendarLink
    verified_at: str | None
    remaining_steps: list[
        Literal[
            "verify_assignment",
            "link_gradebook",
            "link_calendar",
            "publish_assignment",
            "apply_gradebook_flags",
            "verify_setup",
        ]
    ]
    warnings: list[Annotated[str, Field(min_length=1, max_length=1000)]]
    assignment_id: Annotated[str, Field(min_length=1, max_length=255)]
    failure: SetupResultFailure | None


class NoGradebook(Contract):
    mode: Literal["none"]


class ExternalGradebook(Contract):
    mode: Literal["new_external"]
    category_id: str | None
    release_to_students: bool
    count_toward_course_grade: bool


GradebookConfiguration = Annotated[
    NoGradebook | ExternalGradebook, Field(discriminator="mode")
]


class GetCourseAssessmentContextRequest(Contract):
    course_id: Annotated[str, Field(min_length=1, max_length=255)]
    window_start: str | None = None
    window_end: str | None = None


class CreateAssignmentRequest(Contract):
    course_id: Annotated[str, Field(min_length=1, max_length=255)]
    title: Annotated[str, Field(min_length=1, max_length=200)]
    instructions: Annotated[str, Field(min_length=1, max_length=100000)]
    timezone: Annotated[str, Field(min_length=1, max_length=100)]
    visible_at: str | None
    open_at: str
    due_at: str
    close_at: str
    max_points: Annotated[float, Field(gt=0, strict=True)]
    submission_type: Literal[
        "text_only",
        "attachments_only",
        "text_and_attachments",
        "non_electronic",
        "single_attachment",
    ]
    resubmission: Resubmission
    publication: Literal["draft", "published"]
    attachment_resource_refs: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=255)]], Field(max_length=20)
    ]
    gradebook: GradebookConfiguration
    calendar_deadline: Literal["none", "course_calendar"]


class PublishAssignmentRequest(Contract):
    course_id: Annotated[str, Field(min_length=1, max_length=255)]
    assignment_id: Annotated[str, Field(min_length=1, max_length=255)]
    expected_assignment_revision: Annotated[str, Field(min_length=1, max_length=256)]
    gradebook: GradebookConfiguration
    calendar_deadline: Literal["none", "course_calendar"]
