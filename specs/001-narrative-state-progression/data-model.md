# Data Model & State Transitions: Narrative State & Progression Engine

**Feature**: `narrative-state-progression`  
**Phase**: Phase 1 (Data Modeling & Domain Design)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. Domain Entities & Schemas

### 1.1 Narrative Clock (`NarrativeClock`)
Represents an ongoing off-screen agenda, an approaching crisis, or a deadline.
* **Fields**:
  - `name`: `str` — Unique name of the threat/agenda (e.g. `"Plano de Kenjaku / Shibuya"`).
  - `current_segments`: `int` — Current filled segments ($0 \le current \le max$).
  - `max_segments`: `int` — Total segments required to trigger ($4, 6, 8, \text{etc.}$).
  - `trigger_event`: `str` — The explicit world event that erupts when `current == max`.
  - `status`: `str` — `"ACTIVE"`, `"BREACHED"` (current >= max), or `"RESOLVED"`.
* **Serialization in `diario.md`**:
  ```markdown
  ###  Relógios de Ameaça & Prazos
  * **[Nome do Relógio]:** 3/6 (Gatilho: Descrição do evento que eclode)
  ```

---

### 1.2 Dramatic Arc State (`DramaticArc`)
Represents the overarching narrative conflict currently framing the scenes.
* **Fields**:
  - `title`: `str` — Short name of the active arc (e.g. `"A Véspera da Tempestade"`).
  - `central_question`: `str` — The dramatic question that defines the arc (e.g. `"Conseguirão identificar o traidor antes do conselho?"`).
  - `stage`: `str` — One of `["Preparação", "Confrontação", "Clímax", "Resolução"]`.
  - `key_milestones`: `List[str]` — Critical discoveries or shifts needed to advance stages.
* **Serialization in `diario.md`**:
  ```markdown
  ###  Arco Narrativo Ativo
  * **Título:** A Véspera da Tempestade
  * **Pergunta Central:** Conseguirão desmascarar o traidor antes da reunião do conselho?
  * **Fase:** Confrontação
  ```

---

### 1.3 Turn State Shift (`StateShift`)
Represents the irrevocable delta produced by a completed narrative turn.
* **Fields**:
  - `turn_number`: `int` — Canonical turn identifier.
  - `shift_summary`: `str` — Tangible change in the world, alliances, or resources.
  - `clock_deltas`: `Dict[str, int]` — Narrative clocks altered during this turn.
* **Serialization in `diario.md`**:
  ```markdown
  * **Turno 66:** Resumo do que aconteceu.
    * **Mudança de Estado:** Nobara descobriu a pista falsa; o relógio de Kenjaku avançou 1 passo.
  ```

---

## 2. State Transition Diagrams

### 2.1 Narrative Clock Lifecycle
```
     [Created]
         │
         ▼
    ┌──────────┐      Advance (+N)      ┌──────────┐
    │  ACTIVE  ├───────────────────────►│  ACTIVE  │
    └────┬─────┘                        └────┬─────┘
         │                                   │
         │ (current == max)                  │ (Threat Neutralized)
         ▼                                   ▼
   ┌───────────┐                       ┌───────────┐
   │ BREACHED  │                       │ RESOLVED  │
   │ (Rupture) │                       │ (Defused) │
   └───────────┘                       └───────────┘
```

### 2.2 Turn Progression State Machine (The 5-Step Loop)
```
┌────────────────────────────────────────────────────────┐
│ 1. SITUAÇÃO ATIVA                                      │
│    • Pergunta/tensão imediata da cena                  │
│    • Relógios de ameaça ativos pressionando tempo      │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. RESISTÊNCIA & ATRITO                                │
│    • Oposição externa, física, social ou moral         │
│    • Resolução mecânica via 3 Portões (se aplicável)   │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. DECISÃO SIGNIFICATIVA DO JOGADOR                    │
│    • Ação autônoma do protagonista (Zero Puppeteering) │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. IMPACTO CONCRETIZADO                                │
│    • Custos vitais da ficha deduzidos                  │
│    • Avanço no relógio de tempo e clocks de facções    │
└───────────────────────────┬────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. NOVO ESTADO (ANTI-INÉRCIA)                          │
│    • O tabuleiro NÃO volta ao início                   │
│    • Registrado no --state-shift do commit             │
└────────────────────────────────────────────────────────┘
```

---

## 3. Validation Rules & Integrity Constraints

1. **Clock Bounds**: `current_segments` can never be negative. If `current >= max`, the status automatically switches to `BREACHED` and triggers an urgent issue in `cmd_review`.
2. **Mandatory State Delta**: A turn cannot commit with an empty `--state-shift` unless flagged as a pure meta/downtime setup.
3. **Anti-Inertia Constraint**: If 2 consecutive turns share identical or empty `Mudança de Estado`, `cmd_review` flags a `NARRATIVE_STAGNATION` warning.
