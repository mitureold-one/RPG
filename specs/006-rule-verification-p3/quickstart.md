# Quickstart & Validation Guide: P3 Transformação de Regra em Verificação

**Feature**: `rule-verification-p3`  
**Status**: Ready  
**Created**: 2026-10-21  
**Target Backlog Phase**: P3 (Reviewer Lints, Typed Overrides & Boundary Testing)

---

## 1. Pré-Requisitos e Ambiente

* Python 3.10+ instalado no ambiente local.
* Terminal PowerShell ou Bash posicionado na raiz do repositório (`C:\Users\Konor\Documents\RPGPRO`).
* Nenhuma biblioteca externa necessária (apenas a biblioteca padrão do Python).

---

## 2. Cenários de Validação Rápida

### Cenário 1: Validação de Lints de Prosa no Reviewer

1. **Executar Auditoria de Campanha**:
   ```bash
   python lazy_turn.py review --campaign dinastia_cinzas
   ```
2. **Resultado Esperado**:
   - O comando roda com sucesso e retorna `ssot_status: CLEAN` ou lista de issues.
   - Nenhuma exceção de runtime é levantada pelo motor.

3. **Teste de Detecção de Violações (Prosa Suja)**:
   - Inserir temporariamente em um turno de teste:
     - Um emoji (ex.: `🔥`).
     - Uma linha teatral (ex.: `[Comandante]: Atenção às muralhas!`).
     - Um fechamento clichê (ex.: `O que você faz?`).
   - Executar `python lazy_turn.py review --campaign <campanha_teste>`.
   - **Resultado Esperado**:
     - Detecção de `EMOJI_DETECTED` apontando o emoji.
     - Detecção de `SCRIPT_FORMAT_DETECTED` apontando a linha teatral.
     - Detecção de `FOURTH_WALL_QUESTION` apontando a fórmula clichê.

---

### Cenário 2: Validação de Overrides Tipados em `regras.md`

1. **Inspecionar Bloco de Overrides**:
   - Abrir qualquer `campaigns/<id>/regras.md` e verificar o bloco `overrides:`.
   - Executar preparação de turno:
   ```bash
   python lazy_turn.py prepare --campaign dinastia_cinzas --action "Avaliar defesas" --no-roll --json
   ```
2. **Resultado Esperado**:
   - O payload JSON retornado contém sob `step_1_gm_arbitration` a lista estruturada `overrides` com atributos `id`, `type`, `target`, `value` e `condition`.

---

### Cenário 3: Execução da Suíte Completa de Testes de Fronteira

1. **Executar Testes Automatizados**:
   ```bash
   python -m unittest discover tests
   ```
2. **Resultado Esperado**:
   - Todos os testes de contrato de CLI passam (`test_cli_contracts.py`).
   - Os novos testes de fronteira executam com sucesso:
     - `test_boundary_no_diegetic_leaks_in_skills`: Zero substantivos de campanhas presentes nas skills.
     - `test_boundary_cli_docs_contract`: 100% dos comandos nos docs correspondem ao CLI.
     - `test_boundary_prepare_payload_snapshot`: O payload de `prepare` bate estritamente com o snapshot congelado.
