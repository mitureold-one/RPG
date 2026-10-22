# Quickstart & Validation Guide: Sistema de Missões e Progressão (XP)

**Feature**: `quest-and-progression`  
**Date**: 2026-10-22  
**Status**: Ready for Validation  

---

## 1. Pré-Requisitos e Setup

Os testes podem ser executados diretamente em qualquer campanha existente ou em uma campanha temporária de testes:

```bash
# Validar saúde inicial da suíte de testes
python -m unittest discover -s tests
```

---

## 2. Cenários Ponta-a-Ponta para Validação

### Cenário 1: Cadastro e Listagem de Missão
**Objetivo**: Validar criação atômica e parsing estruturado de missões.

```bash
# 1. Cadastrar nova missão principal com objetivo inicial
python lazy_turn.py quest --campaign dinastia_cinzas \
    --add "Resgatar o Emissário de Ferro" \
    --type main \
    --objective "Localizar a cela subterrânea" \
    --clock "Golpe da Guarda de Malakor" \
    --reward "150 XP"

# 2. Adicionar segundo objetivo
python lazy_turn.py quest --campaign dinastia_cinzas \
    --objective "Q1: Escoltá-lo com vida até os portões"

# 3. Listar missões em formato legível e em JSON
python lazy_turn.py quest --campaign dinastia_cinzas --list
python lazy_turn.py quest --campaign dinastia_cinzas --list --json
```
*Resultado Esperado*: `diario.md` ganha a seção `### Missões & Objetivos` com a missão cadastrada e dois checkboxes `[ ]`.

---

### Cenário 2: Avanço de Objetivo e Preparação com Pressão
**Objetivo**: Validar marcação de checkbox e injeção do contexto no `prepare`.

```bash
# 1. Marcar o primeiro objetivo como concluído
python lazy_turn.py quest --campaign dinastia_cinzas --check "Q1:1"

# 2. Executar prepare determinístico
python lazy_turn.py prepare --campaign dinastia_cinzas --no-roll
```
*Resultado Esperado*:
- `diario.md` exibe `* [x] Localizar a cela subterrânea`.
- O payload JSON de saída exibe em `step_1_quest_context` a missão ativa, o objetivo pendente restante e o status do relógio vinculado.

---

### Cenário 3: Conclusão via Commit, Idempotência e Concessão de XP
**Objetivo**: Validar crédito automático de XP, marcação de `XP Pago` e subida de nível.

```bash
# 1. Executar commit concluindo a missão
python lazy_turn.py commit --campaign dinastia_cinzas \
    --summary "Com a chave do capitão, o emissário é retirado das masmorras e guiado pelas sombras até a saída segura." \
    --quest-complete "Q1"

# 2. Inspecionar diário e ficha
python lazy_turn.py progress --campaign dinastia_cinzas --list
```
*Resultado Esperado*:
- A linha da missão em `diario.md` exibe `Status: COMPLETED` e carimbo `XP Pago: 150`.
- A ficha do personagem passa a exibir `Experiência (XP): 150`.
- Tentativas posteriores de rodar commit com a mesma missão não adicionam mais XP.

---

### Cenário 4: Blindagem contra Colisão com Vitais e Atributos
**Objetivo**: Garantir que XP não contamine o snapshot de vitais nem a lista de atributos.

```bash
# Executar teste automatizado de integridade de dados da ficha
python -m unittest tests.test_progression_ssot
```
*Resultado Esperado*:
- `ficha["vitals"]` não contém a chave `xp` nem `experiência`.
- `ficha["stats"]` não contém a chave `xp`.
- Subcomando `commit --cost "stamina: 2"` não interfere em XP.

---

### Cenário 5: Ruptura de Relógio Vinculado e Auditoria (`QUEST_OVERDUE`)
**Objetivo**: Garantir que a ruptura de um relógio gere o lint esperado sem corrupção silenciosa da missão.

```bash
# 1. Avançar relógio vinculado até romper (4/4)
python lazy_turn.py clock --campaign dinastia_cinzas --advance "Golpe da Guarda de Malakor" --steps 2

# 2. Executar auditoria
python lazy_turn.py review --campaign dinastia_cinzas
```
*Resultado Esperado*:
- O relatório acusa `CLOCK_BREACHED` e `QUEST_OVERDUE`.
- O status da missão em `diario.md` permanece intacto até que o GM/jogador determine o desfecho via `--quest-fail` ou transição de contingência.

---

### Cenário 6: Gasto de Pontos de Build (`progress`)
**Objetivo**: Testar evolução de atributos e aquisição de habilidades.

```bash
# 1. Conceder XP suficiente para nível 2 (se necessário)
python lazy_turn.py progress --campaign dinastia_cinzas --award "quest_main:150"

# 2. Gastar ponto de atributo
python lazy_turn.py progress --campaign dinastia_cinzas --spend-attr FOR

# 3. Gastar ponto de habilidade com contexto diegético
python lazy_turn.py progress --campaign dinastia_cinzas \
    --spend-ability "Golpe da Cinza: +2 em combate contra guardas rebeldes" \
    --training "Três horas de treino pesado nas ruínas do pátio leste."
```
*Resultado Esperado*:
- Atributo FOR incrementado em +1 em `ficha.md`.
- Habilidade registrada em `ficha.md`.
- Pontos disponíveis decrementados correspondentemente.
