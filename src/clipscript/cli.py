"""Command-line entry points for ClipScript."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from clipscript.commands import clear_cache, doctor_checks, initialize_project, schema_json
from clipscript.engine import render_project, validate_project_references
from clipscript.project import Project, ProjectError, load_project, resolve_path
from clipscript.tts import TTSGenerationError, list_voices

app = typer.Typer(help="Generate vertical videos from versioned JSON scripts.")
cache_app = typer.Typer(help="Manage the local ClipScript TTS cache.")
app.add_typer(cache_app, name="cache")
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


@app.command()
def init(
    path: str = typer.Argument(..., help="Directory for the starter project."),
    force: bool = typer.Option(False, "--force", help="Replace existing starter files."),
) -> None:
    """Create an offline-runnable Schema v2 project."""
    try:
        script = initialize_project(Path(path), force)
    except ProjectError as exc:
        console.print(f"[red]Project initialization error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold green]Starter project created:[/bold green] {script}")


@app.command()
def doctor() -> None:
    """Check local media, cache, and provider prerequisites without network calls."""
    checks = doctor_checks()
    for name, passed, detail in checks:
        console.print(f"{'OK' if passed else 'FAIL'} {name}: {detail}")
    if not all(passed for name, passed, _ in checks if name != "ElevenLabs configuration"):
        raise typer.Exit(code=1)


@app.command()
def preview(
    input_path: str = typer.Option(..., "--input", "-i", help="Path to a JSON video script."),
    output_path: Optional[str] = typer.Option(  # noqa: UP045 - Typer evaluates hints on Python 3.9.
        None, "--output", "-o", help="Draft MP4 path."
    ),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite an existing draft."),
) -> None:
    """Render a lower-resolution, lower-fps draft without changing source files."""
    project = _load(input_path)
    output = resolve_path(output_path, project.script_dir) if output_path else project.script_dir / "output" / "preview.mp4"
    if output.exists() and not overwrite:
        console.print(f"[yellow]Preview '{output}' already exists. Use --overwrite to replace it.[/yellow]")
        raise typer.Exit(code=1)
    width, height = project.template.resolution
    scale = min(1.0, 360 / max(width, height))
    draft_template = project.template.model_copy(
        update={"resolution": [max(2, round(width * scale)), max(2, round(height * scale))], "fps": min(12, project.template.fps)}
    )
    try:
        rendered = render_project(replace(project, template=draft_template), output_path=output, progress=console.print)
    except (OSError, RuntimeError, ValueError) as exc:
        console.print(f"[red]Preview failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[bold green]Preview generated:[/bold green] {rendered}")


@app.command()
def schema(
    output_path: Optional[str] = typer.Option(  # noqa: UP045 - Typer evaluates hints on Python 3.9.
        None, "--output", "-o", help="Optional JSON Schema file."
    ),
) -> None:
    """Print the current Schema v2 JSON Schema or write it to a file."""
    content = schema_json()
    if output_path:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content, encoding="utf-8")
        console.print(f"Schema written: {output}")
    else:
        console.print(content, end="")


@app.command()
def voices(
    provider: str = typer.Option(..., "--provider", help="Voice provider: edge or elevenlabs."),
) -> None:
    """List provider voices with user-facing configuration errors."""
    try:
        for voice in list_voices(provider):
            console.print(voice)
    except TTSGenerationError as exc:
        console.print(f"[red]Voice lookup failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc


@cache_app.command("clear")
def cache_clear(
    yes: bool = typer.Option(False, "--yes", help="Confirm removal for non-interactive use."),
) -> None:
    """Clear only the effective ClipScript TTS cache."""
    try:
        clear_cache(yes)
    except ProjectError as exc:
        console.print(f"[red]Cache clear failed: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print("ClipScript TTS cache cleared.")


if __name__ == "__main__":
    app()
