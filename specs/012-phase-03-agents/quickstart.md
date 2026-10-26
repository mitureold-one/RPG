# Quickstart & Verification Guide: 012 — Fase 03: Agentes, Conhecimento Epistêmico e Refatoração R2

**Feature:** `phase-03-agents`  
**Status:** Ready for Verification  
**Created:** 2026-10-26  
**Context:** Guia executável passo a passo para validação dos 17 critérios de aceitação ratificados no Gate G3 (`AT01` a `AT17`) e das garantias estruturais da refatoração R2.

---

## 1. Pré-Requisitos e Baseline

Antes e depois da implementação da Fase 03 / R2, toda a suíte existente (211 testes) mais os novos testes de agentes, conhecimento e fronteiras devem passar sem avisos:

```bash
python -m unittest discover -s tests -p "test_*.py"
python -m unittest tests.test_architecture_boundaries
```

---

## 2. Verificação Estrutural da Refatoração R2

1. **Fachadas Enxutas em `council/`:**
   - `council/narrator.py` < 100 linhas (delega para `resources/npcs/`).
   - `council/factions.py` < 100 linhas (delega para `resources/factions/`).
   - `council/quests.py` < 100 linhas (delega para `resources/quests/`).
2. **Teto Estrito `< 300` Linhas:**
   - Todos os módulos em `resources/npcs/`, `resources/factions/`, `resources/quests/`, `resources/knowledge/`, `resources/admission.py` e `application/projectors/faction.py` verificados por `tests/test_architecture_boundaries.py`.

---

## 3. Verificação dos 17 Cenários de Aceite (AT01 a AT17)

A suíte dedicada `tests/test_phase03_agents_and_g3.py` executa e valida cada um dos 17 cenários determinísticos:

```bash
python -m unittest tests.test_phase03_agents_and_g3 -v
```

### Resumo das Asserções Objetivas por Cenário:
- **AT01 (Fato vs crença):** Registrar alegação `rei_morreu` sem evento canônico de morte (`resolve_claim -> FALSE`); registrar `knowledge.acquired` do NPC com `stance="believed"`. Verificar que o NPC acredita na alegação enquanto `resolve_claim` permanece `FALSE`.
- **AT02 (Conhecer sem acreditar):** Registrar `knowledge.acquired` com `awareness="known"` e `stance="disbelieved"`. Verificar que `can_use_claim(require_belief=True)` é `False`, mas `query_claim().availability == "known"`.
- **AT03 (Proveniência):** Tentar adquirir conhecimento sem `ProvenanceRef` ou com `source_id` vazio -> rejeitado com erro de validação; com `ProvenanceRef` válido -> auditável até a fonte.
- **AT04 (Informação falsa):** NPC com crença falsa (`stance="believed"`, `resolve_claim == "FALSE"`) propõe plano baseado nessa alegação -> `validate_intent_admission` admite o plano (intenção operacional), mas o fato canônico do mundo continua `FALSE`.
- **AT05 & AT12 (Desatualização != Falso):** Alegação de estado válida em `t=100` (`valid_to=200`) passa a `status="outdated"` em `t=300` quando a situação muda, permanecendo distinta de `status="refuted"` e verdadeira em `resolve_claim(at_time_sort=150)`.
- **AT06 (Inferência):** Emitir `knowledge.inferred` com `derived_from=[knw_1, knw_2]`. Verificar que a conclusão é registrada como inferência provisória e `resolve_claim` não a promove a fato canônico.
- **AT07 (Conhecimento coletivo):** NPC membro de facção adquire segredo com `visibility="holder_only"`. Consultar `KnowledgeView` para outro membro e para a facção -> retorna `availability="unknown"`.
- **AT08 (Segredo do jogador):** Registrar evento/conhecimento com `holder=("player", "player")` e `visibility="player_meta"`. Submeter proposta do protagonista exigindo esse `claim_id` -> rejeitada pelo validador de admissão.
- **AT09 (Proposta não admitida):** Submeter proposta de plano/objetivo exigindo recurso insuficiente ou alegação `unknown` -> `AdmissionResult.admitted == False`; replay do log ignora a proposta rejeitada.
- **AT10 & AT15 (Reconstrução, correção e crença):** Emitir fato `evt_1`, NPC adquire crença baseada em `evt_1`; depois emitir `correction.issued` sobre `evt_1`. Verificar que o fato canônico é corrigido, mas a crença do NPC permanece `believed` até que `knowledge.revised` seja emitido para aquele NPC.
- **AT11 (Fontes contraditórias):** Mesmo NPC recebe duas `ProvenanceRef` conflitantes (`supports=True` e `supports=False`) sobre o mesmo `claim_id`. O registro consolidado fica com `status="contested"`, preservando ambas as fontes.
- **AT13 (Inferência com premissa refutada):** Premissa `knw_1` é refutada via `knowledge.revised(status="refuted")`. A inferência dependente mantém seu registro histórico sem virar fato e sinaliza premissa comprometida.
- **AT14 (Facção dividida):** Liderança compartilha conhecimento com `scope="subgroup_only"` para `ala_leal`; subgrupo `ala_dissidente` com `stance_towards_leadership="conspiring"` não recebe o conhecimento e mantém plano próprio divergente.
- **AT16 (Replay e snapshot):** Executar `rebuild_projections` do zero e a partir de snapshot com eventos de NPCs, facções e conhecimento -> `npcs.md`, `faccoes.md` e o estado epistêmico reconstruído são byte-idênticos.
- **AT17 (Visibilidade em `KnowledgeView`):** Consultar `KnowledgeView` com audiências cruzadas (`npc_a` tentando ler segredo de `npc_b` ou `faction_internal` de facção rival) -> bloqueado com `availability="unknown"` ou `"unavailable"`.
