"""Synthetic source-derived Assignment list/form/date-picker views, never live."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from urllib.parse import parse_qs, quote

import httpx

from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.storage.memory import MemoryObjectStore
from sakai_mcp.storage.records import PrivateRecords
from tests.fixtures.authentication import settings
from tests.fixtures.five_tool_http import FiveToolHTTP, gradebook_table, page
from tests.fixtures.sakai import FakeOBO

DEFAULT = {
    "new_assignment_title": "",
    "new_assignment_instructions": "",
    "new_assignment_grade_type": "3",
    "new_assignment_grade_points": "10.0",
    "new_assignment_submission_type": "1",
    "assignTo": "individuals",
    "allow_resubmit_number": "1",
    "new_assignment_category": "-1",
    "new_assignment_add_to_gradebook": "add",
}
DATE_DEFAULTS = {
    p: "2026-10-26T09:00"
    for p in (
        "new_assignment_open_",
        "new_assignment_due_",
        "new_assignment_close_",
        "new_assignment_visible_",
        "allow_resubmit_close_",
    )
}


class SetupHTTP(FiveToolHTTP):
    def __init__(self):
        super().__init__()
        self.functions += [
            "asn.new",
            "asn.revise",
            "gradebook.editAssignments",
            "gradebook.gradeAll",
            "section.role.instructor",
            "calendar.read",
            "calendar.new",
        ]
        self.categories = False
        self.zone = "Asia/Karachi"
        self.locale = "en-US"
        self.native_uid = "uid"
        self.models = {}
        self.new_defaults = {}
        self.failed = None
        self.csrf = "synthetic-setup-csrf"
        self.gradebook_data = gradebook_table()
        self.gradebook_data["columns"][1].update(
            title="Synthetic Quiz", extraCredit=False
        )
        self.form_extras = ""
        self.readback_zone = None
        self.edits = {}

    def head(self):
        return (
            "<script>var portal = "
            + json.dumps(
                {
                    "siteId": "course-a",
                    "locale": self.locale,
                    "user": {
                        "id": self.native_uid,
                        "eid": self.native_eid,
                        "timezone": self.readback_zone
                        if self.posts and self.readback_zone
                        else self.zone,
                    },
                }
            )
            + ";</script>"
        )

    def listing(self):
        text = (
            self.head()
            + '<a href="/portal/tool/assignments-p?eventSubmit_doNew_assignment=">Add</a><table>'
        )
        for sid, model in self.models.items():
            ref = quote("/assignment/a/course-a/" + sid, safe="")
            action = "Edit" if model["draft"] else "View"
            title = escape(model["new_assignment_title"], quote=True)
            text += f'<tr><td headers="title"><strong><a name="asnActionLink" title="{title}" href="/portal/tool/assignments-p?eventSubmit_do{action}_assignment=&amp;assignmentId={ref}">'
            if model["draft"]:
                text += '<span class="highlight">Draft</span>'
            text += title + '</a></strong><div class="itemAction">'
            text += f'<a name="asnActionLink" href="/portal/tool/assignments-p?eventSubmit_doEdit_assignment=&amp;assignmentId={ref}">Edit</a></div></td></tr>'
        return text + '</table><input name="eventSubmit_doList_next" disabled>'

    def form(self, identifier=None):
        model = self.models.get(
            identifier, {**DEFAULT, **DATE_DEFAULTS, **self.new_defaults}
        )
        ref = "/assignment/a/course-a/" + identifier if identifier else ""
        text = (
            self.head()
            + '<form name="newAssignmentForm" id="newAssignmentForm" method="post" action="/portal/tool/assignments-p">'
        )
        for key, value in {
            "assignmentId": ref,
            "eventSubmit_doAssignment_form": "",
            "option": "",
            "view": "",
            "sakai_csrf_token": self.csrf,
        }.items():
            text += f'<input type="hidden" name="{key}" value="{escape(value, quote=True)}">'
        for key in ("new_assignment_title", "new_assignment_grade_points"):
            text += f'<input name="{key}" value="{escape(model[key], quote=True)}">'
        text += (
            '<textarea name="new_assignment_instructions">'
            + escape(model["new_assignment_instructions"])
            + "</textarea>"
        )
        for key, values in {
            "new_assignment_grade_type": ["3", "2", "4", "5"],
            "new_assignment_submission_type": ["1", "2", "3", "4", "5", "6"],
            "allow_resubmit_number": [*[str(i) for i in range(1, 11)], "-1"],
            "new_assignment_category": ["-1", "5"],
        }.items():
            if key == "new_assignment_category" and not self.categories:
                continue
            text += f'<select name="{key}">'
            for value in values:
                text += (
                    f'<option value="{value}"'
                    + (" selected" if model[key] == value else "")
                    + f">{value}</option>"
                )
            text += "</select>"
        for key, value in {
            "new_assignment_grade_assignment": "true",
            "allowResToggle": "on",
            "allowVisibleDateToggle": "on",
            "new_assignment_send_to_gradebook": "true",
            "new_assignment_use_peer_assessment": "true",
            "new_assignment_use_review_service": "true",
            "new_assignment_check_anonymous_grading": "true",
            "new_assignment_check_add_due_date": "true",
            "new_assignment_check_auto_announce": "true",
        }.items():
            text += (
                f'<input type="checkbox" name="{key}" value="{value}"'
                + (" checked" if model.get(key) else "")
                + ">"
            )
        text += '<input type="radio" name="assignTo" id="site" value="individuals" checked><input type="radio" name="assignTo" value="individualsFromGroups"><select name="selectedGroups" multiple><option value="group-a">Group</option></select>'
        text += '<div id="assignmentGradingGradebookOptionsPanel"><input type="radio" name="new_assignment_add_to_gradebook" id="create-gradebook-item" value="add" checked></div>'
        for prefix in DATE_DEFAULTS:
            text += f'<sakai-date-picker hidden-prefix="{prefix}" iso-date="{model[prefix]}" add-hidden-fields></sakai-date-picker>'
        return (
            text
            + self.form_extras
            + "<sakai-rubric-association></sakai-rubric-association></form>"
        )

    def __call__(self, req):
        if req.url.path == "/api/sites/course-a/grading/item-data":
            self.calls.append(req)
            items = {
                "/assignment/a/course-a/assignment-a": {
                    "id": 7,
                    "context": "course-a",
                    "name": "Synthetic Quiz",
                    "points": 10.0,
                    "released": True,
                    "counted": True,
                    "extraCredit": False,
                    "externallyMaintained": True,
                    "externalId": "/assignment/a/course-a/assignment-a",
                    "externalAppName": "sakai.assignment.grades",
                    "reference": "/assignment/a/course-a/assignment-a",
                    "categoryId": 5 if self.categories else None,
                }
            }
            for identifier, model in self.models.items():
                if model.get("new_assignment_send_to_gradebook"):
                    ref = "/assignment/a/course-a/" + identifier
                    items[ref] = {
                        "id": items.get(ref, {}).get("id", 20 + len(items)),
                        "context": "course-a",
                        "name": model["new_assignment_title"],
                        "points": float(model["new_assignment_grade_points"]),
                        "released": True,
                        "counted": True,
                        "extraCredit": False,
                        "externallyMaintained": True,
                        "externalId": ref,
                        "externalAppName": "sakai.assignment.grades",
                        "reference": ref,
                        "categoryId": int(model["new_assignment_category"])
                        if model["new_assignment_category"] != "-1"
                        else None,
                    }
            return httpx.Response(
                200,
                json={
                    "items": list(items.values()),
                    "categories": [
                        {
                            "id": 5,
                            "name": "Assignments",
                            "weight": 0.3,
                            "equalWeight": False,
                            "dropLowest": 1,
                            "dropHighest": 0,
                            "keepHighest": 0,
                            "extraCredit": False,
                            "dropKeepEnabled": True,
                        }
                    ]
                    if self.categories
                    else [],
                },
            )
        if req.url.path != "/portal/tool/assignments-p":
            response = super().__call__(req)
            if req.url.path == "/direct/site/course-a.json":
                return httpx.Response(
                    200, json={**response.json(), "title": "Synthetic Course"}
                )
            return response
        self.calls.append(req)
        assert (
            "cookie" not in req.headers
            and req.headers["authorization"] == "Bearer " + self.expected_token
        )
        assert not any(r.url.path.startswith("/api/mcp/v1/") for r in self.calls)
        if req.method == "GET":
            if "eventSubmit_doNew_assignment" in req.url.params:
                self.edits[req.headers["x-mcp-flow"]] = ""
                return page(self.form())
            if "eventSubmit_doEdit_assignment" in req.url.params:
                ref = req.url.params["assignmentId"]
                assert ref.startswith("/assignment/a/course-a/")
                identifier = ref.rsplit("/", 1)[1]
                self.edits[req.headers["x-mcp-flow"]] = identifier
                return page(self.form(identifier))
            return page(self.listing())
        self.posts += 1
        fields = parse_qs(req.content.decode(), keep_blank_values=True)
        assert fields["sakai_csrf_token"] == [self.csrf]
        assert fields["option"] in [["save"], ["post"]]
        assert fields["eventSubmit_doAssignment_form"] == [""]
        editing = self.edits[req.headers["x-mcp-flow"]]
        assert fields["assignmentId"] == [
            "/assignment/a/course-a/" + editing if editing else ""
        ]
        if self.failed == "403":
            return httpx.Response(403)
        if self.failed == "validation":
            return page('<div class="sak-banner-error">Validation</div>')
        identifier = editing or "created-" + str(self.posts)
        model = {k: fields[k][0] if k in fields else v for k, v in DEFAULT.items()}
        for key in (
            "new_assignment_grade_assignment",
            "allowResToggle",
            "allowVisibleDateToggle",
            "new_assignment_send_to_gradebook",
        ):
            model[key] = key in fields
        for prefix in DATE_DEFAULTS:
            values = [
                int(fields[prefix + part][0])
                for part in ("year", "month", "day", "hour", "min")
            ]
            model[prefix] = (
                datetime(*values, tzinfo=UTC)
                .replace(tzinfo=None)
                .isoformat(timespec="minutes")
            )
        model["draft"] = fields["option"] == ["save"]
        self.models[identifier] = model
        if model["new_assignment_send_to_gradebook"]:
            self.gradebook_data["columns"][1].update(
                externalId="/assignment/a/course-a/" + identifier,
                categoryId=None
                if model["new_assignment_category"] == "-1"
                else model["new_assignment_category"],
                released=True,
                includedInCourseGrade=not self.categories
                or model["new_assignment_category"] != "-1",
            )
        if self.failed == "timeout":
            raise httpx.ReadTimeout("synthetic lost setup reply", request=req)
        if self.failed == "500":
            return httpx.Response(500)
        if self.failed == "unknown":
            return page("<html>Unknown state</html>")
        if self.failed == "readback":
            model["new_assignment_instructions"] = "Native normalized differently"
        return page(self.listing())

    def client(self, *, with_store=True, enabled=True):
        return SakaiClient(
            settings(assignment_setup_enabled=enabled, assignment_grading_enabled=True),
            FakeOBO(),
            httpx.AsyncClient(transport=httpx.MockTransport(self)),
            private_records=PrivateRecords(MemoryObjectStore()) if with_store else None,
        )

    def seed(self, *, draft=True, **values):
        self.models["assignment-a"] = {
            **deepcopy(DEFAULT),
            **DATE_DEFAULTS,
            "new_assignment_title": "Existing assignment",
            "new_assignment_instructions": "Existing literal instructions",
            "draft": draft,
            "new_assignment_grade_assignment": True,
            **values,
        }
