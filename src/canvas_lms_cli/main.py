import typer
from .auth import authenticate_from_url

app = typer.Typer()

@app.command()
def authenticate(link: str) -> None:
    result = authenticate_from_url(link)
    print(result)

if __name__ == "__main__":
    app()
