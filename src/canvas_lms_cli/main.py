import sys

import typer
from .auth import authenticate_from_url
from .classes import app as classes_app
from .assignments import app as assignments_app

app = typer.Typer(pretty_exceptions_show_locals=False)
app.add_typer(classes_app, name="classes")
app.add_typer(assignments_app, name="assignments")


@app.command()
def authenticate(link: str) -> None:
    """
    Authenticate to Canvas using a Mobile Login URL from a Mobile Login QR code.
    
    Example usage: canvas-lms-cli authenticate --link <MOBILE_LOGIN_URL>
    """
    
    result = authenticate_from_url(link)

def run() -> None:
    """Entry point: show errors as one readable line instead of a traceback."""
    try:
        app()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
