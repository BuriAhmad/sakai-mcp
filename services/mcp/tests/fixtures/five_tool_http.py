"""Synthetic source-derived Sakai 25.2 wire views; no exercised/live claim."""

from copy import deepcopy
from datetime import UTC, datetime
from html import escape
from urllib.parse import parse_qs

import httpx

from sakai_mcp.sakai.client import SakaiClient
from sakai_mcp.storage.memory import MemoryObjectStore
from sakai_mcp.storage.records import PrivateRecords
from tests.fixtures.authentication import settings
from tests.fixtures.sakai import FakeOBO

SUBMISSION = {
    "id": "submission-a",
    "gradableId": "assignment-a",
    "submitted": True,
    "userSubmission": True,
    "graded": False,
    "returned": False,
    "draft": False,
    "submitters": [
        {
            "id": "student-a",
            "displayId": "student-eid",
            "displayName": "Synthetic Student",
        }
    ],
    "submittedText": "<p>A,B</p>\r\n",
    "submittedAttachments": [],
    "dateSubmittedEpochSeconds": 1790000000,
    "late": False,
    "grade": "",
    "feedbackComment": None,
    "privateNotes": "DO NOT EXPOSE PRIVATE NOTES",
}
ASSIGNMENT = {
    "id": "assignment-a",
    "context": "course-a",
    "title": "Synthetic Quiz",
    "draft": False,
    "gradeScale": "SCORE_GRADE_TYPE",
    "gradeScaleMaxPoints": "10.0",
    "submissionType": "TEXT_ONLY_ASSIGNMENT_SUBMISSION",
    "anonymousGrading": False,
    "allowPeerAssessment": False,
    "openTimeString": "2026-10-01T00:00:00Z",
    "dueTimeString": "2026-10-20T00:00:00Z",
    "closeTimeString": "2026-10-21T00:00:00Z",
    "submissions": [SUBMISSION],
}


def page(data):
    return httpx.Response(
        200, text=data, headers={"content-type": "text/html; charset=utf-8"}
    )


class FiveToolHTTP:
    def __init__(self):
        self.calls = []
        self.posts = 0
        self.functions = ["asn.grade", "annc.new", "gradebook.viewOwnGrades"]
        self.assignment = deepcopy(ASSIGNMENT)
        self.grade_items = [
            {"id": 7, "name": "Synthetic Quiz", "released": True, "points": 10.0}
        ]
        self.grade_html = """<div id="studentGradeSummary"><table id="gradeSummaryTable"><tr class="gb-summary-grade-row">
        <th><span class="gb-summary-grade-title">Synthetic Quiz</span></th>
        <td class="gb-summary-grade-score"><span class="gb-summary-grade-score-raw">8.5</span><span class="gb-summary-grade-score-outof">/ 10.0</span></td></tr></table></div>"""
        self.announcements = []
        self.failure = None
        self.native_eid = "synthetic-eid"
        self.expected_token = "synthetic-token"

    def __call__(self, request):
        self.calls.append(request)
        assert request.url.host == "sakai.example.test"
        assert "cookie" not in request.headers
        assert "/api/mcp/v1/" not in request.url.path
        assert request.headers["authorization"] == "Bearer " + self.expected_token
        path = request.url.path
        if request.headers.get("x-mcp-flow-end"):
            return httpx.Response(200, json={"id": "uid", "eid": self.native_eid})
        if path == "/direct/user/current.json":
            return httpx.Response(200, json={"id": "uid", "eid": self.native_eid})
        if path == "/direct/site/course-a.json":
            return httpx.Response(
                200,
                json={
                    "id": "course-a",
                    "type": "course",
                    "pubView": False,
                    "published": True,
                },
            )
        if path == "/direct/site/course-a/userPerms.json":
            return httpx.Response(200, json=self.functions)
        if path == "/direct/site/course-a/pages.json":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": "page-a",
                        "siteId": "course-a",
                        "url": "https://sakai.example.test/portal/site/course-a/page/page-a",
                        "tools": [
                            {
                                "id": p,
                                "placementId": p,
                                "toolId": t,
                                "context": "course-a",
                                "pageId": "page-a",
                                "siteId": "course-a",
                                "url": "https://sakai.example.test/portal/site/course-a/page/page-a",
                            }
                            for p, t in [
                                ("gradebook-p", "sakai.gradebookng"),
                                ("announcements-p", "sakai.announcements"),
                                ("assignments-p", "sakai.assignment.grades"),
                            ]
                        ],
                    }
                ],
            )
        if path == "/direct/assignment/item/assignment-a.json":
            return httpx.Response(200, json=self.assignment)
        if path == "/portal/tool/assignments-p":
            if "eventSubmit_doGrade_assignment" in request.url.params:
                uid = (
                    "blank"
                    if self.assignment.get("anonymousGrading")
                    or any(
                        r.get("groupId") for r in self.assignment.get("submissions", [])
                    )
                    else "student-a"
                )
                return page(
                    '<table id="submissionList"><tr><td headers="studentname"><sakai-user-photo user-id="'
                    + uid
                    + '"></sakai-user-photo></td></tr></table>'
                )
            return page(
                '<td headers="title"><a href="javascript:void(0)" onclick="window.location=\'/portal/tool/assignments-p?eventSubmit_doGrade_assignment=&amp;assignmentId=%2Fassignment%2Fa%2Fcourse-a%2Fassignment-a\';">Grade</a></td>'
            )
        if path == "/direct/assignment/site/course-a.json":
            return httpx.Response(200, json=[self.assignment])
        if path == "/api/sites/course-a/grading/item-data":
            return httpx.Response(
                200, json={"items": self.grade_items, "categories": []}
            )
        if path == "/api/sites/course-a/grades":
            assert not set(self.functions) & {
                "asn.grade",
                "gradebook.gradeAll",
                "assessment.gradeAssessment.any",
            }, "Aggregate endpoint called for grader"
            return httpx.Response(
                200,
                json={
                    "grades": [
                        {
                            "id": 7,
                            "name": "Synthetic Quiz",
                            "siteId": "course-a",
                            "score": "8.5",
                            "notGradedYet": False,
                            "canGrade": False,
                            "ungraded": 0,
                        }
                    ]
                },
            )
        if path == "/portal/tool/gradebook-p/gradebook":
            return page(self.grade_html)
        if path == "/direct/announcement/site/course-a.json":
            return httpx.Response(200, json=self.announcements)
        if path == "/portal/tool/announcements-p":
            if request.method == "POST":
                self.posts += 1
                fields = parse_qs(request.content.decode(), keep_blank_values=True)
                assert fields["option"] == ["post"] and fields["notify"] == ["o"]
                assert fields["announceTo"] == ["site"] and fields["hidden"] == [
                    "false"
                ]
                assert fields["sakai_csrf_token"] == ["synthetic-csrf"]
                assert not any(
                    k in fields
                    for k in [
                        "selectedRoles",
                        "selectedGroups",
                        "use_start_date",
                        "use_end_date",
                    ]
                )
                from html import unescape

                self.announcements.append(
                    {
                        "announcementId": "created-once",
                        "siteId": "course-a",
                        "channel": "main",
                        "title": unescape(fields["subject"][0]),
                        "body": fields["body"][0],
                        "createdOn": int(datetime.now(UTC).timestamp() * 1000),
                    }
                )
                if self.failure == "timeout":
                    raise httpx.ReadTimeout("synthetic lost response", request=request)
                if self.failure == "500":
                    return httpx.Response(500)
                if self.failure == "validation":
                    return page(
                        '<div class="sak-banner-error">Synthetic validation</div>'
                    )
                if self.failure == "bad-html":
                    return page("<html>Unrecognized response</html>")
            elif "eventSubmit_doNewannouncement" in request.url.params:
                return page("""<form name="reviseForm" method="post" action="/portal/tool/announcements-p">
                <input name="eventSubmit_doAnnouncement_form" type="hidden" value=""><input name="option" type="hidden" value="">
                <input name="subject" value=""><textarea name="body"></textarea><input name="announceTo" value="site" type="radio" checked>
                <input name="hidden" value="false" type="radio" checked><select name="notify"><option value="o" selected>Optional</option><option value="n">None</option></select>
                <input name="selectedGroups" value="stale" type="checkbox" checked><input name="use_start_date" value="true" type="checkbox" checked>
                <input type="hidden" name="sakai_csrf_token" value="synthetic-csrf"></form>""")
            links = '<a href="/portal/tool/announcements-p?eventSubmit_doNewannouncement=">Add</a>'
            for row in self.announcements:
                links += f'<td headers="subject"><a href="/portal/tool/announcements-p?eventSubmit_doShowmetadata=&amp;itemReference=%2Fannouncement%2Fmsg%2Fcourse-a%2Fmain%2F{row["announcementId"]}">{escape(row["title"])}</a></td>'
            return page(links)
        return httpx.Response(404)

    def client(self, *, with_store=True, **changes):
        records = PrivateRecords(MemoryObjectStore()) if with_store else None
        client = SakaiClient(
            settings(assignment_grading_enabled=True, **changes),
            FakeOBO(),
            httpx.AsyncClient(transport=httpx.MockTransport(self)),
            private_records=records,
        )
        return client
