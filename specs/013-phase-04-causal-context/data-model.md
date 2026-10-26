# Data Model: 013 — Fase 04: Contexto Causal no `prepare`

**Feature:** `phase-04-causal-context`
**Spec:** [`spec.md`](spec.md)
**Status:** Draft para revisão

---

## 1. Visão Geral

O contexto é uma **projeção imutável** montada a partir de:

1. projeções Markdown existentes (`diario.md`, `ficha.md`, `npcs.md`, `mundo.md`, `regras.md`);
2. cache derivado `estado.json` (NPCs, facções, conhecimento, eventos recentes);
3. configuração e política de modo/audiência.

Nada no contexto é fonte de verdade. A verdade continua no event log; `estado.json` é cache reconstruível.

---

## 2. Modelos de Contexto (`contracts/context.py`)

### 2.1 `ContextRequest`

```python
@dataclass(frozen=True)
class ContextScene:
    location: str
    present: tuple[str, ...]
    game_time: str
    game_time_sort: int
    scene_type: str = "standard"

@dataclass(frozen=True)
class ContextRequest:
    campaign_id: str
    mode: str                      # gm | narrator | writer | architect | director | reviewer
    action: str
    scene: ContextScene
    viewer: HolderRef              # quem consome o contexto
    audience: HolderRef            # para quem o contexto será narrado
    purpose: str                   # arbitration | narration | prose | structure | direction | audit
    focus: tuple[str, ...] = ()
    limits: "ContextLimits" = ...
    seed: int = 0
```

`ContextLimits`: `max_npcs=5`, `max_factions=3`, `max_facts=8`, `max_consequences=5`, `min_relevance=200`.

### 2.2 `ContextItem`

```python
@dataclass(frozen=True)
class ContextItem:
    kind: str                 # npc | faction | plan | quest | clock | fact | consequence | claim | arc | constraint
    id: str
    label: str
    layer: str                # core | causal
    score: int = 0
    reasons: tuple[str, ...] = ()
    availability: str = "known"   # known | unknown | unavailable | inexistent
    payload: Mapping[str, Any] = field(default_factory=dict)
    sources: tuple[str, ...] = ()  # event_id/record_id/knw_id
```

### 2.3 `ContextOmission`

```python
@dataclass(frozen=True)
class ContextOmission:
    kind: str
    reference: str            # id, nome ou claim citada
    availability: str         # unknown | unavailable | inexistent
    reason: str
    sources: tuple[str, ...] = ()
```

Regra: toda referência citada pela ação, foco ou cena que não virou item **precisa** de omissão; não existe lacuna silenciosa.

### 2.4 `ContextSection`

```python
@dataclass(frozen=True)
class ContextSection:
    key: str
    layer: str
    items: tuple[ContextItem, ...]
    omissions: tuple[ContextOmission, ...]
    hash: str
```

### 2.5 `TurnContext`

```python
@dataclass(frozen=True)
class TurnContext:
    version: int
    request: ContextRequest
    core: ContextSection
    causal: ContextSection
    query: "ContextQueryHandles"
    omissions: tuple[ContextOmission, ...]
    source_last_seq: int
    context_hash: str
    stale: bool
    providers: tuple[str, ...]
```

### 2.6 `ContextQueryHandles`

```python
@dataclass(frozen=True)
class ContextQueryHandles:
    holder: HolderRef
    audience: HolderRef
    purpose: str
    entities: Mapping[str, tuple[str, ...]]   # kind -> ids consultáveis
    commands: tuple[str, ...]                 # ex.: "query claim <clm_...>"
```

`entities` lista apenas IDs que a audiência pode conhecer; IDs ocultos não são enumerados (uma consulta direta a eles retorna `unavailable`).

### 2.7 `ContextQueryResult`

```python
@dataclass(frozen=True)
class ContextQueryResult:
    kind: str
    id: str
    availability: str
    payload: Mapping[str, Any]
    sources: tuple[str, ...] = ()
    reason: str | None = None
```

---

## 3. Porta `ContextProvider`

```python
@runtime_checkable
class ContextProvider(Protocol):
    key: str
    layer: str        # core | causal
    priority: int

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        ...
```

Regras (ARCHITECTURE §6.3): sem I/O, sem importar `resources/*/service`, determinístico, sem estado global, recebe views imutáveis.

`ContextStateView` é o contrato de leitura do cache:

```python
@runtime_checkable
class ContextStateView(Protocol):
    last_seq: int
    def npcs(self) -> Mapping[str, Any]: ...
    def factions(self) -> Mapping[str, Any]: ...
    def knowledge(self) -> Sequence[Any]: ...
    def recent_events(self, limit: int = 50) -> Sequence[Any]: ...
    def quests(self) -> Sequence[Any]: ...
    def clocks(self) -> Sequence[Any]: ...
    def arc(self) -> Mapping[str, Any]: ...
```

---

## 4. Cache `estado.json` (projeção)

Gerado por `application/projectors/state.py` (`StateProjector`, `file="estado.json"`, `order=50`) a partir de `EventStreamView`.

```json
{
  "schema_version": 1,
  "last_seq": 128,
  "projection_version": 1,
  "npcs": [ { "id": "...", "name": "...", "tier": "major", "...": "..." } ],
  "factions": [ { "tag": "CORVOS", "...": "..." } ],
  "knowledge": [ { "record_id": "knw_...", "holder": {"kind":"npc","id":"..."}, "...": "..." } ],
  "recent_events": [
    { "seq": 120, "type": "turn.committed", "game_time": "...", "game_time_sort": 120,
      "actor": {"kind": "agent", "id": "narrator"}, "summary": "...", "refs": ["npc:kael"] }
  ]
}
```

Regras:

- `recent_events`: últimos 50 eventos relevantes, sem prosa pesada; payload resumido (`summary`, `changes`, `correction_id`, `quest_id`, `clock`, `npc_id`, `faction`).
- `knowledge`: apenas campos epistêmicos necessários (`record_id`, `holder`, `claim_id`, `awareness`, `stance`, `confidence`, `status`, `visibility`, `provenance` resumida).
- `quests`, `clocks` e `arc` **não** são duplicados no JSON: `ContextStateView` os lê da projeção `diario.md` (já parseada pelo pipeline), mantendo uma única fonte por recurso.
- Determinístico: listas ordenadas por chave estável; `canonical_json` + `sha256` para hash.
- `last_seq` e `schema_version` obrigatórios; cache inválido é reconstruído, nunca lido parcialmente.

---

## 5. Payload do `prepare` (aditivo)

Chaves novas:

```json
{
  "context_version": 1,
  "context": {
    "version": 1,
    "audience": "protagonist",
    "purpose": "narration",
    "source_last_seq": 128,
    "context_hash": "sha256:...",
    "stale": false,
    "providers": ["ruleset_core", "protagonist_core", "scene_core", "..."],
    "core": { "items": [], "hash": "..." },
    "causal": { "items": [], "hash": "..." },
    "query": { "holder": {...}, "audience": {...}, "purpose": "narration", "entities": {}, "commands": [] }
  },
  "context_omissions": []
}
```

Chaves legadas preservadas sem alteração de tipo/semântica: `campaign`, `system`, `operation_mode`, `next_turn_number`, `canonical_header`, `scene_type`, `stakes`, `is_critical_turn`, `situational_pacing`, `scheduled_scene`, `protagonist`, `step_1_quest_context`, `step_1_faction_context`, `step_1_gm_arbitration`, `step_2_narrator_briefing`, `step_3_writer_mandate`, `step_4_post_turn_commit_template`, `ai_memory_recall`, `source_turns`.

`step_2_narrator_briefing` ganha `context_causal` opcional (lista de itens já filtrados), mas mantém `focal_npcs`, `background_cast`, `scene_relational_matrix`, `triangulation_mandate` e `epistemic_barrier`.

---

## 6. Relevância Causal (determinística)

Pontuação inteira por entidade, com componentes fixos:

| Componente | Pontos | Condição |
| :--- | ---: | :--- |
| Presença na cena | +1000 | nome na cena ou `present` |
| Foco explícito | +500 | citado em `--focus` ou na ação |
| Relógio crítico vinculado | +300 | `current >= max - 1` e `status=ACTIVE` |
| Plano iminente | +300 | passo `in_progress`, plano atualizado nos últimos 3 turnos ou missão associada com relógio crítico |
| Missão ativa vinculada | +250 | entidade é contractor/objetivo de missão ativa |
| Arco ativo | +200 | entidade citada em arco/pergunta central |
| Ameaça | +200 | `rivalry >= 2` ou `trust <= -2` contra o protagonista/facção da cena |
| Dívida/favor | +150 | `debt != 0` |
| Consequência recente | +100 | evento dos últimos 5 turnos afetando a entidade |
| Distância física | −100 | localização conhecida diferente da cena |

- Limiar: `min_relevance=200`; top-K: NPCs 5, facções 3.
- Ordenação: `(-score, kind, id)`; empate nunca depende de ordem de dicionário.
- `reasons`: rótulos legíveis dos componentes ativados (ex.: `plano_iminente`, `divida`, `fora_de_cena`).
- Entidades presentes com score abaixo do limiar permanecem em `background_cast`, **não** em `causal.items`.

---

## 7. Fatos e Consequências

- **Fato vigente:** `turn.committed` não corrigido, `action.resolved` ou `knowledge.*` público relevante; inclui `seq`, `summary`, `game_time`.
- **Fato corrigido:** evento alvo de `correction.issued.corrects`; não entra como vigente; entra como `kind=consequence` com `correction_id` e motivo.
- **Consequência:** `clock.advanced`, `quest.*`, `faction.reputation_changed`, `npc.plan_updated`, `protagonist.*` e `correction.issued` recentes que afetam entidades selecionadas.
- **Filtro:** referências na ação/foco/cena ou vínculo com as entidades causais; limite `max_facts`/`max_consequences`.
- **Sem invenção:** se a ação cita um fato/evento que não existe no cache, gerar omissão `inexistent`.

---

## 8. Conhecimento e Visibilidade

- `knowledge` do cache é convertido em `KnowledgeView` por audiência:
  - `player`: `HolderRef("player", player_id)` / audiência `player`.
  - `protagonist`: `HolderRef("protagonist", protagonist_id)` / audiência `protagonist`.
  - `narrator`/`writer`: audiência `protagonist` e filtro adicional que remove `player_meta` e segredos de terceiros.
  - `gm`: sem filtro; consulta direta ao cache.
- Claims citadas na ação (`clm_` ou nome de fato) são consultadas; o resultado (`known|unknown|unavailable|inexistent`) vira item ou omissão.
- A fonte é sempre `record_id`/`claim_id`; nenhum texto de crença é reescrito.

---

## 9. IDs e Configuração

`regras.md` pode declarar:

```yaml
context:
  player_id: jogador
  protagonist_id: aemon
  relevance:
    min_score: 200
    max_npcs: 5
    max_factions: 3
    max_facts: 8
```

Fallbacks: `player`, slug do nome do protagonista em `ficha.md`, e os padrões da §6.

---

## 10. Invariantes

1. `context_hash` cobre `version`, `source_last_seq`, `audience`, `purpose`, itens e omissões em ordem canônica.
2. Mesmo estado e mesma requisição ⇒ mesmo hash; mudança de estado ⇒ hash diferente.
3. Itens em `core` nunca dependem de relevância; `causal` nunca inclui item com `availability != known`.
4. Toda omissão tem `availability` e `reason`; nenhuma referência citada fica sem item nem omissão.
5. Nenhum item expõe `player_meta` a audiência diferente de player/human.
6. O cache nunca é fonte de verdade; se `last_seq` não bater, é reconstruído antes da leitura.
