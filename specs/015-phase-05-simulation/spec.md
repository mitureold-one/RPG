# Feature Specification: 015 — Fase 05: Simulação de Mundo por Tempo

**Feature Name:** `phase-05-simulation`
**Status:** Draft para revisão (planejamento; nenhum código de produção alterado)
**Created:** 2026-10-26
**Target:** Fase 05 do [`ROADMAP.md`](../../ROADMAP.md), gate [`G4`](g4-decision-record.md) e portas `SimulationPolicy`/`BudgetPolicy` do [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §6.1/§9.3
**Base Analisada:**
- [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 05), §5 (G4), §6.4 (R3), §7.2 (cenários 1, 4, 6 e 10)
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §6.1, §9.3 (`advance_world`), §12 (R3)
- [`g4-decision-record.md`](g4-decision-record.md) (decisões G4-D01 a G4-D15)
- [`specs/013-phase-04-causal-context/spec.md`](../013-phase-04-causal-context/spec.md) (cache `estado.json`, contexto causal)
- [`temporal/calendar.py`](../../temporal/calendar.py) e [`resources/clocks.py`](../../resources/clocks.py) (tempo e relógios atuais)
- [`resources/npcs/service.py`](../../resources/npcs/service.py) e [`resources/factions/service.py`](../../resources/factions/service.py) (planos projetados)

---

## 1. Contexto e Objetivo

As Fases 02–04 entregaram verdade causal, agentes com planos/conhecimento e contexto por relevância. O mundo, porém, só anda quando há turno narrado: `+7d` no diário move a data, mas relógios, planos de NPC e planos de facção ficam parados; não existe fila de trabalho atrasado, orçamento de ciclo, retry nem retomada idempotente.

A Fase 05 entrega o eixo temporal:

1. **`world_tick(elapsed_minutes)`** — o mundo avança por tempo, viagem, descanso, evento crítico ou agendamento, num único lote transacional.
2. **Avanço proporcional** — relógios e planos progridem conforme a cadência declarada, saturando no máximo e sem inventar desfecho.
3. **Profundidade seletiva** — só o que está devido recebe trabalho; o resto permanece silencioso e auditável.
4. **Fila persistente + orçamento** — o que não couber é adiado, nunca descartado, e retomado em ciclo posterior.
5. **Retry e falha auditada** — trabalho que não pode ser resolvido é registrado, tentado de novo com backoff e encerrado como falha permanente quando esgota.
6. **Agendamento futuro** — trabalho datado é validado e dispara exatamente na data declarada, com calendário customizado consistente.

O motor continua **sem chamar LLM**: o tick grava fatos temporais determinísticos, não prosa.

---

## 2. Escopo e Fronteiras Arquiteturais

### 2.1 Dentro do Escopo

1. **Portas e modelos** em `contracts/simulation.py`: `WorldView`, `WorkItem`, `TickRequest`, `TickBudget`, `TickDecision`, `SimulationPolicy`, `BudgetPolicy`.
2. **Políticas puras** em `plugins/`: `TimedSimulationPolicy` (trabalho devido) e `PriorityBudgetPolicy` (seleção sob orçamento, anti-inanição).
3. **Domínio em `resources/world/`**: cadências, resolução determinística de trabalho, projeção de fila e helpers de identidade.
4. **Caso de uso** `application/world_tick.py`: ler estado, montar `WorldView`, selecionar, resolver, gravar lote, reprojetar, auditar; `--dry-run` sem escrita.
5. **Projeções**: data canônica e seção `### Simulação de Mundo` em `diario.md`; `queue.json` com `pending`/`deferred`/`failed`/`scheduled` e hash.
6. **CLI** `world-tick`, `schedule` e `queue` (JSON e legível), com validação de propostas.
7. **Tempo canônico**: `minutes_to_game_time` e `advance_game_time` em `temporal/calendar.py`, com ida-e-volta para os três formatos de data.
8. **R3 (`world/` apenas)**: módulos `< 300` linhas, sem I/O em políticas, fronteiras AST atualizadas.
9. **Suíte de aceite C11–C17** e atualização do critério global de testes.

### 2.2 Fora de Escopo

- Direção narrativa, arcos flexíveis, estagnação e revelação (Fase 06 / G5).
- Memória derivada, indexação e resumos (Fase 07 / G6).
- Narração, prosa, chamada a LLM e concessão de XP/reputação/missão pelo tick.
- `world_tick` implícito em `prepare`/`commit`/`review`.
- Migração das campanhas reais e os 10 cenários de comportamento (Fase 08 / G7).
- Split de `council/reviewer.py` para `review/` (G4-D13 — Fase 06).
- Alteração de schema do `estado.json` ou do envelope de evento.

---

## 3. Requisitos Funcionais

| ID | Requisito | Fonte |
| :--- | :--- | :--- |
| **FR-SIM-01** | `world_tick(campaign, minutes | to, trigger, seed, budget, dry_run)` calcula `from_sort` do diário, `to_sort = from_sort + elapsed`, e a data final por calendário declarado, sem float. | G4-D02; ROADMAP Fase 05 |
| **FR-SIM-02** | Relógios `ACTIVE` avanzam `floor(elapsed / clock_step_minutes)` passos, saturam em `max` e viram `BREACHED` ao atingir o máximo; relógios `RESOLVED` não avançam. | G4-D03 |
| **FR-SIM-03** | Planos ativos de NPC e de facção avançam passos conforme `plan_step_minutes`; o último passo concluído não encerra o plano, que emite `plan_ready_for_resolution`. | G4-D03 |
| **FR-SIM-04** | Só entidades com trabalho devido recebem eventos; o tick retorna `selected`, `deferred`, `silent_entities` e contagens auditáveis. | G4-D09 |
| **FR-SIM-05** | O orçamento adaptativo (`max_items`, `max_items_per_day`, fórmula por dia, `--budget` como teto duro) seleciona trabalho por `(-priority_final, due_at_sort, work_id)`; o excedente é adiado com `budget_exhausted`. | G4-D06, G4-D07 |
| **FR-SIM-06** | `work_id` e `tick_id` são hashes canônicos determinísticos (o `tick_id` inclui a revisão da fila); trabalho com `world.work_completed` não reexecuta e reexecutar o mesmo alvo (`--to` já alcançado) não duplica efeito. | G4-D05, G4-D14 |
| **FR-SIM-07** | Falha de resolução grava `world.work_failed` com `attempts`, `error`, `retry_at_sort`; retry ocorre quando `to_sort >= retry_at_sort` até `max_attempts`, depois vira falha permanente. | G4-D08 |
| **FR-SIM-08** | `world.scheduled` valida `kind`, `entity`, `due_at_sort` e `priority` (1–100); proposta inválida grava `proposal.rejected` e não muta estado. | G4-D10 |
| **FR-SIM-09** | `world.ticked` projeta a data canônica no diário e a seção `### Simulação de Mundo`; `queue.json` projeta a fila com `schema_version`, `last_seq` e hash. | G4-D12 |
| **FR-SIM-10** | `minutes_to_game_time` e `advance_game_time` respeitam calendário declarado e garantem ida-e-volta nos formatos canônicos; salto de 30 dias em calendário 12×30 cai no dia correto do mês seguinte. | G4-D02 |
| **FR-SIM-11** | O tick reutiliza lock, snapshot transacional e `record_command_mutation`; falha no meio restaura diário/fila/projeções. | G4-D15 |
| **FR-SIM-12** | Módulos novos `< 300` linhas; políticas sem I/O; `application/prepare.py` não muda de comportamento; `tests/test_architecture_boundaries.py` cobre os novos arquivos. | ARCHITECTURE §12/§15 |
| **FR-SIM-13** | Nenhuma chave existente de `prepare`, `diario.md`, `ficha.md`, `npcs.md` ou `estado.json` é removida ou tem semântica alterada; mudanças são aditivas. | Fase 04; C3 |
| **FR-SIM-14** | `--dry-run` devolve o plano completo (work items, orçamento, datas, hashes) sem gravar evento, projeção ou fila; o log permanece com o mesmo `last_seq`. | G4-D15 |

---

## 4. Critérios de Aceitação (C11–C17)

- **C11 (Salto temporal):** `world-tick --minutes 10080` a partir de 01/10/300 10:00 produz data exata 08/10/300 10:00; relógio 3/4 com cadência diária vai a `BREACHED` com `current == max`; plano ativo avança passos conforme `plan_step_minutes`; diário e `queue.json` consistentes.
- **C12 (Causa off-screen):** todo evento de trabalho tem `correlation_id = tick_id`; `causation_id` aponta o `world.scheduled` quando o trabalho foi agendado e o `tick_id` lógico caso contrário, com o vínculo material ao `world.ticked` em `meta.dependencies`; nenhum evento de mundo aparece sem tick/agendamento que o origine.
- **C13 (Orçamento não apaga concluído):** com `--budget 1`, um item conclui e os demais são adiados; o `world.work_completed` permanece no log; um tick seguinte drena os adiados sem repetir o concluído.
- **C14 (Retomada idempotente):** reexecutar o mesmo alvo já alcançado (mesmo `--to`, `trigger`, `seed` e `budget`) não adiciona eventos nem altera `queue.json`; `selected=0`, `status=idempotent` e `last_seq` inalterado.
- **C15 (Calendário e agendamento):** em calendário 12×30, `+30d` a partir de 5 de Ventania cai em 5 de Geada; `+1a` cai no mesmo dia do ano seguinte; `world.scheduled` para uma data futura só dispara no tick cujo `to_sort` alcança `due_at_sort`, e o disparo é exatamente uma vez.
- **C16 (Profundidade seletiva):** entidade sem cadência vencida não gera evento; o relatório expõe `silent_entities`; um NPC sem plano ativo não recebe trabalho de plano.
- **C17 (Retry e proposta inválida):** trabalho cuja entidade desapareceu falha com `attempts` crescente e `retry_at_sort`; após `max_attempts` a falha é permanente e não há novo retry; `schedule` inválido gera `proposal.rejected`, zero eventos `world.*` e `last_seq` inalterado.

---

## 5. Modelo Conceitual

```text
TickRequest
├── campaign_id, from_game_time, from_sort, elapsed_minutes
├── trigger: time | travel | rest | critical_event | schedule | manual
├── seed, budget_override, dry_run
└── calendar (declarado), simulation config

WorldView
├── clocks, npcs, factions (de estado.json/diário)
├── planned_scenes, scheduled, deferred, failures, history (de eventos world.*)
└── from_sort, to_sort, elapsed_minutes, config

WorkItem
├── work_id, kind: clock_advance | npc_plan_step | faction_plan_step | scene_due | scheduled
├── entity_kind, entity_id, due_at_sort, priority, payload
└── deferrals, attempts

TickDecision
├── selected: tuple[WorkItem, ...]
├── deferred: tuple[WorkItem, ...]
└── budget: limit, used, remaining, adaptive
```

- **`WorkItem`** é imutável e serializável; `priority` é inteiro (1–100); `payload` é JSON canônico.
- **`SimulationPolicy`** é pura: recebe `WorldView` e devolve trabalho devido ordenado; não grava.
- **`BudgetPolicy`** é pura: recebe itens devidos + orçamento e devolve `TickDecision`.
- **Resolução** de cada item é função determinística de `(item, view)` → `(drafts, outcome)` ou `(erro, retry_at_sort)`.

---

## 6. Eventos e Projeções

| Evento | Papel | Projeção |
| :--- | :--- | :--- |
| `world.ticked` | avanço de tempo e ciclo | data canônica + `### Simulação de Mundo`; `queue.json.last_tick` |
| `world.scheduled` | agendamento validado | `queue.json.scheduled` |
| `world.work_deferred` | item adiado | `queue.json.deferred` |
| `world.work_completed` | trabalho resolvido | `queue.json` remove de pending; `diario.md` recebe linha do trabalho |
| `world.work_failed` | falha com backoff | `queue.json.failed` com `attempts`/`retry_at_sort` |

`estado.json` não muda de schema; `queue.json` é projeção derivada e reconstruível.

---

## 7. Decisões em Aberto (recomendações para aprovação)

| ID | Decisão | Recomendação |
| :--- | :--- | :--- |
| **D1** | Cadências padrão | `clock_step_minutes = 1440`, `plan_step_minutes = 2880`, configuráveis em `regras.md: simulation:` |
| **D2** | Limite adaptativo | `limit = min(max_items, 4 + elapsed//1440)`; `--budget` é teto duro; `max_items = 8` |
| **D3** | Retry | `max_attempts = 3`, `retry_backoff_minutes = 60`, erro determinístico |
| **D4** | Tipo do agendamento | Só `kind` conhecidos; `scene_due` sempre permitido; demais exigem entidade existente |
| **D5** | Nome do arquivo de fila | `queue.json` (não reutilizar `queue.jsonl` legado) |
| **D6** | Seção do diário | `### Simulação de Mundo`, inserida antes de `### Histórico de Turnos` |
| **D7** | `--dry-run` | Calcula `tick_id`/`work_id` e hash de fila previsto; não grava nada |

---

## 8. Critérios de Sucesso

1. **C11–C17 verdes** em `tests/test_phase05_world_tick.py`, com estado via `JsonlEventStore` + `rebuild_projections`.
2. **250 testes legados verdes**, inclusive snapshot de payload do `prepare` e rebuild C3.
3. **Determinismo:** dois ticks idênticos ⇒ mesmos eventos (ids e hashes) e nenhuma duplicação.
4. **Calendário:** ida-e-volta e saltos de 7/30/360 dias consistentes nos três formatos de data.
5. **Orçamento:** concluído nunca é apagado; adiado nunca é descartado.
6. **Fronteiras:** módulos novos `< 300`; políticas sem I/O; `lazy_turn.py < 200`.
7. **Zero invenção:** o tick não cria desfecho de passo, XP, reputação ou missão.

---

## 9. Riscos e Mitigações

| Risco | Mitigação |
| :--- | :--- |
| Tick virar "turno fictício" e fabricar causalidade | G4-D03/D09: só tempo como causa; `plan_ready_for_resolution` em vez de sucesso |
| Projeção de fila divergir do log | `queue.json` derivado por projector, com `last_seq` e hash; teste de rebuild |
| Duplicação em retomada | `work_id` determinístico + dedupe por `world.work_completed`; teste C14 |
| Calendário customizado quebrar em saltos | `minutes_to_game_time` com a mesma aritmética de `game_time_to_minutes`; testes C15 |
| Orçamento achatar a simulação | fórmulas declaradas, `silent_entities` auditáveis, boost anti-inanição |
| Crescimento de arquivos | domínio em módulos pequenos, CLI delegada, projeção separada |

---

## 10. Dependências e Gates

- **Depende de:** Fases 02 (log/projeções), 03 (planos e agentes) e 04 (contexto/cache), todas concluídas.
- **Gate próprio:** G4 — ratificado em 26/10/2026 ([`g4-decision-record.md`](g4-decision-record.md)).
- **Bloqueia:** Fase 06 (G5), que consome `queue.json`, `world.work_completed` e o relatório do tick.
- **R3:** entrega a parte `world/`; o split de `reviewer.py` fica para a Fase 06 (G4-D13).

---

## 11. Fora de Escopo Explícito (anti-scope creep)

- Não implementar diretor, estagnação, revelação ou arcos flexíveis.
- Não implementar memória derivada ou busca semântica.
- Não chamar LLM nem gerar prosa.
- Não alterar `commit`, `prepare`, envelope de evento ou `estado.json`.
- Não migrar campanhas reais nem escrever os 10 cenários da Fase 08.
