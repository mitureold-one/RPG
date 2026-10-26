# Data Model: 012 — Fase 03: Agentes, Conhecimento Epistêmico e Refatoração R2

**Feature:** `phase-03-agents`  
**Status:** Ready for Implementation  
**Created:** 2026-10-26  
**Context:** Especificação formal das entidades epistêmicas (G3), modelos de NPCs em dois níveis, facções com política interna, validação de admissão e novos tipos de eventos canônicos para a Fase 03 / R2.

---

## 1. Identificadores Estáveis (`kernel/ids.py`)

Além dos identificadores já existentes (`evt_`, `bat_`, `cor_`, `wrk_`), o gerador ULID monotônico passa a emitir:
- `clm_<ulid>`: identificador único de alegação (`new_claim_id()`).
- `knw_<ulid>`: identificador único de registro epistêmico/inferência (`new_knowledge_id()`).
- `pln_<ulid>`: identificador único de plano operacional (`new_plan_id()`).

---

## 2. Domínio Epistêmico (`resources/knowledge/model.py`)

### 2.1 `HolderRef`
Identifica o sujeito epistêmico de forma tipada (G3-D06, G3-D07):
- `kind`: `"npc" | "faction" | "subgroup" | "protagonist" | "player"`
- `id`: `str` (ex.: `"aliado_inicial"`, `"CONSELHO_LORDES"`, `"ala_militar"`, `"protagonist"`, `"player"`)

### 2.2 `ClaimProposition` e `Claim` (G3-D10)
```python
@dataclass(frozen=True)
class ClaimProposition:
    subject: str
    predicate: str
    object: str
    scope: str = "global"

@dataclass(frozen=True)
class Claim:
    claim_id: str                  # clm_<ulid>
    proposition: ClaimProposition
    claim_type: str                # "occurrence" | "state" | "prediction" | "normative" | "counterfactual"
    valid_from: int | None = None  # game_time_sort opcional
    valid_to: int | None = None    # game_time_sort opcional
    source_event_id: str | None = None
    fact_ref: str | None = None    # ex: "npc:rei:status" ou "quest:Q1:status"
```

### 2.3 `ProvenanceRef` (G3-D03, G3-D12)
```python
@dataclass(frozen=True)
class ProvenanceRef:
    source_type: str               # "event" | "npc" | "faction" | "document" | "inference" | "system" | "player" | "protagonist" | "subgroup"
    source_id: str                 # ID estável da fonte
    channel: str                   # "observation" | "testimony" | "document" | "communication" | "inference" | "mechanism"
    acquired_at: str               # game_time canônico
    acquired_at_sort: int          # game_time_sort em minutos
    confidence: int                # 0..10000 (basis points da fonte)
    derived_from: tuple[str, ...] = ()  # knw_<ulid> ou clm_<ulid> sem ciclos
    supports: bool = True          # True se sustenta a alegação, False se contradiz
```

> **Nota de Simetria de Atores (Emenda G3):** `source_type` inclui `player`, `protagonist` e `subgroup` em paridade com `HolderRef.kind`, garantindo que eventos de compartilhamento (`knowledge.shared`) registrem a proveniência exata da entidade emissora sem perdas ou mapeamentos artificiais.

### 2.4 `KnowledgeRecord` (G3-D02, G3-D04, G3-D11)
```python
@dataclass(frozen=True)
class KnowledgeRecord:
    record_id: str                 # knw_<ulid>
    holder: HolderRef
    claim_id: str                  # clm_<ulid>
    awareness: str                 # "known" | "unknown"
    stance: str                    # "believed" | "disbelieved" | "uncertain"
    confidence: int                # 0..10000 (basis points determinísticos)
    status: str                    # "current" | "outdated" | "contested" | "refuted"
    provenance: tuple[ProvenanceRef, ...]
    acquired_at: str
    acquired_at_sort: int
    derived_from: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    visibility: str = "holder_only"  # "public" | "holder_only" | "faction_internal" | "subgroup_only" | "protagonist_private" | "player_meta"
    shared_by: str | None = None
```

### 2.5 `ClaimQueryResult` e `KnowledgeView` (G3-D06, G3-D07, G3-D14)
```python
@dataclass(frozen=True)
class ClaimQueryResult:
    claim_id: str
    availability: str              # "known" | "unknown" | "unavailable" | "inexistent"
    record: KnowledgeRecord | None = None
    effective_stance: str | None = None # "believed" | "disbelieved" | "uncertain"
    effective_confidence: int = 0
    reason: str | None = None
```

Assinatura e Matriz de Visibilidade de `KnowledgeView`:
```python
class KnowledgeView:
    def __init__(
        self,
        records: dict[str, KnowledgeRecord],
        holder: HolderRef | None = None,
        audience: HolderRef | None = None,
        purpose: str = "decision", # "decision" | "dialogue" | "audit"
        npc_affiliations: dict[str, dict[str, str]] | None = None,
        claim_validity_map: dict[str, tuple[int | None, int | None]] | None = None,
    ) -> None:
        ...

    def query_claim(self, claim_id: str, target_holder: HolderRef | None = None) -> ClaimQueryResult:
        ...
```

Regras da Matriz de Visibilidade (`query_claim` e `get_beliefs_of`):
1. **`inexistent` vs `unknown`:** se a claim foi registrada via `knowledge.claim_registered` ou existe no repositório, mas o holder não tomou conhecimento dela, retorna `availability="unknown"`. Retorna `availability="inexistent"` apenas se a claim for completamente desconhecida de todo o sistema.
2. **`holder_only`:** visível exclusivamente se `audience == holder`. Para terceiros ou protagonista, retorna `availability="unavailable"`.
3. **`faction_internal`:** visível apenas para a própria facção ou membros leais afiliados. Para não-afiliados ou protagonistas externos, retorna `availability="unavailable"`.
4. **`subgroup_only`:** visível apenas para membros do subgrupo. Para a liderança geral da facção ou outros subgrupos, retorna `availability="unavailable"`.
5. **`player_meta`:** visível **exclusivamente** para o jogador (`audience.kind in ("player", "human")`). Para protagonista, NPCs e facções, retorna **sempre** `availability="unavailable"`.
6. **`protagonist_private`:** visível apenas para o protagonista ou jogador. Para terceiros, retorna `availability="unavailable"`.

### 2.6 Regras de Validação Epistêmica
- `confidence` deve ser `int` estrito (`not isinstance(x, bool)`) no intervalo `0 <= confidence <= 10000`.
- `provenance` não pode ser vazia (`len(provenance) > 0`).
- `awareness == "unknown"` não pode ter `stance == "believed"` ativo como premissa de ação.
- Se `channel == "inference"`, `derived_from` deve conter pelo menos 1 ID existente e não formar ciclo no grafo de proveniência. Inferências não podem ter `confidence == 10000` sem premissas canônicas.
- `outdated` indica que a informação foi válida em janela anterior (`valid_to < current_time_sort` ou supersessão temporal), mantendo distinção explícita de `refuted` (falsa/contradita).
- Se `audience == "protagonist"` e o registro possui visibilidade `"player_meta"`, `query_claim` retorna `availability = "unavailable"`, impedindo vazamento de segredos para o protagonista (AT08, AT17).

---

## 3. Domínio de NPCs em Dois Níveis (`resources/npcs/model.py`)

### 3.1 `RelationalVector`
Representa a relação direcional de um NPC para outro alvo (`Protagonista`, outro NPC ou facção):
```python
@dataclass(frozen=True)
class RelationalVector:
    target_id: str
    trust: int = 0         # -3..+3
    rivalry: int = 0       # 0..+3
    dependency: int = 0    # 0..+3
    debt: int = 0          # -3..+3 (positivo = deve ao alvo; negativo = alvo deve a ele)
    loyalty: int = 0       # -3..+3
    note: str = ""
```

### 3.2 `AgentGoal` e `AgentPlan`
```python
@dataclass(frozen=True)
class AgentGoal:
    goal_id: str
    description: str
    horizon: str           # "short" | "medium" | "long"
    priority: int          # 1..5
    reason: str = ""
    status: str = "active" # "active" | "completed" | "abandoned" | "blocked"

@dataclass(frozen=True)
class PlanStep:
    index: int
    description: str
    prerequisites: tuple[str, ...] = ()
    required_claims: tuple[str, ...] = ()
    required_resources: Mapping[str, int] = field(default_factory=dict)
    status: str = "pending"  # "pending" | "in_progress" | "completed" | "failed" | "blocked"

@dataclass(frozen=True)
class AgentPlan:
    plan_id: str           # pln_<ulid>
    goal_id: str
    title: str
    steps: tuple[PlanStep, ...]
    alternatives: tuple[str, ...] = ()
    completion_conditions: tuple[str, ...] = ()
    status: str = "proposed" # "proposed" | "active" | "completed" | "interrupted" | "abandoned"
```

### 3.3 `NpcState` (Níveis `minor` e `major`)
```python
@dataclass(frozen=True)
class NpcState:
    npc_id: str
    name: str
    tier: str = "minor"            # "minor" | "major"
    classification: str = ""
    role: str = ""
    faction: str = ""
    subgroup_id: str = ""
    attitude: str = "neutra"
    psychology: str = ""
    will: str = ""                 # Objetivo imediato em minor; agenda central em major
    weakness: str = ""
    location: str = ""
    condition: str = "saudável"
    appearance: str = ""
    bonds: Mapping[str, str] = field(default_factory=dict)
    relation_protagonist: str = ""
    # Campos expandidos (populados em NPCs major ou promovidos)
    goals: tuple[AgentGoal, ...] = ()
    plans: tuple[AgentPlan, ...] = ()
    resources: Mapping[str, int] = field(default_factory=dict)
    capabilities: tuple[str, ...] = ()
    commitments: tuple[str, ...] = ()
    relations: Mapping[str, RelationalVector] = field(default_factory=dict)
```

---

## 4. Domínio de Facções com Política Interna (`resources/factions/model.py`)

```python
@dataclass(frozen=True)
class FactionLeadership:
    leader_id: str
    title: str = "Líder"
    authority_rules: tuple[str, ...] = ("leader_only",)
    succession_line: tuple[str, ...] = ()

@dataclass(frozen=True)
class FactionSubgroup:
    subgroup_id: str
    name: str
    leader_id: str
    agenda: str
    stance_towards_leadership: str = "aligned"  # "aligned" | "divergent" | "conspiring"
    members: tuple[str, ...] = ()
    resources: Mapping[str, int] = field(default_factory=dict)

@dataclass(frozen=True)
class FactionState:
    tag: str
    name: str
    description: str
    power: int = 3                 # 1..5
    scale: str = "regional"
    clock: str = ""
    rivals: tuple[str, ...] = ()
    leadership: FactionLeadership | None = None
    collective_goals: tuple[AgentGoal, ...] = ()
    plans: tuple[AgentPlan, ...] = ()
    resources: Mapping[str, int] = field(default_factory=dict)
    influence: Mapping[str, int] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    subgroups: Mapping[str, FactionSubgroup] = field(default_factory=dict)
    internal_conflicts: tuple[str, ...] = ()
```

---

## 5. Catálogo de Novos Eventos da Fase 03 (`contracts/catalog.py`)

Todos os novos eventos são registrados em `V1_EVENT_SCHEMAS` e no `build_v1_catalog()` com `schema_version=1`:

| Tipo de Evento | Payload Obrigatório | Campos Opcionais | Projeção Afetada |
| :--- | :--- | :--- | :--- |
| `knowledge.claim_registered` | `claim_id`, `proposition`, `claim_type` | `valid_from`, `valid_to`, `source_event_id`, `fact_ref` | Estado Epistêmico / `npcs.md` / `faccoes.md` |
| `knowledge.acquired` | `record_id`, `holder`, `claim_id`, `awareness`, `stance`, `confidence`, `provenance` | `status`, `visibility` | Estado Epistêmico / `npcs.md` / `faccoes.md` |
| `knowledge.inferred` | `record_id`, `holder`, `claim_id`, `stance`, `confidence`, `derived_from`, `method` | `provenance`, `visibility` | Estado Epistêmico / `npcs.md` |
| `knowledge.revised` | `record_id`, `holder`, `claim_id`, `stance`, `confidence`, `status`, `reason` | `supersedes`, `provenance` | Estado Epistêmico / `npcs.md` / `faccoes.md` |
| `knowledge.shared` | `record_id`, `from_holder`, `to_holder`, `claim_id`, `scope`, `confidence` | `stance`, `visibility` | Estado Epistêmico / `npcs.md` / `faccoes.md` |
| `npc.promoted` | `npc_id`, `from_tier`, `to_tier` | `goals`, `capabilities`, `resources`, `location`, `condition` | `npcs.md` |
| `npc.goal_updated` | `npc_id`, `goal_id`, `description`, `horizon`, `priority`, `status` | `reason` | `npcs.md` |
| `npc.plan_updated` | `npc_id`, `plan_id`, `goal_id`, `title`, `steps`, `status` | `alternatives`, `completion_conditions` | `npcs.md` |
| `npc.relationship_updated` | `npc_id`, `target_id` | `trust`, `rivalry`, `dependency`, `debt`, `loyalty`, `note` | `npcs.md` |
| `faction.updated` | `tag`, `name` | `leadership`, `collective_goals`, `resources`, `influence`, `limitations`, `internal_conflicts` | `faccoes.md` |
| `faction.subgroup_updated` | `faction_tag`, `subgroup_id`, `name`, `leader_id`, `stance_towards_leadership` | `agenda`, `members`, `resources` | `faccoes.md` |
| `faction.plan_updated` | `faction_tag`, `plan_id`, `title`, `steps`, `status` | `goal_id`, `actor_subgroup_id` | `faccoes.md` |
| `proposal.rejected` | `proposal_kind`, `actor_id`, `reasons` | `payload_summary` | Auditoria apenas (ignorado por estado operacional) |
