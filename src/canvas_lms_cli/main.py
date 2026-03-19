import typer
from .auth import authenticate_from_url
from .classes import app as classes_app

app = typer.Typer()
app.add_typer(classes_app, name="classes")


@app.command()
def authenticate(link: str) -> None:
    result = authenticate_from_url(link)

if __name__ == "__main__":
    app()
