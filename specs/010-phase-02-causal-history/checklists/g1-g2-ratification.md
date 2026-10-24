# G1/G2 Ratification Checklist — 010

**Purpose:** registrar a ratificação das decisões dos gates G1 e G2 antes de qualquer código do R1/Fase 02.
**Spec:** [`spec.md`](../spec.md)
**Created:** 2026-10-23
**Ratified at:** 2026-10-23 — decisões transcritas da mensagem do dono do projeto.
**Status:** Ratificado com ajustes; R1 pendente de `plan.md`/`tasks.md` e dos critérios complementares.

## 0. Estados

- **Ratificado:** decisão aceita como está.
- **Ratificado com ajuste:** proposta aceita após incorporar a alteração registrada na coluna “Ajuste incorporado”.
- **Rejeitado:** proposta não aceita e precisa ser reformulada.

> Regra: os gates G1/G2 estão fechados com os ajustes abaixo. O R1 ainda não começa até `plan.md`/`tasks.md` existirem e os critérios complementares da seção 4 estarem no plano. Nenhum ajuste pode ser revertido sem nova decisão do dono.

---

## 1. G1 — Contrato do Evento

| ID | Decisão | Estado | Ajuste incorporado | Data |
| :--- | :--- | :---: | :--- | :--- |
| G1-D1 | JSONL canônico por campanha; SQLite derivado opcional | Ratificado com ajuste | O motor funciona sem índice; SQLite é sempre reconstruível | 2026-10-23 |
| G1-D2 | Lote atômico por marcadores `batch.open`/`batch.committed` | Ratificado com ajuste | Recuperação obrigatória do segmento antes de aceitar nova escrita; lote incompleto invisível | 2026-10-23 |
| G1-D3 | Envelope congelado; `target`/`preconditions`/`result`/`costs` no payload; dependências em `meta.dependencies` | Ratificado com ajuste | Schemas dos tipos validam seus payloads; o kernel não conhece regras particulares de evento | 2026-10-23 |
| G1-D4 | `game_time` e `game_time_sort` obrigatórios no `EventDraft` | Ratificado | O store não inventa data nem default | 2026-10-23 |
| G1-D5 | `batch_id` = `bat_<ulid>`; `correlation_id` por unidade de trabalho; `causation_id` = evento direto | Ratificado | `correlation_id` identifica a unidade de trabalho (`turn_`, `cmd_`, `campaign_`) | 2026-10-23 |
| G1-D6 | Serialização UTF-8/LF/sem BOM; JSON compacto ordenado; SHA-256 | Ratificado com ajuste | Dois hashes: **hash do evento** (representação canônica do evento) e **hash do lote** (concatenação canônica dos eventos em ordem de `seq`) | 2026-10-23 |
| G1-D7 | `schema_version` por `EventType`; upcasters `N→N+1`; versão futura rejeitada | Ratificado | Sem conversões silenciosas | 2026-10-23 |
| G1-D8 | Retenção integral; segmento 1.000 eventos/1 MB; snapshot 500 eventos/arco | Ratificado com ajuste | Limites são parâmetros operacionais ajustáveis, não regras de domínio; arquivar não apaga nem reescreve | 2026-10-23 |
| G1-D9 | Catálogo mínimo de eventos v1 (spec G1-D9) | Ratificado com ajuste | Cada tipo exige schema, campos obrigatórios e validação antes de ser registrado; nenhum tipo arbitrário é gravável | 2026-10-23 |
| G1-D10 | `EventType` registrado e validado; tipo desconhecido rejeitado no append | Ratificado com ajuste | Registro explícito no `bootstrap.py`; valida tipo, versão, payload e dependências; sem descoberta automática | 2026-10-23 |
| G1-D11 | Layout `events/`, `snapshots/`, `projections/`, `artifacts/prose/`, `queue.jsonl` | Ratificado | Estrutura aceita como proposta | 2026-10-23 |
| G1-D12 | Nenhuma mutação de estado sem evento correspondente | Ratificado com ajuste | Projeções escritas exclusivamente por projectors/`ProjectionWriter`; `mundo.md`/`regras.md` são configuração separada | 2026-10-23 |

**G1 fechado?** `[x]` Sim — todas as decisões ratificadas ou ratificadas com ajuste incorporado.

---

## 2. G2 — Correção, Dependência e Reconstrução

| ID | Decisão | Estado | Ajuste incorporado | Data |
| :--- | :--- | :---: | :--- | :--- |
| G2-D1 | Correção é evento novo; nunca muta nem apaga o original | Ratificado com ajuste | `correction.issued` contém eventos corrigidos, motivo, ator, alterações pretendidas, estado e `correction_id`; se não houver compensação segura, registra pendência para revisão | 2026-10-23 |
| G2-D2 | Dependências explícitas em `meta.dependencies`; grafo é DAG | Ratificado com ajuste | Referências a eventos anteriores do mesmo lote são permitidas; validação considera histórico persistido + lote em validação; profundidade 64 configurável; `seq` não implica causalidade | 2026-10-23 |
| G2-D3 | Reavaliação seletiva dos dependentes; sem LLM; idempotente | Ratificado com ajuste | Reavaliar não é reexecutar: não repete comandos nem concede XP/relógio de novo; fato posterior inconsistente gera registro de inconsistência e exige compensação/correção explícita, sem inventar novo resultado | 2026-10-23 |
| G2-D4 | Rebuild de projeção a partir de snapshot + eventos, com hash e checkpoint | Ratificado com ajuste | Rebuild byte-idêntico para mesma sequência, snapshot, versão de projector e configuração; checkpoints só após sucesso; `projection.rebuilt` é emitido **fora** do cálculo do hash e não altera o resultado verificado | 2026-10-23 |
| G2-D5 | Prosa imutável; correção apenas anota, nunca reescreve | Ratificado | Nova narração é novo artefato associado a novo turno/evento | 2026-10-23 |
| G2-D6 | Retomada sem duplicação: `event_id`, `expected_last_seq`, lote, checkpoint | Ratificado com ajuste | Rejeição explícita de lote duplicado com `DuplicateBatchError`; distinguir nunca persistido / parcial não confirmado / confirmado não projetado / projetado; `correction_id` único no store | 2026-10-23 |
| G2-D7 | Fila esqueleto em `queue.jsonl`; orçamento/retry no G4 | Ratificado com ajuste | Fila append-only e separada do histórico de jogo; criação e conclusão/falha por novos registros, sem sobrescrever o passado | 2026-10-23 |
| G2-D8 | Toda correção tem ator, motivo, alvo e estado auditável | Ratificado | Violações geram erro ou lint identificável, nunca silêncio | 2026-10-23 |
| G2-D9 | Fronteira com G6: Fase 02 guarda hash/caminho da prosa; indexação depois | Ratificado | A solução de armazenamento não pode inviabilizar busca, resumos ou memória derivada de G6 | 2026-10-23 |
| G2-D10 | `rebuild` não reexecuta LLM nem re-concede XP/relógio | Ratificado | Compensações já registradas são aplicadas na ordem dos eventos, sem duplicar XP, relógio ou reputação | 2026-10-23 |

**G2 fechado?** `[x]` Sim — todas as decisões ratificadas ou ratificadas com ajuste incorporado.

---

## 3. Perguntas do dono (Q1–Q10)

| ID | Pergunta | Decisão | Ajuste/observação | Data |
| :--- | :--- | :---: | :--- | :--- |
| Q1 | O catálogo v1 (G1-D9) está aceitável em nomes e granularidade? | Ratificado com ajuste | Catálogo v1 como base; validar cardinalidade `turn.committed`/`prose.recorded` e expressividade dos eventos de correção antes de congelar | 2026-10-23 |
| Q2 | `target`/`preconditions`/`result`/`costs` no payload e dependências em `meta.dependencies`? | Ratificado | Envelope permanece estável | 2026-10-23 |
| Q3 | Lote por marcadores; SQLite opcional na Fase 02? | Ratificado com ajuste | Recuperação de lote incompleto precisa ser rigorosamente especificada e testada | 2026-10-23 |
| Q4 | Retenção integral; segmento 1.000/1 MB; snapshot 500/arco? | Ratificado | Limites são parâmetros operacionais, não regras de domínio | 2026-10-23 |
| Q5 | Correção: `correction.issued` + compensação; prosa imutável? | Ratificado com ajuste | Efeitos numéricos podem ser compensados; fatos contraditórios exigem reavaliação explícita, nunca alteração silenciosa | 2026-10-23 |
| Q6 | Dependências explícitas, DAG, profundidade 64, sem dependência implícita por `seq`? | Ratificado com ajuste | Referências a eventos anteriores do mesmo lote são permitidas; validar histórico persistido + lote | 2026-10-23 |
| Q7 | Prosa: artefato + hash/caminho no evento; indexação em G6? | Ratificado | Busca semântica e indexação ficam para G6 | 2026-10-23 |
| Q8 | Fila: `queue.jsonl` mínimo na Fase 02, orçamento/retry no G4? | Ratificado com ajuste | Fila append-only, sem orçamento nem retry automático agora | 2026-10-23 |
| Q9 | Projeções `diario.md`/`ficha.md`/`npcs.md`; `mundo.md`/`regras.md` config; `faccoes.md` em R2? | Ratificado | Sem antecipar fases futuras | 2026-10-23 |
| Q10 | Escritas de Markdown exclusivas dos projectors no R1? | Ratificado | Nenhum comando mutador mantém segunda via de escrita direta | 2026-10-23 |

---

## 4. Critérios complementares de aceite do R1 (não são gates)

Estes quatro pontos estão incorporados e detalhados em `plan.md` e `tasks.md` como critérios de aceite e testes do R1:

- [x] **C1 — Falhas reais de persistência:** incorporado em `plan.md` (Fase 1) e `tasks.md` (T006–T012; `tests/test_event_store_crash_recovery.py`).
- [x] **C2 — Dependências dentro do lote:** incorporado em `plan.md` (Fase 3) e `tasks.md` (T018–T021; `tests/test_causal_dag.py`).
- [x] **C3 — Rebuild e auditoria:** incorporado em `plan.md` (Fase 4) e `tasks.md` (T022–T028; `tests/test_projection_rebuild.py`).
- [x] **C4 — Correção contraditória:** incorporado em `plan.md` (Fase 6) e `tasks.md` (T035–T039; `tests/test_causal_correction.py`).

Mapeamento: C1 → `FR-G1-09`; C2 → `FR-G2-09`; C3 → `FR-G2-10`; C4 → `FR-G2-11`.

---

## 5. Rejeições

Nenhuma decisão foi rejeitada. Todos os ajustes foram incorporados à proposta; se algum ajuste for recusado depois, registrar aqui motivo e alternativa.

| ID | Motivo | Alternativa | Data |
| :--- | :--- | :--- | :--- |
| — | — | — | — |

---

## 6. Sign-off

- **G1 ratificado com ajustes em:** 23/10/2026 — dono do projeto (registro via mensagem de ratificação).
- **G2 ratificado com ajustes em:** 23/10/2026 — dono do projeto (registro via mensagem de ratificação).
- **Spec 010 pode ir para planning (`plan.md`/`tasks.md`)?** `[x]` Sim.
- **R1 pode começar?** `[x]` Sim: `plan.md` e `tasks.md` concluídos com C1–C4 totalmente incorporados.

---

## 7. Quality gate

- [x] Todas as decisões G1-D1–G1-D12 estão ratificadas ou ratificadas com ajuste.
- [x] Todas as decisões G2-D1–G2-D10 estão ratificadas ou ratificadas com ajuste.
- [x] Q1–Q10 respondidas.
- [x] Nenhuma decisão rejeitada ficou sem alternativa.
- [x] O `spec.md` foi atualizado com os ajustes e mudou para `Ready for Planning`.
- [x] A ratificação foi registrada em `EXECUCAO.md` com link para este checklist (`EX-0013`).
- [x] `plan.md`/`tasks.md` escritos com C1–C4.
- [x] Nenhum código de R1 foi escrito antes deste checklist fechar.

---

## 8. Notas

- O catálogo de eventos é o ponto mais sensível: renomear um tipo depois exige upcaster e testes de compatibilidade.
- O lote por marcadores mantém “um evento por linha” e permite recuperação simples; o custo é um leitor que ignora lote sem `committed`.
- A prosa é o único artefato que não pode ser reconstruído a partir de eventos; por isso hash + caminho são obrigatórios.
- A fila é esqueleto: quem decide orçamento, prioridade e retry é o G4/Fase 05.
- `projection.rebuilt` é auditoria, não parte do cálculo que ele verifica.
