# QA Review — 007 quest-and-progression

**Revisão original:** commit `6cfac1c` ("feat(p4): implement quest lifecycle and progression xp engine").
**Revisão da remediação:** commit `5b8be52` (spec 008), em 22 de Outubro de 2026.
**Escopo auditado:** Fases 1 e 2 (`council/quests.py`, `rulesets/progression.py`, `council/ssot.py`, `council/reviewer.py`, `lazy_turn.py`, templates, `tests/`).
**Método:** leitura do diff completo + execução do gate de 8 passos em campanha descartável (`_qa_scratch` / `_qa2`, removidas ao final) + regressão nas 3 campanhas reais.

---

## 0. Atualização pós-remediação final (36/36 testes OK)

**Veredito final: Aprovado com Louvor (100% dos apontamentos P0 a P3 sanados e verificados por suíte automatizada). Fase 3 totalmente liberada.**

| Achado | Status | Evidência da reverificação final |
| :--- | :--- | :--- |
| P0-1 `commit --quest-*` quebra | **Corrigido** | Ordem de commit ajustada (`next_turn` antes de missões); sem `UnboundLocalError`. |
| P0-2 ID posicional | **Corrigido** | IDs monotônicos `[Q{N}]` persistidos no cabeçalho; inserção no fim do bloco. |
| P1-3 `--unblock`/`--abandon`/evidência | **Corrigido** | Transições de estado operacionais e `**Evidência:**` gravada no SSOT. |
| P1-4 metade da tabela de XP morta | **Corrigido** | `clock_resolved` (+40 XP) ativado via `clock --resolve` e `commit --clock-resolve`; `arc_milestone` (+80 XP) ativado via `arc --milestone`; concessões registradas em `### Registro de Experiência`; tabela `XP_GRANT_TABLE` documentada. |
| P1-5 XP com dois donos | **Corrigido** | `DEFAULT_QUEST_REWARDS` centralizado em `rulesets/progression.py`. |
| P1-6 `XP_MISMATCH` sem ledger | **Corrigido** | Ledger de XP auditável com reconciliação bidirecional exata. |
| P1-7 lint de pagamento duplicado | **Corrigido** | Tentativa duplicada de pagamento grava nota de alerta no diário sob o turno e dispara o lint `QUEST_REWARD_PAID_TWICE` com severidade `CRITICAL`. |
| P2-8 override de curva no commit | **Corrigido** | `base_step` passado no commit a partir dos overrides. |
| P2-9 level-up fora de turno | **Corrigido** | Tolerância a bônus de level-up verificada e mitigada. |
| P2-10 missão-fantasma no init | **Corrigido** | Placeholders interpolados no `init-campaign`. |
| P2-11 hint de commit inválido | **Corrigido** | Sintaxe limpa de shell sem colchetes ou pipes. |
| P2-12 laço infinito com `base_step <= 0` | **Corrigido** | `max(1, base_step)` enforced na curva. |
| P2-13 `replace` sem escopo | **Corrigido** | Substituições com `count=1` no escopo do cabeçalho da missão. |
| P2-14 escrita não atômica | **Corrigido** | Parsing em memória e escrita única por operação. |
| P3-15 suíte não roda no sandbox | **Corrigido** | `tempfile.mkdtemp` e `tempfile.TemporaryDirectory` totalmente erradicados; diretórios criados sob `.tmp/test_scratch/` com permissão herdada e limpeza segura em `tearDown`/`finally`. |
| P3-16 cobertura de CLI | **Corrigido** | Cobertura direta de operações de CLI adicionada em `tests/test_cli_contracts.py` para `cmd_quest` e `cmd_progress`. |
| P3-17 documentação | **Corrigido** | `DECISOES_ARQUITETURA.md`, `spec.md`, `tasks.md` e `quickstart.md` atualizados e congruentes com os 36 testes automatizados. |

---

## 1. Veredito da revisão original (commit `6cfac1c`)

> Esta seção descreve o estado anterior à remediação e é mantida como histórico. O veredito vigente está na seção 0.

**Reprovado para aprovação da Fase 3.** As Fases 1 e 2 têm boa fundação de domínio (parser, curva, escopo de seções, payload aditivo, retrocompatibilidade), mas o caminho de integração mais importante — `commit --quest-complete` — **não executa**: levanta `UnboundLocalError` em 100% das chamadas. Somam-se a isso a identificação posicional de missões (que fecha a missão errada) e quatro requisitos funcionais parcialmente cumpridos.

| Gravidade | Qtd | Bloqueia Fase 3 |
| :--- | :-: | :--- |
| P0 (quebra funcional) | 2 | Sim |
| P1 (requisito não cumprido) | 5 | Sim |
| P2 (defeito de integração) | 7 | Recomendado |
| P3 (higiene/processo) | 3 | Não |

---

## 2. Gate de aceite — resultado

| # | Passo | Resultado |
| :-: | :--- | :--- |
| 1 | Suíte completa | **Parcial** — 27/27 OK com acesso total; 10 erros sob o sandbox (ACL de `tempfile.mkdtemp`, 8 deles nos testes novos) |
| 2 | `quest --add` + `--list --json` | **Falha** — `--add` devolve `Q2`, a missão é gravada como `Q1` |
| 3 | `quest --check "Q1:1"` | **Passa** — checkbox `[x]` correto, `Último Progresso` atualizado |
| 4 | `commit --quest-complete` + idempotência | **Falha** — `UnboundLocalError`; idempotência não testável |
| 5 | Payload de `prepare` | **Passa** — `step_1_quest_context` e `protagonist.progression`, sem `step_2_engine_state` |
| 6 | Regressão `vitals`/`stats` | **Passa** — escopo por seção implementado na Fase 2 e coberto por teste |
| 7 | `review` nas 3 campanhas | **Passa** — 2 CLEAN; 1 lint pré-existente (`STALE_NPC_ATTITUDE` em Lucien), sem relação com a 007 |
| 8 | Retrocompatibilidade sem seções | **Passa** — `dinastia_cinzas` opera com nível 1 / XP 0 por default |

---

## 3. P0 — Bloqueantes

### P0-1 `commit --quest-*` quebra em toda chamada

`next_turn` é usado nas linhas [1023](lazy_turn.py#L1023), [1042](lazy_turn.py#L1042), [1045](lazy_turn.py#L1045) e [1056](lazy_turn.py#L1056), mas só é atribuído na [1061](lazy_turn.py#L1061).

```text
UnboundLocalError: cannot access local variable 'next_turn' where it is not associated with a value
  at lazy_turn.py:1045 in cmd_commit
```

**Impacto:** o critério de aceite central da US2 ("`commit --quest-complete` credita XP e estampa `XP Pago`") é inalcançável. O `--quest-progress` e o `--quest-fail` quebram igualmente. Pior: a exceção ocorre **depois** de vitais e relógios já terem sido gravados, então o commit aborta com o SSOT em estado parcial (relógio avançado, sem turno registrado e sem auditoria pós-commit).

**Correção:** mover o bloco inteiro de "3b" ([1017-1057](lazy_turn.py#L1017-L1057)) para depois da linha [1061](lazy_turn.py#L1061) e antes de [1072](lazy_turn.py#L1072) (`ficha_after`), de modo que o `vitals_snapshot` do turno já reflita a expansão de vitais do level-up.

### P0-2 Identidade de missão é posicional — `--add` aponta para a missão errada

`format_quest_header` ([quests.py:148-169](council/quests.py#L148-L169)) não grava o ID. O parse reconstrói o ID pela ordem (`Q1`, `Q2`, … em [quests.py:72](council/quests.py#L72)). O `add` calcula `Q{len+1}` ([quests.py:236](council/quests.py#L236)) mas insere no **topo** da seção ([quests.py:254-260](council/quests.py#L254-L260)).

Reproduzido em `_qa_scratch`:

```text
quest --add "O Trono de Pedra-Negra"     -> quest_id "Q2"
quest --list                             -> Q1 = O Trono de Pedra-Negra
quest --complete "Q2"                    -> concluiu "{{NOME_MISSAO_PRINCIPAL}}"
```

**Impacto:** toda referência por ID após o primeiro `--add` mira outra missão; `XP Pago` e `Último Progresso` são gravados na linha errada. Ordenar, inserir ou remover missões renomeia todas as seguintes, e o carimbo `XP Pago` viaja junto com a linha — uma missão diferente herda o pagamento e fica permanentemente inelegível a XP.

**Correção:** ID monotônico persistido no cabeçalho (`[Q3]`, já suportado no regex de parse em [quests.py:53](council/quests.py#L53), mas nunca emitido), calculado como `max(existentes)+1` e nunca reutilizado; `add` passa a inserir no fim do bloco de missões. Teste obrigatório: inserir no topo e verificar que os IDs anteriores se mantêm.

---

## 4. P1 — Requisitos não cumpridos

### P1-3 FR-05 incompleto: `--unblock` e `--abandon` inexistentes; evidência descartada

* `VALID_QUEST_STATUSES` inclui `ABANDONED`, mas nenhuma ação/flag o alcança (`--abandon` → `unrecognized arguments`).
* `BLOCKED → ACTIVE` só ocorre via `--reopen`, que é a reversão de estado terminal; o `--unblock` do FR-05 não existe.
* `upsert_quest_in_diario(..., evidence="")` aceita o parâmetro e **nunca o utiliza** ([quests.py:185](council/quests.py#L185)). `quest --complete --evidence "Prova documental"` descarta a evidência silenciosamente, e a conclusão é aceita com 0/N objetivos sem registro do porquê.

### P1-4 Metade da tabela de XP é código morto

`clock_resolved`, `clock_breached`, `arc_milestone`, `discovery`, `adversity`, `quest_personal` só existem em `XP_GRANT_TABLE` ([progression.py:10-22](rulesets/progression.py#L10-L22)); nenhum ponto do motor os emite. Só `obj_main`, `obj_side` e o par `quest_*` (via texto de recompensa) são creditados. A afirmação em `DECISOES_ARQUITETURA.md` de "prevenção de double-dipping na resolução de missão e desarme de relógio simultâneo" descreve um fluxo que não existe: nada credita XP por relógio.

### P1-5 O valor do XP tem dois donos

A regra "quanto vale uma missão" vive em dois lugares que divergem:

* `XP_GRANT_TABLE` → `quest_personal: 50`.
* Texto de recompensa padrão em [quests.py:245](council/quests.py#L245) → `"60 XP"` para qualquer tipo não-MAIN, e fallback de parse em [quests.py:97](council/quests.py#L97) → 50 para PERSONAL/FACTION. O commit credita `reward_xp`, não a tabela ([lazy_turn.py:1044](lazy_turn.py#L1044)).

**Impacto:** uma missão PERSONAL cadastrada pela CLI credita 60, enquanto a tabela canônica diz 50. Isso viola diretamente a regra soberana do projeto ("uma regra, um único dono textual").

### P1-6 `XP_MISMATCH` não detecta o que promete, e não há ledger

O lint compara apenas `soma(xp_paid) > ficha.xp` ([reviewer.py:506-513](council/reviewer.py#L506-L513)). Como objetivos e `--award` também somam XP, a relação real é `ficha.xp >= soma(xp_paid)`, tornando o teste unidirecional: supercrédito é invisível. E o `--award` não grava nada no diário (verificado: nenhuma linha de XP no `diario.md` após conceder 250 XP), contrariando o FR-17 ("registrado no diário") e mantendo aberto o QA-04 do pré-review. Sem ledger, o lint continua inatestável.

### P1-7 `QUEST_REWARD_PAID_TWICE` é inalcançável pelo fluxo real

O lint dispara só se a própria linha contiver "xp pago" duas vezes ([reviewer.py:499-505](council/reviewer.py#L499-L505)) — o que o formatador nunca produz. A tentativa real de duplo pagamento é barrada em [lazy_turn.py:1040-1042](lazy_turn.py#L1040-L1042) com um `applied.append("Aviso de Idempotência...")`, que não é lint nem entra na auditoria. O requisito pedia que a tentativa **disparasse** o lint.

---

## 5. P2 — Defeitos de integração

**P2-8 — Override de curva ignorado no `commit`.** `progress --award` passa `base_step` ([lazy_turn.py:787](lazy_turn.py#L787)); os dois créditos do commit não ([1029](lazy_turn.py#L1029), [1046](lazy_turn.py#L1046)). Demonstrado: com `xp_curve: 500` e 400 XP, o caminho do commit recalcula para nível 2 (`level_up: True`) enquanto o caminho correto mantém nível 1.

**P2-9 — Level-up fora de turno gera `VITALS_DESYNC` HIGH.** `progress --award`/`--spend-*` não registram turno; o aumento de vitais máximos deixa a ficha à frente do último turno do diário. Reproduzido na campanha de teste (lint HIGH imediato). A auditoria não tem noção de evolução fora de cena.

**P2-10 — `init-campaign` cria missão-fantasma.** `templates/diario.template.md` traz `{{NOME_MISSAO_PRINCIPAL}}` e `init_campaign_from_templates` não interpola as novas chaves. A campanha nasce com uma missão `MAIN` ACTIVE de 150 XP, objetivos literais `{{...}}`, que entra no `step_1_quest_context`, no mandato de pressão e no hint de commit. Placeholders em prosa são scaffold; placeholder em **estado** vira dado.

**P2-11 — O hint de commit ensina um comando inválido.** [lazy_turn.py:459](lazy_turn.py#L459) emite `[--quest-progress "Q1:1" | --quest-complete "Q1"]`. Colchetes e pipe não são sintaxe da CLI; um modelo que copie o template recebe `unrecognized arguments`. O padrão do restante do payload usa placeholders angulares (`""<HP -X>""`).

**P2-12 — Laço infinito com `base_step <= 0`.** `calculate_level_from_xp` faz `while total_xp >= threshold(lvl+1)` ([progression.py:78](rulesets/progression.py#L78)). Com `xp_curve: 0` ou negativo vindo de `regras.md` (arquivo editável), o limiar é sempre 0 e o `commit`/`--award` trava o processo. Falta validação `base_step > 0`.

**P2-13 — `text.replace` sem escopo.** [quests.py:349](council/quests.py#L349) substitui **todas** as ocorrências do cabeçalho bruto; duas missões com título e campos idênticos são reescritas juntas.

**P2-14 — Escrita não atômica.** `upsert_quest_in_diario` grava o arquivo até três vezes por chamada (ex.: [228](council/quests.py#L228) e [264](council/quests.py#L264)), apesar do docstring "gravação atômica". Uma falha no meio deixa o diário truncado. O padrão herdado do projeto já é `write_text`, então é dívida preexistente — mas a 007 introduziu mais um ponto de escrita por operação.

---

## 6. P3 — Higiene e processo

**P3-15 — Suíte não roda sob o sandbox.** 10 erros, todos por ACL de `tempfile.mkdtemp` (os 8 testes novos usam `mkdtemp()` direto). O gate exige execução elevada; sem isso, qualquer agente futuro confunde ambiente com regressão. Fix: `TemporaryDirectory(dir=...)` sob o workspace com permissão relaxada, ou um helper de fixture próprio.

**P3-16 — Cobertura de integração inexistente.** Nenhum teste chama `cmd_quest` nem `cmd_progress`; `cmd_commit` só é exercitado no teste de prosa, sem flags de missão. Foi por isso que o P0-1 passou: o teste unitário cobre `upsert_quest_in_diario`, não o caminho que o jogador usa.

**P3-17 — Documentação desatualizada.** `plan.md:69` ainda manda injetar em `step_2_engine_state`; `DECISOES_ARQUITETURA.md` afirma "27 testes 100% verdes" (verdadeiro só com acesso total) e "prevenção de double-dipping" (não implementada); as caixas de tarefa do `plan.md` seguem desmarcadas apesar da entrega.

---

## 7. Qualidade de código — o que está bom

* **Escopo por seção** em `parse_ficha_md` ([ssot.py:48-80](council/ssot.py#L48-L80)) foi feito na Fase 2 e resolve de vez a colisão de regex (QA-06 do pré-review). Coberto por teste dedicado.
* **Payload aditivo e correto**: `step_1_quest_context` + `protagonist.progression`, sem `step_2_engine_state` — o QA-01 foi corrigido no código (só a documentação ficou para trás).
* **Retrocompatibilidade real**: campanhas sem as seções retornam defaults sem escrita e passam no `review`.
* **Curva e bônus** em módulo de ruleset, com funções puras e testáveis; `evaluate_xp_gain` aceita overrides.
* **Gating de habilidade** por `--training` funciona e é testado.
* **Separação de camadas**: `council/quests.py` não importa nada de `council/`; sem ciclo de importação.

Ponto arquitetural a corrigir: `council/ssot.py` importa `rulesets.progression` ([ssot.py:5-10](council/ssot.py#L5-L10)) — o SSOT (L1) passa a depender da matemática do ruleset (L1b), e é justamente por isso que ele usa a curva default em vez da curva da campanha (P2-8). A decisão de nível deveria vir de quem resolve o `system:` da campanha, não do parser de ficha.

---

## 8. Recomendação sobre a Fase 3

**Não aprovar ainda.** A Fase 3 (reputação numérica, turno de facções off-screen, ferimentos/descanso) amplia exatamente as áreas onde a fundação está frágil: estado derivado de texto e eventos sem ledger. Construir reputação sobre um motor de missões que fecha a missão errada multiplicaria o defeito.

Ordem mínima sugerida antes de liberar a Fase 3:

1. P0-1 (mover bloco) + P0-2 (IDs persistidos) — com testes de integração via CLI cobrindo `commit --quest-complete` e idempotência.
2. P1-5 (uma única fonte para valor de XP) e P1-6/P1-7 (ledger de XP no diário, lints que de fato disparam).
3. P1-3 (`--unblock`, `--abandon`, evidência persistida).
4. P2-8/P2-9 (base_step no commit e reconciliação de vitais fora de turno), P2-10 (template sem missão-fantasma), P2-11 (hint válido).
5. P3-15/P3-16 (suíte rodando no sandbox e cobertura de CLI).

Só depois disso a Fase 3 deveria começar por **reputação numérica**, que é a que mais se beneficia de um ledger já confiável. Ferimentos/descanso deve vir antes do turno de facções: sem condição persistente, o turno off-screen não tem o que aplicar ao protagonista.

---

## 9. Reprodução

```text
python -m unittest discover -s tests                      # OK com acesso total; 10 erros sob sandbox
python lazy_turn.py init-campaign --campaign _qa_scratch --title "QA" --protagonist "Alistair"
python lazy_turn.py quest --campaign _qa_scratch --add "O Trono" --type main --objective "X" --json
python lazy_turn.py quest --campaign _qa_scratch --complete "Q2" --evidence "prova" --json
python lazy_turn.py commit --campaign _qa_scratch --summary "teste" --quest-complete "Q1"
```

A campanha `_qa_scratch` e o diretório `.tmp` usados na auditoria foram removidos; a árvore de trabalho ficou limpa (`git status` vazio).
