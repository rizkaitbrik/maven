import typer
from commands.search import search

app = typer.Typer(
    help="Maven CLI",
    no_args_is_help=True,
    invoke_without_command=False,
    add_completion=False
)

@app.callback()
def callback():
    """Maven CLI - Search files using platform-native indexing."""
    pass

app.command(name="search")(search)

def main():
    app()

if __name__ == "__main__":
    main()