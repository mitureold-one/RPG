# Research & Architectural Decisions: 011 — Fechamento dos 5 Achados P2 do QA da Fase 02/R1

**Feature**: `close-phase02-qa-p2`  
**Created**: 2026-10-26  
**Scope**: Resolução técnica das 5 pendências P2 apontadas em [`specs/010-phase-02-causal-history/qa-review.md`](../010-phase-02-causal-history/qa-review.md) e [`EXECUCAO.md`](../../EXECUCAO.md) (`EX-0017` / `EX-0018`).

---

## R-01: Descoberta e Reconstrução Resiliente sem `diario.md` (P2-1)

- **Decision**: Adicionar parâmetro `allow_missing_projections: bool = False` em `campaign.locator.find_campaign(campaign_id, *, allow_missing_projections=False)`. Quando `allow_missing_projections=True` e `diario.md` não existir na raiz da campanha:
  1. Verificar se existe `projections/diario.md` ou segmentos de eventos em `events/*.jsonl`.
  2. Se nenhum dos dois existir, continuar levantando `FileNotFoundError` (campanha genuinamente corrompida).
  3. Se `events/` (ou `projections/diario.md`) existir, extrair `schema_version` de `projections/diario.md` ou do baseline em `campaign.created` (default `CURRENT_SCHEMA_VERSION = 1`), carregar o manifesto de `regras.md` e retornar o dicionário de metadados da campanha normalmente.
  4. Em `application/transaction._serialized_campaign_mutation`, usar `find_campaign(campaign_id, allow_missing_projections=(func.__name__ == "cmd_rebuild"))`, e em `application/showrunner.cmd_rebuild`, chamar `find_campaign(campaign_id, allow_missing_projections=True)`.
- **Rationale**: Preserva a validação estrita (`fail-fast` com `FileNotFoundError`) para todos os comandos de leitura/mutação normais quando `diario.md` sumiu, ao mesmo tempo em que destrava `lazy_turn.py rebuild` para cumprir sua função de recuperar `diario.md`, `ficha.md` e `npcs.md` a partir de `events/`.
- **Alternatives considered**:
  - *Tornar `find_campaign` sempre permissivo para todos os comandos*: Rejeitado porque testes de contrato existentes (`test_cli_contracts.py` / `test_campaign_locator.py`) exigem que `find_campaign(id)` sem `diario.md` e comandos comuns como `prepare`/`review` acusem corrupção até que um `rebuild` explícito seja executado.

---

## R-02: Remoção de Snapshots `*_after` em `meta` e Derivação Pura nos Projetores (P2-2)

- **Decision**:
  1. Remover `diario_after`, `ficha_after` e `npcs_after` de `application/commit_events.py` (`turn.committed.meta`) e de `application/transaction.py` (`record_command_mutation`).
  2. Remover o atalho `if "*_after" in meta: text = meta["*_after"]; continue` de `JournalProjector`, `CharacterSheetProjector` e `NpcProjector`.
  3. Fazer os 3 projetores aplicarem as transformações de texto usando **as mesmas funções puras/determinísticas de domínio** (`resources/clocks.py`, `resources/ledger.py`, `resources/sheet.py`, `resources/progression.py`, `council/quests.py`, `council/factions.py`, `council/narrator.py`) sobre um arquivo temporário ou buffer em memória a partir do baseline de `campaign.created`, alimentado exclusivamente pelos campos estruturados de `ev.payload` de cada evento (`clock.*`, `quest.*`, `arc.updated`, `scene.*`, `protagonist.*`, `faction.reputation_changed`, `npc.updated`, `turn.committed`, `correction.*`).
  4. Enriquecer os payloads dos eventos onde faltavam metadados para reprodução byte-idêntica (ex.: `turn.committed` carrega `vitals_line`, `state_shift`, `alerts`; `quest.*` carrega `contractor`, `clock`, `reward`, `phase`, `evidence`, `turn`; `faction.reputation_changed` carrega `turn`, `quest_id`, `delta_favors`, `delta_debts`; `npc.updated` distingue `mode="upsert"` vs `mode="turn_update"`).
  5. Para o caso de edição manual direta nos arquivos Markdown da raiz fora da CLI (`out_of_band` detectado em `ensure_campaign_event_log`), emitir `command.executed` (`command="sync"`) trazendo as diferenças no `payload` (e não como blob oculto em `meta`), garantindo que o projetor trate explicitamente sincronizações externas.
- **Rationale**: Elimina a duplicação de regexes simplificados nos projetores e garante que o estado projetado na raiz e em `projections/` seja 100% derivado dos payloads dos eventos no log. Qualquer evento compensatório adicionado ao final do log altera real e deterministicamente o Markdown reconstruído.
- **Alternatives considered**:
  - *Reescrever do zero todas as regexes de formatação Markdown dentro de cada Projector*: Rejeitado pela regra Ponytail #2 ("Does it already exist in this codebase? Reuse the helper, util, or pattern that's already here, don't re-write it"), pois duplicar a formatação de `quests.py`, `factions.py` e `narrator.py` geraria divergências sutis de espaçamento e quebras de linha.

---

## R-03: Compensação Causal de Relógios, Missões e Arcos + Reprojeção Automática (P2-3)

- **Decision**:
  1. Estender `CorrectionService.issue_correction` (`application/correction.py`) para aceitar e gerar eventos compensatórios nos 3 novos domínios além de XP, ficha/vitais e reputação:
     - **Relógios (`field == "clock"`)**: calcula o estado atual do relógio no log, aplica `delta` (com clamp $\ge 0$) e/ou novo `status` (`ACTIVE`, `BREACHED`, `RESOLVED`) e emite `clock.advanced` (ou `clock.resolved` quando `status == "RESOLVED"`) com `meta.correction_id`.
     - **Missões (`field == "quest"`)**: emite `quest.status_changed` para o `quest_id` alvo com o novo `status` (`ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`) e justificativa vinculada a `correction_id`.
     - **Arcos (`field == "arc"`)**: emite `arc.updated` restaurando ou retificando `stage`, `title` e/ou `question` com `meta.correction_id`.
  2. Estender a CLI `lazy_turn.py correct` (`interfaces/cli/parser.py`, `interfaces/cli/main.py` e `application/showrunner.py:cmd_correct`) com as opções:
     - `--clock "<nome>:<delta_ou_status>"` (ex.: `--clock "Invasão:-1"` ou `--clock "Invasão:ACTIVE"`)
     - `--quest "<QID>:<STATUS>"` (ex.: `--quest "Q1:ACTIVE"`)
     - `--arc-stage "<Fase>"` / `--arc-title "<Título>"`
  3. Permitir que `CorrectionService` receba `campaign_dir: Path | None = None` (ou que `issue_correction` acione `rebuild_projections` quando `campaign_dir` estiver disponível / configurável no store), garantindo que chamadas diretas a `CorrectionService` ou via `cmd_correct` deixem as projeções na raiz e em `projections/` imediatamente atualizadas.
- **Rationale**: Fecha integralmente o achado P2-3 ("Compensação só cobre XP/ficha/reputação; relógios, missões e arcos não têm compensação; reavaliação é log"), tornando todos os recursos de campanha retificáveis via CLI e serviço com efeito imediato no SSOT.
- **Alternatives considered**:
  - *Criar novos tipos de evento no catálogo apenas para compensação*: Rejeitado porque a spec G2-D1/G2-D3 define que compensações devem usar os próprios eventos canônicos de domínio (`clock.*`, `quest.*`, `arc.updated`) marcados com `meta.correction_id`.

---

## R-04: Decomposição de Módulos Acima de 300 Linhas e Pureza de Camadas (P2-4)

- **Decision**:
  1. Decompor os três arquivos citados nominalmente em P2-4 para ficarem **abaixo de 300 linhas**:
     - `application/commit.py` (atualmente 516 linhas) $\to$ extrair a aplicação de estágio/recursos para `application/commit_stage.py` (< 280 linhas), deixando `application/commit.py` (< 260 linhas) responsável pela orquestração do caso de uso.
     - `adapters/persistence/event_store.py` (atualmente 322 linhas) $\to$ mover a serialização/validação de rascunhos e construção de marcadores de lote para `adapters/persistence/segment_io.py` (ou auxiliar), reduzindo `event_store.py` para < 280 linhas e mantendo `segment_io.py` < 300 linhas.
     - `council/reviewer.py` (atualmente 582 linhas) $\to$ extrair os linters literários (`check_prose_lints`, `detect_temporal_paradoxes`, regexes de script/4ª parede/emoji) e checagens de quests/XP para `council/prose_linter.py` (< 250 linhas), mantendo `council/reviewer.py` < 300 linhas e reexportando `check_prose_lints` e `detect_temporal_paradoxes` para compatibilidade.
  2. Revisar imports de camadas e reforçar `tests/test_architecture_boundaries.py`:
     - Garantir que `application/commit.py`, `adapters/persistence/event_store.py` e `council/reviewer.py` tenham asserção explícita `< 300` linhas em `test_architecture_boundaries.py`.
     - Garantir que `council/` não importe `application/` e que `application/` não importe `adapters/` diretamente.
- **Rationale**: Atende cirurgicamente ao apontamento P2-4 do QA (`application/commit.py 516, event_store.py 316, reviewer.py 692; imports de camada ainda a revisar`) com corte limpo de responsabilidades e proteção por teste AST.
- **Alternatives considered**:
  - *Apenas compactar linhas nos arquivos existentes*: Rejeitado porque `commit.py` (516) e `reviewer.py` (582) têm quase o dobro do alvo de 300 linhas e possuem subdomínios claramente separáveis (`commit_stage` e `prose_linter`).
