"""Source-derived unlinked native grading forms/action, never live acceptance."""

from copy import deepcopy
from urllib.parse import parse_qs

import httpx

from tests.fixtures.five_tool_http import FiveToolHTTP
from tests.fixtures.setup_http import DATE_DEFAULTS, DEFAULT, SetupHTTP


class GradingHTTP(SetupHTTP):
    def __init__(self):
        super().__init__()
        self.models["assignment-a"] = {
            **DEFAULT,
            **DATE_DEFAULTS,
            "draft": False,
            "new_assignment_title": "Synthetic Quiz",
            "new_assignment_grade_assignment": "true",
        }
        self.assignment["submissions"][0].update(properties={}, feedbackText=None)
        self.grade_posts = []
        self.grade_failure = None

    def listing(self):
        return (
            super().listing()
            + '<a href="/portal/tool/assignments-p?eventSubmit_doGrade_assignment=&amp;assignmentId=%2Fassignment%2Fa%2Fcourse-a%2Fassignment-a">Grade</a>'
        )

    def __call__(self, req):
        if req.url.path == "/direct/assignment/setGrade.json":
            self.calls.append(req)
            self.grade_posts.append(req)
            assert req.method == "POST" and "cookie" not in req.headers
            values = {
                k: v[0]
                for k, v in parse_qs(
                    req.content.decode(), keep_blank_values=True
                ).items()
            }
            assert values["courseId"] == values["siteId"] == "course-a"
            assert (
                values["gradableId"] == "assignment-a"
                and values["submissionId"] == "submission-a"
            )
            assert values["studentId"] == "student-a"
            if self.grade_failure == "503":
                return httpx.Response(503)
            row = self.assignment["submissions"][0]
            row.update(grade=values["grade"], graded=True)
            if values["gradeOption"] == "return":
                row.update(returned=True, gradeReleased=True)
            for form, key in [
                ("privateNotes", "privateNotes"),
                ("feedbackText", "feedbackText"),
                ("feedbackComment", "feedbackComment"),
            ]:
                row[key] = values.get(form, "").strip() or None
            for form, key in [
                ("resubmitNumber", "allow_resubmit_number"),
                ("resubmitDate", "allow_resubmit_closeTime"),
                ("extensionDate", "allow_extension_closeTime"),
            ]:
                if form in values:
                    row["properties"][key] = values[form]
                else:
                    row["properties"].pop(key, None)
            row["properties"]["last_graded_date"] = "Synthetic observed date"
            if self.grade_failure == "side-field":
                row["privateNotes"] = "Changed"
            if self.grade_failure == "lost":
                raise httpx.ReadTimeout("Synthetic lost reply")
            if self.grade_failure == "malformed":
                return httpx.Response(200, json={})
            return httpx.Response(
                200,
                json={
                    "submission": deepcopy(row),
                    "assignmentCloseTime": self.assignment["closeTimeString"],
                },
            )
        if (
            req.url.path == "/portal/tool/assignments-p"
            and "eventSubmit_doGrade_assignment" in req.url.params
        ):
            return FiveToolHTTP.__call__(self, req)
        assert "/api/mcp/v1/" not in req.url.path
        return super().__call__(req)
