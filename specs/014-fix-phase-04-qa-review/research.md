# Research & Decision Log: 014 — Remediação dos Bloqueantes de QA da Fase 04

**Feature:** `fix-phase-04-qa-review`  
**Data:** 2026-10-26  
**Status:** Consolidado  

---

## 1. Unificação de `HolderRef` e Respeito às Fronteiras Arquiteturais (P0-1 & P1-3)

### Contexto
O teste de auditoria revelou a existência de duas classes `@dataclass(frozen=True) class HolderRef`:
- `contracts.context.HolderRef`
- `resources.knowledge.model.HolderRef`
Embora ambas possuíssem campos similares (`kind`, `id`), em Python classes de módulos diferentes não são iguais (`contracts.context.HolderRef != resources.knowledge.model.HolderRef`), fazendo com que `HolderRef("npc", "Kael") == HolderRef("npc", "Kael")` retornasse `False`. Isso quebrava buscas em dicionários e comparações no `KnowledgeView`. Além disso, a regra arquitetural estrita (`test_architecture_boundaries.py`) proíbe que `contracts/` importe de `resources/`.

### Decisão
Definir `HolderRef` canonicamente em `contracts/context.py` com validação de `VALID_HOLDER_KINDS = {"npc", "faction", "subgroup", "protagonist", "player"}`. Em `resources/knowledge/model.py`, importar e reexportar `HolderRef` diretamente de `contracts.context`:
```python
from contracts.context import HolderRef
```
### Racional
- Mantém o princípio de única fonte de verdade de tipos (SSOT).
- Respeita a regra de dependência unidirecional: `contracts/` é a camada de tipos compartilhados; `resources/` pode importar de `contracts/`, mas `contracts/` nunca importa de `resources/`.
- Garante identidade de classe (`C is D`) em toda a base de código sem redundâncias.

---

## 2. Reconstrução Canônica de `ProvenanceRef` sem Supressão Silenciosa (P0-1)

### Contexto
A função `_dict_to_knowledge_record` em `application/context/knowledge.py` tentava instanciar `ProvenanceRef` passando campos inexistentes (`source_event_id`, `method`, `source_agent`, `reliability`), enquanto o modelo canônico da Fase 03 (`resources/knowledge/model.py`) define:
```python
ProvenanceRef(
    source_type: str,
    source_id: str,
    channel: str,
    acquired_at: str,
    acquired_at_sort: int,
    confidence: int,
    derived_from: Tuple[str, ...] = (),
    supports: bool = True
)
```
A cláusula `except Exception: return None` engolia o `TypeError`, fazendo com que todo conhecimento canônico com proveniência fosse descartado do pipeline de contexto.

### Decisão
1. Atualizar `_dict_to_knowledge_record` para deserializar os 6 campos obrigatórios de `ProvenanceRef`, com fallback seguro e tipado para valores padrão se opcionais.
2. Não suprimir silenciosamente exceções de schema: se um registro for estruturalmente inválido, emitir log/aviso e registrar omissão explícita, sem engolir erros de programação.
3. Usar os enums e vocabulários canônicos de `awareness` (`known`/`unknown`) e `stance` (`believed`/`disbelieved`/`uncertain`).

---

## 3. Normalização de Relacionamentos em `score_npc` (P0-2)

### Contexto
Em `estado.json`, o estado dos NPCs serializa `NpcState.relationships` como uma lista de dicionários (`list[dict]`), correspondendo aos `RelationalVector` multidimensionais direcionados a cada alvo. Em `resources/context/relevance.py`, `score_npc` chamava diretamente `.get("rivalry", 0)` sobre `npc_data["relationships"]`, disparando `AttributeError: 'list' object has no attribute 'get'` para qualquer NPC com relacionamentos.

### Decisão
Criar o helper puro `_extract_relational_vector(npc_data, target_id="")`:
- Se `relationships` ou `relational_vector` for `dict`, utiliza-o diretamente.
- Se for `list` ou `tuple`, itera sobre os vetores:
  - Se `target_id` (ex: protagonista) for fornecido, busca o vetor onde `item.get("target_id") == target_id`.
  - Se não encontrado ou `target_id` vazio, seleciona o vetor de maior intensidade (ou o primeiro disponível).
- Extrai as dimensões canônicas: `rivalry`, `trust`, `debt`, `loyalty`, `dependency`.

---

## 4. Alinhamento de Sequência de Auditoria e Cache `estado.json` (P1-1 & P2-8)

### Contexto
O comando `rebuild_projections(..., emit_audit_event=True)` gera o arquivo `estado.json` e, logo em seguida, emite o evento de auditoria `projection.rebuilt` com `seq = last_seq + 1`. Na chamada subsequente a `prepare`, `ContextStateViewImpl.load` comparava `store.last_seq` (ex: 6) com `cached_seq` (ex: 5), detectava divergência, chamava `rebuild_projections`, que por sua vez filtrava `projection.*` e regerava `estado.json` com `last_seq = 5`, entrando em um loop infinito de reconstrução e marcando o cache eternamente como `stale=True`.

### Decisão
1. Em `StateProjector`: computar `last_seq` a partir de `view.last_seq` (que representa a posição do fluxo de eventos processado).
2. Em `rebuild_projections`: quando `emit_audit_event=True` for executado, persistir o evento `projection.rebuilt` e atualizar o campo `last_seq` no arquivo `estado.json` já projetado no disco, refletindo a nova sequência do log.
3. Em `ContextStateViewImpl.load`:
   - Validar estritamente `schema_version == 1`.
   - Se `cached_seq < expected_seq`, verificar se os eventos restantes no log entre `cached_seq + 1` e `expected_seq` são exclusivamente eventos técnicos (`projection.*`). Em caso afirmativo, o cache não está desatualizado (é fresco e válido).

---

## 5. Invalidação de Fatos Retificados por `event_id` (P1-2)

### Contexto
O contrato de correção da Fase 02 (`specs/010-phase-02-causal-history/data-model.md`) define que `payload["corrects"]` armazena uma lista de strings com identificadores de evento (`evt_<ulid>`). O `FactsCausalProvider` aceitava apenas inteiros (`seq`) e `StateProjector` não incluía `event_id` nos dicionários de `recent_events`.

### Decisão
1. No `StateProjector`: incluir `"event_id": getattr(ev, "id", "")` em cada item de `recent_events`.
2. No `FactsCausalProvider`: processar `corrects` aceitando tanto `str` (`event_id`) quanto `int` (`seq`). Na verificação de fatos vigentes, desqualificar o evento se seu `event_id` ou seu `seq` constar no conjunto de correções emitidas.

---

## 6. Preservação Estrita do Gameplay e Seleção Focal Legada (P1-4)

### Contexto
O refatoramento da Fase 04 alterou a seleção de atores focais:
- Fallback em `resolve_scene_actors`: antigamente selecionava os 2 primeiros NPCs presentes na cena; a Fase 04 passou a selecionar apenas o primeiro com vontade/plano preenchido, podendo deixar `focal_npcs` vazio.
- `build_quest_context`: parou de filtrar `status == "ACTIVE"`, misturando missões concluídas no mandato de pressão narrativa.

### Decisão
1. Em `resolve_scene_actors`: se após as buscas por foco e ação explícita nenhum NPC for focalizado, selecionar até os 2 primeiros NPCs presentes em cena (`scene_npcs[:2]`) como atores focais por fallback, preservando as orientações do narrador e sugestões de commit.
2. Em `build_quest_context`: aplicar filtro estrito `[q for q in quests if q.get("status") == "ACTIVE"]`.

---

## 7. Resolução de Audiência do Protagonista no CLI `query` (P1-3)

### Contexto
Quando o usuário executa `lazy_turn.py query claim <id> --audience protagonist`, a flag passava `protagonist` como o identificador do holder, em vez de usar o nome real do herói (ex: `"Aemon"`), impedindo a localização das alegações mantidas pelo protagonista.

### Decisão
Em `ContextQueryService.__init__` e no despacho CLI em `main.py`, resolver o nome do protagonista lendo a ficha da campanha (`ficha.md` via `parse_ficha`). Se a audiência tiver `kind == "protagonist"` e `id` padrão, substituir pelo nome real do herói.

---

## 8. Suporte a `active_plan` em `score_faction` (P2-1)

### Contexto
O estado serializa o plano de facção sob a chave `active_plan`, mas `score_faction` buscava apenas `plan` ou `initiative`.

### Decisão
Expandir a busca para:
```python
plan = faction_data.get("active_plan") or faction_data.get("plan") or faction_data.get("initiative") or {}
```
Garantindo o bônus de `+300` e a justificativa `plano_iminente` para facções com planos ativos.
