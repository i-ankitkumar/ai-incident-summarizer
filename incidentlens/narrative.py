"""Optional LLM-generated incident narrative. Fails soft with no API key, no SDK, or an API error."""

from __future__ import annotations

import os

from .analysis import IncidentReport

DEFAULT_MODEL = "claude-sonnet-4-5"

_SYSTEM_PROMPT = """You are an SRE writing a concise post-incident note for engineers who were not on-call.
Use only the facts given in the report and event excerpts below. Do not invent services,
timestamps, or causes that are not present in the data. Reference services and severities
by the exact names given. Keep it to 4-6 sentences: what happened, where it most likely
started, how far it spread, and how it resolved (if the data shows a recovery)."""


def synthesize(report: IncidentReport) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    model = os.environ.get("INCIDENTLENS_MODEL", DEFAULT_MODEL)

    lines = [
        f"Incident window: {report.incident.start.isoformat()} to {report.incident.end.isoformat()} "
        f"({report.duration_minutes:.1f} minutes)",
        f"Services affected ({report.blast_radius}): {', '.join(report.services)}",
        f"Likely origin: {report.likely_origin_service} "
        f'(earliest actionable event: "{report.origin_event.message}")',
        f"Noisiest service: {report.noisiest_service} ({report.noisiest_service_count} events)",
        f"Severity breakdown: {report.severity_counts}",
        "",
        "Event excerpts:",
    ]
    for event in report.incident.events:
        lines.append(f"  [{event.timestamp.isoformat()}] {event.severity} {event.service}: {event.message}")

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": "\n".join(lines)}],
        )
        return response.content[0].text.strip()
    except Exception:
        return None
