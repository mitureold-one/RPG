# CLI Contracts & Schema Interfaces: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature**: `factions-and-reputation`  
**Status**: Completed  
**Created**: 2026-10-22  
**Context**: Contratos de linha de comando, schemas de payload JSON e assinaturas de funções do subcomando `faction` e integrações.

---

## 1. Subcomando CLI `lazy_turn.py faction`

```bash
# Consulta legível e exportação JSON
python lazy_turn.py faction --campaign <id> --list
python lazy_turn.py faction --campaign <id> --list --json

# Cadastro de nova facção em mundo.md
python lazy_turn.py faction --campaign <id> --add "Ordem da Fé Purificadora" --power 4 --scale regional --clock "Purificação Herética" --desc "Inquisidores fanáticos."

# Alteração manual/administrativa de reputação com justificativa
python lazy_turn.py faction --campaign <id> --rep "Conselho dos Lordes:+1" --reason "Doação de armas para a guarnição"

# Manipulação de Favores e Débitos
python lazy_turn.py faction --campaign <id> --favor "Conselho dos Lordes:-1" --reason "Cobrança de escolta armada"
python lazy_turn.py faction --campaign <id> --debt "A Guarda da Meia-Noite:+1" --reason "Empréstimo de suprimentos de emergência"

# Turno de Facções Off-Screen (Tick de Mundo)
python lazy_turn.py faction --campaign <id> --tick
```

### 1.1 Especificação de Argumentos de `faction`

| Argumento | Tipo | Padrão | Descrição |
| :--- | :--- | :--- | :--- |
| `--campaign` | `str` | *Obrigatório* | ID da pasta da campanha em `campaigns/`. |
| `--list` | `bool` | `False` | Exibe resumo formatado das facções e reputações. |
| `--json` | `bool` | `False` | Emite a saída estritamente em JSON válido. |
| `--add` | `str` | `""` | Nome da nova facção a cadastrar em `mundo.md`. |
| `--tag` | `str` | `""` | Tag identificadora (default: slug uppercase do nome). |
| `--power` | `int` | `3` | Poder da facção (1 a 5). |
| `--scale` | `str` | `"regional"` | Escala de atuação (`local`, `regional`, `continental`, `global`). |
| `--clock` | `str` | `""` | Nome de relógio narrativo vinculado em `diario.md`. |
| `--desc` | `str` | `""` | Descrição factual dos objetivos e filosofia da facção. |
| `--rep` | `str` | `""` | Formato `Facção:delta` (ex.: `Guarda:-1` ou `Conselho:+1`). |
| `--reason` | `str` | `""` | Justificativa diegética da alteração de reputação/favor. |
| `--favor` | `str` | `""` | Formato `Facção:delta` (ex.: `Conselho:-1` ou `+1`). |
| `--debt` | `str` | `""` | Formato `Facção:delta` (ex.: `Guarda:+1` ou `-1`). |
| `--tick` | `bool` | `False` | Dispara o avanço autônomo off-screen de relógios de facção. |

---

## 2. Contrato de Retorno JSON de `faction --list --json`

```json
{
  "campaign": "dinastia_cinzas",
  "factions": [
    {
      "tag": "CONSELHO_LORDES",
      "name": "Conselho dos Lordes de Cinzas",
      "description": "Nobres tradicionalistas que exigem a coroação de Aemon e a manutenção dos privilégios senhoriais.",
      "power": 4,
      "scale": "regional",
      "clock": "Conspiração da Corte",
      "clock_progress": "2/4 [ACTIVE]",
      "protagonist_reputation": {
        "score": 2,
        "tier": "Aliado",
        "favors": 1,
        "debts": 0,
        "social_dc_modifier": -2
      }
    },
    {
      "tag": "GUARDA_MEIA_NOITE",
      "name": "A Guarda da Meia-Noite",
      "description": "Tropa veterana de elite liderada por Lorde Malakor.",
      "power": 3,
      "scale": "local",
      "clock": "Golpe da Guarda de Malakor",
      "clock_progress": "2/4 [ACTIVE]",
      "protagonist_reputation": {
        "score": -2,
        "tier": "Hostil",
        "favors": 0,
        "debts": 1,
        "social_dc_modifier": 3
      }
    }
  ]
}
```

---

## 3. Extensões no Subcomando `commit`

No `lazy_turn.py commit`, são adicionadas as seguintes flags:
* `--faction-rep "<Nome>:<delta>"`: Aplica mutações diretas de reputação (suporta múltiplas separadas por pipe `|`).
* `--faction-favor "<Nome>:<delta>"`: Incrementa ou consome favores.
* `--faction-debt "<Nome>:<delta>"`: Incrementa ou quita débitos.

### Automação de Missões (`--quest-complete` e `--quest-fail`):
Ao executar `commit --quest-complete <QID>`:
1. O motor inspeciona a missão para verificar se há o metadado `Contratante: <Facção>`.
2. Se houver, busca a facção correspondente em `mundo.md`.
3. Aplica automaticamente:
   * `Reputação = min(3, Reputação + 1)`
   * `Favores = Favores + 1`
4. Crava a entrada sob `### Registro de Reputação & Facções` em `diario.md`:
   `* **[Turno {N}]** {Facção}: +1 Reputação ({anterior} -> {novo} [{Tier}]) | Favores: +1 | Motivo: Cumprimento de missão contratada | Missão: {QID}`

Ao executar `commit --quest-fail <QID>`:
1. Aplica:
   * `Reputação = max(-3, Reputação - 1)`
   * `Débitos = Débitos + 1`
2. Registra o evento correspondente no diário.

---

## 4. Injeção no Payload de `lazy_turn.py prepare`

O retorno de `cmd_prepare` passa a incorporar `step_1_faction_context`:

```json
{
  "system": "d20_3gates",
  "step_1_gm_arbitration": { ... },
  "step_1_quest_context": { ... },
  "step_1_faction_context": {
    "factions_in_scene": [
      {
        "name": "A Guarda da Meia-Noite",
        "tag": "GUARDA_MEIA_NOITE",
        "score": -2,
        "tier": "Hostil",
        "favors": 0,
        "debts": 1,
        "social_dc_mod": 3,
        "suggested_variant": "disadvantage",
        "members_in_scene": ["Lorde Malakor"],
        "writer_directive": "POSTURA OBRIGATÓRIA DE FACÇÃO HOSTIL: Membros da Guarda da Meia-Noite tratam o protagonista como inimigo jurado (-2). Proibida qualquer cordialidade, cooperação espontânea ou confiança sem coerção física ou chantagem comprovada."
      }
    ]
  },
  "step_2_engine_state": { ... },
  "step_3_writer_mandate": { ... }
}
```

---

## 5. Contrato de Saída do Turno Off-Screen (`faction --tick`)

```json
{
  "campaign": "dinastia_cinzas",
  "operation": "faction_tick",
  "advancements": [
    {
      "faction": "Conselho dos Lordes de Cinzas",
      "power": 4,
      "clock": "Conspiração da Corte",
      "previous_progress": "1/4",
      "new_progress": "2/4",
      "status": "ACTIVE",
      "narrative_hint": "Espiões do Conselho infiltraram as casernas palacianas nos bastidores."
    }
  ],
  "breaches": []
}
```
