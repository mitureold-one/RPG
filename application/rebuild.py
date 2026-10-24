"""application/rebuild.py: Serviço de reconstrução de projeções determinísticas (C3)."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

from application.projection_engine import ProjectionEngine
from application.projectors import (
    CharacterSheetProjector,
    JournalProjector,
    NpcProjector,
)
from contracts.event import ActorRef, EventDraft
from contracts.ports import EventStore, EventStreamView, Projector


def default_projectors() -> list[Projector]:
    return [
        JournalProjector(),
        CharacterSheetProjector(),
        NpcProjector(),
    ]


def rebuild_projections(
    store: EventStore,
    campaign_id: str,
    campaign_dir: Path | str,
    snapshot: dict | None = None,
    engine: ProjectionEngine | None = None,
    emit_audit_event: bool = True,
) -> tuple[int, str]:
    """Reconstrói projeções do zero ou de snapshot de forma byte-idêntica (Critério C3).
    
    O evento projection.rebuilt é emitido fora do cálculo e não afeta o hash verificado.
    """
    c_dir = Path(campaign_dir)
    after_seq = snapshot.get("last_seq", 0) if snapshot else 0

    all_events = tuple(store.read(campaign_id, after_seq=after_seq))
    view = EventStreamView(campaign_id=campaign_id, events=all_events)

    proj_engine = engine or ProjectionEngine(default_projectors(), campaign_dir=c_dir)
    projections = proj_engine.project(view)
    proj_hash = proj_engine.write_projections_atomic(projections)

    if emit_audit_event and all_events:
        # Gravação do evento de auditoria após verificação do hash (C3)
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
        store.append(campaign_id, [audit_draft])

    return view.last_seq, proj_hash


__all__ = ["default_projectors", "rebuild_projections"]
