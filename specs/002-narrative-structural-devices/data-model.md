# Data Model & Domain Entities: Narrative Structural Devices

**Feature**: `narrative-structural-devices`  
**Phase**: Phase 1 (Data Modeling & Domain Design)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. Scene Type Specification (`SceneType`)

An enumeration of supported narrative structural modes:
* **`standard`** *(Default)*: Interactive turn featuring protagonist, 3-gate rolls (if challenged), and 5-stage progression.
* **`interlude`**: Off-screen vignette featuring third-party NPCs and antagonists reacting to prior events.
* **`parallel`**: Simultaneous occurrence unfolding elsewhere in the world during current protagonist action.
* **`timeskip`**: Macro-temporal progression condensing days/weeks/months of downtime, travel, or training.
* **`dossier`**: In-universe epistolary document (intelligence report, letter, intercepted transmission).
* **`flashback`**: Historical memory or retrospective sequence contextualizing an emotional drive or secret.
* **`prologue`**: Mythic, historical, or prequel sequence framing the start of an overarching campaign arc.
* **`epilogue`**: Long-term aftermath and societal resolution following an arc climax.
* **`post_credits`**: Brief cliffhanger or stinger hinting at an emerging conflict.

---

## 2. Serialization in `diario.md`

### 2.1 Standard Turn Entry
```markdown
* **Turno 66:** O furgão atravessa os portões sob chuva torrencial. Vitais: HP 30/30, Stamina 20/20.
  * **Mudança de Estado:** Portão fortificado; guarda alertada.
```

### 2.2 Interlude / Parallel Entry
```markdown
* **Turno 67 [Interlúdio - Esconderijo de Shibuya]:** Kenjaku e Mahito avaliam os efeitos do confronto em Quioto. Presentes: Kenjaku, Mahito, Uraume.
  * **Mudança de Estado:** Kenjaku antecipa a mobilização das maldições; relógio [Incidente de Shibuya] avançou +1.
```

### 2.3 Timeskip Entry
```markdown
* **Turno 68 [Salto Temporal: +2 Meses]:** Dois meses de treinamento intensivo na montanha. Calendário avançou para 25 de Janeiro de 2019. Vitais totalmente restaurados: HP 30/30, Stamina 20/20.
  * **Mudança de Estado:** Treinamento de barreira concluído; facções de Quioto encerraram o inquérito formal.
```

### 2.4 Dossier Entry
```markdown
* **Turno 69 [Dossiê Especial - Arquivos do Clã Kamo]:** Relatório confidencial interceptado classificando o protagonista como 'Ativo de Risco Nível 1'.
  * **Mudança de Estado:** Alerta emitido pelo conselho conservador; informante revelado.
```

---

## 3. State Transitions & Rules

```
                      ┌──────────────────┐
                      │  Standard Turn   │◄──────────────┐
                      └────────┬─────────┘               │
                               │                         │
            ┌──────────────────┼──────────────────┐      │
            ▼                  ▼                  ▼      │
     ┌──────────────┐   ┌──────────────┐   ┌────────────┐│
     │  Interlude   │   │   Timeskip   │   │  Dossier   ││
     │  (Off-screen)│   │  (Macro Leap)│   │ (Document) ││
     └──────┬───────┘   └──────┬───────┘   └─────┬──────┘│
            │                  │                 │       │
            └──────────────────┴─────────────────┴───────┘
```

1. **Protagonist Absence**: When `scene_type != "standard"`, protagonist presence in `diario["present"]` is optional.
2. **Roll Suppression**: In `interlude`, `timeskip`, `dossier`, `prologue`, and `epilogue`, dice rolls are omitted automatically.
3. **Mandatory Delta**: Even cutscenes, dossiers, and interludes must register an explicit `Mudança de Estado`.
