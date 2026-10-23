"""Infraestrutura compartilhada dos testes de contrato.

O ``FakeEventStore`` é a especificação executável que o store JSONL do R1
precisa cumprir. O mixin ``EventStoreContract`` concentra os casos que não
dependem de detalhes internos da implementação.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any, Callable

from contracts.event import ActorRef, AppendResult, Event, EventDraft
from contracts.ports import EventStore
from kernel.errors import SeqConflictError
from kernel.ids import new_event_id

DEFAULT_GAME_TIME = "01 de Janeiro de 304, 00:00"


def make_draft(**overrides: Any) -> EventDraft:
    values: dict[str, Any] = {
        "type": "test.happened",
        "schema_version": 1,
        "actor": ActorRef("system", "kernel-tests"),
        "payload": {"value": 1},
        "game_time": DEFAULT_GAME_TIME,
        "game_time_sort": 0,
    }
    values.update(overrides)
    return EventDraft(**values)


def make_event(**overrides: Any) -> Event:
    values: dict[str, Any] = {
        "event_id": new_event_id(),
        "campaign_id": "camp",
        "seq": 1,
        "type": "test.happened",
        "schema_version": 1,
        "recorded_at": "2026-10-23T10:00:00Z",
        "game_time": DEFAULT_GAME_TIME,
        "game_time_sort": 0,
        "actor": ActorRef("system", "kernel-tests"),
        "causation_id": None,
        "correlation_id": None,
        "payload": {"value": 1},
        "meta": {},
    }
    values.update(overrides)
    return Event(**values)


class FakeEventStore:
    """Store em memória com a semântica de append do kernel."""

    def __init__(self, clock: Callable[[], datetime] | None = None) -> None:
        self._events: dict[str, list[Event]] = {}
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._fail_next_append = False

    def fail_next_append(self) -> None:
        """Faz o próximo lote falhar depois de montar parte dos eventos."""

        with self._lock:
            self._fail_next_append = True

    def append(
        self,
        campaign_id: str,
        drafts: "list[EventDraft] | tuple[EventDraft, ...]",
        expected_last_seq: int | None = None,
    ) -> AppendResult:
        if not isinstance(campaign_id, str) or not campaign_id.strip():
            raise ValueError("campaign_id deve ser texto não vazio")
        batch = tuple(drafts)
        with self._lock:
            current = self._current_seq(campaign_id)
            if expected_last_seq is not None and expected_last_seq != current:
                raise SeqConflictError(
                    f"expected_last_seq={expected_last_seq} não corresponde a {current}",
                    details={"expected": expected_last_seq, "actual": current},
                )
            if not batch:
                return AppendResult(events=(), first_seq=current, last_seq=current)

            events: list[Event] = []
            seq = current
            for index, draft in enumerate(batch):
                if not isinstance(draft, EventDraft):
                    raise TypeError("drafts deve conter apenas EventDraft")
                if self._fail_next_append and index == len(batch) - 1:
                    self._fail_next_append = False
                    raise RuntimeError("falha simulada no append")
                seq += 1
                events.append(
                    Event(
                        event_id=new_event_id(),
                        campaign_id=campaign_id,
                        seq=seq,
                        type=draft.type,
                        schema_version=draft.schema_version,
                        recorded_at=self._recorded_at(),
                        game_time=draft.game_time or DEFAULT_GAME_TIME,
                        game_time_sort=(
                            draft.game_time_sort if draft.game_time_sort is not None else 0
                        ),
                        actor=draft.actor,
                        causation_id=draft.causation_id,
                        correlation_id=draft.correlation_id,
                        payload=draft.payload,
                        meta=draft.meta,
                    )
                )

            self._events.setdefault(campaign_id, []).extend(events)
            return AppendResult(
                events=tuple(events),
                first_seq=events[0].seq,
                last_seq=events[-1].seq,
            )

    def read(self, campaign_id: str, after_seq: int = 0) -> tuple[Event, ...]:
        with self._lock:
            return tuple(
                event
                for event in self._events.get(campaign_id, ())
                if event.seq > after_seq
            )

    def last_seq(self, campaign_id: str) -> int:
        with self._lock:
            return self._current_seq(campaign_id)

    def _current_seq(self, campaign_id: str) -> int:
        events = self._events.get(campaign_id)
        return events[-1].seq if events else 0

    def _recorded_at(self) -> str:
        now = self._clock()
        if not isinstance(now, datetime) or now.tzinfo is None:
            raise ValueError("clock deve devolver datetime com timezone")
        return now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class EventStoreContract:
    """Casos obrigatórios para qualquer implementação de ``EventStore``."""

    def make_store(self) -> EventStore:
        raise NotImplementedError

    def test_append_assigns_identity_order_and_time(self) -> None:
        store = self.make_store()
        result = store.append("camp", [make_draft(payload={"n": 1}), make_draft(payload={"n": 2})])

        self.assertEqual([event.seq for event in result.events], [1, 2])
        self.assertEqual((result.first_seq, result.last_seq), (1, 2))
        self.assertEqual(store.last_seq("camp"), 2)
        self.assertEqual(len({event.event_id for event in result.events}), 2)

        for event in result.events:
            self.assertRegex(event.event_id, r"^evt_[0-9A-HJKMNP-TV-Z]{26}$")
            self.assertEqual(event.campaign_id, "camp")
            recorded = datetime.fromisoformat(event.recorded_at.replace("Z", "+00:00"))
            self.assertEqual(recorded.utcoffset().total_seconds(), 0)

    def test_expected_last_seq_matching_is_accepted(self) -> None:
        store = self.make_store()
        first = store.append("camp", [make_draft()], expected_last_seq=0)
        second = store.append("camp", [make_draft()], expected_last_seq=1)

        self.assertEqual(first.last_seq, 1)
        self.assertEqual(second.last_seq, 2)

    def test_divergent_expected_last_seq_raises_without_writing(self) -> None:
        store = self.make_store()
        store.append("camp", [make_draft()], expected_last_seq=0)

        with self.assertRaises(SeqConflictError) as caught:
            store.append("camp", [make_draft(), make_draft()], expected_last_seq=0)

        self.assertEqual(caught.exception.code, "SEQ_CONFLICT")
        self.assertEqual(caught.exception.details.get("actual"), 1)
        self.assertEqual(store.last_seq("camp"), 1)
        self.assertEqual([event.seq for event in store.read("camp")], [1])

        # O conflito não consome sequência.
        after = store.append("camp", [make_draft()])
        self.assertEqual(after.events[0].seq, 2)

    def test_empty_batch_does_not_create_events_or_advance(self) -> None:
        store = self.make_store()
        empty = store.append("camp", [])

        self.assertEqual(empty.events, ())
        self.assertEqual((empty.first_seq, empty.last_seq), (0, 0))
        self.assertEqual(store.last_seq("camp"), 0)
        self.assertEqual(tuple(store.read("camp")), ())

        store.append("camp", [make_draft()])
        empty_after = store.append("camp", [], expected_last_seq=1)
        self.assertEqual((empty_after.first_seq, empty_after.last_seq), (1, 1))
        self.assertEqual(store.last_seq("camp"), 1)

    def test_read_after_seq_returns_later_events_in_order(self) -> None:
        store = self.make_store()
        store.append("camp", [make_draft(payload={"n": 1}), make_draft(payload={"n": 2}), make_draft(payload={"n": 3})])

        self.assertEqual([event.seq for event in store.read("camp", after_seq=1)], [2, 3])
        self.assertEqual([event.seq for event in store.read("camp", after_seq=3)], [])
        self.assertEqual(tuple(store.read("outra")), ())

    def test_campaigns_have_independent_sequences(self) -> None:
        store = self.make_store()
        first = store.append("a", [make_draft()])
        second = store.append("b", [make_draft()])

        self.assertEqual(first.events[0].seq, 1)
        self.assertEqual(second.events[0].seq, 1)

    def test_store_conforms_to_event_store_protocol(self) -> None:
        self.assertIsInstance(self.make_store(), EventStore)
