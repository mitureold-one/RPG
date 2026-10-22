# Data Model: Sistema de Missões e Progressão (XP)

**Feature**: `quest-and-progression`  
**Date**: 2026-10-22  
**Status**: Ready for Implementation  

---

## 1. Entities & Attributes

### 1.1 Quest (Missão)
Armazenada em `diario.md` sob a seção `### Missões & Objetivos`.

| Atributo | Tipo | Obrigatório | Descrição / Valores Válidos |
| :--- | :--- | :---: | :--- |
| `id` | `str` | Sim | Identificador determinístico da missão (ex.: `Q1`, `Q2`, `Q3`). |
| `title` | `str` | Sim | Título descritivo da missão. |
| `type` | `enum` | Sim | `MAIN` (Principal), `SIDE` (Secundária), `PERSONAL` (Pessoal), `FACTION` (Facção). |
| `status` | `enum` | Sim | `ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`. |
| `phase` | `str` | Não | Estágio atual do desdobramento (ex.: `Investigação`, `Infiltração`, `Confronto`). |
| `contractor` | `str` | Não | Nome do NPC, facção ou patrono que requisitou o objetivo. |
| `clock_link` | `str` | Não | Nome exato do relógio de ameaça vinculado presente em `diario.md`. |
| `reward_text`| `str` | Não | Descrição textual da recompensa (ex.: `150 XP`, `Aliado na Corte`). |
| `reward_xp`  | `int` | Não | Valor numérico canônico de XP sugerido/esperado. |
| `last_progress_turn` | `int` | Não | Número do turno no qual ocorreu a última atualização de progresso. |
| `xp_paid`    | `int` | Não | Marcador de idempotência: quantidade exata de XP já creditada (`None` se pendente). |
| `objectives` | `List[Objective]` | Sim | Lista ordenada de objetivos pontuais da missão. |

### 1.2 Objective (Objetivo)
Sub-elementos aninhados sob uma missão específica.

| Atributo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `quest_id` | `str` | Sim | ID da missão pai. |
| `index` | `int` | Sim | Posição 1-based do objetivo na lista da missão. |
| `text` | `str` | Sim | Descrição clara e verificável da ação necessária. |
| `done` | `bool` | Sim | `True` para `[x]` (concluído); `False` para `[ ]` (pendente). |

---

### 1.3 ProgressionState (Estado de Progressão)
Armazenado em `ficha.md` sob a seção `### Progressão`.

| Atributo | Tipo | Obrigatório | Descrição |
| :--- | :--- | :---: | :--- |
| `level` | `int` | Sim | Nível mecânico do protagonista (mínimo: 1). |
| `xp` | `int` | Sim | Contador acumulado de experiência total conquistada (unidirecional). |
| `next_threshold` | `int` | Sim | Quantidade total de XP necessária para alcançar o próximo nível. |
| `attribute_points` | `int` | Sim | Saldo de pontos disponíveis para aumentar atributos (FOR, DES, etc.). |
| `ability_points` | `int` | Sim | Saldo de pontos disponíveis para adquirir habilidades & técnicas. |

---

### 1.4 XPGrantRecord (Registro de Concessão de XP)
Representa um evento atômico de ganho de experiência processado no turno.

| Atributo | Tipo | Descrição |
| :--- | :--- | :--- |
| `code` | `str` | Código canônico da fonte (`obj_main`, `quest_main`, `clock_resolved`, etc.). |
| `amount` | `int` | Quantidade de XP concedida. |
| `reference` | `str` | ID da missão, relógio ou contexto (ex.: `Q1`, `obj:Q1:2`). |
| `turn` | `int` | Número do turno em que foi processado. |

---

## 2. Canonical Markdown Layouts

### 2.1 Representação em `diario.md`
```markdown
### Missões & Objetivos
* **[MAIN] O Trono de Pedra-Negra** | Fase: Investigação | Status: ACTIVE | Contratante: Conselho dos Lordes | Relógio: Conspiração | Recompensa: 150 XP | Último Progresso: Turno 12 | XP Pago: 0
  * [x] Interrogar o mensageiro do norte
  * [ ] Obter a lealdade da guarnição
  * [ ] Desmascarar o traidor na corte

* **[SIDE] A Forja Ancestral** | Fase: Coleta | Status: ACTIVE | Contratante: Mestre Durn | Recompensa: 60 XP | Último Progresso: Turno 8
  * [x] Encontrar o minério estelar
  * [ ] Purificar as cinzas do crisol
```

### 2.2 Representação em `ficha.md`
```markdown
### Progressão
* **Nível:** 2
* **Experiência (XP):** 410
* **Próximo Nível:** 500
* **Pontos de Atributo:** 1
* **Pontos de Habilidade:** 0
```

---

## 3. State Machine & Transitions

### 3.1 Transições de Estado de Missão

```
                     ┌──────────────────┐
                     │      ACTIVE      │◄────────────────┐
                     └────────┬─────────┘                 │
               ┌──────────────┼──────────────┐            │
               │              │              │            │
               ▼              ▼              ▼            │
        ┌─────────────┐ ┌───────────┐ ┌─────────────┐     │
        │  COMPLETED  │ │  FAILED   │ │   BLOCKED   │     │
        └─────────────┘ └───────────┘ └──────┬──────┘     │
               │              │              │            │
          (Terminal)     (Terminal)          │ unblock    │
               │              │              └────────────┤
               └──────────────┴───────────────────────────┘
                                  ▲
                         --reopen │ (auditado com razão)
```

1. **`ACTIVE` → `COMPLETED`**:
   - Acionado quando todos os objetivos são marcados como `[x]`, ou via `--complete "Q1" --evidence "..."`.
   - Dispara a concessão do XP da missão e grava `XP Pago: <valor>`.
2. **`ACTIVE` → `FAILED`**:
   - Acionado explicitamente via `--fail "Q1" --reason "..."`.
   - Gravado no diário; não concede XP de missão.
3. **`ACTIVE` → `BLOCKED`**:
   - Acionado via `--block "Q1" --reason "..."` quando um obstáculo intransponível impede o prosseguimento.
4. **`BLOCKED` → `ACTIVE`**:
   - Acionado via `--unblock "Q1"`.
5. **`ACTIVE` → `ABANDONED`**:
   - Acionado via `--abandon "Q1"`.
6. **Reabertura (`COMPLETED`/`FAILED` → `ACTIVE`)**:
   - Requer obrigatoriamente a flag `--reopen "Q1" --reason "..."`. Registra evento auditado.

---

## 4. Invariants & Integrity Constraints

1. **Invariante de Isolamento de Regex**:
   - A linha `* **Experiência (XP):** <valor>` jamais deve ser interpretada como vital (`vitals`) nem como atributo (`stats`).
2. **Invariante de Idempotência**:
   - Nenhuma missão com `XP Pago` pode receber um segundo crédito de XP. Tentativas disparam o lint `QUEST_REWARD_PAID_TWICE`.
3. **Invariante de Unidirecionalidade**:
   - O valor de XP acumulado em `ficha.md` é estritamente não-decrescente ($XP_{t+1} \ge XP_t$).
4. **Invariante de Dedup com Relógios**:
   - Se uma missão vinculada a um relógio for concluída e esse relógio for resolvido simultaneamente, o XP concedido é $\max(XP_{\text{missão}}, XP_{\text{relógio}})$, impedindo duplicidade.
5. **Invariante de Não-Automatização de Fracasso**:
   - A ruptura de um relógio (`CLOCK_BREACHED`) nunca altera o status da missão automaticamente no banco textual; gera o lint `QUEST_OVERDUE` para forçar a arbitragem dramática.
