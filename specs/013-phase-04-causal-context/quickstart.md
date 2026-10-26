# Quickstart & Verification Guide: 013 — Fase 04: Contexto Causal

**Feature:** `phase-04-causal-context`
**Status:** Guia de verificação (executável após a implementação)
**Spec:** [`spec.md`](spec.md) · **Plan:** [`plan.md`](plan.md)

---

## 1. Baseline

```powershell
$env:PYTHONPATH='.'
python -m unittest discover -s tests -p "test_*.py"          # 234 legados + novos
python -m unittest tests.test_architecture_boundaries        # 8 + novos
```

O snapshot de contrato do `prepare` (`tests/test_boundary_contracts.py`) deve continuar passando **sem alteração** dos campos existentes.

---

## 2. Preparar uma campanha de teste

```powershell
$env:RPGPRO_CAMPAIGNS_DIR = "$env:TEMP\qa_phase04\campaigns"
python lazy_turn.py init-campaign --campaign ctx_lab --title "Laboratório de Contexto"
```

O comando cria `campaigns/ctx_lab/` com `diario.md`, `ficha.md`, `npcs.md`, `mundo.md`, `regras.md` e `events/` (campanha criada).

Para semear estado causal (NPC distante com plano iminente), use um script Python descartável:

```python
from adapters.persistence.event_store import JsonlEventStore
from contracts.event import ActorRef, EventDraft
from resources.factions.service import make_faction_updated_draft
from resources.npcs.drafts import make_npc_promoted_draft, make_npc_plan_updated_draft

store = JsonlEventStore("campaigns/ctx_lab")
store.append("ctx_lab", [
    make_npc_promoted_draft("malakor", "minor", "major", "01/10", 10, capabilities=["guerra"]),
    make_npc_plan_updated_draft("malakor", "pln_golpe", "tomar_trono",
        "Golpe da Guarda", [{"step_id": "s1", "description": "Cercar o palácio"}],
        "active", "01/10", 11),
    make_faction_updated_draft("MALAKOR", "Guarda de Malakor", "01/10", 11,
        leadership={"leader_id": "malakor", "title": "Comandante"}),
])
```

Depois, `python lazy_turn.py rebuild --campaign ctx_lab --force` gera `estado.json` junto das projeções.

---

## 3. Inspecionar o contexto

```powershell
python lazy_turn.py prepare --campaign ctx_lab --action "Aemon interroga um espião sobre Malakor" --no-roll
```

Saída esperada (resumo):

```text
context.audience = "protagonist" (modo gm: "universe")
context.source_last_seq = <seq>
context.core.items: regras, protagonista, tempo/local, arco, restrições
context.causal.items: inclui malakor (plano_iminente, fora_de_cena, ameaça)
context_omissions: vazio ou apenas referências realmente inexistentes
```

Verificação programática:

```powershell
python -c "import json, subprocess; p=json.loads(subprocess.check_output(['python','lazy_turn.py','prepare','--campaign','ctx_lab','--action','Aemon interroga um espião sobre Malakor','--no-roll'], text=True)); print(p['context']['context_hash']); print([i['id'] for i in p['context']['causal']['items']])"
```

- O hash deve ser idêntico em duas execuções seguidas.
- `malakor` deve aparecer em `causal.items` com `reasons` contendo `plano_iminente`.
- Um NPC presente sem vínculo não deve aparecer em `causal.items` (apenas em `step_2_narrator_briefing.background_cast`).

---

## 4. Verificar audiências e vazamento

Crie uma claim `player_meta` para o jogador e consulte com audiências diferentes:

```powershell
python lazy_turn.py query --campaign ctx_lab --kind claim --id clm_... --audience protagonist --json
python lazy_turn.py query --campaign ctx_lab --kind claim --id clm_... --audience player --json
```

Esperado:

- `protagonist`: `unavailable` ou `unknown`;
- `player`: `known` com `stance`/`confidence`;
- `narrator`/`writer`: nunca `known` para `player_meta`.

No payload de `prepare` em modo `narrator`, `context.causal.items` não pode conter itens `player_meta`.

---

## 5. Fatos, correções e omissões

1. Emita um `turn.committed` com resumo factual e um `correction.issued` sobre ele.
2. Execute `prepare` citando o fato.
3. Verifique:
   - o fato original **não** aparece como vigente;
   - a correção aparece como `consequence` com `correction_id`;
   - ação citando `clm_inexistente` gera `context_omissions` com `availability="inexistent"`.

---

## 6. Cache e staleness

```powershell
# cache fresco: prepare não deve ler o log (teste instrumentado)
python -m unittest tests.test_phase04_state_cache -v

# remover o cache e preparar novamente
Remove-Item campaigns\ctx_lab\estado.json
python lazy_turn.py prepare --campaign ctx_lab --action "Olhar o pátio" --no-roll
# esperado: contexto válido; cache recriado; stale=true na resposta
```

O teste `C08` usa um stub de `EventStore.read` que levanta exceção para provar que, com cache fresco, o log não é relido.

---

## 7. Consulta sob demanda

```powershell
python lazy_turn.py query --campaign ctx_lab --kind npc --id malakor --audience gm --json
python lazy_turn.py query --campaign ctx_lab --kind faction --id MALAKOR --audience protagonist --json
python lazy_turn.py query --campaign ctx_lab --kind quest --id Q1 --audience protagonist --json
python lazy_turn.py query --campaign ctx_lab --kind clock --id "Golpe da Guarda" --audience gm --json
```

Cada saída é `ContextQueryResult` com `availability` explícita e `sources`.

---

## 8. Critérios de aceite

| Critério | Verificação |
| :--- | :--- |
| C01 núcleo/hash | payload contém core completo; duas execuções ⇒ mesmo hash |
| C02 antagonista distante | `malakor` em `causal.items` com `plano_iminente` |
| C03 presença não é suficiência | NPC presente sem vínculo não é causal |
| C04 audiência | `player_meta` só para player; protagonista/narrator nunca |
| C05 fatos/correções | fato corrigido vira consequência, não fato vigente |
| C06 omissões | `clm_inexistente` ⇒ `inexistent`; invisível ⇒ `unavailable`; desconhecido ⇒ `unknown` |
| C07 consulta | `query` JSON determinístico e filtrado |
| C08 cache | cache fresco não lê log; stale reconstrói |
| C09 compatibilidade | 234 legados verdes; chaves antigas intactas |
| C10 modos/R2 | matriz de modos; `prepare < 300`; fronteiras verdes |

---

## 9. Solução de problemas

- **`estado.json` ausente:** rode `rebuild --campaign <id> --force`; o `prepare` também reconstrói, mas o comando explícito é mais fácil de auditar.
- **Cache velho após edição manual de Markdown:** edição manual não é fluxo normal; use `rebuild` e registre a divergência. O `prepare` compara `last_seq`, não hashes de Markdown.
- **Contexto vazio em modo `narrator`:** é esperado quando o protagonista não conhece nada; verifique `context_omissions` e o `step_2_narrator_briefing`.
- **Divergência de hash entre execuções:** verifique ordenação de listas/dicionários e ausência de `datetime.now()`/`set` no caminho.
