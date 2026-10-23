# QA — Fase 01 (Fundação) + baseline R0/R0.5

**Commits auditados:** `cefe5ea` (Fase 01 e 01.5) → `d2f99bf` (HEAD, R0.5).
**Data:** 23 de Outubro de 2026.
**Método:** leitura do código novo (`contracts/`, `kernel/`, `application/`, `interfaces/`, `adapters/`, `temporal/`, `campaign/`), comparação AST do código extraído contra `cefe5ea`, regressão diferencial da CLI antiga × nova sobre cópias idênticas das fixtures, suíte completa, testes adversariais de calendário, schema, registry, runtime, lock e contenção de caminhos, e concorrência real de processos.

**Escopo interpretado:** “Fase 01” = fundação entregue em `EX-0001`/`EX-0002` mais o baseline de kernel `R0`/`R0.5` (`EX-0004`–`EX-0008`), que é o estado atual do HEAD e o que os agentes terminaram. Se o pedido se referia a outro recorte, este parecer precisa ser reescopado.

---

## Atualização pós-remediação — 23/10/2026

**Reverificado em:** `69153a9` (HEAD). O `EX-0010` registra `9c7b872`, que é o commit **pré-amenda** e não é ancestral do HEAD ([P2-5](#p2-5--registro-ex-0010-aponta-para-commit-fora-do-histórico)).

**Resultado:** **156 testes OK**. P1-A (drift de 360 × 365 dias) corrigido para os meses reconhecidos; P2-1, P2-2 e P2-3 fechados. O **P1-B foi retirado** após verificação do cânone: `Sol-Branco` é a **Capital Imperial** (`mundo.md:19`), não um mês; a lista de meses de `regras.md` é que contém um nome de lugar. Restam **P2-D** (revisar a lista canônica dos 12 meses) e **P2-5** (registro de auditoria).

| Achado | Status | Evidência |
| :--- | :---: | :--- |
| P1-A drift `+1y`/`+1mo` | **Corrigido** | `+1y` Valíria → `5 de Ventania de 305`; `+2y` → 306; `+12mo` → 305; `+1mo` 30 Ventania → 30 Geada; Gregorian 31 Jan → 28 Fev |
| P1-B meses com hífen | **Retirado** | `Sol-Branco` é a Capital Imperial (`mundo.md:19`); nenhuma data canônica usa “de Sol-Branco de 304”; o bloco `calendar:` foi introduzido na Fase 01.5 (`7d7f598`) e não existia antes (`065c941`). O regex sem `-` continua como P3 latente |
| P2-D calendário de Valíria | **Aberto** | `regras.md:19` lista `Sol-Branco` (capital) como 5º mês; a lista de 12 nomes foi criada pelo agente em `7d7f598`, sem fonte no cânone. `Noite-Longa` também só aparece nessa lista |
| P2-1 `campaign_id` | **Corrigido** | `validate_campaign_id` rejeita `../`, `..`, `/`, `\`, `:`, espaço, `@`; `find_campaign` levanta; CLI sai 2; `init` retorna erro sem criar diretório |
| P2-2 templates | **Corrigido** | templates ausentes → erro e diretório não criado (teste automatizado) |
| P2-3 lock `plan`/`progress` | **Corrigido** | decorator aplicado; 2 `plan` + 2 `commit` + 1 `progress` concorrentes persistiram; teste de rollback do ledger passa |
| P2-4 documentos canônicos | **Corrigido (com resíduos)** | status/§8/README atualizados; restam “69 testes” em `ROADMAP.md:295` e `ARCHITECTURE.md:222`, e o snapshot `cefe5ea` em `ROADMAP.md:4` (P3) |
| P2-5 registro EX-0010 | **Aberto** | hash registrado não está no histórico; linha do commit tem `\x0c` no lugar do “f” |
| P3-5 README/AGENTS | **Corrigido** | `AGENTS.md` e `README.md` atualizados; `rpgpro-diretrizes-agentes.md` versionado |
| P3-7 cobertura de calendário | **Parcial** | 4 testes novos, mas só `Ventania`; nenhum teste percorre `calendar.months` |
| P3-1/2/3/4/6/8 | **Abertos** | ver seção 5; não foram tocados pelo EX-0010 |

### P1-B — retirado: `Sol-Branco` é a capital, não um mês

O usuário apontou que `Sol-Branco` nomeia o império/capital, não um mês. A verificação confirma o essencial:

- `mundo.md:19` define **Sol-Branco (Capital Imperial)**; o império é Valíria.
- Todas as ocorrências no diário são de lugar (“capital Sol-Branco”, “Senado de Sol-Branco”, “Céus de Sol-Branco”); nenhuma data usa `de Sol-Branco de 304`.
- O bloco `calendar:` não existia em `065c941` (antes da Fase 01.5) e foi introduzido em `7d7f598`; os 12 nomes foram criados pelo agente, sem lista canônica no repositório.

Portanto o teste `05 de Sol-Branco de 304 +30d` usava uma data inválida: o motor não deveria avançá-la. O **P1-B como defeito de motor está retirado**; o problema real é de **dado** (P2-D), a lista de meses declara um lugar como mês.

O que sobra no motor é uma limitação **P3 latente**: os regexes de [temporal/calendar.py:137](temporal/calendar.py#L137) e [253](temporal/calendar.py#L253) não aceitam `-`; se `Noite-Longa` (ou qualquer mês legítimo) tiver hífen, o avanço vira no-op silencioso. `Noite-Longa` também só aparece na lista criada pelo agente, então precisa da mesma revisão canônica. Correção defensiva: incluir `-` na classe e testar todos os meses declarados — mas a decisão dos nomes é do dono da campanha.

### P2-D — Calendário de Valíria declara um lugar como mês

`tests/fixtures/campaigns/imperio_valiria/regras.md:19` lista `Sol-Branco` como o 5º dos 12 meses. O cânone (`mundo.md:19`) diz que Sol-Branco é a Capital Imperial, e nenhuma data do diário usa esse nome como mês. O bloco inteiro foi criado em `7d7f598` (Fase 01.5) — antes dele, `regras.md` não tinha `calendar:`. Como não há lista canônica dos 12 meses no repositório, `Éter`, `Alvorada` e `Noite-Longa` também merecem confirmação (são usados como facção/ordem/estação em outros contextos).

**Impacto:** o motor aceita o calendário declarado como verdade; uma lista inventada contamina `diario.md`, `commit --time` e, na Fase 02, `Event.game_time`. Não é falha de código; é dado Grau 2 a corrigir.

**Correção:** o dono da campanha define a lista canônica dos 12 meses; atualizar `tests/fixtures/campaigns/imperio_valiria/regras.md` (e, se desejado, o template/documentação). Não reescrever `archive/campaigns/` — é histórico. Depois, rodar os testes de calendário com a lista real.

### P2-5 — Registro EX-0010 aponta para commit fora do histórico

`9c7b872` existe no object store, mas `git merge-base --is-ancestor 9c7b872 HEAD` falha; o diff para `69153a9` é só a linha do commit em `EXECUCAO.md` (o hash foi gravado por amend, mudando o próprio hash). Além disso, a linha 288 tem um caractere de controle (`\x0c`) no lugar do “f” de “fix”, e o status “concluído” afirma que todos os P1/P2 foram fechados, o que não se confirmou. Corrigir por nova entrada (`EX-0011`), sem editar a `EX-0010`, e registrar `69153a9`.

**Abaixo, o parecer original de `d2f99bf` (histórico).**

---

## 0. Veredito

**A fundação é sólida e o R0 é comprovadamente behavior-preserving. Os critérios de aceite declarados da Fase 01 e 01.5 passam.** Há, porém, **1 P1** e **4 P2** que devem ser fechados antes de congelar a base para a Fase 02 — sobretudo porque a Fase 02 passará a gravar `game_time` em eventos, tornando erros de calendário permanentes.

| Gravidade | Qtd | Bloqueia congelar a Fase 01 | Bloqueia iniciar a Fase 02 |
| :--- | :-: | :---: | :---: |
| P0 | 0 | — | — |
| P1 | 1 | Sim | Sim |
| P2 | 4 | Recomendado | Sim |
| P3 | 9 (agrupados) | Não | Não |

**Recomendação:** corrigir P1 e P2, adicionar os testes indicados, commitar o relatório e só então abrir a spec da Fase 02 (G1/G2).

---

## 1. Critérios de aceite — resultado

| # | Critério | Fonte | Resultado | Evidência |
| :-: | :--- | :--- | :---: | :--- |
| 1 | Suíte completa verde | ROADMAP §3 | **Passa** | `python -m unittest discover -s tests` → **149 testes, OK**, 17 s, duas execuções; sem `ResourceWarning` |
| 2 | Nenhum typo cria relógio/missão/facção fantasma | ROADMAP §3 | **Passa** | `commit` com relógio, missão e facção inexistentes → 3 recusas; 0 arquivos alterados (hash) |
| 3 | Falha simulada no fim do commit restaura o snapshot | ROADMAP §3 | **Passa** | `test_unexpected_failure_after_writes_restores_snapshot` |
| 4 | Prosa por arquivo funciona | ROADMAP §3 | **Passa** | `check-prose`/`commit --prose-file`: `CLEAN`, `PASSED`, `REJECTED`, `FILE_NOT_FOUND`, `--force` |
| 5 | `+30d` em Valíria com calendário declarado | ROADMAP §3 / 01.5 | **Passa** | `04 de Ventania de 304, 21:15` → `4 de Geada de 304, 21:15` |
| 6 | Typo de facção não cria registro | ROADMAP §3 / 01.5 | **Passa** | `faction --rep "Conselhoo:+1"` sem `--create` → erro, ficha e diário inalterados |
| 7 | `lazy_turn.py` < 200 linhas | ARCHITECTURE §12/§15 | **Passa** | 54 linhas |
| 8 | Markdown idêntico antes/depois do R0 | ARCHITECTURE §12 | **Passa** | 11 comandos idênticos na CLI antiga (`cefe5ea`) × nova → saída igual e **15/15 arquivos Markdown idênticos** |
| 9 | Contratos exercitados com fakes; nenhum plugin real | ARCHITECTURE §5.0.2 | **Passa** | `FakeEventStore` + `EventStoreContract`; `bootstrap` não registra plugins |
| 10 | `contracts/` e `kernel/` sem I/O e sem imports de camadas proibidas | ARCHITECTURE §15 | **Passa** | teste AST + inspeção manual (`json.dumps` é serialização pura) |
| 11 | Fixtures sem dependência das campanhas vivas | ARCHITECTURE §15 | **Passa** | `campaigns/` só tem `.gitkeep`; fixtures e `archive/campaigns` byte-idênticos (15/15) |
| 12 | Nenhum arquivo > 600 linhas | ARCHITECTURE §15 | **Falha** | `council/reviewer.py` tem **688**; o teste de fronteira só mede os pacotes novos ([P3-4](#p3-4--critério-de-600-linhas-não-é-aplicado-ao-legado)) |

---

## 2. Evidência executada

- **Suíte:** 149 testes, OK, 17,03 s (repetida; mesmo resultado). `PYTHONWARNINGS=always::ResourceWarning` não emitiu aviso.
- **AST:** das 15 funções de topo de `lazy_turn.py` em `cefe5ea`, **15/15 têm corpo idêntico** em `application/`/`interfaces/`. Das 12 funções de `council/helpers.py`, 8 são idênticas e 4 diferem **apenas** pela indireção `_get_campaign_dirs()`/`dirs` (comportamento preservado).
- **Regressão diferencial:** worktree temporário em `cefe5ea` × HEAD, com cópias idênticas das fixtures: 18 invocações read-only com saída e exit code iguais (a única diferença foi o caminho da campanha na mensagem de erro de campanha inexistente); 11 comandos mutantes produziram **saída igual** e **15/15 Markdown iguais**.
- **Concorrência:** 4 `commit` em paralelo → turnos 4, 5, 6 e 7, sem duplicata nem perda; `.campaign.lock` liberado.
- **Entidades:** `clock --advance "Relogio Fantasma"` e `quest --complete Q99` retornam erro e não alteram o diário.
- **Conteúdo:** `init-campaign` em diretório vazio cria os 5 arquivos e passa em `review` com `ssot_status: CLEAN`.
- **Fixture `perpetuos_terra_incognita`:** `review` = `FOUND_1_ISSUES` (`STALE_NPC_ATTITUDE`). É pré-existente e idêntico ao `archive/`, não é regressão ([P3-6](#p3-6--fixtures-não-estão-todas-clean)).

---

## 3. P1 — Bloqueante

### P1-A — `+1y` e `+1mo` ignoram o calendário declarado

`parse_time_increment` ([temporal/calendar.py:65-88](temporal/calendar.py#L65-L88)) converte unidades em minutos fixos: `+1mo` = 30 dias e `+1y` = **365 dias**. Depois, `advance_time_str` aplica esses minutos ao calendário **declarado** ([temporal/calendar.py:120-151](temporal/calendar.py#L120-L151)). Em Valíria o ano tem 12 × 30 = **360 dias**, então `+1y` avança um ano e cinco dias.

```text
advance_time_str("05 de Ventania de 304, 08:06", 525600, calendar=valiria)
  -> "10 de Ventania de 305, 08:06"      # esperado: 05 de Ventania de 305
advance_time_str("05 de Ventania de 304, 08:06", 360*1440, calendar=valiria)
  -> "05 de Ventania de 305, 08:06"      # correto
```

O caminho é anunciado ao usuário e ao agente: `--time` documenta `'+1y'` ([interfaces/cli/parser.py:36](interfaces/cli/parser.py#L36)), `_compute_commit_datetime` aceita o incremento ([application/commit_validation.py:37-43](application/commit_validation.py#L37-L43)) e o commit grava a data resultante no `diario.md` sem aviso. `+1mo` também é uma aproximação de 30 dias: correta para Valíria, errada para calendários com meses de duração variável e para o fallback gregoriano (`31 de Janeiro +1mo` cai em 2 de Março).

**Impacto:** data de jogo silenciosamente errada no SSOT. Na Fase 02 esse valor passa a ser gravado em `Event.game_time`/`game_time_sort`, tornando o desvio permanente no log — por isso o achado é bloqueante agora.

**Correção recomendada:** interpretar unidades relativas no nível do calendário, não em minutos: `+1y` = `len(months)` meses (ou soma de `days_per_month`), `+1mo` = deslocamento de índice de mês, `+Nd/h/m/w` = `timedelta`. Alternativa mínima: em `_compute_commit_datetime`, quando houver calendário, converter `+Nmo`/`+Ny` usando `days_per_month` antes de chamar `advance_time_str`.

**Testes a adicionar:**
- `+1y` em Valíria a partir de `05 de Ventania de 304` → `05 de Ventania de 305`.
- `+1mo` a partir de `30 de Ventania de 304` → `1 de Geada de 304`.
- Virada de 360 dias (12 meses) sem drift e `+1y` × 2 = 2 anos exatos.
- Teste gregoriano para `+1mo` com mês de 31 dias (documentar a semântica escolhida).

---

## 4. P2 — Corrigir antes da Fase 02

### P2-1 — `campaign_id` não é validado: leitura e escrita fora de `campaigns/`

`find_campaign` concatena `base / campaign_id` sem sanitizar ([campaign/locator.py:164-168](campaign/locator.py#L164-L168)); `init_campaign_from_templates` faz o mesmo ([campaign/templates.py:24-31](campaign/templates.py#L24-L31)). Com `campaign_id` contendo `..` ou separador de caminho, o motor sai da raiz de campanhas.

```text
find_campaign("../outside")                       -> id "../outside", dir ...\campaigns\..\outside
init_campaign_from_templates("../criada_fora")    -> status "ok", diretório criado FORA de campaigns/
```

**Impacto:** um `--campaign` alucinado ou malicioso pode ler/gravar um “SSOT” fora da árvore de campanhas. É CLI local, mas o agente é o principal cliente da CLI.

**Correção:** validar o id com `^[a-z0-9][a-z0-9_-]*$` em `find_campaign`, `init_campaign_from_templates` e no parser; depois resolver o caminho e exigir que o pai seja exatamente uma das raízes de `CAMPAIGN_DIRS`. Rejeitar `.`, `..`, `/`, `\`, `:` e caminhos absolutos.

### P2-2 — `init-campaign` com templates incompletos devolve sucesso e cria campanha quebrada

O laço de criação só grava os templates que existem ([campaign/templates.py:122-130](campaign/templates.py#L122-L130)) e retorna `status: ok` com `created_files` menor que 5.

```text
init_campaign_from_templates("nova")  # apenas ficha.template.md presente
  -> {"status": "ok", "created_files": ["ficha.md"]}
```

Depois, `find_campaign` falha porque não há `diario.md`, mas o diretório já foi criado e aparenta sucesso para o chamador.

**Correção:** verificar a existência dos 5 templates **antes** de criar o diretório; em falta, retornar erro e não criar nada. Alternativa: criar em diretório temporário e só publicar com `os.replace` após validar os 5 arquivos.

### P2-3 — `plan` e `progress` mutam o SSOT fora do lock/snapshot da campanha

A fronteira transacional cobre `commit`, `clock`, `arc`, `quest` e `faction` ([application/transaction.py:10-43](application/transaction.py#L10-L43)), mas não `cmd_plan` ([application/showrunner.py:89-140](application/showrunner.py#L89-L140)) nem `cmd_progress` ([application/progression.py:107-150](application/progression.py#L107-L150)).

- `plan --add/--complete/--milestone` grava `diario.md` sem `campaign_lock`; pode intercalar com um `commit` e perder a atualização de um dos dois.
- `progress --award` grava **dois** arquivos (`ficha.md` e o ledger em `diario.md`) sem lock e sem snapshot; uma exceção entre os dois deixa XP concedido sem lastro no ledger (`XP_MISMATCH`) ou o inverso.

**Correção:** aplicar `@_serialized_campaign_mutation` em `cmd_plan` e `cmd_progress` (mesmo padrão dos demais), com teste de concorrência `plan × commit` e de falha injetada no meio do `progress --award`. Observação: `cmd_plan` só escreve um arquivo, mas o lock ainda é necessário para não competir com `commit`.

### P2-4 — Documentos canônicos divergem do estado real do HEAD

| Documento | Afirma | Realidade |
| :--- | :--- | :--- |
| [ARCHITECTURE.md:3](ARCHITECTURE.md#L3) | “o próximo passo é R0” | R0 e R0.5 concluídos em `d2f99bf` |
| [ROADMAP.md:342-350](ROADMAP.md#L342-L350) | “Executar R0”, “Executar R0.5”, “Escrever a spec da Fase 02” | R0/R0.5 já executados e registrados em `EX-0004`–`EX-0008` |
| [ROADMAP.md:46](ROADMAP.md#L46), [60](ROADMAP.md#L60), [321](ROADMAP.md#L321) | 68/69 testes | 149 testes |
| [ARCHITECTURE.md:639](ARCHITECTURE.md#L639), [696](ARCHITECTURE.md#L696) | “69 testes existentes” | 149 no HEAD |
| [README.md:36-47](README.md#L36-L47) | `campaigns/` com 3 campanhas vivas; `helpers.py` como módulo de constantes | `campaigns/` vazio; campanhas em `archive/` e `tests/fixtures/`; módulos extraídos |

**Impacto:** o `ARCHITECTURE.md` é declarado dono da árvore/gates e o `ROADMAP.md` dona do plano; um agente que os siga pode reexecutar R0 ou assumir campanhas que não existem. É contradição direta com `EXECUCAO.md`, que é o registro do que aconteceu.

**Correção:** atualizar o cabeçalho/§16 do `ARCHITECTURE.md` (“R0 e R0.5 concluídos; próximo passo: spec da Fase 02”), os “Próximos passos” e os números de teste do `ROADMAP.md`, e a árvore do `README.md`. Não reescrever o histórico; apenas o estado atual.

---

## 5. P3 — Higiene e robustez (não bloqueiam)

### P3-1 — Contrato de erro da CLI é inconsistente

`plan` e `arc` sem JSON caem em `KeyError: 'arc'` e `KeyError: 'current_scene_header'` com traceback quando a campanha não existe ([interfaces/cli/main.py:130](interfaces/cli/main.py#L130), [162](interfaces/cli/main.py#L162)); `clock`, `quest` e `progress` ignoram `error` e exibem “nenhum relógio/missão” ou nível 1 como se a campanha existisse ([main.py:106-114](interfaces/cli/main.py#L106-L114), [225-257](interfaces/cli/main.py#L225-L257)). `commit` com erro retorna exit 0; `check-prose` retorna 1. O mesmo vale para entradas extremas: `--time "+999999999y"` estoura `OverflowError` com traceback (rollback funciona, mas o usuário vê stack trace) e `--favor "-1"` é anunciado no help ([parser.py:163](interfaces/cli/parser.py#L163)) mas falha porque `-1` vira nome de facção.

**Sugestão:** centralizar o tratamento de `{"error": ...}` no despacho (imprimir erro e `sys.exit(1)`), validar o retorno antes de formatar e corrigir o help de `--favor`/`--debt`.

### P3-2 — Contratos do kernel ainda são rasos em imutabilidade e validação

- `EventDraft`/`Event` são `frozen=True`, mas `payload`/`meta` são `dict` mutáveis: `event.payload["x"] = 1` funciona e `hash(event)` falha. A “imutabilidade” do envelope é só de atributo ([contracts/event.py:50-121](contracts/event.py#L50-L121)).
- `EventStreamView` promete stream “ordenado”, mas não valida `seq` crescente/contígua ([contracts/ports.py:33-52](contracts/ports.py#L33-L52)).
- `FakeEventStore` inventa `game_time = "01 de Janeiro de 304, 00:00"` quando o draft não traz data ([tests/contract_support.py:106](tests/contract_support.py#L106)); o contrato não deixa claro quem preenche `game_time`/`game_time_sort` (aplicação ou store), e o fake mascara o caso “ausente”.
- `PatternError` de regex inválida e `TypeError` de `minItems` não-string escapam como exceções genéricas em vez de `SchemaError` ([kernel/schema.py:121-127](kernel/schema.py#L121-L127), [179-192](kernel/schema.py#L179-L192)); `enum` aceita `True` para `[1]` por igualdade Python.
- `PluginManifest` valida nome/versão com `.strip()` mas descarta o resultado ([kernel/registry.py:40-64](kernel/registry.py#L40-L64)); `Registry.register` não normaliza `point`/`name`, então `register(" p ", " n ")` não é encontrado por `get("p", "n")` ([kernel/registry.py:79-95](kernel/registry.py#L79-L95)).
- `Runtime.__post_init__` congela o registry **do chamador** ([kernel/runtime.py:42-43](kernel/runtime.py#L42-L43)); é efeito colateral de construtor em objeto documentado como imutável.

### P3-3 — Inversão de camada em `campaign/locator._get_campaign_dirs`

O localizador de campanha consulta `sys.modules["council.helpers"]` para honrar patches de teste ([campaign/locator.py:19-25](campaign/locator.py#L19-L25)). Funciona, mas faz `campaign` depender de `council.helpers` (fachada de domínio) e introduz estado global mutável no caminho de localização. Preferível: injetar as raízes de campanha como parâmetro ou usar uma variável de módulo explicitamente substituível.

### P3-4 — Critério de 600 linhas não é aplicado ao legado

`council/reviewer.py` tem **688** linhas, acima do limite de falha de [ARCHITECTURE.md:688](ARCHITECTURE.md#L688) (§15, item 2). O teste de fronteira só mede `application`, `interfaces`, `contracts`, `kernel`, `adapters`, `temporal` e `campaign` ([tests/test_architecture_boundaries.py:110-113](tests/test_architecture_boundaries.py#L110-L113)). É dívida preexistente (R3), mas o critério declarado não está sendo verificado. `narrator.py` (600), `ssot.py` (797), `factions.py` (853) e `quests.py` (506) também estão acima do alvo de 300/400.

### P3-5 — README e `AGENTS.md` desatualizados após o R0.5

Além da árvore do README ([P2-4](#p2-4--documentos-canônicos-divergem-do-estado-real-do-head)), [AGENTS.md:12](AGENTS.md#L12) manda “assumir a única campanha existente” em `campaigns/`, que agora está vazio. Uma sessão nova não tem campanha para rotear; falta a instrução de criar via `init-campaign` ou usar as fixtures. `rpgpro-diretrizes-agentes.md` é citado como fonte em `ROADMAP.md`/`EXECUCAO.md`, mas está **não versionado** (`?? rpgpro-diretrizes-agentes.md`).

### P3-6 — Fixtures não estão todas `CLEAN`

`tests/fixtures/campaigns/perpetuos_terra_incognita` retorna `FOUND_1_ISSUES` (`STALE_NPC_ATTITUDE` em `Lucien`). O fixture é byte-idêntico ao `archive/campaigns`, então é estado legado conhecido (citado no QA da 009), não regressão. Registrar para não tratar “3 campanhas CLEAN” como critério já cumprido sem ressalva.

### P3-7 — Cobertura de teste do calendário não pega o P1

`tests/test_temporal_calendar.py` valida `+1y = 525600` minutos (a implementação atual) e só testa calendário customizado com `+2d`. Falta o caso “unidade relativa × calendário declarado” que revelaria o P1.

### P3-8 — `json.dumps` no `contracts` é aceitável, mas o teste de I/O é heurístico

O teste AST procura chamadas cujo nome seja exatamente `open` e imports com raiz proibida; não pegaria `builtins.open(...)`, `__import__("os")` ou um `open` obtido por `getattr`. Hoje a inspeção manual confirma que `contracts/`/`kernel/` não fazem I/O, então é robustez do teste, não defeito do código.

### P3-9 — Nota de ambiente

Esta auditoria rodou no ambiente atual (sem sandbox). O QA anterior valorizava “suíte verde sob sandbox”; não revalidei essa condição aqui, apenas a suíte verde.

---

## 6. O que está bom

- **R0 é behavior-preserving de verdade:** AST idêntico para 15/15 funções da CLI e regressão diferencial com 15/15 Markdown idênticos. A extração não é “parece igual”; é comprovadamente igual.
- **Lock e atomicidade funcionam:** 4 commits concorrentes geraram turnos 4–7 sem perda nem duplicata; `atomic_write_text` não deixa `.tmp`.
- **Validação prévia de entidades é eficaz:** relógio, missão e facção fantasmas são recusados antes de qualquer escrita; três commits rejeitados deixaram 0 arquivos alterados.
- **Caminhos de prosa estão completos:** `check-prose`, `--prose`, `--prose-file`, `--force`, `PASSED`/`REJECTED`/`FILE_NOT_FOUND`, com exit code coerente no `check-prose`.
- **Calendário declarativo funciona no caso central:** `+30d` em Valíria e virada de mês (`30 de Ventania +1d` → `1 de Geada`) corretos; mês desconhecido falha antes de escrever.
- **Fixtures e arquivo:** `archive/campaigns` preservado, fixtures idênticas, `campaigns/` limpo com `.gitkeep`; suíte sem campanhas vivas.
- **Contratos com fakes têm suíte real:** envelope, `EventStore` (identidade, ordem, `expected_last_seq`, lote vazio, falha all-or-nothing), schema, registry, runtime e bootstrap cobertos por 149 testes; sem warnings de recurso.
- **`EXECUCAO.md` bate com a realidade nos números:** 149 testes e R0.5 registrados de forma consistente (o problema é o roadmap/arquitetura não terem acompanhado).

---

## 7. Recomendação e ordem de execução

1. **P1-A:** corrigir semântica de `+1mo`/`+1y` no calendário declarado e adicionar os 4 testes do P1.
2. **P2-1/P2-2:** validar `campaign_id` e fazer `init-campaign` ser tudo-ou-nada.
3. **P2-3:** cobrir `plan` e `progress` com a fronteira transacional + testes de concorrência/falha.
4. **P2-4/P3-5:** atualizar `ARCHITECTURE.md`, `ROADMAP.md`, `README.md` e `AGENTS.md` para o estado pós-R0.5.
5. Reexecutar a suíte, commitar este QA e os reparos, e só então abrir a spec da Fase 02 (G1/G2).
6. P3 pode entrar no backlog de R1/R2/R3; P3-2 (imutabilidade do envelope) merece decisão explícita no G1, antes do `EventStore` JSONL.

---

## 8. Como reproduzir

```powershell
# suíte
python -m unittest discover -s tests

# P1: calendário
python -c "from temporal.calendar import advance_time_str, parse_time_increment; from campaign.locator import parse_regras_manifest; import pathlib; cal=parse_regras_manifest(pathlib.Path('tests/fixtures/campaigns/imperio_valiria/regras.md'))['calendar']; print(advance_time_str('05 de Ventania de 304, 08:06', parse_time_increment('+1y'), cal))"

# P2-1/P2-2: contenção e templates
$tmp = Join-Path $env:TEMP 'qa_contain'; New-Item -ItemType Directory -Force $tmp | Out-Null
$env:RPGPRO_CAMPAIGNS_DIR = "$tmp\campaigns"; New-Item -ItemType Directory -Force "$tmp\campaigns" | Out-Null
python lazy_turn.py init-campaign --campaign "../fora" --title "Fora"
Test-Path "$tmp\fora"   # True = escreveu fora de campaigns/

# P2-3: mutadores fora do lock
Select-String -Path application\showrunner.py,application\progression.py -Pattern '_serialized_campaign_mutation|def cmd_plan|def cmd_progress'
```

---

## 9. Arquivos tocados por este QA

- `QA-FASE-01.md` (este relatório).
- `EXECUCAO.md` (entrada `EX-0009`, append-only).
- Nenhum código de produção foi alterado; nenhuma fixture foi modificada.
