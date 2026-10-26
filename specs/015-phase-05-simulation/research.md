# Research & Technical Decisions: 015 — Fase 05: Simulação de Mundo por Tempo

**Feature:** `phase-05-simulation`
**Status:** Consolidado (G4 ratificado em 26/10/2026)
**Created:** 2026-10-26
**Spec:** [`spec.md`](spec.md) · **Plan:** [`plan.md`](plan.md) · **Gate:** [`g4-decision-record.md`](g4-decision-record.md)

---

## 1. Contexto da investigação

A Fase 05 acrescenta o eixo temporal sem trocar o modelo de verdade das fases anteriores: o evento é fato, a projeção é derivada e o comando é transacional. A pesquisa abaixo fixa as decisões que o G4 ratificou e explica por que cada alternativa foi descartada. O objetivo não é escolher uma arquitetura nova, e sim impedir que o tick vire um scheduler implícito, não determinístico ou não auditável.

---

## 2. Por que tick explícito

**Decisão:** `world_tick(elapsed_minutes)` é o único mecanismo de avanço autônomo do mundo. Ele é acionado por `time`, `travel`, `rest`, `critical_event`, `schedule` ou `manual`, grava o acionador no evento e executa um único lote transacional. Não existe tick implícito em `prepare`, `commit`, `review` ou leitura de projeção. O tick não narra, não chama LLM e não decide desfecho.

**Alternativas rejeitadas:**
- Tick implícito no `prepare`, porque transformaria leitura de contexto em mutação de estado e quebraria a idempotência do turno.
- Tick em daemon ou cron, porque introduziria relógio de parede, concorrência e um caminho de escrita fora do comando auditável.
- Tick por turno narrado, porque o mundo deixaria de andar em viagens, descansos e saltos sem cena.

**Consequência:** o avanço tem autor, acionador e lote únicos; `--dry-run` é possível sem efeito colateral; a retomada é reconhecida por identidade; e nenhum evento de mundo aparece sem um tick que o origine (C12).

---

## 3. Por que minutos inteiros

**Decisão:** a unidade canônica é o minuto inteiro desde a época da campanha (`game_time_sort`). Todo cálculo usa `to_sort = from_sort + elapsed_minutes`; a data final é derivada do calendário, nunca digitada pela IA. `float` é proibido em tempo, orçamento e prioridade.

**Alternativas rejeitadas:**
- Horas ou dias em ponto flutuante, porque arredondamentos acumulados fariam dois ticks idênticos produzirem datas diferentes.
- `datetime.now()` como referência, porque o resultado dependeria da máquina e do fuso, não da diegese.

**Consequência:** `+10080` minutos produz exatamente `01/10/300, 10:00 → 08/10/300, 10:00`; os hashes de `work_id` e `tick_id` são estáveis; e a conversão de ida-e-volta vale para os três formatos canônicos (FR-SIM-01, FR-SIM-10, C11).

---

## 4. Por que fila derivada do log, em vez de store paralelo

**Decisão:** a fila é derivada dos eventos `world.*`. `queue.json` é uma projeção inspecionável com `schema_version`, `last_seq` e `hash`, reconstruível por `rebuild`. Não existe banco de fila, `queue.jsonl` concorrente ou cache de fila como fonte de verdade; o `queue.jsonl` legado da Fase 02 permanece apenas como artefato histórico.

**Alternativas rejeitadas:**
- Fila em SQLite como verdade, porque criaria um segundo store transacional, com lock, migração e risco de divergência em relação ao event log.
- `queue.json` como verdade, porque uma edição manual ou um rebuild parcial passaria a alterar o passado.

**Consequência:** replay e rebuild reconstroem a fila byte a byte; a correção causal continua valendo; o hash de `queue.json` denuncia divergência; e o item adiado nunca é descartado (G4-D04, C3, C14).

---

## 5. Por que cadência declarada

**Decisão:** o avanço é proporcional ao tempo e usa cadências declaradas em `regras.md: simulation:` — `clock_step_minutes = 1440` e `plan_step_minutes = 2880`. Relógios avançam `floor(elapsed / clock_step_minutes)` passos, saturam em `max` e ficam `BREACHED` ao atingir o máximo. Planos avançam `floor(elapsed / plan_step_minutes)` passos.

**Alternativas rejeitadas:**
- Um passo por turno narrado, porque o número de turnos não mede o tempo diegético e um salto de sete dias não pode ser fatiado em cenas fictícias.
- Cadência decidida pela IA a cada tick, porque o resultado deixaria de ser reproduzível e auditável.

**Consequência:** sete dias valem sete passos de relógio e três passos de plano; o relógio 3/4 com cadência diária chega a `BREACHED` com `current == max`; entidades sem cadência vencida permanecem silenciosas (C11, C16).

---

## 6. Por que `plan_ready_for_resolution` em vez de concluir o plano

**Decisão:** o último passo concluído não encerra o plano. O plano permanece `active` e o trabalho entrega o fato `plan_ready_for_resolution`, para que a agência da Fase 03/06 decida o desfecho. O tick não marca sucesso, não concede XP e não altera reputação.

**Alternativas rejeitadas:**
- Encerrar o plano automaticamente no último passo, porque o tempo não é resultado de plano nem prova de sucesso.
- Marcar o plano como falho quando o tempo acaba, porque ausência de desfecho não é falha.

**Consequência:** o motor registra apenas o que pode justificar; a resolução continua sendo evento de agência; e o plano pronto fica visível sem inventar causalidade (G4-D03, G4-D09).

---

## 7. Por que retry com backoff em vez de retry imediato

**Decisão:** falha de resolução grava `world.work_failed` com `attempts`, `error` determinístico e `retry_at_sort = to_sort + retry_backoff_minutes * attempts`. O item é re-derivado quando `to_sort >= retry_at_sort` e `attempts < max_attempts`; ao esgotar, vira falha permanente. Padrões: `max_attempts = 3`, `retry_backoff_minutes = 60`.

**Alternativas rejeitadas:**
- Retry imediato no mesmo tick, porque uma falha determinística entraria em laço e consumiria o orçamento sem avançar o tempo.
- Sem retry, porque uma falha transitória (entidade ainda não projetada, por exemplo) perderia trabalho para sempre.

**Consequência:** falhas transitórias não matam o item, falhas permanentes saem da fila ativa com motivo, e o histórico preserva `attempts`, `error` e `retry_at_sort` (FR-SIM-07, C17).

---

## 8. Por que o calendário declarado é autoridade

**Decisão:** o bloco `calendar:` de `regras.md` é a autoridade para converter minutos em data. Sem calendário, valem 12 meses de 30 dias para datas nomeadas e 365/30 para datas numeradas, como em `temporal/calendar.py`. `minutes_to_game_time` e `advance_game_time` usam a mesma aritmética de `game_time_to_minutes` e garantem ida-e-volta nos três formatos canônicos.

**Alternativas rejeitadas:**
- Calendário gregoriano fixo, porque quebraria campanhas com meses e anos próprios.
- Data final informada pela IA, porque o tick deixaria de derivar o tempo do tempo decorrido.

**Consequência:** `+30d` a partir de 5 de Ventania cai em 5 de Geada; `+1a` cai no mesmo dia do ano seguinte; o agendamento futuro dispara exatamente em `due_at_sort` (FR-SIM-10, C15).

---

## 9. Por que orçamento adaptativo com teto duro

**Decisão:** o limite do ciclo é `min(max_items, 4 + floor(elapsed_minutes / 1440))`, com o teto diário `max_items_per_day` como limite adicional; `--budget N` é teto duro e vence a fórmula. A seleção ordena por `(-priority_final, due_at_sort, work_id)`, com prioridade base por tipo e boost anti-inanição de `min(deferrals, 5)`. O que não couber é adiado com `budget_exhausted`, nunca descartado nem resumido como concluído.

**Alternativas rejeitadas:**
- Limite fixo de um item por tick, porque saltos longos ficariam lentos e a fila cresceria sem necessidade.
- Sem limite, porque um salto de anos tentaria resolver o mundo inteiro em um comando.
- Descartar o excedente, porque o adiamento é justamente o que garante retomada.
- Reordenar a fila pela IA em tempo de execução, porque prioridade subjetiva destruiria o determinismo.

**Consequência:** com `--budget 1`, um item conclui e os demais são adiados; o concluído permanece no log; um tick seguinte drena os adiados sem repetir o concluído (FR-SIM-05, C13).

---

## 10. Alternativas rejeitadas (síntese)

| Alternativa | Motivo da rejeição | Decisão que a substitui |
| :--- | :--- | :--- |
| Fila SQLite como verdade | Store paralelo, lock e migração; quebra o princípio de que o event log é a única fonte. | G4-D04 |
| Tick implícito no `prepare` | Leitura viraria mutação; idempotência e `--dry-run` ficariam impossíveis. | G4-D01 |
| Avanço por número de turnos | Turno não é unidade de tempo; saltos sem cena ficariam invisíveis. | G4-D03 |
| RNG para desempate | Replay deixaria de reproduzir ids e hashes; `seed` fica reservado a extensões futuras. | G4-D14 |
| Concluir o plano no último passo | O tempo não prova sucesso nem autoriza desfecho. | G4-D03 |
| Retry imediato | Laço determinístico e consumo inútil do orçamento. | G4-D08 |

Toda decisão acima é reproduzível por teste com estado construído via `JsonlEventStore` + `rebuild_projections`, sem depender de prosa ou de relógio de parede.
