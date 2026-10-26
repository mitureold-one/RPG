# Implementation Plan: 013 — Fase 04: Contexto Causal no `prepare`

**Feature:** `phase-04-causal-context`
**Spec:** [`spec.md`](spec.md) · **Research:** [`research.md`](research.md) · **Data model:** [`data-model.md`](data-model.md) · **Contracts:** [`contracts/context_contracts.md`](contracts/context_contracts.md)
**Status:** Draft para revisão
**Created:** 2026-10-26

---

## 1. Estratégia

O `prepare` atual (`application/prepare.py`, 475 linhas) mistura três responsabilidades: carregar a campanha, resolver mecânica (rolagens/disputas) e montar o payload. A Fase 04 separa a terceira em um pipeline de contexto e extrai a segunda para `application/arbitration.py`, reduzindo o `prepare` a orquestração abaixo de 300 linhas.

Princípios:

1. **Aditivo, não substitutivo:** o payload legado (`step_1_*`…`step_4_*`) é preservado; as camadas novas são acrescentadas e os steps passam a ser derivados delas.
2. **Cache derivado, nunca verdade:** `estado.json` é projetado pelo `ProjectionEngine`; o `commit` já reprojeta na transação, então o cache fica fresco sem trabalho extra de escrita.
3. **Determinismo total:** pontuação inteira, ordenação estável, `context_hash` canônico, nenhum relógio real.
4. **Visibilidade reutilizada:** `KnowledgeView` da Fase 03 é a única porta para crenças; não há filtro epistêmico paralelo.
5. **Falha explícita:** cache ausente/velho é reconstruído; se a reconstrução falhar, `prepare` retorna erro — nunca contexto vazio silencioso.

---

## 2. Arquitetura de Módulos

```text
contracts/
  context.py                 ~180  ContextRequest/Scene/Item/Omission/Section/TurnContext/Query
  ports.py                   +30   ContextProvider, ContextStateView (Protocol)
resources/context/
  __init__.py                 ~1
  model.py                   ~120  enums, limites, validações puras
  policy.py                  ~100  modo → audiência/propósito/visibilidades
  relevance.py               ~160  pontuação, componentes, top-K, reasons
application/context/
  __init__.py                 ~1
  state.py                   ~180  ContextStateView, leitura de estado.json, staleness
  assembler.py               ~220  orquestra providers, camadas, hash, payload
  providers.py               ~240  ruleset/protagonist/scene/quest/clock
  agents.py                  ~220  npc/faction providers + relevância
  knowledge.py               ~180  knowledge/facts/consequences + omissões
  query.py                   ~160  ContextQueryService
application/projectors/
  state.py                   ~180  StateProjector (estado.json)
application/
  arbitration.py             ~220  rolagens/disputas extraídas de prepare.py
  prepare.py                 ~260  orquestração e payload legado
interfaces/cli/
  parser.py                  +~20  subcomando query
  main.py                    +~15  despacho query
tests/
  test_phase04_causal_context.py  ~450  C01–C10
  test_phase04_state_cache.py     ~180  snapshot/staleness
  fixtures/context/*              golden payload subsets
```

Todos os arquivos novos ficam `< 300` linhas; `prepare.py` e `context/*` entram no `strict_300_targets` e no teste de fronteiras.

---

## 3. Fluxo do `prepare`

```text
cmd_prepare(campaign, action, mode, ...)
  ├── load campaign + ruleset + projeções Markdown
  ├── context_request = build_request(mode, action, cena, audience)
  ├── state = ContextStateView.load(campaign)      # estado.json + staleness
  ├── sections = [p.provide(request, state) for p in providers_by_priority]
  ├── causal = relevance.filter(sections.causal, limits)
  ├── omissions = collect(request, sections, causal)
  ├── legacy_steps = assemble_legacy(sections)      # step_1..step_4
  ├── arbitration = resolve_rolls(...)              # application/arbitration.py
  └── payload = {**legacy_payload, context..., context_omissions}
```

Ordem dos providers: `core` (10–30) → `causal` (40–70). O `assembler` não conhece regras de domínio; ele só ordena, filtra e hasheia.

---

## 4. Cache de Estado

1. `StateProjector` (`order=50`) gera `estado.json` a partir de `EventStreamView`, chamando `project_npcs_state`, `project_factions_state` e `project_knowledge_state` (Fase 03).
2. `default_projectors()` inclui o projector; `rebuild_projections` e a transação do `commit` gravam o arquivo em `projections/` e na raiz.
3. `ContextStateView.load`:
   - lê `estado.json`; valida `schema_version` e `last_seq`;
   - compara com `store.last_seq(campaign_id)`;
   - se divergente/ausente: chama `rebuild_projections(..., emit_audit_event=False)`, marca `stale=true` e relê;
   - se a reconstrução falhar: `PrepareError` explícito.
4. Teste instrumentado: com cache fresco, `EventStore.read` não é chamado (stub levanta exceção).

**Trade-off:** preparar contexto após um commit custa uma leitura de JSON + projeções Markdown, não um replay. Em campanhas longas, o JSON cresce com o conhecimento; limites e poda ficam para a Fase 07.

---

## 5. Relevância Causal

`resources/context/relevance.py` é puro:

```python
def score_npc(npc, request, state, context_facts) -> tuple[int, tuple[str, ...]]
def score_faction(faction, request, state, context_facts) -> tuple[int, tuple[str, ...]]
def select(items, limits) -> tuple[ContextItem, ...]
```

- Componentes da tabela do `data-model.md` §6.
- "Plano iminente": `plan.status == active` e (`in_progress` ou atualizado nos últimos 3 turnos ou missão vinculada com relógio crítico).
- "Ameaça": `RelationalVector.rivalry >= 2` ou `trust <= -2` contra o protagonista/facção da cena; para facções, `rivals` + reputação negativa.
- "Distância": `location` conhecida diferente da cena ⇒ −100 (não exclui).
- Entidades presentes abaixo do limiar permanecem em `background_cast`; nunca são promovidas a causais.
- Saída ordenada por `(-score, kind, id)`; `reasons` são strings estáveis.

---

## 6. Conhecimento, Fatos e Omissões

- `knowledge.py` monta `KnowledgeView` conforme a política do modo e consulta claims citadas na ação/foco.
- Cada consulta gera item (`known`) ou omissão (`unknown|unavailable|inexistent`).
- `facts.py` lê `recent_events` do cache:
  - fato vigente = evento não corrigido;
  - fato corrigido = `correction.issued.corrects` → consequência, nunca fato vigente;
  - consequências = `clock.advanced`, `quest.*`, `faction.reputation_changed`, `npc.plan_updated`, `correction.issued` dos últimos turnos.
- Toda referência citada sem correspondência vira omissão; o payload não sintetiza texto ausente.

---

## 7. Consulta sob Demanda e CLI

- `ContextQueryService` lê o mesmo `estado.json` e reutiliza `KnowledgeView`.
- CLI:
  ```text
  python lazy_turn.py query --campaign <id> --kind claim|npc|faction|quest|clock \
      --id <id> --audience protagonist|player|gm [--json]
  ```
- Saída padrão legível; `--json` devolve `ContextQueryResult`.
- Nenhuma consulta escreve no log ou nas projeções.

---

## 8. Refatoração R2 e Compatibilidade

1. Extrair de `prepare.py`:
   - mecânica (needs_roll, contest, roll, custo) → `application/arbitration.py`;
   - quests/facções/NPCs/memória/epistemic barrier → `application/context/providers.py` e `agents.py`.
2. `prepare.py` passa a: carregar campanha, montar `ContextRequest`, chamar `assemble_context`, chamar `resolve_arbitration` e compor o payload legado.
3. `step_1_quest_context`, `step_1_faction_context`, `step_2_narrator_briefing`, `step_3_writer_mandate` e `step_4_post_turn_commit_template` continuam com o mesmo formato; valores de baseline idênticos.
4. `tests/test_boundary_contracts.py` roda sem alteração; o snapshot dourado novo cobre apenas as chaves aditivas.

---

## 9. Fases de Execução

| Fase | Entrega | Critério de saída |
| :--- | :--- | :--- |
| **P0** | Baseline: 234 testes verdes, `pytest`/unittest, limites atuais; branch/commit limpo | baseline registrado |
| **P1** | `contracts/context.py`, portas, `resources/context/{model,policy,relevance}` com testes puros | contratos verdes, determinismo |
| **P2** | `StateProjector`, `ContextStateView`, staleness, integração no `rebuild`/`commit` | C08 verde; JSON determinístico |
| **P3** | Providers de núcleo (`ruleset`, `protagonist`, `scene`) + `arbitration.py` | paridade do payload legado |
| **P4** | Providers causais (`quest`, `clock`, `npc`, `faction`) + relevância | C02/C03 verdes |
| **P5** | `knowledge`, `facts`, omissões | C04/C05/C06 verdes |
| **P6** | `assembler`, payload aditivo, hash, políticas por modo | C01/C09/C10 verdes |
| **P7** | `query` service + CLI | C07 verde |
| **P8** | Limpeza R2, fronteiras, quickstart, `EXECUCAO` | 234+novos verdes; `prepare < 300` |

---

## 10. Testes

- **C01–C10** em `tests/test_phase04_causal_context.py`, todos via `JsonlEventStore` + `rebuild_projections`.
- **C02:** construir NPC/facção distante com plano ativo e relógio crítico; `prepare` deve incluí-lo com `reasons`.
- **C03:** NPC presente sem vínculo não entra em `causal.items`; distante relevante entra.
- **C04:** `player_meta` para player; protagonista recebe `unknown`/`unavailable`; narrator/writer não veem meta.
- **C05:** `correction.issued` remove fato vigente e gera consequência.
- **C06:** ação cita `clm_inexistente`/NPC desconhecido; omissões corretas.
- **C07:** CLI `query` JSON e matriz de visibilidade.
- **C08:** cache fresco não chama `EventStore.read`; cache velho reconstrói e `stale=true`.
- **C09:** dois `prepare` idênticos ⇒ mesmo hash; mudança de evento ⇒ hash diferente; snapshot legado intacto.
- **C10:** matriz de modos e limites de linha/fronteiras.
- Testes de contrato de provider: pureza, sem I/O, hash estável.
- Teste de fumaça de tempo: preparar contexto com 10k eventos sintéticos < 150 ms no ambiente de CI local (alerta, não bloqueio).

---

## 11. Riscos e Mitigações

| Risco | Mitigação |
| :--- | :--- |
| Refatoração quebrar payload | Snapshot de contrato + testes de paridade antes de mover lógica |
| Relevância virar "sopa" subjetiva | Pesos fixos, `reasons`, top-K, configuração explícita, testes dourados |
| Cache divergir | `last_seq` + hash + reconstrução + teste de staleness |
| Vazamento epistêmico | `KnowledgeView` única porta; testes de matriz por modo |
| Contexto grande | Limites por camada; medir contagem no payload; orçamento na Fase 05 |
| Duplicação de parsers | Projeções Markdown continuam sendo a entrada; nenhum parser novo de diário/NPC |

---

## 12. Decisões Pendentes de Aprovação

Ver `spec.md` §7 (D1–D7). O plano assume as recomendações; qualquer mudança altera apenas os pontos indicados, não a arquitetura.

---

## 13. Definição de Pronto

- C01–C10 verdes; 234 legados verdes; fronteiras verdes.
- `application/prepare.py < 300` linhas; novos módulos `< 300`.
- `prepare` não lê o log quando o cache está fresco.
- `query` CLI funcional.
- `specs/013-phase-04-causal-context/quickstart.md` reproduzível.
- `EXECUCAO.md` com entrada da fase e `ROADMAP.md` atualizado para "em implementação" somente após aprovação da spec.
