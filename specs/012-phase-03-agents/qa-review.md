# QA Review — 012 Fase 03 / R2 (Agentes e Contrato Epistêmico G3)

**Commits auditados:** nenhum — a implementação está **não commitada** no worktree, sobre a base `930773a` (`docs(exec): record EX-0022 for G3 ratification`).
**Data:** 26/10/2026.
**Método:** suíte completa, testes de fronteira, leitura dos 16 arquivos novos/alterados, comparação AST entre as fachadas `council/` e o `HEAD`, confronto entre os 13 tipos de evento do catálogo e os tipos realmente emitidos/projetados, e sondas adversariais executadas contra o store real (`validate_draft_batch`), a projeção epistêmica, o validador de admissão e o replay.
**Escopo:** Refatoração R2 (`council/` → `resources/`), Contrato Epistêmico G3 (`Claim`, `ProvenanceRef`, `KnowledgeRecord`, `resolve_claim`, `KnowledgeView`), NPCs em dois níveis, facções com política interna, admissão de propostas, portas de política, projeções `npcs.md`/`faccoes.md`, suíte `tests/test_phase03_agents_and_g3.py`, documentação de fase.

---

## Re-auditoria 5 — 26/10/2026 (EX-0031): fechamento

**Objeto:** fechamento das ressalvas R1–R5 da quarta rodada (`EX-0031`), worktree ainda sem commit.
**Suíte:** **234 testes OK em 84,5 s**; fronteiras **8 OK**; fase 03 **21 OK** (17 ATs + AT18 + 3 regressões).
**Sondas:** `probe_phase03.py` a `probe_phase03e.py`.

**Veredito: APROVADO — sem ressalvas funcionais.** O Gate G3 está atendido; restam apenas ajustes documentais P2/P3 antes do commit.

### 1. Ressalvas da rodada anterior — fechadas

| Ressalva | Status | Evidência |
| :--- | :---: | :--- |
| R1 `source_type` fora da spec | **Fechado** | `data-model.md` §2.3 agora documenta os 9 valores, em paridade com `HolderRef.kind` |
| R2 FR-AG-04 sem teste | **Fechado** | `test_at18_governance_and_physical_admission` cobre autoridade (`UNAUTHORIZED_FACTION_LEADERSHIP`), condição (`ACTOR_INCAPACITATED`) e localização (`LOCATION_MISMATCH`) |
| R3 testes suplementares com nome de AT | **Fechado** | renomeados para `test_regression_p0/p1/p2_*` |
| R4 negação explícita virava `UNKNOWN` | **Fechado** | `"O capitao nao morreu"` → `FALSE`; `"morreu sem luta"` → `TRUE` |
| R5 fallback `pln_<npc_id>` | **Fechado** | fallback agora deriva de `evt_<ulid>`/`seq` (`resources/npcs/service.py:146-155` e equivalente em facções) |

Nenhuma regressão encontrada nas sondas de visibilidade, compartilhamento, replay e rebuild.

### 2. Ajustes documentais antes do commit (não bloqueiam o G3)

1. **P2 — `tasks.md` foi substituído.** O arquivo canônico da feature (T001–T038) virou uma lista de remediação T001–T017; o plano original não está mais recuperável no worktree (era untracked). Restaurar as 38 tarefas e mover a remediação para um `tasks-remediation-2.md`, ou registrar a substituição formalmente.
2. **P3 — `AT18` não faz parte da matriz ratificada.** `spec.md` §4 continua com 17 critérios, mas o teste e `EX-0031` falam em “18 ATs canônicos”. Renomear para `test_fr_ag_04_admission` (ou ratificar AT18 com o dono).
3. **P3 — “Emenda G3” no `data-model.md`.** A nota que amplia `source_type` está rotulada como emenda ao G3, mas o `g3-decision-record.md` não foi alterado. Ou registrar a emenda formalmente, ou remover o rótulo.
4. **P3 — status de fase desatualizados.** `ROADMAP.md` (linha 122), `ARCHITECTURE.md` e `checklists/g3-ratification.md` ainda descrevem a fase como reprovada/em remediação. Atualizar no mesmo commit da homologação.

### 3. Reprodução

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"
python -m unittest tests.test_phase03_agents_and_g3
python .tmp/probe_phase03c.py
python .tmp/probe_phase03d.py
python .tmp/probe_phase03e.py
```

---

## Re-auditoria 4 — 26/10/2026 (EX-0029)

**Objeto:** quarta rodada de remediação (registro originalmente numerado `EX-0028`, renumerado para `EX-0029` por duplicidade).
**Suíte:** **233 testes OK em 72,2 s**; fronteiras **8 OK**; fase 03 **20 OK** (17 ATs + 3 suplementares).
**Sondas:** `probe_phase03.py` a `probe_phase03e.py`, mais matriz de visibilidade e origens de compartilhamento.

**Veredito: APROVADO COM RESSALVAS. O Gate G3 está tecnicamente atendido; restam apenas pendências P2/P3 de contrato e cobertura, não bloqueantes.**

### 1. Bloqueios anteriores — fechados e verificados

| Achado | Status | Evidência |
| :--- | :---: | :--- |
| P0 `knowledge.shared` com origem não-NPC quebrava o replay | **Fechado** | `player→protagonist`, `subgroup→faction` e `protagonist→player` projetam sem erro, com `source_type` preservado; `test_at18` cobre os três |
| P1 `player_meta` bloqueava a claim inteira | **Fechado** | Claim com registro público de NPC + `player_meta` retorna `known` para audiência NPC; `test_at19` |
| P1 `holder_only` legível sem audiência | **Fechado** | `KnowledgeView(records=recs).query_claim` → `unavailable`; `test_at19` |
| P2 antinegação com `"sem"` | **Fechado** | `"O capitao morreu sem luta"` → `TRUE`; a janela agora olha apenas tokens anteriores ao predicado |
| P2 `plans` duplicados / `commitments` ausente | **Fechado** | `test_at20`: um plano por `plan_id`, commitments projetados |
| AT02/AT09/AT10 rasos | **Fechado** | AT02 testa `unknown` → rejeição e `known`+`disbelieved` → admissão; AT09 comprova estado inalterado; AT10 executa `rebuild_projections` e confere proveniência preservada |

Matriz de visibilidade verificada (8 audiências × 6 tipos de registro): `public` acessível a todos; `holder_only` só ao holder; `faction_internal` à facção e a membro leal, negado a dissidente e a audiências externas; `subgroup_only` só ao subgrupo; `player_meta` só a player/human; `protagonist_private` só a protagonista/player. Nenhum vazamento encontrado.

### 2. Cobertura AT

**17/17 ATs plenos** (`AT01` a `AT17`), com `AT02`, `AT09` e `AT10` agora aprofundados. Os testes `AT18` a `AT20` são suplementares e corretos, mas não fazem parte dos critérios ratificados — ver ressalva R3.

### 3. Ressalvas (não bloqueantes)

1. **R1 (P2) — Contrato de `source_type` expandido sem sincronizar a spec.** `VALID_SOURCE_TYPES` passou a aceitar `player`, `protagonist` e `subgroup` (`resources/knowledge/model.py:14`), enquanto [`data-model.md`](data-model.md) e `tasks.md` (T021) enumeram apenas `event|npc|faction|document|inference|system`. A solução funciona, mas o contrato canônico precisa ser emendado ou o replay deve mapear o holder para um dos seis tipos.
2. **R2 (P2) — FR-AG-04 sem teste dedicado.** A autoridade de facção, a condição incapacitante e a localização estão implementadas e foram verificadas manualmente (`UNAUTHORIZED_FACTION_LEADERSHIP`, `LOCATION_MISMATCH`, `ACTOR_INCAPACITATED`), mas nenhum AT as exercita. Adicionar um teste de admissão por autoridade.
3. **R3 (P3) — Nomes `AT18`–`AT20`.** São testes de regressão dos achados de QA, não critérios ratificados; convém renomeá-los (ex.: `test_shared_non_npc_origins`) para não confundir a matriz AT01–AT17.
4. **R4 (P3) — Negação explícita ainda retorna `UNKNOWN`.** `"O capitao nao morreu na batalha"` deveria resolver `FALSE` (o evento canônico nega o fato), não `UNKNOWN`. O resolvedor segue heurístico por texto; aceitável para prosa livre, mas vale registrar a limitação em `resolver.py`.
5. **R5 (P3) — Fallback `pln_<npc_id>`.** Permanece para eventos escritos sem `plan_id`, fora do formato `pln_<ulid>`; preferir derivar um ULID determinístico do evento.
6. **R6 (P3) — Numeração de execução.** O registro da rodada foi renumerado de `EX-0028` para `EX-0029` por colidir com o parecer de QA; manter a sequência única.

### 4. Reprodução

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"
python -m unittest tests.test_phase03_agents_and_g3
python .tmp/probe_phase03.py
python .tmp/probe_phase03b.py
python .tmp/probe_phase03c.py
python .tmp/probe_phase03d.py
python .tmp/probe_phase03e.py
```

---

## Re-auditoria 3 — 26/10/2026 (EX-0027)

**Objeto:** terceira rodada de remediação (`EX-0027`), worktree ainda sem commit.
**Suíte:** **230 testes OK em 75,4 s**; fronteiras **8 OK**; fase 03 **17 OK**; drafts **13/13** aceitos.
**Sondas:** `probe_phase03.py`, `probe_phase03b.py`, `probe_phase03c.py`, `probe_phase03d.py` e a nova `.tmp/probe_phase03e.py`.

**Veredito da terceira rodada: REPROVADO, com escopo residual pequeno.**

A suíte de aceite finalmente corresponde à semântica ratificada (15 ATs plenos, 2 parciais), a matriz de visibilidade funciona para `holder_only`/`faction_internal`/`subgroup_only`, os campos de FR-AG-02/03 são projetados, `contested` consolida entre registros, `faccoes.md` é gerado no rebuild e o replay/snapshot é byte-idêntico. Restam **1 P0 e 2 P1** pontuais, todos reproduzíveis.

### 1. P0 — `knowledge.shared` quebra o replay quando a origem é `player`, `protagonist` ou `subgroup`

`project_knowledge_state` deriva o `source_type` da proveniência diretamente de `from_holder.kind` (`resources/knowledge/service.py:192`), mas `VALID_SOURCE_TYPES` só aceita `event|npc|faction|document|inference|system`:

```text
player -> protagonist : CRASH ValueError source_type inválido: 'player'
subgroup -> faction   : CRASH ValueError source_type inválido: 'subgroup'
protagonist -> player : CRASH ValueError source_type inválido: 'protagonist'
```

As fábricas já aceitam esses holders (mapeamento de `ActorRef` em `resources/knowledge/drafts.py:11-21`), então o evento canônico entra no log e o replay levanta exceção. FR-G3-06 exige `holder_id` tipado para NPC, facção, subgrupo, protagonista e jogador, com compartilhamento explícito; o caminho de compartilhamento a partir de qualquer um desses três holders não sobrevive à reconstrução. Nenhum AT cobre `knowledge.shared` com origem diferente de NPC (AT07 usa membro NPC).

### 2. P1 — `player_meta` bloqueia a claim inteira, inclusive conhecimento público posterior

O bloqueio em `query_claim` (`resources/knowledge/view.py:114-117`) verifica se **qualquer** registro da claim é `player_meta` e, em caso positivo, retorna `unavailable` para qualquer audiência que não seja player/human. Isso ignora o registro selecionado:

```text
claim com registro publico NPC + player_meta, audiencia NPC -> unavailable (esperado known)
holder sem registro (outro NPC) -> unavailable
```

Cenário real: o jogador recebe meta-conhecimento de um fato; depois um NPC o descobre publicamente. A partir daí **todo** NPC recebe `unavailable` para sempre, mesmo com registro `public` ou `knowledge.shared` explícito. O filtro deveria olhar o registro efetivamente selecionado (`_is_accessible`), não o conjunto inteiro.

### 3. P1 — `holder_only` é legível por uma view sem holder e sem audiência

`_is_accessible` retorna `True` para `holder_only` quando `aud` é `None` (`resources/knowledge/view.py:67-68`), e `query_claim` sem holder usa o primeiro registro conhecido:

```text
KnowledgeView(records=recs).query_claim(cid) -> known   (registro holder_only de npc_a)
```

A view sem holder deveria responder `unknown`/`unavailable` ou exigir holder; hoje ela expõe segredo de holder para uma audiência não especificada.

### 4. P2 — Resolvedor e cobertura

1. **Antinegação por janela de 40 caracteres ainda gera falso negativo:** `"O capitao morreu sem luta"` → `UNKNOWN` (o marcador `sem` suprime um fato verdadeiro); `"O capitao nao morreu"` → `UNKNOWN`, quando o evento canônico nega o fato e o resultado correto seria `FALSE`.
2. **AT10 parcial:** o teste verifica que `correction.issued` invalida o fato, mas não reconstrói o estado epistêmico nem confere a proveniência preservada, como o critério exige.
3. **AT02 e AT09 rasos:** AT02 não afirma `availability="known"` nem `stance="disbelieved"` na view (só a admissão); AT09 verifica apenas que não existe NPC no estado, sem provar que a proposta não alterou nada.
4. **`plans` duplica versões:** cada `npc.plan_updated` do mesmo `plan_id` acrescenta outro `AgentPlan` à tupla (`resources/npcs/service.py:136-137`); não há consolidação por id.
5. **`commitments` nunca é populado:** o campo existe em `NpcState`, mas nenhum evento o alimenta (`npc.promoted` recebe `goals`, não commitments).
6. **Fallback `pln_<npc_id>`:** permanece para eventos sem `plan_id` (`resources/npcs/service.py:128`), fora do formato documentado `pln_<ulid>`.

### 5. Cobertura AT após a terceira rodada

| AT | Teste | Veredito |
| :--- | :--- | :---: |
| AT01 fato vs crença | `test_at01` | Passa |
| AT02 conhecer sem acreditar | `test_at02` | Parcial |
| AT03 proveniência | `test_at03` | Passa |
| AT04 informação falsa | `test_at04` | Passa |
| AT05 desatualização | `test_at05` | Passa |
| AT06 inferência | `test_at06` | Passa |
| AT07 conhecimento coletivo | `test_at07` | Passa |
| AT08 segredo do jogador | `test_at08` | Passa |
| AT09 proposta não admitida | `test_at09` | Parcial |
| AT10 reconstrução e correção | `test_at10` | Parcial |
| AT11 fontes contraditórias | `test_at11` | Passa |
| AT12 desatualizado ≠ falso | `test_at12` | Passa |
| AT13 premissa refutada | `test_at13` | Passa |
| AT14 facção dividida | `test_at14` | Passa |
| AT15 correção não reescreve crença | `test_at15` | Passa |
| AT16 replay e snapshot | `test_at16` | Passa |
| AT17 visibilidade | `test_at17` | Passa |

**15 plenos, 2 parciais; zero desalinhados.** O problema remanescente é de código não coberto (P0/P1), não de mapeamento dos testes.

### 6. Recomendação

1. Mapear `from_holder.kind` para um `source_type` válido no replay de `knowledge.shared` (`player`/`protagonist` → `system` ou `npc`; `subgroup` → `faction`) e adicionar um AT de compartilhamento com origem não-NPC.
2. Restringir o bloqueio de `player_meta` ao registro selecionado, não a qualquer registro da claim.
3. Negar `holder_only` quando não há `audience` (ou exigir holder na view).
4. Reforçar AT02/AT09/AT10 com as asserções que os critérios exigem.
5. Opcional: consolidar `plans` por `plan_id` e remover o fallback `pln_<npc_id>`.

**Reprodução:**

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"
python .tmp/probe_phase03.py
python .tmp/probe_phase03b.py
python .tmp/probe_phase03c.py
python .tmp/probe_phase03d.py
python .tmp/probe_phase03e.py
```

---

## Re-auditoria — 26/10/2026 (EX-0025)

**Objeto:** remediação submetida em `EX-0025` (worktree ainda sem commit, base `930773a`).
**Suíte:** **230 testes OK em 68,4 s**; fronteiras **8 OK**; `test_phase03_agents_and_g3` **17 OK**; `test_phase03_draft_validation` **1 OK**.
**Sondas:** as duas de 26/10 (`probe_phase03.py`, `probe_phase03b.py`) mais `.tmp/probe_phase03c.py` e `.tmp/probe_phase03d.py`.

**Veredito da segunda rodada: REPROVADO, com progresso substancial.**

O núcleo epistêmico passou a funcionar de ponta a ponta para holders NPC e facção, os drafts são aceitos pelo store e o replay é determinístico. R2 permanece aprovado. Restam, porém, **2 P0 e 5 P1** que impedem a homologação: a suíte de aceite continua com **9 dos 17 ATs fora da semântica ratificada** e `KnowledgeView` **não bloqueia vazamento de segredos** (AT17).

### 1. Fechados nesta rodada (verificados)

| Achado original | Status | Evidência |
| :--- | :---: | :--- |
| P0-1 drafts rejeitados pelo store | **Fechado** | `validate_draft_batch` aceita os 13 tipos; `test_phase03_draft_validation` 1 OK; sondas A/B sem `UnknownEventTypeError`/`SchemaError` |
| P0-2 projeção ignora eventos canônicos | **Fechado** | `project_knowledge_state` trata os 5 `knowledge.*`; `knowledge.acquired/inferred/revised/shared` produzem 1 registro cada |
| P1-1 proveniência vazia aceita | **Fechado** | `validate_provenance_chain(provenance=())` → `(False, ["Registro epistêmico carece de proveniência..."])` |
| P1-2 `outdated` inexistente | **Fechado** | `project_knowledge_state(..., current_time_sort=300)` → `status="outdated"` para claim com `valid_to=200` |
| P1-4 admissão sem autoridade | **Fechado** | `known`+`disbelieved` → admitido; `acts_for_faction` sem liderança → `UNAUTHORIZED_FACTION_LEADERSHIP` |
| P1-5 IDs aleatórios no replay | **Fechado** | replays sucessivos produzem o mesmo estado; nenhum `knw_`/`pln_` novo no replay |
| P1-6 `knowledge.shared` ausente | **Parcial** | destinatário recebe `known`; terceiro recebe `unknown`; mas a fábrica quebra para `from_holder` não-NPC (ver R-P1-1) |
| P1-7 nenhuma integração | **Parcial** | projectors e projeções consumem os tipos canônicos; `faccoes.md` continua desligado por padrão (ver R-P1-5) |
| P2-1 código morto na projeção | **Fechado** | laço vazio removido; projeção reescrita |
| P2-3 inferência sem calibração | **Fechado** | confiança limitada pela menor premissa; premissa inexistente/refutada rejeitada |
| P3-1 docstring do catálogo | **Fechado** | `contracts/catalog.py` documenta 38 tipos |

Governança também foi corrigida: `ROADMAP.md`/`ARCHITECTURE.md` voltaram a **“em implementação”** e o checklist G3 tem a aprovação de QA como item **em aberto**.

### 2. P0 remanescentes

#### R-P0-1 — A suíte de aceite continua rotulando ATs com semântica diferente da ratificada

`tests/test_phase03_agents_and_g3.py` foi reescrito e passa, mas **9 dos 17 testes não exercitam o critério correspondente** de `spec.md` §4:

| Teste | O que faz | AT ratificado |
| :--- | :--- | :--- |
| `test_at02` (L152) | desconhecido → rejeitado; conhecido+crente → admitido | AT02: **conhecer sem acreditar** (`known` + `disbelieved`, `availability="known"`) |
| `test_at05` (L349) | herança de facção por membro leal | AT05: informação **`outdated`** distinta de `current` |
| `test_at06` (L413) | premissa refutada bloqueia nova inferência | AT06: **inferência registrada com premissas**, não promovida a fato |
| `test_at07` (L449) | replay determinístico | AT07: **membro descobre segredo que não se propaga** |
| `test_at08` (L477) | promoção `minor` → `major` | AT08: **segredo do jogador** bloqueado ao protagonista |
| `test_at10` (L529) | recursos e capacidades | AT10: **reconstrução + correção** preservando proveniência |
| `test_at12` (L576) | coesão de facção | AT12: **`outdated` não é falso** |
| `test_at13` (L611) | imutabilidade de tupla | AT13: **inferência com premissa refutada** permanece histórica |
| `test_at17` (L764) | portas `BehaviorPolicy`/`FactionPolicy` | AT17: **visibilidade** não vaza segredo |

Os demais são parciais: AT01 não registra crença falsa coexistindo com fato; AT03 não testa proveniência ausente (embora o código já rejeite); AT09 não verifica que a proposta rejeitada fica fora do estado; AT11 empacota as duas fontes em um único `knowledge.acquired`, codificação que o teste original não exigia; AT16 não compara bytes nem cobre `faccoes.md` ou snapshot.

Além disso, `EX-0025` afirma “17 testes integrados pelo `JsonlEventStore` real (com `store.append` e `rebuild_projections`)”. Seis testes (`AT03`, `AT06`, `AT10`, `AT13`, `AT14`, `AT17`) não tocam o store — constroem `KnowledgeRecord` ou `KnowledgeView` em memória.

**Consequência:** o gate G3 continua não verificado, apesar de 230 testes verdes e da afirmação de cobertura de 100%.

#### R-P0-2 — `KnowledgeView` não impede vazamento de segredo (AT17 falha)

As únicas barreiras em `query_claim` são `player_meta` para audiência `protagonist` e `protagonist_private` para terceiros (`resources/knowledge/view.py:134-149`). `holder_only`, `faction_internal` e `subgroup_only` não são confrontados com a audiência:

```text
holder_only -> self: known
holder_only -> protagonista: known   (esperado unavailable)
holder_only -> terceiro: known       (esperado unavailable)
faction_internal -> protagonista: known (esperado unavailable)
player_meta, audience=npc -> known   (esperado unavailable)
player_meta, audience=protagonist -> unavailable
```

O caso de `player_meta` é particularmente grave: basta a audiência não ser `protagonist` para o segredo do jogador aparecer para qualquer NPC ou facção. Não há teste cobrindo isso porque o “AT17” testa portas de política, não visibilidade.

**Consequência:** FR-G3-07 e AT17 não são atendidos; o contrato de leitura pode expor segredos de jogador/NPC/facção a qualquer audiência.

### 3. P1 remanescentes

#### R-P1-1 — Fábricas de conhecimento quebram para holders `player`, `protagonist` e `subgroup`

`make_knowledge_acquired_draft`, `make_knowledge_inferred_draft`, `make_knowledge_revised_draft` e `make_knowledge_shared_draft` derivam o ator de `ActorRef(kind=holder.kind, ...)` (`resources/knowledge/drafts.py:64,103,143,181`), mas `ActorRef` só aceita `human|agent|system|npc|faction`:

```text
player holder: ValueError actor.kind inválido: 'player'
subgroup from_holder: ValueError actor.kind inválido: 'subgroup'
```

**Consequência:** AT08 (segredo do jogador) e AT14 (compartilhamento por subgrupo) não podem ser construídos pela fábrica canônica, apenas contornando com `actor=` explícito ou montando `KnowledgeRecord` à mão — que é o que os testes fazem.

#### R-P1-2 — `resolve_claim` ainda decide por substring e aceita negação como afirmação

O ramo de `occurrence` continua montando `evt_text` e testando `prop.predicate in evt_text` (`resources/knowledge/resolver.py:104-112`):

```text
evento: "O capitao nao morreu na batalha"
claim:  capitao / morreu / ""
resultado: TRUE
```

**Consequência:** G3-D10 exige resolução determinística do fato canônico; a implementação atual é determinística, mas factualmente errada. A remediação anunciada como “comparação estrutural” não ocorreu neste ramo.

#### R-P1-3 — `contested` só existe quando as duas fontes estão no mesmo registro

A consolidação em `resources/knowledge/service.py:211-233` olha apenas `rec.provenance`. Duas aquisições separadas do mesmo `claim_id` pelo mesmo holder — o cenário natural de AT11 — permanecem `current`:

```text
rec1 (supports=True): current
rec2 (supports=False): current
(esperado: status consolidado "contested")
```

**Consequência:** FR-G3-08/AT11 só funciona na codificação artificial usada pelo teste (duas proveniências num único `knowledge.acquired`).

#### R-P1-4 — Estado projetado descarta campos exigidos por FR-AG-02/FR-AG-03

- `NpcState` (`resources/npcs/model.py:88-101`) não possui `location`, `condition` nem `commitments`, embora `npc.promoted`/`npc.updated` os carreguem e a projeção os colete e descarte.
- `FactionState` (`resources/factions/model.py:47-60`) não possui `collective_goals`, `influence`, `limitations` nem `internal_conflicts`, embora `faction.updated` os exija no payload.

```text
NpcState campos ausentes: ['location', 'condition', 'commitments']
FactionState campos ausentes: ['collective_goals', 'influence', 'limitations', 'internal_conflicts']
```

**Consequência:** o estado reconstruído não representa o que a spec manda persistir; os dados existem no log e são perdidos na projeção.

#### R-P1-5 — `faccoes.md` não é produzido pelo rebuild padrão, e o “AT16” não verifica bytes

`default_projectors(..., include_factions=False)` (`application/rebuild.py:24-35`) nunca inclui `FactionProjector` — nenhum chamador de `rebuild_projections` passa `include_factions=True` e a campanha não nasce com `faccoes.md`. O teste AT16 apenas verifica que `npcs.md` existe e contém o id, sem comparar hashes, sem `faccoes.md`, sem snapshot:

```text
hash rebuild 1 == 2: True | npcs.md byte-idêntico: True
faccoes.md gerado: False
```

**Consequência:** FR-AG-06 e AT16 não são demonstrados; a metade “facções” da projeção permanece código não executado em produção.

### 4. P2 remanescentes

1. **`inexistent` × `unknown`:** claim registrada em `knowledge.claim_registered` mas sem nenhum `KnowledgeRecord` retorna `inexistent` (`resources/knowledge/view.py:86-92`), quando o correto é `unknown` (a alegação existe; o holder não a conhece). A view não recebe o registro de claims.
2. **`build_view` não calcula `outdated`:** `DefaultKnowledgeProvider.build_view` chama `project_knowledge_state(events)` sem `current_time_sort` nem `claim_validity_map` (`resources/knowledge/view.py:268-269`); a transição só existe em chamadas diretas.
3. **Identidade de plano:** o fallback do replay gera `pln_<npc_id>`/`pln_<tag>` (`resources/npcs/service.py:126`, `resources/factions/service.py:108`), fora do formato documentado `pln_<ulid>`; dois planos do mesmo NPC colidem e só o último sobrevive em `active_plan`.
4. **Construtor polimórfico:** `KnowledgeView` aceita oito parâmetros posicionais em três formatos (`resources/knowledge/view.py:36-62`); chamadas posicionais com `(records, npc_affiliations)` passam a interpretar o segundo argumento como holder.
5. **`get_beliefs_of` sem audiência:** lista crenças sem aplicar a matriz de visibilidade (`resources/knowledge/view.py:192-227`), ao contrário de `query_claim`.
6. **Evidência de `EX-0025` superdimensionada:** “probes 100% aprovados” não se sustenta — as sondas são diagnóstico, não asserção, e continuam imprimindo `t=150 -> FALSE` e `faccoes.md gerado: False`.

### 5. Cobertura AT após a remediação

| AT | Teste atual | Veredito |
| :--- | :--- | :---: |
| AT01 fato vs crença | `test_at01` | Parcial |
| AT02 conhecer sem acreditar | `test_at02` | **Errado** |
| AT03 proveniência | `test_at03` (DAG/ciclo) | Parcial |
| AT04 informação falsa | `test_at04` | Passa |
| AT05 desatualização | `test_at05` (herança) | **Errado** |
| AT06 inferência | `test_at06` (refutação) | **Errado** |
| AT07 conhecimento coletivo | `test_at07` (replay) | **Errado** |
| AT08 segredo do jogador | `test_at08` (promoção) | **Errado** |
| AT09 proposta não admitida | `test_at09` | Parcial |
| AT10 reconstrução e correção | `test_at10` (recursos) | **Errado** |
| AT11 fontes contraditórias | `test_at11` | Parcial |
| AT12 desatualizado ≠ falso | `test_at12` (coesão) | **Errado** |
| AT13 inferência com premissa refutada | `test_at13` (imutabilidade) | **Errado** |
| AT14 facção dividida | `test_at14` | Passa |
| AT15 correção não reescreve crença | `test_at15` | Passa |
| AT16 replay e snapshot | `test_at16` | Parcial |
| AT17 visibilidade | `test_at17` (portas) | **Errado** |

**Aprovados de forma plena: 3 de 17 (AT04, AT14, AT15); errados: 9.**

### 6. Recomendação

1. Reescrever os 9 testes AT listados para a semântica de `spec.md` §4, incluindo AT02 (`known`+`disbelieved`), AT05/AT12 (`outdated` e `resolve_claim`), AT07/AT08 (não-propagação e segredo do jogador), AT10 (correção + rebuild), AT13 (premissa refutada) e AT17 (vazamento).
2. Implementar a matriz de visibilidade em `query_claim`: `holder_only`, `faction_internal`, `subgroup_only` e `player_meta` precisam ser confrontados com `audience` (não só `protagonist_private`/`player_meta`).
3. Corrigir a fábrica de drafts para holders `player`/`protagonist`/`subgroup` (mapear ator ou exigir `actor` explícito, com erro claro).
4. Substituir a decisão por substring no resolvedor por comparação estrutural com o evento/estado canônico.
5. Consolidar `contested` entre registros do mesmo `claim_id`/holder.
6. Expor os campos de FR-AG-02/FR-AG-03 nos modelos e incluir `faccoes.md` no rebuild padrão, com comparação byte a byte no teste.
7. Só então submeter nova rodada; a documentação de fase já está corretamente em “em implementação”.

**Reprodução da segunda rodada:**

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"
python .tmp/probe_phase03.py
python .tmp/probe_phase03b.py
python .tmp/probe_phase03c.py
python .tmp/probe_phase03d.py
```

---

## 0. Veredito

**Reprovado no G3; aprovado apenas o R2.**

A refatoração R2 é real e preserva comportamento: **229 testes OK** em 35,6 s, **8/8 testes de fronteira OK**, fachadas com 40–59 linhas, submódulos com 59–247 linhas e nenhum nome público perdido na comparação AST contra o `HEAD`.

O núcleo da Fase 03, porém, **não entrega o contrato ratificado no G3**. A camada epistêmica projeta **zero registros** a partir dos 5 eventos `knowledge.*` do catálogo, todas as fábricas de evento da fase produzem drafts que o **store real rejeita**, `KnowledgeView` não implementa `(holder, audience, purpose)` nem `availability`, e a suíte de aceite rotula AT01–AT17 com semântica diferente da ratificada em `g3-decision-record.md`.

| Gravidade | Qtd | Bloqueia a Fase 03 |
| :--- | :-: | :---: |
| P0 | 4 | Sim |
| P1 | 7 | Sim |
| P2 | 6 | Recomendado |
| P3 | 4 | Não |

**Conclusão curta:** os 229 testes verdes validam uma camada paralela auto-consistente que o pipeline real não consegue alimentar. O código novo não é alcançável por `lazy_turn.py`, `commit`, `prepare` ou `rebuild`; e, quando seria, o catálogo o rejeita.

---

## 1. O que foi verificado e passou (R2)

| Verificação | Resultado | Evidência |
| :--- | :---: | :--- |
| Suíte completa | **Passa** | `python -m unittest discover -s tests -p "test_*.py"` → `Ran 229 tests in 35.645s`, `OK` |
| Fronteiras AST | **Passa** | `python -m unittest tests.test_architecture_boundaries` → `Ran 8 tests`, `OK` |
| Fachadas `< 100` linhas | **Passa** | `council/quests.py` 34, `council/narrator.py` 40, `council/factions.py` 51 |
| Submódulos `< 300` linhas | **Passa** | `resources/knowledge/*` 93–182, `resources/npcs/*` 97–187, `resources/factions/*` 59–247, `resources/quests/*` 72–218, `resources/admission.py` 81, `plugins/agent_policies.py` 120 |
| Preservação de símbolos | **Passa** | Comparação AST `HEAD` × módulos extraídos: zero funções/classes/constantes ausentes em `narrator.py`, `factions.py` e `quests.py` |
| Plugins puros | **Passa** | `plugins/agent_policies.py` sem `open()` e sem imports de I/O |
| Catálogo estendido | **Passa** | `build_v1_catalog()` → 38 tipos (25 base + 13 da Fase 03) |

R2 pode ser mantido. Os achados abaixo tratam exclusivamente da camada de agentes/conhecimento e da documentação que a declara pronta.

---

## 2. P0 — Bloqueantes

### P0-1 — Os eventos da Fase 03 não podem ser persistidos; o store rejeita todos os drafts das fábricas

As fábricas em `resources/knowledge/service.py`, `resources/npcs/service.py`, `resources/factions/service.py` e `resources/admission.py` produzem drafts que `validate_draft_batch` recusa:

```text
knowledge.claimed    -> REJEITADO: UnknownEventTypeError: Tipo de evento desconhecido: 'knowledge.claimed'
npc.promoted         -> REJEITADO: SchemaError: Campo obrigatório ausente: 'from_tier'
proposal.rejected    -> REJEITADO: SchemaError: Campo obrigatório ausente: 'proposal_kind'
```

Detalhamento:

- `make_knowledge_claim_draft` (`resources/knowledge/service.py:147`) emite `knowledge.claimed`, tipo **ausente** de `contracts/catalog.py`. O catálogo registra `knowledge.claim_registered`, `knowledge.acquired`, `knowledge.inferred`, `knowledge.revised` e `knowledge.shared`.
- `make_npc_promoted_draft` (`resources/npcs/service.py:151`) envia `{npc_id, name, tier, archetype, capabilities}`; o schema exige `npc_id`, `from_tier` e `to_tier` (`contracts/catalog.py:161`).
- `make_proposal_rejected_draft` (`resources/admission.py:67`) não envia `proposal_kind`, exigido em `contracts/catalog.py:189`.
- `make_faction_leadership_draft` (`resources/factions/service.py:169`) emite `faction.leadership_changed`, tipo **ausente** do catálogo; `faction.subgroup_created` (usado em `resources/factions/service.py:80` e no teste AT14) também não existe — o catálogo tem `faction.subgroup_updated`.

**Consequência:** nenhum fato epistêmico, promoção de NPC, rejeição de proposta ou mudança de liderança pode entrar no event log. Como o log é a única fonte de verdade (G3-D13), o estado da fase nunca existe em campanha real.

### P0-2 — A projeção epistêmica ignora os 5 eventos canônicos e só entende tipos que não existem

`project_knowledge_state` (`resources/knowledge/service.py:20`) trata `knowledge.claimed`, `knowledge.disputed`, `knowledge.validated`, `knowledge.retracted` e `knowledge.refuted`. Nenhum deles está no catálogo; os cinco canônicos não são tratados:

```text
catalogo: ['knowledge.acquired', 'knowledge.claim_registered', 'knowledge.inferred', 'knowledge.revised', 'knowledge.shared']
tratados pela projeção: []
knowledge.acquired -> registros reconstruídos: 0
knowledge.inferred -> registros reconstruídos: 0
knowledge.revised  -> registros reconstruídos: 0
knowledge.shared   -> registros reconstruídos: 0
```

O mesmo desalinhamento atinge o domínio de agentes:

| Módulo | Tipos consumidos | Situação no catálogo |
| :--- | :--- | :--- |
| `resources/npcs/service.py:80` | `npc.goal_set` | não existe (catálogo: `npc.goal_updated`) |
| `resources/npcs/service.py:119` | `npc.relationship_mutated` | não existe (catálogo: `npc.relationship_updated`) |
| `resources/factions/service.py:50` | `faction.leadership_changed` | não existe |
| `resources/factions/service.py:80` | `faction.subgroup_created` | não existe (catálogo: `faction.subgroup_updated`) |
| `resources/factions/service.py` | `faction.updated` | **não tratado** |
| `application/projectors/npc.py` | `npc.goal_set`, `npc.relationship_mutated` | não existem |

**Consequência:** AT07, AT10, AT14, AT15 e AT16 não podem ser satisfeitos com eventos válidos. Os testes passam porque fabricam o tipo que a projeção espera, não o tipo que a spec define.

### P0-3 — `KnowledgeView` não implementa o contrato ratificado

`KnowledgeView` (`resources/knowledge/view.py:17`) tem assinatura `(records, npc_affiliations)`:

```text
KnowledgeView(holder, audience, purpose) -> TypeError: __init__() takes from 2 to 3 positional arguments but 4 were given
ClaimQueryResult existe em resources/: False
```

Não há `availability` (`known | unknown | unavailable | inexistent`), não há distinção de audiência e `DefaultKnowledgeProvider.build_view(events, holder_kind, holder_id, audience_kind, audience_id, purpose)` (`resources/knowledge/view.py:112`) **descarta os seis parâmetros** e devolve uma view sem holder.

**Consequência:** FR-G3-07, AT02 e AT17 não são implementáveis. Não existe API capaz de responder “o protagonista pode ver este segredo do jogador?”; a única filtragem existente é “não devolva registros de outro holder”, que não é o critério de visibilidade.

### P0-4 — A suíte de aceite não corresponde aos ATs ratificados e a documentação foi autodeclarada aprovada

`tests/test_phase03_agents_and_g3.py` tem 17 testes e todos passam, mas 9 deles verificam outra coisa:

| Teste | O que testa | AT ratificado (spec §4) |
| :--- | :--- | :--- |
| `test_at02_...` | admissão exige crença | AT02: conhecer sem acreditar (`known` + `disbelieved`) |
| `test_at05_...` | herança coletiva de facção | AT05: informação `outdated` distinta de `current` |
| `test_at07_...` | replay de `knowledge.claimed` | AT07: membro descobre segredo que não se propaga |
| `test_at08_...` | promoção `minor` → `major` | AT08: segredo do jogador bloqueado ao protagonista |
| `test_at10_...` | guarda de recursos/capacidades | AT10: reconstrução + correção preservando proveniência |
| `test_at11_...` | `knowledge.disputed` → `contested` | AT11: duas fontes contraditórias coexistem |
| `test_at12_...` | coesão de facção | AT12: `outdated` não é falso |
| `test_at16_...` | estado de `NpcState` em memória | AT16: replay/snapshot byte-idêntico de `npcs.md`/`faccoes.md` |
| `test_at17_...` | portas de política | AT17: visibilidade não vaza segredo |

Além disso, `checklists/g3-ratification.md` foi editado pelo implementador para marcar “Spec 012 escrita e aprovada” e substituir a assinatura de ratificação por “Ratificação aprovada e implementada com sucesso”, e `ROADMAP.md`/`ARCHITECTURE.md` passaram a declarar a Fase 03 “concluída e aprovada” com base nessa suíte. `EX-0023` afirma cobertura “individualmente [d]os 17 critérios de aceitação”, o que as sondas desmentem.

**Consequência:** o gate G3 não foi verificado; os documentos canônicos registram um estado falso. Antes de qualquer correção de código, essas declarações precisam ser revertidas.

---

## 3. P1 — Bloqueantes de confiabilidade

### P1-1 — Proveniência ausente é aceita (AT03)

`validate_provenance_chain` não exige `provenance` não vazia:

```text
KnowledgeRecord(provenance=(), derived_from=()) -> validate_provenance_chain: (True, [])
```

`resources/knowledge/provenance.py:58` só valida dependências declaradas; um registro sem fonte alguma passa. AT03 (“rejeita conhecimento sem proveniência”) falha. O teste `test_at03` cobre apenas ciclo.

### P1-2 — `outdated` nunca é produzido e janela expirada vira `FALSE`

Não há transição para `outdated` em `project_knowledge_state`; o bloco de expiração (`resources/knowledge/service.py:137-142`) é código morto:

```python
valid_to = p.get("valid_to") if (rec.claim_id and False) else None
```

O resolvedor, por sua vez, converte expiração em falsidade:

```text
resolve_claim(state, valid_from=10, valid_to=100)
t=50  -> TRUE
t=150 -> FALSE
```

AT05/AT12 exigem que a informação antiga permaneça registrada como `outdated` e **não** seja classificada como falsa no período em que valeu. O resolvedor viola a distinção.

### P1-3 — Fontes contraditórias não geram `contested` (AT11)

O único caminho para `contested` é o evento não canônico `knowledge.disputed`. Duas proveniências com `supports=True`/`supports=False` sobre o mesmo `claim_id` produzem registros `current` independentes; `ProvenanceRef.supports` é lido em nenhum ponto da projeção. O teste AT11 usa o evento inventado, não o cenário ratificado.

### P1-4 — Admissão ignora autoridade de facção e confunde conhecer com crer

`validate_intent_admission` (`resources/admission.py:18`) verifica crença, capacidades e recursos. Não verifica:

- `intent.acts_for_faction` e liderança/autoridade (`FactionLeadership`) — FR-AG-04 exige validação de autoridade para ações de facção;
- condição/localização (`intent.location` é ignorado);
- `awareness == known` separado de `stance` — usa `is_believed`, que exige `believed`.

Provas:

```text
known+disbelieved -> admitted: (False, ["EPISTEMIC_UNSATISFIED: ..."])
intent acts_for_faction sem liderança -> admitted: True, erros: []
```

O primeiro caso é exatamente AT02 (conhecer sem acreditar): o agente sabe que a ponte caiu, não acredita, e o motor o impede de usar a informação. O segundo permite que qualquer NPC aja em nome de uma facção que não lidera.

### P1-5 — Replay não é determinístico; byte-identidade impossível (AT16/G3-D13)

As projeções geram IDs quando o payload não os traz (`new_knowledge_id()` em `resources/knowledge/service.py:38`; `new_plan_id()` em `resources/npcs/service.py:111` e `resources/factions/service.py:143`). Como os ULIDs são aleatórios (`kernel/ids.py`), duas execuções do mesmo log divergem:

```text
plan_id run1: pln_01M5W8N3VGM4ZNC846AYRPC0TT
plan_id run2: pln_01M5W8N3VGM4ZNC846AYRPC0TV
deterministico: False

knowledge.claimed sem record_id -> chaves run1 != run2
```

Rebuild a partir do mesmo `events/` não reproduz o mesmo estado, muito menos `npcs.md`/`faccoes.md` byte-idênticos.

### P1-6 — `knowledge.shared` não existe na prática (AT07/AT14)

O evento canônico de compartilhamento não é projetado; `KnowledgeView.get_beliefs_of` (`resources/knowledge/view.py:29`) só agrega conhecimento coletivo que **já exista** como registro de facção/subgrupo. Sem `knowledge.shared`, não há como criar esse registro, e não há teste de “membro descobre segredo e os demais não passam a conhecê-lo”.

### P1-7 — Nenhuma integração com o pipeline real

Busca por chamadores fora de `tests/`:

- `project_knowledge_state`, `validate_intent_admission`, `project_npcs_state` e `project_factions_state` são referenciados apenas nos próprios módulos e na suíte de aceite;
- `FactionProjector` é opcional (`application/rebuild.py:24`, `include_factions: bool = False`) e nenhum chamador passa `include_factions=True`; `faccoes.md` nunca é gerado por `rebuild` padrão;
- `bootstrap.py` registra as portas, mas nada consome `knowledge_provider`, `behavior_policy` ou `faction_policy`.

Parte do consumo por `prepare` é escopo da Fase 04 (spec §2.2), mas a projeção de `faccoes.md` e o registro dos eventos no commit são escopo desta fase (FR-AG-06, T032, T034).

---

## 4. P2 / P3

### P2

1. **Código morto na projeção:** `resources/knowledge/service.py:137-142` (laço que não faz nada) e `contradicted_event` em `resources/knowledge/resolver.py:86`, nunca atribuído — o ramo `if contradicted_event: return "FALSE"` é inalcançável.
2. **Resolvedor por substring:** `resolve_claim` casa `subject`/`predicate`/`object` via `in str(payload)` (`resources/knowledge/resolver.py:98-102`). Predicados como “morreu” casam com “não morreu”; não há comparação estrutural com o fato canônico.
3. **`confidence` de inferência sem teto:** o docstring de `validate_provenance_chain` promete bloquear inferência com `confidence=10000` sem premissas canônicas; a checagem não existe.
4. **Testes contornam o store:** `_wrap_draft` (`tests/test_phase03_agents_and_g3.py:64`) constrói `Event` à mão; nenhum teste passa por `validate_draft_batch`, `JsonlEventStore.append` ou `rebuild`.
5. **`build_view` ignora holder/audiência:** além do P0-3, o parâmetro `events` é aceito mas a view resultante não guarda o holder consultado.
6. **`is_claim_believed` trata `contested` como crença ativa** (`resources/knowledge/view.py:83`), o que confunde “crença” com “disputa em aberto”.

### P3

1. `contracts/catalog.py:1` ainda diz “25 tipos canônicos”; o catálogo tem 38.
2. `resources/knowledge/model.py:28-39`: `HolderRef.id` valida tipo mas não normaliza; `HolderRef("npc", "")` levanta erro genérico no meio do replay.
3. `resources/factions/service.py:28` cria facção a partir de `faction.reputation_changed` sem usar o payload — entrada fantasma no mapa.
4. `tests/test_phase03_agents_and_g3.py:1-21` documenta os ATs com a semântica errada (ver P0-4), o que induz o próximo leitor ao erro.

---

## 5. Critérios de aceite — resultado independente

| AT | Resultado | Evidência |
| :--- | :---: | :--- |
| AT01 fato vs crença | **Parcial** | `resolve_claim` resolve `fact_ref`; nenhum teste registra crença real e a mantém contra o fato |
| AT02 conhecer sem acreditar | **Falha** | `known` + `disbelieved` é rejeitado na admissão; sem `availability` |
| AT03 proveniência | **Falha** | Ciclo detectado; registro sem proveniência aceito |
| AT04 informação falsa | **Passa (isolado)** | Crença falsa admite intenção e `resolve_claim` permanece `FALSE` |
| AT05 desatualização | **Falha** | `outdated` nunca é emitido |
| AT06 inferência | **Parcial** | `ProvenanceRef` exige premissa; `knowledge.inferred` não é projetado |
| AT07 conhecimento coletivo | **Falha** | `knowledge.shared` não projetado; sem teste de não-propagação |
| AT08 segredo do jogador | **Falha** | Sem audiência/visibilidade; o teste cobre promoção de NPC |
| AT09 proposta não admitida | **Parcial** | Validação funciona; `proposal.rejected` inválido no schema; replay não é testado |
| AT10 reconstrução + correção | **Falha** | Eventos canônicos geram zero registros |
| AT11 fontes contraditórias | **Falha** | Só via `knowledge.disputed` (não canônico) |
| AT12 desatualizado ≠ falso | **Falha** | Janela expirada retorna `FALSE` |
| AT13 inferência sobre premissa refutada | **Passa (isolado)** | `InvalidPremiseError`; `derived_from` preservado |
| AT14 facção dividida | **Parcial** | Subgrupo e lealdade existem; compartilhamento restrito não existe |
| AT15 correção não reescreve crença | **Parcial** | Lógica correta, exercitada com `knowledge.claimed` inválido |
| AT16 replay e snapshot | **Falha** | IDs aleatórios no replay; nenhum teste de projeção/snapshot |
| AT17 visibilidade | **Falha** | `KnowledgeView` sem audiência/`availability` |

**Aprovados de forma plena: 2 de 17 (AT04, AT13).**

---

## 6. Por que 229 testes verdes não aprovam a fase

1. A suíte nova valida funções isoladas com eventos que o catálogo não aceita.
2. Nenhum teste atravessa `JsonlEventStore.append` → `rebuild` → Markdown.
3. As asserções de AT foram escritas para o que o código faz, não para o que o G3 ratificou.
4. As garantias estruturais (R2) são reais, mas independentes do contrato epistêmico.
5. A documentação de fase foi promovida a “aprovada” pelo próprio implementador, sem QA independente.

---

## 7. Recomendação e ordem de correção

1. **Reverter as declarações de status:** `ROADMAP.md` (Fase 03), `ARCHITECTURE.md` e `checklists/g3-ratification.md` voltam a “em implementação”; a assinatura de ratificação não pode ser reescrita pelo implementador.
2. **Alinhar o contrato de eventos:** escolher uma única nomenclatura — a do catálogo — e corrigir fábricas, projeções e projectors; os drafts precisam passar em `validate_draft_batch`.
3. **Reescrever `project_knowledge_state`** para `claim_registered`, `acquired`, `inferred`, `revised` e `shared`, com `outdated`, `contested` e isolamento de `correction.issued`.
4. **Implementar `KnowledgeView(holder, audience, purpose)` + `ClaimQueryResult.availability`**, com testes de vazamento entre NPC, facção, protagonista e jogador.
5. **Corrigir a admissão:** `awareness` separado de `stance`, autoridade de facção, localização e condição.
6. **Eliminar geração de IDs no replay** (exigir ID no payload ou derivar deterministicamente do evento).
7. **Refazer a suíte de aceite** com um teste por AT ratificado, atravessando store e rebuild; só então registrar nova execução.

---

## 8. Reprodução

```powershell
# suíte e fronteiras
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"
python -m unittest tests.test_architecture_boundaries

# sondas usadas nesta auditoria
python .tmp/probe_phase03.py
python .tmp/probe_phase03b.py
```

As sondas (ignoradas pelo git, em `.tmp/`) verificam: tipos do catálogo × tipos projetados; `validate_draft_batch` de cada fábrica; projeção dos eventos canônicos; assinatura de `KnowledgeView`; `awareness`/`belief` e autoridade na admissão; determinismo de replay; janela temporal no resolvedor. Elas não alteram o repositório.

**Arquivos auditados:** `resources/knowledge/{model,provenance,resolver,service,view}.py`, `resources/admission.py`, `resources/npcs/{model,service}.py`, `resources/factions/{model,service}.py`, `resources/quests/*`, `plugins/agent_policies.py`, `contracts/{ports,catalog}.py`, `kernel/ids.py`, `bootstrap.py`, `application/projectors/{npc,faction}.py`, `application/rebuild.py`, `council/{narrator,factions,quests}.py`, `tests/test_phase03_agents_and_g3.py`, `tests/test_architecture_boundaries.py`, `specs/012-phase-03-agents/*`, `ROADMAP.md`, `ARCHITECTURE.md`, `EXECUCAO.md`.
