# Specification Quality Checklist: 015 — Fase 05: Simulação de Mundo por Tempo

**Purpose**: Validar completude e qualidade da especificação antes do planejamento.
**Created**: 2026-10-26
**Feature**: [`spec.md`](../spec.md)
**Gate**: [`g4-decision-record.md`](../g4-decision-record.md)

## Qualidade do Conteúdo

- [x] Escopo delimitado e verificável em `spec.md` §2.1.
- [x] Fora de escopo explícito em `spec.md` §2.2 e §11, sem lacunas ambíguas.
- [x] Nenhum marcador `[NEEDS CLARIFICATION]` permanece.
- [x] Requisitos testáveis e sem ambiguidade de comportamento.
- [x] Critérios de sucesso mensuráveis e ligados a C11–C17.
- [x] Linguagem técnica precisa; termos como tick, fila, adiamento e retry são definidos.
- [x] Modelo conceitual coerente com os contratos e com as projeções existentes.
- [x] Nenhum requisito de prosa, LLM, XP ou direção narrativa foi introduzido.

## Completude dos Requisitos

- [x] FR-SIM-01 a FR-SIM-14 estão definidos e rastreáveis.
- [x] Critérios C11–C17 cobrem salto, causa, orçamento, retomada, calendário, profundidade e retry.
- [x] Decisões G4-D01 a G4-D15 estão referenciadas na spec, no plano e neste checklist.
- [x] Riscos e mitigações estão registrados em `spec.md` §9 e `plan.md` §11.
- [x] Dependências (Fases 02–04) e gates (G4, G5) estão identificados.
- [x] Nenhuma contradição com `ARCHITECTURE.md` §6.1, §9.3 e §12 (R3).
- [x] Nenhuma contradição de escopo com `ROADMAP.md` §3 (Fase 05) e §5 (G4).
- [x] Catálogo limitado aos cinco eventos aprovados: `world.ticked`, `world.scheduled`, `world.work_deferred`, `world.work_completed`, `world.work_failed`.
- [x] Nomes de arquivos e módulos coincidem com `plan.md` e não introduzem stores paralelos.
- [x] Orçamento adaptativo, teto duro, prioridade e anti-inanição estão especificados.
- [x] Identidade determinística, deduplicação e retomada idempotente estão especificadas.
- [x] Calendário declarado, ida-e-volta e agendamento futuro estão especificados.
- [x] O tick não inventa desfecho, não concede XP e não altera reputação ou missão.

## Rastreabilidade dos Requisitos

| Requisito | Seção da spec | Critério ou teste |
| :--- | :--- | :--- |
| FR-SIM-01 | §3, §5 | C11 |
| FR-SIM-02 | §3 | C11 |
| FR-SIM-03 | §3, §6 | C11, C16 |
| FR-SIM-04 | §3, §5 | C16 |
| FR-SIM-05 | §3, §5 | C13 |
| FR-SIM-06 | §3, §6 | C14 |
| FR-SIM-07 | §3, §6 | C17 |
| FR-SIM-08 | §3, §6 | C17 |
| FR-SIM-09 | §3, §6 | C11, C13 |
| FR-SIM-10 | §3, §4 | C15 |
| FR-SIM-11 | §3, §10 | C14 |
| FR-SIM-12 | §2.1, §10 | `test_architecture_boundaries` |
| FR-SIM-13 | §2.2, §3 | suíte legada e rebuild C3 |
| FR-SIM-14 | §3, §6 | C14 |

## Prontidão da Feature

- [x] Todos os requisitos funcionais têm critério de aceitação associado.
- [x] Os cenários de aceite cobrem o fluxo principal e os casos de orçamento, retry e calendário.
- [x] O quickstart é reproduzível apenas com CLI e arquivos Markdown.
- [x] O plano P0–P8 tem critério de saída por fase.
- [x] A definição de pronto inclui suíte completa, fronteiras, `queue.json` e `--dry-run`.
- [x] Não há pendência bloqueante; D1–D7 do §7 estão cobertas pelas recomendações aceitas no plano.

## Observações

- G4 foi ratificado em 26/10/2026 com as emendas de cadência, orçamento, retry, catálogo de eventos, R3 faseado e remoção de `max_depth`.
- A linha de status do `ROADMAP.md` foi alinhada à homologação (`EX-0044`); spec, plano e gate não se contradizem.
- Documento concluído; a suíte de aceite C11–C17 e a re-auditoria independente (§6 de `qa-review.md`) validaram a implementação.
