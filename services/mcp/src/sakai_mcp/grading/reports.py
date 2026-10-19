"""Deterministic grading reports."""

import csv
import io
from typing import Any


def report_csv(rows: list[dict[str, Any]]) -> str:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    fields = [
        "submission_id",
        "sakai_user_id",
        "score",
        "max_score",
        "review_status",
        "issues",
    ]
    writer.writerow(fields)
    for row in rows:
        values = [row[k] for k in fields[:-1]] + [";".join(row["issues"])]
        writer.writerow(
            [
                "'" + v
                if isinstance(v, str) and v.startswith(("=", "+", "-", "@"))
                else v
                for v in values
            ]
        )
    return output.getvalue()
