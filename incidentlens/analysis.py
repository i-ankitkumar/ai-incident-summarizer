"""Deterministic root-cause and blast-radius analysis over a clustered incident."""

from __future__ import annotations

from dataclasses import dataclass

from .events import Event
from .timeline import Incident


@dataclass
class IncidentReport:
    incident: Incident
    likely_origin_service: str
    origin_event: Event
    noisiest_service: str
    noisiest_service_count: int
    blast_radius: int
    duration_minutes: float
    severity_counts: dict

    @property
    def services(self) -> list[str]:
        return sorted(self.incident.services)


def analyze(incident: Incident) -> IncidentReport:
    """Score an incident's timeline with two intentionally simple, explainable heuristics.

    Likely origin: the service that emitted the earliest actionable (CRITICAL or ERROR)
    event in the window. This is a heuristic, not ground truth -- a slow-building
    problem can surface as a WARNING elsewhere first -- but for cascading failures,
    where dependents start erroring within seconds of the root service, it is
    usually right, and it is always inspectable: the exact event backing the guess
    is included in the report.

    Noisiest service: whichever service produced the most events in the window,
    which is often the service engineers should silence first during an incident
    review, whether or not it is the root cause.
    """
    actionable = [e for e in incident.events if e.is_actionable] or list(incident.events)
    origin_event = min(actionable, key=lambda e: e.timestamp)

    counts: dict[str, int] = {}
    for event in incident.events:
        counts[event.service] = counts.get(event.service, 0) + 1
    noisiest_service, noisiest_count = max(counts.items(), key=lambda kv: kv[1])

    return IncidentReport(
        incident=incident,
        likely_origin_service=origin_event.service,
        origin_event=origin_event,
        noisiest_service=noisiest_service,
        noisiest_service_count=noisiest_count,
        blast_radius=len(incident.services),
        duration_minutes=incident.duration.total_seconds() / 60,
        severity_counts=incident.severity_counts(),
    )
