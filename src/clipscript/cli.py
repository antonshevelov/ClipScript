"""Command-line entry points for ClipScript."""

from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from clipscript.engine import render_project, validate_project_references
from clipscript.project import Project, ProjectError, load_project, resolve_path

app = typer.Typer(help="Generate vertical videos from versioned JSON scripts.")
console = Console()

def _load(input_path: str) -> Project:
    try:
        return load_project(input_path)
    except ProjectError as exc:
        console.print(f"[red]Script validation error: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def validate(
    input_path: str = typer.Option(..., "--input", "-i", help="Path to a JSON video script."),
) -> None:
    """Validate a script, its template, and all referenced assets."""
    project = _load(input_path)
    try:
        validate_project_references(project)
    except ValueError as exc:
        console.print(f"[red]Project validation error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print("[bold green]Script is valid.[/bold green]")


@app.command()
def generate(
    input_path: str = typer.Option(..., "--input", "-i", help="Path to a JSON video script."),
    output_path: Optional[str] = typer.Option(  # noqa: UP045 - Typer evaluates hints on Python 3.9.
        None, "--output", "-o", help="Path for the final MP4."
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing output file."),
) -> None:
    """Generate a vertical video from a JSON script."""
    project = _load(input_path)
    output = resolve_path(output_path or project.script.output, base_dir=project.script_dir)
    if output.exists() and not overwrite:
        console.print(f"[yellow]Output '{output}' already exists. Use --overwrite to replace it.[/yellow]")
        raise typer.Exit(code=1)
    try:
        rendered_path = render_project(project, output_path=output, progress=console.print)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Render failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold green]Video generated:[/bold green] {rendered_path}")


if __name__ == "__main__":
    app()
