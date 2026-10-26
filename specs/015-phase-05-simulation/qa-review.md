# QA Review — Fase 05: Simulação de Mundo por Tempo

**Feature:** `phase-05-simulation` · **Gate:** [`G4`](g4-decision-record.md) · **Spec:** [`spec.md`](spec.md)
**Status:** **APROVADO** na re-auditoria independente de 26/10/2026 ([§6](#6-re-auditoria-independente)). O histórico abaixo registra a primeira auditoria, que foi interrompida antes do parecer; a homologação está em `EX-0044`.
**Regra de governança:** este documento não declara aprovação por conta própria. O veredito final é o da re-auditoria independente (§6).

---

## 1. Escopo auditado

`contracts/simulation.py`, `contracts/simulation_rules.py`, `contracts/catalog.py` (5 eventos `world.*`), `temporal/calendar.py` (`minutes_to_game_time`, `advance_game_time`, `validate_game_time`), `resources/world/` (config, ids, cadence, drafts, queue, workqueue, resolve, state), `plugins/{simulation_policy,budget_policy}.py`, `application/{world_tick,world_schedule}.py`, `application/projectors/{queue,world_journal}.py`, `application/transaction.py`, `interfaces/cli/`, `tests/test_phase05_world_tick.py`, `tests/test_phase05_policies.py`.

## 2. Achados

| ID | Gravidade | Achado | Evidência | Status |
| :--- | :---: | :--- | :--- | :--- |
| **P0-1** | P0 | Vários itens do mesmo ciclo resolviam contra a mesma visão congelada. Com débito adiado + trabalho novo na mesma entidade, o evento mais recente regredia o estado: relógio `Beta` terminava `4/10 ACTIVE` (deveria ser `10/10 BREACHED`) e planos voltavam de `[completed, in_progress, pending]` para `[in_progress, pending, pending]`. | `probe_qa5_tick.py` §D → `out_tick.txt` `deferred_plus_new_same_tick` | **Corrigido** (`resources/world/state.py`; resolução sequencial com estado atualizado) |
| **P1-1** | P1 | Reagendar trabalho idêntico levantava `DuplicateBatchError` (traceback) em vez de resposta idempotente. | `probe_qa5_tick.py` §F → `out_tick.txt` `duplicate_schedule` | **Corrigido** (`cmd_schedule` detecta `already_scheduled`/`already_completed`; defesa contra `DuplicateBatchError`) |
| **P2-1** | P2 | `queue.json` ordenava por `priority` bruto, divergindo da seleção (`priority_final`). | `probe_qa5_budget.py` → `queue_order_vs_selection` (50/46 vs 60/55) | **Corrigido** (`workqueue.queue_document` inclui e ordena por `priority_final`) |
| **P2-2** | P2 | `max_depth` era aceito na configuração e ignorado no comportamento (nenhum efeito na seleção). | `probe_qa5_budget.py` → `max_depth_effect.equal = true` | **Corrigido por remoção** (`G4-D06` emendado: profundidade de avaliação pertence à Fase 06) |
| **P2-3** | P2 | `game_time_to_minutes` com calendário declarado e mês fora da lista caía silenciosamente no índice 0 (Janeiro/Ventania), gerando data errada sem erro. | `probe_qa5_time.py` → `roundtrip` caso `named_cal2` (`30 de Solsticio` ≠ `Solstício`) | **Corrigido** (`game_time_to_minutes` levanta `ValueError`; `validate_game_time` já cobria tick/schedule) |
| **P3-1** | P3 | `event_ids_equal: false` entre duas campanhas idênticas. | `out_tick.txt` `determinism` | **Não é defeito**: `evt_<ulid>` é identidade única por persistência; tick ids, work ids, payloads e hash da fila são idênticos. |
| **P3-2** | P3 | `world.ticked.causation_id = null`. | `out_causality.txt` | **Por desenho**: o tick é a raiz do ciclo; o vínculo material é `meta.dependencies` para o evento anterior e `correlation_id = tick_id` para os descendentes. |

## 3. O que passou na verificação

- **Determinismo de conteúdo:** `tick_id`, work ids, payloads de `world.*` e bytes/hash de `queue.json` idênticos entre campanhas equivalentes.
- **Idempotência após drenagem:** reexecutar `--to` já alcançado devolve `status=idempotent`, zero eventos e fila byte-idêntica.
- **Teto duro de orçamento:** `--budget 1/3/8/20` nunca executa mais que o teto; o excedente vira `world.work_deferred`; concluídos persistem.
- **Entradas inválidas:** `--budget <= 0`, `trigger` fora do enum e `seed` não inteiro devolvem erro explícito sem evento.
- **Calendário:** `+7d/+30d/+360d` consistentes em 12×30; mês nomeado sem calendário falha explícita nos três caminhos (tick, schedule, `validate_game_time`); formatos `Dia N`, `DD/MM/AAAA` e `D de Mês de AAAA` preservam formato.
- **Causalidade:** dependências intra-lote apontam para o evento anterior real; trabalho agendado causa no `world.scheduled`; trabalho derivado usa `tick_id` e `correlation_id`.
- **Persistência:** `world.work_completed` sobrevive a `rebuild --force` com auditoria; uma cena devida dispara exatamente uma vez; `queue.json` mantém hash após rebuild.
- **Retry:** `attempts` cresce, `retry_at_sort` respeita backoff, falha esgota em `permanent` e a prioridade original é preservada.
- **Fronteiras:** módulos novos `< 300` linhas, políticas sem I/O, `lazy_turn.py < 200`.

## 4. Evidência de execução

- `python -m unittest tests.test_phase05_world_tick tests.test_phase05_policies` -> 32 testes OK.
- `python -m unittest discover -s tests -p "test_*.py"` -> suíte completa verde (contagem em `EX-0043`).
- `python -m unittest tests.test_architecture_boundaries` -> 8 testes OK.
- Sondas reexecutadas: `.tmp/probe_qa5_tick.py` (estado monotônico, agenda idempotente), `.tmp/probe_qa5_budget.py` (ordem da fila = seleção), `.tmp/probe_qa5_smoke.py` (diário e seção de simulação).

## 5. Pendências

1. **Re-auditoria independente** por agente novo: reexecutar sondas e a suíte, confirmar os cinco achados fechados e emitir veredito final sem autodeclaração do implementador.
2. Se a re-auditoria apontar resíduo, nova remediação e nova entrada em `EXECUCAO.md`.
3. `review/` continua fora da Fase 05 por decisão G4-D13 (Fase 06).

## 6. Re-auditoria independente

**Data:** 26/10/2026 · **Auditor:** agente independente (re-auditoria) · **Objeto:** Fase 05 (`specs/015-phase-05-simulation/`).

Este parecer substitui o status histórico do cabeçalho; o registro da auditoria interrompida permanece como histórico.

### 6.1 Comandos e contagens

| Comando | Resultado |
| :--- | :--- |
| `python -m unittest tests.test_phase05_world_tick tests.test_phase05_policies` | **32 testes OK** (5,3 s; 0 falhas, 0 erros) |
| `python -m unittest tests.test_phase05_world_tick tests.test_phase05_policies tests.test_architecture_boundaries` | **40 testes OK** (6,4 s; 0 falhas, 0 erros) |
| `python -m unittest discover -s tests -p "test_*.py"` | **282 testes OK** (74,97 s; 0 falhas, 0 erros) |
| `.tmp/probe_qa5_tick.py` | JSON integral; `deferred_plus_new_same_tick` e `duplicate_schedule` conferidos |
| `.tmp/probe_qa5_budget.py` | teto duro 1/3/8/20; `max_depth` inerte; fila = seleção |
| `.tmp/probe_qa5_smoke.py` | tick `+10080 min`, 3 `world.work_completed`, diário e hash de fila |
| `.tmp/probe_reauth_state.py` | `ok=true`; `clock_violations=[]`, `plan_violations=[]` |
| `.tmp/probe_reauth_dupe.py` | `already_scheduled`, 1 conclusão, `idempotent`, hash de rebuild igual |

### 6.2 Situação dos cinco achados

| ID | Status | Evidência |
| :--- | :---: | :--- |
| **P0-1** | **Fechado** | `.tmp/probe_reauth_state.py`: `Alfa` 9→10 e `Beta` 9→10; final `Alfa 10/10 BREACHED`, `Beta 10/10 BREACHED`; planos finais `[completed, completed, pending]`; nenhuma violação de monotonicidade. |
| **P1-1** | **Fechado** | `probe_qa5_tick.py`: duplicata devolve `already_completed`, mesmo `work_id`, `scene_completions_total=1`. `probe_reauth_dupe.py`: `already_scheduled`, mesmo `work_id`, sem exceção, `last_seq_unchanged=true`; segundo `--to` com `status=idempotent`, 0 eventos e 1 `world.work_completed`. |
| **P2-1** | **Fechado** | Seleção e `queue.json` em `[cena_A, relogio_B]`; `priority_final` `[60, 55]` nos dois lados (bruto `[46, 50]`), `priority_final_coherent=true`. |
| **P2-2** | **Fechado** | `TickBudget(max_items, max_items_per_day, override)` sem `max_depth`; `DEFAULT_SIMULATION` sem a chave; `normalize_simulation({"max_depth": 1})` ignora e mantém defaults; sonda com `max_depth` 1 vs 5 seleciona o mesmo (`equal=true`). Resíduo de `max_depth` apenas no `DependencyGraph` (`kernel/dag.py` e seu teste), fora do orçamento. |
| **P2-3** | **Fechado** | `game_time_to_minutes("30 de Solsticio de 304, 23:59", calendar=CAL12)` levanta `ValueError` ("Mês 'Solsticio' não consta no calendário..."); `"5 de Outubro de 300, 10:00"` sem calendário devolve `155396760`. |

### 6.3 Achados novos

**Nenhum achado novo.**

Observação não bloqueante: no cenário `same_target_with_deferred` da sonda antiga, repetir o mesmo `--to` com adiados abertos drena um item e altera `last_seq`. Isso é o comportamento de C13/AT-G4-03 (novo ciclo sobre trabalho adiado), não uma falha de C14, cujo teste drena antes de repetir. Registrado para transparência.

### 6.4 Riscos de escopo

- **Sem XP/reputação/missão, narração ou LLM no tick:** grep em `application/world_tick.py`, `application/world_schedule.py`, `plugins/*`, `resources/world/*`, `application/projectors/world_journal.py` e `interfaces/cli/world_cli.py` encontrou apenas docstrings; não há import ou chamada de LLM nem escrita de progressão.
- **`queue.json` reconstruível:** `cmd_rebuild(force=True)` (mesmo caminho do `rebuild --force`) devolve `status=ok`, `events_replayed=8`, e o hash da fila permanece `sha256:95205c3b...`; 1 `world.work_completed` após o rebuild.
- **Fronteiras:** os 40 testes incluem `tests.test_architecture_boundaries` (8), verdes; os 32 restantes são de Fase 05.

### 6.5 Veredito

**APROVADO.** Os cinco achados estão fechados com evidência reproduzível, a suíte completa (282) e os 40 testes de Fase 05/fronteiras passam, e não há achado novo. A Fase 05 está apta à homologação; a observação de 6.3 é comportamento previsto em C13/AT-G4-03, não ressalva.
