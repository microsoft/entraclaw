"""Local→backend migration helper for ADR-005 Phase 5.

Walks an existing local data directory (typically ``~/.entraclaw/data``)
and copies every file into a target :class:`MemoryBackend` (typically
:class:`BlobBackend`). Idempotent by design: re-runs after a partial
failure resume cleanly because already-present keys are skipped, with
the target's content treated as authoritative (per ADR §"Migration":
"blob becomes the source of truth, local is now a cache").

Source files are *never* deleted — that's the rollback path for
``ENTRACLAW_KEEP_MEMORY_LOCAL=true``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from entraclaw.storage.backend import MemoryBackend


@dataclass
class MigrationReport:
    """Summary of one ``migrate_local_to_backend`` call."""

    copied: int = 0
    skipped: int = 0
    bytes_copied: int = 0
    keys_copied: list[str] = field(default_factory=list)
    errors: list[tuple[str, str]] = field(default_factory=list)
    """List of (key, error_message) for files that failed to copy."""


def migrate_local_to_backend(
    local_root: Path, target: MemoryBackend
) -> MigrationReport:
    """Copy every file under *local_root* into *target*.

    Keys are the POSIX-style relative path from *local_root* (so a file
    at ``<root>/interactions/2026-04-17.jsonl`` becomes the key
    ``"interactions/2026-04-17.jsonl"``).

    A non-existent or empty *local_root* returns an empty report.
    Files already present in *target* are skipped (cloud is authoritative
    on rerun). Per-file errors are captured in ``report.errors`` rather
    than raised, so one bad file doesn't abort the whole migration.
    """
    report = MigrationReport()
    root = Path(local_root)
    if not root.exists():
        return report

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        key = path.relative_to(root).as_posix()
        try:
            if target.exists(key):
                report.skipped += 1
                continue
            content = path.read_text()
        except Exception as exc:  # noqa: BLE001 — record + continue
            report.errors.append((key, str(exc)))
            continue
        try:
            target.write_text(key, content)
        except Exception as exc:  # noqa: BLE001
            report.errors.append((key, str(exc)))
            continue
        report.copied += 1
        report.bytes_copied += len(content)
        report.keys_copied.append(key)

    return report
