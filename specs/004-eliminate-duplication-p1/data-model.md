# Phase 1 Data Model & Schemas: P1 Deduplication & Cognitive Load Reduction

**Feature**: `eliminate-duplication-p1`  
**Status**: Completed  
**Created**: 2026-10-21  

---

## 1. Minimalist Router Schema (`AGENTS.md`)

```yaml
AGENTS_MD_ROUTER:
  max_lines: 15
  sections:
    - title: "RPGPRO Sovereign Router"
    - statement: "Identity & deterministic autonomy"
    - sovereignty_ladder:
        - "Grau 1 (Universal): Framework RPGPRO (regras universais, dados de 3 portões, SSOT Markdown)"
        - "Grau 2 (Diegese): Regras e mundo da campanha ativa (campaigns/<id>/regras.md e mundo.md)"
        - "Grau 3 (Psicologia): Análise de pesos dos NPCs (campaigns/<id>/npcs.md)"
    - routing_rules:
        - "Active campaign detection under campaigns/"
        - "Action turns -> rpg-narrative-engine (prepare -> step_3_writer_mandate -> commit)"
        - "Macro-planning & pacing -> rpg-showrunner on-demand (plan, clock, arc)"
        - "Inviolable directives: Zero emojis, anti-puppeteering, SSOT Markdown"
```

---

## 2. Dynamic Prose Mandate Entity (`step_3_writer_mandate`)

Injected by `lazy_turn.py prepare` as the Single Source of Truth for text generation:

```typescript
interface WriterMandatePayload {
  scene_type: string;             // standard | interlude | parallel | timeskip | dossier | flashback | prologue | epilogue | post_credits | fade_to_black
  why_this_structure: string;     // Rationale for structural selection
  structure_and_tone: string;     // Ordered sequence of dramatic beats and required tone
  dialogue_and_style: string;     // Dialogue formatting, perspective, and hook instructions
}
```

---

## 3. Campaign Rules File Schema (`campaigns/<id>/regras.md`)

Refactored from Grade 1 duplication into pure Grade 2 Diegetic Rules:

```markdown
# Regras de Arbitragem & Sistema de Poder: {Nome da Campanha}

## 1. Modificadores Diegéticos & Overrides de DC (Grau 2)
* A escala base de desafio segue a Escala Canônica Universal do Framework (DC 10 Fácil, DC 15 Média, DC 20 Difícil, DC 25 Extrema).
* [Opcional: Overrides ou limiares específicos desta campanha, se houver. Ex: "DC 20 para feitiços sem catalisador". Caso contrário: "Nenhum override ativo — utiliza a escala universal padrão."]

---

## 2. Economia de Recursos & Sistema de Poder
* **HP (Pontos de Vida):** [Significado diegético da vitalidade neste cenário]
* **Stamina:** [Significado diegético do esforço físico neste cenário]
* **{Recurso Especial}:** [Definição do recurso místico/tecnológico/energético e regras de recarga]

---

## 3. Leis Especiais de Arbitragem & Tabus do Universo (Grau 2 - Diegese)
* [Regra diegética 1]
* [Regra diegética 2]
```

---

## 4. Markdown SSOT Schemas in `references/3_campaign_crud_and_state.md`

### 4.1 Threat Clocks Schema in `diario.md`
```markdown
### Relógios de Ameaça & Prazos
* **[{Nome do Relógio}]:** {Passos Atuais}/{Passos Totais} (Gatilho: {Descrição do evento de ruptura}) [{ACTIVE|RESOLVED}]
```
*Governança de Uso*: Documentada exclusivamente em `rpg-showrunner/SKILL.md`.

### 4.2 Scene Queue & Milestones Schema in `diario.md`
```markdown
### Planejamento de Trama & Fila de Cenas
* **Fila de Cenas Agendadas:**
  * [ ] **[{scene_type}]** (Atores: {Personagens em foco}): {Batida ou premissa da cena}.
* **Marcos Futuros do Arco:**
  * {Marco projetado para o clímax ou resolução}.
```
*Governança de Uso*: Documentada exclusivamente em `rpg-showrunner/SKILL.md`.
