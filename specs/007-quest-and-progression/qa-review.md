# QA Review — 007 quest-and-progression

**Papel:** analista de qualidade do código (revisão independente).
**Status:** pré-implementação — nenhum código da spec foi escrito ainda.
**Data:** 22 de Outubro de 2026.
**Referências:** `specs/007-quest-and-progression/spec.md`, `checklists/requirements.md`, `DECISOES_ARQUITETURA.md`, código atual em `council/`, `rulesets/`, `lazy_turn.py`.

---

## 1. Estado verificado do repositório

| Item | Situação |
| :--- | :--- |
| `specs/007-quest-and-progression/spec.md` | Existe (271 linhas), `.specify/feature.json` aponta para a pasta |
| `checklists/requirements.md` | Existe, todos os itens marcados |
| `plan.md` / `tasks.md` | **Ausentes** — a spec está em "Ready for Planning", sem plano técnico |
| `council/quests.py` | **Ausente** |
| `rulesets/progression.py` | **Ausente** |
| Subcomandos `quest` / `progress` em `lazy_turn.py` | **Ausentes** (grep sem ocorrências) |
| Seções `### Missões & Objetivos` / `### Progressão` nos templates | **Ausentes** |
| `git status` | Apenas `.specify/feature.json` modificado e `specs/007-.../` não rastreado |

Conclusão: não há o que auditar em código. Esta revisão antecipa os defeitos que fariam a implementação falhar no gate de aceite.

---

## 2. Baseline da suíte (antes de qualquer mudança)

```text
python -m unittest discover -s tests   →  Ran 19 tests — OK  (com acesso total)
python -m unittest discover -s tests   →  Ran 19 tests — 2 errors (under sandbox)
```

Os 2 erros são ambientais, não regressões: `tempfile.mkdtemp` cria diretórios com ACL restritiva e o sandbox do harness nega a criação de subdiretórios dentro deles (`PermissionError` em `test_p2_schema_version_and_loud_failures` e `test_p3_check_prose_cli_and_commit_enforcement`). Redirecionar `TEMP`/`TMP` para o workspace não resolve — a ACL é herdada do `mkdtemp`. O gate da spec 007 precisa rodar a suíte com acesso elevado ou os testes novos não podem depender de `tempfile`.

Observação: o comando termina com exit code 1 no PowerShell mesmo em caso `OK`, porque o unittest escreve em stderr. O gate deve olhar a linha `OK`/`FAILED`, não o exit code.

---

## 3. Achados — spec versus código real

### QA-01 — P1 — FR-14 referencia um bloco de payload que não existe

A spec manda injetar em `step_2_engine_state.protagonist` ([spec.md:81](spec.md#L81), [spec.md:174](spec.md#L174)). O payload real não tem `step_2_engine_state`: ele expõe `protagonist` no topo e `step_2_narrator_briefing` ([lazy_turn.py:412](lazy_turn.py#L412), [lazy_turn.py:425](lazy_turn.py#L425)). O teste de contrato também afirma `step_2_narrator_briefing` ([test_boundary_contracts.py:219](tests/test_boundary_contracts.py#L219)).

A deriva é anterior à 007: a spec 006 já cita `step_2_engine_state` ([spec 006:96](../006-rule-verification-p3/spec.md#L96)) enquanto o código entrega `step_2_narrator_briefing`.

**Impacto:** o implementador vai criar uma chave nova (`step_2_engine_state`) e duplicar o protagonista, ou gravar no lugar errado. Qualquer teste que congele o payload depois disso ratifica a duplicata.
**Recomendação:** emendar a spec para `protagonist.progression` (topo) e corrigir também a spec 006; adicionar teste que falhe se `step_2_engine_state` aparecer.

### QA-02 — P1 — ID de missão derivado de ordem é instável

[spec.md:101](spec.md#L101) admite "Q1, Q2 baseado na ordem ou hash curto". Se o ID nascer da posição, cadastrar uma missão no topo renumera todas as seguintes e quebra `quest --check "Q2:1"` e o histórico `XP Pago`.

**Recomendação:** ID monotônico (`max(existentes) + 1`), nunca reutilizado, gravado na linha; nunca recalculado a partir da ordem. Teste: inserir `Q0` no topo e verificar que `Q1` continua sendo `Q1`.

### QA-03 — P1 — Duplo crédito objetivo + missão sem regra explícita

A tabela dá `obj_main` 40 e `quest_main` 150 ([spec.md:174-186](spec.md#L174-L186)). A máquina de estados permite `--complete` com evidência mesmo com objetivos abertos ([spec.md](spec.md#L113)). Não está definido se objetivos abertos são auto-marcados nem se rendem XP na conclusão.

**Impacto:** o total de XP passa a depender da ordem das chamadas (marcar tudo e depois concluir ≠ concluir direto), e `XP_MISMATCH` fica impossível de satisfazer.
**Recomendação:** regra única — XP de objetivo só existe em `--check`; `--complete` credita exclusivamente `quest_*`; objetivos abertos no fechamento são listados como pendências, não auto-marcados. Cobrir com teste de duas sequências que devem produzir o mesmo total.

### QA-04 — P1 — `XP_MISMATCH` não tem ledger onde se apoiar

O lint compara a soma dos créditos históricos "no diário" com o total da ficha ([spec.md:188](spec.md#L188)), mas nenhum formato de registro de XP é definido — o `commit` grava apenas resumo, vitais e mudança de estado ([lazy_turn.py:888-893](lazy_turn.py#L888-L893)).

**Recomendação:** definir ledger explícito (seção `### Ledger de XP` no diário com `Turno | código | valor | total`, ou linha por turno), ou rebaixar o lint para "soma de `XP Pago` ≤ XP da ficha". Sem isso o requisito é inatestável.

### QA-05 — P2 — `progress --award` é ambíguo e contorna a validação

`--award "<codigo_fonte>[:quantidade]"` ([spec.md:195](spec.md#L195), [spec.md:60](spec.md#L60)) mistura duas semânticas: multiplicador da tabela (`obj_main:1` = 40) ou valor absoluto. Como é "administrativo/retroativo", também não há barreira contra creditar XP sem estado de missão correspondente.

**Recomendação:** fixar `código:quantidade` com quantidade inteira ≥ 1 multiplicando a tabela; exigir `--reason` obrigatório; registrar no ledger e no diário; lint quando o total creditado exceder o justificável.

### QA-06 — P2 — A "blindagem de regex" da Fase 1 é convenção, não enforcement

[spec.md:141](spec.md#L141) prescreve gravar `Experiência (XP)` sem barra, mas nada no código impede que o modelo escreva `**XP:** 410` (casa com o regex de atributos, [ssot.py:64](council/ssot.py#L64)) ou `XP: 410 / 500` (casa com o de vitais, [ssot.py:43](council/ssot.py#L43)). Isso contraria a regra soberana do projeto ("o que não possui enforcement é guideline").

**Recomendação:** antecipar para a Fase 1 ao menos um lint `PROGRESSION_FORMAT_VIOLATION` no reviewer (detectar rótulos de XP/Nível/Pontos fora da seção `### Progressão`) ou escopar os parsers já na Fase 1. A convenção sozinha não passa no gate.

### QA-07 — P2 — Ganho de Ponto de Habilidade ambíguo

"+1 Ponto de Habilidade a cada 2 níveis pares (Nível 2, 4, 6...)" ([spec.md:169](spec.md#L169)) admite duas leituras: todo nível par, ou um ponto a cada dois níveis (4, 8, 12). A lista de exemplo sugere todo par, mas o texto não fecha.

**Recomendação:** "1 Ponto de Habilidade em todo nível par" e teste de tabela para níveis 1 a 10.

### QA-08 — P2 — `quest --objective "<ID>: <texto>"` quebra em texto com dois-pontos

Objetivos reais contêm `:` ("Obter a lealdade: guarnição norte"). O split ingênuo corrompe o registro.
**Recomendação:** dividir no primeiro `:` apenas, validando que o prefixo casa com `^[A-Z]\d+$`.

### QA-09 — P2 — Esquema de `quest --list --json` não está congelado

O critério de aceite fala em "representação estruturada válida" sem definir chaves. Sem snapshot, o contrato não é verificável e a spec 007 repetirá o problema que a 006 resolveu com esquema congelado.
**Recomendação:** declarar o JSON canônico (missão: `id`, `type`, `title`, `status`, `phase`, `contractor`, `clock`, `reward`, `objectives[{index,text,done}]`, `xp_paid`, `last_progress_turn`) e congelá-lo em teste.

### QA-10 — P3 — Defaults de progressão para campanhas legadas

As 3 campanhas não têm `### Progressão`. O parser precisa devolver nível 1 / XP 0 / próximo limiar 250 **sem escrever na ficha** (leitura pura) e sem dividir por zero na curva.
**Recomendação:** `parse_progression_from_ficha` com defaults e sinalizador `present: false`; teste em campanha sem a seção.

### QA-11 — P3 — Fase 1 acumula pontos não gastáveis

A Fase 1 credita nível e pontos, mas o gasto só chega na Fase 2. É aceitável, desde que documentado no `quickstart` e que a UI deixe claro que os pontos ficam retidos.
**Recomendação:** nota explícita no plano e no help do comando.

### QA-12 — P3 — `spec.md` afirma "sem detalhes de implementação", mas a spec é toda de implementação

O checklist marca "No implementation details leaking" ([requirements.md:9](checklists/requirements.md#L9)), enquanto a spec fixa módulos, funções e nomes de arquivo. Não é um defeito funcional, mas o checklist está inflado e perde valor como controle. Recomendação: ajustar o checklist ou assumir que a 007 é uma spec técnica (como as 002–006) e não de produto.

---

## 4. Gate de aceite proposto (Fase 1)

Executar após a implementação, nesta ordem:

```text
1. python -m unittest discover -s tests
   → OK. Se houver erro de ACL em tempfile, rodar com acesso elevado e registrar (não mascarar).

2. python lazy_turn.py quest --campaign <cid> --add "Teste QA" --type side --objective "A" --objective "B"
   python lazy_turn.py quest --campaign <cid> --list --json
   → JSON com id estável, objetivos íntegros, status ACTIVE.

3. python lazy_turn.py quest --campaign <cid> --check "Q1:1"
   → checkbox [x], Último Progresso atualizado, XP de obj_side creditado uma única vez.

4. python lazy_turn.py commit --campaign <cid> --summary "..." --quest-complete "Q1" --evidence "..."
   → estado COMPLETED, XP Pago crava 60, nível recalculado.
   Reexecutar o MESMO commit → no-op, XP inalterado, lint QUEST_REWARD_PAID_TWICE.

5. python lazy_turn.py prepare --campaign <cid> --mode gm
   → payload com protagonist.progression e step_1_quest_context; ausência de step_2_engine_state.

6. python -c "from council.ssot import parse_ficha_md; ..."
   → 'xp' e 'experiência' ausentes de ficha['vitals'] e ficha['stats'] (teste de regressão).

7. python lazy_turn.py review --campaign <cid> (nas 3 campanhas)
   → sem lint CRITICAL novo; lints de missão só quando realmente aplicáveis.

8. python lazy_turn.py prepare/commit/review em campanha sem as seções novas
   → sem exceção, defaults nível 1 / lista vazia.
```

**Critério de reprovação automática:** qualquer um dos 8 itens falhando, ou qualquer alteração que quebre `tests/test_boundary_contracts.py` sem atualização explícita do contrato.

---

## 5. Próximo passo

Aguardar o código da Fase 1 e substituir este documento pela revisão pós-implementação (mesmo arquivo, seção "Revisão de código"), cobrindo: legibilidade, coesão dos módulos, duplicação com `ssot.py`/`reviewer.py`, atomicidade de escrita, e aderência à regra "um dono textual, um ponto de enforcement".
