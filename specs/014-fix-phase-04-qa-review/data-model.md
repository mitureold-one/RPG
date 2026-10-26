# Data Model: 014 — Remediação dos Bloqueantes de QA da Fase 04

**Feature:** `fix-phase-04-qa-review`  
**Data:** 2026-10-26  
**Status:** Consolidado  

---

## 1. Entidades de Conhecimento e Identidade Epistêmica

### 1.1 `HolderRef` (Unificado em `contracts/context.py`)
Identificador unificado de sujeito epistêmico em todo o sistema.

```python
VALID_HOLDER_KINDS = {"npc", "faction", "subgroup", "protagonist", "player"}

@dataclass(frozen=True)
class HolderRef:
    kind: str
    id: str

    def __post_init__(self) -> None:
        if self.kind not in VALID_HOLDER_KINDS:
            raise ValueError(f"kind de holder inválido: '{self.kind}' (esperado: {VALID_HOLDER_KINDS})")
        if not self.id or not isinstance(self.id, str):
            raise ValueError("id do holder deve ser string não vazia")
```

### 1.2 `ProvenanceRef` (Canônico da Fase 03 em `resources/knowledge/model.py`)
Rastreabilidade exata e imutável de onde e como o conhecimento foi originado.

```python
@dataclass(frozen=True)
class ProvenanceRef:
    source_type: str        # 'event', 'npc', 'faction', 'document', 'inference', 'system', 'player', 'protagonist'
    source_id: str          # ex: 'evt_01J...' ou 'Aemon'
    channel: str            # 'observation', 'testimony', 'document', 'communication', 'inference', 'mechanism'
    acquired_at: str        # Timestamp textual da diegese (ex: '01/10/300 08:00')
    acquired_at_sort: int   # Ordem inteira monotonamente crescente
    confidence: int         # 0..10000 (basis points estritos)
    derived_from: tuple[str, ...] = ()
    supports: bool = True
```

### 1.3 `KnowledgeRecord` (Estado Epistêmico Completo)
Representação consolidada de uma alegação mantida por um agente.

```python
@dataclass(frozen=True)
class KnowledgeRecord:
    record_id: str
    holder: HolderRef
    claim_id: str
    awareness: str = "known"           # 'known' | 'unknown'
    stance: str = "believed"           # 'believed' | 'disbelieved' | 'uncertain'
    confidence: int = 10000            # 0..10000 basis points
    status: str = "current"            # 'current' | 'outdated' | 'contested' | 'refuted'
    provenance: tuple[ProvenanceRef, ...] = ()
    acquired_at: str = "01/01 00:00"
    acquired_at_sort: int = 0
    derived_from: tuple[str, ...] = ()
    supersedes: tuple[str, ...] = ()
    visibility: str = "holder_only"    # 'public' | 'holder_only' | 'faction_internal' | 'player_meta'
    shared_by: str | None = None
```

---

## 2. Entidades de Relacionamento e Relevância de NPCs

### 2.1 Vetor Relacional de NPC (`NpcState.relationships`)
No arquivo `estado.json`, os relacionamentos de um NPC são serializados canonicamente como uma lista de vetores:

```json
{
  "id": "npc_kael",
  "name": "Kael",
  "tier": "major",
  "relationships": [
    {
      "target_id": "Aemon",
      "trust": -2,
      "rivalry": 2,
      "dependency": 0,
      "debt": 0,
      "loyalty": -1
    }
  ]
}
```

### 2.2 Estrutura Normalizada para Cálculo de Relevância
O helper puro `_extract_relational_vector` normaliza as representações (`list[dict]` ou `dict`) para um dicionário padrão:

| Campo | Tipo | Intervalo | Significado |
| :--- | :--- | :--- | :--- |
| `target_id` | `str` | id do alvo | Identificador do sujeito com quem se relaciona |
| `trust` | `int` | `-3..+3` | Confiança (< -1: hostil/desconfiado) |
| `rivalry` | `int` | `0..+3` | Nível de rivalidade (>= 2 gera justificativa `ameaca`) |
| `debt` | `int` | `-3..+3` | Dívida/favor (!= 0 gera justificativa `divida`) |
| `loyalty` | `int` | `-3..+3` | Lealdade jurada |
| `dependency` | `int` | `0..+3` | Dependência operacional |

---

## 3. Entidades de Histórico Causal e Eventos Recentes

### 3.1 Item de `recent_events` no Cache `estado.json`
Todo evento recente incluído no cache deve carregar seu identificador canônico de evento:

```json
{
  "seq": 7,
  "event_id": "evt_01JABCDEF1234567890",
  "type": "turn.committed",
  "game_time": "01/10/300 09:00",
  "game_time_sort": 7,
  "actor": {"kind": "human", "id": "gm"},
  "summary": "Portão reforçado com barricadas de ferro.",
  "refs": ["npc:Aemon"],
  "payload": {"turn": 1, "action": "Aemon vigia o portão", "summary": "Portão reforçado..."}
}
```

### 3.2 Payload de Correção (`correction.issued`)
Payload de retificação causal compatível com Fase 02:

```json
{
  "correction_id": "corr_01",
  "corrects": ["evt_01JABCDEF1234567890"],
  "reason": "O portão foi reforçado com madeira e não ferro.",
  "changes": [
    {"field": "summary", "old": "Portão de ferro", "new": "Portão de madeira"}
  ]
}
```

---

## 4. Cache de Estado Derivado (`estado.json`)

Estrutura canônica persistida na raiz da campanha e em `projections/estado.json`:

```json
{
  "schema_version": 1,
  "last_seq": 8,
  "npcs": [...],
  "factions": [...],
  "knowledge": [...],
  "recent_events": [...]
}
```

- `schema_version`: Inteiro estrito (deve ser `1`).
- `last_seq`: Número da sequência do último evento computado pelo projetor ou alinhado pós-auditoria.
