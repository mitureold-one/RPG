# G4 — Orçamento, Prioridade, Retry e Retomada da Simulação

**Projeto:** RPGPRO
**Fase de destino:** Fase 05 — Simulação
**Tipo:** Decision Record / Gate
**Status:** **Ratificado em 26/10/2026, com emendas**
**Ratifica:** decisão do dono de abrir a Fase 05 após a homologação da Fase 04 (`EX-0039`/`EX-0040`)
**Checklist:** [`checklists/g4-ratification.md`](checklists/g4-ratification.md)
**Implementação:** condicionada à [`spec.md`](spec.md), ao [`plan.md`](plan.md) e ao [`tasks.md`](tasks.md); este registro não altera código.

---

## 1. Contexto

A Fase 05 faz o mundo evoluir por tempo e por eventos. As Fases 02, 03 e 04 entregaram a verdade causal (event log, projeções, correções), o estado de agentes (NPCs, facções, conhecimento, admissão) e o contexto causal no `prepare`. Falta o eixo temporal: nada avança sem um turno narrado, planos e relógios não reagem a saltos de tempo, não existe fila de trabalho atrasado e o motor não sabe o que fazer quando o ciclo é interrompido.

O G4 é o dono exclusivo das decisões que a arquitetura deixou abertas em [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §1: valores de orçamento/fila, prioridade, retry, retomada e os limites de autonomia do tick. Sem essas decisões, a Fase 05 produziria um scheduler implícito, não determinístico e não auditável.

**Princípio que governa o gate:** o mundo continua sem o protagonista, mas o motor só registra o que pode justificar. Tempo decorrido é uma causa; tempo decorrido não é resultado de plano, de missão ou de conflito.

---

## 2. Decisões ratificadas

### G4-D01 — O tick é explícito, causal e único

- `world_tick(elapsed_minutes)` é o único mecanismo de avanço autônomo do mundo.
- O tick é acionado por: **tempo** (salto declarado), **viagem**, **descanso**, **evento crítico** ou **agendamento**; o acionador é registrado no evento (`trigger`).
- Não existe tick implícito em `prepare`, `commit`, `review` ou leitura de projeção.
- Um tick é um lote transacional único: ou todo o trabalho selecionado é gravado, ou nada é.
- O tick nunca narra, nunca cria prosa e nunca chama LLM.

### G4-D02 — Tempo canônico em minutos inteiros

- A unidade canônica é **minuto inteiro** desde a época da campanha (`game_time_sort`).
- O calendário declarado em `regras.md` (`calendar:`) é a autoridade para converter minutos em data; sem calendário, valem 12 meses de 30 dias para datas nomeadas e 365/30 para datas numeradas, exatamente como em [`temporal/calendar.py`](../../temporal/calendar.py).
- `float` é proibido em tempo, orçamento e prioridade.
- Data final do tick é **derivada** de `início + elapsed_minutes`; não é digitada pela IA.
- Ida-e-volta obrigatória: `minutes_to_game_time(game_time_to_minutes(t)) == t` para os formatos canônicos (`Dia N, HH:MM`, `DD/MM/AAAA, HH:MM`, `D de Mês de AAAA, HH:MM`).

### G4-D03 — Avanço proporcional com cadência declarada

- Relógios: `delta = floor(elapsed_minutes / clock_step_minutes)`; mínimo 0; saturação em `max`; ao atingir `max` o relógio fica `BREACHED` (ruptura é fato, não sucesso do protagonista).
- Planos de NPC e de facção: `delta_steps = floor(elapsed_minutes / plan_step_minutes)`; passos avançam de `pending` para `in_progress` e de `in_progress` para `completed` **pelo tempo declarado**, nunca por narração do motor.
- O último passo concluído **não encerra o plano**: o plano permanece `active` e o trabalho entrega o fato `plan_ready_for_resolution`, para que a agência (Fase 03/06) decida o desfecho.
- Cadências padrão: `clock_step_minutes = 1440` (1 passo/dia) e `plan_step_minutes = 2880` (1 passo/2 dias), configuráveis no bloco `simulation:` de `regras.md`.
- Avanço é proporcional ao tempo decorrido, não ao número de turnos; saltos longos não são fatiados em turnos fictícios.

### G4-D04 — Fila persistente derivada do log

- A fila de trabalho é derivada de eventos `world.*` (ver G4-D11); `queue.json` é **projeção** inspecionável, com `schema_version`, `last_seq` e `hash`.
- Não existe store paralelo, banco de fila ou `queue.jsonl` concorrente como verdade (coerente com G3-D13 e [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §2/D1).
- `queue.jsonl` legado permanece apenas como artefato histórico da Fase 02; a Fase 05 não o utiliza como fonte.
- Item adiado nunca é descartado: ele permanece com o mesmo `work_id` até ser executado ou falhar permanentemente.

### G4-D05 — Identidade determinística do trabalho

- `work_id = "wrk_" + sha256("kind|entity_kind:entity_id|due_at_sort|payload_canônico")[:26]`.
- O mesmo estado e o mesmo tick produzem os mesmos `work_id`s; replay e retomada são reconhecidos por identidade.
- Trabalho com `world.work_completed` registrado **nunca** é reexecutado, mesmo que o estado volte a parecer devido.
- O tick inteiro também tem identidade `tick_id = "tck_" + sha256(campanha|from_sort|to_sort|trigger|seed|queue_revision)[:26]`, usada para auditoria e para explicar por que uma reexecução é idempotente.

### G4-D06 — Orçamento adaptativo, com teto duro

- Limites: `max_items` (padrão 8), `max_items_per_day` (padrão 6) e `max_depth` (profundidade de avaliação, padrão 2), configuráveis em `simulation:`.
- Limite adaptativo do ciclo: `limit = min(max_items, 4 + floor(elapsed_minutes / 1440))`; saltos de 7 dias podem executar até 8 itens.
- `--budget N` explícito é teto duro e vence a fórmula.
- O que não couber é **adiado** com motivo `budget_exhausted`, nunca descartado nem resumido como "concluído".
- Estouro de orçamento não invalida evento já concluído no mesmo lote nem apaga histórico.

### G4-D07 — Prioridade determinística e anti-inanição

- Prioridade base por tipo: `scene_due = 60`, `clock_advance = 50`, `faction_plan_step = 40`, `npc_plan_step = 30`, `scheduled = payload.priority` (padrão 50).
- Itens adiados recebem `priority_final = base + min(deferrals, 5)`, garantindo que trabalho antigo não morra no fim da fila.
- Ordenação total e estável: `(-priority_final, due_at_sort, work_id)`.
- Não há prioridade "subjetiva" decidida pela IA: a IA pode **agendar** prioridade explícita em `world.scheduled`; não pode reordenar a fila em tempo de execução.

### G4-D08 — Retry com backoff e falha permanente auditada

- Falha de resolução produz `world.work_failed` com `attempts`, `error` determinístico e `retry_at_sort = to_sort + retry_backoff_minutes * attempts`.
- Padrões: `max_attempts = 3`, `retry_backoff_minutes = 60`.
- Enquanto `attempts < max_attempts`, o item é re-derivado no próximo tick quando `to_sort >= retry_at_sort`; ao esgotar, a falha é permanente e o item sai da fila ativa.
- Retry nunca repete efeito já concluído; falha nunca apaga trabalho concluído.
- `world.work_failed` preserva `kind`, `entity_kind`, `entity_id` e `payload` para re-derivação auditável.

### G4-D09 — Profundidade seletiva: só o devido é avaliado

- Nenhuma entidade recebe avaliação porque existe; só recebe trabalho o que está **devido** (cadência vencida, agendamento vencido, relógio ativo, passo pendente).
- A simulação não produz resultado de passo, não decide conflito, não concede XP e não altera reputação; essas são consequências de resolução (Fase 02/03) ou de direção (Fase 06).
- Entidade sem trabalho devido não gera evento algum; o silêncio é auditável e esperado.

### G4-D10 — Gatilhos da IA são propostas validadas

- A IA pode acionar tick (`--trigger`) e agendar trabalho (`schedule`); ambos são **propostas**, nunca fatos.
- Validação: `kind` conhecido, `entity` existente (quando aplicável), `due_at_sort` futuro ou igual ao início, `payload` JSON serializável e canônico, prioridade 1–100.
- Proposta inválida ⇒ `proposal.rejected` (tipo existente da Fase 03) com motivos, zero mutação de estado, zero evento de mundo.
- A IA não pode declarar sucesso de trabalho, criar trabalho já concluído nem rebaixar prioridade de item devido.

### G4-D11 — Catálogo de eventos da simulação (5 tipos novos)

| Tipo | Obrigatórios | Papel |
| :--- | :--- | :--- |
| `world.ticked` | `tick_id`, `from_game_time`, `to_game_time`, `elapsed_minutes`, `trigger`, `budget_limit`, `selected`, `deferred` | fato do avanço de tempo e do ciclo |
| `world.scheduled` | `work_id`, `kind`, `entity_kind`, `entity_id`, `due_game_time`, `due_at_sort`, `priority` | agendamento futuro validado |
| `world.work_deferred` | `work_id`, `kind`, `due_at_sort`, `reason`, `deferrals` | item adiado por orçamento ou falha transitória |
| `world.work_completed` | `work_id`, `kind`, `outcome` | trabalho resolvido deterministicamente |
| `world.work_failed` | `work_id`, `kind`, `error`, `attempts`, `retry_at_sort` | falha auditável com backoff |

Regras: `schema_version = 1`, upcasters vazios na Fase 05, payloads validados pelo catálogo v1, ordem de lote `world.ticked` → trabalho → agendamentos do ciclo.

### G4-D12 — Projeções e SSOT

- `world.ticked` atualiza a data canônica em `diario.md` (linha `Data & Local`) e registra o ciclo em `### Simulação de Mundo`; a data é o `ev.game_time` do tick.
- `queue.json` (projector dedicado, ordem 60) projeta `pending`, `deferred`, `failed`, `scheduled` e o último tick, com hash canônico; é leitura operacional, não verdade.
- `estado.json` **não muda de schema** na Fase 05; `prepare` continua consumindo o cache da Fase 04.
- `diario.md`, `npcs.md`, `ficha.md` continuam projeções; nenhum comando novo escreve Markdown diretamente.

### G4-D13 — R3 da Fase 05: `world/` agora, `review/` na Fase 06

- A Fase 05 entrega a parte de `world/` do R3: portas `SimulationPolicy`/`BudgetPolicy`, implementações em `plugins/`, regras em `resources/world/` e projeção de fila.
- O split de `council/reviewer.py` para `review/` fica para a Fase 06, junto de `DirectorPolicy`/`StagnationPolicy`, porque compartilha o mesmo ponto de entrada de auditoria e a Fase 05 não deve misturar refatoração de prosa com semântica nova de simulação.
- Nenhum módulo novo passa de 300 linhas; `interfaces/cli/main.py` delega comandos novos a `interfaces/cli/world_cli.py`.

### G4-D14 — Determinismo e replay

- Sem aleatoriedade: `seed` existe no contrato para extensões futuras, mas a política padrão é determinística e ignora o seed.
- Dois ticks com o mesmo estado, mesmo `elapsed_minutes` e mesmos parâmetros produzem os mesmos `tick_id`, `work_id`s e o mesmo conjunto de drafts.
- `world.work_completed` grava o resultado estruturado do trabalho, de modo que replay não reexecuta a decisão.
- Rebuild de projeção a partir do log é byte-idêntico ao rebuild completo (C3 preservado).

### G4-D15 — Falha explícita e limite de autonomia

- Erros de campanha, calendário, configuração ou entidade são devolvidos como erro tipado; nunca como tick vazio silencioso.
- `--dry-run` calcula o plano de trabalho e o orçamento sem gravar evento, projeção ou fila.
- O tick respeita o lock de campanha e o snapshot transacional existentes; falha no meio restaura o estado anterior.
- A Fase 05 **não** implementa: narração, diretor, estagnação, revelação, memória derivada, chamada a LLM, alteração de XP/reputação/missão e migração de campanhas.

---

## 3. Fronteiras arquiteturais

```text
contracts/simulation.py     WorkItem, TickRequest, TickBudget, TickDecision,
                            SimulationPolicy, BudgetPolicy, WorldView
plugins/simulation_policy.py  TimedSimulationPolicy (puro, sem I/O)
plugins/budget_policy.py      PriorityBudgetPolicy (puro, sem I/O)
resources/world/              regras de cadência, resolução de trabalho, fila projetada
application/world_tick.py     orquestração transacional do ciclo
application/projectors/world.py  projeção de diario.md e queue.json
interfaces/cli/world_cli.py   despacho de world-tick, schedule e queue
```

O G4 não implementa a Fase 06, não altera `commit`/`prepare`, não muda o envelope do evento e não cria store paralelo.

---

## 4. Critérios de aceitação do gate

- **AT-G4-01:** `+7d` a partir de um estado com relógio 3/4 e plano ativo avança relógio e passos proporcionalmente, e a data final é exatamente `início + 10080 min`.
- **AT-G4-02:** com `--budget 1`, o primeiro item é concluído, os demais são adiados, e os eventos concluídos permanecem no log.
- **AT-G4-03:** reexecutar o mesmo tick (mesmo tempo e parâmetros) não duplica `world.work_completed`; um novo tick drena o que foi adiado sem repetir o concluído.
- **AT-G4-04:** trabalho que falha é registrado com `attempts` e `retry_at_sort`; ao esgotar `max_attempts`, vira falha permanente auditável.
- **AT-G4-05:** `schedule` com `kind` desconhecido, entidade inexistente ou data inválida gera `proposal.rejected` e zero mutação.
- **AT-G4-06:** calendário declarado 12×30 permanece consistente em salto de 30 dias e em salto de 1 ano; agendamento futuro dispara exatamente em `due_at_sort`.
- **AT-G4-07:** dois ticks idênticos produzem os mesmos `tick_id`/`work_id`s e o mesmo hash de `queue.json`.
- **AT-G4-08:** entidade sem cadência vencida não gera evento; profundidade seletiva é observável na contagem de eventos por tick.

Cada critério deve ser verificável por teste automatizado com estado construído via `JsonlEventStore` + `rebuild_projections`; qualidade de prosa não é critério.

---

## 5. Condições de implementação

1. Este G4 está ratificado; a Fase 05 pode ser especificada e implementada.
2. `spec.md`, `plan.md` e `tasks.md` da spec 015 precedem qualquer código de produção.
3. Os 5 eventos novos entram no catálogo v1 com schema validado e sem upcaster.
4. Nenhum commit da fase mistura refatoração de `reviewer.py` (G4-D13).
5. `EXECUCAO.md` recebe entrada ao final da implementação, com evidência observável.
6. A Fase 06 continua bloqueada pelo G5 e não recebe trabalho desta fase.

---

## 6. Registro de ratificação

Ratificado em 26/10/2026, na abertura da Fase 05 autorizada pelo dono, com as emendas G4-D03 (cadência declarada), G4-D06 (teto duro + adaptativo), G4-D08 (backoff e falha permanente), G4-D11 (catálogo mínimo de 5 eventos) e G4-D13 (R3 faseado). O checklist item a item está em [`checklists/g4-ratification.md`](checklists/g4-ratification.md).

**Relações:** [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 05) e §5 (G4); [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §6.1, §9.3 e §12 (R3); [`specs/012-phase-03-agents/g3-decision-record.md`](../012-phase-03-agents/g3-decision-record.md) (fronteira do scheduler); [`EXECUCAO.md`](../../EXECUCAO.md).
