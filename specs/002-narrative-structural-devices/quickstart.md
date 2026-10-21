# Quickstart & Validation Guide: Narrative Structural Devices

**Feature**: `narrative-structural-devices`  
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

## 2. Validation Scenarios

### Scenario A: Running an Interlude (Off-Screen Faction POV)
1. Prepare an interlude scene with off-screen antagonists:
   ```powershell
   python lazy_turn.py prepare --campaign jjk_sakigake `
     --scene-type interlude `
     --actors "Kenjaku, Mahito" `
     --action "Kenjaku e Mahito discutem a resposta aos acontecimentos de Quioto"
   ```
2. Verify output JSON:
   - `scene_type` is `"interlude"`.
   - `actors_in_scene` contains `"Kenjaku", "Mahito"`.
   - Dice roll requirement is waived.
   - `3_narrator_direction` instructs cutscene direction.

---

### Scenario B: Committing a Timeskip (+2 Meses)
1. Execute a timeskip commit:
   ```powershell
   python lazy_turn.py commit --campaign jjk_sakigake `
     --scene-type timeskip `
     --time "+60d" `
     --summary "Dois meses de treinamento na floresta e refinamento do fluxo de energia." `
     --state-shift "Técnica estabilizada; facções adversárias concluíram seus preparativos de inverno." `
     --clock-advance "Incidente de Shibuya:1"
   ```
2. Verify `diario.md`:
   - Turn is recorded with `[TIMESKIP]`.
   - Calendar jumped forward 60 days.
   - Vitals are replenished to maximum.

---

### Scenario C: Generating an In-Universe Special Dossier
1. Prepare a classified dossier scene:
   ```powershell
   python lazy_turn.py prepare --campaign jjk_sakigake `
     --scene-type dossier `
     --action "Relatório confidencial do Conselho de Quioto sobre o nível de ameaça do protagonista"
   ```
2. Verify output JSON:
   - `council_pipeline["4_writer_prose"]` mandates epistolary document layout.
