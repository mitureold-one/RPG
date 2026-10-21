# Quickstart & Verification Guide: P1 Deduplication & Cognitive Load Reduction

**Feature**: `eliminate-duplication-p1`  
**Status**: Ready for Verification  
**Created**: 2026-10-21  

---

## 1. Verificação da Linha do Roteador (`AGENTS.md`)

Execute o comando PowerShell para auditar a contagem de linhas e garantir ausência de regras de prosa estáticas:

```powershell
# 1. Contar linhas totais de AGENTS.md (deve ser <= 15)
$lines = (Get-Content AGENTS.md).Count
Write-Host "Total de linhas em AGENTS.md: $lines"
if ($lines -gt 15) { Write-Error "AGENTS.md ultrapassou o teto de 15 linhas!" }

# 2. Garantir que não há regras de formatação de prosa em AGENTS.md
Select-String -Path AGENTS.md -Pattern "travessão|script teatral|Linha 1 Obrigatória|4 Batidas"
# (Deve retornar ZERO resultados)
```

---

## 2. Verificação do Mandato Dinâmico de Prosa (`step_3_writer_mandate`)

Execute um turno com `prepare` e valide se o payload JSON contém o mandato estrutural de escrita esperado:

```powershell
# Executar prepare para cena interlude
python lazy_turn.py prepare --campaign imperio_valiria --action "Conselho de guerra" --scene-type interlude --no-roll

# Critério de Validação:
# O campo 'step_3_writer_mandate' retornado deve conter as diretrizes específicas de 'interlude'
# (protagonista ausente, foco em diálogos cruzados dos antagonistas, revelação de planos).
```

---

## 3. Verificação de SSOT no Módulo 3 (`references/3_campaign_crud_and_state.md`)

Certifique-se de que comandos operacionais de CLI não foram reintroduzidos no Módulo 3:

```powershell
# Buscar blocos de comandos de relógios e planos no Módulo 3
Select-String -Path .agents/skills/rpg-narrative-engine/references/3_campaign_crud_and_state.md -Pattern "python lazy_turn.py clock|python lazy_turn.py plan"
# (Deve retornar ZERO resultados - todo uso operacional pertence a rpg-showrunner)
```

---

## 4. Verificação da Escala de DC nas Campanhas

Certifique-se de que a escada genérica de DC foi removida das 3 campanhas ativas e do template:

```powershell
# Checar ocorrências de DC genérico em regras.md
Select-String -Path campaigns/*/regras.md, templates/regras.template.md -Pattern "DC 10 \(Ação Básica sob Pressão\)"
# (Deve retornar ZERO resultados)
```

---

## 5. Execução dos Testes Automatizados de Contrato

Execute a suíte de contratos atualizada para validar todas as regras do P1:

```powershell
python -m unittest tests/test_cli_contracts.py
```
*(Deve passar com 100% de sucesso).*
