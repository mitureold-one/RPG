"""adapters/persistence/event_store.py: Armazenamento canônico append-only em JSONL."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Mapping, Sequence

from adapters.persistence.batch_io import (
    check_duplicate_batch,
    materialize_and_write_batch,
    validate_draft_batch,
)
from adapters.persistence.lock import CampaignLock
from adapters.persistence.segment_io import (
    read_segment_events,
    recover_segment_on_write,
)
from contracts.event import AppendResult, Event, EventDraft, EventType
from contracts.ports import register_event_store_factory
from kernel.dag import DependencyGraph
from kernel.errors import SeqConflictError
from kernel.event_catalog import build_v1_catalog
from kernel.ids import new_event_id

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

            validate_draft_batch(batch, self.catalog, batch_fps, expected_last_seq)

            provisional_ids = [new_event_id() for _ in batch]
            self.dep_graph.validate_batch(batch, provisional_ids, known_eids, parent_map)

            curr_bytes = active_seg.stat().st_size if active_seg.exists() else 0
            if (
                active_count >= self.max_events_per_segment
                or curr_bytes >= self.max_bytes_per_segment
            ):
                idx = int(_SEGMENT_RE.match(active_seg.name).group(1)) + 1
                active_seg = self._events_dir(campaign_id) / f"{idx:06d}.jsonl"

            events, first_seq, final_seq = materialize_and_write_batch(
                active_seg=active_seg,
                campaign_id=campaign_id,
                batch=batch,
                provisional_ids=provisional_ids,
                last_seq=last_seq,
                recorded_at=self._recorded_at(),
            )
            return AppendResult(events=tuple(events), first_seq=first_seq, last_seq=final_seq)

    _check_duplicate_batch = staticmethod(check_duplicate_batch)

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
