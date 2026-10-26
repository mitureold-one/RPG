# Checklist de Ratificação — G3

**Gate:** G3 — Contrato Epistêmico e Fronteiras de Estado
**Fase de destino:** Fase 03 — Agentes
**Data:** 26/10/2026
**Decisão:** **Ratificado com emendas**
**Registro:** [`g3-decision-record.md`](../g3-decision-record.md)

## 1. Decisões

| Item | Decisão | Estado |
| :--- | :--- | :---: |
| G3-D01 | Verdade canônica separada de alegação e crença; fato é evento/estado, sem tabela paralela | Ratificado |
| G3-D02 | `awareness` separado de `stance`; conhecer não é acreditar | Ratificado |
| G3-D03 | Proveniência referenciável e obrigatória | Ratificado com emenda |
| G3-D04 | `current`, `outdated`, `contested`, `refuted`; revisão append-only | Ratificado |
| G3-D05 | Inferência provisória com premissas e sem virar fato | Ratificado |
| G3-D06 | Conhecimento individual separado do coletivo; sem propagação automática | Ratificado |
| G3-D07 | Escopos de visibilidade: mundo, NPC, facção, protagonista, jogador | Ratificado com emenda |
| G3-D08 | Proposta da IA não é estado canônico; admissão valida | Ratificado |
| G3-D09 | Integridade causal e histórico preservado | Ratificado |
| G3-D10 | `claim_id` estável e resolvedor de verdade do motor | Ratificado com emenda |
| G3-D11 | `KnowledgeRecord` mínimo com confiança determinística | Ratificado com emenda |
| G3-D12 | Proveniência por IDs, sem ciclos, com `derived_from` | Ratificado com emenda |
| G3-D13 | Event log é verdade; operacional por replay; snapshot é cache | Ratificado com emenda |
| G3-D14 | Conhecimento coletivo e `KnowledgeView` | Ratificado com emenda |
| G3-D15 | Correção de fato não reescreve crença; evento epistêmico próprio | Ratificado com emenda |

## 2. Critérios de aceitação

| Critério | Cobertura | Estado |
| :--- | :--- | :---: |
| AT01 | Fato vs crença | Ratificado |
| AT02 | Conhecer sem acreditar | Ratificado |
| AT03 | Proveniência | Ratificado |
| AT04 | Informação falsa | Ratificado |
| AT05 | Desatualização | Ratificado |
| AT06 | Inferência | Ratificado |
| AT07 | Conhecimento coletivo | Ratificado |
| AT08 | Segredo do jogador | Ratificado |
| AT09 | Proposta não admitida | Ratificado |
| AT10 | Reconstrução e correção | Ratificado |
| AT11 | Fontes contraditórias | Adicionado na ratificação |
| AT12 | Desatualizado não é falso | Adicionado na ratificação |
| AT13 | Inferência com premissa refutada | Adicionado na ratificação |
| AT14 | Facção dividida | Adicionado na ratificação |
| AT15 | Correção não reescreve crença | Adicionado na ratificação |
| AT16 | Replay e snapshot | Adicionado na ratificação |
| AT17 | `KnowledgeView` e vazamento | Adicionado na ratificação |

## 3. Condições

- [x] Decisão de persistência fechada: event log canônico; replay; snapshot é cache.
- [x] Identidade de alegação e resolvedor de verdade definidos.
- [x] Schema mínimo de conhecimento/crença definido.
- [x] Proveniência e inferência com IDs definidos.
- [x] Conhecimento coletivo e visibilidade definidos como contrato.
- [x] Correção de fato separada de revisão de crença.
- [x] Critérios de aceitação ampliados.
- [ ] Spec 012 escrita e aprovada.
- [ ] `plan.md`/`tasks.md` da Fase 03 aprovados.
- [ ] R2 planejado antes de ampliar `narrator.py`/`factions.py`/`quests.py`.

## 4. Assinatura

Ratificação solicitada pelo dono do projeto em 26/10/2026 e transcrita pelo agente de QA/arquitetura. A implementação permanece condicionada à spec 012, ao plano/tarefas e ao R2; este checklist não autoriza código por si só.
