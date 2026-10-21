# Interface & CLI Contracts: Narrative Structural Devices

**Feature**: `narrative-structural-devices`  
**Phase**: Phase 1 (Interface Contracts)  
**Status**: Completed  
**Date**: 2026-10-18  

---

## 1. CLI Extensions

### 1.1 Command: `lazy_turn.py prepare`
Adds `--scene-type` and `--actors`:

```powershell
python lazy_turn.py prepare --campaign <CAMPAIGN_ID> `
  --scene-type <standard|interlude|parallel|timeskip|dossier|flashback|prologue|epilogue|post_credits> `
  [--actors "<NPC1, NPC2>"] `
  [--advance-time "<+7d|+1m|+2m>"]
```

#### JSON Payload Changes:
```json
{
  "campaign": "jjk_sakigake",
  "scene_type": "interlude",
  "actors_in_scene": ["Kenjaku", "Mahito", "Uraume"],
  "canonical_header": " [25 de Novembro de 2018, 22:15] |  [Esconderijo de Shibuya] |  [Kenjaku, Mahito, Uraume]",
  "council_pipeline": {
    "3_narrator_direction": {
      "scene_type_directive": "INTERLÚDIO: Acompanhe a reação dos antagonistas/terceiros. Explore suas vontades, planos e atritos internos sem a presença do protagonista.",
      "directive": "Conduza a cena com subtexto e tensão entre os vilões -> Corte Seco com revelação ou decisão tomada."
    },
    "4_writer_prose": {
      "prose_style": "Cena cinematográfica em terceira pessoa focada nos NPCs.",
      "dialogue_format": "[**Nome do NPC**]: — \"Fala...\" (CADA FALA EM PARÁGRAFO ISOLADO)"
    }
  }
}
```

---

### 1.2 Command: `lazy_turn.py commit`
Adds `--scene-type`:

```powershell
python lazy_turn.py commit --campaign <CAMPAIGN_ID> `
  --summary "<Resumo factual da cena/interlúdio/dossiê>" `
  --state-shift "<Mudança concreta gerada>" `
  [--scene-type <interlude|timeskip|dossier|...>] `
  [--clock-advance "<Nome:Passos>"] `
  [--time "<Data/Hora ou Salto>"]
```

#### Behavior:
* If `--scene-type` is specified, tags the turn in `diario.md`:
  `* **Turno {N} [{SceneType.upper()}]:** {summary}. Vitais: {vitals}.`
* If `--scene-type timeskip`, automatically restores depleted vitals unless partial costs are passed in `--cost`.
