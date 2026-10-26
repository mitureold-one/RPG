# Contracts: 013 — Fase 04: Contexto Causal

**Feature:** `phase-04-causal-context`
**Spec:** [`../spec.md`](../spec.md) · **Data model:** [`../data-model.md`](../data-model.md)

---

## 1. Porta `ContextProvider`

Local: `contracts/ports.py` (protocolo) + `contracts/context.py` (modelos).

```python
class ContextProvider(Protocol):
    key: str
    layer: str        # "core" | "causal"
    priority: int

    def provide(self, request: ContextRequest, state: ContextStateView) -> ContextSection:
        ...
```

Regras:

- `priority` menor executa antes; empate resolvido por `key`.
- `layer="core"` é sempre incluído; `layer="causal"` passa pelo filtro de relevância.
- Providers não fazem I/O, não importam `resources/*/service`, não chamam LLM e não gravam.
- O provider devolve `ContextSection` com `items` e `omissions`; não decide o payload final.

### 1.1 Providers padrão

| `key` | Camada | Prioridade | Responsabilidade |
| :--- | :--- | ---: | :--- |
| `ruleset_core` | core | 10 | sistema, ladder de DC, overrides, restrições |
| `protagonist_core` | core | 20 | ficha, vitais, atributos, progressão |
| `scene_core` | core | 30 | tempo, local, presentes, arco ativo, cabeçalho |
| `quest_causal` | causal | 40 | missões ativas, objetivos pendentes, pressão |
| `clock_causal` | causal | 45 | relógios ativos/críticos e gatilhos |
| `npc_causal` | causal | 50 | NPCs focais e distantes por relevância |
| `faction_causal` | causal | 55 | facções da cena e distantes por relevância |
| `knowledge_causal` | causal | 60 | crenças/fatos por audiência + omissões |
| `facts_causal` | causal | 65 | fatos recentes, correções e consequências |

`ai_memory_recall` existente permanece como provedor opcional (`memory_causal`, prioridade 70), sem indexação nova.

---

## 2. `ContextStateView`

Local: `contracts/context.py` (protocolo) + `application/context/state.py` (implementação).

```python
class ContextStateView(Protocol):
    last_seq: int
    stale: bool

    def npcs(self) -> Mapping[str, Any]: ...
    def factions(self) -> Mapping[str, Any]: ...
    def knowledge(self) -> Sequence[Any]: ...
    def recent_events(self, limit: int = 50) -> Sequence[Any]: ...
    def quests(self) -> Sequence[Any]: ...
    def clocks(self) -> Sequence[Any]: ...
    def arc(self) -> Mapping[str, Any]: ...
```

- Implementação lê `estado.json` (projeção) e as projeções Markdown.
- `last_seq` é comparado com `EventStore.last_seq(campaign_id)`; divergência dispara reconstrução única.
- Nenhum método devolve referência mutável; listas/tuplas congeladas.

---

## 3. `ContextQueryService`

Local: `application/context/query.py` (serviço) + `interfaces/cli`.

```python
class ContextQueryService:
    def __init__(self, campaign_id: str, audience: HolderRef, purpose: str = "query"): ...

    def claim(self, claim_id: str) -> ContextQueryResult: ...
    def npc(self, npc_id: str) -> ContextQueryResult: ...
    def faction(self, tag: str) -> ContextQueryResult: ...
    def quest(self, quest_id: str) -> ContextQueryResult: ...
    def clock(self, name: str) -> ContextQueryResult: ...
```

- Reutiliza `KnowledgeView` e a matriz de visibilidade da Fase 03.
- `availability` sempre explícita (`known|unknown|unavailable|inexistent`).
- Sem escrita, sem evento, sem LLM.
- CLI: `python lazy_turn.py query --campaign <id> --kind claim|npc|faction|quest|clock --id <id> --audience protagonist|player|gm [--json]`.

---

## 4. `StateProjector`

Local: `application/projectors/state.py`.

```python
class StateProjector:
    file = "estado.json"
    section = "body"
    order = 50

    def project(self, view: EventStreamView) -> ProjectionSection: ...
```

- Produz JSON canônico (`sort_keys`, separadores estáveis) com `schema_version`, `last_seq`, `npcs`, `factions`, `knowledge`, `recent_events`.
- Incluído em `default_projectors` e, portanto, em `rebuild_projections`; o `commit` já reprojeta via transação.
- Falha de serialização é erro explícito; nunca grava JSON parcial.

---

## 5. Payload Contract (resumo)

```python
{
  "context_version": 1,
  "context": {
    "version": 1,
    "audience": "protagonist",
    "purpose": "narration",
    "source_last_seq": 128,
    "context_hash": "sha256:...",
    "stale": False,
    "providers": [...],
    "core": {"items": [...], "hash": "..."},
    "causal": {"items": [...], "hash": "..."},
    "query": {"holder": {...}, "audience": {...}, "purpose": "...", "entities": {}, "commands": [...]}
  },
  "context_omissions": [...]
}
```

- `items` e `omissions` são listas ordenadas; cada item tem `kind`, `id`, `score`, `reasons`, `availability`, `sources`.
- Chaves legadas são preservadas; nenhuma é removida ou renomeada.

---

## 6. Compatibilidade e Versionamento

- `context_version=1`; mudanças incompatíveis sobem a versão e exigem atualização do snapshot de contrato.
- `estado.json.schema_version=1`; leitor rejeita versão desconhecida e reconstrói.
- `ContextProvider` declara `api_version` apenas se virar plugin externo (Fase 04 usa providers internos).

---

## 7. Testes de Contrato

1. Provider puro: sem `open`, sem imports de `adapters`/`interfaces`/`resources.*.service`.
2. `ContextSection.hash` estável para a mesma entrada.
3. `ContextQueryService` respeita `player_meta` × protagonista.
4. `StateProjector` gera JSON parseável, determinístico e com `last_seq`.
5. Cache velho → reconstrução; cache fresco → nenhuma leitura de `EventStore.read`.
