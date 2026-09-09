"""Event parsing: turn raw observability signals (JSON lines) into structured Events."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_VALID_SEVERITIES = ("CRITICAL", "ERROR", "WARNING", "INFO")


@dataclass(frozen=True)
class Event:
    timestamp: datetime
    service: str
    severity: str
    message: str
    source_file: str

    @property
    def is_actionable(self) -> bool:
        return self.severity in ("CRITICAL", "ERROR")


def _parse_line(line: str, source_file: str, line_no: int) -> Event:
    try:
        data = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source_file}:{line_no}: invalid JSON") from exc

    raw_timestamp = data.get("timestamp")
    if not raw_timestamp:
        raise ValueError(f"{source_file}:{line_no}: missing 'timestamp' field")
    try:
        timestamp = datetime.fromisoformat(str(raw_timestamp).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{source_file}:{line_no}: invalid timestamp {raw_timestamp!r}") from exc

    severity = str(data.get("severity", "INFO")).upper()
    if severity not in _VALID_SEVERITIES:
        raise ValueError(f"{source_file}:{line_no}: unknown severity {severity!r}")

    service = data.get("service")
    if not service:
        raise ValueError(f"{source_file}:{line_no}: missing 'service' field")

    message = data.get("message", "")
    return Event(
        timestamp=timestamp,
        service=service,
        severity=severity,
        message=message,
        source_file=source_file,
    )


def parse_jsonl(path: Path) -> list[Event]:
    """Parse a single newline-delimited JSON event file."""
    path = Path(path)
    events: list[Event] = []
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        events.append(_parse_line(line, path.name, line_no))
    return sorted(events, key=lambda e: e.timestamp)


def parse_directory(directory: Path) -> list[Event]:
    """Parse every *.jsonl file in a directory and merge them into one chronological stream."""
    events: list[Event] = []
    for path in sorted(Path(directory).glob("*.jsonl")):
        events.extend(parse_jsonl(path))
    return sorted(events, key=lambda e: e.timestamp)
