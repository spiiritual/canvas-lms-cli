import json as json_module
from datetime import datetime, timedelta, timezone

import typer
from rich.console import Console
from rich.table import Table

from . import canvas_api
from .classes import format_date_relative, format_datetime, get_assignment_status

app = typer.Typer(help="Commands related to assignments in Canvas.")


@app.command(name="upcoming")
def upcoming(days: int = 7, json: bool = False):
    """
    Prints assignments and other to-dos due in the next N days across all classes. Use --json to print raw JSON data.

    Example usage: canvas-lms-cli assignments upcoming --days 14
    """

    now = datetime.now(timezone.utc)
    items = canvas_api.make_paginated_request(
        "planner/items",
        params={
            "per_page": 100,
            "start_date": now.isoformat(),
            "end_date": (now + timedelta(days=days)).isoformat(),
        },
    )

    if json:
        print(json_module.dumps(items, indent=2))
        return

    table = Table(title=f"Due in the next {days} days")
    table.add_column("", no_wrap=True)
    table.add_column("Due", style="yellow", no_wrap=True)
    table.add_column("Class", style="cyan")
    table.add_column("Title", style="white")
    table.add_column("Type", style="dim")
    table.add_column("Points", style="dim", justify="right")

    for item in items:
        plannable = item.get("plannable", {})
        due_at = plannable.get("due_at") or item.get("plannable_date")
        submissions = item.get("submissions") or {}

        if submissions.get("graded") or submissions.get("submitted"):
            status = "[green]✓[/green]"
        elif submissions.get("missing"):
            status = "[red]✗[/red]"
        else:
            status = "○"

        points = plannable.get("points_possible")
        table.add_row(
            status,
            f"{format_datetime(due_at)} ({format_date_relative(due_at)})",
            item.get("context_name", "—"),
            plannable.get("title") or plannable.get("name", "Untitled"),
            item.get("plannable_type", "—").replace("_", " "),
            "—" if points is None else f"{points:g}",
        )

    Console().print(table)


@app.command(name="list")
def list_assignments(course_id: str, json: bool = False):
    """
    Prints every assignment in a class with its due date, points, and your submission status. Use --json to print raw JSON data.

    Example usage: canvas-lms-cli assignments list <COURSE_ID>
    """

    assignments = canvas_api.make_paginated_request(
        f"courses/{course_id}/assignments",
        params={
            "per_page": 100,
            "include[]": ["submission"],
            "order_by": "due_at",
        },
    )

    if json:
        print(json_module.dumps(assignments, indent=2))
        return

    table = Table(title="Assignments")
    table.add_column("", no_wrap=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Due", style="yellow", no_wrap=True)
    table.add_column("Score", justify="right")

    for assignment in assignments:
        icon, color = get_assignment_status(assignment)
        submission = assignment.get("submission") or {}
        score = submission.get("score")
        points = assignment.get("points_possible")
        score_str = (
            f"{round(score, 2):g}/{points:g}" if score is not None and points is not None
            else ("—" if points is None else f"—/{points:g}")
        )

        table.add_row(
            f"[{color}]{icon}[/{color}]",
            assignment.get("id", "—"),
            assignment.get("name", "Untitled"),
            format_datetime(assignment.get("due_at")),
            score_str,
        )

    Console().print(table)
