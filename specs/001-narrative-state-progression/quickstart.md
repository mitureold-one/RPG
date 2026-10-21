# Quickstart & Validation Guide: Narrative State & Progression Engine

**Feature**: `narrative-state-progression`  
**Phase**: Phase 1 (Quickstart & Validation)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. Prerequisites & Setup

Ensure you are working in the root of the project:
```powershell
cd c:\Users\Konor\Documents\RPGPRO
```

---

## 2. End-to-End Validation Scenarios

### Scenario A: Registering and Listing a Faction Clock
1. Create a test threat clock for an impending ambush or plot:
   ```powershell
   python lazy_turn.py clock --campaign jjk_sakigake --add "Ataque da Facção Inimiga" --max 4 --trigger "Invasão surpresa ao complexo"
   ```
2. Verify the clock is registered in `diario.md`:
   ```powershell
   python lazy_turn.py clock --campaign jjk_sakigake --list
   ```
   **Expected Outcome**: Shows `[Ataque da Facção Inimiga]: 0/4 [░░░░] (ACTIVE)`.

---

### Scenario B: Advancing a Clock & Tri-Scale Inspection via Prepare
1. Advance the clock by 2 steps:
   ```powershell
   python lazy_turn.py clock --campaign jjk_sakigake --advance "Ataque da Facção Inimiga" --steps 2
   ```
2. Run `prepare` to verify Tri-Scale output:
   ```powershell
   python lazy_turn.py prepare --campaign jjk_sakigake --action "Conferir defesas" --no-roll
   ```
   **Expected Outcome**: The JSON output contains `world_scale.active_clocks` reflecting `2/4`.

---

### Scenario C: Committing a Turn with Mandatory State Shift
1. Commit a turn with an explicit state shift:
   ```powershell
   python lazy_turn.py commit --campaign jjk_sakigake `
     --summary "Sakigake e Megumi reforçaram o portão leste após avistarem batedores." `
     --state-shift "Portão leste fortificado (+2 DEF); batedores inimigos recuaram para alertar o grupo principal." `
     --clock-advance "Ataque da Facção Inimiga:1"
   ```
2. Verify `diario.md`:
   - Contains the new turn with `Mudança de Estado`.
   - The clock `Ataque da Facção Inimiga` now stands at `3/4`.

---

### Scenario D: Clock Breach & Automatic Crisis Trigger
1. Advance the final step:
   ```powershell
   python lazy_turn.py clock --campaign jjk_sakigake --advance "Ataque da Facção Inimiga" --steps 1
   ```
2. Run `review`:
   ```powershell
   python lazy_turn.py review --campaign jjk_sakigake
   ```
   **Expected Outcome**: Flags `CLOCK_BREACHED: O relógio 'Ataque da Facção Inimiga' atingiu 4/4! Gatilho obrigatório: Invasão surpresa ao complexo.`
