from __future__ import annotations
import os
import json
import typer
from rich.console import Console
from rich.table import Table
from dotenv import load_dotenv

load_dotenv()

app = typer.Typer(help="Ripple — trend-driven social content generator")
console = Console()


@app.command()
def run(
    niche: str = typer.Argument(..., help="Content niche, e.g. 'AI productivity tools'"),
    platforms: str = typer.Option("twitter,linkedin", help="Comma-separated platforms"),
    angles: int = typer.Option(3, help="Number of content angles"),
    variations: int = typer.Option(2, help="Variations per angle per platform"),
    subreddits: str = typer.Option("", help="Comma-separated subreddits (optional)"),
    top_k: int = typer.Option(5, help="Memory lookback depth"),
):
    from core.config import RunConfig
    from core import pipeline

    config = RunConfig(
        niche=niche,
        platforms=[p.strip() for p in platforms.split(",")],
        angles=angles,
        variations=variations,
        subreddits=[s.strip() for s in subreddits.split(",") if s.strip()],
        top_k_memory=top_k,
    )

    console.print(f"\n[bold cyan]Running Ripple[/] for niche: [yellow]{niche}[/]")
    console.print(f"Platforms: {', '.join(config.platforms)} | Angles: {angles} | Variations: {variations}\n")

    with console.status("Agents working..."):
        result = pipeline.run(config)

    if result.error:
        console.print(f"[bold red]Error:[/] {result.error}")
        raise typer.Exit(1)

    console.print(f"[bold green]Done[/] in {result.duration_seconds}s — {len(result.pieces)} pieces generated\n")

    table = Table(title=f"Top Content — Run {result.run_id}", show_lines=True)
    table.add_column("Platform", style="cyan", width=10)
    table.add_column("Angle", width=20)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Hook", width=55)
    table.add_column("Rec", width=4)

    for piece in sorted(result.pieces, key=lambda p: p.score, reverse=True)[:15]:
        table.add_row(
            piece.platform,
            piece.angle[:20],
            f"{piece.score:.0f}",
            piece.hook[:55],
            "★" if piece.recommended else "",
        )

    console.print(table)
    console.print(f"\nFull output saved to outputs/{result.run_id}.json")


@app.command()
def ui():
    """Launch the Streamlit UI."""
    import subprocess, sys
    ui_path = os.path.join(os.path.dirname(__file__), "ui", "app.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", ui_path])


@app.command()
def ingest(path: str = typer.Argument(..., help="Path to CSV with performance data")):
    """Ingest engagement CSV into memory."""
    from memory.ingest import ingest_csv
    stats = ingest_csv(path)
    console.print(f"[green]Ingested:[/] {stats['updated']} records, skipped {stats['skipped']}")


@app.command()
def runs():
    """List past runs."""
    from core import pipeline
    all_runs = pipeline.list_runs()
    if not all_runs:
        console.print("No runs found.")
        return
    table = Table(title="Past Runs")
    table.add_column("Run ID")
    table.add_column("Niche")
    table.add_column("Platforms")
    table.add_column("Pieces", justify="right")
    table.add_column("Duration", justify="right")
    for r in all_runs:
        table.add_row(
            r["run_id"],
            r["niche"][:40],
            ", ".join(r["platforms"]),
            str(r["pieces"]),
            f"{r['duration_seconds']}s",
        )
    console.print(table)


if __name__ == "__main__":
    app()
