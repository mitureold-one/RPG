# Quickstart & Verification Guide: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature**: `factions-and-reputation`  
**Status**: Ready for Verification  
**Created**: 2026-10-22  
**Context**: Gate de validação prática ponta a ponta executável em campanha isolada de teste.

---

## 1. Pré-Requisitos

Executar a suíte de regressão completa para confirmar o baseline 100% verde antes de iniciar:

```bash
python -m unittest discover tests
```
*Critério de Aceite:* 36 testes executados e aprovados sem erros.

---

## 2. Cenário de Validação Ponta a Ponta (8 Passos)

Para não mutar as campanhas reais do RPGPRO, os testes manuais e de homologação podem ser executados com uma campanha descartável `_qa_factions`:

```bash
python lazy_turn.py init-campaign --campaign _qa_factions --title "Crônica de Teste de Facções" --protagonist "Kaelen"
```

---

### Passo 1: Cadastro de Facção com Atributos Estruturados
Cadastrar uma facção militar de elite em `mundo.md`:

```bash
python lazy_turn.py faction --campaign _qa_factions --add "Ordem da Lâmina Rubra" --power 4 --scale regional --clock "Cerco da Fortaleza" --desc "Guerreiros mercenários com lealdade ao ouro."
```

*Verificação*:
- O arquivo `campaigns/_qa_factions/mundo.md` exibe a linha formatada com tag, poder 4, escala regional e relógio vinculado.

---

### Passo 2: Listagem e Consulta JSON de Facções
Verificar a exposição via CLI:

```bash
python lazy_turn.py faction --campaign _qa_factions --list --json
```

*Verificação*:
- Retorna JSON com a lista de facções, poder 4, relógio vinculado e a reputação inicial do protagonista (0 / Neutro).

---

### Passo 3: Mutação Numérica de Reputação e Saldo de Favores
Ajustar a reputação do protagonista com a nova ordem:

```bash
python lazy_turn.py faction --campaign _qa_factions --rep "Ordem da Lâmina Rubra:+2" --reason "Entrega do pagamento em ouro aos comandantes"
python lazy_turn.py faction --campaign _qa_factions --favor "Ordem da Lâmina Rubra:+1" --reason "Pacto formal de lealdade"
```

*Verificação*:
- `campaigns/_qa_factions/ficha.md` exibe: `* **[ORDEM_LAMINA_RUBRA] Ordem da Lâmina Rubra:** +2 (Aliado) | Favores: 1 | Débitos: 0`.
- `campaigns/_qa_factions/diario.md` registra a entrada sob `### Registro de Reputação & Facções`.

---

### Passo 4: Injeção de Contexto Político no `prepare`
Verificar se a arbitragem de cena recebe os modificadores sociais e diretivas:

```bash
python lazy_turn.py prepare --campaign _qa_factions --action "Negociar reforços com o Capitão da Lâmina Rubra" --no-roll
```

*Verificação*:
- O payload JSON contém `step_1_faction_context` indicando a Ordem como `Aliado` (+2), aplicando bônus na DC (`social_dc_mod: -2`) e diretiva de cooperação ativa.

---

### Passo 5: Conclusão de Missão com Contratante e Ganho Automático
Cadastrar uma missão patrocinada pela facção e concluí-la via commit:

```bash
python lazy_turn.py quest --campaign _qa_factions --add "Expurgar o Posto Avançado" --type side --contractor "Ordem da Lâmina Rubra" --objective "Eliminar os batedores inimigos"
python lazy_turn.py commit --campaign _qa_factions --summary "Kaelen limpa o posto avançado e apresenta as insígnias dos batedores." --quest-complete "Q1" --force
```

*Verificação*:
- A reputação com a Ordem avança automaticamente de `+2` para `+3` (Venerado).
- Favores aumentam para 2.
- A linha do turno em `diario.md` ou ledger registra a concessão decorrente de contrato cumprido.

---

### Passo 6: Turno de Facções Off-Screen (`faction --tick`)
Simular a passagem de tempo em bastidores:

```bash
python lazy_turn.py clock --campaign _qa_factions --add "Cerco da Fortaleza" --max 4
python lazy_turn.py faction --campaign _qa_factions --tick
```

*Verificação*:
- O relógio "Cerco da Fortaleza", associado à facção de Poder 4, avança de 0/4 para 1/4 [ACTIVE].
- Um resumo estruturado relata a movimentação nos bastidores.

---

### Passo 7: Validação dos Novos Lints de Integridade no Revisor
Provocar inconsistências deliberadas para verificar o disparo dos linters:

1. Inserir em `ficha.md` uma reputação com facção inexistente `[FACCAO_FANTASMA]`:
   - Executar `python lazy_turn.py review --campaign _qa_factions`
   - *Verificação:* O lint `FACTION_UNKNOWN` é disparado com severidade `HIGH`.
2. Adulterar manualmente o valor de reputação para `+1` na ficha sem lançamento correspondente no diário:
   - *Verificação:* O lint `FACTION_REP_MISMATCH` é disparado com severidade `HIGH`.
3. Associar um NPC em `npcs.md` a uma facção inexistente:
   - *Verificação:* O lint `FACTION_ORPHANED_NPC` é disparado com severidade `MEDIUM`.

---

### Passo 8: Limpeza e Encerramento
Remover a campanha descartável:

```bash
python -c "import shutil; shutil.rmtree('campaigns/_qa_factions', ignore_errors=True)"
```
