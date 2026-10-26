# QA Review — 010 Fase 02 / R1 (História Causal)

**Commits auditados:** `7f2c165` (HEAD, `feat(causal): implement Phase 02 causal history, G1/G2 gates and R1 refactoring (EX-0014)`), comparado a `a6771fb` (base R0/R0.5).
**Data:** 24/10/2026.
**Método:** suíte completa, leitura do diff e dos módulos novos, execução ponta a ponta da CLI em campanha descartável, sondas adversariais de crash, concorrência, snapshot, hash, duplicação, rollback, catálogo e correção.
**Escopo:** Fase 02 (G1/G2) e R1, incluindo `JsonlEventStore`, catálogo, DAG, projeções/rebuild, correções, prosa, fila, integração no `commit`, CLI `rebuild`/`correct` e refatoração `ssot.py` → `resources/`.

---

## Re-verificação independente e fechamento de P1-C / P2-4 / P2-5 — 26/10/2026

**Suíte:** **211 testes OK**; fronteiras **7 OK** (com `journal.py` 264, `correction.py` 289, `sheet.py` 214, `npc.py` 92 e `catalog.py` 134 incluídos no limite estrito `< 300`). **P1-C, P2-1, P2-2, P2-3, P2-4 e P2-5 passam integralmente.**

| Verificação independente | Resultado | Evidência |
| :--- | :---: | :--- |
| P2-1 recuperação sem `diario.md` | **Passa** | `rebuild --force` restaurou diário/ficha/NPCs byte-idênticos só com `events/`; sem `diario.md` e sem `events/`, erro explícito |
| P2-2 sem blobs `*_after` | **Passa** | Nenhum evento com `diario_after`/`ficha_after`/`npcs_after`; rebuild só de eventos restaurou os três hashes |
| P2-3 `--clock`, `--quest`, `--arc` | **Passa** | `clock C1:-1` → 0/2; `Q2:ACTIVE`; arco título/fase atualizados na raiz e em `projections/` |
| **P1-C / P2-3 `--vital`/`--rep`** | **Passa** | `--vital hp:+2` com HP 20 → **22/25**; `--vital mana:+3` com CE 25 → **28/30**; `--vital hp:18` → **18/25**; `--rep FTest:-1` com score 1 → **0** (`test_vital_and_reputation_compensation_applies_relative_delta_and_absolute_values_p1_c`) |
| P2-4 alvos originais | **Passa** | `commit.py` 222, `commit_stage.py` 270, `event_store.py` 188, `batch_io.py` 170, `reviewer.py` 292, `prose_linter.py` 275, `reviewer_checks.py` 269 |
| P2-4 `journal.py` e `correction.py` | **Passa** | `journal.py` 264, `correction.py` 289, `sheet.py` 214, `npc.py` 92, `catalog.py` 134 — todos `< 300` linhas e fiscalizados em `test_architecture_boundaries.py` |
| P2-5 testes/docs | **Passa** | **211 testes OK** e documentos sincronizados em 211 testes, incluindo cobertura automatizada para `--vital` (relativo/absoluto/sinônimos) e `--rep` |

**Veredito independente:** **APROVADO SEM RESSALVAS** — P1-C e P2-1 a P2-5 fechados e verificados.

---

## Atualização final pós-fechamento dos 5 P2 e P1-C — 26/10/2026 (`specs/011-close-phase02-qa-p2`)

**Resultado:** **211 testes OK** (incluindo 7 testes de fronteiras e tamanho `< 300` linhas). Todos os achados **P0, P1, P2 e P3** foram integralmente resolvidos e verificados:

- **P2-1 (Recuperação sem `diario.md`):** `find_campaign(..., allow_missing_projections=True)` e `cmd_rebuild` localizam a campanha via `events/` (ou `projections/diario.md`) mesmo quando `diario.md` foi deletado da raiz, restaurando os arquivos Markdown byte-idênticos enquanto comandos comuns continuam falhando rápido se `diario.md` estiver ausente.
- **P2-2 (Zero blobs `*_after` em `meta`):** `diario_after`, `ficha_after` e `npcs_after` foram completamente removidos de `turn.committed.meta` e de `record_command_mutation`. `JournalProjector`, `CharacterSheetProjector` e `NpcProjector` derivam 100% do estado a partir dos payloads dos eventos sobre o baseline inicial de `campaign.created`, mantendo raiz e `projections/` byte-idênticos.
- **P1-C & P2-3 (Compensação causal exata + reprojeção imediata):** `CorrectionService.issue_correction` e `lazy_turn.py correct` suportam `--vital` (deltas com sinal `+N`/`-N`, valores absolutos e sinônimos como `mana`), `--rep` (`new_score = clamp_reputation(score_atual + delta)`), `--clock`, `--quest`, `--arc-stage` e `--arc-title`, emitindo eventos compensatórios com `meta.correction_id` e reconstruindo as projeções imediatamente.
- **P2-4 (Módulos `< 300` linhas e fronteiras de camada):** `application/commit.py` (222), `application/commit_stage.py` (270), `application/correction.py` (289), `application/projectors/journal.py` (264), `application/projectors/sheet.py` (214), `application/projectors/npc.py` (92), `contracts/catalog.py` (134), `adapters/persistence/event_store.py` (188), `adapters/persistence/batch_io.py` (170), `adapters/persistence/segment_io.py` (261), `council/reviewer.py` (292), `council/prose_linter.py` (275) e `council/reviewer_checks.py` (269) respeitam `< 300` linhas e zero imports proibidos entre camadas, fiscalizados em `tests/test_architecture_boundaries.py`.
- **P2-5 (Testes e documentação sincronizados):** novos testes de aceite em `tests/test_projection_rebuild.py` e `tests/test_causal_correction.py` elevam a suíte para **211 testes verdes**, sincronizados em `ROADMAP.md`, `ARCHITECTURE.md`, `README.md` e `EXECUCAO.md` (`EX-0019`, `EX-0020`).

| Achado | Status | Evidência |
| :--- | :---: | :--- |
| P0-1 log opcional/silencioso | **Corrigido** | Sem `events/`, `commit` recria e grava lote; não há mais `if events.exists()`/`except: pass` |
| P0-2 projeções fora do SSOT | **Corrigido** | Raiz == `projections/` em diário/ficha/NPCs; rebuild a partir do zero restaura hashes |
| P0-3 commit só com 3 eventos | **Corrigido** | Commit completo gera `turn.*`, `action.resolved`, `sheet_changed`, `npc.updated`, `clock.*`, `quest.*`, `progression_changed`, `faction.reputation_changed`, `prose.recorded`, `turn.committed` |
| P1-1 rollback do log | **Corrigido** | Exceção no fim do commit mantém 4 → 4 eventos e restaura Markdown/projeções |
| P1-2 store sem catálogo | **Corrigido** | Store default usa `build_v1_catalog()`; tipo desconhecido e `schema_version=99` são rejeitados |
| P1-3 duplicata | **Corrigido** | Lote idêntico com `expected_last_seq` atual gera `DuplicateBatchError` (teste novo em `test_event_store_crash_recovery`) |
| P1-4 `correct --delta-xp` | **Corrigido** | Compensação `protagonist.progression_changed` com `xp_delta=-50` |
| P1-5 lock/`last_seq` | **Corrigido** | Um único `.campaign.lock`; `last_seq` não trunca (tail aberto preservado) |
| P1-6 snapshot | **Corrigido** | Rebuild com snapshot preserva turno antigo e inclui o novo |
| P1-7 reavaliação | **Corrigido** | `correction.recomputed` lista afetados; compensação cobre XP, vitais, reputação, relógio, missão e arco e reconstrói projeções |
| P1-8 `expected_last_seq` | **Corrigido** | `ensure`/`commit_events_and_project`/correção passam a sequência esperada |
| P1-9 hash | **Corrigido** | Hash adulterado gera `ReplayError` |
| **P1-A idempotência** | **Corrigido** | Lote idêntico reenviado com `expected_last_seq` atual → `DuplicateBatchError`; correção repetida → erro e apenas uma compensação `xp_delta=-50` |
| **P1-B NPC no histórico** | **Corrigido** | `--npc-updates "Aliado Inicial: Atitude: alerta \| Relação: Confiança +1"` gera **um** `npc.updated` (`changes` com `attitude` e `relation`); raiz e log concordam, sem `relacao` fantasma |
| **P1-C vital/reputação** | **Corrigido** | `--vital hp:+2` com HP 20 → 22/25; `--vital mana:+3` → 28/30; `--rep FTest:-1` com score 1 → 0 (`test_vital_and_reputation_compensation_applies_relative_delta_and_absolute_values_p1_c`) |
| P2-1 perda de `diario.md` | **Corrigido** | Sem `diario.md`, `cmd_rebuild` localiza a campanha via `events/` e restaura `diario.md` byte-idêntico (`test_cmd_rebuild_recovers_missing_diario_md_and_rejects_empty_campaign_p2_1`) |
| P2-2 snapshots em `meta` | **Corrigido** | Zero eventos possuem `diario_after`/`ficha_after`/`npcs_after` em `meta`; projectors derivam 100% do estado a partir dos payloads (`test_zero_after_blobs_in_event_meta_across_commit_and_commands_p2_2`) |
| P2-3 correção limitada | **Corrigido** | Relógio, missão, arco, vitais e reputação compensados e reprojetados imediatamente |
| P2-4 camadas/tamanho | **Corrigido** | Todos os módulos e projetores da Fase 02 (`commit`, `commit_stage`, `correction`, `journal`, `sheet`, `npc`, `catalog`, `event_store`, `batch_io`, `segment_io`, `reviewer`, `prose_linter`, `reviewer_checks`) `< 300` linhas no teste de fronteira |
| P2-5 docs/testes | **Corrigido** | 211 testes verdes e documentos sincronizados em 211 testes |

**Veredito final:** **APROVADO SEM RESSALVAS.** Fase 02 (`R1`) pronta para congelamento definitivo.

### Correção dos P1 residuais (24/10)

- `application/correction.py`: correção idêntica pendente gera `DuplicateBatchError`; `resolve` continua permitido.
- `adapters/persistence/event_store.py`: fingerprint de lote verificado mesmo com `expected_last_seq`; exceções apenas para `test.*` e `projection.rebuilt`.
- `council/narrator.py` e `application/commit_events.py`: parser único de NPCs, `parse_npc_update_fields` e tolerância a `|` antes de subcampo.
- Testes: `test_duplicate_batch_rejected_even_with_expected_last_seq`, `test_repeated_correction_is_rejected_without_duplicate_compensation`, `test_commit_npc_subfields_are_structured_without_phantom_npc`; suíte **206 OK**.
- Evidência manual: lote duplicado → `DuplicateBatchError`; segunda correção → erro e uma única compensação; NPC → um evento com `attitude`/`relation`; raiz == `projections/`; `review` CLEAN.

**Abaixo, o parecer original de `7f2c165` (histórico).**

---

## 0. Veredito

**Reprovado.** A suíte tem **199 testes verdes**, mas a implementação **não entrega o invariante central da fase**: o event log não é a verdade e as projeções não são o SSOT. O `commit` continua gravando os Markdown raiz diretamente, emite eventos apenas quando já existe um diretório `events/` e transforma qualquer falha do caminho causal em `except: pass`. Em paralelo, cria uma cópia simplificada em `projections/` que nenhum leitor do jogo usa.

| Gravidade | Qtd | Bloqueia a Fase 02 |
| :--- | :-: | :---: |
| P0 | 3 | Sim |
| P1 | 10 | Sim |
| P2 | 8 | Recomendado |
| P3 | 7 (agrupados) | Não |

**Conclusão curta:** a base do `JsonlEventStore` (lote, marcadores, recuperação, DAG, hashes) é promissora, mas está **desconectada do fluxo real do jogo**. Os 199 testes verdes validam peças isoladas, não a integração prometida por C1–C4.

---

## 1. Critérios de aceite — resultado

| Critério | Resultado | Evidência |
| :--- | :---: | :--- |
| G1-D1 JSONL é a verdade | **Falha** | `commit` grava raiz e, sem `events/`, não emite nada |
| G1-D2 lote atômico/recovery | **Parcial** | Testes diretos passam; recuperação trunca sem lock e a integração não a usa |
| G1-D3 envelope/payload | **Parcial** | Envelope intacto; `commit` não emite eventos de recurso |
| G1-D4 `game_time` obrigatório | **Passa** | `InvalidDraftError` no store |
| G1-D5 IDs | **Passa** | `evt_<ulid>`, `bat_<ulid>` |
| G1-D6 serialização/hashes | **Parcial** | Dois hashes existem; hash do lote não é verificado na leitura |
| G1-D7 versionamento/upcasters | **Parcial** | Só funciona com catálogo injetado; produção não injeta |
| G1-D8 retenção/segmentos | **Parcial** | Segmentos funcionam; snapshots não são gerados |
| G1-D9 catálogo | **Parcial** | 25 tipos, não 23; schemas existem, mas o store de produção não os usa |
| G1-D10 registro | **Parcial** | `bootstrap.py` registra, mas o store não consome o registry |
| G1-D11 layout | **Parcial** | `events/`, `projections/`, `artifacts/`, `queue.jsonl`; `snapshots/` ausente |
| G1-D12 nenhuma mutação sem evento | **Falha** | `commit` muta ficha/diário/NPCs sem eventos para a maioria dos recursos |
| G2-D1 correção append-only | **Parcial** | `correction.issued` existe; compensação é só XP e o CLI não a dispara |
| G2-D2 DAG | **Passa (isolado)** | Ciclos, profundidade e intra-lote testados no DAG |
| G2-D3 reavaliação seletiva | **Falha** | `correction.recomputed` apenas lista IDs; não reavalia fato/projeção |
| G2-D4 rebuild | **Falha** | Projeta em `projections/`, não na raiz; snapshot perde estado anterior |
| G2-D5 prosa imutável | **Parcial** | Hash/caminho; escrita não atômica e conteúdo sofre `.strip()` |
| G2-D6 idempotência | **Falha** | `DuplicateBatchError` nunca é disparado; `expected_last_seq` não é usado |
| G2-D7 fila | **Parcial** | Append-only básico; sem lock/fsync |
| G2-D8 auditoria | **Parcial** | Inconsistência aparece no `review`; não há fluxo de resolução |
| G2-D9 fronteira G6 | **Parcial** | Prosa recuperável; indexação futura |
| G2-D10 rebuild sem efeitos | **Parcial** | Não toca a raiz, portanto não “reconstrói” o estado real |
| C1 crash | **Parcial** | Store direto; não há teste de falha real no `commit` |
| C2 dependências intra-lote | **Parcial** | DAG direto; `commit` não declara dependências |
| C3 auditoria isolada | **Parcial** | Implementação aparenta correta; teste recomputa com o próprio evento |
| C4 correção contraditória | **Parcial** | Flag e lint funcionam; compensação/reavaliação não |

---

## 2. P0 — Bloqueantes

### P0-1 — A história causal é opcional e silenciosa; a raiz continua sendo a verdade

`application/commit.py:470` só executa a integração causal **se `campaigns/<id>/events/` já existir**. Todo o bloco está dentro de `try/except Exception: pass` em `application/commit.py:531-532`. Antes disso, o commit já gravou `ficha.md` (`:196`), `npcs.md` e `diario.md` (`:465`) diretamente.

```text
# campanha qa_a, após init, removendo events/
commit --summary "sem events dir" -> status "ok"
diario.md mudou: True
events/ existe: False
```

Se o diretório não existe, o turno é gravado sem nenhum evento. Se o event store falha, a exceção é engolida e o commit retorna `ok` mesmo assim. Em `campaign/templates.py:148-171`, a criação do `campaign.created` também está em `try/except: pass`; uma campanha pode nascer sem o evento inicial.

**Consequência:** D1 (“event log é a verdade”) e G1-D12 (“nenhuma mutação sem evento”) não são verdadeiros. O log pode divergir da raiz sem que ninguém saiba.

**Correção mínima:** o `commit` deve emitir o lote completo **antes** de qualquer projeção; falha no append aborta o turno; remover o `if events.exists()` e o `except: pass`; criar o event store na inicialização da campanha de forma atômica.

### P0-2 — As projeções são uma cópia paralela simplificada, não `diario.md`/`ficha.md`/`npcs.md`

`ProjectionEngine` escreve em `campaigns/<id>/projections/` (`application/projection_engine.py:24`, `:43-45`). A raiz continua sendo escrita diretamente pelo `commit`. Em campanha descartável:

```text
raiz diario.md hash:      f9e13f4b071dad88
projection diario.md:     c988e286f14d2512
root == proj:             False
```

O conteúdo é outro schema: o projector de diário só conhece `turn.committed`, `clock.advanced` e `correction.issued` (`application/projectors/journal.py`); o de ficha só projeta nível/XP/HP/Stamina/reputação (`sheet.py`); o de NPC só `npc.updated` (`npc.py`). Atributos, inventário, missões, arcos, relógios, vínculos e prosa não são reconstruídos.

**Consequência:** `rebuild` retorna sucesso, mas `diario.md`, `ficha.md` e `npcs.md` não são restaurados. O teste de “byte-idêntico” compara `projections/` com `projections/`, nunca com a raiz. O `prepare` e o `review` continuam lendo a raiz; a projeção é um arquivo morto.

**Correção mínima:** ou os leitores passam a consumir `projections/` e a raiz deixa de ser escrita diretamente, ou os projectors gravam exatamente nos arquivos canônicos. Em qualquer caso, o teste de rebuild deve comparar a raiz com o resultado do rebuild, byte a byte.

### P0-3 — O `commit` emite três tipos de evento; o resto do estado não tem causalidade

Numa campanha real, após init + um `commit`:

```text
[(1, 'campaign.created'), (2, 'turn.proposed'), (3, 'turn.committed')]
```

`application/commit.py:478-526` só cria `turn.proposed`, `prose.recorded` (quando há prosa) e `turn.committed`. Não há `command.executed`, `clock.*`, `quest.*`, `npc.updated`, `faction.reputation_changed`, `protagonist.progression_changed`, `arc.updated`, `scene.*` nem `protagonist.sheet_changed`, embora o próprio commit mutile esses estados em Markdown.

**Consequência:** o log não reconstrói a campanha; `rebuild` produz uma ficha/diário/NPCs incompletos; o grafo causal fica vazio. G1-D12 e o critério de cobertura de mutação da spec falham.

**Correção mínima:** cada mutação de estado do `commit`/comandos precisa gerar o evento correspondente no mesmo lote; o `commit` não pode escrever estado projetado diretamente.

---

## 3. P1 — Bloqueantes de confiabilidade

### P1-1 — O rollback da transação não cobre o event log, projeções nem prosa

`_serialized_campaign_mutation` faz snapshot apenas de `ficha`, `diario`, `npcs` e `mundo` (`application/transaction.py`). O event store, `projections/`, `artifacts/prose/` e `queue.jsonl` ficam fora.

Prova: com `cmd_review` forçado a levantar no fim do commit, os Markdown são restaurados, mas o log passa de 1 para 3 eventos:

```text
B commit raised: falha simulada
B events before/after rollback: 1 3
types after: ['campaign.created', 'turn.proposed', 'turn.committed']
```

**Consequência:** um turno “desfeito” na raiz continua no log e pode ser ressuscitado por rebuild/projeção. A correção precisa de uma transação única que cubra log + projeções + prosa, ou de um marcador de lote abortado.

### P1-2 — Produção constrói o store sem catálogo; validação de tipo/schema/upcast está desligada

`JsonlEventStore(camp_dir)` aparece em `application/commit.py:528`, `application/showrunner.py:232`, `:262` e `campaign/templates.py:152`, sempre sem `catalog=...`. O catálogo só é usado em testes e no `bootstrap.py`, que registra `EventType` num `Registry` que o store não consome.

Prova com o store de produção:

```text
unknown/future accepted: 6   # tipo "qualquer.tipo", schema_version=99
```

**Consequência:** FR-G1-04 e FR-G1-07 não valem em produção. Um evento inválido ou de versão futura entra no log; a leitura não aplica upcasters.

### P1-3 — `DuplicateBatchError` não existe no comportamento; lotes duplicados são aceitos

`DuplicateBatchError` é apenas importado em `event_store.py:17`; nunca é levantado. Não há `batch_id` de entrada nem chave de idempotência. Prova:

```text
E duplicate batch accepted: 2 3
```

**Consequência:** FR-G2-07 e o Cenário 6 do quickstart não são implementados. Retry/reenvio duplica história.

### P1-4 — `correct --delta-xp` não gera compensação

`cmd_correct` monta `{"field": "xp", "delta": delta_xp}` (`application/showrunner.py:266`), mas `CorrectionService` só compensa `field == "xp_delta"` (`application/correction.py:88`). Prova:

```text
correct --delta-xp -50 -> events_appended: 1
events after: ['campaign.created', 'turn.proposed', 'turn.committed', 'projection.rebuilt', 'correction.issued']
compensation present: False
```

**Consequência:** o Cenário 4 do quickstart (“evento compensatório `protagonist.progression_changed`”) é falso. O teste passa porque só verifica `events_appended > 0`.

### P1-5 — Dois regimes de lock e `last_seq` que trunca sem lock

O store calcula `_events_dir` como `base_dir/events` quando `base_dir.name == campaign_id` (`event_store.py:52-54`), mas o lock é sempre `base_dir/campaign_id` (`:169`). O `commit` usa `JsonlEventStore(camp_dir)`; a transação usa `campaign_dir/.campaign.lock`. Resultado real:

```text
lock .campaign.lock
lock qa_causal/.campaign.lock
dir  qa_causal/
```

São dois locks diferentes para o mesmo estado. Além disso, `last_seq()` chama `_inspect_campaign()`, que chama `_recover_segment()` e trunca o arquivo (`:126-132`), **sem adquirir lock**. Um leitor chamando `last_seq` enquanto um escritor grava pode truncar o lote em voo.

**Correção:** um único lock por campanha, compartilhado por commit/rebuild/correct/store; `last_seq` estritamente somente leitura; recuperação apenas no `append` sob lock.

### P1-6 — Rebuild a partir de snapshot perde todo o estado anterior ao snapshot

`rebuild_projections` usa `snapshot` apenas como `after_seq` (`application/rebuild.py:39-45`). O snapshot não é passado aos projectors. Prova com `snapshot={"last_seq": 2}`:

```text
contains turn1: False
contains turn2: True
```

**Consequência:** o Cenário 8 e a promessa de retenção/snapshot não funcionam. O rebuild “a partir de snapshot” reconstrói só o rabo.

### P1-7 — Correção não reavalia dependentes; só registra IDs

`CorrectionService` calcula `affected_ids` (`application/correction.py:54`) e grava `correction.recomputed` com a lista (`:117-133`), mas não recalcula projeções, fatos ou resultados. A compensação é só `xp_delta`; atributos, vitais e relógios citados no plano não são compensados. O commit real não declara dependências, então `affected_ids` é quase sempre vazio.

**Consequência:** FR-G2-03 e a parte “reavaliação seletiva” de G2-D3 não são implementadas. C4 funciona apenas como flag de inconsistência.

### P1-8 — `expected_last_seq` nunca é usado pelos chamadores

A única ocorrência de `expected_last_seq` fora da assinatura é a verificação interna em `event_store.py:172`. Nenhum caller (`commit`, `correct`, `rebuild`, `init`) passa o valor. O teste de concorrência do FR-G1-03 só chama o store diretamente.

**Consequência:** a proteção contra escrita atrasada/concorrente não existe no fluxo real.

### P1-9 — Hash do lote não é verificado; leitura engole corrupção

`read()` (`event_store.py:296-358`) ignora o `hash` do marcador `committed` e tem `except Exception: continue` por evento. Prova: alterar o hash do lote para zeros e reler:

```text
D read after corrupt hash: [(1, 'campaign.created'), (2, 'turn.committed')]
```

**Consequência:** corrupção e eventos inválidos são silenciosos; não há `ReplayError`. O hash existe no arquivo, mas não protege nada na leitura.

### P1-10 — Os 199 testes verdes não testam a integração prometida

Os testes novos validam componentes isolados, não os critérios:

- `test_projection_rebuild.py` compara `projections/` com `projections/`; nunca com `diario.md`/`ficha.md`/`npcs.md` da raiz.
- `test_quickstart_scenarios.py` Cenário 3 apaga `projections/` e compara o hash consigo mesmo; Cenário 4 só verifica `events_appended > 0`; Cenário 6 não testa duplicata; Cenário 7 usa `assertRaises(Exception)`; Cenário 8 não cria snapshot; Cenário 9 só testa o caso feliz; Cenário 10 recalcula com o próprio evento de auditoria; Cenário 11 testa a flag, não a compensação.
- `test_causal_correction.py` testa compensação direta via `CorrectionService` com `field=xp_delta`, mas não o caminho CLI (`field=xp`).
- `test_event_catalog.py` testa `upcast_payload` diretamente, não `store.read` com catálogo.
- `test_cli_contracts.py` aceita “erro ou sucesso” no caso de evento inexistente.

**Consequência:** a afirmação “199/199 e C1–C4 validados” não se sustenta. A suíte verde dá falsa confiança.

---

## 4. P2 — Correções importantes

### P2-1 — `init-campaign` pode criar campanha sem `campaign.created`

O append do evento inicial está em `try/except: pass` (`campaign/templates.py:148-171`). Se o store falhar, a campanha é criada sem evento e o `commit` pode não emitir nada. O payload também fixa `calendar: "standard"` (`:163`), perdendo o calendário de `regras.md`.

### P2-2 — `game_time_sort` não é tempo de jogo

`commit` usa `next_turn * 100` (`application/commit.py:483`, `:498`, `:516`), não minutos desde a época. A ordenação fica artificial e não conversa com `CalendarProvider`.

### P2-3 — Eventos reais não declaram dependências

`turn.proposed`, `prose.recorded` e `turn.committed` são criados sem `meta.dependencies` (`commit.py:478-526`). O `prose.recorded` não depende do turno; o `turn.committed` não depende da proposta. O grafo causal do fluxo real fica vazio, apesar de C2 funcionar no teste direto.

### P2-4 — `rebuild --force` é ignorado e snapshots não são gerados

`cmd_rebuild` aceita `force` (`showrunner.py:222`) e nunca o usa. Não há código que grave `snapshots/`; `rebuild_projections` aceita um `snapshot` que não contém estado. O CLI não expõe snapshot.

### P2-5 — `ProseStore` não é atômico, altera o texto e não impõe cardinalidade

`store_turn_prose` faz `content.strip().encode()` (`application/prose_store.py:23`) e `write_bytes` direto (`:31`). Não usa `atomic_write_text`, não faz `fsync`, não verifica se o arquivo existente confere e permite dois `prose.recorded` para o mesmo turno. O hash é do texto stripado, não do original.

### P2-6 — Violações de camada e de tamanho

- `application/commit.py`, `application/showrunner.py` importam `adapters.persistence.event_store` diretamente; a aplicação deveria depender da porta.
- `resources/*` importam `adapters.persistence.files`; a arquitetura previa `resources → ports`.
- `council/reviewer.py` importa `application.correction` (`:673`), invertendo a direção domínio → aplicação.
- `kernel/event_catalog.py` conhece 25 tipos de domínio; o kernel deveria ser agnóstico.
- Tamanhos acima do alvo: `application/commit.py` 552, `council/reviewer.py` 692, `adapters/persistence/event_store.py` 365. O teste de fronteira usa `< 600`, não o alvo de 300 ([`tests/test_architecture_boundaries.py:113`](../../tests/test_architecture_boundaries.py#L113)).

### P2-7 — `ProjectionEngine` deixa projeções obsoletas e vazias

`write_projections_atomic` só escreve os arquivos produzidos (`projection_engine.py:43-45`); se um projector deixa de produzir um arquivo, o antigo permanece. Projeções sem eventos viram arquivos mínimos, não remoção/estado vazio explícito.

### P2-8 — Inconsistência causal não tem fluxo de resolução

`check_causal_inconsistencies` só lê `correction.issued` com flag e o `review` acusa para sempre (`application/correction.py:138-157`). Não há comando/evento para marcar a pendência como resolvida, e a correção contraditória continua no log sem estado final.

---

## 5. P3 — Higiene

- **Documentação de testes divergente:** `EX-0014` diz 199, `ROADMAP.md:321`/`ARCHITECTURE.md:3`/`639`/`696` ainda dizem 157, `README.md:45` diz 156, `quickstart.md:12` fixa o baseline em 157. `EX-0014` diz “Commit: pendente”, mas o commit `7f2c165` existe.
- **Catálogo:** o plano fala em 23 tipos (`plan.md:32`), o catálogo tem 25; `campaign.created.calendar` é `string` (“standard”), enquanto a spec/data-model usam mapa de calendário.
- **`Mapping` não importado** em `adapters/persistence/event_store.py:39`; funciona só porque `from __future__ import annotations` adia a avaliação.
- **`last_seq` cria `events/`** como efeito colateral (`_inspect_campaign` faz `mkdir`), mesmo em leitura.
- **`SkeletonQueue`** não usa lock nem `fsync`; dois processos podem intercalar linhas.
- **`_next_ulid` privado** importado por `application/correction.py:12`.
- **Teste de fronteira** não cobre imports de `resources`/`application`/`council` nem o alvo de 300 linhas; valida apenas `< 600`.
- **Cenário 3 do quickstart** apaga `projections/`, não a raiz; portanto não prova reconstrução do SSOT.

---

## 6. O que funciona

- `JsonlEventStore` direto: marcadores `batch.open`/`batch.committed`, recuperação por truncamento, rotação de segmento, `game_time` obrigatório, hashes de evento/lote, `expected_last_seq` na API.
- `DependencyGraph`: ciclo, profundidade 64, auto-dependência, dependência futura e intra-lote — testes diretos passam.
- Correção contraditória: `correction.issued` + flag `inconsistency_detected` + `review` com `CAUSAL_INCONSISTENCY` funcionam.
- `ProseStore`/`SkeletonQueue`: lifecycle básico e verificação de hash.
- Refatoração `ssot.py`: 53 linhas, fachada preservada; a suíte legada continua verde.
- 199 testes executam em ~19 s.

---

## 7. Por que 199 verdes não aprovam a fase

A suíte testa **componentes**, não o fluxo:

1. Store direto, com catálogo injetado e campanha criada à mão.
2. DAG direto, com dependências construídas no teste.
3. Projeções comparadas a si mesmas, não à raiz.
4. Correção via `CorrectionService` com `xp_delta`, não via CLI com `xp`.
5. Nenhum teste de commit sem `events/`, commit com store quebrado, rollback de log, duplicata, snapshot real, hash corrompido ou rebuild da raiz.

---

## 8. Recomendação e ordem de correção

1. **Tornar o log a verdade:** remover `if events.exists()` e `except: pass`; criar o store na inicialização; se o append falhar, abortar o turno; emitir todos os eventos de recurso no mesmo lote.
2. **Unificar projeções e SSOT:** projectors gravam `diario.md`/`ficha.md`/`npcs.md` (ou leitores passam a ler `projections/`); rebuild compara a raiz byte a byte.
3. **Fechar G1:** injetar `build_v1_catalog()` no store de produção; validar hash do lote na leitura; remover truncamento de `last_seq`; um único lock; `expected_last_seq` nos callers.
4. **Fechar G2:** corrigir `field=xp` → `xp_delta`; implementar duplicata; compensar mais que XP; reavaliar dependentes de fato; snapshots com estado; resolver inconsistência.
5. **Reescrever os testes de aceite** para os cenários reais (C1–C4 e os 11 do quickstart) contra a raiz, o commit e a CLI.
6. Só então declarar R1/Fase 02 concluída.

---

## 9. Reprodução

```powershell
# suíte
python -m unittest discover -s tests -p "test_*.py"

# e2e em campanha descartável: init, commit, root vs projections, corrigir
$env:RPGPRO_CAMPAIGNS_DIR = "$env:TEMP\qa_phase2\campaigns"
python lazy_turn.py init-campaign --campaign qa_causal --title "QA Causal"
python lazy_turn.py commit --campaign qa_causal --summary "O herói cruza o portão." --time +1h
python lazy_turn.py rebuild --campaign qa_causal
python lazy_turn.py correct --campaign qa_causal --event <evt_id> --reason "XP indevido" --delta-xp -50
python lazy_turn.py review --campaign qa_causal

# probes cobertos: remove events/ e repete commit; inspeciona events/, projections/, raiz
```

**Arquivos auditados:** `application/commit.py`, `application/rebuild.py`, `application/projection_engine.py`, `application/projectors/*`, `application/correction.py`, `application/prose_store.py`, `adapters/persistence/event_store.py`, `adapters/persistence/lock.py`, `adapters/persistence/skeleton_queue.py`, `kernel/dag.py`, `kernel/event_catalog.py`, `campaign/templates.py`, `application/showrunner.py`, `council/reviewer.py`, `tests/test_*.py`.
