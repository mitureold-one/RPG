# Checklist de Ratificação — G4

**Gate:** G4 — Orçamento, Prioridade, Retry e Retomada da Simulação
**Fase de destino:** Fase 05 — Simulação
**Data:** 26/10/2026
**Decisão:** **Ratificado com emendas**
**Registro:** [`g4-decision-record.md`](../g4-decision-record.md)

## 1. Decisões

| Item | Decisão | Estado |
| :--- | :--- | :---: |
| G4-D01 | Tick explícito, causal, transacional e sem narração | Ratificado |
| G4-D02 | Tempo em minutos inteiros; calendário declarado autoridade; proibido float | Ratificado |
| G4-D03 | Avanço proporcional por cadência declarada; plano não fecha por tempo | Ratificado com emenda |
| G4-D04 | Fila persistente derivada do log; `queue.json` é projeção | Ratificado |
| G4-D05 | `work_id`/`tick_id` determinísticos; trabalho concluído nunca reexecuta | Ratificado |
| G4-D06 | Orçamento adaptativo com teto duro e adiamento sem descarte | Ratificado com emenda |
| G4-D07 | Prioridade inteira fixa por tipo, boost anti-inanição e ordenação estável | Ratificado |
| G4-D08 | Retry com backoff, máximo de tentativas e falha permanente auditada | Ratificado com emenda |
| G4-D09 | Profundidade seletiva: só o devido é avaliado; silêncio é auditável | Ratificado |
| G4-D10 | Gatilhos da IA são propostas validadas; inválido vira `proposal.rejected` | Ratificado |
| G4-D11 | Catálogo mínimo de 5 eventos `world.*` | Ratificado com emenda |
| G4-D12 | Projeções: data canônica no diário, `queue.json`, `estado.json` inalterado | Ratificado |
| G4-D13 | R3 faseado: `world/` na Fase 05, `review/` na Fase 06 | Ratificado com emenda |
| G4-D14 | Determinismo total; replay não reexecuta decisão | Ratificado |
| G4-D15 | Falha explícita, `--dry-run` sem escrita e limite de autonomia | Ratificado |

## 2. Critérios de aceitação

| Critério | Cobertura | Estado |
| :--- | :--- | :---: |
| AT-G4-01 | `+7d` avança relógio e planos proporcionalmente; data final exata | Ratificado |
| AT-G4-02 | Orçamento pequeno: concluído persiste, restante é adiado | Ratificado |
| AT-G4-03 | Retomada/drenagem sem duplicar trabalho concluído | Ratificado |
| AT-G4-04 | Retry com backoff e falha permanente auditada | Ratificado |
| AT-G4-05 | Agendamento inválido rejeitado sem mutação | Ratificado |
| AT-G4-06 | Calendário customizado consistente e agendamento na data exata | Ratificado |
| AT-G4-07 | Determinismo de `tick_id`, `work_id` e hash de fila | Ratificado |
| AT-G4-08 | Profundidade seletiva observável na contagem de eventos | Ratificado |

## 3. Condições

- [x] Gate G4 fechado antes de qualquer código de produção.
- [x] Limites de orçamento, prioridade, retry e retomada definidos.
- [x] Eventos da simulação definidos com schema v1 e sem upcaster.
- [x] Fila sem store paralelo (coerente com G3-D13).
- [x] R3 faseado explicitamente (G4-D13).
- [x] Fronteira com G5/Fase 06 preservada.
- [x] `spec.md`, `plan.md` e `tasks.md` da spec 015 escritos.
- [x] Fase 04 homologada antes da abertura (`EX-0039`/`EX-0040`).
