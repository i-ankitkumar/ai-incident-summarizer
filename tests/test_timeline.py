from datetime import timedelta
from pathlib import Path

from incidentlens.events import parse_directory, parse_jsonl
from incidentlens.timeline import build_incidents

REPO_ROOT = Path(__file__).parent.parent
INCIDENTS_DIR = REPO_ROOT / "incidents"


def test_single_file_clusters_into_one_incident():
    events = parse_jsonl(INCIDENTS_DIR / "checkout-latency-spike.jsonl")
    incidents = build_incidents(events)
    assert len(incidents) == 1
    assert incidents[0].services == {
        "checkout-service",
        "payment-service",
        "notification-service",
        "inventory-service",
    }


def test_directory_of_far_apart_incidents_stays_separate():
    events = parse_directory(INCIDENTS_DIR)
    incidents = build_incidents(events)
    assert len(incidents) == 3


def test_small_gap_keeps_events_together():
    events = parse_jsonl(INCIDENTS_DIR / "checkout-latency-spike.jsonl")
    incidents = build_incidents(events, gap=timedelta(minutes=15))
    assert len(incidents) == 1


def test_tiny_gap_splits_events_apart():
    events = parse_jsonl(INCIDENTS_DIR / "checkout-latency-spike.jsonl")
    incidents = build_incidents(events, gap=timedelta(seconds=30))
    assert len(incidents) > 1


def test_empty_events_returns_no_incidents():
    assert build_incidents([]) == []


def test_incident_duration_and_severity_counts():
    events = parse_jsonl(INCIDENTS_DIR / "db-connection-pool-exhaustion.jsonl")
    incidents = build_incidents(events)
    incident = incidents[0]
    assert incident.duration == incident.end - incident.start
    counts = incident.severity_counts()
    assert counts["ERROR"] >= 3
    assert counts["CRITICAL"] == 1
