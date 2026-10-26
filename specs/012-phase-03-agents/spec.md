# Feature Specification: 012 — Fase 03: Agentes, Conhecimento Epistêmico e Refatoração R2

**Feature Name:** `phase-03-agents`  
**Status:** In Remediation (G3 ratificado; R2 concluído e aprovado; remediação da Rodada 2 de QA em especificação)  
**QA Review:** [`qa-review.md`](qa-review.md) (Re-auditoria de 26/10/2026: R2 aprovado; G3 reprovado por semântica de testes e visibilidade de escopos)  
**Ratificação G3:** [`g3-decision-record.md`](g3-decision-record.md) e [`checklists/g3-ratification.md`](checklists/g3-ratification.md)  
**Created:** 2026-10-26  
**Target:** Fase 03 do [`ROADMAP.md`](../../ROADMAP.md) e etapa R2 da refatoração arquitetural  
**Base Analisada:**
- [`specs/012-phase-03-agents/g3-decision-record.md`](g3-decision-record.md) (G3-D01 a G3-D15 e AT01 a AT17)
- [`specs/012-phase-03-agents/checklists/g3-ratification.md`](checklists/g3-ratification.md)
- [`specs/012-phase-03-agents/qa-review.md`](qa-review.md) (Apontamentos R-P0-1, R-P0-2, R-P1-1 a R-P1-5 e P2)
- [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 03), §5 (G3), §6.1, §6.4 (R2)
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §4, §6, §7, §12 (R2)
- [`rpgpro-diretrizes-agentes.md`](../../rpgpro-diretrizes-agentes.md) §6 (NPCs autônomos), §7 (Facções autônomas)

---

## 1. Contexto e Objetivo

Com a Fase 02/R1 concluída e aprovada (event store append-only em JSONL, projeções determinísticas e subsistema de correção causal) e o Gate G3 ratificado com emendas, a **Fase 03** introduz o domínio de **Agentes Autônomos (NPCs e Facções)** e o **Contrato Epistêmico Determinístico**, acompanhados da etapa **R2 da Refatoração Arquitetural**.

O objetivo desta especificação atualizada é incorporar os requisitos mandatórios da **segunda rodada de auditoria de QA (EX-0025)**, garantindo que:
1. A matriz de visibilidade de `KnowledgeView` barre vazamento de segredos para todas as classes de audiência (AT17);
2. Holders especiais (`player`, `protagonist`, `subgroup`) emitam drafts válidos no store através do mapeamento transparente de `ActorRef`;
3. A resolução de fatos canônicos em `resolve_claim` seja puramente estrutural, imune a negações textuais em substrings;
4. O status `contested` consolide divergências entre múltiplos registros epistêmicos do mesmo holder/claim;
5. Os modelos de domínio `NpcState` e `FactionState` exponham todos os campos contratuais de FR-AG-02 e FR-AG-03;
6. A projeção `faccoes.md` participe do `rebuild_projections` padrão com verificação de igualdade byte a byte;
7. A suíte `tests/test_phase03_agents_and_g3.py` cubra os 17 critérios de aceitação exatamente conforme sua semântica ratificada em `g3-decision-record.md`, com 100% dos testes integrados via `JsonlEventStore` real.

---

## 2. Escopo e Fronteiras Arquiteturais

### 2.1 Dentro do Escopo (Fase 03 + R2 + Remediação QA Rodada 2)
1. **Refatoração R2 (`resources/`)**:
   - Preservação da decomposição de `council/` em `resources/npcs/`, `resources/factions/`, `resources/quests/` e `resources/knowledge/`, mantendo fachadas `< 100` linhas e submódulos `< 300` linhas.
2. **Contrato Epistêmico e Visibilidade Rigorosa**:
   - `KnowledgeRecord` com proveniência acíclica, separação estrita entre `awareness` e `stance`, calibração de inferências e distinção exata entre `inexistent` e `unknown`.
   - `KnowledgeView` com matriz de visibilidade completa para `holder_only`, `faction_internal`, `subgroup_only`, `protagonist_private` e `player_meta`.
   - Isolamento causal estrito: `correction.issued` não reescreve crenças de agentes sem evento explícito `knowledge.revised`.
3. **Domínio de NPCs e Facções em Dois Níveis**:
   - `NpcState` completo: objetivos, planos, recursos, capacidades, localização, condição, compromissos e relações dimensionais.
   - `FactionState` completo: objetivos coletivos, planos corporativos, recursos, influência, limitações, conflitos internos, liderança e subgrupos dissidentes.
   - Replay 100% determinístico sem geração aleatória de identificadores.
4. **Admissão de Propostas e Portas Desacopladas**:
   - Validador `validate_intent_admission` aceitando fatos conhecidos (`availability == "known"`) independentemente de crença subjetiva, checando autoridade de liderança para ações de facção e barreiras físicas.
5. **Suíte de Aceite Integrada AT01–AT17**:
   - 17 testes integrados via `JsonlEventStore.append` e `rebuild_projections`, alinhados um a um aos critérios ratificados.

### 2.2 Fora de Escopo
- Scheduler narrativo global e coordenação temporal `world_tick` (Fase 05).
- Memória vetorial e busca semântica de prosa (Fase 07).

---

## 3. Requisitos Funcionais e Critérios de Remediação

### 3.1 Requisitos Epistêmicos Canônicos (Gate G3)

| ID | Requisito | Decisão G3 |
| :--- | :--- | :--- |
| **FR-G3-01** | Toda alegação possui `claim_id` (`clm_<ulid>`), proposição atômica (`subject`, `predicate`, `object`) e `claim_type`. Fatos canônicos são derivados dos eventos ou estados aceitos pelo motor. | G3-D01, G3-D10 |
| **FR-G3-02** | O motor fornece `resolve_claim(claim, at_time, events, world_state) -> TRUE \| FALSE \| UNKNOWN \| INDETERMINATE` baseado em comparação estrutural com os payloads de eventos e estados projetados. | G3-D10 |
| **FR-G3-03** | `KnowledgeRecord` separa `awareness` (`known \| unknown`) de `stance` (`believed \| disbelieved \| uncertain`), com `confidence` em basis points (`0..10000`) e status (`current \| outdated \| contested \| refuted`). | G3-D02, G3-D04 |
| **FR-G3-04** | Todo registro epistêmico exige proveniência não-vazia (`len(provenance) > 0`) e grafo acíclico (DAG). | G3-D03, G3-D05 |
| **FR-G3-05** | Inferências exigem premissas canônicas; premissas refutadas ou corrigidas bloqueiam novas inferências e mantêm o histórico. | G3-D05, G3-D12 |
| **FR-G3-06** | Conhecimento individual de membros não vaza automaticamente para a facção sem `knowledge.shared`. | G3-D06, G3-D14 |
| **FR-G3-07** | `KnowledgeView` aplica matriz de visibilidade estrita com `ClaimQueryResult` (`known`, `unknown`, `unavailable`, `inexistent`). | G3-D07, G3-D14 |
| **FR-G3-08** | Fontes conflitantes coexistem no histórico e marcam o status consolidado do holder/claim como `contested`. | G3-D04, G3-D11 |
| **FR-G3-09** | `correction.issued` anula fatos no motor mas preserva crenças subjetivas dos agentes até emissão de `knowledge.revised`. | G3-D15 |

### 3.2 Requisitos Específicos da Segunda Rodada de Remediação (QA Review)

| ID | Requisito de Remediação | Achado QA |
| :--- | :--- | :--- |
| **FR-FIX-08** | **Matriz Completa de Visibilidade em `KnowledgeView`:** `query_claim` e `get_beliefs_of` devem confrontar o escopo (`visibility`) com a audiência (`audience`):<br>• `holder_only`: inacessível (`unavailable`) para terceiros e protagonista;<br>• `faction_internal`: inacessível (`unavailable`) para não-afiliados à facção;<br>• `subgroup_only`: inacessível (`unavailable`) para a liderança da facção ou membros de outros subgrupos;<br>• `protagonist_private`: inacessível (`unavailable`) para NPCs e facções;<br>• `player_meta`: visível **exclusivamente** para o jogador; inacessível (`unavailable`) para protagonista, NPCs e facções. | R-P0-2, AT17 |
| **FR-FIX-09** | **Mapeamento de `ActorRef` para Holders Especiais:** As fábricas de drafts de knowledge devem mapear transparentemente `player` para `human`, `protagonist` para `npc` (ou `agent`), e `subgroup` para `faction` (ou `agent`), permitindo que holders não-NPC emitam rascunhos válidos aceitos por `validate_draft_batch`. | R-P1-1, AT08, AT14 |
| **FR-FIX-10** | **Resolução Estrutural Antinegação em `resolve_claim`:** A avaliação de ocorrências em `resolve_claim` deve ser baseada nos campos estruturados do payload do evento e verificar explicitamente a ausência de operadores de negação textual (ex: "não", "nao", "impediu", "failed"), impedindo falsos positivos como avaliar "O capitão não morreu" como TRUE para a claim "capitão morreu". | R-P1-2, AT01 |
| **FR-FIX-11** | **Consolidação Inter-Registros de `contested`:** Em `project_knowledge_state`, se um mesmo holder possuir múltiplos registros ou proveniências para o mesmo `claim_id` com evidências conflitantes (`supports=True` e `supports=False`) ou stances contraditórias, o status resultante para aquela alegação deve ser consolidado como `contested` e a stance como `uncertain`. | R-P1-3, AT11 |
| **FR-FIX-12** | **Completude de `NpcState` e `FactionState`:**<br>• `NpcState` deve expor `location`, `condition` e `commitments`;<br>• `FactionState` deve expor `collective_goals`, `influence`, `limitations` e `internal_conflicts`.<br>Todos os campos devem ser alimentados deterministicamente pelas projeções. | R-P1-4, FR-AG-02, FR-AG-03 |
| **FR-FIX-13** | **Rebuild Padrão de `faccoes.md` e Projeções Byte-Idênticas:** `default_projectors` em `application/rebuild.py` deve incluir `FactionProjector` por padrão. O teste AT16 deve verificar que tanto `npcs.md` quanto `faccoes.md` são reconstruídos de forma byte-idêntica entre execuções do zero e a partir de snapshots. | R-P1-5, FR-AG-06, AT16 |
| **FR-FIX-14** | **Reescrita Estrita dos 17 Testes de Aceite AT01–AT17 100% via Store:** A suíte `tests/test_phase03_agents_and_g3.py` deve ser reescrita de modo que todos os 17 testes passem pelo `JsonlEventStore.append` e reflitam a semântica canônica ratificada de `spec.md` §4: AT01 (fato vs crença), AT02 (conhecer sem crer), AT03 (DAG e rejeição sem proveniência), AT04 (plano com crença falsa), AT05 (outdated vs current), AT06 (inferência com premissas), AT07 (segredo individual de facção não vaza), AT08 (segredo do jogador inacessível ao protagonista), AT09 (proposta rejeitada fora do estado), AT10 (reconstrução e correção causal), AT11 (fontes conflitantes em eventos separados), AT12 (outdated não é falso na vigência), AT13 (inferência com premissa refutada histórica), AT14 (subgrupo dissidente com plano sigiloso), AT15 (isolamento de crença diante de correction), AT16 (rebuild byte-idêntico de npcs e faccoes), AT17 (matriz de visibilidade sem vazamento). | R-P0-1 |
| **FR-FIX-15** | **Distinção Exata de `inexistent` vs `unknown`:** Se uma claim estiver registrada na campanha via `knowledge.claim_registered`, a consulta por um holder que não a conhece deve retornar `availability="unknown"`. O retorno `inexistent` é reservado apenas para alegações totalmente ausentes do catálogo e dos registros da campanha. `build_view` deve repassar `current_time_sort` e `claim_validity_map`. | Achado P2-1, P2-2 |

---

## 4. Matriz de Aceitação Ratificada (AT01 a AT17)

1. **AT01 (Fato vs Crença):** Fato canônico registrado no motor (rei vivo); crença subjetiva do NPC (rei morto). O fato no motor não é alterado e a crença subjetiva persiste no store.
2. **AT02 (Conhecer sem Acreditar):** NPC tem ciência de um fato (`awareness="known"`, `stance="disbelieved"`); intenção fundamentada no fato é admitida para resolução.
3. **AT03 (Proveniência Obrigatória e DAG):** Registro com proveniência e DAG de premissas é aceito; registro sem proveniência ou com ciclo é rejeitado com erro tipado.
4. **AT04 (Informação Falsa Sustenta Plano):** Crença falsa do NPC sustenta plano operacional admitido sem alterar a verdade fática do mundo.
5. **AT05 (Desatualização Distinta de Falsidade):** Informação histórica com janela expirada é marcada deterministicamente como `outdated` sem se perder.
6. **AT06 (Inferência com Premissas):** Inferência provisória é registrada com premissas no store e nunca se promove a fato canônico consumado.
7. **AT07 (Conhecimento Coletivo Sem Auto-Propagação):** Membro de facção descobre segredo; demais membros e a facção não conhecem a claim sem `knowledge.shared`.
8. **AT08 (Segredo do Jogador Inacessível ao Protagonista):** Conhecimento com `visibility="player_meta"` retorna `availability="unavailable"` para o protagonista.
9. **AT09 (Proposta Não Admitida Fora do Estado):** Proposta sem requisitos gera evento `proposal.rejected` e é ignorada na reconstrução do estado aceito.
10. **AT10 (Reconstrução com Correção):** Histórico com eventos de conhecimento e evento posterior `correction.issued` preserva integridade fática e proveniências.
11. **AT11 (Fontes Contraditórias):** Duas fontes conflitantes recebidas em eventos distintos coexistem e consolidam o status do registro como `contested`.
12. **AT12 (Desatualizado Não é Falso na Vigência):** `resolve_claim` avalia estado expirado como `FALSE` para o presente, mas preserva sua validade no período histórico.
13. **AT13 (Inferência com Premissa Refutada):** Premissa refutada via `knowledge.revised` bloqueia novas inferências e mantém a inferência original histórica.
14. **AT14 (Facção Dividida e Subgrupo Dissidente):** Subgrupo com postura rebelde mantém planos com `visibility="subgroup_only"`, inacessíveis para a liderança.
15. **AT15 (Correção Não Reescreve Crença):** Correção de fato via `correction.issued` invalida a verdade canônica mas preserva intacta a crença subjetiva do NPC no store.
16. **AT16 (Replay e Snapshot Byte-Idêntico):** Reconstrução do zero e a partir de snapshot gera arquivos `npcs.md` e `faccoes.md` com hashes idênticos.
17. **AT17 (Matriz de Visibilidade Sem Vazamentos):** `KnowledgeView` bloqueia vazamento de segredos para todas as classes de audiência não autorizadas.

---

## 5. Critérios de Sucesso e Qualidade

1. **17/17 Cenários AT01–AT17** aprovados em suíte integrada pelo `JsonlEventStore`.
2. **100% dos 15 Apontamentos da Re-Auditoria** comprovadamente resolvidos em sondas adversariais (`probe_phase03c.py` e `probe_phase03d.py`).
3. **Limites Arquiteturais R2:** fachadas `< 100` linhas, submódulos `< 300` linhas, ausência de I/O em plugins.
4. **Zero Regressões:** todos os 230 testes da suíte completa verdes.
5. **Governança:** submissão formal para a terceira rodada de auditoria de QA sem autodeclarações indevidas em `ROADMAP.md` e `ARCHITECTURE.md`.
