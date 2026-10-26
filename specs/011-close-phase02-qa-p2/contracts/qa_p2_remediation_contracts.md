# Interface & Projection Contracts: 011 — Fechamento dos 5 Achados P2 do QA da Fase 02/R1

**Feature**: `close-phase02-qa-p2`  
**Created**: 2026-10-26

---

## 1. Contrato de Localização e Rebuild sem `diario.md` (P2-1)

### 1.1 `campaign.locator.find_campaign`
```python
def find_campaign(campaign_id: str, *, allow_missing_projections: bool = False) -> dict | None:
```
- **Invariante Padrão (`allow_missing_projections=False`)**:
  - Se `camp_dir` existir mas `camp_dir / "diario.md"` não existir $\to$ levanta `FileNotFoundError("Campanha '<id>' corrompida: 'diario.md' não encontrado...")`.
- **Modo Recuperação (`allow_missing_projections=True`)**:
  - Se `camp_dir / "diario.md"` não existir, verifica se `(camp_dir / "events")` possui pelo menos um segmento `.jsonl` não vazio ou se `(camp_dir / "projections" / "diario.md")` existe.
  - Caso positivo, resolve `schema_version` (default `1`) e retorna o dicionário da campanha permitindo que `cmd_rebuild` reconstrua `diario.md`, `ficha.md` e `npcs.md` na raiz e em `projections/`.
  - Caso negativo (sem `diario.md` e sem `events/`), levanta `FileNotFoundError`.

---

## 2. Contrato de Projeção Pura sem Snapshots em `meta` (P2-2)

- **Proibição de Blobs em `meta`**:
  - Nenhum evento emitido por `cmd_commit`, `cmd_clock`, `cmd_plan`, `cmd_arc`, `cmd_quest`, `cmd_progress`, `cmd_faction` ou `cmd_upsert_npc` pode conter as chaves `diario_after`, `ficha_after` ou `npcs_after` em `event.meta`.
- **Invariante de Equivalência Raiz $\equiv$ Projeção**:
  - Após qualquer comando mutante ou `lazy_turn.py rebuild --campaign <id> --force`, para cada arquivo $f \in \{\text{diario.md}, \text{ficha.md}, \text{npcs.md}\}$:
    $$\text{SHA256}(\text{camp\_dir}/f) = \text{SHA256}(\text{camp\_dir}/\text{projections}/f)$$

---

## 3. Contrato CLI e Serviço de Correção Causal Estendido (P2-3)

### 3.1 CLI `lazy_turn.py correct`
```text
python lazy_turn.py correct --campaign <id> --event <evt_id_ou_cor_id> --reason "<motivo>"
    [--delta-xp <int>]
    [--vital "<recurso>:<novo_valor_ou_delta>"]
    [--rep "<faccao>:<delta>"]
    [--clock "<nome_relogio>:<delta_ou_status>"]
    [--quest "<QID>:<STATUS>"]
    [--arc-stage "<Fase>"]
    [--arc-title "<Título>"]
    [--contradiction]
    [--resolve]
    [--json]
```

### 3.2 Semântica dos Argumentos de Compensação
- `--clock "Invasão:-1"`: emite `clock.advanced` reduzindo 1 segmento (mínimo 0) e recalculando status (`ACTIVE` se `current < max`).
- `--clock "Invasão:ACTIVE"` ou `--clock "Invasão:RESOLVED"`: emite `clock.advanced`/`clock.resolved` ajustando o status do relógio.
- `--quest "Q1:ACTIVE"` (ou `BLOCKED`, `FAILED`, `ABANDONED`, `COMPLETED`): emite `quest.status_changed` atualizando o status da missão `Q1` em `diario.md`.
- `--arc-stage "Preparação"` / `--arc-title "Novo Arco"`: emite `arc.updated` atualizando a seção `### Arco Narrativo Ativo` em `diario.md`.
- **Pós-condição Obrigatória**: Toda execução bem-sucedida de `issue_correction` / `cmd_correct` atualiza imediatamente `diario.md`, `ficha.md` e `npcs.md` na raiz e em `projections/`.

---

## 4. Contrato de Limites de Tamanho e Fronteiras de Camada (P2-4)

Fiscalizado por `tests/test_architecture_boundaries.py`:
- `lazy_turn.py` < 200 linhas.
- `council/helpers.py` < 100 linhas.
- `council/ssot.py` < 100 linhas.
- `application/commit.py` < 300 linhas.
- `adapters/persistence/event_store.py` < 300 linhas.
- `council/reviewer.py` < 300 linhas.
- `contracts/` e `kernel/`: zero I/O e zero imports de camadas superiores.
- `adapters/persistence/`: zero imports de `council`, `rulesets`, `interfaces`, `application`.
- `application/`: zero imports de `interfaces`, `lazy_turn` e zero imports diretos de `adapters.persistence.event_store` (usa a porta `contracts.ports.create_event_store`).
- `council/`: zero imports de `application` ou `interfaces`.
