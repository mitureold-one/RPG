# QA Review — 014 Fase 04: Re-auditoria da Remediação (EX-0036)

**Commit auditado:** `6e91074` (`feat(phase-04): implementar contexto causal e remediacao de QA (EX-0036)`), worktree limpo.
**Data:** 26/10/2026.
**Método:** suíte completa, testes da fase, leitura do diff de remediação, confronto com C01–C10 de [`specs/013-phase-04-causal-context/spec.md`](../013-phase-04-causal-context/spec.md) e com FR-FIX-01 a FR-FIX-08 de [`spec.md`](spec.md), além de sondas adversariais (`probe_phase04.py`, `probe_phase04b.py`, `probe_phase04c.py`).
**Escopo:** remediação dos 2 P0, 5 P1 e P2 críticos da primeira implementação da Fase 04.

---

## Re-auditoria final — 26/10/2026 (EX-0038)

**Commit auditado:** `bc8c2ff` (`fix(phase-04): sanar escopo residual ...`), worktree limpo.
**Suíte:** **250 testes OK em 67,8 s**; fronteiras **8 OK**; fase 04 **16 OK**; `prepare.py` 287 linhas.
**Sondas:** `probe_phase04.py`, `probe_phase04b.py` e `probe_phase04c.py`, todas sem crash e com os cenários esperados.

**Veredito: APROVADO COM RESSALVAS MENORES.** Os 2 P0, todos os P1 e os 6 P2 anteriores foram fechados e verificados. Restam apenas P3 de acabamento/documentação; o Gate técnico da Fase 04 (C01–C10) está atendido.

### 1. Fechados nesta rodada

| Achado | Status | Evidência |
| :--- | :---: | :--- |
| P1 fallback focal | **Fechado** | `dinastia_cinzas`: `focal: ['Lady Vespera', 'Sylvia']`; fallback dos 2 primeiros presente |
| P2-1 `unknown` × `inexistent` | **Fechado** | `clm_desconhecida` registrada sem registro → omissão `unknown` |
| P2-2 GM universo | **Fechado** | modo `gm` usa `universe:gm`; `faction_internal` visível (`clm_segredo_fac` em `causal.items`) |
| P2-3 núcleo com overrides/restrições | **Fechado** | `context.core` ruleset expõe `system`, `dc_ladder`, `tier_names`, `overrides`, `restrictions` |
| P2-4 `query.entities` filtrado | **Fechado** | protagonista lista apenas entidades presentes/ativas/vinculadas |
| P2-5 hash sensível a payload | **Fechado** | `_section_hash` inclui `payload` e `reason`; teste C09 confirma hashes diferentes |
| P2-6 fatos por relevância | **Fechado** | `FactsCausalProvider` pontua por ação/presentes/local/recência e aplica limiar |
| Mandato de missão | **Fechado** | C09 confirma `ALERTA CRÍTICO` a 1 passo da ruptura de relógio |
| C06/C07/C09/C10 | **Fechado** | `unknown`/`unavailable` cobertos; parser CLI exercitado; matriz GM/Player/Narrador validada |

### 2. P3 — ressalvas de acabamento

1. **Cena com um único NPC presente e sem vontade/plano fica sem focal.** O fallback só entra com `len(scene_npcs) >= 2` (`application/context/scene.py:59-61`); o comportamento antigo selecionava esse único NPC. Cena de um só interlocutor perde `focal_npcs` e `mandatory_npc_updates`.
2. **`--audience gm` em modo `narrator`/`writer`** continua mapeando para `player:player`; só o modo `gm` padrão usa `universe:gm`. O override explícito “gm” deveria ser universo.
3. **C07 exercita o parser CLI, não a execução do comando `query`**; o caminho `main()` continua sem teste automatizado.
4. **`ContextScene.game_time_sort`** recebe `last_turn_num`, não tempo de jogo (`application/prepare.py:212`).
5. **Governança documental:** `ROADMAP.md` linha 141 já declara a Fase 04 “aprovada ... homologadas ... EX-0036”, antes do parecer final; a referência deve apontar para `EX-0039` e para este parecer.

### 3. Reprodução

```powershell
$env:PYTHONPATH='.'
python -m unittest discover tests
python .tmp/probe_phase04.py
python .tmp/probe_phase04b.py
python .tmp/probe_phase04c.py
```

---

## 0. Veredito

**Reprovado com escopo residual pequeno.** Os **2 P0 e 4 dos 5 P1** foram sanados e verificados; permanecem **1 P1** (fallback de atores focais, exigido por FR-FIX-06/SC-05) e **6 P2**. Há ainda um **P0 de governança**: o implementador alterou o veredito do parecer de QA (`specs/013-phase-04-causal-context/qa-review.md`) para “APROVADO APÓS REMEDIAÇÃO” sem auditoria independente; o parecer foi restaurado pelo QA.

| Gravidade | Qtd | Bloqueia a homologação |
| :--- | :-: | :---: |
| P0 de governança | 1 | Sim |
| P1 técnico | 1 | Sim |
| P2 | 6 | Recomendado |
| P3 | 4 | Não |

---

## 1. Fechados e verificados

| Achado original | Status | Evidência |
| :--- | :---: | :--- |
| P0-1 conhecimento com proveniência descartado | **Fechado** | `_dict_to_knowledge_record` reconstrói `ProvenanceRef` canônico; probe com `knowledge.acquired` + provenance devolve registro e o claim aparece em `causal.items` |
| P0-2 crash em NPC com relacionamento | **Fechado** | `_extract_relational_vector` normaliza `list[dict]`/`dict`; `prepare` com `npc.relationship_updated` conclui sem `AttributeError` |
| P1-1 loop de staleness após `rebuild` | **Fechado** | `rebuild` com `emit_audit_event=True` → `load.stale=False`, `last_seq` igual ao store |
| P1-2 correção por `event_id` | **Fechado** | `recent_events` inclui `event_id`; `corrects: ["evt_..."]` remove o fato vigente |
| P1-3 `HolderRef`/query de protagonista | **Fechado** | `HolderRef` unificado (mesma classe); `query claim` player → `known`, protagonista → `unavailable` |
| P1-5 fixtures não canônicas | **Parcial** | C04 agora usa proveniência, C05 usa `event_id`, C08 usa auditoria; C06/C07/C09 ainda rasos (ver §4) |

**Suíte:** **250 testes OK em 59,9 s**; fronteiras **8 OK**; fase 04 **13 OK**; `prepare.py` 287 linhas.

---

## 2. P0 — Governança

### P0-GOV — Veredito de QA reescrito pelo implementador

O arquivo `specs/013-phase-04-causal-context/qa-review.md` é o parecer independente do QA. No commit `6e91074`, a seção “0. Veredito” foi alterada de **“Reprovado”** para **“APROVADO APÓS REMEDIAÇÃO”**, com a tabela marcando P0/P1/P2 como “Resolvido (EX-0036)”.

Isso inverte o papel das partes: implementação não homologa a si mesma, e o parecer de QA não pode ser reescrito pelo implementador. O veredito foi restaurado nesta re-auditoria; a aprovação depende de novo parecer independente após os itens abaixo.

---

## 3. P1 — Fallback focal não restaurado

`FR-FIX-06` e `SC-05` da spec 014 exigem: “os dois primeiros NPCs presentes são mantidos como atores focais por fallback” quando nenhum tem vontade/plano. O código continua com:

```python
if not focal_names and scene_npcs:
    for n in scene_npcs:
        if n.get("will") or n.get("plan"):
            focal_names.add(str(n.get("name", "")))
            break
```

(`application/context/scene.py:57-61`)

Prova na fixture `dinastia_cinzas`, cena com Lady Vespera e Sylvia presentes:

```text
focal: ['Lady Vespera']
background: ['Sylvia (...']
mandatory_npc_updates: ['Lady Vespera']
```

O comportamento legado selecionava Lady Vespera **e** Sylvia; o novo deixa apenas uma focal. `build_quest_context` foi corrigido para filtrar `ACTIVE`, mas o fallback focal continua em desacordo com a própria spec de remediação.

---

## 4. P2 remanescentes

1. **Claim registrada e desconhecida vira `inexistent`.** O `estado.json` não guarda `registered_claims`; `KnowledgeCausalProvider` e `ContextQueryService` constroem `KnowledgeView` sem esse conjunto. Ação citando `clm_desconhecida` (registrada em `knowledge.claim_registered`, sem `knowledge.acquired`) retorna `inexistent`, quando o correto é `unknown` (FR-CTX-06/C06).
2. **GM não recebe o universo.** `resolve_mode_policy` usa `HolderRef("player", "gm")`; segredo `faction_internal` consultado em modo `gm` retorna `unknown`, não `known` (FR-CTX-05/10).
3. **Núcleo sem overrides/restrições.** O item `ruleset` do `context.core` expõe apenas `system`, `dc_ladder` e `tier_names`; overrides e restrições continuam só em `step_1_gm_arbitration` (FR-CTX-02).
4. **`query.entities` lista todos os IDs.** `ContextAssembler` enumera todos os NPCs/facções do estado, sem filtro de audiência, contrariando o data-model §2.6.
5. **Hash de seção ignora payload.** `_section_hash` cobre apenas `(kind, id, score, availability)`; mudança de `stance`/`confidence`/`summary` com o mesmo id não altera o hash (C09).
6. **Fatos sem filtro de relevância.** `FactsCausalProvider` inclui os últimos fatos/consequências independentemente da ação e das entidades selecionadas; o C05 não cobre esse recorte.

Além disso, o mandato de missão perdeu os alertas de relógio crítico do comportamento legado (`build_quest_context`), e o C09 continua verificando apenas presença de chaves, não valores.

---

## 5. P3 — Cobertura e higiene

- **C06** testa apenas `inexistent`; não cobre `unknown` nem `unavailable` por referência natural.
- **C07** testa somente `ContextQueryService`; o CLI `query` não tem teste automatizado.
- **C09** não compara valores legados (focal, mandato de missão) nem alteração de hash.
- **C10** verifica audiência/propósito, mas não uma matriz de vazamento por camada.
- `ContextScene.game_time_sort` continua recebendo `last_turn_num`, não tempo de jogo.
- `ContextQueryService` não aplica visibilidade a NPC/facção/quest/clock; só a claims.

---

## 6. Reprodução

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"       # 250 OK
python .tmp/probe_phase04.py                              # cache, knowledge, relationship, hash
python .tmp/probe_phase04b.py                             # prepare com relationship, knowledge e correction
python .tmp/probe_phase04c.py                             # unknown, GM universe, core
```

**Arquivos auditados:** `specs/014-fix-phase-04-qa-review/*`, `application/context/*`, `resources/context/*`, `application/projectors/state.py`, `application/prepare.py`, `contracts/context.py`, `resources/knowledge/model.py`, `tests/test_phase04_*.py`, `specs/013-phase-04-causal-context/qa-review.md`.
