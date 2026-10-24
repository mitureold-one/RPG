# Gate Specification: 010 — Fase 02: História Causal (G1/G2)

**Feature Name:** `phase-02-causal-history`
**Status:** Ready for Planning — G1/G2 ratificados com ajustes em 23/10/2026
**Ratificação:** [`checklists/g1-g2-ratification.md`](checklists/g1-g2-ratification.md)
**Created:** 2026-10-23
**Target:** Fase 02 do [`ROADMAP.md`](../../ROADMAP.md) e etapa R1 da refatoração
**Base analisada:** [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §2 (D1/D2/D4), §5.0–§5.4, §8, §11; [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 02) e §5 (gates); [`contracts/event.py`](../../contracts/event.py); [`contracts/ports.py`](../../contracts/ports.py); [`EXECUCAO.md`](../../EXECUCAO.md) `EX-0011`; [`QA-FASE-01.md`](../../QA-FASE-01.md).

> **Regra deste documento:** G1 e G2 foram ratificados com ajustes em 23/10/2026. Os ajustes estão consolidados nas seções 2.3 e 3.3 e no checklist de ratificação. O R1 só começa depois de `plan.md`/`tasks.md` e dos critérios complementares C1–C4 (seção 4.1). A Fase 02 não pode ser declarada concluída sem esses critérios ([`ROADMAP.md`](../../ROADMAP.md) §5).

---

## 0. Leitura rápida

- São **12 decisões de G1** e **10 de G2**, todas ratificadas em 23/10/2026; oito de G1 e seis de G2 têm ajuste incorporado.
- As cinco decisões que mais impactam o resto: **Q1** (catálogo de eventos), **Q3** (lote/índice), **Q5** (correção/compensação), **Q7** (prosa) e **Q10** (quem escreve o Markdown).
- O que já está fixo não volta à mesa: JSONL, `evt_<ulid>`, envelope, `expected_last_seq`, projeções reconstruíveis e D4 (sem migração).
- Quatro critérios complementares de R1 (seção 4.1) não são gates: falha de persistência em posições, dependências intra-lote, hash de auditoria independente e correção contraditória.
- Se tudo for implementado como ratificado, o R1 começa pelo `EventStore` JSONL, projeções e rebuild; sem catálogo fechado, não há como começar.

---

## 1. Contexto e problema

### 1.1 Onde o projeto está

O R0/R0.5 entregou a fundação: `contracts/`, `kernel/`, `bootstrap.py`, CLI extraída, persistência atômica, lock cooperativo, fixtures e 157 testes verdes. O motor já sabe **validar e escrever Markdown**, mas ainda não sabe **registrar a história causal**:

- `commit` grava o resultado diretamente em `ficha.md`, `diario.md` e `npcs.md`; não há evento;
- não há reconstrução a partir de uma fonte imutável;
- não há correção: o passado só pode ser sobrescrito;
- não há grafo de dependências entre fatos;
- não há prosa original recuperável por turno;
- não há retomada idempotente após interrupção.

A Fase 02 existe para transformar “Markdown mutável” em “log append-only + projeções reconstruíveis”, sem perder o que já funciona.

### 1.2 O que já está decidido — não reabrir

Estas escolhas estão fixadas no [`ARCHITECTURE.md`](../../ARCHITECTURE.md) e o G1 apenas as ratifica, não as rediscute ([`ROADMAP.md`](../../ROADMAP.md) §5: “G1 não reabre o que o ARCHITECTURE já fixou”):

1. **D1:** o event log é a verdade; `diario.md`, `ficha.md` e `npcs.md` são projeções; `mundo.md` e `regras.md` são configuração.
2. **D2:** JSONL canônico por campanha; SQLite é índice derivado e reconstruível; snapshots periódicos.
3. **D4:** campanhas antigas são descartadas; não há migração nem `campaign.imported`; a primeira campanha nova começa com `campaign.created`.
4. **Envelope do evento:** `event_id` (`evt_<ulid>`), `campaign_id`, `seq` monotônico, `type`, `schema_version`, `recorded_at` UTC, `game_time`, `game_time_sort`, `actor`, `causation_id`, `correlation_id`, `payload`, `meta` ([`ARCHITECTURE.md`](../../ARCHITECTURE.md) §5.1).
5. **Identidade e ordem:** `event_id`, `seq` e `recorded_at` são atribuídos pelo `EventStore`, sob o mesmo lock da escrita; a aplicação só produz `EventDraft` ([`ARCHITECTURE.md`](../../ARCHITECTURE.md) §5.0.1).
6. **Concorrência:** `expected_last_seq` é comparado dentro de `append()`, na mesma seção crítica; divergência vira `SeqConflictError`.
7. **Atomicidade:** `append()` é all-or-nothing; nenhum leitor observa lote parcial. O mecanismo é decisão do G1.
8. **Serialização:** JSON canônico (`sort_keys`, sem `NaN`) é a forma de igualdade e hash.
9. **Projeções:** projectors registrados, ordenados, com checkpoint; rebuild sem duplicar efeitos.
10. **Portas e composição:** `bootstrap.py` é o único composition root; registry congelado; kernel sem I/O.

### 1.3 O que falta — objeto deste documento

**G1** fecha o contrato do evento: payloads, serialização/versionamento, retenção, mecanismo de lote e layout do log.

**G2** fecha a política de correção, dependências, reconstrução e efeitos sobre a história já persistida.

### 1.4 Fora de escopo

- migrar ou importar campanhas antigas (D4);
- comportamento de NPCs, facções, contexto, simulação, diretor e memória derivada (Fases 03–07);
- chamadas a LLM dentro do motor;
- UI, multiusuário, sincronização em rede;
- reescrever prosa antiga;
- decidir orçamento/retry da fila (G4, Fase 05).

---

## 2. G1 — Contrato do Evento

### 2.1 Resumo das decisões ratificadas

| ID | Decisão | Status |
| :--- | :--- | :---: |
| G1-D1 | JSONL canônico por campanha; SQLite derivado opcional na Fase 02 | Ratificado com ajuste |
| G1-D2 | Lote atômico por marcadores `batch.open`/`batch.committed` no segmento | Ratificado com ajuste |
| G1-D3 | Envelope congelado; `target`/`preconditions`/`result`/`costs` no payload; dependências em `meta.dependencies` | Ratificado com ajuste |
| G1-D4 | `game_time` e `game_time_sort` obrigatórios no `EventDraft`; sem default inventado pelo store | Ratificado |
| G1-D5 | `batch_id` = `bat_<ulid>`; `correlation_id` por unidade de trabalho (`turn_`, `cmd_`, `campaign_`); `causation_id` = evento direto | Ratificado |
| G1-D6 | Serialização UTF-8, LF, sem BOM, um objeto JSON por linha; hashes SHA-256 do evento e do lote | Ratificado com ajuste |
| G1-D7 | `schema_version` por `EventType`, upcasters `N→N+1`, versão futura rejeitada | Ratificado |
| G1-D8 | Retenção integral; segmento a cada 1.000 eventos ou 1 MB; snapshot a cada 500 eventos ou fechamento de arco | Ratificado com ajuste |
| G1-D9 | Catálogo mínimo de tipos de evento v1 (G1-D9) | Ratificado com ajuste |
| G1-D10 | `EventType` registrado e validado; tipo desconhecido rejeitado no append | Ratificado com ajuste |
| G1-D11 | Layout `events/`, `snapshots/`, `projections/`, `artifacts/prose/`, `queue.jsonl` | Ratificado |
| G1-D12 | Nenhuma mutação de estado sem evento correspondente | Ratificado com ajuste |

### 2.2 Detalhamento

> O texto abaixo é a proposta original; os ajustes ratificados na seção 2.3 prevalecem em caso de diferença.

#### G1-D1 — JSONL canônico, índice opcional

- Cada campanha tem `events/000001.jsonl`, `000002.jsonl`, ... Segmentos append-only.
- A verdade é o JSONL. `index.sqlite` é derivado e pode ser apagado/rebuildado; a Fase 02 **não depende** dele para `read`/`last_seq`/`prepare`. Se o índice não existir, a leitura varre os segmentos.
- O índice só passa a ser obrigatório quando houver consulta que não caiba na leitura sequencial; isso pode ficar para R1 tardio ou Fase 03.

**Recomendação:** JSONL obrigatório; SQLite opcional na Fase 02. **Ratificação:** Q3 aceita com ressalva (recuperação de lote incompleto testada).

#### G1-D2 — Lote atômico por marcadores

O segmento contém dois tipos de linha:

```json
{"record":"batch","state":"open","batch_id":"bat_01J...","first_seq":7,"event_count":3}
{"record":"event","event_id":"evt_01J...","campaign_id":"...","seq":7,...}
{"record":"event","event_id":"evt_01J...","campaign_id":"...","seq":8,...}
{"record":"event","event_id":"evt_01J...","campaign_id":"...","seq":9,...}
{"record":"batch","state":"committed","batch_id":"bat_01J...","last_seq":9,"hash":"sha256:..."}
```

Regras:

1. O escritor adquire o lock, atribui `seq`, grava `open`, os eventos e, por último, `committed`; faz `fsync` antes de liberar.
2. Um leitor só aceita eventos de um lote com `committed` correspondente. Lote sem `committed` (crash) é invisível.
3. Na recuperação, o store trunca o segmento até o último `committed` **antes** de qualquer novo append; se preferir não truncar, precisa garantir que nenhum lote posterior seja gravado atrás de um lote incompleto.
4. `hash` é o SHA-256 da concatenação dos JSONs canônicos dos eventos do lote; serve para detectar corrupção.
5. Lote vazio não cria marcadores e devolve `AppendResult(events=(), first_seq=atual, last_seq=atual)`.
6. `record` é um campo do arquivo, não do `Event`: ao ler, o store remove `record` e reconstrói o `Event` canônico. O hash do lote usa o JSON sem `record`.

**Alternativa considerada:** um arquivo por lote (`events/000001.jsonl` por lote) com `os.replace` atômico. É mais simples de ler, mas multiplica arquivos e conflita com a segmentação por volume. **Ratificação:** marcadores aceitos; recuperação de lote incompleto é critério de teste (Q3).

#### G1-D3 — Onde ficam alvo, pré-condições, resultado, custos e dependências

O envelope fica congelado. Nada de novo campo obrigatório em `Event`/`EventDraft`:

- `payload.target`: `{kind, id}` quando o evento tem alvo (NPC, facção, missão, relógio);
- `payload.preconditions`: lista de strings verificáveis;
- `payload.result`: objeto específico do tipo (`success`/`failure`, grau, margem, etc.);
- `payload.costs`: objeto (`hp`, `stamina`, `xp`, `time`, ...);
- `payload.state`: `proposta`, `tentativa`, `concluída`, `rejeitada`, `adiada` ou `abandonada`, quando o tipo representar ciclo de vida;
- `meta.dependencies`: lista de `event_id` dos eventos dos quais este depende;
- `meta.correction_id`: presente quando o evento é compensação de uma correção;
- `meta.policy`, `meta.seed`, `meta.context_hash`: quando houver plugin/LLM, conforme [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §6.4.

**Ratificação:** Q2 aceita; o envelope permanece estável.

#### G1-D4 — `game_time` obrigatório

`EventDraft.game_time` e `game_time_sort` passam a ser **obrigatórios no `EventDraft` e no append**. O store não inventa data (o `FakeEventStore` atual usa `01 de Janeiro de 304` como default — isso mascara erro de aplicação e deve sair). A aplicação calcula via `CalendarProvider` antes de montar o lote.

#### G1-D5 — IDs e correlação

- `event_id`: `evt_<ulid>` (já fixado).
- `batch_id`: `bat_<ulid>`.
- `correlation_id`: identificador da unidade de trabalho; recomendação `turn_000001` (6 dígitos, crescente) para turnos, `cmd_<ulid>` para comandos fora do turno e `campaign_<id>` para `campaign.created`.
- `causation_id`: `event_id` do evento que causou diretamente este; `null` quando não houver.
- `campaign_id`: validado como no R0 (`^[a-z0-9_][a-z0-9_-]*$`).

#### G1-D6 — Serialização canônica

- UTF-8, sem BOM, quebras `\n`.
- Um objeto JSON por linha; sem pretty-print.
- `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, `allow_nan=False`.
- **Hash do evento:** `sha256(canonical_json(event))`, prefixado `sha256:`.
- **Hash do lote:** `sha256` da concatenação dos `canonical_json(event)` em ordem de `seq`, também prefixado `sha256:`. Os dois hashes são distintos e verificáveis separadamente.
- Números: inteiros e floats finitos; `bool` não é `int` na validação de schema.

#### G1-D7 — Versionamento

- `schema_version` é por `EventType`, começa em 1.
- `upcasters` mapeiam `N → N+1`; a leitura aplica a cadeia até a versão atual antes de projetar.
- Versão **maior** que a suportada é rejeitada com `SchemaError`; nunca é ignorada.
- Campos não são removidos silenciosamente; renomear exige upcaster.
- `api_version` da porta `EventStore` sobe apenas em quebra de contrato.

#### G1-D8 — Retenção

- Nenhum evento é apagado no fluxo normal.
- Segmento novo a cada 1.000 eventos ou 1 MB, o que vier primeiro.
- Snapshot a cada 500 eventos ou no fechamento de arco.
- Segmentos antigos podem ser arquivados (movidos), nunca reescritos.
- `rebuild` = snapshot mais recente + eventos seguintes.
- Sem horizonte de expiração na Fase 02.

#### G1-D9 — Catálogo mínimo de eventos v1

O catálogo abaixo cobre as mutações que hoje existem em `diario.md`, `ficha.md` e `npcs.md`. **Qualquer mutação nova exige um `EventType` registrado e schema validado.**

| Tipo | `payload.state` | Payload mínimo | `meta.dependencies` |
| :--- | :--- | :--- | :--- |
| `campaign.created` | concluída | `title`, `system`, `calendar`, `start_game_time`, `config_version` | — |
| `command.executed` | concluída | `command`, `args`, `status`, `summary` | — |
| `turn.proposed` | proposta | `turn`, `action`, `summary`, `stakes`, `dc`, `stat`, `target`, `preconditions` | — |
| `turn.rejected` | rejeitada | `turn`, `reasons` | `turn.proposed` |
| `action.resolved` | tentativa | `turn`, `result`, `outcome`, `costs`, `effects` | `turn.proposed` |
| `turn.committed` | concluída | `turn`, `summary`, `scene_type`, `location`, `present`, `vitals`, `costs` | `turn.proposed`, `action.resolved` (quando houver) |
| `clock.created` | concluída | `name`, `max`, `trigger` | — |
| `clock.advanced` | concluída | `name`, `steps`, `current`, `max`, `status` | evento causal |
| `clock.resolved` | concluída | `name`, `status`, `xp_granted` | evento causal |
| `quest.created` | concluída | `quest_id`, `title`, `type`, `contractor`, `clock`, `reward` | — |
| `quest.objective_completed` | concluída | `quest_id`, `objective_index`, `xp_granted` | evento causal |
| `quest.completed` | concluída | `quest_id`, `xp_granted`, `contractor_rep` | evento causal |
| `quest.failed` | concluída | `quest_id`, `reason`, `contractor_rep` | evento causal |
| `quest.status_changed` | concluída | `quest_id`, `from`, `to`, `reason` | evento causal |
| `arc.updated` | concluída | `title`, `question`, `stage`, `scene_name`, `date_time`, `location`, `present` | evento causal |
| `scene.planned` | concluída | `beat`, `scene_type`, `actors` | evento causal |
| `scene.completed` | concluída | `index` | evento causal |
| `npc.updated` | concluída | `npc_id`, `changes` | evento causal |
| `faction.reputation_changed` | concluída | `faction`, `delta_rep`, `new_score`, `favors`, `debts`, `reason` | evento causal |
| `protagonist.progression_changed` | concluída | `xp_delta`, `xp_total`, `level`, `attribute_points`, `ability_points`, `source` | evento causal |
| `protagonist.sheet_changed` | concluída | `kind`, `target`, `new_value`, `points_remaining`, `source` | evento causal |
| `prose.recorded` | concluída | `turn`, `text_hash`, `text_path`, `source`, `bytes`, `scene_type` | `turn.committed` |
| `correction.issued` | concluída | `corrects`, `reason`, `changes`, `state` | eventos corrigidos |
| `correction.recomputed` | concluída | `correction_id`, `affected`, `outcome` | `correction.issued` |
| `projection.rebuilt` | concluída | `from_seq`, `to_seq`, `projection_version`, `hash` | — |

Observações:

- `command.executed` cobre comandos que mudam estado fora do `commit` (`clock`, `quest`, `faction`, `progress`, `plan`, `arc`). Os eventos de recurso dependem dele.
- `turn.proposed`/`turn.rejected`/`action.resolved` materializam “proposta” e “tentativa”; `turn.committed` materializa o fato.
- `quest.status_changed` cobre BLOCKED/UNBLOCKED/ABANDONED/REOPENED; `quest.completed`/`quest.failed` ficam separados por causa do XP e da reputação de contratante.
- `protagonist.sheet_changed` cobre mutações de ficha que não são XP (gastar atributo, aprender habilidade, adicionar item/marco, vital alterado fora de `turn.committed`). Se o dono preferir tipos específicos, é a decisão Q1.
- `faction.reputation_changed` projeta em `ficha.md`; criação/alteração estrutural de facção em `mundo.md` fica para R2/Fase 03, quando `faccoes.md` existir.
- `arc.updated`, `scene.planned` e `scene.completed` existem para reconstruir o diário sem depender de escrita manual.
- `prose.recorded` guarda hash e caminho; o texto completo fica em `artifacts/prose/` (G6 decide indexação/recuperação).
- `projection.rebuilt` é um evento de auditoria; não altera estado de jogo.

**Ratificação:** Q1 com ajuste; Q7 aceita (indexação em G6).

#### G1-D10 — Registro e validação

- Todo `EventType` é registrado explicitamente no `bootstrap.py`/`kernel` (sem descoberta automática).
- `append` valida: tipo registrado, `schema_version` compatível, payload contra `payload_schema`, `game_time` presente, `actor` válido, `meta.dependencies` existentes (quando declaradas).
- Tipo desconhecido ou payload inválido → erro tipado; nada é gravado.
- O kernel não ganha `if event_type == ...`; cada recurso declara seu `EventType`.

#### G1-D11 — Layout

```text
campaigns/<id>/
  events/
    000001.jsonl          # segmento com marcadores de lote + eventos
    000002.jsonl
  snapshots/
    000001.json           # {last_seq, state_hash, projection_hash, ...}
  projections/
    diario.md
    ficha.md
    npcs.md
  artifacts/
    prose/
      turn_000001-<hash>.md
  queue.jsonl             # fila esqueleto (G2-D7)
  index.sqlite            # opcional/derivado
  mundo.md                # configuração
  regras.md               # configuração
```

`mundo.md` e `regras.md` continuam configuração; `faccoes.md` só entra em R2. Campanhas legadas em `archive/` não são migradas.

#### G1-D12 — Nenhuma mutação sem evento

- Nenhum `write_text` de projeção fora do `ProjectionWriter`.
- Nenhum comando mutador sem emitir `command.executed` + eventos de recurso.
- Edição manual de projeção é exceção operacional e exige `import-md` (fora do escopo da Fase 02); sem `import-md`, o rebuild sobrescreve a edição e registra divergência.

---

### 2.3 Ajustes ratificados de G1

- **G1-D1:** o motor funciona sem índice; SQLite é sempre reconstruível.
- **G1-D2:** recuperação obrigatória do segmento antes de nova escrita; lote sem `committed` é invisível; os dois hashes são definidos em G1-D6.
- **G1-D3:** envelope estável; cada tipo valida seu payload; o kernel não conhece regras particulares de evento.
- **G1-D4:** `game_time`/`game_time_sort` obrigatórios já no `EventDraft`; sem default do store.
- **G1-D5:** `evt_<ulid>` e `bat_<ulid>`; `correlation_id` identifica a unidade de trabalho; `causation_id` o evento direto.
- **G1-D6:** dois hashes distintos — hash do evento (representação canônica do evento) e hash do lote (concatenação canônica dos eventos em ordem de `seq`); SHA-256 sobre bytes canônicos.
- **G1-D7:** upcasters `N→N+1`; versão futura rejeitada; nenhuma conversão silenciosa.
- **G1-D8:** limites de segmento/snapshot são parâmetros operacionais ajustáveis; arquivar não apaga nem reescreve.
- **G1-D9:** cada tipo exige schema, campos obrigatórios e validação antes do registro; nenhum tipo arbitrário é gravável. Validar a cardinalidade 1:1 entre `turn.committed` e `prose.recorded` quando houver prosa, e confirmar que `correction.issued` cobre `corrects`/`changes`/`state`/`correction_id` (Q1; C4).
- **G1-D10:** registro explícito no `bootstrap.py`; valida tipo, versão, payload e dependências; sem descoberta automática.
- **G1-D11:** layout aceito.
- **G1-D12:** projeções escritas só por projectors/`ProjectionWriter`; `mundo.md`/`regras.md` são configuração separada.

---

## 3. G2 — Correção, Dependência e Reconstrução

### 3.1 Resumo das decisões ratificadas

| ID | Decisão | Status |
| :--- | :--- | :---: |
| G2-D1 | Correção é evento novo; nunca muta nem apaga o original | Ratificado com ajuste |
| G2-D2 | Dependências explícitas em `meta.dependencies`; grafo é DAG | Ratificado com ajuste |
| G2-D3 | Reavaliação seletiva dos dependentes; sem LLM; idempotente | Ratificado com ajuste |
| G2-D4 | Rebuild de projeção a partir de snapshot + eventos, com hash e checkpoint | Ratificado com ajuste |
| G2-D5 | Prosa é imutável; correção apenas anota, nunca reescreve | Ratificado |
| G2-D6 | Retomada sem duplicação: `event_id`, `expected_last_seq`, lote, checkpoint | Ratificado com ajuste |
| G2-D7 | Fila esqueleto em `queue.jsonl`; orçamento/retry ficam para G4 | Ratificado com ajuste |
| G2-D8 | Toda correção tem ator, motivo, alvo e estado auditável | Ratificado |
| G2-D9 | Fronteira com G6: Fase 02 guarda hash/caminho da prosa; indexação/recuperação vem depois | Ratificado |
| G2-D10 | `rebuild` não reexecuta LLM nem re-concede XP/relógio; recalcula a partir dos eventos | Ratificado |

### 3.2 Detalhamento

> O texto abaixo é a proposta original; os ajustes ratificados na seção 3.3 prevalecem em caso de diferença.

#### G2-D1 — Correção como evento

Uma correção é um `correction.issued` append-only:

```json
{
  "type": "correction.issued",
  "payload": {
    "corrects": ["evt_01J..."],
    "reason": "XP de missão concedido em duplicidade",
    "changes": [{"field": "xp_delta", "from": 150, "to": 0}],
    "state": "concluída"
  },
  "meta": {"dependencies": ["evt_01J..."]}
}
```

Regras:

- o evento original permanece intacto;
- a correção referencia os eventos corrigidos;
- a correção pode gerar **eventos de compensação** do mesmo recurso (`protagonist.progression_changed` com `xp_delta` negativo, `protagonist.sheet_changed` para pontos, `clock.advanced` com ajuste, `quest.status_changed` para reabrir), sempre com `meta.correction_id`;
- se o domínio não souber compensar, a correção fica registrada como anotação (`payload.annotation: true`) e o `review` acusa pendência;
- correção de `campaign.created` ou de configuração é proibida; `mundo.md`/`regras.md` são configuração e mudam por edição operacional/`import-md` (fora do escopo da Fase 02), não por correção de evento.

**Ratificação:** Q5 com ajuste.

#### G2-D2 — Grafo de dependências

- Cada evento declara `meta.dependencies: [event_id, ...]`.
- O grafo é um DAG; ciclo é rejeitado no append.
- Não há dependência implícita por `seq`; a ordem de leitura é `seq`, mas a causalidade é explícita.
- Profundidade máxima configurável (recomendação: 64); acima disso, o append falha com `DependencyDepthError`.
- O índice de dependências é derivado (`index.sqlite` ou varredura); não é verdade.
- Dependência apontando para evento inexistente é rejeitada.

**Ratificação:** Q6 com ajuste.

#### G2-D3 — Reavaliação seletiva

Ao corrigir `E`:

1. coletar dependentes diretos de `E` (eventos com `meta.dependencies` contendo `E`);
2. expandir transitivamente, respeitando o DAG e a profundidade máxima;
3. reexecutar apenas os projectors (e políticas determinísticas, quando existirem) afetados;
4. se o resultado mudar, emitir `correction.recomputed` com `affected` e `outcome`;
5. não reexecutar LLM; usar os dados gravados no evento original;
6. eventos não dependentes permanecem intocados.

Critério de aceite: corrigir um evento de XP de missão não altera projeções de NPC ou relógio não relacionados.

#### G2-D4 — Rebuild de projeção

- `rebuild` lê o snapshot mais recente (ou `seq=0`) e aplica os eventos em ordem de `seq`.
- Projectors são determinísticos e ordenados por `order`.
- Cada arquivo é gravado atomicamente; ao final, calcula `projection_hash` e grava um `projection.rebuilt`.
- Se o hash não bater com o checkpoint, a projeção é marcada `dirty` e reconstruída de novo.
- `rebuild` não reexecuta comandos, não re-concede XP, não avança relógios: apenas projeta os eventos válidos.
- O resultado deve ser byte-idêntico ao Markdown produzido pelo fluxo normal (mesmos dados, mesma versão de projeção).

#### G2-D5 — Prosa imutável

- `prose.recorded` guarda `text_hash`, `text_path`, `bytes`, `source` e `scene_type`.
- O texto original fica em `artifacts/prose/` e nunca é editado.
- Correção de um turno não reescreve a prosa; adiciona `correction.issued` com `prose_impact: "annotation"` e uma nota no diário.
- Reescrever prosa é um novo turno, não uma correção.
- O `review` deve acusar `PROSE_MISSING` se o caminho/hash não existir.

#### G2-D6 — Idempotência e retomada

- `event_id` é único; reenvio do mesmo lote é rejeitado com `DuplicateBatchError` (a alternativa “no-op idempotente” fica registrada, mas não é o default).
- `expected_last_seq` impede escrita concorrente/atrasada.
- Lote sem `committed` é invisível; retry grava novo lote com a sequência correta.
- Checkpoint de projeção evita reprojetar o que já foi aplicado.
- `correction_id` é único; repetir a mesma correção não duplica compensação.

**Ratificação:** Q6/Q5 com ajuste.

#### G2-D7 — Fila esqueleto

`queue.jsonl` guarda trabalho não concluído:

```json
{"work_id":"wrk_01J...","kind":"clock.advance","status":"pending","due_game_time":"...","priority":3,"payload":{...}}
```

- Fase 02: append, leitura, marcação `done`/`failed` por **novo registro** (`work.done`/`work.failed`), sem sobrescrever a linha original; sem orçamento, retry automático ou prioridade adaptativa.
- G4/Fase 05 fecha orçamento, retry e retomada.
- A fila é derivada do estado? Não: é registro operacional append-only, separado do event log de jogo.

**Ratificação:** Q8 com ajuste.

#### G2-D8 — Auditoria

- Toda correção tem `actor`, `reason`, `corrects`, `changes`, `state`.
- `review` emite lint para: dependência ausente, ciclo, correção sem motivo, compensação sem `correction_id`, prosa ausente.
- Nenhuma correção silenciosa: o diário mostra a nota e o evento fica no log.

#### G2-D9 — Fronteira com G6

- Fase 02 garante que a prosa original é recuperável por `turn` (hash + caminho).
- Indexação, busca, resumos derivados e reconstrução de memória são G6/Fase 07.
- O evento não carrega o texto completo se o artefato existir; carrega hash/caminho. Se o artefato for perdido, o evento continua auditável e o lint acusa.
- **Dependência de G6:** o armazenamento mínimo da prosa também é objeto de G6. Esta spec propõe artefato + hash/caminho como mínimo para a Fase 02; se G6 exigir outro formato (ex.: texto no JSONL, blob store), a decisão de G6 prevalece e ajusta `prose.recorded`.

#### G2-D10 — Rebuild não reexecuta efeitos

- XP, relógios e reputação são **recalculados** a partir dos eventos, não re-concedidos.
- Se um evento de XP foi compensado, o rebuild aplica o original e a compensação na ordem de `seq`.
- Nenhuma chamada a LLM no rebuild; nenhum `commit` é refeito.

---

### 3.3 Ajustes ratificados de G2

- **G2-D1:** `correction.issued` carrega eventos corrigidos, motivo, ator, alterações pretendidas, estado e `correction_id`; compensação numérica quando segura; se não for, registra pendência para revisão.
- **G2-D2:** referências a eventos anteriores do mesmo lote são permitidas; validação considera histórico persistido + lote em validação; profundidade 64 configurável; `seq` não implica causalidade.
- **G2-D3:** reavaliar não é reexecutar; sem LLM, sem repetir comandos, sem conceder XP/relógio de novo; fato posterior inconsistente gera registro de inconsistência e exige compensação/correção explícita, sem inventar novo resultado.
- **G2-D4:** rebuild byte-idêntico para a mesma sequência, snapshot, versão de projector e configuração; checkpoints só após sucesso; `projection.rebuilt` é emitido fora do cálculo do hash e não altera o resultado verificado.
- **G2-D5:** nova narração é novo artefato associado a novo turno/evento; o texto antigo permanece.
- **G2-D6:** lote duplicado rejeitado com `DuplicateBatchError`; quatro estados de retomada (nunca persistido, parcial não confirmado, confirmado não projetado, projetado); `correction_id` único no store.
- **G2-D7:** fila append-only e separada do histórico de jogo; criação e conclusão/falha por novos registros, sem sobrescrever.
- **G2-D8:** violações de correção geram erro ou lint identificável.
- **G2-D9:** o armazenamento da prosa não pode inviabilizar busca, resumos ou memória derivada de G6.
- **G2-D10:** compensações aplicadas na ordem dos eventos, sem duplicar XP, relógio ou reputação.

---

## 4. Cenários de aceite

### 4.1 Critérios complementares de aceite do R1 (não são gates)

- **C1 — Falhas reais de persistência:** interromper a escrita antes, durante e depois do marcador `batch.committed`; em todas as posições, nenhum leitor vê lote parcial e a recuperação trunca o rabo antes de novo append.
- **C2 — Dependências dentro do lote:** um turno cujos eventos dependem uns dos outros no mesmo `append` é aceito e validado (referências a eventos anteriores do lote).
- **C3 — Rebuild e auditoria:** `projection.rebuilt` é emitido fora do cálculo do hash e não altera o hash que está verificando.
- **C4 — Correção contraditória:** uma correção que invalida um fato posterior registra a inconsistência e exige compensação/correção explícita; o passado não é alterado silenciosamente.

Mapeamento: C1 → `FR-G1-09`; C2 → `FR-G2-09`; C3 → `FR-G2-10`; C4 → `FR-G2-11`.

### Cenário 1 — Evento ida-e-volta

- Criar campanha nova; emitir `campaign.created` e um `turn.committed`.
- Ler o log; os eventos voltam com `event_id`, `seq`, `recorded_at`, `payload` e `meta` idênticos ao canônico.
- `last_seq` = 2; `read(after_seq=0)` devolve os dois em ordem.

### Cenário 2 — Lote atômico sob crash

- Injetar falha antes, durante e depois do marcador `committed`, inclusive após gravar 2 de 3 eventos.
- Nenhum leitor vê o lote; `last_seq` continua o anterior.
- Retry grava o lote completo com a mesma sequência inicial; não há buraco nem duplicata.

### Cenário 3 — Rebuild de projeção

- A partir dos eventos, reconstruir `diario.md`, `ficha.md` e `npcs.md` do zero.
- Hash dos arquivos igual ao do fluxo normal; XP/relógios não duplicados.
- Rebuild repetido é idempotente.

### Cenário 4 — Correção seletiva

- Corrigir um `quest.completed` com XP errado.
- Apenas projeções de missão/progressão são afetadas; NPCs e relógios não relacionados permanecem byte-idênticos.
- A correção e a compensação aparecem no log; o original permanece.

### Cenário 5 — Prosa recuperável

- `prose.recorded` aponta para o artefato; o texto original é recuperável por turno.
- Corrigir o turno não altera o texto; apenas adiciona nota.
- Artefato ausente gera lint `PROSE_MISSING`.

### Cenário 6 — Retomada sem duplicação

- Interromper após o commit do lote e antes da projeção.
- Ao retomar, o checkpoint evita reprojetar; nenhum XP/relógio é duplicado.
- Reenviar o mesmo lote não cria segundo evento.

### Cenário 7 — Versionamento

- Ler evento `schema_version=1` com `EventType` atual `2`; o upcaster produz o payload 2.
- Evento com `schema_version=3` (futuro) é rejeitado com `SchemaError`.

### Cenário 8 — Retenção e rebuild por snapshot

- Segmentos múltiplos + snapshot no meio; rebuild a partir do snapshot reproduz o estado.
- Segmento arquivado não é reescrito; leitura histórica continua funcionando enquanto o arquivo existir.

### Cenário 9 — Dependências dentro do lote

- Um lote de turno contém `turn.proposed`, `action.resolved`, `turn.committed` e `clock.advanced`, com dependências entre eventos do próprio lote.
- O append aceita referências a eventos anteriores do mesmo lote e rejeita referência a evento posterior do mesmo lote.
- A ordem de leitura é `seq`; a causalidade é a declarada.

### Cenário 10 — Rebuild e auditoria sem autoinfluência

- `projection.rebuilt` é emitido após o hash da projeção ser calculado, fora da aplicação que o calcula.
- O hash verificado antes e depois do evento de auditoria é o mesmo.
- Rebuild repetido não altera o hash por causa do próprio evento de auditoria.

### Cenário 11 — Correção contraditória

- Corrigir um fato que invalidaria um evento posterior (ex.: mudar o resultado de um turno que concedeu XP).
- O sistema registra a inconsistência e exige compensação/correção explícita; não reescreve o evento posterior nem inventa um novo resultado.
- O `review` acusa a pendência enquanto ela não for resolvida.

---

## 5. Requisitos funcionais testáveis

| ID | Requisito | Gate |
| :--- | :--- | :---: |
| FR-G1-01 | Todo evento tem `event_id` `evt_<ulid>`, `seq` contíguo e `recorded_at` UTC atribuídos pelo store | G1 |
| FR-G1-02 | `append` de lote com falha não deixa evento visível nem consome `seq` | G1 |
| FR-G1-03 | `expected_last_seq` divergente gera `SeqConflictError` sem escrita | G1 |
| FR-G1-04 | Payload validado contra `EventType.payload_schema`; tipo desconhecido rejeitado | G1 |
| FR-G1-05 | `game_time`/`game_time_sort` ausentes no draft são rejeitados no append | G1 |
| FR-G1-06 | Serialização canônica estável e hash SHA-256 reproduzível | G1 |
| FR-G1-07 | Upcaster `1→2` lê evento antigo; versão futura rejeitada | G1 |
| FR-G1-08 | Segmento/snapshot permitem rebuild sem perda | G1 |
| FR-G1-09 | Falha de escrita antes/durante/depois do marcador não deixa lote parcial visível; recuperação trunca antes de novo append | G1 |
| FR-G1-10 | Hash do evento e hash do lote são distintos e verificáveis separadamente | G1 |
| FR-G2-01 | Correção é novo evento que referencia o original; original intacto | G2 |
| FR-G2-02 | Grafo de dependências é DAG; ciclo/ausente rejeitado | G2 |
| FR-G2-03 | Correção reavalia apenas dependentes afetados | G2 |
| FR-G2-04 | Rebuild reproduz Markdown byte-idêntico ao fluxo normal | G2 |
| FR-G2-05 | Rebuild não reexecuta LLM nem re-concede XP/relógio | G2 |
| FR-G2-06 | Prosa original recuperável; correção não a reescreve | G2 |
| FR-G2-07 | Reenvio/retomada não duplica eventos nem efeitos | G2 |
| FR-G2-08 | Fila esqueleto registra trabalho pendente e concluído | G2 |
| FR-G2-09 | Referências a eventos anteriores do mesmo lote são aceitas; referências posteriores são rejeitadas | G2 |
| FR-G2-10 | `projection.rebuilt` é emitido fora do cálculo do hash e não altera o resultado verificado | G2 |
| FR-G2-11 | Correção contraditória registra inconsistência e exige compensação/correção explícita | G2 |

---

## 6. Critérios de sucesso

1. **Cobertura de mutação:** 100% das mutações de `diario.md`, `ficha.md` e `npcs.md` têm evento correspondente; nenhum `write_text` fora do `ProjectionWriter`.
2. **Atomicidade:** 100 execuções de crash simulado não produzem lote parcial visível.
3. **Reconstrução:** rebuild de uma campanha de teste reproduz os três Markdown com hash idêntico ao fluxo normal.
4. **Correção seletiva:** corrigir um evento de XP altera somente as projeções dependentes; as demais permanecem byte-idênticas.
5. **Idempotência:** retomada após interrupção não duplica `event_id`, XP, relógio ou linha de diário.
6. **Versionamento:** evento antigo é upcastado; evento futuro é rejeitado.
7. **Prosa:** 100% dos turnos com `prose.recorded` têm artefato recuperável e hash válido.
8. **Auditoria:** toda correção tem ator, motivo, alvo e estado; `review` acusa violações.
9. **Persistência:** falhas em qualquer posição do lote não produzem estado parcial visível e a recuperação é idempotente.
10. **Dependências intra-lote:** eventos do mesmo lote podem declarar dependência de eventos anteriores do lote, sem ciclo.
11. **Auditoria de rebuild:** o evento `projection.rebuilt` não participa do hash que verifica.
12. **Correção contraditória:** o sistema registra a inconsistência e exige decisão explícita, sem reescrever o passado.

---

## 7. Perguntas ratificadas (Q1–Q10)

Ratificação de 23/10/2026: **Q2, Q4, Q7, Q9 e Q10** integrais; **Q1, Q3, Q5, Q6 e Q8** com ajuste. A decisão vinculante e os detalhes estão no [`checklists/g1-g2-ratification.md`](checklists/g1-g2-ratification.md).

| ID | Pergunta | Decisão | Ajuste/observação |
| :--- | :--- | :---: | :--- |
| Q1 | Catálogo v1 em nomes e granularidade | Ratificado com ajuste | Catálogo v1 como base; validar cardinalidade `turn.committed`/`prose.recorded` e expressividade das correções antes de congelar |
| Q2 | `target`/`preconditions`/`result`/`costs` no payload; dependências em `meta.dependencies` | Ratificado | Envelope permanece estável |
| Q3 | Lote por marcadores; SQLite opcional na Fase 02 | Ratificado com ajuste | Recuperação de lote incompleto rigorosamente especificada e testada |
| Q4 | Retenção integral; segmento 1.000/1 MB; snapshot 500/arco | Ratificado | Limites são parâmetros operacionais, não regras de domínio |
| Q5 | Correção com `correction.issued` + compensação; prosa imutável | Ratificado com ajuste | Efeitos numéricos compensáveis; fato contraditório exige reavaliação explícita, nunca alteração silenciosa |
| Q6 | Dependências explícitas, DAG, profundidade 64, sem causalidade por `seq` | Ratificado com ajuste | Referências a eventos anteriores do mesmo lote permitidas; validar histórico + lote |
| Q7 | Prosa em artefato + hash/caminho; indexação em G6 | Ratificado | Busca semântica e indexação ficam para G6 |
| Q8 | Fila `queue.jsonl` mínima na Fase 02; orçamento/retry no G4 | Ratificado com ajuste | Fila append-only, sem orçamento nem retry automático agora |
| Q9 | Projeções `diario.md`/`ficha.md`/`npcs.md`; `mundo.md`/`regras.md` config; `faccoes.md` em R2 | Ratificado | Sem antecipar fases futuras |
| Q10 | Escritas de Markdown exclusivas dos projectors no R1 | Ratificado | Nenhum comando mantém segunda via de escrita direta |

---

## 8. Processo de ratificação (concluído)

1. A ratificação foi concluída em 23/10/2026; o registro vinculante está no [`checklists/g1-g2-ratification.md`](checklists/g1-g2-ratification.md).
2. G1 e G2 estão fechados com ajustes; este documento passa a **Ready for Planning**.
3. O próximo passo é escrever `plan.md` e `tasks.md` com os quatro critérios complementares C1–C4.
4. O R1 só começa depois do plano; a Fase 02 não pode ser declarada concluída sem C1–C4.
5. Uma rejeição futura exige nova decisão do dono e atualização do checklist; não se implementa por cima de uma decisão revertida.
6. O registro da ratificação entra em `EXECUCAO.md` como nova entrada (`EX-0013`), com link para o checklist.

---

## 9. Relações

- [`ROADMAP.md`](../../ROADMAP.md) §3 (Fase 02), §5 (G1/G2), §6.4 (R1), §7.2 (cenários).
- [`ARCHITECTURE.md`](../../ARCHITECTURE.md) §2 (D1/D2/D4), §5.0–§5.4, §8, §11.
- [`contracts/event.py`](../../contracts/event.py) e [`contracts/ports.py`](../../contracts/ports.py) — o que o R0 já fixou.
- [`checklists/g1-g2-ratification.md`](checklists/g1-g2-ratification.md) — decisões ratificadas e C1–C4.
- [`EXECUCAO.md`](../../EXECUCAO.md) `EX-0012` (spec) e `EX-0013` (ratificação).
- [`QA-FASE-01.md`](../../QA-FASE-01.md) — auditoria que liberou a base.
