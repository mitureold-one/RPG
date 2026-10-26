# Data Model: 011 — Fechamento dos 5 Achados P2 do QA da Fase 02/R1

**Feature**: `close-phase02-qa-p2`  
**Created**: 2026-10-26  
**Scope**: Estruturas de payload de eventos (sem snapshots `*_after` em `meta`), contratos de compensação causal e modelo de descoberta resiliente de campanha.

---

## 1. Descoberta Resiliente de Campanha (`CampaignDescriptor` — P2-1)

Quando `find_campaign(campaign_id, allow_missing_projections=True)` é invocado (por exemplo, via `lazy_turn.py rebuild`):

| Campo | Tipo | Origem Primária | Fallback quando `diario.md` ausente |
|---|---|---|---|
| `id` | `str` | `validate_campaign_id(campaign_id)` | Idêntico |
| `dir` | `Path` | `base / clean_id` | Idêntico |
| `diario` | `Path` | `camp_dir / "diario.md"` | Caminho alvo onde o rebuild gravará `diario.md` |
| `ficha` | `Path` | `camp_dir / "ficha.md"` | Caminho alvo onde o rebuild gravará `ficha.md` |
| `npcs` | `Path` | `camp_dir / "npcs.md"` | Caminho alvo onde o rebuild gravará `npcs.md` |
| `mundo` | `Path` | `camp_dir / "mundo.md"` | Arquivo estático de configuração |
| `regras` | `Path` | `camp_dir / "regras.md"` | Arquivo estático de configuração |
| `schema_version` | `int` | `diario.md` (`schema_version: 1`) | Lido de `projections/diario.md` ou `events/000001.jsonl` (`campaign.created.payload.config_version`, default `1`) |
| `system` | `str` | `parse_regras_manifest(regras.md)` | Idêntico |
| `calendar` | `dict` | `parse_regras_manifest(regras.md)` | Idêntico |

**Regra de Validação**:
- Se `diario.md` não existir na raiz e `allow_missing_projections=False`, levanta `FileNotFoundError`.
- Se `diario.md` não existir na raiz, `allow_missing_projections=True`, mas **nem** `events/*.jsonl` **nem** `projections/diario.md` existirem, levanta `FileNotFoundError` (campanha irrecuperável).

---

## 2. Payloads Canônicos para Projeção Derivada sem `*_after` (P2-2)

Proíbe-se o uso de `meta["diario_after"]`, `meta["ficha_after"]` e `meta["npcs_after"]` em qualquer evento de turno ou de comando. Os projetores reconstroem `diario.md`, `ficha.md` e `npcs.md` aplicando cada evento em ordem de `seq` sobre o baseline inicial de `campaign.created`.

### 2.1 `turn.committed`
```json
{
  "turn": 4,
  "summary": "O herói atravessa a ponte sob fogo cerrado",
  "scene_type": "standard",
  "location": "Ponte de Cinzas",
  "present": ["Protagonista", "Aliado Inicial"],
  "vitals": {"hp": 17, "stamina": 13, "ce": 10},
  "vitals_line": "HP 17/20, Stamina 13/15, Energia 10/10",
  "costs": {"hp": -3, "stamina": -2},
  "state_shift": "A ponte foi interditada pela guarda",
  "alerts": [],
  "restored_vitals": false
}
```

### 2.2 `protagonist.sheet_changed`
```json
{
  "kind": "vital | attribute | ability | milestone | item | condition",
  "target": "FOR",
  "new_value": 11,
  "delta": 1,
  "points_remaining": 0,
  "training": "",
  "source": "spend_attr | commit_cost | commit | compensação_cor_..."
}
```

### 2.3 `protagonist.progression_changed`
```json
{
  "xp_delta": 150,
  "xp_total": 300,
  "level": 2,
  "attribute_points": 1,
  "ability_points": 1,
  "base_step": 250,
  "turn": 4,
  "skip_ledger": false,
  "source": "Missão 'Escolta' (Q1) concluída"
}
```

### 2.4 `faction.reputation_changed`
```json
{
  "faction": "Conselho",
  "delta_rep": 1,
  "new_score": 1,
  "delta_favors": 1,
  "delta_debts": 0,
  "favors": 1,
  "debts": 0,
  "turn": 4,
  "quest_id": "Q1",
  "reason": "Cumprimento de missão contratada (Q1)"
}
```

### 2.5 `quest.created`, `quest.objective_completed`, `quest.completed`, `quest.failed`, `quest.status_changed`
- `quest.created`: `id`, `title`, `type`, `objectives`, `contractor`, `clock`, `reward`, `phase`.
- `quest.objective_completed`: `id`, `objective_idx`, `xp_awarded`, `turn`.
- `quest.completed`: `id`, `xp_awarded`, `evidence`, `turn`.
- `quest.failed`: `id`, `reason`, `turn`.
- `quest.status_changed`: `id`, `status` (`ACTIVE` | `BLOCKED` | `ABANDONED` | `COMPLETED` | `FAILED`), `reason`, `objective` (quando `add_objective`), `turn`.

### 2.6 `npc.updated`
```json
{
  "npc_id": "aliado_inicial",
  "changes": {
    "name": "Aliado Inicial",
    "mode": "turn_update | upsert",
    "raw_update": "Atitude: alerta | Relação: Confiança +1",
    "attitude": "alerta",
    "relation": "Confiança +1",
    "bonds": "",
    "classification": "",
    "role": "",
    "faction": "",
    "psychology": "",
    "will": "",
    "weakness": "",
    "dynamics": "",
    "appearance": ""
  }
}
```

---

## 3. Especificação de Mudanças Compensatórias (`CorrectionChange` — P2-3)

Cada item em `changes` de `CorrectionService.issue_correction` segue um dos contratos abaixo:

| Domínio (`field`) | Campos de Entrada em `change` | Evento Compensatório Emitido | Efeito na Projeção |
|---|---|---|---|
| `xp` / `xp_delta` | `delta: int` | `protagonist.progression_changed` | Ajusta XP, nível, pontos/vitais de nível em `ficha.md` e adiciona entrada no XP Ledger em `diario.md` |
| `vital` / `hp` / `stamina` / `ce` / `attribute` / `item` / `condition` | `target: str`, `new_value: Any` (ou `delta: int`) | `protagonist.sheet_changed` | Atualiza recurso vital, atributo ou item em `ficha.md` |
| `reputation` | `faction: str`, `delta: int`, `delta_favors: int = 0`, `delta_debts: int = 0` | `faction.reputation_changed` | Atualiza reputação/favores/débitos em `ficha.md` e adiciona entrada no Ledger de Facções em `diario.md` |
| `clock` | `name: str`, `delta: int = 0`, `status: str = ""` (`ACTIVE`\|`BREACHED`\|`RESOLVED`) | `clock.advanced` (e/ou `clock.resolved`) | Ajusta progresso ($\ge 0$) e status do relógio em `diario.md` |
| `quest` | `quest_id: str` (ou `id`), `status: str` (`ACTIVE`\|`BLOCKED`\|`COMPLETED`\|`FAILED`\|`ABANDONED`), `reason: str = ""` | `quest.status_changed` | Transiciona o status da missão em `diario.md` |
| `arc` | `title: str = ""`, `stage: str = ""`, `question: str = ""` | `arc.updated` | Atualiza Título, Pergunta Central e/ou Fase do arco ativo em `diario.md` |
