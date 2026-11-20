import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from datetime import datetime, timedelta, timezone
from . import canvas_api

app = typer.Typer(help="Commands related to courses/classes in Canvas.")


@app.command(name="list")
def list_classes(json: bool = False):
    """
    Prints a list of active classes and their ids, names, current scores, and current grades. Use --json to print raw JSON data.

    Example usage: canvas-lms-cli classes list
    """

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
    table.add_column("Start", style="dim")
    table.add_column("End", style="dim")

    for course in courses:
        course_id = course.get("id", "N/A")
        name = course.get("name", "Unknown")

        start_at = course.get("start_at")
        end_at = course.get("end_at")

        start_str = format_date(start_at)
        end_str = format_date(end_at)

        table.add_row(course_id, name, start_str, end_str)

    console.print(table)


def format_date(iso_date: str) -> str:
    if not iso_date:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except:
        return "—"


def format_datetime(iso_date: str) -> str:
    if not iso_date:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%b %d, %I:%M %p")
    except:
        return "—"


def format_date_relative(iso_date: str) -> str:
    if not iso_date:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = dt - now

        if diff.total_seconds() < 0:
            return "Past due"
        elif diff.days == 0:
            hours = int(diff.total_seconds() / 3600)
            if hours == 0:
                minutes = int(diff.total_seconds() / 60)
                return f"In {minutes}m"
            return f"In {hours}h"
        elif diff.days == 1:
            return "Tomorrow"
        elif diff.days < 7:
            return f"In {diff.days} days"
        else:
            return dt.strftime("%b %d")
    except:
        return "—"


def get_assignment_status(assignment: dict) -> tuple[str, str]:
    submission = assignment.get("submission", {})
    if isinstance(submission, list):
        submission = submission[0] if submission else {}
    due_at = assignment.get("due_at")
    workflow_state = (
        submission.get("workflow_state", "") if isinstance(submission, dict) else ""
    )

    if workflow_state in ("graded", "submitted"):
        return ("✓", "green")
    if submission.get("missing") if isinstance(submission, dict) else False:
        return ("✗", "red")
    if due_at:
        due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if (
            due_dt < datetime.now(timezone.utc) and not submission.get("submitted_at")
            if isinstance(submission, dict)
            else True
        ):
            return ("✗", "red")
        if (due_dt - datetime.now(timezone.utc)).days <= 2:
            return ("!", "yellow")
    return ("○", "default")


def fetch_course_dashboard(course_id: str) -> dict:
    user = canvas_api.make_request("users/self")

    course = canvas_api.make_request(
        f"courses/{course_id}",
        params={
            "include[]": [
                "total_scores",
                "term",
                "syllabus_body",
                "settings",
                "banner_image",
            ],
        },
    )

    enrollments = canvas_api.make_request(
        f"courses/{course_id}/enrollments",
        params={
            "user_id": user["id"],
            "per_page": 100,
            "state[]": ["active", "completed"],
            "type[]": ["StudentEnrollment", "StudentViewEnrollment"],
        },
    )

    assignment_groups = canvas_api.make_request(
        f"courses/{course_id}/assignment_groups",
        params={
            "include[]": [
                "assignments",
                "submission",
                "score_statistics",
                "checkpoints",
            ],
            "per_page": 100,
            "scope_assignments_to_student": "true",
        },
    )

    announcements = canvas_api.make_request(
        f"courses/{course_id}/discussion_topics",
        params={
            "per_page": 100,
            "only_announcements": "true",
            "include[]": ["sections"],
        },
    )

    course_users = canvas_api.make_request(
        f"courses/{course_id}/users",
        params={
            "per_page": 100,
            "include[]": ["enrollments", "avatar_url"],
            "exclude_inactive": "true",
        },
    )

    now = datetime.now(timezone.utc)
    week_later = now + timedelta(days=7)

    planner = canvas_api.make_request(
        "planner/items",
        params={
            "per_page": 100,
            "start_date": now.isoformat(),
            "end_date": week_later.isoformat(),
            "context_codes[]": f"course_{course_id}",
        },
    )

    activity = canvas_api.make_request(
        "users/self/activity_stream",
        params={"only_active_courses": "true"},
    )

    student_enrollment = None
    for enroll in enrollments:
        if (
            enroll.get("user_id") == user["id"]
            and enroll.get("type") == "StudentEnrollment"
        ):
            student_enrollment = enroll
            break

    instructors = []
    for u in course_users:
        for enroll in u.get("enrollments", []):
            role = enroll.get("role", "")
            if "Teacher" in role or "TaEnrollment" in role:
                instructors.append(u)
                break

    all_assignments = []
    for group in assignment_groups:
        for assignment in group.get("assignments", []):
            assignment["_group_name"] = group.get("name", "")
            assignment["_group_weight"] = group.get("weight", 0)
            all_assignments.append(assignment)

    upcoming_assignments = []
    for assign in all_assignments:
        due_at = assign.get("due_at")
        if due_at:
            due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
            if now <= due_dt <= week_later:
                upcoming_assignments.append(assign)

    upcoming_assignments.sort(key=lambda x: x.get("due_at", ""))

    recent_announcements = []
    week_ago = now - timedelta(days=7)
    for ann in announcements:
        posted_at = ann.get("posted_at")
        if posted_at:
            posted_dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            if posted_dt >= week_ago:
                recent_announcements.append(ann)

    recent_announcements.sort(key=lambda x: x.get("posted_at", ""), reverse=True)

    recent_grades = []
    for assign in all_assignments:
        submission = assign.get("submission", {})
        if isinstance(submission, list):
            submission = submission[0] if submission else None
        if submission and isinstance(submission, dict):
            posted_at = submission.get("posted_at")
            if posted_at:
                posted_dt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
                if posted_dt >= week_ago:
                    submission["_assignment"] = assign
                    recent_grades.append(submission)

    recent_grades.sort(key=lambda x: x.get("posted_at", ""), reverse=True)

    course_activity = []
    for item in activity:
        context_code = item.get("context_code", "")
        if f"course_{course_id}" in context_code:
            course_activity.append(item)

    course_activity.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    recent_activity = course_activity[:10]

    return {
        "course": course,
        "enrollment": student_enrollment,
        "assignments": all_assignments,
        "upcoming": upcoming_assignments,
        "announcements": recent_announcements,
        "instructors": instructors,
        "planner": planner,
        "recent_grades": recent_grades,
        "recent_activity": recent_activity,
    }


def render_dashboard(data: dict) -> None:
    console = Console()
    course = data["course"]
    enrollment = data["enrollment"]
    domain = canvas_api.retrieve_domain()

    console.print()
    console.print(
        Panel.fit(
            f"[bold cyan]{course.get('name', 'Unknown Course')}[/bold cyan]\n"
            f"[dim]{course.get('course_code', '')}[/dim]",
            title="Course Overview",
            border_style="cyan",
        )
    )

    if enrollment and enrollment.get("grades"):
        grades = enrollment["grades"]
        current_score = grades.get("current_score")
        current_grade = grades.get("current_grade")
        final_score = grades.get("final_score")
        final_grade = grades.get("final_grade")

        grade_text = Text()
        if current_score is not None and current_grade:
            grade_text.append(
                f"Current: [bold]{current_score:.1f}% ({current_grade})[/bold]"
            )
        if final_score is not None and final_grade:
            if grade_text:
                grade_text.append("  |  ")
            grade_text.append(f"Final: [bold]{final_score:.1f}% ({final_grade})[/bold]")

        if grade_text:
            console.print(Panel(grade_text, border_style="green", title="Grade"))

    instructors = data["instructors"]
    if instructors:
        teacher_names = []
        ta_names = []
        for u in instructors:
            is_ta = False
            for enroll in u.get("enrollments", []):
                if enroll.get("role") == "TaEnrollment":
                    is_ta = True
                    break
            if is_ta:
                ta_names.append(u.get("name", "Unknown"))
            else:
                teacher_names.append(u.get("name", "Unknown"))

        staff_text = Text()
        if teacher_names:
            staff_text.append("[bold]Teachers:[/bold] ")
            staff_text.append(", ".join(teacher_names))
        if ta_names:
            if staff_text:
                staff_text.append("\n")
            staff_text.append("[bold]TAs:[/bold] ")
            staff_text.append(", ".join(ta_names))

        console.print(Panel(staff_text, border_style="blue", title="Staff"))

    html_url = course.get("html_url", f"https://{domain}/courses/{course.get('id')}")
    grades_url = f"{html_url}/grades"

    links_text = Text()
    links_text.append(f"[link={html_url}]Course Page[/link]\n")
    links_text.append(f"[link={grades_url}]Grades Page[/link]")

    console.print(Panel(links_text, border_style="dim", title="Quick Links"))

    upcoming = data["upcoming"]
    if upcoming:
        upcoming_table = Table(show_header=True, header_style="bold magenta")
        upcoming_table.add_column("Status", width=8)
        upcoming_table.add_column("Assignment", width=30)
        upcoming_table.add_column("Due", width=20)
        upcoming_table.add_column("Points", justify="right", width=8)
        upcoming_table.add_column("Type", width=15)

        for assign in upcoming[:10]:
            status_icon, status_color = get_assignment_status(assign)
            name = assign.get("name", "Unknown")[:28]
            due = format_datetime(assign.get("due_at", ""))
            points = assign.get("points_possible", 0)
            group = assign.get("_group_name", "")

            lockdown = ""
            if assign.get("require_lockdown_browser"):
                lockdown = "🔒"

            upcoming_table.add_row(
                f"[{status_color}]{status_icon}[/{status_color}]",
                name,
                due,
                f"{points:.0f}" if isinstance(points, float) else str(points),
                f"{group} {lockdown}".strip(),
            )

        console.print(
            Panel(
                upcoming_table,
                title=f"[bold]Upcoming (Next 7 Days)[/bold] ({len(upcoming)} items)",
            )
        )
    else:
        console.print(
            Panel(
                "[dim]No assignments due in the next 7 days[/dim]",
                title="[bold]Upcoming (Next 7 Days)[/bold]",
            )
        )

    recent_announcements = data["announcements"]
    if recent_announcements:
        console.print()
        console.print("[bold magenta]Recent Announcements[/bold magenta]")

        for ann in recent_announcements[:5]:
            title = ann.get("title", "Untitled")
            posted = ann.get("posted_at", "")
            author = ann.get("author", {}).get("display_name", "Unknown")
            posted_str = format_date_relative(posted) if posted else ""

            message_html = ann.get("message", "")
            message_text = strip_html(message_html)[:100]

            read_state = ann.get("read_state", "read")
            read_indicator = (
                "[dim]✓ read[/dim]" if read_state == "read" else "[bold]! unread[/bold]"
            )

            console.print(f"  📢 [bold]{title}[/bold] {read_indicator}")
            console.print(f"     [dim]{posted_str} by {author}[/dim]")
            if message_text:
                console.print(f"     [dim]{message_text}...[/dim]")
            console.print()

    recent_grades = data["recent_grades"]
    if recent_grades:
        console.print("[bold green]Recently Graded[/bold green]")

        for sub in recent_grades[:5]:
            assign = sub.get("_assignment", {})
            name = assign.get("name", "Unknown")[:35]
            score = sub.get("score", 0)
            points = assign.get("points_possible", 0)
            posted = sub.get("posted_at", "")
            posted_str = format_date_relative(posted) if posted else ""

            comment = (
                sub.get("grader_comments", [{}])[0].get("comment", "")
                if sub.get("grader_comments")
                else ""
            )
            comment_preview = comment[:60] if comment else ""

            console.print(f"  ✅ [bold]{name}[/bold]")
            console.print(f"     Score: [green]{score}/{points}[/green] | {posted_str}")
            if comment_preview:
                console.print(f'     [dim]"{comment_preview}"[/dim]')
            console.print()

    console.print()


def strip_html(html: str) -> str:
    import re

    if not html:
        return ""
    text = re.sub(r"<[^>]+>", "", html)
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return text.strip()


@app.command(name="view")
def view_course(course_id: str, json: bool = False):
    """
    Display a comprehensive dashboard for a course including metadata, upcoming assignments, and recent activity.

    Example usage: canvas-lms-cli classes view 1068
    """

    data = fetch_course_dashboard(course_id)

    if json:
        import json as json_module

        data_clean = {k: v for k, v in data.items() if k != "recent_grades"}
        import copy

        data_clean = copy.deepcopy(data)
        for sub in data_clean.get("recent_grades", []):
            sub.pop("_assignment", None)
        for assign in data_clean.get("assignments", []):
            assign.pop("_group_name", None)
            assign.pop("_group_weight", None)
        print(json_module.dumps(data_clean, indent=2, default=str))
        return

    render_dashboard(data)
