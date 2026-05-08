"""Helper utilities for the skill-refiner skill.

Parses .metplot/task-log.jsonl and groups entries by skill / category to make
the refiner's job easier. The skill itself does the LLM-driven work of
deciding what's worth refining; this script just does the structured I/O.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


def task_log_path(workspace: Path | None = None) -> Path:
    """Return the path to the task log for the current workspace."""
    root = workspace or Path.cwd()
    return root / ".metplot" / "task-log.jsonl"


def read_entries(log_path: Path) -> Iterator[dict]:
    """Yield parsed JSON entries from the task log, skipping malformed lines."""
    if not log_path.exists():
        return
    with log_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # Tolerate stray lines; the agent may have appended notes.
                continue


def filter_session(entries: Iterator[dict], since: datetime) -> list[dict]:
    """Keep only entries with timestamp >= since."""
    out = []
    for e in entries:
        ts = e.get("ts")
        if not ts:
            continue
        try:
            t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if t >= since:
            out.append(e)
    return out


def group_by_skill(entries: list[dict]) -> dict[str, list[dict]]:
    """Group entries by the `skill` field."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for e in entries:
        skill = e.get("skill", "<unknown>")
        groups[skill].append(e)
    return dict(groups)


def append_entry(entry: dict, log_path: Path | None = None) -> None:
    """Append a single entry to the task log. Skills call this after each step."""
    path = log_path or task_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    entry.setdefault("ts", datetime.now(timezone.utc).isoformat())
    with path.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def session_start(workspace: Path | None = None) -> datetime:
    """Pick a heuristic session-start: 6 hours ago or last 'session_start' marker."""
    log = task_log_path(workspace)
    cutoff = datetime.now(timezone.utc).replace(microsecond=0)
    cutoff = cutoff.fromtimestamp(cutoff.timestamp() - 6 * 3600, tz=timezone.utc)
    if not log.exists():
        return cutoff
    last_marker = None
    for e in read_entries(log):
        if e.get("step") == "session_start":
            ts = e.get("ts")
            if ts:
                try:
                    last_marker = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except ValueError:
                    pass
    return last_marker or cutoff


if __name__ == "__main__":
    # Sanity dump for debugging.
    log = task_log_path()
    entries = list(read_entries(log))
    print(f"Loaded {len(entries)} entries from {log}")
    grouped = group_by_skill(entries)
    for skill, items in grouped.items():
        print(f"  {skill}: {len(items)} entries")
