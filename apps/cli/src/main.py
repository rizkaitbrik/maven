import typer
from commands.search import search
from commands.index import index
from commands import daemon_cmd

app = typer.Typer(
    help="Maven CLI",
    no_args_is_help=True,
    invoke_without_command=False,
    add_completion=False
)


# Daemon subcommand group
daemon_app = typer.Typer(help="Manage Maven daemon")
daemon_app.command(name="start")(daemon_cmd.start)
daemon_app.command(name="stop")(daemon_cmd.stop)
daemon_app.command(name="status")(daemon_cmd.status)
daemon_app.command(name="logs")(daemon_cmd.logs)
daemon_app.command(name="restart")(daemon_cmd.restart)

@app.callback()
def callback():
    """Maven CLI - Search files using platform-native indexing."""
    pass

app.command(name="search")(search)
app.command(name="index")(index)
app.add_typer(daemon_app, name="daemon")

def main():
    app()

if __name__ == "__main__":
    main()