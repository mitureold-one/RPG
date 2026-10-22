# Phase 1 Data Model & Schemas: P3 Transformação de Regra em Verificação

**Feature**: `rule-verification-p3`  
**Status**: Completed  
**Created**: 2026-10-21  
**Target Backlog Phase**: P3 (Reviewer Lints, Typed Overrides & Boundary Testing)

---

## 1. Reviewer Issue Entity (`council/reviewer.py`)

Todos os diagnósticos emitidos pelo `cmd_review` em `council/reviewer.py` seguem o modelo canônico de issue de integridade.

### Issue Schema
```typescript
interface ReviewerIssue {
  type: string;             // Identificador único da regra violada
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  detail: string;           // Diagnóstico contextualizado e ação corretiva recomendada
}
```

### Novos Tipos de Issue Introduzidos em P3

| Tipo de Issue | Severidade | Gatilho / Condição | Exemplo de Diagnóstico |
| :--- | :---: | :--- | :--- |
| `EMOJI_DETECTED` | `MEDIUM` | Caractere Unicode pertencente a faixas de emojis ou pictogramas no texto do diário. | `"Caractere emoji detectado no Turno 12 ('🔥'): o estilo literário do RPGPRO exige prosa textual pura sem emojis."` |
| `SCRIPT_FORMAT_DETECTED` | `HIGH` | Linha iniciada por padrão de roteiro teatral (`[Nome]:` ou `Nome: "fala"`). | `"Formato teatral detectado no Turno 12 ('Kallista: Não recue.'): utilize travessão literário (—) e diálogo integrado à narrativa."` |
| `FOURTH_WALL_QUESTION` | `MEDIUM` | Final de cena ou resumo contendo pergunta clichê de encerramento ("O que você faz?"). | `"Pergunta clichê de quarta parede detectada no encerramento ('O que você faz?'): encerre com impacto sensorial e gancho diegético aberto."` |

---

## 2. Machine-Readable Overrides Entity (`regras.md`)

O bloco de mecânicas de campanha em `regras.md` padroniza os modificadores sistêmicos da mesa sob a chave `overrides:`.

### Schema Estruturado
```typescript
interface MechanicOverride {
  id: string;                                                                 // Identificador kebab_case ou snake_case
  type: "cost_multiplier" | "resistance" | "immunity" | "threshold_shift" | "stat_penalty" | "custom";
  target: string;                                                             // Recurso ou atributo (ex: stamina, hp, mana_detection, mental)
  value: number | string | boolean;                                           // Valor numérico (2.0, -2) ou qualificador (immune, true)
  condition?: string;                                                         // Contexto de aplicação da regra
}

interface CampaignMechanicsManifest {
  system: string;                                                             // ex: "d20_3gates"
  ruleset?: string;                                                           // ex: "d20_3gates"
  overrides: MechanicOverride[];
}
```

### Representação Canônica em `regras.md`
```yaml
system: d20_3gates
overrides:
  - id: exhaustion_friction
    type: cost_multiplier
    target: stamina
    value: 2.0
    condition: "Esforço extremo continuado sem repouso"
  - id: mana_sensor_immunity
    type: immunity
    target: mana_detection
    value: true
    condition: "Artefatos ou feitiços de medição mágica"
  - id: torquasm_vo_defense
    type: resistance
    target: mental_influence
    value: immune
    condition: "Encantos de submissão ou controle mental"
```

---

## 3. Preparation Payload Snapshot Schema (`lazy_turn.py prepare`)

O payload retornado por `cmd_prepare` deve respeitar o contrato estrito congelado pela suíte de testes.

### Snapshot de Contrato JSON
```typescript
interface PreparePayloadSnapshot {
  campaign: string;
  system: string;
  operation_mode: "prepare";
  step_1_gm_arbitration: {
    action: string;
    ruleset: string;
    dc_ladder: Record<string, string>;
    overrides: MechanicOverride[];
    roll_result?: {
      natural: number;
      modifier: number;
      total: number;
      dc: number;
      tier: string;
      summary: string;
    };
  };
  step_2_engine_state: {
    scene_type: string;
    vitals: Record<string, any>;
    inventory: string[];
    active_clocks: Array<{
      name: string;
      progress: string;
      trigger: string;
    }>;
  };
  step_3_writer_mandate: {
    prose_guidelines: string[];
    active_scene_mandate: {
      type: string;
      instructions: string[];
    };
    present_npcs: Array<{
      name: string;
      attitude: string;
      will: string;
    }>;
  };
  step_4_post_turn_commit_template: {
    command_template: string;
  };
}
```
