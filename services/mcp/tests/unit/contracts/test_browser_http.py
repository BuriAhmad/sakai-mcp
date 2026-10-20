"""Synthetic source-derived browser shapes, not live-rendered acceptance evidence."""

import base64
import json
from decimal import Decimal

import pytest

from sakai_mcp.contracts.gradebook_ui import scores, table_data, wicket_update
from sakai_mcp.contracts.native_forms import native_form, native_url
from sakai_mcp.errors import SakaiError

ORIGIN = "https://sakai.example.test"
BASE = ORIGIN + "/portal/tool/placement-a"
FORM = b"""<html><form name="reviseForm" method="post" action="?panel=Main">
<input type="hidden" name="sakai_csrf_token" value="synthetic-csrf">
<input type="hidden" name="eventSubmit_doAnnouncement_form" value="">
<input type="hidden" name="option" value="">
<input name="subject" value="A &amp; B">
<textarea name="body">&lt;p&gt;literal&lt;/p&gt;\nsecond line</textarea>
<input name="notify" type="checkbox" value="y">
<input name="hidden" type="checkbox" value="true" checked>
<select name="audience"><option value="site" selected>Site</option><option value="group">Group</option></select>
<input name="selected" value="one"><input name="selected" value="two">
<input name="disabled" value="never" disabled>
<button type="submit" name="submit">Post</button>
</form></html>"""


def test_native_form_preserves_rendered_controls_and_literal_values():
    form = native_form(FORM, "reviseForm", ORIGIN, BASE, "placement-a")
    assert form.action == BASE + "?panel=Main"
    assert form.csrf == "synthetic-csrf"
    values = form.values({"option": "post", "subject": "New"})
    assert ("body", "<p>literal</p>\nsecond line") in values
    assert ("audience", "site") in values
    assert ("hidden", "true") in values
    assert ("selected", "one") in values and ("selected", "two") in values
    assert not any(key in {"notify", "submit", "disabled"} for key, _ in values)
    assert "synthetic-csrf" not in repr(form)
    for changes in [{"acting_user": "other"}, {"sakai_csrf_token": "forged"}]:
        with pytest.raises(SakaiError):
            form.values(changes)


@pytest.mark.parametrize(
    "candidate",
    [
        "https://[invalid/portal/tool/placement-a",
        "https://foreign.example.test/portal/tool/placement-a",
        "//foreign.example.test/portal/tool/placement-a",
        "javascript:alert(1)",
        "/portal/tool/placement-b",
        "/portal/tool/placement-a-evil",
        "/portal/tool/placement-a/../other",
        "/portal/tool/placement-a/%2e%2e/x",
        "/portal/tool/placement-a/%252f",
        "/portal/tool/placement-a/%2felsewhere",
        "/portal/tool/placement-a;jsessionid=browser",
        BASE + "?sakai.session=browser",
        "https://user:secret@sakai.example.test/portal/tool/placement-a",
        "\n" + BASE,
        "/portal/tool/placement-a#fragment",
    ],
)
def test_rendered_urls_do_not_become_an_arbitrary_proxy(candidate):
    with pytest.raises(SakaiError):
        native_url(ORIGIN, BASE, candidate, "placement-a")


@pytest.mark.parametrize(
    "data",
    [
        FORM.replace(b'name="sakai_csrf_token"', b'name="other"'),
        FORM.replace(
            b'name="sakai_csrf_token" value="synthetic-csrf"',
            b'name="sakai_csrf_token" value=""',
        ),
        FORM.replace(
            b"</form>", b'<input name="sakai_csrf_token" value="duplicate"></form>'
        ),
        FORM + FORM,
        b"<form>" + FORM + b"</form>",
        FORM.replace(b'method="post"', b'method="get"'),
        FORM.replace(
            b'<input name="subject"', b'<input type="password" name="subject"'
        ),
        FORM.replace(b"</form>", b""),
        FORM.replace(b"<select", b"<fieldset disabled><select"),
        b"<html>Login required</html>",
    ],
)
def test_missing_or_ambiguous_form_state_fails_closed(data):
    with pytest.raises(SakaiError):
        native_form(data, "reviseForm", ORIGIN, BASE, "placement-a")


def packed(values):
    return "packed:" + base64.b64encode(bytes(values)).decode()


def test_native_packed_integer_null_and_fractional_display_values():
    observed = scores(packed([0, 126, 127, 128, 127, 191, 255, 192, 8, 5]), 2, 3)
    assert [v.value for v in observed] == [
        Decimal(0),
        Decimal(126),
        None,
        Decimal(127),
        Decimal(16383),
        Decimal("8.05"),
    ]
    # Deliberately test an independent row including display rounding/carry.
    fractional = scores(packed([192, 8, 50, 192, 8, 100]), 1, 2)
    assert fractional[0].value == Decimal("8.50")
    assert fractional[1].text == "8.100"
    assert "native-fraction-carry-unverified" in fractional[1].warnings


def test_json_matrix_preserves_blank_zero_and_display_precision():
    values = scores("json:[null,0,8.501,-1]", 2, 2)
    assert [v.value for v in values] == [
        None,
        Decimal(0),
        Decimal("8.501"),
        Decimal(-1),
    ]
    assert scores("json:[]", 0, 0) == ()


@pytest.mark.parametrize(
    "value,rows,cols",
    [
        ("json:[true]", 1, 1),
        ("json:[NaN]", 1, 1),
        ("json:[]", 1, 1),
        (packed([192, 8]), 1, 1),
        (packed([192, 8, 101]), 1, 1),
        (packed([1, 2]), 1, 1),
        ("packed:???", 1, 1),
        ("unknown:[]", 0, 0),
        ("json:[]", True, 0),
        ("json:[]", 100001, 1),
    ],
)
def test_invalid_matrix_data_never_silently_shifts_students_or_columns(
    value, rows, cols
):
    with pytest.raises(SakaiError):
        scores(value, rows, cols)


def test_table_json_is_parsed_without_executing_surrounding_script():
    value = {
        "students": [{"userId": "uid-a"}],
        "columns": [{"type": "assignment", "assignmentId": 7}],
        "rowCount": 1,
        "columnCount": 1,
        "serializedGrades": "json:[8.5]",
    }
    html = (
        "<script>var tableData = "
        + json.dumps(value)
        + ';\nthrow new Error("must never execute");</script>'
    ).encode()
    assert table_data(html) == value
    with pytest.raises(SakaiError):
        table_data(html + html)
    value["rowCount"] = 2
    with pytest.raises(SakaiError):
        table_data(
            ("<script>var tableData = " + json.dumps(value) + ";</script>").encode()
        )


def test_wicket_updates_keep_component_data_and_report_unexecuted_scripts():
    observed = wicket_update(
        b'<ajax-response><component id="panel"><![CDATA[<p>synthetic</p>]]></component><evaluate><![CDATA[throw "never execute";]]></evaluate></ajax-response>',
        ORIGIN,
        BASE,
        "placement-a",
    )
    assert observed.components == (("panel", "<p>synthetic</p>"),)
    assert observed.scripts_present and observed.redirect is None
    for data in [
        b"<html>Login</html>",
        b"<ajax-response><redirect>/portal/login</redirect></ajax-response>",
        b'<ajax-response><component id="same"/><component id="same"/></ajax-response>',
    ]:
        with pytest.raises(SakaiError):
            wicket_update(data, ORIGIN, BASE, "placement-a")
