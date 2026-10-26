# Implementation Plan: 015 — Fase 05: Simulação de Mundo por Tempo

**Feature:** `phase-05-simulation`
**Spec:** [`spec.md`](spec.md) · **Gate:** [`g4-decision-record.md`](g4-decision-record.md) · **Data model:** [`data-model.md`](data-model.md) · **Contracts:** [`contracts/p5-simulation-contracts.md`](contracts/p5-simulation-contracts.md)
**Status:** Aprovado para implementação (G4 ratificado)
**Created:** 2026-10-26

---

## 1. Estratégia

O eixo temporal é novo, mas o repertório é o existente: evento é verdade, projeção é derivada, comando é transacional e determinístico. A Fase 05 se apoia em três decisões estruturais:

1. **Tempo é dado, não relógio de parede.** Todo avanço é `from_sort + elapsed_minutes`; `int` sempre.
2. **Fila é projeção.** `queue.json` deriva de `world.*`; não há store paralelo (G4-D04). Isso mantém replay, rebuild e correção funcionando sem exceção.
3. **Trabalho é identidade + resultado.** `work_id` determinístico garante retomada sem duplicar; `world.work_completed` grava o resultado, então replay não decide de novo (G4-D05/D14).

O tick é um comando como outro qualquer: lock de campanha, snapshot transacional, lote único no `EventStore`, rebuild de projeções. `--dry-run` executa tudo menos a escrita.

---

## 2. Arquitetura de Módulos

```text
contracts/
  simulation.py              ~288  WorldView, WorkItem, TickRequest, TickBudget,
                                   TickDecision, WorkOutcome, SimulationPolicy, BudgetPolicy
  simulation_rules.py        ~106  helpers puros: active_plan_of, plan_has_open_steps,
                                   steps_for_elapsed, build_item (id canônico)
  catalog.py                 +40   5 schemas world.* (sem upcaster)
temporal/
  calendar.py                +170  minutes_to_game_time, advance_game_time, validate_game_time
resources/world/
  config.py                   ~76   bloco simulation: + defaults + TickBudget
  ids.py                      ~63   work_id/tick_id determinísticos
  cadence.py                 ~100   deltas proporcionais, saturação, plan_progress
  drafts.py                  ~204   fábricas de EventDraft (tick, trabalho, agendamento, rejeição)
  queue.py                   ~169   agregação dos eventos world.* (índice + merge pós-snapshot)
  workqueue.py               ~189   adiados/agendados/retry + documento queue.json
  resolve.py                 ~298   resolução pura por kind → drafts/outcome/erro
plugins/
  simulation_policy.py       ~138   TimedSimulationPolicy.due(view)
  budget_policy.py            ~43   PriorityBudgetPolicy.select
application/
  world_tick.py              ~274   orquestração transacional, relatório, dry-run
  world_schedule.py          ~212   schedule validado e leitura da fila (queue)
  projectors/queue.py         ~55   queue.json
  projectors/world_journal.py ~85   seção ### Simulação de Mundo e data canônica
  projectors/journal.py      +2     delega eventos world.* ao world_journal
  rebuild.py                 +2     registra QueueProjector (ordem 60)
interfaces/cli/
  world_cli.py               ~110   dispatch de world-tick, schedule e queue
  parser.py                  +40    três subcomandos
  main.py                    +6     delega a world_cli
tests/
  test_phase05_world_tick.py ~430   C11–C17
  test_phase05_policies.py   ~230   contratos puros de política, cadência e tempo
```

Regras: `plugins/` sem I/O e sem importar `resources`; `resources/world/` sem CLI/aplicação; todo arquivo `< 300` linhas; `lazy_turn.py` continua `< 200`.

---

## 3. Fluxo do `world_tick`

```text
cmd_world_tick(campaign, minutes|to, trigger, seed, budget, dry_run)
  ├── find_campaign + ensure_campaign_event_log          (transação/lock)
  ├── diario = parse_diario_md → from_game_time, clocks, planos
  ├── from_sort = game_time_to_minutes(from_game_time, calendar)
  ├── to_sort   = from_sort + elapsed                    (ou to explícito)
  ├── to_game_time = minutes_to_game_time(to_sort, from_game_time, calendar)
  ├── state = ContextStateViewImpl.load(...)             (estado.json fresco)
  ├── world_events = store.read() filtrado por "world."
  ├── view = WorldView(state, world_events, config, from/to)
  ├── due = TimedSimulationPolicy().due(view)            (puro)
  ├── decision = PriorityBudgetPolicy().select(due, budget)
  ├── drafts = [world.ticked] + resolve(selected) + deferred
  ├── dry_run → relatório sem append (mesmo tick_id/work_ids)
  ├── record_command_mutation(drafts)                    (append + rebuild)
  └── relatório: selected, deferred, silent_entities, budget, queue_hash
```

### 3.1 Regras de resolução por `kind`

| kind | Pré-condições | Efeito | Falha |
| :--- | :--- | :--- | :--- |
| `clock_advance` | relógio existe e `ACTIVE` | `clock.advanced` com `current` saturado; `clock.resolved` se `BREACHED` | relógio ausente/resolvido ⇒ falha transitória |
| `npc_plan_step` | NPC com plano `active` e passo não concluído | `npc.plan_updated` com statuses avançados; `plan_ready_for_resolution` no último | plano inativo/ausente ⇒ falha |
| `faction_plan_step` | facção com plano `active` | `faction.plan_updated` equivalente | idem |
| `scene_due` | agendamento existente | `world.work_completed` com `outcome.scene_due` | payload inválido ⇒ falha permanente |
| `scheduled` | `world.scheduled` válido e vencido | resolve pelo `kind` interno | idem |

### 3.2 Idempotência

- `tick_id` inclui `queue_revision` (contagem de eventos `world.*`); reexecução idêntica devolve `status=idempotent` quando não há trabalho novo e nenhum item concluído a repetir.
- Antes de selecionar, a política remove `work_id`s com `world.work_completed`; se o conjunto devido resultar vazio e `elapsed == 0`, o comando não grava nada.

---

## 4. Orçamento e Prioridade

```text
limit = min(max_items, 4 + elapsed_minutes // 1440)   # adaptativo por dia
limit = budget_override se informado                  # teto duro
priority_final = base[kind] + min(deferrals, 5)       # anti-inanição
ordem = (-priority_final, due_at_sort, work_id)
```

- `base`: `scene_due 60`, `clock_advance 50`, `scheduled 50`, `faction_plan_step 40`, `npc_plan_step 30`.
- `deferred` herda `work_id` e incrementa `deferrals`; o próximo tick o recoloca no topo da faixa.
- `remaining == 0` não é erro: é o comportamento esperado sob orçamento.

---

## 5. Retry e Falha

1. Falha ⇒ `world.work_failed` com `attempts = anteriores + 1`, `error` estável e `retry_at_sort = to_sort + backoff * attempts`.
2. `due()` inclui falhas com `retry_at_sort <= to_sort` e `attempts < max_attempts`, respeitando o `payload` original.
3. Esgotado `max_attempts`, o item não é mais derivado; `queue.json.failed` o marca `permanent: true`.
4. Falha nunca remove `world.work_completed` anterior do mesmo `work_id` (não há trabalho concluído que falhe depois).

---

## 6. Projeções

### 6.1 `diario.md`

- `world.ticked`: atualiza `Data & Local` (data = `ev.game_time`, local preservado) e acrescenta linha em `### Simulação de Mundo`:
  `* **Tick <tick_id>:** +<elapsed> min (<from> → <to>) | <selected> executados, <deferred> adiados.`
- `world.work_completed`: linha `* **<kind>** <entity_id>: <resumo determinístico> (<tick_id>)`.
- Seção inserida antes de `### Histórico de Turnos`; idempotente no rebuild (replay a partir do baseline).

### 6.2 `queue.json`

```json
{
  "schema_version": 1,
  "last_seq": 42,
  "hash": "sha256:...",
  "last_tick": {"tick_id": "...", "to_game_time": "...", "selected": 3, "deferred": 1},
  "pending": [{"work_id": "...", "kind": "...", "entity_id": "...", "due_at_sort": 123, "priority": 50, "deferrals": 0}],
  "deferred": [],
  "failed": [{"work_id": "...", "attempts": 2, "retry_at_sort": 456, "error": "...", "permanent": false}],
  "scheduled": [{"work_id": "...", "due_game_time": "...", "due_at_sort": 789, "kind": "scene_due"}]
}
```

Listas ordenadas por `(-priority, due_at_sort, work_id)`; `hash` sobre o JSON canônico sem o próprio hash.

---

## 7. CLI

```text
python lazy_turn.py world-tick --campaign <id> --minutes 10080 [--trigger time|travel|rest|critical_event|manual]
                             [--to "<data>"] [--budget N] [--seed N] [--dry-run] [--json]
python lazy_turn.py schedule --campaign <id> --at "<data>" --kind scene_due|clock_advance|npc_plan_step|faction_plan_step
                             --entity <id> [--payload k=v ...] [--priority N] [--json]
python lazy_turn.py queue --campaign <id> [--json]
```

- `world-tick` sem `--minutes` e sem `--to` ⇒ erro explícito (evita tick implícito).
- `--to` anterior ao início ⇒ erro de validação.
- `schedule` com entidade inexistente (exceto `scene_due`) ⇒ `proposal.rejected`.
- `queue` lê `queue.json`; se ausente/velho, reconstrói via `rebuild` antes de exibir.

---

## 8. Configuração (`regras.md`)

```yaml
simulation:
  clock_step_minutes: 1440
  plan_step_minutes: 2880
  max_items: 8
  max_items_per_day: 6
  retry_backoff_minutes: 60
  max_attempts: 3
```

`campaign/locator.py` passa a expor `simulation` em `find_campaign`/manifesto com defaults conservadores; ausência do bloco não quebra campanhas existentes.

---

## 9. Fases de Execução

| Fase | Entrega | Critério de saída |
| :--- | :--- | :--- |
| **P0** | Baseline: 250 testes verdes; worktree limpo; G4 + spec aprovados | baseline registrado |
| **P1** | `contracts/simulation.py`, 5 schemas em `catalog.py`, `temporal` ida-e-volta | testes puros de contrato e calendário |
| **P2** | `resources/world/{cadence,ids,queue,config,resolve}` + testes unitários | resolução determinística sem I/O |
| **P3** | `plugins/{simulation_policy,budget_policy}` + contrato de portas | C13/C16 verdes em isolamento |
| **P4** | `WorldProjector` (`diario.md` + `queue.json`) e registro no rebuild | rebuild byte-idêntico; hash estável |
| **P5** | `application/world_tick.py` + relatório + `--dry-run` | C11/C12/C14 verdes |
| **P6** | CLI `world-tick`/`schedule`/`queue` + validação de proposta | C15/C17 verdes |
| **P7** | Fronteiras, quickstart, limites de linha | AST verdes; módulos `< 300` |
| **P8** | `EXECUCAO`, `ROADMAP`, `ARCHITECTURE`; suíte completa | 250+novos verdes; commit |

---

## 10. Testes

- **C11:** salto de 7 dias com relógio e plano; datas exatas; diário atualizado.
- **C12:** matriz de causas: todo trabalho tem `tick_id` em `correlation_id`; agendamento tem `causation_id` do `world.scheduled`.
- **C13:** `--budget 1`; concluído persiste; adiados em `queue.json`; drenagem posterior.
- **C14:** reexecução byte-idêntica de `queue.json` e `last_seq`; `status=idempotent`.
- **C15:** calendário 12×30; `+30d`, `+1a`; agendamento exato e disparo único.
- **C16:** entidade sem cadência vencida não gera evento; `silent_entities` no relatório.
- **C17:** falha com backoff, esgotamento e `proposal.rejected` sem mutação.
- Testes puros de política (ordenação, starvation, teto duro) em `test_phase05_policies.py`.
- Regressão: suíte integral + `test_architecture_boundaries` + `test_boundary_contracts`.

---

## 11. Riscos e Mitigações

| Risco | Mitigação |
| :--- | :--- |
| Projeção de fila ficar inconsistente no rebuild | projector determinístico com `last_seq` e hash; teste de rebuild C3 com 500 eventos |
| Dedupe mascarar trabalho legítimo | `work_id` inclui `due_at_sort` e payload; teste de dois ticks consecutivos |
| Calendário customizado divergir | mesma aritmética de `game_time_to_minutes`; testes de ida-e-volta |
| Tick consumir tempo demais | orçamento e limites; `--dry-run` para inspeção; telemetria no relatório |
| Refatoração R3 escapar do escopo | `review/` explicitamente fora (G4-D13) |

---

## 12. Decisões Pendentes de Aprovação

Ver `spec.md` §7 (D1–D7). O plano assume as recomendações; mudanças afetam apenas constantes e nomes, não a arquitetura.

---

## 13. Definição de Pronto

- C11–C17 verdes; suíte integral verde; fronteiras verdes.
- `world-tick`, `schedule` e `queue` funcionais em JSON e legível.
- `queue.json` reconstruível e com hash estável.
- `--dry-run` sem escrita comprovado por `last_seq` inalterado.
- Módulos novos `< 300` linhas; políticas sem I/O.
- `quickstart.md` reproduzível; `EXECUCAO.md` e `ROADMAP.md` atualizados.
