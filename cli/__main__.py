"""CLI entrypoint for OpenGraph AI.

Mounts subcommand groups onto the root Typer application.
Run with:  python -m cli [OPTIONS] COMMAND [ARGS]...
"""

import typer

from cli.commands.extract import app as extract_app
from cli.commands.graphdb import app as graphdb_app
from cli.commands.upload import upload
from engine.config import load_env_config

load_env_config()

app = typer.Typer(
    name="opengraph",
    help="OpenGraph AI — turn heterogeneous data into semantic knowledge graphs.",
    no_args_is_help=True,
)

# ── Register subcommand groups ────────────────────────────────────────────────
app.add_typer(extract_app, name="extract")
app.add_typer(graphdb_app, name="graphdb")
app.command("upload")(upload)

@app.callback(invoke_without_command=True)
def root(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit."),
) -> None:
    """OpenGraph AI CLI root command."""
    if version:
        typer.echo("opengraph 0.1.0")
        raise typer.Exit()


if __name__ == "__main__":
    app()
