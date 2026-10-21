# Phase 1 CLI Contract: Showrunner & Narrative Engine Commands

**Feature**: `fix-cli-and-runtime-p0`  
**Status**: Completed  
**Created**: 2026-10-21  

---

## 1. Showrunner CLI Interface

### 1.1 Fila de Cenas (`plan`)

```bash
# Listar fila atual de cenas e status do ritmo
python lazy_turn.py plan --campaign <id> --list

# Agendar uma nova cena futura
python lazy_turn.py plan --campaign <id> --add "<Titulo>" --scene-type <tipo> [--actors "<Personagens>"]

# Marcar uma cena como concluída pelo índice numérico
python lazy_turn.py plan --campaign <id> --complete <indice_inteiro>

# Adicionar um marco futuro do arco
python lazy_turn.py plan --campaign <id> --milestone "<Descricao do Marco>"
```

*Restrições de Validação*:
- `--scene-type` deve ser um dos 10 valores canônicos.
- `--complete` deve receber um inteiro (índice 0-based da lista de pendências).
- Não utilizar flags inexistentes como `--add-scene`, `--type`, `--trigger` ou `--complete-scene`.

---

### 1.2 Relógios Narrativos de Facção (`clock`)

```bash
# Listar relógios ativos e rompidos
python lazy_turn.py clock --campaign <id> --list

# Cadastrar novo relógio ativo com gatilho de ruptura
python lazy_turn.py clock --campaign <id> --add "<Nome da Ameaca>" --max <4|6|8> --trigger "<Condicao de Ruptura>"

# Avançar passos de um relógio
python lazy_turn.py clock --campaign <id> --advance "<Nome>" --steps <passos_int>

# Desarmar ou resolver um relógio
python lazy_turn.py clock --campaign <id> --resolve "<Nome>"
```

*Restrições de Validação*:
- `--steps` deve ser um inteiro positivo (padrão: 1).
- Não utilizar sintaxe combinada como `--advance "Nome:passos"`.

---

### 1.3 Transições Atômicas de Arco (`arc`)

```bash
python lazy_turn.py arc --campaign <id> \
  --title "Arco N: <Nome do Novo Arco>" \
  --question "<Pergunta Dramatica Central>" \
  --stage "<Apresentacao|Conflito|Climax|Resolucao>" \
  --scene-name "Cena 1: <Nome da Cena Inicial>" \
  --date "<Data e Hora Canonica>" \
  --location "<Novo Local Canonico>" \
  --present "<Personagens Presentes>" \
  --resolve-clocks \
  --milestone "<Sintese do Marco alcancado no Arco anterior>"
```

*Restrições de Validação*:
- `--resolve-clocks` é uma flag booleana pura (sem argumentos de valor).

---

## 2. Narrative Engine Scene Type Contract (`prepare`)

```bash
python lazy_turn.py prepare --campaign <id> --action "<Acao do Jogador>" --scene-type <tipo>
```

*Saída Esperada no JSON (`step_3_writer_mandate`)*:
- Deve conter os campos obrigatórios `scene_type`, `why_this_structure`, `structure_and_tone` e `dialogue_and_style`.
- Nenhum dos 10 tipos válidos pode retornar o fallback silencioso de `standard` a menos que `standard` tenha sido o tipo solicitado.
