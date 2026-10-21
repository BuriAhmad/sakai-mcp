"""Synthetic existing raw-model codec fields plus the established native views."""

from copy import deepcopy

import httpx

from tests.fixtures.grading_http import GradingHTTP


class ContextHTTP(GradingHTTP):
    def __init__(self):
        super().__init__()
        self.assignment.update(access="SITE", groups=[])
        self.raw = {
            "id": "assignment-a",
            "context": "course-a",
            "title": "Synthetic Quiz",
            "instructions": "Synthetic instructions",
            "scaleFactor": 100,
            "maxGradePoint": 1000,
            "releaseGrades": False,
            "deleted": False,
            "draft": False,
            "isGroup": False,
            "allowPeerAssessment": False,
            "contentReview": False,
            "groups": [],
            "attachments": [],
            "visibleDate": None,
            "openDate": {"epochSecond": 1790812800, "nano": 123456789},
            "dueDate": None,
            "closeDate": None,
            "properties": {},
            "submissions": [{"privateNotes": "SYNTHETIC PRIVATE RAW OVERFETCH"}],
        }
        self.raw_status = 200

    def __call__(self, request):
        if request.url.path == "/direct/assignment/annc/course-a/assignment-a.json":
            self.calls.append(request)
            assert not request.url.query and request.method == "GET"
            return httpx.Response(
                self.raw_status,
                json={
                    "assignment": deepcopy(self.raw),
                    "context": "course-a",
                    "assignmentId": "assignment-a",
                },
            )
        result = super().__call__(request)
        if request.url.path == "/direct/site/course-a.json":
            value = result.json()
            value["title"] = "Synthetic course"
            return httpx.Response(200, json=value)
        return result
