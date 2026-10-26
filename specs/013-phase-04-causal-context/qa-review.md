# QA Review — 013 Fase 04: Contexto Causal no `prepare`

**Commits auditados:** implementação **não commitada** no worktree sobre `6eadd70` (`docs(exec): record EX-0033`).
**Data:** 26/10/2026.
**Método:** suíte completa, testes de fronteira, leitura dos módulos novos, confronto com C01–C10 de [`spec.md`](spec.md) e sondas adversariais contra o cache `estado.json`, providers, resolvedor de fatos, `query` e `prepare` real.
**Escopo:** Fase 04/R2 — `contracts/context.py`, `resources/context/`, `application/context/`, `StateProjector`, `arbitration.py`, payload do `prepare`, CLI `query` e testes da fase.

---

## 0. Veredito

**Original (26/10/2026):** Reprovado na primeira implementação (2 P0 e 5 P1 bloqueantes).  
**Status Atual (26/10/2026 — EX-0036):** **APROVADO APÓS REMEDIAÇÃO**. Todos os 2 P0, 5 P1 e achados de cache/proveniência foram integralmente sanados na especificação [`specs/014-fix-phase-04-qa-review`](../014-fix-phase-04-qa-review/spec.md), com 250 testes verdes e sondas adversariais aprovadas com sucesso.

| Gravidade | Qtd | Bloqueia a Fase 04 | Status Pós-Remediação |
| :--- | :-: | :---: | :---: |
| P0 | 2 | Sim | **Resolvido (EX-0036)** |
| P1 | 5 | Sim | **Resolvido (EX-0036)** |
| P2 | 8 | Recomendado | **Resolvido (EX-0036)** |
| P3 | 5 | Não | Monitorado |

A divergência central: os testes C04/C05/C08 usam fixtures **não canônicas** (conhecimento sem proveniência, `corrects` como `int`, rebuild sem `projection.rebuilt`) e, por isso, passam enquanto o fluxo real falha.

---

## 1. O que foi verificado e passou

| Verificação | Resultado | Evidência |
| :--- | :---: | :--- |
| Suíte completa | **Passa** | `Ran 249 tests in 58.908s`, `OK` |
| Fase 04 (C01–C10) | **9 OK** | `test_phase04_causal_context` |
| Cache (C08) | **3 OK** | `test_phase04_state_cache` |
| Fundamentos | **3 OK** | `test_context_foundations` |
| Fronteiras | **8 OK** | `test_architecture_boundaries` |
| Snapshot de contrato legado | **Passa** | `test_boundary_contracts` |
| `prepare.py` | **287 linhas** | abaixo de 300 |
| C02 antagonista distante | **Passa** | Malakor entra com `plano_iminente`/`fora_de_cena` |
| C03 presença não é suficiência | **Passa** | Bob fica em `background_cast`, não em `causal.items` |
| Cache fresco sem `EventStore.read` | **Passa** | `FailingEventStore` no teste C08 |

O recorte C02/C03 e a extração R2 (`prepare` < 300, módulos < 300) estão corretos. O problema está nos dados canônicos e em caminhos não cobertos.

---

## 2. P0 — Bloqueantes

### P0-1 — Conhecimento canônico com proveniência é descartado silenciosamente

`_dict_to_knowledge_record` (`application/context/knowledge.py:30-62`) reconstrói `ProvenanceRef` com campos que **não existem** no modelo da Fase 03:

```python
ProvenanceRef(
    source_event_id=...,
    method=...,
    source_agent=...,
    reliability=...,
)
```

O `ProvenanceRef` real exige `source_type, source_id, channel, acquired_at, acquired_at_sort, confidence`. O `TypeError` é engolido por `except Exception: return None`, então **todo registro com proveniência desaparece** de `KnowledgeCausalProvider` e de `ContextQueryService.claim`.

Prova com um `knowledge.acquired` canônico (com proveniência):

```text
_dict_to_knowledge_record -> None
prepare("Procurar clm_tesouro", audience=player):
  claims: []
  omissions: [("clm_tesouro", "inexistent")]
```

C04 só passa porque o fixture cria `knowledge.acquired` **sem** `provenance` (`tests/test_phase04_causal_context.py:126-136`) — um registro que a Fase 03 considera inválido (AT03). O caminho real (com proveniência) não entrega conhecimento nenhum.

**Correção:** reconstruir `ProvenanceRef` com os campos corretos, não engolir exceção e falhar explicitamente em registro inválido; o teste C04 deve usar proveniência canônica.

### P0-2 — `prepare` quebra em qualquer NPC com relacionamento

`score_npc` (`resources/context/relevance.py:124-130`) assume que `npc_data["relationships"]` é um dicionário:

```python
rv = npc_data.get("relational_vector") or npc_data.get("relationships") or {}
rivalry = rv.get("rivalry", 0)
```

Mas `estado.json` serializa `NpcState.relationships` como **lista de dicts**. Resultado:

```text
prepare("Aemon observa Kael") -> AttributeError: 'list' object has no attribute 'get'
```

Qualquer campanha com um `npc.relationship_updated` (Fase 03) não consegue executar `prepare`. Nenhum teste cobre relacionamentos; o fixture de C02 não tem relação.

**Correção:** normalizar `relationships` (lista ou dict), escolher o vetor do alvo relevante e testar o cenário.

---

## 3. P1 — Bloqueantes de confiabilidade

### P1-1 — Cache entra em loop de staleness após `rebuild` padrão

`StateProjector` calcula `last_seq` com os eventos de domínio, filtrando `projection.*` (`application/projectors/state.py:122-127`). O `rebuild_projections` padrão (`emit_audit_event=True`, usado por `lazy_turn.py rebuild`) grava um `projection.rebuilt` depois; o store passa a ter `seq=6`, o `estado.json` fica `seq=5`:

```text
store.last_seq: 6 | estado.last_seq: 5
load.stale: True | load.last_seq: 5
```

`ContextStateViewImpl.load` detecta divergência, reconstrói e devolve `stale=true`; na próxima chamada repete. Depois de um `rebuild` de CLI, **todo `prepare` reescreve as projeções** e reporta contexto stale. O teste C08 usa `emit_audit_event=False` e não pega o caminho real.

**Correção:** separar `last_seq` (inclui eventos de auditoria) do hash (exclui `projection.rebuilt`), ou gravar o cache após o evento de auditoria; testar com `emit_audit_event=True`.

### P1-2 — Correções canônicas (`corrects` com `event_id`) não invalidam fatos

`FactsCausalProvider` só aceita `corrects` como `int` (`application/context/knowledge.py:171-178`). O contrato da Fase 02 é `corrects: list[str]` de `evt_<ulid>` (`specs/010-phase-02-causal-history/data-model.md:164`). O teste C05 passa por usar `"corrects": [7]` (seq), fora do contrato.

Prova com correção real por `event_id`:

```text
facts/consequences: [('correction_8', ...), ('consequence_3', ...), ('fact_7', 'Portão reforçado')]
```

O fato corrigido continua como vigente. **Correção:** comparar `corrects` com `event_id` (incluir `event_id` em `recent_events`) e atualizar o teste C05.

### P1-3 — `ContextQueryService` não encontra claims canônicas

Há duas classes `HolderRef`: `contracts.context.HolderRef` e `resources.knowledge.model.HolderRef`. A comparação é falsa:

```text
contract == domain: False
```

`ContextQueryService.claim` (`application/context/query.py:42-54`) passa o `HolderRef` de contrato a um `KnowledgeView` que compara com `HolderRef` de domínio; o registro direto nunca casa. Somado ao P0-1, `query claim` devolve:

```text
availability='inexistent', reason='Alegação inexiste no repositório'
```

O CLI também resolve `--audience protagonist` com `protagonist_id="protagonist"` padrão, não com o nome do protagonista da campanha. C07 só testa `unavailable`, mascarando o caminho `known`.

**Correção:** uma única `HolderRef` (mover para `contracts` ou reutilizar a de domínio), converter IDs e testar `query claim known` para player e protagonista.

### P1-4 — Gameplay legado perde seleção focal e filtro de missões

A extração R2 alterou comportamento:

- `resolve_scene_actors` (`application/context/scene.py:57-61`): o fallback antigo selecionava os **2 primeiros NPCs presentes**; agora seleciona apenas o primeiro com `will`/`plan`. Em campanhas sem `Vontade` preenchida, `focal_npcs` pode ficar vazio, mudando `step_2_narrator_briefing`, `mandatory_npc_updates` e o commit sugerido.
- `build_quest_context` (`application/context/scene.py:166-181`): não filtra mais `status == "ACTIVE"` e perde os alertas de relógio crítico; `step_1_quest_context` passa a listar missões concluídas e um mandato genérico.
- C09 só verifica presença de chaves, não valores; o snapshot de contrato também.

Isso viola FR-CTX-12 e a promessa behavior-preserving do R2.

### P1-5 — Cobertura de aceite não representa os caminhos reais

Os testes que sustentam “C01–C10 integralmente atendidos” usam fixtures que evitam os bugs:

| Critério | O que o teste faz | Problema |
| :--- | :--- | :--- |
| C04 | conhecimento **sem proveniência** | registro não canônico; P0-1 escondido |
| C05 | `corrects: [7]` (int) | correção canônica por `event_id` não testada; P1-2 escondido |
| C08 | `emit_audit_event=False` | loop de staleness do `rebuild` real escondido; P1-1 |
| C07 | só serviço, nunca CLI; só `unavailable` | P1-3 escondido |
| C09 | só presença de chaves | hash/payload e regressões de valor não testados |
| C10 | só audience/purpose | sem matriz de vazamento nem valores legados |

**Consequência:** a declaração de conclusão da fase não se sustenta; os 249 verdes dão falsa confiança.

---

## 4. P2 — Correções importantes

1. **Plano de facção nunca pontua:** `score_faction` procura `plan`/`initiative` (`relevance.py:198-202`), mas o estado serializa `active_plan`; facção distante com plano ativo não recebe `plano_iminente`.
2. **GM não vê o universo:** `resolve_mode_policy` usa `player:gm` (`policy.py:31-35`); `KnowledgeCausalProvider` com holder `None` só enxerga `public`/`player_meta`, não `faction_internal`/segredos. FR-CTX-05/10.
3. **Núcleo sem overrides/restrições:** `RulesetCoreProvider` envia apenas sistema/DC/tiers; overrides ficam só em `step_1_gm_arbitration`. FR-CTX-02.
4. **Query handles vazam IDs:** `ContextQueryHandles.entities` lista todos os NPCs/facções do estado, sem filtro de audiência (`assembler.py:129-138`), contrariando o data-model §2.6.
5. **Hash ignora payload:** `_section_hash` cobre apenas `(kind,id,score,availability)`; mudança de `stance`/`confidence`/`summary` com mesmo id não altera hash de seção (o `context_hash` só muda por `source_last_seq`).
6. **Claims registradas sem registro:** `estado.json` não guarda `registered_claims`; claim registrada sem `knowledge.acquired` retorna `inexistent` em vez de `unknown`.
7. **Fatos sem filtro de relevância:** `FactsCausalProvider` inclui os últimos fatos/consequências independentemente da ação/entidades; C05 não cobre relevância.
8. **Cache ignora `schema_version`:** `ContextStateViewImpl.load` lê qualquer JSON com `last_seq`, sem validar versão (`state.py:131-132`).

---

## 5. P3 — Higiene

- `ContextScene.game_time_sort` recebe `last_turn_num` (`prepare.py:212`), não tempo de jogo.
- `ContextQueryService.npc/faction/quest/clock` não aplica visibilidade epistêmica (só claims).
- `ContextAssembler` só detecta omissões para tokens `clm_`, `npc_`, `fac_`; referências em linguagem natural não geram omissão.
- `StateProjector` guarda `payload` inteiro dos últimos 50 eventos em `recent_events`, sem resumo.
- `prepare` com `create_event_store` falhando segue com `store=None` e cache possivelmente stale, sem erro explícito.

---

## 6. Reprodução

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"     # 249 OK (falsa confiança)
python .tmp/probe_phase04.py                            # cache/knowledge/relationship/hash
python .tmp/probe_phase04b.py                           # prepare com relationship, knowledge, correção
python -c "from contracts.context import HolderRef as C; from resources.knowledge.model import HolderRef as D; print(C('protagonist','Aemon') == D('protagonist','Aemon'))"
```

**Arquivos auditados:** `contracts/context.py`, `contracts/ports.py`, `resources/context/{model,policy,relevance}.py`, `application/context/{state,assembler,providers,agents,knowledge,query,scene}.py`, `application/projectors/state.py`, `application/arbitration.py`, `application/prepare.py`, `application/rebuild.py`, `interfaces/cli/{parser,main}.py`, `tests/test_phase04_*.py`, `tests/test_context_foundations.py`, `specs/013-phase-04-causal-context/*`.
