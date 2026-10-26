# Feature Specification: 013 — Fase 04: Contexto Causal no `prepare`

**Feature Name:** `phase-04-causal-context`
**Status:** Draft para revisão (planejamento; nenhum código de produção alterado)
**Created:** 2026-10-26
**Target:** Fase 04 do [`ROADMAP.md`](../../ROADMAP.md), etapa R2 da refatoração arquitetural e `ContextProvider` do [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §6.1/§9.1
**Base Analisada:**
- [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 04), §5 (G4–G7 abertos), §6.4 (R2)
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §6.1 (`ContextProvider`), §8.3 (leitura de projeções), §9.1 (`prepare_turn`), §12 (R2)
- [`rpgpro-diretrizes-agentes.md`](../../rpgpro-diretrizes-agentes.md) §10.1 (contexto por relevância causal) e §10.2 (memória em camadas)
- [`specs/012-phase-03-agents/spec.md`](../012-phase-03-agents/spec.md) e [`data-model.md`](../012-phase-03-agents/data-model.md) (estado de agentes e contrato epistêmico)
- [`application/prepare.py`](../../application/prepare.py) (implementação atual, 475 linhas)
- [`tests/test_boundary_contracts.py`](../../tests/test_boundary_contracts.py) (snapshot de contrato do payload)

---

## 1. Contexto e Objetivo

As Fases 02 e 03 entregaram a verdade causal (event log, projeções, correções) e o estado de agentes (NPCs, facções, conhecimento, admissão). O `prepare`, porém, continua montando contexto **por presença física e por Markdown reparseado**: NPCs e facções distantes não entram, planos e conhecimentos não são consultados, e a distinção `desconhecido`/`indisponível`/`inexistente` não existe no payload.

A Fase 04 muda o `prepare` para montar contexto **por relevância causal**, em três camadas:

1. **Núcleo obrigatório:** regras, estado do protagonista, tempo, localização, arco ativo, objetivos relevantes e restrições.
2. **Contexto causal da cena:** NPCs e facções pertinentes, planos, missões, relógios, fatos anteriores, consequências e conhecimento — inclusive entidades distantes cujo plano, ameaça, dívida ou relação pode afetar a decisão atual.
3. **Consulta sob demanda:** a IA consulta o estado persistente quando o núcleo não basta, com a mesma matriz de visibilidade da Fase 03.

A ausência de um detalhe no contexto **não autoriza inventá-lo como fato**: toda lacuna precisa ser classificada como `unknown`, `unavailable` ou `inexistent`.

---

## 2. Escopo e Fronteiras Arquiteturais

### 2.1 Dentro do Escopo

1. **Porta `ContextProvider` e modelos de contexto** em `contracts/` e `resources/context/`, puros e determinísticos.
2. **Provedores padrão** para núcleo (regras, protagonista, cena) e contexto causal (missões, relógios, NPCs, facções, conhecimento, fatos/consequências).
3. **Seleção por relevância causal** de NPCs e facções distantes, com pontuação inteira determinística, desempate estável e explicação (`reasons`).
4. **Camadas no payload do `prepare`** (`context.core`, `context.causal`, `context.query`, `context_omissions`), preservando todas as chaves legadas (`step_1_*` a `step_4_*`).
5. **Políticas por modo/audiência:** `gm`, `narrator`, `writer`, `architect`, `director` e `reviewer`, com separação rígida entre jogador, protagonista e universo.
6. **Consulta sob demanda** (`ContextQueryService` + CLI `query`) respeitando a matriz de visibilidade da Fase 03.
7. **Cache de estado derivado** (`estado.json`) produzido por projector e lido pelo `prepare`, com `last_seq`, hash e detecção de staleness — sem reparsear o log inteiro quando o cache está fresco.
8. **Extração R2 de `context/`** e redução de `application/prepare.py` para menos de 300 linhas, movendo arbitragem mecânica para `application/arbitration.py`.
9. **Suíte de aceite da Fase 04** (C01–C10), snapshot dourado e teste de não-reparseamento.

### 2.2 Fora de Escopo

- `world_tick`, scheduler global, orçamento adaptativo, retry e retomada (Fase 05 / G4).
- Diretor narrativo causal, arcos flexíveis por marcos e controle formal de revelação (Fase 06 / G5).
- Indexação semântica e memória derivada de longo prazo (Fase 07 / G6).
- Migração das três campanhas e os 10 cenários de comportamento (Fase 08 / G7).
- Chamadas a LLM; o `prepare` continua devolvendo contexto e mandato, não prosa.
- Novos `EventType`s. O cache `estado.json` é projeção, não verdade (G3-D13).

---

## 3. Requisitos Funcionais

| ID | Requisito | Fonte |
| :--- | :--- | :--- |
| **FR-CTX-01** | O `prepare` monta três camadas explícitas (`core`, `causal`, `query`) e devolve `context_version`, `context_hash`, `source_last_seq` e `omissions`, mantendo todas as chaves legadas do payload. | ROADMAP Fase 04; ARCHITECTURE §9.1 |
| **FR-CTX-02** | O núcleo obrigatório contém: sistema/regras e overrides, estado do protagonista, tempo de jogo, localização, arco ativo, objetivos/restrições relevantes e cabeçalho canônico. | Diretrizes §10.1 |
| **FR-CTX-03** | O contexto causal seleciona NPCs e facções por relevância — presença física, plano iminente, ameaça, dívida, relação, vínculo com missão/relógio/arco e consequência recente — e **não apenas por presença**. Cada item traz `score` e `reasons`. | ROADMAP Fase 04; Diretrizes §10.1 |
| **FR-CTX-04** | Fatos, consequências e correções recentes entram no contexto causal quando afetam entidades selecionadas; fato corrigido não pode ser apresentado como vigente. | Fase 02; ROADMAP Fase 04 |
| **FR-CTX-05** | O conhecimento é injetado por audiência via `KnowledgeView`: `player` pode ver `player_meta`; `protagonist` não; `narrator`/`writer` veem o que o protagonista sabe e os fatos da cena, nunca meta-conhecimento; `gm` vê o universo. | Fase 03; Diretrizes §3.7; AT17 |
| **FR-CTX-06** | Toda lacuna referenciada pela ação/cena é classificada como `unknown`, `unavailable` ou `inexistent`, com motivo e fonte; o `prepare` nunca inventa fato ausente. | Diretrizes §10.1 |
| **FR-CTX-07** | Existe consulta sob demanda ao estado persistente (`ContextQueryService`) para claim, NPC, facção, missão e relógio, com a mesma visibilidade, exposta também por CLI `query` em JSON. | ROADMAP Fase 04 |
| **FR-CTX-08** | O `prepare` lê o cache derivado `estado.json`; se `last_seq` divergir do store ou o arquivo faltar, reconstrói o cache uma vez e registra `context.stale=true` na resposta. Com cache fresco, não chama `EventStore.read`. | ARCHITECTURE §8.3 |
| **FR-CTX-09** | A saída é determinística: mesma entrada + mesmo `last_seq` ⇒ mesmo `context_hash`; ordenação por `(-score, kind, id)`; nenhuma dependência de relógio real, `set` ou hash de dicionário. | ARCHITECTURE §6.3; Fase 02 |
| **FR-CTX-10** | Modos aplicam políticas distintas: `gm` (universo/arbitragem), `narrator`/`writer` (protagonista/narração), `architect` (autor/estrutura), `director` (autor/direção), `reviewer` (auditoria, sem contexto novo). | `MODE_PROSE_MANDATES`; Fase 03 |
| **FR-CTX-11** | Módulos novos em `resources/context/`, `application/context/` e `contracts/` ficam `< 300` linhas; `application/prepare.py` fica `< 300`; `plugins/` continua sem I/O; `tests/test_architecture_boundaries.py` cobre os novos arquivos. | ARCHITECTURE §12 (R2), §15 |
| **FR-CTX-12** | O payload legado permanece compatível: `test_boundary_prepare_payload_snapshot` continua passando sem alteração de campos existentes; novos campos são aditivos. | `tests/test_boundary_contracts.py` |

---

## 4. Critérios de Aceitação (C01–C10)

- **C01 (Núcleo):** payload contém regras, protagonista, tempo, localização, arco, objetivos e restrições no núcleo; `context_hash` estável entre duas execuções idênticas.
- **C02 (Antagonista distante):** um NPC/facção fora da cena, com plano ativo iminente ou relógio crítico, entra no contexto causal com `score > 0`, `reasons` explícitas e aparece em `causal.entities`.
- **C03 (Presença não é suficiência):** NPC presente sem relevância causal aparece no elenco de cena/background, mas não é promovido a entidade causal; NPC distante relevante é incluído.
- **C04 (Conhecimento por audiência):** para a mesma claim, `player` recebe `player_meta`; `protagonist` recebe `unknown`/`unavailable`; `narrator`/`writer` não recebem `player_meta`; `gm` recebe o universo. Nenhum vazamento.
- **C05 (Fatos e correções):** fato corrigido por `correction.issued` não entra como vigente; a correção e as consequências afetadas entram com referência ao evento.
- **C06 (Omissões):** ação que cita NPC/claim inexistente gera `omissions` com `inexistent`; entidade existente mas invisível gera `unavailable`; entidade existente e desconhecida pelo holder gera `unknown`; nenhum desses casos produz item inventado.
- **C07 (Consulta sob demanda):** `query claim|npc|faction|quest|clock` devolve JSON determinístico e respeita a mesma visibilidade do contexto.
- **C08 (Cache e staleness):** com `estado.json` fresco, `prepare` não chama `EventStore.read` (teste com stub que falha); com `last_seq` divergente, o cache é reconstruído e `stale=true` aparece.
- **C09 (Compatibilidade e determinismo):** suíte legada continua verde; `context_hash` muda quando o estado muda e permanece igual quando não muda; nenhuma chave legada é removida.
- **C10 (Modos e R2):** cada modo produz a audiência/propósito esperados; `application/prepare.py < 300` linhas; novos módulos `< 300`; nenhum I/O em `plugins/`; fronteiras AST verdes.

---

## 5. Modelo Conceitual do Contexto

```text
TurnContext
├── request: ContextRequest      (campanha, modo, ação, cena, viewer, audience, purpose, limites)
├── core: ContextSection         (obrigatório)
├── causal: ContextSection       (relevância causal)
├── query: ContextQueryHandles   (holder, audience, entidades consultáveis, comandos)
├── omissions: tuple[ContextOmission, ...]
└── meta: version, source_last_seq, context_hash, stale, providers
```

- **`ContextItem`**: `kind`, `id`, `label`, `layer`, `score`, `reasons`, `availability`, `payload`, `sources` (event/record IDs).
- **`ContextOmission`**: `kind`, `reference`, `availability` (`unknown|unavailable|inexistent`), `reason`, `sources`.
- **`ContextSection`**: `key`, `layer`, `items`, `omissions`, `hash`.
- **`ContextRequest`**: `campaign_id`, `mode`, `action`, `scene` (time, location, present, scene_type), `viewer`, `audience`, `purpose`, `focus`, `limits` (max NPCs/facções/fatos), `seed`.
- **`ContextStateView`**: visão imutável do cache (`last_seq`, npcs, factions, knowledge, quests, clocks, arc, recent_events).

O payload legado (`step_1_*`…`step_4_*`) passa a ser **derivado** das camadas, preservando os mesmos campos e valores de baseline.

---

## 6. Políticas por Modo e Audiência

| Modo | Audiência | Propósito | Inclui | Nunca inclui |
| :--- | :--- | :--- | :--- | :--- |
| `gm` | universo | arbitragem | tudo, inclusive segredos e `player_meta` | — |
| `narrator` | protagonista | narração | o que o protagonista sabe, fatos da cena, planos visíveis | `player_meta`, segredos de outros holders |
| `writer` | protagonista | prosa | idem narrator | idem |
| `architect` | autor | estrutura | arcos, fios, relógios, planos, omissões estruturais | segredos de cena irrelevantes |
| `director` | autor | direção | arcos/fios/relógios (Fase 06 consumirá) | prosa e metas do jogador |
| `reviewer` | auditoria | auditoria | issues existentes | contexto novo |

A audiência é derivada do modo, mas pode ser sobrescrita por `--audience` (avançado) para depuração; a política nunca amplia visibilidade sem modo explícito.

---

## 7. Decisões em Aberto (recomendações para aprovação)

| ID | Decisão | Recomendação |
| :--- | :--- | :--- |
| **D1** | Nome/local do cache de estado | `estado.json` como projector `StateProjector` (`order=50`), gravado em `projections/` e na raiz pelo `ProjectionEngine`, com `schema_version`, `last_seq`, `hash`. |
| **D2** | Pesos e limites da relevância | Inteiros: presença 1000, foco 500, relógio crítico 300, plano iminente 300, missão 250, arco 200, ameaça 200, dívida 150, consequência 100, distância −100; limiares 200; top 5 NPCs e 3 facções, configuráveis em `regras.md` (`context:`). |
| **D3** | Mapa modo→audiência | Tabela da §6; `--audience` só para depuração. |
| **D4** | Superfície da consulta | `ContextQueryService` (Python) + CLI `lazy_turn.py query` com subcomandos; saída JSON. |
| **D5** | IDs de jogador/protagonista | `player_id`/`protagonist_id` opcionais em `regras.md`; fallback `player` e slug do nome do protagonista. |
| **D6** | Registrar o hash no commit | Opcional nesta fase: `commit --context-hash` grava em `turn.proposed.meta`; se não aprovado, apenas `prepare` devolve o hash. |
| **D7** | Staleness | Reconstruir automaticamente com `emit_audit_event=False` e marcar `stale=true`; falha de reconstrução é erro explícito, nunca contexto vazio silencioso. |

---

## 8. Critérios de Sucesso

1. **C01–C10 verdes** em suíte dedicada, com estados construídos via `JsonlEventStore` e `rebuild_projections`.
2. **234 testes legados continuam verdes**, inclusive o snapshot de contrato do `prepare`.
3. **Antagonista distante** com plano iminente entra no contexto; NPC presente e irrelevante não é promovido.
4. **Zero vazamento** de `player_meta` para protagonista/narrador/writer.
5. **Zero invenção:** toda lacuna referenciada tem omissão classificada.
6. **Sem reparseamento** do log quando o cache está fresco (teste instrumentado).
7. **`context_hash` determinístico** e `prepare < 300` linhas; novos módulos `< 300`; fronteiras verdes.

---

## 9. Riscos e Mitigações

| Risco | Mitigação |
| :--- | :--- |
| Refatoração do `prepare` quebrar o payload legado | Snapshot de contrato + testes de paridade antes de mover lógica; chaves novas apenas aditivas |
| Relevância subjetiva/instável | Pesos inteiros documentados, desempate determinístico, `reasons` auditáveis, configuração explícita |
| Cache `estado.json` divergir do log | `last_seq` + hash; reconstrução automática; teste de staleness |
| Vazamento epistêmico em modo `narrator`/`writer` | Políticas por modo + testes de matriz de audiência; reutilizar `KnowledgeView` |
| Contexto grande demais | Limites por camada (top-K) e contagem no payload; orçamento real fica para Fase 05 |
| Custo de projetar estado a cada commit | Snapshot incremental pelo projector existente; medir tempo em teste de fumaça |

---

## 10. Dependências e Gates

- **Depende de:** Fases 02 (event log/projeções/correções) e 03 (agentes/conhecimento/visibilidade), ambas concluídas.
- **Não possui gate próprio.** O G4 continua aberto e bloqueia a Fase 05; o G5 bloqueia a Fase 06.
- **R2:** esta fase executa a extração de `context/` prevista em ARCHITECTURE §12.

---

## 11. Fora de Escopo Explícito (anti-scope creep)

- Não implementar `world_tick`, scheduler, orçamento, retry ou fila persistente.
- Não implementar diretor, arcos flexíveis, estagnação ou revelação formal.
- Não implementar memória vetorial, resumos derivados ou indexação semântica.
- Não chamar LLM nem gravar prosa no `prepare`.
- Não alterar o catálogo de eventos nem a semântica de `commit`.
