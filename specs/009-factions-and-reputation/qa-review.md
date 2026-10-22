# QA Review — 009 factions-and-reputation (Fase 3)

**Commits auditados:** `e26009e` (fechamento dos achados da 007/008) e `ba847e0` (Fase 3).
**Data da Revisão Original:** 22 de Outubro de 2026.
**Data da Remediação:** 22 de Outubro de 2026.
**Método:** leitura do diff completo, execução do gate em campanha descartável (`_qa3`) e em uma cópia de `dinastia_cinzas` (`_qa4`), regressão nas 3 campanhas reais, suíte sob sandbox.

---

## 0. Atualização pós-remediação

**Veredito atual: Fase 3 aprovada com todos os 4 P1 e defeitos P2 corrigidos e verificados por testes unitários e de integração.**
A suíte avançou para 56/56 testes 100% OK em ambiente sandbox. As 3 campanhas canônicas estão íntegras e limpas.

| Achado | Status | Evidência da reverificação |
| :--- | :---: | :--- |
| **P1-A** Economia de XP farmável | **Corrigido** | `cmd_clock` valida transição `ACTIVE -> RESOLVED` (segunda resolução concede 0 XP); `cmd_arc` valida unicidade do marco antes de creditar +80 XP. Testado em `test_p1_a_clock_resolve_and_arc_milestone_idempotence`. |
| **P1-B** Modificador social nunca chega ao modelo | **Corrigido** | Campo `* **Facção / Afiliação:**` adicionado aos templates e preenchido nas 3 campanhas canônicas. `resolve_scene_factions` implementa inferência por citação em `mundo.md`/papel e injeção por território em `location`. Testado em `prepare --campaign dinastia_cinzas` (emite `social_dc_mod: -2` e diretiva aliada) e em `test_p1_b_resolve_scene_factions_inference_and_territory`. |
| **P1-C** Falso-positivo em `FACTION_REP_MISMATCH` | **Corrigido** | Comparação refeita contra `new_score` do último registro no ledger em vez de soma de deltas a partir de zero. Clampeamento no teto (+3) e baselines herdados não geram mais divergência. Testado em `test_p1_c_reputation_mismatch_no_false_positive_on_clamp_or_baseline`. |
| **P1-D** `FACTION_UNKNOWN` falha por colisão de palavras | **Corrigido** | Adicionada lista canônica de `FACTION_STOPWORDS` (`ordem`, `conselho`, `guarda`, `clã`, etc.) antes da interseção de tokens. `Ordem Fantasma` agora dispara `FACTION_UNKNOWN` HIGH mesmo com `Ordem Estabelecida` em `mundo.md`. Testado em `test_p1_d_faction_unknown_detects_phantom_with_stopword`. |
| **P2-1** `faction --rep` em facção inexistente | **Corrigido** | Emite aviso explícito no `stderr` e grava `"warning"` no payload caso a facção não conste em `mundo.md`. Split seguro por `rsplit(":", 1)`. |
| **P2-2** O tick não deixa rastro | **Corrigido** | `simulate_faction_tick` persiste registro factual em `diario.md` sob `### Movimentações de Facções Off-Screen` identificando autoria, relógio, novo progresso e turnos. |
| **P2-3** `campaign` vazio no tick | **Corrigido** | `find_campaign` agora inclui `"id": campaign_id` em seu dicionário canônico e `cmd_faction` propaga o id para o retorno do tick. |
| **P2-4** Vocabulário de escala | **Corrigido** | `global` adicionado ao conjunto de escolhas da CLI e normalizado em `VALID_SCALES`. |
| **P2-5** Território ignorado | **Corrigido** | Unificado com P1-B: parâmetro `location` agora injeta a facção territorial com bônus/penalidade e diretiva de jurisdição. |

---

## 1. Veredito Original (Histórico)

**Arquitetura aprovada. Entrega da Fase 3 reprovada por 4 P1.** A base é sólida — parsing tolerante a legado, ledger de reputação que faz round-trip, tick off-screen determinístico e retrocompatibilidade limpa. Mas dois defeitos atingem exatamente o que a fase prometia entregar (o modificador social nunca chega ao modelo; a economia de XP pode ser farmada) e dois tornam a camada de auditoria não confiável (um lint que sempre acusa e outro que nunca acusa).

| Gravidade | Qtd | Bloqueia declarar a Fase 3 entregue |
| :--- | :-: | :--- |
| P0 | 0 | — |
| P1 | 4 | Sim |
| P2 | 5 | Recomendado |
| P3 | 3 | Não |

---

## 2. Gate — resultado

| # | Passo | Resultado |
| :-: | :--- | :--- |
| 1 | Suíte completa sob sandbox | **Passa** — 51 testes OK sem elevação, nenhum `mkdtemp` restante |
| 2 | `faction --list` em campanha legada | **Passa** — bullets de prosa viram facções com tag derivada |
| 3 | `faction --add` + `--tick` | **Passa** — facção Poder 5 avança o relógio vinculado |
| 4 | `--rep`, `--favor`, `--debt` | **Passa** — clamp, escalões, favores/débitos não-negativos, ledger |
| 5 | `prepare` → `step_1_faction_context` | **Falha de integração** — só funciona se o NPC tiver campo `Facção`, que não existe em template nem campanhas |
| 6 | Missão com contratante → reputação | **Passa** — +1 rep e +1 favor; contratante inexistente cria facção fantasma |
| 7 | Lints de facção | **Parcial** — `FACTION_ORPHANED_NPC` e `FACTION_ATTITUDE_DESYNC` corretos; `FACTION_UNKNOWN` falha por colisão de palavra; `FACTION_REP_MISMATCH` falso-positivo |
| 8 | P1-4 anterior (XP de relógio/arco) | **Corrigido** — `clock --resolve` +40 e `arc --milestone` +80, com ledger e guarda de vínculo |
| 9 | P1-7 anterior (pagamento duplicado) | **Corrigido** — alerta persistido no turno e lint `CRITICAL` dispara |
| 10 | Retrocompatibilidade | **Passa** — 3 campanhas CLEAN, apenas o `STALE_NPC_ATTITUDE` pré-existente |

---

## 3. P1 — Bloqueantes

### P1-A — Economia de XP farmável por repetição de comando

Repetir a resolução do mesmo relógio credita +40 de novo; repetir o mesmo marco de arco credita +80 de novo.

```text
clock --resolve "Prazo Final"   -> xp_granted: 40   (1a vez)
clock --resolve "Prazo Final"   -> xp_granted: 40   (2a vez, relógio já RESOLVED)
arc --milestone "Queda do portao" -> arc_milestone_xp: 80 (2a vez)
XP: 330 -> 450
```

O bloco de `cmd_clock` ([lazy_turn.py:565-578](lazy_turn.py#L565-L578)) concede depois do update, sem comparar o status anterior; o de `cmd_arc` ([lazy_turn.py:683-695](lazy_turn.py#L683-L695)) concede sempre que `--milestone` é passado. O `XP_MISMATCH` não pega, porque o ledger registra cada concessão e a reconciliação continua fechando.

**Correção:** capturar o status anterior e só creditar na transição `ACTIVE -> RESOLVED`; no arco, só creditar se o marco ainda não constar em `Marcos da Crônica`. Foi exatamente a classe de bug corrigida nas missões — a lição não foi generalizada para as novas fontes.

### P1-B — O modificador social nunca chega ao modelo

`resolve_scene_factions` só reconhece facção por `npc["faction"]` ([factions.py:674-681](council/factions.py#L674-L681)). Nenhuma das 3 campanhas tem esse campo em `npcs.md`, e `templates/npcs.template.md` não o inclui. Resultado: `step_1_faction_context.factions_in_scene` é sempre `[]` em produção, e o `social_dc_mod`/`suggested_variant` — o payoff mecânico da fase — nunca entra no payload. O parâmetro `location` da função é declarado e nunca usado ([factions.py:658-661](council/factions.py#L658-L661)), então facção territorial também não entra.

Verificado: adicionando `* **Facção / Afiliação:** Ordem Estabelecida` a um NPC, o payload passa a trazer `social_dc_mod: 0` e a diretiva de postura. Sem o campo, nada.

**Correção:** incluir o campo no template (default `Independente`), preencher nas 3 campanhas e/ou inferir afiliação a partir de `mundo.md`/`npcs.md`; usar `location` para facção dominante do território.

### P1-C — `FACTION_REP_MISMATCH` acusa corretamente formatos errados

O lint soma `delta_rep` do ledger e compara com o valor absoluto da ficha ([reviewer.py:636-655](council/reviewer.py#L636-L655)). Como o valor inicial nunca é registrado, qualquer reputação que não comece em 0 gera divergência. Dois casos provados:

* **Teto:** ficha em +3 (Venerado) e um `+1` clampeado → ledger soma 4, ficha 3 → HIGH falso.
* **Legado:** cópia de `dinastia_cinzas` (Conselho começa em +2), primeiro `--rep +1` → ficha 3, ledger 1 → HIGH falso.

Consequência prática: as 3 campanhas reais passam a acusar divergência no primeiro ajuste de reputação, e campanhas que maxam reputação nunca voltam a CLEAN.

**Correção:** comparar o `new_score` do último lançamento daquela facção com a ficha (o dado já é gravado no ledger), ou registrar o baseline na primeira entrada.

### P1-D — `FACTION_UNKNOWN` não detecta facção fantasma

O cruzamento por palavra compartilhada de 5+ caracteres ([reviewer.py:574-590](council/reviewer.py#L574-L590)) roda sem a lista de exceções usada no fallback textual. Resultado: `Ordem Fantasma` foi aceita como conhecida por compartilhar o token `ordem` com `Ordem Estabelecida`. O ledger e a ficha registram a facção fantasma, e o lint não diz nada.

**Correção:** aplicar a mesma lista de stopwords (`ordem`, `conselho`, `guarda`, `clã`) antes da interseção; exigir match por tag ou nome exato/prefixo antes do fuzzy.

---

## 4. P2 — Defeitos de integração

**P2-1 — `faction --rep` cria facção inexistente em silêncio.** `update_reputation_in_ficha` não valida contra `mundo.md`; foi assim que a fantasma entrou. Deveria exigir `--add` prévio ou emitir aviso explícito.

**P2-2 — O tick não deixa rastro.** `simulate_faction_tick` devolve o relatório apenas em JSON e não grava nada no diário. Numa sessão futura, ninguém sabe qual facção avançou o quê; os relógios guardam o progresso, não a autoria. Falta um `### Movimentações Off-Screen` ou uma nota de turno.

**P2-3 — `campaign` vazio no tick.** `campaign_info.get("id", "")` ([factions.py:647](council/factions.py#L647)) — `find_campaign` não retorna `id`, então o campo sai vazio.

**P2-4 — Vocabulário de escala divergente.** A CLI aceita `local, urbano, regional, continental, planar`; a spec fala em `global`. `format_faction_line` grava o que vier, sem normalizar.

**P2-5 — `resolve_scene_factions` ignora território.** Ver P1-B; NPC é o único caminho de entrada.

---

## 5. P3 — Higiene

* `cmd_faction(list_factions=...)` não usa o parâmetro: `--list` é comportamento default e o parâmetro morto engana quem for integrar.
* Nomes de facção com `:` quebram `--rep/--favor/--debt` (split simples).
* O tick é determinístico e "sempre ligado" para Poder 4-5 (avança em todo tick), enquanto a spec descreve "maior probabilidade/frequência". Funciona, mas convém documentar a regra real.

---

## 6. O que está bom

* **Suíte sob sandbox**: 51 testes OK sem elevação — o P3-15 foi resolvido de verdade, não contornado.
* **P1-7 fechado de forma correta**: a tentativa barrada vira linha `**Alerta:**` no turno e o lint dispara `CRITICAL` na auditoria.
* **P1-4 fechado**: relógio resolvido e marco de arco creditam XP com ledger, e o guard de vínculo com missão ativa funciona (resolver relógio ligado a missão ativa não credita).
* **Conversão de legado**: a linha única `Reputação com Facções: A (Favorável), B (Suspeita)` virou bullets estruturados preservando as duas facções.
* **Ledger de reputação faz round-trip** com turno, delta, score resultante, favores, débitos, motivo e missão.
* **Lints precisos**: `FACTION_ORPHANED_NPC` e `FACTION_ATTITUDE_DESYNC` dispararam nos cenários corretos, inclusive respeitando a exceção psicológica.
* **Retrocompatibilidade**: 3 campanhas reais sem novos lints.

---

## 7. Recomendação

Corrigir os 4 P1 antes de declarar a Fase 3 entregue. Os quatro são localizados (uma guarda de transição, um campo de template, um comparador e um filtro de stopwords) e não exigem mudança arquitetural.

Para a sequência, manter o hábito que esta rodada expôs: antes de liberar um sistema novo, verificar (a) idempotência de toda fonte de recurso, (b) se o dado que o motor calcula realmente chega ao payload, e (c) se cada lint tem um teste que o faça **disparar** e outro que o faça **silenciar** no caso legítimo. Nenhuma dessas três checagens existia para a Fase 3.
