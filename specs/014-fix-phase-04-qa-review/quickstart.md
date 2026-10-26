# Quickstart: 014 — Validação da Remediação da Fase 04

**Feature:** `fix-phase-04-qa-review`  
**Data:** 2026-10-26  
**Status:** Consolidado  

---

## 1. Pré-Requisitos

Executar a partir da raiz do repositório RPGPRO no PowerShell:

```powershell
$env:PYTHONPATH='.'
```

---

## 2. Cenários de Validação Rápida

### Cenário 1: Unificação de `HolderRef` (Zero Descompasso de Classes)
Valida que as instâncias de `HolderRef` de contratos e de recursos são exatamente a mesma classe e comparam como iguais:

```powershell
python -c "from contracts.context import HolderRef as C; from resources.knowledge.model import HolderRef as D; assert C('protagonist','Aemon') == D('protagonist','Aemon'); print('OK: HolderRef unificado com sucesso')"
```
*Resultado esperado:* `OK: HolderRef unificado com sucesso`

---

### Cenário 2: Validação com Dados Canônicos no `prepare` (Relacionamentos, Conhecimento e Correção)
Criação e execução de sonda adversarial rápida para provar que `prepare` funciona com listas de relacionamentos, registros de conhecimento com proveniência e correções de eventos por `event_id`:

```powershell
python -c "
import tempfile, json
from pathlib import Path
from adapters.persistence.event_store import JsonlEventStore
from contracts.event import ActorRef, EventDraft
from resources.knowledge.drafts import make_claim_registered_draft, make_knowledge_acquired_draft
from resources.knowledge.model import HolderRef, ProvenanceRef
from application.rebuild import rebuild_projections
from application import cmd_prepare
from council import helpers

with tempfile.TemporaryDirectory() as tmp:
    camp = Path(tmp) / 'c1'
    camp.mkdir(parents=True)
    orig = list(helpers.CAMPAIGN_DIRS)
    helpers.CAMPAIGN_DIRS = [camp.parent]
    try:
        (camp / 'diario.md').write_text('<!-- schema_version: 1 -->\n# Diário\n### Cena 1\n* **Local:** Salão\n* **Presentes:** Aemon, Kael\n### Missões\n* **[Q1] Resgate** | Status: ACTIVE | Contratante: Rei | Alvo: Kael\n  * [ ] Salvar\n* **[Q2] Velha** | Status: COMPLETED | Contratante: Guarda | Alvo: Ladrão\n', encoding='utf-8')
        (camp / 'ficha.md').write_text('# Ficha\n* **Nome:** Aemon\n* **PV:** 20/20\n* **FOR:** 10 (+0)\n* **DES:** 10 (+0)\n* **VIG:** 10 (+0)\n* **VON:** 10 (+0)\n', encoding='utf-8')
        (camp / 'npcs.md').write_text('# NPCs\n### Kael\n* **Tier:** major\n* **Presença:** Presente\n', encoding='utf-8')
        (camp / 'regras.md').write_text('<!-- schema_version: 1 -->\n# Regras\n* system: d20_3gates\n', encoding='utf-8')
        (camp / 'mundo.md').write_text('# Mundo\n', encoding='utf-8')

        store = JsonlEventStore(camp)
        actor = ActorRef('human', 'gm')
        ev0 = EventDraft('campaign.created', 1, actor, {'title': 'c1', 'system': 'd20_3gates', 'calendar': 'standard', 'start_game_time': '01/01', 'config_version': 1}, '01/01', 0)
        ev1 = make_npc_relationship_updated_draft('Kael', 'Aemon', '01/01', 1, trust=-2, rivalry=2)
        ev2 = make_claim_registered_draft('clm_ouro', {'subject': 'ouro', 'predicate': 'guardado', 'object': 'cofre'}, 'state', '01/01', 2)
        prov = ProvenanceRef('event', 'evt_01', 'observation', '01/01', 3, 9000)
        ev3 = make_knowledge_acquired_draft('knw_01', HolderRef('protagonist', 'Aemon'), 'clm_ouro', '01/01', 4, provenance=[prov])
        ev4 = EventDraft('turn.committed', 1, actor, {'turn': 1, 'action': 'guarda', 'summary': 'Cofre selado'}, '01/01', 5)
        stored = store.append('c1', [ev0, ev1, ev2, ev3, ev4])
        ev4_id = stored.events[-1].event_id
        ev5 = EventDraft('correction.issued', 1, actor, {
            'correction_id': 'corr_1',
            'corrects': [ev4_id],
            'reason': 'Cofre aberto',
            'changes': []
        }, '01/01', 6)
        store.append('c1', [ev5])
        rebuild_projections(store, 'c1', camp, emit_audit_event=True)

        res = cmd_prepare('c1', action='Observar Kael', no_roll=True)
        assert res is not None
        assert 'context' in res
        # Missão concluída Q2 não pode figurar no quest_pressure_mandate
        assert 'Velha' not in res['step_1_quest_context']['quest_pressure_mandate']
        print('OK: Sonda de dados canônicos passou com sucesso')
    finally:
        helpers.CAMPAIGN_DIRS = orig
"
```
*Resultado esperado:* `OK: Sonda de dados canônicos passou com sucesso`

---

### Cenário 3: Ausência de Loop de Staleness após `rebuild`
Verifica que o comando `rebuild` com `emit_audit_event=True` não deixa o cache eternamente obsoleto:

```powershell
python -c "
import tempfile
from pathlib import Path
from adapters.persistence.event_store import JsonlEventStore
from contracts.event import ActorRef, EventDraft
from application.rebuild import rebuild_projections
from application.context.state import ContextStateViewImpl

with tempfile.TemporaryDirectory() as tmp:
    camp = Path(tmp) / 'c1'
    camp.mkdir(parents=True)
    store = JsonlEventStore(camp)
    actor = ActorRef('human', 'gm')
    ev0 = EventDraft('campaign.created', 1, actor, {'title': 'c1', 'system': 'd20_3gates', 'calendar': 'standard', 'start_game_time': '01/01', 'config_version': 1}, '01/01', 0)
    store.append('c1', [ev0])
    (camp / 'diario.md').write_text('<!-- schema_version: 1 -->\n# Diário\n', encoding='utf-8')
    (camp / 'regras.md').write_text('<!-- schema_version: 1 -->\n# Regras\n* system: d20_3gates\n', encoding='utf-8')
    
    # Rebuild com emissão de evento de auditoria
    rebuild_projections(store, 'c1', camp, emit_audit_event=True)

    # Leitura do cache: deve ser fresco (stale=False)
    view = ContextStateViewImpl.load('c1', camp, store=store)
    assert not view.stale, 'Cache não pode estar stale após rebuild'
    print('OK: Cache fresco sem loop de staleness')
"
```
*Resultado esperado:* `OK: Cache fresco sem loop de staleness`

---

### Cenário 4: Execução da Suíte Completa e Limites Arquiteturais

```powershell
python -m unittest tests/test_architecture_boundaries.py
python -m unittest tests/test_phase04_causal_context.py
python -m unittest tests/test_phase04_state_cache.py
python -m unittest discover -s tests -p "test_*.py"
```
*Resultado esperado:* Todos os testes passam com zero falhas e limites estritos de 300 linhas respeitados.
