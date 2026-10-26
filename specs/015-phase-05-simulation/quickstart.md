# Quickstart & Verification Guide: 015 — Fase 05: Simulação de Mundo por Tempo

**Feature:** `phase-05-simulation`
**Status:** Guia reproduzível (verificado na Fase 05, homologada em `EX-0044`)
**Created:** 2026-10-26
**Spec:** [`spec.md`](spec.md) · **Plan:** [`plan.md`](plan.md) · **Data model:** [`data-model.md`](data-model.md)

---

## 1. Pré-requisitos

Execute a partir da raiz do repositório, no PowerShell. Os subcomandos `world-tick`, `schedule` e `queue` são entregues pela Fase 05.

```powershell
$env:PYTHONPATH='.'
$env:RPGPRO_CAMPAIGNS_DIR = "$env:TEMP\rpgpro_phase05\campaigns"
$camp = "$env:RPGPRO_CAMPAIGNS_DIR\sim_lab"
New-Item -ItemType Directory -Force -Path $env:RPGPRO_CAMPAIGNS_DIR | Out-Null
```

---

## 2. Criar a campanha de teste

```powershell
python lazy_turn.py init-campaign --campaign sim_lab --title "Laboratório de Simulação" --protagonist "Aemon" --date "01/10/300, 10:00" --location "Posto Avançado"
```

Saída esperada: JSON com `status: "ok"`, `campaign: "sim_lab"` e os cinco arquivos criados. O template já nasce com o relógio `Ameaça Iminente` em `0/4`; os arquivos `diario.md`, `ficha.md`, `npcs.md`, `mundo.md`, `regras.md` e `events/` passam a existir.

---

## 3. Cadastrar relógio e plano

```powershell
python lazy_turn.py clock --campaign sim_lab --add "Pressão da Guilda" --max 4 --trigger "A Guilda fecha o cerco"
python lazy_turn.py clock --campaign sim_lab --advance "Pressão da Guilda" --steps 3
python lazy_turn.py plan --campaign sim_lab --add "Emboscada na Estrada" --scene-type interlude --actors "Rival Inicial"
```

Saída esperada: `Pressão da Guilda` em `3/4 [ACTIVE]`; a fila de cenas mostra `Emboscada na Estrada` como `[ ]`. O `plan` registra a cena no diário, não cria um `world.scheduled`; o agendamento formal é feito no passo 6.

---

## 4. Rodar o primeiro tick de sete dias

```powershell
python lazy_turn.py world-tick --campaign sim_lab --minutes 10080 --trigger time --json
```

Saída esperada (resumo): `from = "01/10/300, 10:00"`, `to = "08/10/300, 10:00"`, `elapsed_minutes = 10080`, `selected` com os dois relógios ativos, `deferred` vazio e `budget_limit = 8`. `status = "ok"` e `queue_hash` é o hash previsto da fila.

```powershell
Select-String -Path "$camp\diario.md" -Pattern "Data & Local","Simulação de Mundo","Tick"
Get-Content "$camp\queue.json"
```

O diário deve mostrar `Data & Local: 08/10/300, 10:00` e uma seção `### Simulação de Mundo` com a linha do tick. `queue.json` deve ter `schema_version: 1`, `last_seq` maior que zero, `last_tick.to_game_time = "08/10/300, 10:00"` e as listas `pending`, `deferred`, `failed` e `scheduled`. Os dois relógios ativos (`Ameaça Iminente` e `Pressão da Guilda`) chegam a `4/4 [BREACHED]` com a cadência diária; um relógio `RESOLVED` não avançaria.

---

## 5. Rodar com orçamento 1 e drenar

Agende duas cenas para o mesmo instante futuro, para que o próximo salto tenha mais de um item devido. Para `scene_due`, o payload precisa de `beat`; sem ele a resolução falha com `scene_payload_invalid:missing_beat`.

```powershell
python lazy_turn.py schedule --campaign sim_lab --at "15/10/300, 10:00" --kind scene_due --entity "Emboscada na Estrada" --payload "beat=Emboscada na Estrada" --priority 60 --json
python lazy_turn.py schedule --campaign sim_lab --at "15/10/300, 10:00" --kind scene_due --entity "Cerco ao Posto" --payload "beat=Cerco ao Posto" --priority 55 --json
```

```powershell
python lazy_turn.py world-tick --campaign sim_lab --minutes 10080 --budget 1 --trigger time --json
```

Saída esperada: `from = "08/10/300, 10:00"`, `to = "15/10/300, 10:00"`, `len(selected) == 1`, `len(deferred) == 1` e `budget_limit = 1`. O log recebe um `world.work_completed` e um `world.work_deferred` com `reason = "budget_exhausted"`; a cena concluída permanece no log.

```powershell
python lazy_turn.py world-tick --campaign sim_lab --minutes 1440 --trigger time --json
```

Saída esperada: `from = "15/10/300, 10:00"`, `to = "16/10/300, 10:00"`, `len(selected) == 1` e `deferred` vazio; nenhum `world.work_completed` anterior é repetido ou apagado.

---

## 6. Agendar, rodar `--dry-run` e consultar a fila

```powershell
python lazy_turn.py schedule --campaign sim_lab --at "23/10/300, 10:00" --kind scene_due --entity "Chegada do Mensageiro" --payload "beat=Chegada do Mensageiro" --priority 60 --json
```

O agendamento válido grava `world.scheduled` e aparece em `queue.json.scheduled`. Prove que o `--dry-run` não escreve:

```powershell
$before = (python lazy_turn.py queue --campaign sim_lab --json | ConvertFrom-Json).last_seq
python lazy_turn.py world-tick --campaign sim_lab --minutes 10080 --trigger time --dry-run --json
$after = (python lazy_turn.py queue --campaign sim_lab --json | ConvertFrom-Json).last_seq
if ($before -ne $after) { throw "dry-run alterou last_seq" }
```

Saída esperada: o relatório mostra `events_planned > 0`, o item agendado como selecionado para `23/10/300, 10:00`, `dry_run = true` e `last_seq` idêntico antes e depois; nenhum evento, linha de diário ou alteração de `queue.json` é gravado.

```powershell
python lazy_turn.py queue --campaign sim_lab
python lazy_turn.py queue --campaign sim_lab --json
```

Saída esperada: `Chegada do Mensageiro` em `scheduled`, com `due_game_time = "23/10/300, 10:00"`; `last_tick.to_game_time = "16/10/300, 10:00"`; nenhum trabalho concluído duplicado. Rode `python lazy_turn.py rebuild --campaign sim_lab --force` e confira o mesmo `hash`.

---

## 7. Verificação final

```powershell
python -m unittest tests.test_phase05_world_tick tests.test_phase05_policies tests.test_architecture_boundaries tests.test_boundary_contracts -v
python -m unittest discover -s tests -p "test_*.py"
```

Critérios observáveis:

| Verificação | Resultado esperado |
| :--- | :--- |
| C11 salto temporal | `+10080` de `01/10/300, 10:00` chega a `08/10/300, 10:00`; relógios saturam em `BREACHED` |
| C12 causa off-screen | todo trabalho tem `correlation_id = tick_id` e `causation_id` do `world.ticked` ou `world.scheduled` |
| C13 orçamento | `--budget 1` conclui um item, adia os demais e não apaga o concluído |
| C14 retomada | reexecutar o mesmo tick não adiciona eventos; `status = "idempotent"` |
| C15 calendário | `+30d` e `+1a` consistentes; agendamento dispara uma única vez em `due_at_sort` |
| C16 profundidade seletiva | entidade sem cadência vencida não gera evento; `silent_entities` no relatório |
| C17 retry/proposta | falha cresce `attempts`, esgota em `permanent`; `schedule` inválido gera `proposal.rejected` sem mutação |
| Regressão | 282 testes verdes no total; snapshot do `prepare` e rebuild C3 intactos |
| Fronteiras | módulos novos `< 300` linhas; políticas sem I/O; `lazy_turn.py < 200` |

Se algum comando `world-tick` devolver erro de campanha, calendário ou configuração, o esperado é erro tipado e nenhuma escrita — nunca um tick vazio silencioso.

