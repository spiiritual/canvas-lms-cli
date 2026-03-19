import typer
from rich.console import Console
from rich.table import Table
from datetime import datetime
from . import canvas_api

app = typer.Typer()


@app.command(name="list")
def list_classes(json: bool = False):
    courses = canvas_api.make_request(
        "courses",
        params={
            "per_page": 100,
            "enrollment_state": "active",
            "include[]": ["total_scores", "term"],
        },
    )

    if json:
        import json as json_module

        print(json_module.dumps(courses, indent=2))
        return

    console = Console()
    table = Table(title="Your Classes")

    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Name", style="white")
    table.add_column("Score", style="green", justify="right")
    table.add_column("Grade", style="yellow", justify="center")
    table.add_column("Start", style="dim")
    table.add_column("End", style="dim")

    for course in courses:
        course_id = course.get("id", "N/A")
        name = course.get("name", "Unknown")

        enrollments = course.get("enrollments", [])
        score = None
        grade = None
        for enrollment in enrollments:
            if enrollment.get("type") == "student":
                score = enrollment.get("computed_current_score")
                grade = enrollment.get("computed_current_grade")
                break

        score_str = f"{score:.1f}%" if score is not None else "—"
        grade_str = grade if grade else "—"

        start_at = course.get("start_at")
        end_at = course.get("end_at")

        start_str = format_date(start_at)
        end_str = format_date(end_at)

        table.add_row(course_id, name, score_str, grade_str, start_str, end_str)

    console.print(table)


def format_date(iso_date: str) -> str:
    if not iso_date:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except:
        return "—"
