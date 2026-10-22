# Interface Contracts: Sistema de Missões e Progressão (XP)

**Feature**: `quest-and-progression`  
**Date**: 2026-10-22  
**Status**: Ready for Implementation  

---

## 1. CLI Commands Contract (`lazy_turn.py`)

### 1.1 Subcomando `quest`
Gerencia o ciclo de vida de missões e objetivos em `diario.md`.

```bash
# Listagem
python lazy_turn.py quest --campaign <id> [--list] [--json]

# Cadastro de Nova Missão
python lazy_turn.py quest --campaign <id> --add "<Título>" --type <main|side|personal|faction> \
    [--objective "<texto>"] [--faction "<nome>"] [--clock "<nome>"] [--reward "<texto>"]

# Adição de Objetivo a Missão Existente
python lazy_turn.py quest --campaign <id> --objective "<ID>: <texto>"

# Marcar Objetivo como Concluído
python lazy_turn.py quest --campaign <id> --check "<ID>:<num_obj>"

# Concluir Missão (Transição para COMPLETED)
python lazy_turn.py quest --campaign <id> --complete "<ID>" [--evidence "<texto>"]

# Falhar Missão (Transição para FAILED)
python lazy_turn.py quest --campaign <id> --fail "<ID>" --reason "<texto>"

# Bloquear ou Reabrir Missão
python lazy_turn.py quest --campaign <id> --block "<ID>" --reason "<texto>"
python lazy_turn.py quest --campaign <id> --reopen "<ID>" --reason "<texto>"
```

#### Resposta JSON (`quest --list --json`)
```json
{
  "campaign": "dinastia_cinzas",
  "quests": [
    {
      "id": "Q1",
      "title": "O Trono de Pedra-Negra",
      "type": "MAIN",
      "status": "ACTIVE",
      "phase": "Investigação",
      "contractor": "Conselho dos Lordes",
      "clock": "Conspiração",
      "reward": "150 XP",
      "reward_xp": 150,
      "last_progress_turn": 12,
      "xp_paid": 0,
      "progress_summary": "1/3",
      "objectives": [
        {"index": 1, "text": "Interrogar o mensageiro do norte", "done": true},
        {"index": 2, "text": "Obter a lealdade da guarnição", "done": false},
        {"index": 3, "text": "Desmascarar o traidor na corte", "done": false}
      ]
    }
  ],
  "active_count": 1,
  "completed_count": 0
}
```

---

### 1.2 Subcomando `progress`
Gerencia consulta de XP, evolução de nível e alocação de pontos de build.

```bash
# Consulta de Nível e Pontos
python lazy_turn.py progress --campaign <id> [--list] [--json]

# Gasto de Ponto de Atributo
python lazy_turn.py progress --campaign <id> --spend-attr <FOR|DES|CON|INT|SAB|CAR>

# Gasto de Ponto de Habilidade com Evidência Diegética de Treino
python lazy_turn.py progress --campaign <id> --spend-ability "<Nome>: <efeito>" --training "<contexto diegético>"

# Concessão Administrativa / Retroativa de XP
python lazy_turn.py progress --campaign <id> --award "<codigo_fonte>[:quantidade]"
```

#### Resposta JSON (`progress --list --json`)
```json
{
  "campaign": "dinastia_cinzas",
  "progression": {
    "level": 2,
    "xp": 410,
    "next_threshold": 500,
    "progress_percent": 82.0,
    "attribute_points": 1,
    "ability_points": 0
  }
}
```

---

### 1.3 Flags no Subcomando `commit`
Flags estendidas para acoplar o avanço de objetivos e missões diretamente na consolidação do turno.

```bash
python lazy_turn.py commit --campaign <id> \
    --summary "Texto do resumo..." \
    [--quest-progress "<ID>:<num_obj>"] \
    [--quest-complete "<ID>"] \
    [--quest-fail "<ID>"]
```

* **Efeito no Commit**:
  1. Conclui os objetivos indicados ou fecha a missão.
  2. Credita automaticamente o XP da tabela no contador da ficha.
  3. Estampa `XP Pago: <valor>` na linha da missão no diário.
  4. Recalcula se o total de XP atinge o novo nível; se sim, incrementa nível e disponibiliza pontos.

---

## 2. Engine Payload Contract (`lazy_turn.py prepare`)

O payload gerado na etapa de preparação é estendido com dois nós canônicos:

### 2.1 Contexto de Missões (`step_1_quest_context`)
Injetado sob `step_1_quest_context`:
```json
{
  "active_quests": [
    {
      "id": "Q1",
      "title": "O Trono de Pedra-Negra",
      "type": "MAIN",
      "phase": "Investigação",
      "contractor": "Conselho dos Lordes",
      "clock": "Conspiração",
      "clock_status": "ACTIVE",
      "clock_progress": "3/4",
      "clock_critical": true,
      "pending_objectives": [
        "Obter a lealdade da guarnição",
        "Desmascarar o traidor na corte"
      ],
      "reward": "150 XP"
    }
  ],
  "quest_pressure_mandate": "ALERTA CRÍTICO: O relógio 'Conspiração' está a 1 passo da ruptura (3/4). A cena presente DEVE exercer pressão extrema sobre a missão 'O Trono de Pedra-Negra'."
}
```

### 2.2 Resumo de Progressão do Protagonista
Injetado sob `step_2_engine_state.protagonist.progression`:
```json
{
  "level": 2,
  "xp": 410,
  "next_threshold": 500,
  "attribute_points": 1,
  "ability_points": 0,
  "scale_guidance": "Protagonista Nível 2: Calibre a escala de oponentes e atrito para desafios moderados condizentes com um herói em ascensão."
}
```

---

## 3. Reviewer Audit Issues Contract (`council/reviewer.py`)

Novos tipos de inconformidade detectados pela auditoria de integridade:

| Issue Type | Severidade | Gatilho de Detecção |
| :--- | :---: | :--- |
| `QUEST_WITHOUT_OBJECTIVES` | `MEDIUM` | Missão cadastrada sem nenhum objetivo em checkbox aninhado. |
| `QUEST_STALE` | `LOW` | Missão com status `ACTIVE` sem progresso registrado há mais de 10 turnos. |
| `QUEST_CLOCK_LINK_BROKEN` | `HIGH` | Campo `Relógio:` aponta para um nome ausente em `### Relógios de Ameaça & Prazos`. |
| `QUEST_OVERDUE` | `HIGH` | Relógio vinculado atingiu status `BREACHED` e a missão permanece com status `ACTIVE`. |
| `QUEST_REWARD_PAID_TWICE` | `CRITICAL` | Tentativa de creditar XP em missão que já contém carimbo de `XP Pago`. |
| `XP_MISMATCH` | `HIGH` | Divergência entre o log histórico de créditos de XP no diário e o total acumulado na ficha. |
