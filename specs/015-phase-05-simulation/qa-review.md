# QA Review — Fase 05: Simulação de Mundo por Tempo

**Feature:** `phase-05-simulation` · **Gate:** [`G4`](g4-decision-record.md) · **Spec:** [`spec.md`](spec.md)
**Status:** **AUDITORIA INDEPENDENTE INTERROMPIDA** — o agente auditor falhou antes de emitir o parecer. As sondas que ele produziu (`.tmp/probe_qa5_{smoke,time,tick,budget,causality}.py` e `out_*.txt`) foram recuperadas, reexecutadas e transformadas nos achados abaixo; a remediação está em `EX-0043`. A **re-auditoria independente** (agente novo) é pendência explícita.
**Regra de governança:** este documento não declara aprovação por conta própria. O veredito final cabe à re-auditoria.

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
