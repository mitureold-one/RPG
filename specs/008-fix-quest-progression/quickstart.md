# Quickstart & Verification Gate: 008 — Remediação de Integridade

**Feature**: `fix-quest-progression`  
**Status**: Ready for Verification  
**Created**: 2026-10-22  
**Context**: Roteiro de verificação ponta a ponta baseado no gate de aceite de 8 passos do relatório de QA.

---

## Pré-requisitos & Ambiente

* Python 3.10+ (Standard Library).
* Shell PowerShell ou Bash no diretório raiz do repositório `RPGPRO`.

---

## Gate de Aceite: Roteiro de 8 Passos

### Passo 1: Execução da Suíte Completa de Testes
Executar a suíte em ambiente sandbox local:
```bash
python -m unittest discover tests
```
* **Critério de Sucesso**: Todos os testes executam sem exceções de ACL (`PermissionError`) e sem falhas.

---

### Passo 2: Criação de Campanha e Adição Monotônica de Missões
Criar campanha temporária de testes:
```bash
python lazy_turn.py init-campaign --campaign _qa_gate --title "Campanha de Teste QA" --protagonist "Aveline"
```

Adicionar duas missões sucessivas:
```bash
python lazy_turn.py quest --campaign _qa_gate --add "O Trono de Pedra-Negra" --type main --objective "Encontrar o selo"
python lazy_turn.py quest --campaign _qa_gate --add "A Forja Ancestral" --type side --objective "Coletar minério"
```

Listar via JSON:
```bash
python lazy_turn.py quest --campaign _qa_gate --list --json
```
* **Critério de Sucesso**: 
  - A primeira missão é `Q1` e a segunda é `Q2`.
  - O arquivo `diario.md` exibe `* **[Q1] [MAIN] O Trono de Pedra-Negra**` no topo e `* **[Q2] [SIDE] A Forja Ancestral**` abaixo.
  - Não há placeholders `{{NOME_MISSAO_PRINCIPAL}}` corrompidos no diário.

---

### Passo 3: Marcação de Objetivo com Checkbox
Avançar objetivo da missão `Q1`:
```bash
python lazy_turn.py quest --campaign _qa_gate --check "Q1:1"
```
* **Critério de Sucesso**:
  - O objetivo 1 de `Q1` passa para `[x] Encontrar o selo`.
  - `Último Progresso` é atualizado.

---

### Passo 4: Conclusão via Commit sem Erro de Escopo (P0-1)
Executar o commit do turno concluindo a missão `Q1`:
```bash
python lazy_turn.py commit --campaign _qa_gate --summary "Aveline recupera o selo e entrega ao conselho." --quest-complete "Q1"
```
* **Critério de Sucesso**:
  - O comando executa sem `UnboundLocalError`.
  - A missão `Q1` recebe `Status: COMPLETED` e `XP Pago: 150`.
  - A ficha `ficha.md` recebe 150 XP acumulados.
  - O turno no diário arquiva os vitais e o resumo factual.

---

### Passo 5: Teste de Idempotência e Auditoria de Tentativa Duplicada
Tentar concluir novamente a mesma missão `Q1` em outro commit:
```bash
python lazy_turn.py commit --campaign _qa_gate --summary "Aveline revisita o conselho." --quest-complete "Q1"
```
* **Critério de Sucesso**:
  - O motor bloqueia o crédito duplo de XP.
  - Nenhum XP adicional é gravado na ficha.
  - A auditoria reporta o aviso/issue de duplicidade impedida.

---

### Passo 6: Desbloqueio, Abandono e Registro de Evidência
Testar os novos comandos de ciclo de vida na missão `Q2`:
```bash
# Bloquear
python lazy_turn.py quest --campaign _qa_gate --block "Q2" --reason "Minas desabadas"

# Desbloquear
python lazy_turn.py quest --campaign _qa_gate --unblock "Q2"

# Concluir com evidência diegética
python lazy_turn.py quest --campaign _qa_gate --complete "Q2" --evidence "Minério entregue ao ferreiro com recibo assinado"
```
* **Critério de Sucesso**:
  - O status transiciona `BLOCKED` -> `ACTIVE` -> `COMPLETED`.
  - A evidência é registrada no arquivo `diario.md`.

---

### Passo 7: Concessão Avulsa com Ledger e Auditoria de Integridade
Testar o subcomando `progress --award` e auditar integridade:
```bash
python lazy_turn.py progress --campaign _qa_gate --award 40 --reason "Relógio de conspiração desarmado"
python lazy_turn.py review --campaign _qa_gate
```
* **Critério de Sucesso**:
  - A linha `* **[XP] +40 XP** (Relógio de conspiração desarmado) | Turno ...` consta em `diario.md`.
  - O comando `review` valida a coerência exata (`XP_MISMATCH` passa sem alertas).

---

### Passo 8: Regressão nas Campanhas Reais e Limpeza
Executar auditoria nas campanhas oficiais e remover o scratch de teste:
```bash
python lazy_turn.py review --campaign sombra_da_coroa
python lazy_turn.py review --campaign dinastia_cinzas
python lazy_turn.py review --campaign o_veo_de_ignis
```
Limpeza da campanha temporária:
```powershell
Remove-Item -Recurse -Force campaigns/_qa_gate
```
* **Critério de Sucesso**: Nenhuma nova violação é introduzida nas campanhas ativas.
