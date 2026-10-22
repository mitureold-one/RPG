# Implementation Plan: P3 Transformação de Regra em Verificação

**Feature**: `rule-verification-p3`  
**Status**: Ready for Implementation  
**Created**: 2026-10-21  
**Target Backlog Phase**: P3 (Reviewer Lints, Typed Overrides & Boundary Testing)

---

## 1. Plan Overview & Objectives

Este plano de implementação formaliza as entregas da fase **P3** definidas em `DECISOES_ARQUITETURA.md` e na especificação de requisitos:
1. **Lints Determinísticos de Prosa no Reviewer (`council/reviewer.py`)**: Implementar verificadores rígidos baseados em regex para erradicar emojis (`EMOJI_DETECTED`), notação de roteiro teatral (`SCRIPT_FORMAT_DETECTED`) e perguntas clichês de quarta parede (`FOURTH_WALL_QUESTION`).
2. **Bloco de Overrides Tipados em `regras.md`**: Padronizar os modificadores de mecânica em formato estruturado legível por máquina (`id`, `type`, `target`, `value`, `condition`), consumido pelo motor e refletido no payload de `lazy_turn.py prepare`.
3. **Suíte de Testes de Fronteira**:
   - **Vazamento Diegético**: Teste automatizado validando que as skills universais não contêm substantivos ou entidades das 3 campanhas ativas.
   - **Contrato de CLI vs Documentação**: Teste comparando a interface real do argparse (`lazy_turn.build_cli()`) com exemplos e referências nos documentos Markdown.
   - **Snapshot de Payload**: Teste comparando a estrutura gerada por `lazy_turn.py prepare` com um snapshot congelado.

---

## 2. Technical Context & Constitution Gates

* **Biblioteca Padrão Exclusiva**: Todas as expressões regulares de emojis, parsing de overrides e testes utilizam exclusivamente a standard library do Python (`re`, `json`, `pathlib`, `unittest`, `argparse`, `shlex`).
* **Soberania do SSOT**: `regras.md` permanece o único ponto de declaração de regras da campanha, combinando leis diegéticas em prosa com o bloco tipado `yaml` de mecânicas.
* **Fail-Fast & Zero Falso Positivo**: As regexes de lint são desenhadas para operar com precisão sobre os resumos de turnos e trechos narrativos recentes sem interferir na metainformação técnica do diário.

---

## 3. Work Breakdown Structure

### Phase 1: Lints de Prosa no Reviewer (`council/reviewer.py`)
- [ ] **Task 1.1**: Implementar a função utilitária `check_prose_lints(text: str, context_label: str)` com as três regras de lint:
  - Regex Unicode para emojis (`EMOJI_DETECTED`).
  - Regex multiline para formato teatral `[Nome]:` e `Nome: "..."` (`SCRIPT_FORMAT_DETECTED`).
  - Regex para perguntas clichês de encerramento (`FOURTH_WALL_QUESTION`).
- [ ] **Task 1.2**: Integrar `check_prose_lints` no fluxo de auditoria de `cmd_review` em `council/reviewer.py`, inspecionando resumos de turnos recentes e trechos narrativos do diário.
- [ ] **Task 1.3**: Criar testes unitários focados validando a detecção precisa de cada um dos três lints e a ausência de falsos positivos em prosa normal com travessão (`—`).

### Phase 2: Overrides Tipados em `regras.md` & Engine
- [ ] **Task 2.1**: Implementar parser robusto do bloco `yaml` de `regras.md` em `council/helpers.py` / `council/ssot.py` para extrair a lista estruturada de `overrides`.
- [ ] **Task 2.2**: Atualizar `lazy_turn.py prepare` para injetar os overrides tipados sob `step_1_gm_arbitration.overrides`.
- [ ] **Task 2.3**: Atualizar o template canônico `templates/regras.template.md` com o esquema estruturado de `overrides`.
- [ ] **Task 2.4**: Atualizar as 3 campanhas ativas (`campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md`, `campaigns/perpetuos_terra_incognita/regras.md`) para o novo esquema estruturado de `overrides`.

### Phase 3: Suíte de Testes de Fronteira (`tests/`)
- [ ] **Task 3.1**: Implementar teste de **Vazamento Diegético**:
  - Extrair nomes de protagonistas, NPCs registrados e entidades diegéticas das três campanhas.
  - Varre os arquivos em `.agents/skills/` e diretórios de skills globais.
  - Assegurar zero ocorrências desses substantivos nas skills.
- [ ] **Task 3.2**: Implementar teste de **Contrato de CLI vs Documentação**:
  - Validar comandos `python lazy_turn.py ...` documentados em `README.md`, `DECISOES_ARQUITETURA.md` e nos `SKILL.md`.
  - Garantir que todos os comandos executem parse seco com sucesso contra o `lazy_turn.build_cli()`.
- [ ] **Task 3.3**: Implementar teste de **Snapshot do Payload de Preparação**:
  - Executar `lazy_turn.cmd_prepare` com parâmetros determinísticos (`--no-roll`).
  - Validar a conformidade da estrutura de chaves e tipos com o snapshot canônico congelado.
- [ ] **Task 3.4**: Executar a suíte de testes completa (`python -m unittest discover tests`) garantindo 100% de sucesso.

---

## 4. Acceptance Criteria Checklist

- [ ] `council/reviewer.py` detecta emojis (`EMOJI_DETECTED`), formato teatral (`SCRIPT_FORMAT_DETECTED`) e perguntas clichês de quarta parede (`FOURTH_WALL_QUESTION`).
- [ ] O bloco `overrides:` em `regras.md` é estruturado, tipado e legível por máquina em todas as campanhas e templates.
- [ ] O payload emitido por `lazy_turn.py prepare` expõe a lista de `overrides` tipados em `step_1_gm_arbitration`.
- [ ] Teste automatizado garante que nenhuma skill universal contém termos diegéticos das 3 campanhas ativas.
- [ ] Teste automatizado garante paridade absoluta entre a CLI do `lazy_turn.py` e os comandos citados na documentação.
- [ ] Teste automatizado valida a estabilidade estrutural do snapshot de saída do `prepare`.
- [ ] 100% dos testes unitários e de contrato executam com sucesso.
