# incidentlens — AI Observability Incident Summarizer

A small tool that turns a pile of raw alerts and log lines from a cascading
failure into a single, structured incident report: what broke first, how far
it spread, which service was noisiest, and (optionally) a short AI-written
narrative — all traceable back to the exact events that produced it.

## Why

Most "AI incident summarizer" demos work by dumping raw logs straight into an
LLM prompt and hoping for a coherent story back. That's expensive per
incident, non-deterministic (ask twice, get two different root causes), and
opaque — there's no way to check *why* the model picked a given service as
the origin. This tool inverts that: a deterministic pass over the timeline
does the actual reconstruction — clustering events, picking the earliest
actionable signal as the likely origin, counting blast radius — using nothing
but timestamps and severities. That result is exact, reproducible, and free.
An LLM only gets involved, optionally, to turn the structured report into a
few sentences of prose for a status page or handoff note.

## How it works

```
incidents/*.jsonl  ──parse_directory()──▶  chronological Events
                                                    │
                                        build_incidents(gap=15min)
                                                    │
                                                    ▼
                                          clustered Incidents
                                                    │
                                              analyze()
                                                    │
                        ┌───────────────────────────┴───────────────────────────┐
                        │                                                       │
              always: origin service, blast radius,                  --synthesize: narrative.synthesize()
              noisiest service, severity breakdown                   (Claude API, optional, graceful
                                                                        fallback to the report only)
```

Consecutive events within a configurable quiet window (15 minutes by default)
are treated as one incident, regardless of which service emitted them — this
is what lets a cascading failure (one service's outage tripping alerts in its
dependents seconds later) show up as a single incident instead of several
seemingly unrelated ones. Within an incident, the "likely origin" is the
service behind the earliest CRITICAL or ERROR event — a simple heuristic, not
ground truth, but one that's always inspectable: the exact backing event ships
in the report.

## Install

```bash
pip install -e .
# optional: pip install -e ".[ai]"   # to enable --synthesize
```

## Usage

```bash
$ incidentlens summarize incidents/checkout-latency-spike.jsonl
```

```
                                  Incident 1: 2026-08-14 09:14 UTC
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field              ┃ Value                                                                       ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Duration           │ 12.0 min                                                                    │
│ Services affected  │ 4 (checkout-service, inventory-service, notification-service,               │
│                    │ payment-service)                                                            │
│ Likely origin      │ checkout-service                                                            │
│ Origin event       │ ERROR: timeout calling inventory-service after 5000ms                       │
│ Noisiest service   │ checkout-service (6 events)                                                 │
│ Severity breakdown │ CRITICAL=1, ERROR=4, INFO=3, WARNING=3                                      │
└────────────────────┴─────────────────────────────────────────────────────────────────────────────┘
```

`incidentlens` correctly separates unrelated incidents even when their raw
event files sit in the same directory:

```bash
$ incidentlens list incidents/
```

```
                    Detected incidents
┏━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
┃ # ┃ Start                ┃ Duration ┃ Services ┃ Events ┃
┡━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━┩
│ 1 │ 2026-08-14 09:14 UTC │ 12.0 min │ 4        │ 11     │
│ 2 │ 2026-08-20 14:02 UTC │ 12.0 min │ 5        │ 11     │
│ 3 │ 2026-08-27 03:00 UTC │ 12.4 min │ 5        │ 10     │
└───┴──────────────────────┴──────────┴──────────┴────────┘
```

Passing `--synthesize` without `ANTHROPIC_API_KEY` set shows exactly what it
will and won't do — same fail-soft pattern as the `--enhance` flag in
[azpipegen](https://github.com/i-ankitkumar/azure-pipeline-generator) and the
`--synthesize` flag in
[policyrag](https://github.com/i-ankitkumar/compliance-policy-bot):

```bash
$ incidentlens summarize incidents/certificate-expiry-outage.jsonl --synthesize
```

```
                                Incident 1: 2026-08-27 03:00 UTC
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Field              ┃ Value                                                                   ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Duration           │ 12.4 min                                                                │
│ Services affected  │ 5 (auth-service, ingress-gateway, mobile-bff, oncall-bot, web-frontend) │
│ Likely origin      │ ingress-gateway                                                         │
│ Origin event       │ ERROR: TLS handshake failed: certificate expired 2026-08-27T03:00:00Z   │
│ Noisiest service   │ ingress-gateway (5 events)                                              │
│ Severity breakdown │ CRITICAL=1, ERROR=5, INFO=3, WARNING=1                                  │
└────────────────────┴─────────────────────────────────────────────────────────────────────────┘
--synthesize requested but skipped (no ANTHROPIC_API_KEY, missing SDK, or API error) -- showing the
deterministic report only.
```

With a key set, that last line is replaced by a short, still-grounded prose
summary built only from the fields and event excerpts above it — the model
is instructed not to invent services, timestamps, or causes beyond what the
report already contains.

## The sample incidents

Three synthetic but realistic cascading failures, each on its own day so they
never accidentally merge: a checkout-latency spike that starts in
`checkout-service` and trips `payment-service` and `notification-service`; a
database connection-pool exhaustion in `orders-db` that cascades into
`orders-service`, `checkout-service`, and `auth-service`; and a TLS
certificate expiry on `ingress-gateway` that takes out login, mobile, and web
traffic at once. Each has a clear, verifiable origin service, which is what
the test suite checks against.

## Development

```bash
pip install -e ".[dev]"
pytest
```

19 tests cover event parsing and validation, time-based incident clustering
(including that unrelated incidents days apart never merge, and that a
smaller gap threshold splits a single incident into several), and root-cause
analysis correctness against all three shipped sample incidents.

## Roadmap

- [ ] Ingest adapters for real sources: Prometheus Alertmanager webhooks, a generic syslog tailer
- [ ] Per-service dependency graph to replace the "noisiest service" heuristic with an actual blast-radius trace
- [ ] `--format json` for piping reports into a status-page or ticketing integration
- [ ] Rolling incident history with `incidentlens compare` to spot repeat root causes over time

## About

Built by [Ankit Kumar](https://iankitkumar.in) — DevOps/Cloud engineer whose
day job includes a Global Policy & Compliance Standards project, which is a
different flavor of the same instinct behind this tool: turn a pile of raw
signals into something an on-call engineer can actually act on. Part of a
series of small, real infra tools — see [pinned
repos](https://github.com/i-ankitkumar) for the others, including
[tfscan](https://github.com/i-ankitkumar/terraform-security-scanner) (policy
enforcement for Terraform),
[azpipegen](https://github.com/i-ankitkumar/azure-pipeline-generator), and
[policyrag](https://github.com/i-ankitkumar/compliance-policy-bot).

## License

MIT
