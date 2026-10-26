# Data Model: 015 — Fase 05: Simulação de Mundo por Tempo

**Feature:** `phase-05-simulation`
**Status:** Aprovado para implementação (G4 ratificado)
**Created:** 2026-10-26
**Spec:** [`spec.md`](spec.md) · **Plan:** [`plan.md`](plan.md) · **Gate:** [`g4-decision-record.md`](g4-decision-record.md)

---

## 1. Visão geral

O modelo separa **pedido** (`TickRequest`, `TickBudget`), **visão** (`WorldView`), **trabalho** (`WorkItem`, `TickDecision`) e **resultado** (`WorkOutcome`). Nenhum objeto é fonte de verdade: a verdade permanece no event log; `queue.json` e `diario.md` são projeções reconstruíveis.

---

## 2. Enums e constantes

| Enum | Valores | Uso |
| :--- | :--- | :--- |
| `kind` | `clock_advance`, `npc_plan_step`, `faction_plan_step`, `scene_due`, `scheduled` | Tipo do trabalho |
| `entity_kind` | `clock`, `npc`, `faction`, `scene`, `world` | Natureza da entidade |
| `trigger` | `time`, `travel`, `rest`, `critical_event`, `schedule`, `manual` | Acionador do tick |
| `status` do trabalho | `scheduled`, `pending`, `deferred`, `completed`, `failed`, `permanent` | Ciclo de vida |
| `status` do outcome | `completed`, `failed` | Resultado da resolução |

Prioridade base: `scene_due = 60`, `clock_advance = 50`, `scheduled = 50`, `faction_plan_step = 40`, `npc_plan_step = 30`. Prioridade explícita sempre em `1..100`.

---

## 3. Pedido e orçamento

### 3.1 `TickRequest`

```python
@dataclass(frozen=True)
class TickRequest:
    campaign_id: str
    from_game_time: str          # data canônica do diário no início
    from_sort: int               # minutos desde a época da campanha
    elapsed_minutes: int         # >= 0; --to é convertido pela CLI
    trigger: str = "manual"      # enum da §2
    seed: int = 0                # reservado; a política padrão ignora
    budget: TickBudget = TickBudget()
    dry_run: bool = False
```

Invariantes: `from_sort >= 0`, `elapsed_minutes >= 0`, `trigger` no enum, `seed` inteiro, `budget` tipado. `to_sort = from_sort + elapsed_minutes` é derivado e nunca recebido como verdade separada. `dry_run` calcula tudo e não grava.

### 3.2 `TickBudget`

```python
@dataclass(frozen=True)
class TickBudget:
    max_items: int = 8
    max_items_per_day: int = 6
    override: int | None = None   # --budget N; teto duro
```

Limite efetivo: `override`, se informado; caso contrário `max(1, min(max_items, max_items_per_day * ceil(elapsed/1 dia), 4 + elapsed_minutes // 1440))`. `max_items_per_day` atua como teto diário adicional e nunca eleva o teto de `max_items`; `override` não pode ser menor que 1. (`max_depth` foi removido na auditoria da fase: profundidade de avaliação pertence à Fase 06.)

---

## 4. `WorldView`

```python
@dataclass(frozen=True)
class WorldView:
    campaign_id: str
    from_sort: int
    to_sort: int
    elapsed_minutes: int
    clocks: tuple[Mapping[str, Any], ...] = ()
    npcs: Mapping[str, Any] = {}
    factions: Mapping[str, Any] = {}
    planned_scenes: tuple[Mapping[str, Any], ...] = ()
    scheduled: tuple[WorkItem, ...] = ()
    deferred: tuple[WorkItem, ...] = ()
    failures: tuple[Mapping[str, Any], ...] = ()
    completed_ids: frozenset[str] = frozenset()
    config: Mapping[str, Any] = {}
```

- `clocks`, `npcs`, `factions` e `planned_scenes` vêm das projeções/estado fresco; `scheduled` (vencidos), `deferred` (abertos), `failures` (elegíveis a retry) e `completed_ids` vêm dos eventos `world.*`; o histórico completo permanece no `EventStore`.
- Invariantes: `to_sort >= from_sort`; `elapsed_minutes` é a diferença declarada no pedido; listas e mapas são imutáveis para a política; nenhuma política faz I/O.
- `completed_ids` é o conjunto de `work_id`s com `world.work_completed`; é a barreira de deduplicação.

---

## 5. `WorkItem`

```python
@dataclass(frozen=True)
class WorkItem:
    work_id: str                 # wrk_<26 hex>
    kind: str                    # enum da §2
    entity_kind: str             # clock | npc | faction | scene | world
    entity_id: str
    due_at_sort: int             # minutos; >= 0
    priority: int = 50           # 1..100
    payload: Mapping[str, Any] = {}  # JSON canônico
    deferrals: int = 0
    attempts: int = 0
```

Invariantes: `work_id` casa `^wrk_[0-9a-f]{26}$`; `kind` e `entity_kind` estão nos enums; `entity_id` é texto não vazio; `due_at_sort`, `deferrals` e `attempts` são inteiros `>= 0`; `payload` é objeto JSON canônico (chaves ordenadas, sem `float` em tempo/orçamento). Para `scene_due`, `payload.beat` é obrigatório; sem ele a resolução falha com `scene_payload_invalid:missing_beat`. `priority_final = min(100, max(priority, base[kind]) + min(deferrals, 5))`; o boost de no máximo 5 pontos impede que item antigo morra no fim da fila. `with_deferral()` preserva `work_id`, `due_at_sort` e `payload`, e incrementa `deferrals`; a nova tentativa é representada pelo `attempts` gravado em `world.work_failed` e relido na re-derivação.

---

## 6. `TickDecision` e `WorkOutcome`

```python
@dataclass(frozen=True)
class TickDecision:
    selected: tuple[WorkItem, ...]
    deferred: tuple[WorkItem, ...]
    limit: int
    adaptive: bool
    silent_entities: tuple[str, ...] = ()

@dataclass(frozen=True)
class WorkOutcome:
    work_id: str
    kind: str
    status: str                  # completed | failed
    summary: str = ""
    details: Mapping[str, Any] = {}
    error: str = ""
    retry_at_sort: int | None = None
    attempts: int = 0
```

Invariantes de `TickDecision`: `selected` e `deferred` são disjuntos; `selected + deferred` cobre exatamente o trabalho devido; `len(selected) <= limit`; `used = len(selected)`; `remaining = max(0, limit - used)`; `remaining == 0` é comportamento esperado, não erro. `silent_entities` lista, em ordem estável, entidades sem trabalho devido.

Invariantes de `WorkOutcome`: `completed` tem `summary`/`details` e não tem `retry_at_sort`; `failed` tem `error` determinístico e `retry_at_sort` inteiro; `details` é JSON canônico. O `status` do outcome não substitui o status do trabalho na fila. Em `world.work_completed`, apenas `summary` e `details` são persistidos no campo `outcome`; `work_id` e `kind` ficam no envelope do evento.

---

## 7. Eventos `world.*` (schema v1)

Campos obrigatórios e opcionais do catálogo v1. Nenhum upcaster na Fase 05; o evento não muda de envelope.

| Evento | Campos obrigatórios | Campos opcionais |
| :--- | :--- | :--- |
| `world.ticked` | `tick_id: str`; `from_game_time: str`; `to_game_time: str`; `elapsed_minutes: int`; `trigger: str`; `budget_limit: int`; `selected: int`; `deferred: int` | `seed: int`; `queue_hash: str` |
| `world.scheduled` | `work_id: str`; `kind: str`; `entity_kind: str`; `entity_id: str`; `due_game_time: str`; `due_at_sort: int`; `priority: int` | `payload: object`; `priority_final: int` |
| `world.work_deferred` | `work_id: str`; `kind: str`; `due_at_sort: int`; `reason: str`; `deferrals: int` | `entity_kind: str`; `entity_id: str`; `priority: int` |
| `world.work_completed` | `work_id: str`; `kind: str`; `outcome: object` | `entity_kind: str`; `entity_id: str` |
| `world.work_failed` | `work_id: str`; `kind: str`; `error: str`; `attempts: int`; `retry_at_sort: int` | `entity_kind: str`; `entity_id: str`; `payload: object` |

`world.ticked.selected` e `deferred` são contagens do ciclo; `world.work_completed.outcome` carrega `summary: str` e `details: object`, enquanto `work_id` e `kind` ficam no envelope do evento; em passos de plano, `outcome.details.plan_ready_for_resolution` sinaliza plano pronto sem encerrá-lo; `reason` de adiamento por orçamento é `budget_exhausted`; `priority` e `priority_final` são inteiros `1..100`.

Ordem do lote: `world.ticked` primeiro, depois eventos de trabalho (`world.work_completed`, `world.work_failed`, `world.work_deferred`) e, por fim, `world.scheduled` do ciclo. `world.work_completed` é terminal para o `work_id`; falha nunca apaga conclusão anterior.

---

## 8. `queue.json`

```json
{
  "schema_version": 1,
  "last_seq": 128,
  "hash": "sha256:...",
  "last_tick": {"tick_id": "tck_...", "to_game_time": "08/10/300, 10:00", "trigger": "time", "selected": 2, "deferred": 0},
  "pending": [{"work_id": "wrk_...", "kind": "clock_advance", "entity_kind": "clock", "entity_id": "Pressão da Guilda", "due_at_sort": 123, "priority": 50, "deferrals": 0, "payload": {}}],
  "deferred": [],
  "failed": [{"work_id": "wrk_...", "kind": "clock_advance", "entity_kind": "clock", "entity_id": "Pressão da Guilda", "error": "entidade_ausente", "attempts": 2, "retry_at_sort": 456, "payload": {}, "permanent": false}],
  "scheduled": [{"work_id": "wrk_...", "kind": "scene_due", "entity_kind": "scene", "entity_id": "Chegada do Mensageiro", "due_game_time": "23/10/300, 10:00", "due_at_sort": 789, "priority": 60, "payload": {"beat": "Chegada do Mensageiro"}}]
}
```

- `schema_version = 1`; `last_seq` é o `last_seq` do `EventStore` no momento da projeção; `last_tick` é `null` antes do primeiro tick e pode trazer `trigger`.
- `hash` é `sha256:` sobre o JSON canônico do documento sem o próprio `hash`; rebuild a partir do log reproduz o mesmo hash.
- `pending` reúne todo trabalho não concluído (adiados + agendados), ordenado por `(-priority_final, due_at_sort, work_id)`; `deferred` e `scheduled` são recortes dessa lista, e `priority_final` é derivado de `priority` e `deferrals`.
- `failed[].permanent` é `true` somente quando `attempts >= max_attempts`; até lá o item ainda é elegível a retry.
- `queue.json` é leitura operacional: não é consultado como verdade por política, não substitui o log e é reconstruído por `rebuild`.

---

## 9. Invariantes de identidade, orçamento e retry

**Identidade.** `work_id = "wrk_" + sha256("kind|entity_kind:entity_id|due_at_sort|payload_canônico")[:26]`; `tick_id = "tck_" + sha256("campanha|from_sort|to_sort|trigger|seed|queue_revision")[:26]`; `queue_revision` é a contagem de eventos `world.*` no início do ciclo. O mesmo estado e os mesmos parâmetros produzem os mesmos ids; replay não reexecuta `world.work_completed`. Item adiado conserva `work_id` e `due_at_sort`; nova data de vencimento gera outro `work_id`. Reexecução idêntica sem trabalho novo devolve `selected = 0` e `status = idempotent`, sem append e sem alteração de fila.

**Orçamento.** `--budget N` é teto duro e nunca é ultrapassado; o que não couber é adiado com `deferrals + 1` e `reason = budget_exhausted`; conclusão anterior nunca é removida nem reescrita; `remaining == 0` é esperado e não gera evento de erro; entidade sem trabalho devido não gera evento e aparece em `silent_entities`.

**Retry.** `attempts` começa em `0` e cada falha grava `attempts + 1`; `retry_at_sort = to_sort + retry_backoff_minutes * attempts`, com padrões `60` e `max_attempts = 3`; o item volta a ser devido quando `to_sort >= retry_at_sort` e `attempts < max_attempts`; ao esgotar, a falha vira permanente e não é mais re-derivada; `world.work_failed` preserva `kind`, `entity_kind`, `entity_id` e `payload`; trabalho concluído nunca falha depois.

---

## 10. Transições de status do trabalho

| De | Para | Condição | Efeito |
| :--- | :--- | :--- | :--- |
| `scheduled` | `pending` | `to_sort >= due_at_sort` | item entra no conjunto devido do ciclo |
| `pending` | `completed` | selecionado e resolução ok | `world.work_completed`; terminal |
| `pending` | `deferred` | não selecionado por orçamento | `world.work_deferred`; `deferrals + 1` |
| `pending` | `failed` | selecionado e resolução falha | `world.work_failed`; `attempts + 1` |
| `deferred` | `pending` | próximo tick, ainda devido e com orçamento | mesmo `work_id`, `deferrals` preservado |
| `deferred` | `failed` | selecionado e resolução falha | `world.work_failed`; `attempts + 1` |
| `failed` | `pending` | `to_sort >= retry_at_sort` e `attempts < max_attempts` | re-derivação com o `payload` original |
| `failed` | `permanent` | `attempts >= max_attempts` | sai da fila ativa; `permanent: true` |

`completed` e `permanent` são terminais para o mesmo `work_id`. Não existem atalhos `scheduled → completed` nem `pending → permanent`.

---

## 11. Regras de ordenação

- Ordem total e estável: `(-priority_final, due_at_sort, work_id)`; empate nunca depende de dicionário, horário de criação ou RNG.
- `selected` e as listas de `queue.json` usam a mesma ordem; `silent_entities` é ordenado por `(entity_kind, entity_id)`.
- `world.ticked` é sempre o primeiro evento do lote; a ordem interna dos trabalhos segue `selected`; payloads são serializados em JSON canônico antes de qualquer hash.
