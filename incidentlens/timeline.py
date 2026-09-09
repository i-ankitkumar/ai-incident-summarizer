"""Cluster raw events into discrete incidents based on time proximity."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta

from .events import Event

DEFAULT_GAP = timedelta(minutes=15)


@dataclass
class Incident:
    events: list[Event] = field(default_factory=list)

    @property
    def start(self):
        return self.events[0].timestamp

    @property
    def end(self):
        return self.events[-1].timestamp

    @property
    def duration(self):
        return self.end - self.start

    @property
    def services(self) -> set[str]:
        return {e.service for e in self.events}

    def severity_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.events:
            counts[event.severity] = counts.get(event.severity, 0) + 1
        return counts


def build_incidents(events: list[Event], gap: timedelta = DEFAULT_GAP) -> list[Incident]:
    """Group chronologically sorted events into incidents separated by quiet gaps.

    Two consecutive events belong to the same incident if they land no more than
    `gap` apart, regardless of which service emitted them -- this is what lets a
    cascading failure (one service's outage triggering alerts in its dependents)
    show up as a single incident instead of several seemingly unrelated ones.
    """
    if not events:
        return []

    incidents: list[Incident] = [Incident(events=[events[0]])]
    for event in events[1:]:
        current = incidents[-1]
        if event.timestamp - current.end <= gap:
            current.events.append(event)
        else:
            incidents.append(Incident(events=[event]))
    return incidents
