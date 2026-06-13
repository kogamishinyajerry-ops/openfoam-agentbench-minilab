"""Append-only experience store backed by JSONL."""
from __future__ import annotations

import json
from pathlib import Path

from ..models import ExperienceRecord
from ..paths import DATA_DIR

DEFAULT_STORE = DATA_DIR / "experience_memory.jsonl"


class ExperienceStore:
    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path else DEFAULT_STORE

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def append(self, record: ExperienceRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(record.model_dump_json() + "\n")

    def extend(self, records: list[ExperienceRecord]) -> None:
        for r in records:
            self.append(r)

    def all(self) -> list[ExperienceRecord]:
        if not self.path.exists():
            return []
        out: list[ExperienceRecord] = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(ExperienceRecord.model_validate_json(line))
        return out

    def recall(self, failure_mode) -> ExperienceRecord | None:
        """The flywheel's *retrieval* half: given a failure mode, return the most
        recent stored lesson for it (or None if never seen). This is what lets a
        recurring fault reuse a known fix instead of exploring from scratch.

        ``failure_mode`` may be a ``FailureMode`` enum or its string value.
        """
        key = getattr(failure_mode, "value", failure_mode)
        matches = [r for r in self.all() if r.failure_mode.value == key]
        return matches[-1] if matches else None
