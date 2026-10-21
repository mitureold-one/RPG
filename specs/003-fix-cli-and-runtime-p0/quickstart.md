# Quickstart & Verification Guide: P0 Runtime & CLI Fixes

**Feature**: `fix-cli-and-runtime-p0`  
**Status**: Ready for Verification  
**Created**: 2026-10-21  

---

## 1. Verificação da CLI do Showrunner (`plan`, `clock`, `arc`)

Execute os seguintes comandos para garantir que não ocorram erros de argumentos não reconhecidos (`argparse error`):

### 1.1 Teste do subcomando `plan`
```powershell
# 1. Listar fila
python lazy_turn.py plan --campaign imperio_valiria --list

# 2. Adicionar cena com as flags corretas
python lazy_turn.py plan --campaign imperio_valiria --add "Teste de Cena P0" --scene-type interlude --actors "Conselho"

# 3. Listar e verificar que foi cadastrada
python lazy_turn.py plan --campaign imperio_valiria --list

# 4. Concluir a cena recém-criada (usar o índice da lista)
python lazy_turn.py plan --campaign imperio_valiria --complete 0
```

### 1.2 Teste do subcomando `clock`
```powershell
# 1. Adicionar relógio
python lazy_turn.py clock --campaign imperio_valiria --add "Ameaca de Teste P0" --max 4 --trigger "Invasao"

# 2. Avançar passos
python lazy_turn.py clock --campaign imperio_valiria --advance "Ameaca de Teste P0" --steps 1

# 3. Resolver relógio
python lazy_turn.py clock --campaign imperio_valiria --resolve "Ameaca de Teste P0"
```

### 1.3 Teste do subcomando `arc`
```powershell
# Validar help e execução sem passar argumentos para --resolve-clocks
python lazy_turn.py arc --help
```

---

## 2. Verificação de Cobertura de Tipos de Cena em `prepare`

Execute `prepare` para cada um dos tipos de cena que eram órfãos e verifique que o mandato retornado é especializado:

```powershell
# 1. Prologue
python lazy_turn.py prepare --campaign imperio_valiria --action "Abertura da era" --scene-type prologue --no-roll

# 2. Epilogue
python lazy_turn.py prepare --campaign imperio_valiria --action "Rescaldo da guerra" --scene-type epilogue --no-roll

# 3. Post-credits
python lazy_turn.py prepare --campaign imperio_valiria --action "Ameaça nas sombras" --scene-type post_credits --no-roll
```

*Critério de Sucesso*:
O campo `"step_3_writer_mandate"` no JSON de saída para cada comando deve conter `"scene_type": "prologue"`, `"scene_type": "epilogue"` e `"scene_type": "post_credits"`, com as respectivas instruções de tom e enquadramento (e não as instruções de combate/ação de `standard`).

---

## 3. Verificação de Links Relativos e Desativação Automática

```powershell
# 1. Garantir que não há referências hardcoded de máquina em .agents/skills
Select-String -Path .agents/skills/rpg-narrative-engine/SKILL.md -Pattern "C:/Users/Konor"
Select-String -Path .agents/skills/rpg-showrunner/SKILL.md -Pattern "C:/Users/Konor"

# 2. Garantir que Showrunner não possui auto-ativação
Select-String -Path .agents/skills/rpg-showrunner/SKILL.md -Pattern "Ativa-se automaticamente"
```

*Critério de Sucesso*:
Zero ocorrências encontradas.
