# Interface Contracts: 012 — Fase 03: Agentes, Conhecimento Epistêmico e Refatoração R2

**Feature:** `phase-03-agents`  
**Status:** Ready for Implementation  
**Created:** 2026-10-26  
**Context:** Contratos formais de portas (`contracts/ports.py`), resolvedor de verdade, `KnowledgeView`, validador de admissão de propostas e serviços de recursos (`resources/npcs`, `resources/factions`, `resources/quests`, `resources/knowledge`).

---

## 1. Novas Portas de Extensão (`contracts/ports.py`)

```python
@dataclass(frozen=True)
class Intent:
    """Proposta de ação, plano, objetivo ou revisão epistêmica de um agente."""
    actor_kind: str                # "npc" | "faction" | "subgroup"
    actor_id: str
    intent_kind: str               # "action" | "plan_step" | "goal_update" | "share_knowledge" | "conspire"
    description: str
    target_id: str | None = None
    required_claims: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    required_resources: Mapping[str, int] = field(default_factory=dict)
    location: str | None = None
    acts_for_faction: str | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ReactionContext:
    """Visão imutável entregue a uma BehaviorPolicy."""
    campaign_id: str
    game_time: str
    game_time_sort: int
    npc_state: Any                 # NpcState imutável
    knowledge_view: Any            # KnowledgeView filtrada para o NPC
    present_actors: tuple[str, ...] = ()
    seed: int = 0


@dataclass(frozen=True)
class FactionContext:
    """Visão imutável entregue a uma FactionPolicy."""
    campaign_id: str
    game_time: str
    game_time_sort: int
    faction_state: Any             # FactionState imutável
    knowledge_view: Any            # KnowledgeView filtrada para a facção/subgrupo
    active_clocks: tuple[dict[str, Any], ...] = ()
    seed: int = 0


@runtime_checkable
class BehaviorPolicy(Protocol):
    """Porta para políticas determinísticas de comportamento de NPC."""
    name: str
    version: str

    def propose(self, ctx: ReactionContext) -> tuple[Intent, ...]:
        ...


@runtime_checkable
class FactionPolicy(Protocol):
    """Porta para políticas determinísticas de facção e subgrupos."""
    name: str
    version: str

    def propose(self, ctx: FactionContext) -> tuple[Intent, ...]:
        ...


@runtime_checkable
class KnowledgeProvider(Protocol):
    """Porta para consulta de conhecimento/crença e construção de KnowledgeView."""
    name: str

    def build_view(
        self,
        events: Sequence[Event],
        holder_kind: str,
        holder_id: str,
        audience_kind: str = "self",
        audience_id: str = "",
        purpose: str = "decision",
    ) -> Any:
        ...
```

---

## 2. Contrato do Resolvedor de Verdade e `KnowledgeView` (`resources/knowledge/`)

### 2.1 `resolve_claim` (`resources/knowledge/resolver.py`)
```python
TruthValue = Literal["TRUE", "FALSE", "UNKNOWN", "INDETERMINATE"]

def resolve_claim(
    claim: Claim,
    at_time_sort: int,
    events: Sequence[Event],
    projected_state: Mapping[str, Any] | None = None,
) -> TruthValue:
    """Resolve deterministicamente o valor de verdade de uma alegação no motor (G3-D10).
    
    Regras:
    1. claim_type == 'normative' -> 'INDETERMINATE'.
    2. claim_type == 'counterfactual' -> 'INDETERMINATE'.
    3. claim_type == 'prediction' -> 'UNKNOWN' (a menos que valid_to <= at_time_sort e source_event_id confirmado).
    4. claim_type == 'occurrence':
       - verifica eventos com game_time_sort <= at_time_sort;
       - se source_event_id foi corrigido/anulado por correction.issued, retorna 'FALSE';
       - se o evento canônico existe e confere com proposition, retorna 'TRUE';
       - se há evento canônico que contradiz diretamente o predicado, retorna 'FALSE';
       - caso contrário, retorna 'UNKNOWN'.
    5. claim_type == 'state':
       - avalia fact_ref/proposition contra o estado canônico em at_time_sort;
       - respeita janela [valid_from, valid_to] se declarada.
    """
```

### 2.2 `KnowledgeView` (`resources/knowledge/view.py`)
```python
@dataclass(frozen=True)
class ClaimQueryResult:
    claim_id: str
    availability: Literal["known", "unknown", "unavailable", "inexistent"]
    record: KnowledgeRecord | None = None


class KnowledgeView:
    """Contrato imutável de leitura epistêmica filtrado por holder, audience e purpose (G3-D07, G3-D14)."""

    def query_claim(self, claim_id: str) -> ClaimQueryResult:
        """Consulta uma alegação específica respeitando barreira de visibilidade."""
        ...

    def known_believed_claims(self) -> tuple[KnowledgeRecord, ...]:
        """Devolve apenas registros com awareness='known', stance='believed' e status in ('current', 'contested')."""
        ...

    def can_use_claim(self, claim_id: str, require_belief: bool = False) -> bool:
        """Verifica se o holder conhece (e opcionalmente acredita em) claim_id para sustentar uma decisão."""
        ...
```

---

## 3. Contrato do Validador de Admissão (`resources/admission.py`)

```python
@dataclass(frozen=True)
class AdmissionResult:
    admitted: bool
    reasons: tuple[str, ...] = ()
    admitted_intent: Intent | None = None


def validate_intent_admission(
    intent: Intent,
    agent_state: NpcState | FactionState,
    knowledge_view: KnowledgeView,
    faction_state: FactionState | None = None,
) -> AdmissionResult:
    """Valida se uma proposta da IA/política pode ser admitida pelo motor (G3-D08, G3-D09).
    
    Verificações obrigatórias:
    1. Epistêmica: todo claim_id em intent.required_claims deve ter awareness == 'known'
       na knowledge_view do ator (impede uso de segredos do jogador ou fatos desconhecidos - AT08, AT09).
    2. Capacidades: todo item em intent.required_capabilities deve pertencer a agent_state.capabilities.
    3. Recursos: para cada (res_key, qty) em intent.required_resources, agent_state.resources.get(res_key, 0) >= qty.
    4. Condição/Localização: se agent_state estiver incapacitado ('morto', 'inconsciente', 'preso') ou
       intent.location divergir da localização atual sem etapa de deslocamento, rejeita.
    5. Autoridade de Facção: se intent.acts_for_faction estiver definido, verifica se actor_id é o
       leader_id da facção ou autorizado em leadership.authority_rules.
    """
```

---

## 4. Contrato do `FactionProjector` (`application/projectors/faction.py`)

```python
class FactionProjector:
    """Reconstrói faccoes.md a partir do stream de eventos (e baseline de mundo.md)."""
    file: str = "faccoes.md"
    section: str = "full"
    order: int = 40

    def project(self, view: EventStreamView) -> ProjectionSection:
        ...
```

- `ProjectionEngine` em `application/projectors/engine.py` inclui `FactionProjector` quando a campanha possuir eventos `faction.updated` / `faction.subgroup_updated` / `faction.plan_updated` ou `faccoes.md` presente, mantendo total compatibilidade retroativa com as campanhas de teste da Fase 02 que possuem apenas `diario.md`, `ficha.md` e `npcs.md`.
