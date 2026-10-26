"""adapters/persistence/batch_io.py: Validação de rascunhos e escrita atômica de lotes JSONL."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping, Sequence

from adapters.persistence.segment_io import compute_draft_batch_fp
from contracts.event import Event, EventDraft, EventType
from contracts.serialization import canonical_json, hash_batch
from kernel.errors import (
    DuplicateBatchError,
    InvalidDraftError,
    SchemaError,
    UnknownEventTypeError,
)
from kernel.ids import new_batch_id
from kernel.schema import validate_schema


def check_duplicate_batch(
    batch: Sequence[EventDraft],
    batch_fps: set[str],
    expected_last_seq: int | None = None,
) -> None:
    for d in batch:
        if "batch_id" in d.meta and f"batch_id:{d.meta['batch_id']}" in batch_fps:
            raise DuplicateBatchError(
                f"Lote duplicado detectado (batch_id={d.meta['batch_id']})",
                details={"batch_id": d.meta["batch_id"]},
            )
        if "idempotency_key" in d.meta and f"idempotency_key:{d.meta['idempotency_key']}" in batch_fps:
            raise DuplicateBatchError(
                f"Lote duplicado detectado (idempotency_key={d.meta['idempotency_key']})",
                details={"idempotency_key": d.meta["idempotency_key"]},
            )
    test_only = all(d.type.startswith("test.") for d in batch)
    audit_only = all(d.type == "projection.rebuilt" for d in batch)
    if not test_only and not audit_only:
        fp = compute_draft_batch_fp(batch)
        if fp in batch_fps:
            raise DuplicateBatchError(
                "Lote de eventos idêntico já foi persistido anteriormente",
                details={"fingerprint": fp},
            )


def validate_draft_batch(
    batch: Sequence[EventDraft],
    catalog: Mapping[str, EventType] | None,
    batch_fps: set[str],
    expected_last_seq: int | None = None,
) -> None:
    for d in batch:
        if not isinstance(d, EventDraft):
            raise TypeError("drafts deve conter apenas EventDraft")
        if d.game_time is None or not str(d.game_time).strip():
            raise InvalidDraftError("game_time é obrigatório no EventDraft")
        if d.game_time_sort is None or d.game_time_sort < 0:
            raise InvalidDraftError("game_time_sort deve ser inteiro >= 0")

        if catalog is not None:
            if d.type not in catalog:
                raise UnknownEventTypeError(
                    f"Tipo de evento desconhecido: '{d.type}'",
                    details={"type": d.type},
                )
            evt_type = catalog[d.type]
            if d.schema_version > evt_type.schema_version:
                raise SchemaError(
                    f"Versão de schema futura não suportada: {d.schema_version} > {evt_type.schema_version}",
                    details={"type": d.type, "version": d.schema_version},
                )
            validate_schema(d.payload, evt_type.payload_schema, path=f"{d.type}.payload")

    check_duplicate_batch(batch, batch_fps, expected_last_seq)


def materialize_and_write_batch(
    *,
    active_seg: Path,
    campaign_id: str,
    batch: Sequence[EventDraft],
    provisional_ids: Sequence[str],
    last_seq: int,
    recorded_at: str,
) -> tuple[list[Event], int, int]:
    batch_id = new_batch_id()
    events: list[Event] = []
    curr_seq = last_seq

    for i, d in enumerate(batch):
        curr_seq += 1
        eid = provisional_ids[i]
        meta_dict = dict(d.meta)
        if "dependencies" in meta_dict and isinstance(meta_dict["dependencies"], (list, tuple)):
            resolved_deps = []
            for dep in meta_dict["dependencies"]:
                if (dep.startswith("batch:") and dep[6:].isdigit()) or (dep.startswith("@") and dep[1:].isdigit()):
                    k = int(dep[6:] if dep.startswith("batch:") else dep[1:])
                    resolved_deps.append(provisional_ids[k])
                else:
                    resolved_deps.append(dep)
            meta_dict["dependencies"] = resolved_deps
        events.append(
            Event(
                event_id=eid,
                campaign_id=campaign_id,
                seq=curr_seq,
                type=d.type,
                schema_version=d.schema_version,
                recorded_at=recorded_at,
                game_time=d.game_time,
                game_time_sort=d.game_time_sort,
                actor=d.actor,
                causation_id=d.causation_id,
                correlation_id=d.correlation_id,
                payload=d.payload,
                meta=meta_dict,
            )
        )

    batch_hash = hash_batch(events)
    first_seq = events[0].seq
    final_seq = events[-1].seq

    open_marker = {
        "record": "batch",
        "state": "open",
        "batch_id": batch_id,
        "first_seq": first_seq,
        "event_count": len(events),
    }
    committed_marker = {
        "record": "batch",
        "state": "committed",
        "batch_id": batch_id,
        "last_seq": final_seq,
        "hash": batch_hash,
    }

    with open(active_seg, "a", encoding="utf-8", newline="\n") as f:
        f.write(canonical_json(open_marker) + "\n")
        for e in events:
            e_dict = {
                "record": "event",
                "event_id": e.event_id,
                "campaign_id": e.campaign_id,
                "seq": e.seq,
                "type": e.type,
                "schema_version": e.schema_version,
                "recorded_at": e.recorded_at,
                "game_time": e.game_time,
                "game_time_sort": e.game_time_sort,
                "actor": {"id": e.actor.id, "kind": e.actor.kind},
                "causation_id": e.causation_id,
                "correlation_id": e.correlation_id,
                "payload": dict(e.payload),
                "meta": dict(e.meta),
            }
            f.write(canonical_json(e_dict) + "\n")
        f.write(canonical_json(committed_marker) + "\n")
        f.flush()
        os.fsync(f.fileno())

    return events, first_seq, final_seq


__all__ = ["check_duplicate_batch", "materialize_and_write_batch", "validate_draft_batch"]
