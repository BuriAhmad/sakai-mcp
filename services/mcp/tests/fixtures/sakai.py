from mcp.server.auth.provider import AccessToken

from sakai_mcp.errors import ErrorCode, SakaiError
from sakai_mcp.security.obo import DownstreamToken


class FakeClient:
    def __init__(self):
        self.courses = self.announcements = self.assignments = self.grading = self

    writes = 0
    deny_privileged = False

    async def list_my_courses(self, _):
        return [{"id": "course-a", "title": "Field Methods"}]

    async def get_my_grades(self, _, course_id):
        assert course_id == "course-a"
        return [{"itemId": 10, "title": "Lab 1", "score": "18", "pointsPossible": 20.0}]

    async def get_course_announcements(self, _, course_id):
        assert course_id == "course-a"
        return [
            {
                "id": "one",
                "title": "Orientation",
                "body": "Welcome",
                "postedAt": 1_780_000_000_000,
            },
            {
                "id": "two",
                "title": "Week 2",
                "body": "Read chapter 2",
                "postedAt": 1_780_000_100_000,
            },
        ]

    async def get_course_submissions(self, _, course_id, assignment_id):
        if self.deny_privileged:
            raise SakaiError(ErrorCode.FORBIDDEN)
        assert course_id == "course-a" and assignment_id == "assignment-a"
        return [
            {
                "id": "submission-a",
                "submitterIds": ["student-a"],
                "submittedAt": 1_780_000_000.5,
            }
        ]

    async def create_course_announcement(self, _, course_id, title, body):
        if self.deny_privileged:
            raise SakaiError(ErrorCode.FORBIDDEN)
        self.writes += 1
        assert (
            course_id == "course-a"
            and title == "Lab update"
            and body == "Bring notebooks."
        )
        return {
            "id": "new",
            "courseId": course_id,
            "title": title,
            "postedAt": 1_780_000_000_000,
        }


class FakeOBO:
    calls = 0

    async def acquire(self, _: AccessToken) -> DownstreamToken:
        self.calls += 1
        return DownstreamToken(
            "synthetic-token", "tenant", "person", "synthetic-eid", 2_000_000_000
        )


def principal():
    return AccessToken(token="upstream", client_id="test-client", scopes=["mcp.access"])
