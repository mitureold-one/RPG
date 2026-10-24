"""adapters/persistence/segment_io.py: Leitura, validação de hash e recuperação de segmentos JSONL."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from contracts.event import ActorRef, Event, EventDraft, EventType
from contracts.serialization import canonical_json, hash_batch
from kernel.errors import ReplayError, SchemaError
from kernel.event_catalog import upcast_payload


def compute_draft_batch_fp(batch: Sequence[EventDraft]) -> str:
    items = [
        {
            "type": d.type,
            "schema_version": d.schema_version,
            "actor": {"kind": d.actor.kind, "id": d.actor.id},
            "game_time": d.game_time,
            "game_time_sort": d.game_time_sort,
            "payload": dict(d.payload),
            "meta": {k: v for k, v in d.meta.items() if k != "dependencies"},
        }
        for d in batch
    ]
    return hashlib.sha256(canonical_json(items).encode("utf-8")).hexdigest()


def compute_events_batch_fp(events: Sequence[Event]) -> str:
    items = [
        {
            "type": e.type,
            "schema_version": e.schema_version,
            "actor": {"kind": e.actor.kind, "id": e.actor.id},
            "game_time": e.game_time,
            "game_time_sort": e.game_time_sort,
            "payload": dict(e.payload),
            "meta": {k: v for k, v in e.meta.items() if k != "dependencies"},
        }
        for e in events
    ]
    return hashlib.sha256(canonical_json(items).encode("utf-8")).hexdigest()


def record_to_raw_event(record: Mapping[str, Any]) -> Event:
    try:
        actor_data = record["actor"]
        actor = ActorRef(kind=actor_data["kind"], id=actor_data["id"])
        return Event(
            event_id=record["event_id"],
            campaign_id=record["campaign_id"],
            seq=int(record["seq"]),
            type=record["type"],
            schema_version=int(record["schema_version"]),
            recorded_at=record["recorded_at"],
            game_time=record.get("game_time"),
            game_time_sort=record.get("game_time_sort"),
            actor=actor,
            causation_id=record.get("causation_id"),
            correlation_id=record.get("correlation_id"),
            payload=record.get("payload", {}),
            meta=record.get("meta", {}),
        )
    except Exception as exc:
        raise ReplayError(f"Registro de evento malformado no segmento: {exc}") from exc


def apply_catalog_upcast(ev: Event, catalog: Mapping[str, EventType] | None) -> Event:
    if catalog is None or ev.type not in catalog:
        return ev
    target_type = catalog[ev.type]
    upcasted_payload = upcast_payload(target_type, ev.schema_version, ev.payload)
    if ev.schema_version == target_type.schema_version and upcasted_payload == dict(ev.payload):
        return ev
    return Event(
        event_id=ev.event_id,
        campaign_id=ev.campaign_id,
        seq=ev.seq,
        type=ev.type,
        schema_version=target_type.schema_version,
        recorded_at=ev.recorded_at,
        game_time=ev.game_time,
        game_time_sort=ev.game_time_sort,
        actor=ev.actor,
        causation_id=ev.causation_id,
        correlation_id=ev.correlation_id,
        payload=upcasted_payload,
        meta=ev.meta,
    )


def read_segment_events(
    seg: Path,
    catalog: Mapping[str, EventType] | None = None,
    *,
    verify_hash: bool = True,
) -> tuple[list[Event], set[str]]:
    """Lê apenas lotes committed de um segmento sem alterar o arquivo em disco."""
    if not seg.exists() or seg.stat().st_size == 0:
        return [], set()

    events_out: list[Event] = []
    batch_fps: set[str] = set()
    current_batch_open = False
    corrupted_in_open_batch = False
    pending_raw: list[Event] = []

    with open(seg, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except Exception as exc:
                if current_batch_open:
                    corrupted_in_open_batch = True
                break

            if not isinstance(record, dict):
                if current_batch_open:
                    corrupted_in_open_batch = True
                break

            rec_type = record.get("record")
            if rec_type == "batch":
                state = record.get("state")
                if state == "open":
                    current_batch_open = True
                    corrupted_in_open_batch = False
                    pending_raw = []
                elif state == "committed" and current_batch_open:
                    if corrupted_in_open_batch:
                        raise ReplayError(f"Lote committed contem linha corrompida em {seg.name}")
                    if verify_hash:
                        expected_hash = record.get("hash")
                        actual_hash = hash_batch(pending_raw)
                        if expected_hash != actual_hash:
                            raise ReplayError(
                                f"Divergencia de hash de lote em {seg.name}: esperado {expected_hash}, obtido {actual_hash}",
                                details={"segment": seg.name, "expected": expected_hash, "actual": actual_hash},
                            )
                    if pending_raw:
                        batch_fps.add(compute_events_batch_fp(pending_raw))
                        if record.get("batch_id"):
                            batch_fps.add(f"batch_id:{record['batch_id']}")
                        for pev in pending_raw:
                            if "batch_id" in pev.meta:
                                batch_fps.add(f"batch_id:{pev.meta['batch_id']}")
                            if "idempotency_key" in pev.meta:
                                batch_fps.add(f"idempotency_key:{pev.meta['idempotency_key']}")
                    for raw_ev in pending_raw:
                        events_out.append(apply_catalog_upcast(raw_ev, catalog))
                    current_batch_open = False
                    pending_raw = []
            elif rec_type == "event" and current_batch_open:
                try:
                    raw_ev = record_to_raw_event(record)
                    pending_raw.append(raw_ev)
                except (ReplayError, SchemaError):
                    corrupted_in_open_batch = True

    return events_out, batch_fps


def recover_segment_on_write(
    path: Path,
) -> tuple[int, int, set[str], dict[str, list[str]], set[str]]:
    """Recupera segmento truncando lotes incompletos sob CampaignLock (Critério C1)."""
    if not path.exists() or path.stat().st_size == 0:
        return 0, 0, set(), {}, set()

    last_committed_offset = 0
    last_seq = 0
    event_count = 0
    committed_event_ids: set[str] = set()
    committed_parents: dict[str, list[str]] = {}
    batch_fps: set[str] = set()

    current_batch_open = False
    current_batch_events: list[tuple[int, str, list[str], Event]] = []

    with open(path, "rb") as f:
        while True:
            raw_line = f.readline()
            if not raw_line:
                break
            line_str = raw_line.decode("utf-8", errors="replace").strip()
            if not line_str:
                continue
            try:
                record = json.loads(line_str)
            except Exception:
                break
            if not isinstance(record, dict):
                break

            rec_type = record.get("record")
            if rec_type == "batch":
                state = record.get("state")
                if state == "open":
                    current_batch_open = True
                    current_batch_events = []
                elif state == "committed" and current_batch_open:
                    raw_evs = [item[3] for item in current_batch_events]
                    expected_hash = record.get("hash")
                    if expected_hash and expected_hash != hash_batch(raw_evs):
                        raise ReplayError(
                            f"Divergencia de hash de lote em {path.name}",
                            details={"segment": path.name},
                        )
                    current_batch_open = False
                    last_committed_offset = f.tell()
                    if raw_evs:
                        batch_fps.add(compute_events_batch_fp(raw_evs))
                        if record.get("batch_id"):
                            batch_fps.add(f"batch_id:{record['batch_id']}")
                        for pev in raw_evs:
                            if "batch_id" in pev.meta:
                                batch_fps.add(f"batch_id:{pev.meta['batch_id']}")
                            if "idempotency_key" in pev.meta:
                                batch_fps.add(f"idempotency_key:{pev.meta['idempotency_key']}")
                    for s, eid, deps, _ in current_batch_events:
                        last_seq = s
                        event_count += 1
                        committed_event_ids.add(eid)
                        committed_parents[eid] = deps
                    current_batch_events = []
            elif rec_type == "event" and current_batch_open:
                try:
                    raw_ev = record_to_raw_event(record)
                    s = int(record["seq"])
                    eid = str(record["event_id"])
                    deps = list(record.get("meta", {}).get("dependencies", []))
                    current_batch_events.append((s, eid, deps, raw_ev))
                except Exception:
                    break

    current_size = path.stat().st_size
    if current_size > last_committed_offset:
        with open(path, "r+b") as f:
            f.seek(last_committed_offset)
            f.truncate()
            f.flush()
            os.fsync(f.fileno())

    return last_seq, event_count, committed_event_ids, committed_parents, batch_fps


__all__ = [
    "apply_catalog_upcast",
    "compute_draft_batch_fp",
    "compute_events_batch_fp",
    "read_segment_events",
    "recover_segment_on_write",
    "record_to_raw_event",
]
