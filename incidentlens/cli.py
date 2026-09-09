"""Command-line interface for incidentlens."""

from __future__ import annotations

import argparse
import sys
from datetime import timedelta
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analysis import analyze
from .events import Event, parse_directory, parse_jsonl
from .narrative import synthesize
from .timeline import build_incidents

console = Console()


def _load_events(path: Path) -> list[Event]:
    if path.is_dir():
        return parse_directory(path)
    return parse_jsonl(path)


def _run_summarize(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]No such file or directory:[/red] {path}")
        return 1

    events = _load_events(path)
    if not events:
        console.print("[yellow]No events found.[/yellow]")
        return 0

    incidents = build_incidents(events, gap=timedelta(minutes=args.gap))

    for i, incident in enumerate(incidents, start=1):
        report = analyze(incident)

        table = Table(title=f"Incident {i}: {report.incident.start.strftime('%Y-%m-%d %H:%M UTC')}")
        table.add_column("Field")
        table.add_column("Value")
        table.add_row("Duration", f"{report.duration_minutes:.1f} min")
        table.add_row("Services affected", f"{report.blast_radius} ({', '.join(report.services)})")
        table.add_row("Likely origin", report.likely_origin_service)
        table.add_row("Origin event", f"{report.origin_event.severity}: {report.origin_event.message}")
        table.add_row("Noisiest service", f"{report.noisiest_service} ({report.noisiest_service_count} events)")
        table.add_row(
            "Severity breakdown",
            ", ".join(f"{k}={v}" for k, v in sorted(report.severity_counts.items())),
        )
        console.print(table)

        if args.synthesize:
            narrative = synthesize(report)
            if narrative:
                console.print(Panel(narrative, title="AI-synthesized summary", border_style="green"))
            else:
                console.print(
                    "[dim]--synthesize requested but skipped (no ANTHROPIC_API_KEY, missing SDK, "
                    "or API error) -- showing the deterministic report only.[/dim]"
                )

    return 0


def _run_list(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.exists():
        console.print(f"[red]No such file or directory:[/red] {path}")
        return 1

    events = _load_events(path)
    incidents = build_incidents(events, gap=timedelta(minutes=args.gap))

    table = Table(title="Detected incidents")
    table.add_column("#")
    table.add_column("Start")
    table.add_column("Duration")
    table.add_column("Services")
    table.add_column("Events")
    for i, incident in enumerate(incidents, start=1):
        table.add_row(
            str(i),
            incident.start.strftime("%Y-%m-%d %H:%M UTC"),
            f"{incident.duration.total_seconds() / 60:.1f} min",
            str(len(incident.services)),
            str(len(incident.events)),
        )
    console.print(table)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="incidentlens",
        description="Reconstruct and summarize incidents from raw observability events.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    summarize = sub.add_parser("summarize", help="Summarize incidents found in a file or directory of event logs")
    summarize.add_argument("path", help="Path to a .jsonl event file or a directory of them")
    summarize.add_argument(
        "--gap", type=float, default=15, help="Minutes of quiet time that separates two incidents (default: 15)"
    )
    summarize.add_argument(
        "--synthesize", action="store_true", help="Also generate an AI narrative summary (requires ANTHROPIC_API_KEY)"
    )
    summarize.set_defaults(func=_run_summarize)

    list_cmd = sub.add_parser("list", help="List incidents detected in a file or directory, without full detail")
    list_cmd.add_argument("path", help="Path to a .jsonl event file or a directory of them")
    list_cmd.add_argument(
        "--gap", type=float, default=15, help="Minutes of quiet time that separates two incidents (default: 15)"
    )
    list_cmd.set_defaults(func=_run_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
