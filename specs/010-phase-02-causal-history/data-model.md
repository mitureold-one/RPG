# Data Model: 010 — Fase 02: História Causal & Refatoração R1

**Feature:** `phase-02-causal-history`  
**Status:** Completed  
**Created:** 2026-10-24  
**Context:** Especificação formal de entidades de domínio, schemas dos 23 tipos de eventos v1, marcadores atômicos de lote, layout de diretórios, fila esqueleto e snapshots para o R1/Fase 02.

---

## 1. Estrutura Canônica do Envelope de Evento

O envelope persistido é imutável e padronizado em [`contracts/event.py`](../../contracts/event.py):

| Campo | Tipo | Descrição | Regras de Validação |
|---|---|---|---|
| `event_id` | `str` | Identificador único global monotônico | Formato `evt_<ulid>` (26 caracteres ULID) |
| `campaign_id` | `str` | Identificador da campanha dona | Formato slug `^[a-z0-9_][a-z0-9_-]*$` |
| `seq` | `int` | Sequência monotônica estrita contígua | Inteiro $\ge 1$, sem lacunas por campanha |
| `type` | `str` | Nome do tipo de evento no catálogo | Ex.: `turn.committed`, `clock.advanced` |
| `schema_version` | `int` | Versão do schema do payload | Inteiro $\ge 1$ |
| `recorded_at` | `str` | Timestamp UTC do registro em disco | ISO-8601 com sufixo `Z` |
| `game_time` | `str` | Data e hora canônica do mundo diegético | Texto não-vazio obrigatório |
| `game_time_sort` | `int` | Minutos decorridos desde a época inicial | Inteiro $\ge 0$ obrigatório |
| `actor` | `ActorRef` | Entidade causadora do evento | Objeto `{"kind": "<kind>", "id": "<id>"}` |
| `causation_id` | `str \| None` | Evento direto que causou este evento | Formato `evt_<ulid>` ou `null` |
| `correlation_id` | `str \| None` | Identificador da unidade de trabalho | Ex.: `turn_000001`, `cmd_<ulid>` |
| `payload` | `dict` | Dados específicos do tipo de evento | Validado contra o `payload_schema` do `EventType` |
| `meta` | `dict` | Metadados de rastreabilidade | Contém `dependencies: list[str]`, etc. |

### 1.1 `ActorRef`
* `kind`: `human`, `agent`, `system`, `npc` ou `faction`.
* `id`: identificador do ator (ex.: `user`, `gm_narrative_engine`, `system_store`, `npc_malakor`, `CONSELHO_LORDES`).

---

## 2. Marcadores de Lote no Segmento JSONL (G1-D2, C1)

Cada arquivo de segmento `campaigns/<id>/events/<segment:06d>.jsonl` contém registros de dois tipos operacionais (`record`):

### 2.1 Marcador `batch.open`
Indica a abertura atômica de um lote de escrita sob lock:
```json
{
  "record": "batch",
  "state": "open",
  "batch_id": "bat_01JABCDEFGHJKMNPQRSTVWXYZ0",
  "first_seq": 10,
  "event_count": 3
}
```

### 2.2 Registro de Evento (`record: event`)
Contém o envelope canônico completo acrescido do discriminador de arquivo `"record": "event"`:
```json
{
  "record": "event",
  "event_id": "evt_01JABCDEFGHJKMNPQRSTVWXYZ1",
  "campaign_id": "dinastia_cinzas",
  "seq": 10,
  "type": "turn.proposed",
  "schema_version": 1,
  "recorded_at": "2026-10-24T12:00:00Z",
  "game_time": "01 de Janeiro de 304, 10:00",
  "game_time_sort": 600,
  "actor": {"kind": "agent", "id": "narrative_engine"},
  "causation_id": null,
  "correlation_id": "turn_000010",
  "payload": {
    "turn": 10,
    "action": "Investigar a cripta dos ancestrais",
    "summary": "Busca por registros de sucessão",
    "stakes": "Descoberta de testamento ou emboscada",
    "dc": 15,
    "stat": "INT",
    "target": {"kind": "location", "id": "cripta_ancestrais"},
    "preconditions": ["tocha acesa", "chave de prata"]
  },
  "meta": {"dependencies": []}
}
```

### 2.3 Marcador `batch.committed`
Confirmação atômica do lote. Leitores só aceitam os eventos se este marcador for encontrado:
```json
{
  "record": "batch",
  "state": "committed",
  "batch_id": "bat_01JABCDEFGHJKMNPQRSTVWXYZ0",
  "last_seq": 12,
  "hash": "sha256:4a5c9f28d81395b08c9038d17b5f21e5f8f8b8a8b1a2b3c4d5e6f7a8b9c0d1e2"
}
```

---

## 3. Catálogo Mínimo de Eventos v1 (23 Tipos)

### Grupo 1: Ciclo de Vida & Comandos
1. **`campaign.created`** (v1)
   - `payload`: `title` (str), `system` (str), `calendar` (str), `start_game_time` (str), `config_version` (int)
2. **`command.executed`** (v1)
   - `payload`: `command` (str), `args` (list[str]), `status` (str: `success`/`error`), `summary` (str)

### Grupo 2: Loop Narrativo de Turno
3. **`turn.proposed`** (v1)
   - `payload`: `turn` (int), `action` (str), `summary` (str), `stakes` (str), `dc` (int), `stat` (str), `target` (dict opcional), `preconditions` (list[str])
4. **`turn.rejected`** (v1)
   - `payload`: `turn` (int), `reasons` (list[str])
   - `meta.dependencies`: `[<turn.proposed evt_id>]`
5. **`action.resolved`** (v1)
   - `payload`: `turn` (int), `result` (str: `success`/`failure`/`critical_success`/`critical_failure`), `outcome` (str), `costs` (dict), `effects` (dict)
   - `meta.dependencies`: `[<turn.proposed evt_id>]`
6. **`turn.committed`** (v1)
   - `payload`: `turn` (int), `summary` (str), `scene_type` (str), `location` (str), `present` (list[str]), `vitals` (dict), `costs` (dict)
   - `meta.dependencies`: referências aos eventos causais do turno

### Grupo 3: Relógios Narrativos
7. **`clock.created`** (v1)
   - `payload`: `name` (str), `max` (int), `trigger` (str)
8. **`clock.advanced`** (v1)
   - `payload`: `name` (str), `steps` (int), `current` (int), `max` (int), `status` (str: `active`/`breached`)
   - `meta.dependencies`: `[<causal evt_id>]`
9. **`clock.resolved`** (v1)
   - `payload`: `name` (str), `status` (str: `completed`/`breached`), `xp_granted` (int)
   - `meta.dependencies`: `[<causal evt_id>]`

### Grupo 4: Missões & Contratos
10. **`quest.created`** (v1)
    - `payload`: `quest_id` (str), `title` (str), `type` (str), `contractor` (str|None), `clock` (str|None), `reward` (dict)
11. **`quest.objective_completed`** (v1)
    - `payload`: `quest_id` (str), `objective_index` (int), `xp_granted` (int)
12. **`quest.completed`** (v1)
    - `payload`: `quest_id` (str), `xp_granted` (int), `contractor_rep` (dict opcional)
13. **`quest.failed`** (v1)
    - `payload`: `quest_id` (str), `reason` (str), `contractor_rep` (dict opcional)
14. **`quest.status_changed`** (v1)
    - `payload`: `quest_id` (str), `from` (str), `to` (str), `reason` (str)

### Grupo 5: Showrunner & Cenas
15. **`arc.updated`** (v1)
    - `payload`: `title` (str), `question` (str), `stage` (str), `scene_name` (str), `date_time` (str), `location` (str), `present` (list[str])
16. **`scene.planned`** (v1)
    - `payload`: `beat` (str), `scene_type` (str), `actors` (list[str])
17. **`scene.completed`** (v1)
    - `payload`: `index` (int)

### Grupo 6: NPCs & Facções
18. **`npc.updated`** (v1)
    - `payload`: `npc_id` (str), `changes` (dict)
19. **`faction.reputation_changed`** (v1)
    - `payload`: `faction` (str), `delta_rep` (int), `new_score` (int), `favors` (int), `debts` (int), `reason` (str)

### Grupo 7: Protagonista & Progressão
20. **`protagonist.progression_changed`** (v1)
    - `payload`: `xp_delta` (int), `xp_total` (int), `level` (int), `attribute_points` (int), `ability_points` (int), `source` (str)
21. **`protagonist.sheet_changed`** (v1)
    - `payload`: `kind` (str: `attribute`/`ability`/`vital`/`item`), `target` (str), `new_value` (any), `points_remaining` (int), `source` (str)

### Grupo 8: Prosa, Correções & Auditoria
22. **`prose.recorded`** (v1)
    - `payload`: `turn` (int), `text_hash` (str), `text_path` (str), `source` (str), `bytes` (int), `scene_type` (str)
    - `meta.dependencies`: `[<turn.committed evt_id>]`
23. **`correction.issued`** (v1)
    - `payload`: `correction_id` (str: `cor_<ulid>`), `corrects` (list[str]), `reason` (str), `changes` (list[dict]), `state` (str: `concluída`/`pendente`), `inconsistency_detected` (bool, default false)
    - `meta.dependencies`: lista dos `evt_<ulid>` corrigidos
24. **`correction.recomputed`** (v1)
    - `payload`: `correction_id` (str), `affected` (list[str]), `outcome` (str)
    - `meta.dependencies`: `[<correction.issued evt_id>]`
25. **`projection.rebuilt`** (v1)
    - `payload`: `from_seq` (int), `to_seq` (int), `projection_version` (int), `hash` (str)

---

## 4. Fila Esqueleto (`queue.jsonl`)

Arquivo `campaigns/<id>/queue.jsonl`:
```json
{"record":"work","work_id":"wrk_01JABCDEFGHJKMNPQRSTVWXYZ0","kind":"clock.advance","status":"pending","created_at":"2026-10-24T12:00:00Z","due_game_time":"01 de Janeiro de 304, 12:00","priority":3,"payload":{"name":"Cerco da Fortaleza","steps":1}}
{"record":"work","work_id":"wrk_01JABCDEFGHJKMNPQRSTVWXYZ0","status":"done","completed_at":"2026-10-24T12:05:00Z","result_event_id":"evt_01JABCDEFGHJKMNPQRSTVWXYZ5"}
```
Regras:
* Append-only: nenhuma linha existente é sobrescrita.
* Estados de trabalho: `pending` $\to$ `done` ou `failed`.

---

## 5. Estrutura de Snapshot de Projeção (`snapshots/`)

Arquivo `campaigns/<id>/snapshots/<snapshot_seq:06d>.json` (gerado a cada 500 eventos ou fechamento de arco):
```json
{
  "snapshot_version": 1,
  "campaign_id": "dinastia_cinzas",
  "last_seq": 500,
  "recorded_at": "2026-10-24T12:00:00Z",
  "projection_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "state": {
    "protagonist": {
      "xp": 350,
      "level": 2,
      "vitals": {"hp": 24, "stamina": 18}
    },
    "clocks": {
      "Cerco da Fortaleza": {"current": 4, "max": 6, "status": "active"}
    },
    "quests": {
      "Q01": {"status": "ACTIVE", "completed_objectives": [0]}
    },
    "factions": {
      "CONSELHO_LORDES": {"score": 2, "favors": 1, "debts": 0}
    }
  }
}
```

---

## 6. Layout em Disco do R1 / Fase 02

```text
campaigns/<id>/
  events/
    000001.jsonl          # Segmento de até 1.000 eventos ou 1 MB (marcadores + eventos)
    000002.jsonl
  snapshots/
    000500.json           # Snapshots periódicos de estado
  projections/
    diario.md             # Projeção canônica
    ficha.md              # Projeção canônica
    npcs.md               # Projeção canônica
  artifacts/
    prose/
      turn_000001-<hash>.md  # Prosa imutável por turno
  queue.jsonl             # Fila esqueleto de tarefas
  index.sqlite            # Índice opcional/derivado reconstruível
  mundo.md                # Configuração estática da campanha
  regras.md               # Configuração estática da campanha
```
