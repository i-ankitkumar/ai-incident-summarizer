from pathlib import Path

from incidentlens.analysis import analyze
from incidentlens.events import parse_jsonl
from incidentlens.timeline import build_incidents

REPO_ROOT = Path(__file__).parent.parent
INCIDENTS_DIR = REPO_ROOT / "incidents"


def _report_for(filename):
    events = parse_jsonl(INCIDENTS_DIR / filename)
    incident = build_incidents(events)[0]
    return analyze(incident)


def test_checkout_latency_spike_origin_is_checkout_service():
    report = _report_for("checkout-latency-spike.jsonl")
    assert report.likely_origin_service == "checkout-service"
    assert report.origin_event.severity in ("ERROR", "CRITICAL")


def test_db_connection_pool_exhaustion_origin_is_orders_db():
    report = _report_for("db-connection-pool-exhaustion.jsonl")
    assert report.likely_origin_service == "orders-db"


def test_certificate_expiry_origin_is_ingress_gateway():
    report = _report_for("certificate-expiry-outage.jsonl")
    assert report.likely_origin_service == "ingress-gateway"


def test_blast_radius_counts_distinct_services():
    report = _report_for("checkout-latency-spike.jsonl")
    assert report.blast_radius == 4


def test_noisiest_service_matches_actual_max_event_count():
    report = _report_for("checkout-latency-spike.jsonl")
    counts: dict[str, int] = {}
    for event in report.incident.events:
        counts[event.service] = counts.get(event.service, 0) + 1
    assert report.noisiest_service_count == max(counts.values())
    assert counts[report.noisiest_service] == report.noisiest_service_count


def test_duration_minutes_is_positive_and_matches_timedelta():
    report = _report_for("certificate-expiry-outage.jsonl")
    assert report.duration_minutes > 0
    assert abs(report.duration_minutes - report.incident.duration.total_seconds() / 60) < 1e-9
