from pathlib import Path

import pytest

from incidentlens.events import parse_directory, parse_jsonl

REPO_ROOT = Path(__file__).parent.parent
INCIDENTS_DIR = REPO_ROOT / "incidents"


def test_parse_jsonl_returns_sorted_events():
    events = parse_jsonl(INCIDENTS_DIR / "checkout-latency-spike.jsonl")
    assert len(events) == 11
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_parse_jsonl_fields():
    events = parse_jsonl(INCIDENTS_DIR / "checkout-latency-spike.jsonl")
    first = events[0]
    assert first.service == "checkout-service"
    assert first.severity == "WARNING"
    assert "p99 latency" in first.message
    assert first.source_file == "checkout-latency-spike.jsonl"


def test_is_actionable():
    events = parse_jsonl(INCIDENTS_DIR / "checkout-latency-spike.jsonl")
    by_severity = {e.severity: e for e in events}
    assert by_severity["CRITICAL"].is_actionable
    assert by_severity["ERROR"].is_actionable
    assert not by_severity["WARNING"].is_actionable
    assert not by_severity["INFO"].is_actionable


def test_parse_directory_merges_all_files_chronologically():
    events = parse_directory(INCIDENTS_DIR)
    sources = {e.source_file for e in events}
    assert sources == {
        "certificate-expiry-outage.jsonl",
        "checkout-latency-spike.jsonl",
        "db-connection-pool-exhaustion.jsonl",
    }
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)


def test_missing_service_field_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"timestamp": "2026-01-01T00:00:00Z", "severity": "ERROR", "message": "oops"}\n')
    with pytest.raises(ValueError, match="missing 'service'"):
        parse_jsonl(bad)


def test_unknown_severity_raises(tmp_path):
    bad = tmp_path / "bad.jsonl"
    bad.write_text(
        '{"timestamp": "2026-01-01T00:00:00Z", "service": "x", "severity": "BOGUS", "message": "oops"}\n'
    )
    with pytest.raises(ValueError, match="unknown severity"):
        parse_jsonl(bad)


def test_blank_lines_are_skipped(tmp_path):
    doc = tmp_path / "sparse.jsonl"
    doc.write_text(
        '{"timestamp": "2026-01-01T00:00:00Z", "service": "x", "severity": "INFO", "message": "a"}\n'
        "\n"
        '{"timestamp": "2026-01-01T00:01:00Z", "service": "x", "severity": "INFO", "message": "b"}\n'
    )
    events = parse_jsonl(doc)
    assert len(events) == 2
