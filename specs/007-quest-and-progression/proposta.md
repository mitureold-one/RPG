# 007 — Proposta: Sistema de Missões e Sistema de Progressão (+ o que mais falta)

**Status:** Proposta (aguardando aprovação). Aprovada, promove-se para `spec.md` no padrão das specs 001–006.
**Data:** 21 de Outubro de 2026.
**Base analisada:** `lazy_turn.py`, `council/` (ssot, gm, reviewer, narrator, writer, helpers), `rulesets/d20_3gates.py`, `templates/`, as 3 campanhas ativas e as specs 001–006.

---

## 1. O que o motor já cobre (não reinventar)

| Sistema | Dono textual | Enforcement real |
| :--- | :--- | :--- |
| Loop de turno `prepare` → prosa → `commit` | `lazy_turn.py` | Payload `step_3_writer_mandate` + auditoria pós-commit |
| SSOT em 5 Markdown | `council/ssot.py` | Parsers e upserts atômicos |
| Relógios de facção | seção de `diario.md` | `parse_clocks_from_diario` + lint `CLOCK_BREACHED` |
| Arco dramático | seção de `diario.md` | `update_arc_in_diario` |
| Fila de cenas / marcos futuros | seção de `diario.md` | `parse_plot_from_diario` + `PENDING_MILESTONE_PROMOTION` |
| Ruleset plugável | `rulesets/` | `load_ruleset` resolve a matemática |
| Overrides tipados | bloco `yaml` de `regras.md` | `step_1_gm_arbitration.overrides` |
| Matriz relacional de NPCs | `npcs.md` | Briefing focal + triangulação horizontal |
| Barreira epistêmica | `narrator.py` | Termos proibidos injetados no payload |
| Lints de prosa | `reviewer.py` | Emoji, formato teatral, quarta parede |
| Auditoria de integridade | `reviewer.py` | 13 verificações disparadas no `commit` |
| Memória de longo prazo | `writer.py` | `query_aimemory` no `prepare` |

---

## 2. Diagnóstico: as lacunas

A percepção está correta, e é mais ampla do que XP. Hoje o motor narra muito bem o **presente** e não possui **economia de progresso** nem **gramática de objetivos**.

1. **Não existe XP.** Zero ocorrências de nível, experiência ou progressão no código. O atributo alimenta `(valor - 10) // 2` e nunca cresce: o protagonista é mecanicamente estático para sempre.
2. **Não existe missão.** O que há é decorativo:
   * `ficha.md` → `Marcos de Evolução Pessoal` são linhas de texto; `--add-milestone` (`lazy_turn.py:950`) grava qualquer coisa sem custo nem efeito.
   * `diario.md` → `Marcos Futuros do Arco` são strings soltas (`parse_plot_from_diario`); o reviewer só emite um aviso heurístico de severidade LOW quando detecta correspondência de palavras. Não há dono, prazo, estado, recompensa nem consequência de falha.
3. **Poder narrativo sem lastro mecânico.** `--add-ability` (`lazy_turn.py:949`) adiciona habilidades sem pré-requisito, custo, limite ou validação — qualquer prosa pode "conceder" um poder.
4. **Relações e reputação são prosa.** `Reputação com Facções` (seção de Vínculos de `ficha.md`) é texto livre; o motor não consegue reagir a ela.
5. **Descanso infinito.** `timeskip` restaura todos os vitais ao máximo (`lazy_turn.py:766-777`) sem custo, risco ou rolagem — não existe ferimento, sequela ou treino.

Efeito prático: campanhas longas perdem vetor (nada a perseguir), a recompensa é sempre puramente literária (nada a conquistar) e o acúmulo de poder fica fora do controle do motor.

---

## 3. Prioridade 1 — Sistema de Missões

### 3.1 Princípios

* Missão é **estado**, não prosa. Vive em `diario.md`: preserva o invariante dos 5 arquivos e a seção fica antes do histórico de turnos, então o parse continua barato em diário longo.
* **O motor valida, o LLM propõe** — exatamente o padrão já usado nos relógios.
* Nenhuma missão sem objetivo verificável e sem consequência de falha.
* Sem plugin no `prepare`, missão não existe: o dado tem de entrar no payload para virar pressão de cena.

### 3.2 Modelo de dados (nova seção em `diario.md`)

```markdown
### Missões & Objetivos
* **[MAIN] O Trono de Pedra-Negra** | Fase: Investigação | Status: ACTIVE | Contratante: Conselho dos Lordes | Relógio: Conspiração | Recompensa: 150 XP | Último Progresso: Turno 12
  * [x] Interrogar o mensageiro do norte
  * [ ] Obter a lealdade da guarnição
  * [ ] Desmascarar o traidor na corte
```

* **Tipos:** `MAIN`, `SIDE`, `PERSONAL`, `FACTION`.
* **Status:** `ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`.
* **Campos opcionais:** `Relógio` (vincula a um relógio existente), `Prazo` (data canônica), `Recompensa` (texto + XP sugerido).
* **Objetivos:** sub-bullets com checkbox; a contagem é a fonte de progresso.
* O parser é tolerante: campos ausentes não quebram a linha; seção ausente devolve lista vazia (campanhas antigas seguem válidas sem migração).

### 3.3 Máquina de estados

```text
ACTIVE  ──todos os objetivos OU --complete --evidence──> COMPLETED
ACTIVE  ──--fail --reason OU relógio vinculado rompido──> FAILED
ACTIVE  ──--block "motivo"──> BLOCKED ──> ACTIVE
ACTIVE  ──--abandon──> ABANDONED
COMPLETED / FAILED são terminais; reabrir exige --reopen e registra a reversão no diário.
```

Relógio rompido **não** conclui nem falha a missão sozinho: gera o lint `QUEST_OVERDUE` e um mandato de consequência. Fechar a missão continua sendo decisão de ficção, auditada.

### 3.4 Superfície de CLI (espelha `clock` e `plan`)

| Comando | Efeito |
| :--- | :--- |
| `quest --list [--json]` | Lista missões, fases, objetivos e progresso |
| `quest --add "Título" --type main --objective "..." --faction "..." --clock "..." --reward "..."` | Cadastra missão |
| `quest --objective "Q2: texto"` | Adiciona objetivo |
| `quest --check "Q2:1"` | Marca objetivo concluído |
| `quest --complete "Q2" [--evidence "texto"]` | Encerra como COMPLETED e credita XP |
| `quest --fail "Q2" --reason "texto"` | Encerra como FAILED |
| `quest --reopen "Q2" --reason "texto"` | Reverte estado terminal (auditado) |

### 3.5 Ganchos no motor

* **`prepare`:**
  * `step_1_quest_context`: missões ativas, objetivos pendentes, prazo, recompensa, último progresso e o mandato de pressão ("uma missão ativa deve produzir atrito concreto nesta cena").
  * `commit` hint passa a sugerir a flag de progresso quando a ação do jogador casa com um objetivo pendente.
* **`commit`:** `--quest-progress`, `--quest-complete`, `--quest-fail` gravam estado e são o único caminho de crédito de XP.
* **`reviewer`:** `QUEST_WITHOUT_OBJECTIVES`, `QUEST_STALE` (sem progresso há N turnos), `QUEST_CLOCK_LINK_BROKEN`, `QUEST_OVERDUE`, `QUEST_REWARD_PAID_TWICE`.

---

## 4. Prioridade 1 — Sistema de Progressão (XP)

### 4.1 A armadilha do nome (ler antes de escrever qualquer linha)

Três colisões reais, todas silenciosas:

1. **`PE` está ocupado.** `normalize_vital_key` (`council/ssot.py:13`) mapeia `pe` para energia/magia. Chamar a moeda de progressão de "PE" a funde com o recurso mágico.
2. **`XP: 410 / 500` viraria recurso vital.** O regex de vitais (`council/ssot.py:43`) captura qualquer `**Rótulo:** N / M`, inclusive fora da seção de vitais. Resultado: XP entra em `ficha["vitals"]`, aparece no snapshot de vitais do turno, dispara `VITALS_DESYNC` na auditoria e passa a ser debitável por `--cost`.
3. **`**XP:** 410` viraria atributo.** O regex de atributos (`council/ssot.py:64`) casa `[A-ZÀ-Ú]{2,5}` + número. `XP` entraria em `ficha["stats"]` e, quando nenhum `--stat` é passado, `chosen_stat = next(iter(ficha["stats"].keys()))` (`lazy_turn.py:224`) poderia escolher XP como modificador de rolagem.

**Mitigação imediata (Fase 1):** gravar como `* **Experiência (XP):** 410` e **nunca** como razão — o `E` maiúsculo seguido de minúscula quebra o regex de atributos e a ausência de `/` quebra o de vitais.

**Mitigação durável (Fase 2):** escopar os parsers por seção (`### Vitais & Recursos`, `### Atributos`). Isso corrige um bug latente que já existe hoje, independente da progressão.

### 4.2 Modelo de dados (nova seção em `ficha.md`)

```markdown
### Progressão
* **Nível:** 2
* **Experiência (XP):** 410
* **Próximo Nível:** 500
* **Pontos de Atributo:** 1
* **Pontos de Habilidade:** 0
```

XP é **contador acumulativo unidirecional** (nunca diminui, nunca é "gasto"). A moeda de gasto são os **Pontos de Atributo** e **Pontos de Habilidade** — assim não existe dívida de XP nem nível regressivo.

### 4.3 Tabela de concessão (determinística, calculada pelo motor)

| Código | Fonte | XP |
| :--- | :--- | ---: |
| `obj_main` | Objetivo de missão principal | 40 |
| `obj_side` | Objetivo de missão secundária | 15 |
| `quest_side` | Missão secundária concluída | 60 |
| `quest_main` | Missão principal concluída | 150 |
| `quest_personal` | Missão pessoal concluída | 50 |
| `clock_resolved` | Relógio desarmado por ação do protagonista | 40 |
| `clock_breached` | Relógio rompido e consequência sobrevivida | 30 |
| `arc_milestone` | Marco de arco alcançado | 80 |
| `discovery` | Revelação canônica / dossiê | 25 |
| `adversity` | Revés crítico sobrevivido | 20 |
| `turn` | Turno comum | 0 |

Vitória fácil não rende XP; sofrimento rende. Não há XP por existir (anti-grind), nem XP sem código de razão validado contra o estado real da missão/relógio.

### 4.4 Curva de nível

```text
T(L) = 250 * (L - 1) * L / 2      →  L2: 250 | L3: 750 | L4: 1500 | L5: 2500 | L10: 11250
```

Configurável por override já suportado em `regras.md`:

```yaml
  - id: xp_curve
    type: xp_curve
    target: level_threshold
    value: 250
    condition: "Curva de progressão da campanha"
```

**Ganhos por nível:** +1 Ponto de Atributo, +2 HP máximo, +1 Stamina máxima, +1 Energia máxima; +1 Ponto de Habilidade a cada 2 níveis. Teto de atributo 20 (sobrescrevível por override).

### 4.5 Gasto

| Comando | Efeito |
| :--- | :--- |
| `progress --list [--json]` | Nível, XP, próximo limiar, pontos disponíveis |
| `progress --spend-attr FOR` | +1 no atributo, consome 1 Ponto de Atributo, respeita teto |
| `progress --spend-ability "Nome: efeito" --training "cena de treino"` | Consome 1 Ponto de Habilidade e exige evidência diegética |
| `progress --award "obj_main:1"` | Uso administrativo/retroativo, registrado no diário |

Gasto é comando próprio, fora do `commit`: subir de nível não é consequência de cena, é decisão de build.

### 4.6 Anti-abuso e idempotência

* XP só é creditado via `commit` (ou `--award` administrativo), sempre com código de razão.
* Cada missão concluída grava `XP Pago: 150` na própria linha; segundo crédito é recusado e vira lint `QUEST_REWARD_PAID_TWICE`.
* `reviewer` valida `XP_MISMATCH`: soma dos códigos no diário tem de bater com o XP acumulado da ficha.
* Ledger de XP é append-only; qualquer decréscimo é anomalia de integridade.

### 4.7 Payload

`prepare` ganha `protagonist.progression` (nível, XP, limiar, pontos) e o mandato "use o nível para calibrar a escala dos oponentes". A mudança é **aditiva**: o teste de snapshot (`tests/test_boundary_contracts.py:169-240`) valida por `assertIn`, não por igualdade, então não quebra.

---

## 5. Ranking dos demais sistemas candidatos

| # | Sistema | Lacuna que fecha | Esforço | Impacto | Depende de |
| :-: | :--- | :--- | :-: | :-: | :--- |
| 1 | **Reputação numerada de facções** | `Reputação` é texto livre; o motor não reage | M | Alto | Missões |
| 2 | **Turno de facções off-screen** | O mundo só se move quando o LLM lembra; relógios não têm agenda própria | G | Alto | Relógios + Reputação |
| 3 | **Ferimentos, condições e descanso** | `timeskip` cura 100% de graça; não há sequela, veneno, exaustão | M | Alto | Progressão |
| 4 | **Grafo de informação (quem sabe o quê)** | A barreira epistêmica é lista de palavras, não estado: NPC "sabe" sem ter sido informado | G | Alto | NPCs |
| 5 | **Inventário quantificado e economia** | Itens são strings; não há quantidade, moeda ou escassez | M | Médio | — |
| 6 | **Relógios pessoais do protagonista** | Planos do jogador não têm mecânica; reusa a máquina de relógios | P | Médio | — |
| 7 | **Consentimento e limites de mesa** | A precedência em `DECISOES_ARQUITETURA.md` cita "Consentimento e Limites da Campanha", mas nada implementa | P | Médio (maturidade) | — |
| 8 | **Recap automático ("previously on")** | Contexto frio em campanhas longas custa tokens e memória | P | Médio | — |

Esforço: P = pequeno, M = médio, G = grande. Ordem sugerida de execução: 1 → 3 → 2 → 4.

---

## 6. Custos de integração e riscos

* **Sem migração obrigatória.** Seções ausentes devolvem listas vazias; as 3 campanhas ativas continuam válidas. `schema_version` só sobe se algum formato de linha existente mudar (não é o caso).
* **Testes a tocar:** `tests/test_boundary_contracts.py` (payload e contrato de CLI documentado), `tests/test_cli_contracts.py` (novos subcomandos). Novos testes obrigatórios: parse de missão, idempotência de XP, XP fora de `vitals`/`stats`.
* **Documentação mínima:** `README.md` (estrutura e comandos), `templates/diario.template.md`, `templates/ficha.template.md`, `SKILL.md` do narrative-engine (3 linhas apontando para a CLI, sem reescrever regra — a regra vive no código).
* **Regra de ouro da `DECISOES_ARQUITETURA.md`:** um dono textual, um ponto de enforcement. XP e missão **não** podem virar prosa em skill; se não houver enforcement, não é sistema, é sugestão.
* **Ruído retroativo:** os novos lints podem acusar as 3 campanhas antigas. Rodar `python lazy_turn.py review --campaign <id>` logo após a implementação e ajustar antes de seguir.

---

## 7. Fases sugeridas

**Fase 1 — Fundação (sem gasto de pontos).**
`council/quests.py` (parser, upsert, máquina de estados), `rulesets/progression.py` (tabela, curva, cálculo), subcomando `quest`, ganchos em `prepare`/`commit`, crédito de XP idempotente, templates e testes. Estimativa: ~2 módulos novos, ~5 arquivos alterados, ~600 linhas.

**Fase 2 — Gasto e rigor.**
`progress` (spend/level-up/abilities), ganhos de nível aplicados na ficha, parsers escopados por seção, lints novos no reviewer, backfill das 3 campanhas.

**Fase 3 — Mundo reativo.**
Reputação numerada, depois turno de facções off-screen; ferimentos/condições em paralelo.

---

## 8. Critérios de aceite da Fase 1

1. `quest --add` cria linha parseável; `quest --list --json` devolve esquema estável.
2. `commit --quest-complete "Q1"` credita XP uma única vez, grava `XP Pago` e recalcula nível.
3. Repetir o mesmo `--quest-complete` é no-op e vira lint, sem duplicar XP.
4. `prepare` inclui missões ativas, objetivos pendentes e progresso de nível.
5. `XP` nunca aparece em `ficha["vitals"]` nem em `ficha["stats"]` (teste de regressão).
6. Campanha sem a seção nova continua operando (retrocompatibilidade).
7. `python -m unittest discover -s tests` verde.
8. `review` das 3 campanhas sem novos lints de severidade CRITICAL.
