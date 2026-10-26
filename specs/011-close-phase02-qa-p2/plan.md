# Implementation Plan: 011 — Fechamento dos 5 Achados P2 do QA da Fase 02/R1

**Feature**: `close-phase02-qa-p2`  
**Status**: Completed — implementado e aprovado em 26/10/2026 (211 testes; `EX-0021`).
**Created**: 2026-10-26  
**Target**: Fechamento definitivo da Fase 02 / R1 e aprovação sem ressalvas do QA  
**Base Analisada**:
- [`specs/011-close-phase02-qa-p2/spec.md`](spec.md)
- [`specs/011-close-phase02-qa-p2/research.md`](research.md)
- [`specs/011-close-phase02-qa-p2/data-model.md`](data-model.md)
- [`specs/011-close-phase02-qa-p2/contracts/qa_p2_remediation_contracts.md`](contracts/qa_p2_remediation_contracts.md)
- [`specs/011-close-phase02-qa-p2/quickstart.md`](quickstart.md)
- [`specs/010-phase-02-causal-history/qa-review.md`](../010-phase-02-causal-history/qa-review.md)
- [`EXECUCAO.md`](../../EXECUCAO.md) (`EX-0017` e `EX-0018`)

---

## 1. Technical Context & Overview

A auditoria de QA da Fase 02/R1 (`EX-0017` e `EX-0018`) confirmou o fechamento de todos os itens P0 e P1 (206 testes verdes), restando **5 achados P2** para o congelamento definitivo da etapa R1:

- **P2-1 (Perda de `diario.md`)**: `find_campaign` exige `diario.md` na raiz mesmo durante `rebuild`, impedindo recuperar a campanha quando `diario.md` é deletado mas `events/` está intacto.
- **P2-2 (Snapshots `*_after` em `meta`)**: `turn.committed` e comandos salvam `diario_after`, `ficha_after` e `npcs_after` no `meta`, fazendo os projetores copiarem blobs de texto em vez de derivarem o estado a partir dos eventos.
- **P2-3 (Compensação limitada)**: `CorrectionService` e `cmd_correct` compensam apenas XP, ficha e reputação, faltando suporte para relógios (`clock`), missões (`quest`) e arcos (`arc`), além de reprojeção automática no próprio serviço quando o diretório da campanha é fornecido.
- **P2-4 (Camadas e tamanho de arquivos)**: `application/commit.py` (516 linhas), `adapters/persistence/event_store.py` (322 linhas) e `council/reviewer.py` (582 linhas) estão acima da meta de 300 linhas citada pelo QA.
- **P2-5 (Documentação e testes)**: faltam testes automatizados dedicados para perda de `diario.md`, ausência de blobs `*_after` em `meta`, compensação de relógio/missão/arco e atualização final de `qa-review.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `README.md` e `EXECUCAO.md`.

### Stack & Restrições Técnicas
- **Linguagem / Runtime**: Python 3.11+, 100% Standard Library (`json`, `re`, `pathlib`, `hashlib`, `tempfile`, `shutil`, `unittest`, `ast`). Zero dependências externas.
- **Arquitetura**: Monólito modular com Event Store JSONL append-only como fonte da verdade e Markdown (`diario.md`, `ficha.md`, `npcs.md`) como projeções determinísticas.
- ** unknowns / NEEDS CLARIFICATION**: Nenhum (todos resolvidos em [`research.md`](research.md)).

---

## 2. Constitution & Sovereignty Check

| Diretriz / Gate | Status | Verificação no Design |
|---|---|---|
| **D1 — Event Log é a verdade; Markdown é projeção** | PASS | Ao eliminar `*_after` de `meta` (P2-2) e permitir `rebuild` sem `diario.md` (P2-1), os arquivos Markdown passam a ser 100% derivados dos payloads dos eventos. |
| **G2-D1 / G2-D3 — Correção append-only e compensação** | PASS | `CorrectionService` e CLI `correct` passam a cobrir XP, vitais/ficha, reputação, relógios, missões e arcos com reprojeção imediata (P2-3). |
| **Ponytail Rung #2 — Reutilizar helpers existentes** | PASS | Projetores reutilizam as funções determinísticas de formatação já existentes no codebase em vez de duplicar regexes. |
| **Limites de Tamanho (< 300 LOC nos alvos de R1) e Fronteiras AST** | PASS | `commit.py`, `event_store.py` e `reviewer.py` serão decompostos para < 300 linhas cada e fiscalizados por `test_architecture_boundaries.py` (P2-4). |
| **Zero Emojis & Registro Append-Only em `EXECUCAO.md`** | PASS | Nenhum emoji introduzido; nova entrada será adicionada ao final de `EXECUCAO.md` com evidências verificáveis (P2-5). |

---

## 3. Work Breakdown Structure (Fases de Implementação)

### Fase 1: Descoberta Resiliente e Rebuild sem `diario.md` (P2-1)
1. **`campaign/locator.py`**:
   - Adicionar `allow_missing_projections: bool = False` em `find_campaign`.
   - Quando `diario.md` não existir na raiz:
     - Se `not allow_missing_projections`, manter o `raise FileNotFoundError(...)` atual.
     - Se `allow_missing_projections=True`, verificar se `(camp_dir / "events")` contém segmentos `.jsonl` ou se `(camp_dir / "projections" / "diario.md")` existe; extrair `schema_version` de `projections/diario.md` ou assumir `CURRENT_SCHEMA_VERSION` quando `events/` existir; se nenhum existir, levantar `FileNotFoundError`.
2. **`application/transaction.py` e `application/showrunner.py`**:
   - Em `_serialized_campaign_mutation`, chamar `find_campaign(campaign_id, allow_missing_projections=(func.__name__ == "cmd_rebuild"))`.
   - Em `cmd_rebuild`, chamar `find_campaign(campaign_id, allow_missing_projections=True)` e reconstruir `diario.md`, `ficha.md` e `npcs.md` na raiz e em `projections/`.

### Fase 2: Projetores Derivados de Eventos e Remoção de Snapshots `*_after` (P2-2)
1. **Enriquecimento de Payloads Canônicos (`contracts/catalog.py`, `application/commit_events.py`, `application/showrunner.py`, `application/progression.py`, `application/factions.py`, `interfaces/cli/main.py`)**:
   - Remover completamente `diario_after`, `ficha_after` e `npcs_after` de `application/commit_events.py` e `application/transaction.py`.
   - Garantir que cada evento emitido por `commit` e pelos subcomandos CLI inclua no seu `payload` todos os campos necessários para reconstrução exata:
     - `turn.committed`: `turn`, `summary`, `scene_type`, `location`, `present`, `vitals`, `vitals_line`, `costs`, `state_shift`, `alerts`, `restored_vitals`.
     - `quest.created`: `id`, `title`, `type`, `objectives`, `contractor`, `clock`, `reward`, `phase`.
     - `quest.objective_completed`, `quest.completed`, `quest.failed`, `quest.status_changed`: incluir `turn`, `evidence`, `reason`, `objective` (quando `add_objective`).
     - `faction.reputation_changed`: incluir `delta_favors`, `delta_debts`, `turn`, `quest_id`, `reason`.
     - `protagonist.progression_changed`: incluir `turn`, `base_step`, `skip_ledger`, `source`.
     - `protagonist.sheet_changed`: incluir `kind`, `target`, `new_value`, `delta`, `points_remaining`, `training`, `source`.
     - `npc.updated`: incluir `mode` (`"upsert"` ou `"turn_update"`), `raw_update` e todos os campos passados a `upsert_npc_to_md` ou `apply_npc_updates_to_md`.
2. **Refatoração dos Projetores (`application/projectors/journal.py`, `sheet.py`, `npc.py`)**:
   - Remover os blocos `if "*_after" in meta:` dos três projetores.
   - Fazer `JournalProjector`, `CharacterSheetProjector` e `NpcProjector` aplicarem cada evento do stream deterministicamente reutilizando as funções de domínio (`upsert_clock_in_diario`, `upsert_quest_in_diario`, `append_xp_ledger_entry`, `append_faction_ledger_entry`, `upsert_planned_scene_in_diario`, `update_arc_in_diario`, `update_progression_in_ficha`, `spend_attribute_point_in_ficha`, `spend_ability_point_in_ficha`, `upsert_ficha_feature`, `update_reputation_in_ficha`, `apply_npc_updates_to_md`, `upsert_npc_to_md`).
   - Tratar `command.executed` com `command == "sync"` via `payload.files` apenas quando houver edição manual externa do usuário fora da CLI.

### Fase 3: Compensação Causal de Relógios, Missões e Arcos + Reprojeção Automática (P2-3)
1. **`application/correction.py` (`CorrectionService`)**:
   - Aceitar `campaign_dir: Path | str | None = None` no construtor e/ou inferir do `store` quando disponível; se presente, chamar `rebuild_projections(self.store, campaign_id, campaign_dir, emit_audit_event=False)` logo após `self.store.append(...)`.
   - Adicionar suporte aos novos tipos de `changes`:
     - `field == "clock"`: calcula o progresso atual do relógio `name` a partir dos eventos lidos, aplica `delta` (clamp $\ge 0$) e/ou `status` (`ACTIVE`, `BREACHED`, `RESOLVED`) e emite `clock.advanced` (e `clock.resolved` se `RESOLVED`) com `meta={"dependencies": list(resolved_deps), "correction_id": cor_id}`.
     - `field == "quest"`: emite `quest.status_changed` para `quest_id`/`id` com `status` e `reason=f"compensação_{cor_id}: {reason}"`.
     - `field == "arc"`: emite `arc.updated` com `title`, `stage` e/ou `question` informados em `ch`.
2. **CLI e Showrunner (`interfaces/cli/parser.py`, `interfaces/cli/main.py`, `application/showrunner.py`)**:
   - Adicionar `--vital`, `--rep`, `--clock`, `--quest`, `--arc-stage` e `--arc-title` ao subcomando `correct` e repassar na lista `changes` de `cmd_correct`.

### Fase 4: Decomposição de Módulos (< 300 LOC) e Fronteiras de Camadas (P2-4)
1. **Decompor `application/commit.py` (516 linhas $\to$ < 260 linhas)**:
   - Extrair a preparação e execução em `.staging/` (vitais, features, NPCs, relógios, quests, facções, fila de trama e entrada de diário) para `application/commit_stage.py` (< 280 linhas).
2. **Decompor `adapters/persistence/event_store.py` (322 linhas $\to$ < 260 linhas)**:
   - Mover helpers de validação de rascunho e serialização de lote para `adapters/persistence/segment_io.py` (ou `adapters/persistence/batch_io.py`), mantendo todos os módulos de `adapters/persistence/` abaixo de 300 linhas.
3. **Decompor `council/reviewer.py` (582 linhas $\to$ < 280 linhas)**:
   - Extrair linters literários e temporais (`check_prose_lints`, `detect_temporal_paradoxes`, `parse_pt_date`, constantes regex) para `council/prose_linter.py` (< 200 linhas) e sub-auditorias de missões/XP/relógios para `council/reviewer_checks.py` (ou `council/reviewer_domain.py`, < 280 linhas), reexportando os símbolos públicos em `council/reviewer.py`.
4. **Fortalecer `tests/test_architecture_boundaries.py`**:
   - Adicionar verificação explícita de `< 300` linhas para `application/commit.py`, `adapters/persistence/event_store.py`, `council/reviewer.py` (e novos módulos extraídos) e checagem de que `council/` não importa `application/`.

### Fase 5: Testes Automatizados de Aceite e Sincronização Documental (P2-5)
1. **Novos Testes Automatizados**:
   - `tests/test_projection_rebuild.py`: teste de remoção de `diario.md` (e `ficha.md`/`npcs.md`) da raiz seguido de `cmd_rebuild` e `cmd_review` (P2-1), e teste verificando que nenhum evento emitido por `commit` ou comandos possui `diario_after`, `ficha_after` ou `npcs_after` em `meta` (P2-2).
   - `tests/test_causal_correction.py`: testes de compensação de `clock`, `quest` e `arc` via `CorrectionService` e via `cmd_correct`, verificando atualização imediata de `diario.md` (P2-3).
   - `tests/test_architecture_boundaries.py`: validação dos limites `< 300` linhas e fronteiras de importação (P2-4).
2. **Sincronização Documental**:
   - Atualizar [`specs/010-phase-02-causal-history/qa-review.md`](../010-phase-02-causal-history/qa-review.md) marcando P2-1 a P2-5 como **Corrigido** com evidências.
   - Sincronizar contagem de testes e status em `ROADMAP.md`, `ARCHITECTURE.md`, `README.md` e registrar nova entrada em `EXECUCAO.md`.
