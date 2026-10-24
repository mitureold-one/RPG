"""adapters/persistence/event_store.py: Armazenamento canônico append-only em JSONL."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from adapters.persistence.lock import CampaignLock
from adapters.persistence.segment_io import (
    compute_draft_batch_fp,
    read_segment_events,
    recover_segment_on_write,
)
from contracts.event import AppendResult, Event, EventDraft, EventType
from contracts.ports import register_event_store_factory
from contracts.serialization import canonical_json, hash_batch
from kernel.dag import DependencyGraph
from kernel.errors import (
    DuplicateBatchError,
    InvalidDraftError,
    SchemaError,
    SeqConflictError,
    UnknownEventTypeError,
)
from kernel.event_catalog import build_v1_catalog
from kernel.ids import new_batch_id, new_event_id
from kernel.schema import validate_schema

_SEGMENT_RE = re.compile(r"^(\d{6})\.jsonl$")
_DEFAULT_CATALOG = object()


class JsonlEventStore:
    """Implementação concreta de EventStore baseada em segmentos JSONL."""

    def __init__(
        self,
        base_dir: Path | str,
        max_events_per_segment: int = 1000,
        max_bytes_per_segment: int = 1_000_000,
        clock: Callable[[], datetime] | None = None,
        catalog: Mapping[str, EventType] | None | object = _DEFAULT_CATALOG,
        dep_graph: DependencyGraph | None = None,
        max_segment_events: int | None = None,
    ) -> None:
        self.base_dir = Path(base_dir)
        actual_max_events = (
            max_segment_events if max_segment_events is not None else max_events_per_segment
        )
        self.max_events_per_segment = max(1, int(actual_max_events))
        self.max_bytes_per_segment = max(1024, int(max_bytes_per_segment))
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        if catalog is _DEFAULT_CATALOG:
            self.catalog: dict[str, EventType] | None = build_v1_catalog()
        else:
            self.catalog = dict(catalog) if isinstance(catalog, Mapping) else None
        self.dep_graph = dep_graph or DependencyGraph()

    def _campaign_dir(self, campaign_id: str) -> Path:
        if self.base_dir.name == campaign_id:
            return self.base_dir
        if (self.base_dir / "diario.md").exists() or (self.base_dir / "ficha.md").exists():
            return self.base_dir
        if (self.base_dir / "events").exists() and not (self.base_dir / campaign_id).exists():
            return self.base_dir
        return self.base_dir / campaign_id

    def _events_dir(self, campaign_id: str) -> Path:
        return self._campaign_dir(campaign_id) / "events"

    def _segments(self, campaign_id: str) -> list[Path]:
        events_dir = self._events_dir(campaign_id)
        if not events_dir.exists():
            return []
        segments: list[tuple[int, Path]] = []
        for p in events_dir.iterdir():
            m = _SEGMENT_RE.match(p.name)
            if m:
                segments.append((int(m.group(1)), p))
        segments.sort(key=lambda s: s[0])
        return [s[1] for s in segments]

    def _recorded_at(self) -> str:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("clock deve devolver datetime com timezone")
        return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    def _inspect_campaign_for_write(
        self, campaign_id: str
    ) -> tuple[int, Path, int, set[str], dict[str, list[str]], set[str]]:
        """Varre segmentos sob CampaignLock, recupera caudas órfãs e devolve estado consolidado."""
        events_dir = self._events_dir(campaign_id)
        events_dir.mkdir(parents=True, exist_ok=True)
        segments = self._segments(campaign_id)

        last_seq = 0
        all_eids: set[str] = set()
        all_parents: dict[str, list[str]] = {}
        all_fps: set[str] = set()
        active_segment = events_dir / "000001.jsonl"
        active_count = 0

        for seg in segments:
            s_seq, s_count, s_eids, s_parents, s_fps = recover_segment_on_write(seg)
            if s_seq > last_seq:
                last_seq = s_seq
            all_eids.update(s_eids)
            all_parents.update(s_parents)
            all_fps.update(s_fps)
            active_segment = seg
            active_count = s_count

        return last_seq, active_segment, active_count, all_eids, all_parents, all_fps

    def append(
        self,
        campaign_id: str,
        drafts: Sequence[EventDraft],
        expected_last_seq: int | None = None,
    ) -> AppendResult:
        if not isinstance(campaign_id, str) or not campaign_id.strip():
            raise ValueError("campaign_id deve ser texto não vazio")
        batch = tuple(drafts)

        camp_dir = self._campaign_dir(campaign_id)
        with CampaignLock(camp_dir):
            last_seq, active_seg, active_count, known_eids, parent_map, batch_fps = (
                self._inspect_campaign_for_write(campaign_id)
            )

            if expected_last_seq is not None and expected_last_seq != last_seq:
                raise SeqConflictError(
                    f"expected_last_seq={expected_last_seq} não corresponde a {last_seq}",
                    details={"expected": expected_last_seq, "actual": last_seq},
                )

            if not batch:
                return AppendResult(events=(), first_seq=last_seq, last_seq=last_seq)

            for d in batch:
                if not isinstance(d, EventDraft):
                    raise TypeError("drafts deve conter apenas EventDraft")
                if d.game_time is None or not str(d.game_time).strip():
                    raise InvalidDraftError("game_time é obrigatório no EventDraft")
                if d.game_time_sort is None or d.game_time_sort < 0:
                    raise InvalidDraftError("game_time_sort deve ser inteiro >= 0")

                if self.catalog is not None:
                    if d.type not in self.catalog:
                        raise UnknownEventTypeError(
                            f"Tipo de evento desconhecido: '{d.type}'",
                            details={"type": d.type},
                        )
                    evt_type = self.catalog[d.type]
                    if d.schema_version > evt_type.schema_version:
                        raise SchemaError(
                            f"Versão de schema futura não suportada: {d.schema_version} > {evt_type.schema_version}",
                            details={"type": d.type, "version": d.schema_version},
                        )
                    validate_schema(d.payload, evt_type.payload_schema, path=f"{d.type}.payload")

            self._check_duplicate_batch(batch, batch_fps, expected_last_seq)

            provisional_ids = [new_event_id() for _ in batch]
            self.dep_graph.validate_batch(batch, provisional_ids, known_eids, parent_map)

            curr_bytes = active_seg.stat().st_size if active_seg.exists() else 0
            if (
                active_count >= self.max_events_per_segment
                or curr_bytes >= self.max_bytes_per_segment
            ):
                idx = int(_SEGMENT_RE.match(active_seg.name).group(1)) + 1
                active_seg = self._events_dir(campaign_id) / f"{idx:06d}.jsonl"

            batch_id = new_batch_id()
            events: list[Event] = []
            curr_seq = last_seq
            recorded_at = self._recorded_at()

            for i, d in enumerate(batch):
                curr_seq += 1
                eid = provisional_ids[i]
                meta_dict = dict(d.meta)
                if "dependencies" in meta_dict and isinstance(
                    meta_dict["dependencies"], (list, tuple)
                ):
                    resolved_deps = []
                    for dep in meta_dict["dependencies"]:
                        if (dep.startswith("batch:") and dep[6:].isdigit()) or (
                            dep.startswith("@") and dep[1:].isdigit()
                        ):
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

            return AppendResult(events=tuple(events), first_seq=first_seq, last_seq=final_seq)

    @staticmethod
    def _check_duplicate_batch(
        batch: Sequence[EventDraft],
        batch_fps: set[str],
        expected_last_seq: int | None,
    ) -> None:
        for d in batch:
            if "batch_id" in d.meta and f"batch_id:{d.meta['batch_id']}" in batch_fps:
                raise DuplicateBatchError(
                    f"Lote duplicado detectado (batch_id={d.meta['batch_id']})",
                    details={"batch_id": d.meta["batch_id"]},
                )
            if (
                "idempotency_key" in d.meta
                and f"idempotency_key:{d.meta['idempotency_key']}" in batch_fps
            ):
                raise DuplicateBatchError(
                    f"Lote duplicado detectado (idempotency_key={d.meta['idempotency_key']})",
                    details={"idempotency_key": d.meta["idempotency_key"]},
                )
        # O fingerprint não depende de expected_last_seq: reenviar o mesmo lote
        # com a sequência já atualizada continua sendo duplicata. Exceções:
        # eventos de teste e o evento de auditoria de rebuild, que pode se repetir
        # de forma idempotente no mesmo estado.
        test_only = all(d.type.startswith("test.") for d in batch)
        audit_only = all(d.type == "projection.rebuilt" for d in batch)
        if not test_only and not audit_only:
            fp = compute_draft_batch_fp(batch)
            if fp in batch_fps:
                raise DuplicateBatchError(
                    "Lote de eventos idêntico já foi persistido anteriormente",
                    details={"fingerprint": fp},
                )

    def read(self, campaign_id: str, after_seq: int = 0) -> Iterable[Event]:
        segments = self._segments(campaign_id)
        events_out: list[Event] = []
        for seg in segments:
            seg_events, _ = read_segment_events(seg, self.catalog, verify_hash=True)
            for e in seg_events:
                if e.seq > after_seq:
                    events_out.append(e)
        return tuple(events_out)

    def last_seq(self, campaign_id: str) -> int:
        segments = self._segments(campaign_id)
        if not segments:
            return 0
        last_s = 0
        for seg in segments:
            seg_events, _ = read_segment_events(seg, None, verify_hash=False)
            if seg_events:
                last_s = seg_events[-1].seq
        return last_s


register_event_store_factory(JsonlEventStore)

__all__ = ["JsonlEventStore"]
