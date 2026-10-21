# Interface & CLI Contracts: Narrative State & Progression Engine

**Feature**: `narrative-state-progression`  
**Phase**: Phase 1 (Interface Contracts)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. CLI Commands & Schemas

### 1.1 Command: `lazy_turn.py clock`
Manages narrative clocks for ongoing threats, faction agendas, and deadlines.

```powershell
python lazy_turn.py clock --campaign <CAMPAIGN_ID> [OPTIONS]
```

#### Arguments & Options:
* `--campaign <id>` (Required): Campaign identifier.
* `--list`: Lists all registered clocks with current status and progress bars.
* `--add "<Nome>"`: Registers a new clock.
  * `--max <N>`: Maximum segments (Default: `4`).
  * `--trigger "<Evento>"`: Text description of what happens upon breach.
* `--advance "<Nome>"`: Ticks a clock forward.
  * `--steps <N>`: Number of steps to advance (Default: `1`).
* `--resolve "<Nome>"`: Marks a clock as defused/resolved.
* `--json`: Outputs the result in JSON format.

#### Example Output (`--list --json`):
```json
{
  "campaign": "jjk_sakigake",
  "active_clocks": [
    {
      "name": "Plano de Kenjaku / Incidente de Shibuya",
      "progress": "4/6",
      "current": 4,
      "max": 6,
      "status": "ACTIVE",
      "trigger": "Ataque coordenado contra o selamento de Satoru Gojo."
    }
  ],
  "breached_clocks": []
}
```

---

### 1.2 Extensions to `lazy_turn.py prepare`
The JSON output returned by `cmd_prepare` is extended with structured tri-scale state:

```json
{
  "campaign": "jjk_sakigake",
  "council_pipeline": {
    "1_architect_canon": {
      "current_calendar": "25 de Novembro de 2018, 19:57",
      "world_scale": {
        "active_clocks": [
          {"name": "Incidente X", "segments": "3/4", "status": "ACTIVE"}
        ],
        "breached_threats": []
      },
      "arc_scale": {
        "title": "A Véspera da Tempestade",
        "central_question": "Conseguirão desmascarar o plano antes da reunião?",
        "stage": "Confrontação"
      }
    },
    "3_narrator_direction": {
      "pacing_directive": "CICLO EM 5 FASES: Situação Ativa -> Resistência -> Escolha -> Consequência -> NOVO ESTADO OBRIGATÓRIO.",
      "anti_inertia_alert": null
    }
  }
}
```

---

### 1.3 Extensions to `lazy_turn.py commit`
Adds state-progression flags:

```powershell
python lazy_turn.py commit --campaign <CAMPAIGN_ID> `
  --summary "<Resumo do turno>" `
  --state-shift "<O que mudou no tabuleiro/alianças/recursos>" `
  --clock-advance "<NomeDoRelogio:1>" `
  --time "+30m" `
  --cost "HP -2, CE -10"
```

#### Behavior:
1. Updates `diario.md` with both the turn summary and the mandatory `Mudança de Estado`.
2. Advances specified narrative clocks in `diario.md`.
3. Auto-advances time-sensitive clocks if in-game elapsed time crosses clock thresholds.
4. Audits the post-commit state; if a clock breached its threshold, flags `CLOCK_BREACHED` in the return JSON.
