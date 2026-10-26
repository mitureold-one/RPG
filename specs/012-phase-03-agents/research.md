# Architectural Research: 012 — Fase 03: Agentes, Conhecimento Epistêmico e Refatoração R2

**Feature:** `phase-03-agents`  
**Status:** Completed  
**Created:** 2026-10-26  
**Context:** Resolução das decisões de engenharia, trade-offs e arquitetura para implementar a Fase 03 do [`ROADMAP.md`](../../ROADMAP.md) e a etapa R2 da refatoração arquitetural ([`ARCHITECTURE.md`](../../ARCHITECTURE.md)), fundamentada no Gate G3 ratificado com emendas ([`g3-decision-record.md`](g3-decision-record.md)).

---

## 1. Decisão 1: Estratégia de Decomposição R2 sem Quebra de Compatibilidade (`council/` -> `resources/`)

* **Contexto:** `council/factions.py` (853 linhas), `council/narrator.py` (633 linhas) e `council/quests.py` (507 linhas) violam o limite arquitetural de 300 linhas por módulo. A Condição 3 do G3 determina que o R2 deve preceder a expansão desses domínios na Fase 03. Ao mesmo tempo, 211 testes existentes e os comandos da CLI importam funções públicas diretamente de `council.narrator`, `council.factions` e `council.quests`.
* **Decisão:**
  - Seguir exatamente o padrão bem-sucedido de `council/ssot.py` (R1) e `council/helpers.py` (R0d):
    1. Extrair a lógica de `council/quests.py` para `resources/quests/` (`parser.py`, `mutations.py`, `ledger.py`), deixando `council/quests.py` como fachada reexportadora (< 60 linhas).
    2. Extrair a lógica de `council/narrator.py` para `resources/npcs/` (`parser.py`, `mutations.py`, `initiative.py`, `scene_director.py`, `model.py`, `service.py`), deixando `council/narrator.py` como fachada (< 70 linhas).
    3. Extrair a lógica de `council/factions.py` para `resources/factions/` (`parser.py`, `reputation.py`, `tick.py`, `context.py`, `model.py`, `service.py`), deixando `council/factions.py` como fachada (< 70 linhas).
    4. Criar `resources/knowledge/` (`model.py`, `resolver.py`, `provenance.py`, `view.py`, `service.py`) para o motor epistêmico G3.
  - Nenhum arquivo em `resources/` poderá ultrapassar 300 linhas (fiscalizado em `tests/test_architecture_boundaries.py`).
* **Racional:**
  - Preserva 100% dos 211 testes existentes sem necessidade de reescrever imports nos testes legados, enquanto isola responsabilidades em módulos pequenos e coesos prontos para receber as extensões da Fase 03.
* **Alternativas Consideradas:**
  - *Remover `council/*.py` e alterar todos os imports do repositório*: Descartado por violar a regra de migração do [`ROADMAP.md`](../../ROADMAP.md) §6.5 ("Manter os nomes públicos reexportados; os testes atuais são o contrato").

---

## 2. Decisão 2: Identidade de Alegação (`Claim`) e Resolvedor Determinístico de Verdade (G3-D01, G3-D10)

* **Contexto:** Agentes precisam raciocinar sobre afirmações que podem ser verdadeiras, falsas, desconhecidas ou indeterminadas, sem criar uma segunda tabela de "fatos" paralela ao event log.
* **Decisão:**
  - Introduzir `new_claim_id()` (`clm_<ulid>`) e `new_knowledge_id()` (`knw_<ulid>`) em `kernel/ids.py`.
  - Uma `Claim` contém `claim_id`, `proposition: ClaimProposition(subject, predicate, object, scope)`, `claim_type` (`occurrence | state | prediction | normative | counterfactual`), `valid_from`, `valid_to`, `source_event_id` (opcional) e `fact_ref` (opcional).
  - O resolvedor `resolve_claim(claim, at_time_sort, world_view) -> TruthValue` opera deterministicamente:
    * `normative`: retorna sempre `INDETERMINATE` (não é apta à verdade factual).
    * `prediction` / `counterfactual`: retorna `UNKNOWN` enquanto o horizonte temporal não se cumpriu ou `INDETERMINATE` se contrafactual.
    * `occurrence`: verifica na `world_view` (stream de eventos confirmados até `at_time_sort` e não anulados por `correction.issued` sem compensação) se o `source_event_id` ou predicado correspondente ocorreu (`TRUE`), se foi explicitamente refutado/contradito por evento canônico (`FALSE`), ou se não há registro conclusivo (`UNKNOWN`).
    * `state`: consulta o estado projetado na `world_view` em `at_time_sort` (`fact_ref` ex.: `npc.status`, `clock.status`, `quest.status`, `faction.leader`) e compara com `proposition.object` (`TRUE`, `FALSE` ou `UNKNOWN`).
* **Racional:**
  - Cumpre estritamente a Emenda G3-D01/G3-D10: o motor resolve a verdade contra o event log e projeções sem depender da opinião da IA e sem tabela paralela de fatos.

---

## 3. Decisão 3: Modelo Epistêmico, Proveniência Acíclica e Revisão Sem Apagar Histórico (G3-D02 a G3-D05, G3-D11, G3-D12, G3-D15)

* **Contexto:** Um agente pode conhecer um relato sem acreditar nele (`awareness` vs `stance`), inferir conclusões provisórias a partir de premissas, receber relatos contraditórios e manter crenças desatualizadas mesmo quando o mundo é corrigido.
* **Decisão:**
  - `KnowledgeRecord` imutável em memória/projeção, derivado dos eventos:
    * `knowledge.claim_registered` (registra uma `Claim` no catálogo epistêmico da campanha);
    * `knowledge.acquired` (aquisição inicial ou nova fonte sobre um `claim_id` por um `holder_id`);
    * `knowledge.inferred` (conclusão derivada de `derived_from: list[knw_id]`, exigindo validação de existência e aciclicidade DAG);
    * `knowledge.revised` (atualização de `stance`, `confidence` ou `status` por nova evidência, supersessão ou aquisição de correção);
    * `knowledge.shared` (compartilhamento explícito de um `claim_id` de um `holder` para outro `holder`, ex.: NPC -> facção ou liderança -> subgrupo).
  - Confiança (`confidence`) é representada por inteiro em basis points (`0..10000`, onde `10000 = 100.00%`), eliminando drift de ponto flutuante em replays.
  - Fontes contraditórias: quando um mesmo `holder_id` recebe uma nova `ProvenanceRef` com evidência oposta aceita sobre o mesmo `claim_id` sem refutar a anterior, o estado projetado para `(holder_id, claim_id)` assume `status="contested"`, preservando ambas as entradas em `provenance`.
  - Integração com `CorrectionService` (G3-D15): quando `correction.issued` corrige um evento `evt_X`, o estado canônico do mundo muda, mas os `KnowledgeRecord`s dos agentes que tinham `source_id=evt_X` **não têm seu `stance` reescrito automaticamente**; o fato continua acreditado pelo agente até que um evento `knowledge.revised` registre que o agente tomou ciência da correção.
* **Racional:**
  - Garante rastreabilidade completa para AT01–AT06 e AT10–AT15, mantendo 100% da verdade no event log JSONL (G3-D13).

---

## 4. Decisão 4: `KnowledgeView`, Segredos e Barreira Epistêmica (G3-D06, G3-D07, G3-D14)

* **Contexto:** O jogador, o protagonista, cada NPC, cada facção e cada subgrupo possuem horizontes de informação distintos. A Fase 04 precisará consultar essa fronteira sem ler o log bruto.
* **Decisão:**
  - `HolderRef(kind, id)` tipado com `kind` em `{"npc", "faction", "subgroup", "protagonist", "player", "world"}`.
  - `VisibilityScope` em cada registro: `public`, `holder_only`, `faction_internal`, `subgroup_only`, `protagonist_private`, `player_meta`.
  - `KnowledgeView.query(holder, audience, purpose)`:
    * Filtra apenas registros em que `holder` tem `awareness == "known"` OU que são `public` na localização/contexto, E cujo `visibility` permite exposição para `audience`.
    * Segredos com `visibility="player_meta"` (revelados ao jogador em interlúdios off-screen) retornam `UNKNOWN` quando consultados com `holder=protagonist`, impedindo metagaming (AT08).
    * Segredos de um membro de facção (`holder=npc:X`, `visibility=holder_only`) retornam `UNKNOWN` para outros membros e para `faction:F` até que `knowledge.shared` ocorra (AT07, AT14).
    * Consulta a um `claim_id` ou entidade classifica explicitamente ausências em: `unknown` (existe no mundo, mas o holder desconhece), `unavailable` (fora do escopo da view solicitada) ou `inexistent` (não registrado no mundo).
* **Racional:**
  - Substitui e complementa a heurística léxica de `extract_epistemic_forbidden_terms` por um contrato estrutural determinístico auditável (AT07, AT08, AT14, AT17).

---

## 5. Decisão 5: Modelagem de NPCs em Dois Níveis, Facções com Política Interna e Admissão (G3-D08, G3-D09)

* **Contexto:** O [`ROADMAP.md`](../../ROADMAP.md) Fase 03 exige NPCs em dois níveis (`minor` e `major`), planos em etapas, facções com liderança/subgrupos/conspirações e validação de capacidade/recurso/conhecimento antes de aceitar propostas.
* **Decisão:**
  - **NPCs (`resources/npcs/model.py`):**
    * `NpcTier`: `"minor"` | `"major"`.
    * Todo NPC possui identidade, `tier`, `faction_id`, `subgroup_id`, `attitude`, `location`, `condition`, `bonds` e `immediate_goal`.
    * NPCs `major` possuem adicionalmente: `goals` (lista de `AgentGoal` com horizonte `short|medium|long` e `priority`), `plans` (lista de `AgentPlan` com `plan_id`, `goal_id`, `steps: tuple[PlanStep, ...]`, `alternatives`, `completion_conditions`, `status`), `resources` (`dict[str, int]`), `capabilities` (`tuple[str, ...]`), `commitments` e `relations` (`dict[str, RelationalVector]` com `trust`, `rivalry`, `dependency`, `debt`, `loyalty` em `-3..+3`).
    * Promoção: `npc.promoted` eleva um NPC `minor` para `major` inicializando as estruturas avançadas sem perder vínculos ou histórico.
  - **Facções (`resources/factions/model.py`):**
    * Além de `tag`, `name`, `power`, `scale`, `clock` e `rivals`, toda facção relevante modela `collective_goals`, `plans`, `resources`, `influence`, `limitations`, `leadership` (`leader_id`, `authority_rules`, `succession_line`), `subgroups` (`dict[str, FactionSubgroup]` com `leader_id`, `stance_towards_leadership`, `agenda`, `members`) e `internal_conflicts` (divergências e conspirações).
    * Nova projeção `faccoes.md` gerada por `FactionProjector` em `application/projectors/faction.py` (quando a campanha tiver eventos de estado de facção ou `faccoes.md` ativo, mantendo `mundo.md` intocado como configuração estática conforme D1).
  - **Validador de Admissão (`resources/admission.py`):**
    * Antes de admitir uma proposta (`AgentProposal` de objetivo, plano ou intenção), `validate_proposal(proposal, agent_state, knowledge_view, faction_state)` verifica:
      1. **Conhecimento:** todas as `required_claims` citadas na proposta têm `awareness == "known"` para o `actor` na `KnowledgeView` (AT04 permite agir sobre crença falsa desde que `known` e `believed`; AT08/AT09 barra uso de fato `unknown`).
      2. **Capacidade e Recursos:** o agente possui todas as `required_capabilities` e saldo suficiente em `required_resources`.
      3. **Localização e Condição:** o agente não está incapacitado e satisfaz restrições de local.
      4. **Autoridade de Facção:** se a proposta age em nome da facção oficial, valida se o ator é `leader_id` ou possui delegação em `authority_rules`; caso contrário, só pode agir como subgrupo/conspiração dissidente.
    * Se aprovada, emite os eventos operacionais correspondentes (`npc.goal_updated`, `npc.plan_updated`, `faction.plan_updated`, etc.). Lembrete: plano aceito tem `status="active"` (intenção operacional), nunca altera fatos do mundo sozinho.
    * Se rejeitada, devolve `AdmissionResult(admitted=False, reasons=...)`; opcionalmente registra auditoria não canônica sem mutar o estado operacional.
* **Racional:**
  - Fecha todos os entregáveis da Fase 03 do [`ROADMAP.md`](../../ROADMAP.md) e os critérios AT01–AT17 com módulos enxutos e determinísticos.
