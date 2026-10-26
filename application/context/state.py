"""Implementação de ContextStateView para leitura e validação do cache estado.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from contracts.ports import ContextStateView, EventStore
from council import parse_diario_md


class PrepareError(RuntimeError):
    """Erro explícito levantado em caso de falha irrecuperável na preparação de contexto."""


class ContextStateViewImpl:
    """Visão imutável de estado derivada de estado.json com auto-cura de staleness."""

    def __init__(
        self,
        last_seq: int,
        stale: bool,
        npcs: Mapping[str, Any],
        factions: Mapping[str, Any],
        knowledge: Sequence[Any],
        recent_events: Sequence[Any],
        quests: Sequence[Any] = (),
        clocks: Sequence[Any] = (),
        arc: Mapping[str, Any] | None = None,
        registered_claims: Sequence[str] = (),
    ) -> None:
        self.last_seq = int(last_seq)
        self.stale = bool(stale)
        self._npcs = dict(npcs)
        self._factions = dict(factions)
        self._knowledge = tuple(knowledge)
        self._recent_events = tuple(recent_events)
        self._quests = tuple(quests)
        self._clocks = tuple(clocks)
        self._arc = dict(arc or {})
        self._registered_claims = tuple(registered_claims)

    def npcs(self) -> Mapping[str, Any]:
        return self._npcs

    def factions(self) -> Mapping[str, Any]:
        return self._factions

    def knowledge(self) -> Sequence[Any]:
        return self._knowledge

    def registered_claims(self) -> Sequence[str]:
        return self._registered_claims

    def recent_events(self, limit: int = 50) -> Sequence[Any]:
        return self._recent_events[-limit:]

    def quests(self) -> Sequence[Any]:
        return self._quests

    def clocks(self) -> Sequence[Any]:
        return self._clocks

    def arc(self) -> Mapping[str, Any]:
        return self._arc

    @classmethod
    def load(
        cls,
        campaign_id: str,
        campaign_dir: Path | str,
        store: EventStore | None = None,
        diario_data: Mapping[str, Any] | None = None,
    ) -> ContextStateView:
        """Carrega estado.json, detecta staleness contra o store e reconstrói se necessário."""
        c_dir = Path(campaign_dir)
        state_file = c_dir / "estado.json"
        if not state_file.exists():
            state_file = c_dir / "projections" / "estado.json"

        expected_seq = store.last_seq(campaign_id) if store is not None else None
        stale = False
        data: dict[str, Any] | None = None

        if state_file.exists():
            try:
                parsed = json.loads(state_file.read_text(encoding="utf-8"))
                if isinstance(parsed, dict) and int(parsed.get("schema_version", 0)) == 1:
                    data = parsed
            except (json.JSONDecodeError, OSError):
                data = None

        cached_seq = data.get("last_seq", -1) if isinstance(data, dict) else -1
        is_divergent = False
        if expected_seq is not None:
            if cached_seq != expected_seq:
                is_divergent = True
                if store is not None and 0 <= cached_seq < expected_seq:
                    try:
                        tail_events = list(store.read(campaign_id, after_seq=cached_seq))
                        if tail_events and all(e.type.startswith("projection.") for e in tail_events):
                            is_divergent = False
                    except Exception:
                        is_divergent = True

        if data is None or is_divergent:
            stale = True
            if store is not None and expected_seq is not None and expected_seq > 0:
                from application.rebuild import rebuild_projections

                try:
                    rebuild_projections(store, campaign_id, c_dir, emit_audit_event=False)
                except Exception as exc:
                    raise PrepareError(
                        f"Falha ao reconstruir cache para campanha '{campaign_id}': {exc}"
                    ) from exc

                state_file = c_dir / "estado.json"
                if not state_file.exists():
                    state_file = c_dir / "projections" / "estado.json"

                if not state_file.exists():
                    raise PrepareError(
                        f"estado.json não foi gerado após reconstrução da campanha '{campaign_id}'"
                    )

                try:
                    data = json.loads(state_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    raise PrepareError(
                        f"estado.json corrompido após reconstrução da campanha '{campaign_id}': {exc}"
                    ) from exc
            elif expected_seq and expected_seq > 0:
                raise PrepareError(
                    f"Cache estado.json ausente para campanha '{campaign_id}' e nenhum store fornecido"
                )
            else:
                data = {
                    "schema_version": 1,
                    "last_seq": 0,
                    "npcs": [],
                    "factions": [],
                    "knowledge": [],
                    "recent_events": [],
                }

        if not isinstance(data, dict):
            raise PrepareError(f"Formato inválido de estado.json para campanha '{campaign_id}'")

        last_seq = expected_seq if (not is_divergent and expected_seq is not None) else data.get("last_seq", 0)

        # Mapeia NPCs por id
        npcs_raw = data.get("npcs", [])
        npcs_map: dict[str, Any] = {}
        if isinstance(npcs_raw, list):
            for n in npcs_raw:
                if isinstance(n, dict):
                    nid = n.get("id") or n.get("name")
                    if nid:
                        npcs_map[str(nid)] = n
        elif isinstance(npcs_raw, dict):
            npcs_map = npcs_raw

        # Mapeia facções por tag
        factions_raw = data.get("factions", [])
        factions_map: dict[str, Any] = {}
        if isinstance(factions_raw, list):
            for f in factions_raw:
                if isinstance(f, dict):
                    tag = f.get("tag") or f.get("name")
                    if tag:
                        factions_map[str(tag)] = f
        elif isinstance(factions_raw, dict):
            factions_map = factions_raw

        knowledge_raw = data.get("knowledge", [])
        recent_raw = data.get("recent_events", [])
        registered_raw = data.get("registered_claims", [])

        # Extrai quests, clocks e arc do diário
        diario = dict(diario_data or {})
        if not diario:
            diario_path = c_dir / "diario.md"
            if diario_path.exists():
                try:
                    diario = parse_diario_md(diario_path)
                except Exception:
                    diario = {}

        quests = diario.get("active_quests", [])
        if not quests and c_dir:
            diario_path = c_dir / "diario.md"
            if diario_path.exists():
                try:
                    from council import parse_quests_from_diario
                    quests = parse_quests_from_diario(diario_path)
                except Exception:
                    pass
        clocks = diario.get("clocks", [])
        arc = diario.get("plot_plan", {})

        return cls(
            last_seq=last_seq,
            stale=stale,
            npcs=npcs_map,
            factions=factions_map,
            knowledge=knowledge_raw,
            recent_events=recent_raw,
            quests=quests,
            clocks=clocks,
            arc=arc,
            registered_claims=registered_raw,
        )


__all__ = ["ContextStateViewImpl", "PrepareError"]
