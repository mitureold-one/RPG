# Contratos P5 — Simulação, Orçamento e Fila

**Feature:** `phase-05-simulation` · **Gate:** [`G4`](../g4-decision-record.md)
**Status:** Aprovado para implementação
**Regra:** este documento fixa assinaturas e invariantes; qualquer mudança de contrato exige emenda no G4.

---

## 1. `contracts/simulation.py`

### 1.1 Enums e constantes

```python
WORK_KINDS = ("clock_advance", "npc_plan_step", "faction_plan_step", "scene_due", "scheduled")
WORK_STATUSES = ("scheduled", "pending", "deferred", "completed", "failed", "permanent")
TRIGGERS = ("time", "travel", "rest", "critical_event", "schedule", "manual")
BASE_PRIORITY = {
    "scene_due": 60,
    "clock_advance": 50,
    "scheduled": 50,
    "faction_plan_step": 40,
    "npc_plan_step": 30,
}
```

### 1.2 `WorkItem` (frozen)

| Campo | Tipo | Regra |
| :--- | :--- | :--- |
| `work_id` | `str` | `wrk_` + 26 caracteres hex; imutável |
| `kind` | `str` | um de `WORK_KINDS` |
| `entity_kind` | `str` | `clock`, `npc`, `faction`, `scene`, `world` |
| `entity_id` | `str` | não vazio |
| `due_at_sort` | `int` | `>= 0` |
| `priority` | `int` | `1..100` |
| `payload` | `Mapping[str, Any]` | JSON canônico |
| `deferrals` | `int` | `>= 0`, padrão 0 |
| `attempts` | `int` | `>= 0`, padrão 0 |

Invariantes: `priority_final = min(100, max(priority, BASE_PRIORITY[kind]) + min(deferrals, 5))`; ordenação `(-priority_final, due_at_sort, work_id)`; nunca mutado em voo — adiamento cria cópia com `deferrals + 1`.

### 1.3 `TickBudget`

```python
@dataclass(frozen=True)
class TickBudget:
    max_items: int = 8
    max_items_per_day: int = 6
    max_depth: int = 2
    override: int | None = None   # --budget; teto duro

    def limit(self, elapsed_minutes: int) -> int: ...
```

`limit = override` quando informado; senão `min(max_items, max_items_per_day * ceil(elapsed/1 dia), 4 + elapsed // 1440)`; mínimo 1; nunca negativo. O teto explícito é duro e vence a fórmula.

### 1.4 `TickRequest`

Campos: `campaign_id`, `from_game_time`, `from_sort`, `elapsed_minutes`, `trigger`, `seed`, `budget`, `dry_run`, `calendar`, `config`.

Invariantes: `elapsed_minutes >= 0`; `trigger in TRIGGERS`; `to_sort = from_sort + elapsed_minutes`; `seed` inteiro; `calendar` apenas leitura.

### 1.5 `WorldView`

Campos: `campaign_id`, `from_sort`, `to_sort`, `elapsed_minutes`, `clocks`, `npcs`, `factions`, `planned_scenes`, `scheduled`, `deferred`, `failures`, `completed_ids`, `config`.

Invariantes: view imutável; `completed_ids` contém todo `work_id` com `world.work_completed`; `deferred` contém o último `world.work_deferred` por `work_id`; `failures` contém o último `world.work_failed` por `work_id`.

### 1.6 `TickDecision`

```python
@dataclass(frozen=True)
class TickDecision:
    selected: tuple[WorkItem, ...]
    deferred: tuple[WorkItem, ...]
    budget: TickBudget
    limit: int
    adaptive: bool
    silent_entities: tuple[str, ...]
```

### 1.7 Portas

```python
class SimulationPolicy(Protocol):
    name: str
    version: str
    def due(self, view: WorldView) -> tuple[WorkItem, ...]: ...

class BudgetPolicy(Protocol):
    name: str
    version: str
    def select(self, items: tuple[WorkItem, ...], budget: TickBudget,
               elapsed_minutes: int) -> TickDecision: ...
```

Regras: puras, determinísticas, sem I/O, sem importar `resources`/`adapters`/`interfaces`; não gravam; não alteram `view`.

---

## 2. Eventos (`contracts/catalog.py`)

| Tipo | Payload |
| :--- | :--- |
| `world.ticked` | `tick_id:str`, `from_game_time:str`, `to_game_time:str`, `elapsed_minutes:int`, `trigger:str`, `budget_limit:int`, `selected:int`, `deferred:int` (+ opcionais `seed:int`, `queue_hash:str`) |
| `world.scheduled` | `work_id:str`, `kind:str`, `entity_kind:str`, `entity_id:str`, `due_game_time:str`, `due_at_sort:int`, `priority:int` (+ `payload:object`) |
| `world.work_deferred` | `work_id:str`, `kind:str`, `due_at_sort:int`, `reason:str`, `deferrals:int` |
| `world.work_completed` | `work_id:str`, `kind:str`, `outcome:object` |
| `world.work_failed` | `work_id:str`, `kind:str`, `error:str`, `attempts:int`, `retry_at_sort:int` (+ `entity_kind:str`, `entity_id:str`, `payload:object`) |

Regras: `schema_version = 1`; sem upcaster na Fase 05; todo evento de trabalho carrega `correlation_id = tick_id`; `causation_id` aponta o `world.scheduled` quando o trabalho nasce de agendamento e o `tick_id` lógico caso contrário — o vínculo material com o `world.ticked` (que só recebe `event_id` no append) fica em `meta.dependencies`, preenchido por `record_command_mutation`.

---

## 3. Projeção `queue.json`

```json
{
  "schema_version": 1,
  "last_seq": 42,
  "hash": "sha256:...",
  "last_tick": {"tick_id": "...", "to_game_time": "...", "selected": 3, "deferred": 1, "trigger": "time"},
  "pending": [],
  "deferred": [],
  "failed": [],
  "scheduled": []
}
```

- `pending`: união ordenada de `deferred` e `scheduled` (trabalho aberto), útil para inspeção rápida.
- `deferred`: adiados com `deferrals` (último evento por `work_id`).
- `failed`: último `world.work_failed` por `work_id` com `permanent` calculado (`attempts >= max_attempts`); falhas permanentes saem de `pending`/`scheduled`.
- `scheduled`: agendamentos sem `world.work_completed` com o mesmo `work_id`.
- `hash`: SHA-256 do JSON canônico do documento sem a chave `hash`.

---

## 4. Contrato de CLI

```text
world-tick --campaign <id> [--minutes N | --to "<data>"] [--trigger T] [--budget N] [--seed N] [--dry-run] [--json]
schedule   --campaign <id> --at "<data>" --kind K --entity <id> [--payload k=v ...] [--priority N] [--json]
queue      --campaign <id> [--json]
```

Respostas mínimas:

| Comando | Campos |
| :--- | :--- |
| `world-tick` | `status` (`ok`/`idempotent`/`error`), `tick_id`, `from`, `to`, `elapsed_minutes`, `budget_limit`, `selected[]`, `deferred[]`, `silent_entities[]`, `events_planned`, `queue_hash`, `dry_run` |
| `schedule` | `status`, `work_id`, `due_game_time`, `kind`, `entity_id`, `priority` — ou `status=rejected` + `reasons[]` |
| `queue` | `pending`, `deferred`, `failed`, `scheduled`, `last_tick`, `queue_hash` |

Códigos de saída: `0` sucesso; `1` erro de validação/campanha; `2` proposta rejeitada (`schedule` inválido).

---

## 5. Invariantes de teste

1. `work_id` e `tick_id` são funções puras de entrada canônica.
2. Trabalho concluído não reexecuta; trabalho adiado não desaparece.
3. `--dry-run` não altera `last_seq`, nenhum arquivo e nenhum hash.
4. Toda mutação passa por `record_command_mutation` (lock + snapshot + rebuild).
5. `queue.json` reconstruível a partir do log com hash estável.
6. Módulos novos `< 300` linhas; políticas sem I/O.
