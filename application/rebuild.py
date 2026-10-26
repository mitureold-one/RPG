"""application/rebuild.py: Serviço de reconstrução de projeções determinísticas (C3)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from application.projection_engine import ProjectionEngine
from application.projectors import (
    CharacterSheetProjector,
    FactionProjector,
    JournalProjector,
    NpcProjector,
    QueueProjector,
    StateProjector,
)
from contracts.event import ActorRef, EventDraft
from contracts.ports import EventStore, EventStreamView, Projector
from contracts.serialization import canonical_json

SNAPSHOT_INTERVAL = 500


def default_projectors(
    initial_files: Mapping[str, str] | None = None,
    include_factions: bool = True,
) -> list[Projector]:
    init = initial_files or {}
    projectors: list[Projector] = [
        JournalProjector(initial_text=init.get("diario.md")),
        CharacterSheetProjector(initial_text=init.get("ficha.md")),
        NpcProjector(initial_text=init.get("npcs.md")),
        StateProjector(initial_text=init.get("estado.json")),
        QueueProjector(initial_text=init.get("queue.json")),
    ]
    if include_factions or "faccoes.md" in init:
        projectors.append(FactionProjector(initial_text=init.get("faccoes.md")))
    return projectors


def save_snapshot(campaign_dir: Path | str, last_seq: int, files: Mapping[str, str]) -> Path:
    camp_path = Path(campaign_dir)
    snap_dir = camp_path / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{last_seq:06d}.json"
    tmp_path = snap_dir / f".{last_seq:06d}.json.{os.getpid()}.tmp"
    payload = {"last_seq": int(last_seq), "files": dict(files)}
    with open(tmp_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(canonical_json(payload) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp_path, snap_path)
    return snap_path


def load_latest_snapshot(campaign_dir: Path | str, max_seq: int) -> dict[str, Any] | None:
    snap_dir = Path(campaign_dir) / "snapshots"
    if not snap_dir.exists():
        return None
    for snap_file in sorted(snap_dir.glob("*.json"), reverse=True):
        try:
            data = json.loads(snap_file.read_text(encoding="utf-8"))
            seq = int(data.get("last_seq", 0))
            files = data.get("files")
            if 0 < seq <= max_seq and isinstance(files, dict):
                return {"last_seq": seq, "files": {str(k): str(v) for k, v in files.items()}}
        except Exception:
            continue
    return None


def rebuild_projections(
    store: EventStore,
    campaign_id: str,
    campaign_dir: Path | str,
    snapshot: dict | None = None,
    engine: ProjectionEngine | None = None,
    emit_audit_event: bool = True,
    *,
    force: bool = False,
) -> tuple[int, str]:
    """Reconstrói projeções do zero ou de snapshot de forma byte-idêntica (Critério C3).
    
    O evento projection.rebuilt é emitido fora do cálculo e não afeta o hash verificado.
    """
    c_dir = Path(campaign_dir)
    current_last_seq = store.last_seq(campaign_id)
    after_seq = 0
    initial_files: dict[str, str] | None = None

    if snapshot is not None and not force:
        after_seq = int(snapshot.get("last_seq", 0))
        if isinstance(snapshot.get("files"), Mapping):
            initial_files = {str(k): str(v) for k, v in snapshot["files"].items()}
        elif after_seq > 0:
            disk_snap = load_latest_snapshot(c_dir, after_seq)
            if disk_snap and disk_snap["last_seq"] == after_seq:
                initial_files = disk_snap["files"]
            else:
                prefix_events = tuple(
                    e for e in store.read(campaign_id, after_seq=0) if e.seq <= after_seq
                )
                prefix_view = EventStreamView(campaign_id=campaign_id, events=prefix_events)
                prefix_engine = ProjectionEngine(default_projectors(), campaign_dir=c_dir)
                initial_files = prefix_engine.project(prefix_view)
    elif not force and current_last_seq > 0 and engine is None:
        disk_snap = load_latest_snapshot(c_dir, current_last_seq)
        if disk_snap is not None:
            after_seq = int(disk_snap["last_seq"])
            initial_files = disk_snap["files"]

    all_events = tuple(store.read(campaign_id, after_seq=after_seq))
    view = EventStreamView(campaign_id=campaign_id, events=all_events)

    proj_engine = engine or ProjectionEngine(
        default_projectors(initial_files), campaign_dir=c_dir
    )
    projections = proj_engine.project(view)
    proj_hash = proj_engine.write_projections_atomic(projections)

    effective_last_seq = view.last_seq if all_events else after_seq
    if effective_last_seq > 0 and (force or (effective_last_seq % SNAPSHOT_INTERVAL == 0)):
        save_snapshot(c_dir, effective_last_seq, projections)

    if emit_audit_event and all_events:
        audit_draft = EventDraft(
            type="projection.rebuilt",
            schema_version=1,
            actor=ActorRef("system", "rebuild_service"),
            payload={
                "from_seq": after_seq + 1 if all_events else 0,
                "to_seq": view.last_seq,
                "projection_version": 1,
                "hash": proj_hash,
            },
            game_time=all_events[-1].game_time,
            game_time_sort=all_events[-1].game_time_sort,
        )
        store.append(campaign_id, [audit_draft], expected_last_seq=view.last_seq)

    return effective_last_seq, proj_hash


__all__ = [
    "SNAPSHOT_INTERVAL",
    "default_projectors",
    "load_latest_snapshot",
    "rebuild_projections",
    "save_snapshot",
]
