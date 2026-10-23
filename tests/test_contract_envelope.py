"""Contratos do envelope: validação, normalização e resultado de append."""

from __future__ import annotations

import unittest

from contracts.event import ActorRef, AppendResult, EventDraft, EventType
from contracts.serialization import canonical_json
from contract_support import make_draft, make_event
from kernel.ids import new_event_id


class EventDraftContractTests(unittest.TestCase):
    def test_payload_is_copied_and_normalized(self) -> None:
        source = {"nested": {"items": (1, 2)}, "ok": True}
        draft = make_draft(payload=source)
        source["nested"]["items"] = []

        self.assertEqual(draft.payload, {"nested": {"items": [1, 2]}, "ok": True})

    def test_meta_is_copied(self) -> None:
        meta = {"seed": 7}
        draft = make_draft(meta=meta)
        meta["seed"] = 8
        self.assertEqual(draft.meta, {"seed": 7})

    def test_payload_must_be_object(self) -> None:
        with self.assertRaises(ValueError):
            make_draft(payload=[])

    def test_payload_rejects_non_string_keys(self) -> None:
        with self.assertRaises(ValueError):
            make_draft(payload={1: "x"})

    def test_payload_rejects_non_json_value(self) -> None:
        with self.assertRaises(ValueError):
            make_draft(payload={"bad": {1, 2}})

    def test_payload_rejects_non_finite_float(self) -> None:
        with self.assertRaises(ValueError):
            make_draft(payload={"bad": float("nan")})

    def test_type_and_schema_version_are_required(self) -> None:
        with self.assertRaises(ValueError):
            make_draft(type="")
        with self.assertRaises(ValueError):
            make_draft(schema_version=0)
        with self.assertRaises(ValueError):
            make_draft(schema_version=True)

    def test_game_time_sort_must_be_non_negative(self) -> None:
        with self.assertRaises(ValueError):
            make_draft(game_time_sort=-1)

    def test_actor_kind_is_validated(self) -> None:
        with self.assertRaises(ValueError):
            ActorRef("deity", "x")
        with self.assertRaises(ValueError):
            ActorRef("system", "")

    def test_optional_fields_may_be_absent(self) -> None:
        draft = make_draft(game_time=None, game_time_sort=None)
        self.assertIsNone(draft.game_time)
        self.assertIsNone(draft.game_time_sort)


class EventContractTests(unittest.TestCase):
    def test_event_id_format(self) -> None:
        make_event(event_id=new_event_id())
        for invalid in ("evt_" + "0" * 25, "evt_" + "I" * 26, "uuid-123", "evt_" + "U" * 26):
            with self.assertRaises(ValueError):
                make_event(event_id=invalid)

    def test_seq_starts_at_one(self) -> None:
        with self.assertRaises(ValueError):
            make_event(seq=0)

    def test_recorded_at_must_be_utc(self) -> None:
        make_event(recorded_at="2026-10-23T10:00:00Z")
        make_event(recorded_at="2026-10-23T10:00:00+00:00")
        for invalid in ("2026-10-23T10:00:00", "2026-10-23T10:00:00+03:00", "ontem"):
            with self.assertRaises(ValueError):
                make_event(recorded_at=invalid)

    def test_payload_is_normalized_on_event(self) -> None:
        event = make_event(payload={"b": (1, 2), "a": {"z": None}})
        self.assertEqual(event.payload, {"b": [1, 2], "a": {"z": None}})

    def test_canonical_json_is_stable(self) -> None:
        self.assertEqual(
            canonical_json({"b": 1, "a": {"d": 2, "c": 3}}),
            '{"a":{"c":3,"d":2},"b":1}',
        )


class AppendResultContractTests(unittest.TestCase):
    def test_empty_result_requires_unchanged_sequence(self) -> None:
        AppendResult(events=(), first_seq=0, last_seq=0)
        with self.assertRaises(ValueError):
            AppendResult(events=(), first_seq=1, last_seq=0)

    def test_result_requires_contiguous_sequence(self) -> None:
        first = make_event(seq=1)
        third = make_event(seq=3)
        with self.assertRaises(ValueError):
            AppendResult(events=(first, third), first_seq=1, last_seq=3)

    def test_result_rejects_mixed_campaigns(self) -> None:
        first = make_event(seq=1, campaign_id="a")
        second = make_event(seq=2, campaign_id="b")
        with self.assertRaises(ValueError):
            AppendResult(events=(first, second), first_seq=1, last_seq=2)

    def test_result_rejects_wrong_bounds(self) -> None:
        first = make_event(seq=1)
        with self.assertRaises(ValueError):
            AppendResult(events=(first,), first_seq=2, last_seq=1)


class EventTypeContractTests(unittest.TestCase):
    def test_upcasters_must_be_callable(self) -> None:
        with self.assertRaises(ValueError):
            EventType(type="x", schema_version=2, payload_schema={}, upcasters={1: "nope"})

    def test_valid_upcaster_is_kept(self) -> None:
        upcaster = lambda payload: payload  # noqa: E731
        event_type = EventType(
            type="x", schema_version=2, payload_schema={"type": "object"}, upcasters={1: upcaster}
        )
        self.assertIs(event_type.upcasters[1], upcaster)


if __name__ == "__main__":
    unittest.main()
