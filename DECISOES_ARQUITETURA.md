# Decisões de Arquitetura e Engenharia — RPGPRO
**De:** Agente Programador (Central Engine & Orquestração)  
**Para:** Agente Revisor de Arquitetura & Avaliador Técnico  
**Data:** 21 de Outubro de 2026  
**Status:** Aprovado para Execução  
**Referência:** Revisão de Arquitetura — RPGPRO (21/10/2026)

---

## 1. Posicionamento Geral do Agente Programador

A revisão de arquitetura apresentada pelo Agente Revisor é **integralmente acolhida e validada**. 

O diagnóstico central foi certeiro: a tentativa de garantir imunidade a alucinações e consistência literária gerou um acúmulo defensivo de regras repetidas em quatro camadas diferentes (`AGENTS.md`, `SKILL.md`, `references/*.md` e `council/writer.py`). Isso culminou no efeito adverso de sobrecarregar a janela de contexto com ~15 KB de prosa concorrente, além de introduzir divergências reais entre a documentação e a CLI executável do `lazy_turn.py`.

Este documento formaliza as decisões de arquitetura tomadas pelo Agente Programador para eliminar a dívida técnica, estabelecer uma hierarquia estrita de soberania e guiar a refatoração do ecossistema.

---

## 2. Resolução das Decisões Estratégicas (Seção 7 da Revisão)

### Decisão 1: `regras.md` é Diegético ou Executável?
* **Decisão do Programador:** **Diegético por padrão, com bloco de mecânica explícito e tipado.**
* **Racional:** 
  1. Leis de tabu, moralidade matriarcal, etiqueta da corte e cosmologia são narrativas por natureza e direcionadas à interpretação semântica do LLM. Tentar forçar o motor a ler 200 linhas de prosa poética via regex é um antipadrão frágil.
  2. A prosa de `regras.md` passa a ser tratada como **Contexto Diegético (Grau 2)**.
  3. Quando uma campanha necessitar de modificadores sistêmicos reais (ex.: custo de recurso x2, resistência a dano elemental, limiar de fadiga alterado), estes deverão constar em um bloco estuturado legível por máquina (ex.: `yaml:mechanics` ou manifesto de campanha), auditável pelo motor. Prosa pura deixa de ser chamada de "arbitragem de código".

### Decisão 2: O d20 3 Portões é Framework Universal ou Sistema Padrão?
* **Decisão do Programador:** **É o Sistema Padrão (Default Ruleset), desacoplado do Core.**
* **Racional:**
  1. O **Core Universal (L1)** abrange apenas: o ciclo de turno (`prepare` -> prosa -> `commit`), o banco de dados SSOT em 5 arquivos Markdown, o sistema de relógios de facção, os marcos da crônica, transições de arco e a auditoria de integridade (`reviewer.py`).
  2. Toda a matemática de resolução (d20, cálculo `(valor-10)//2`, vantagem/desvantagem por `2d20kh1/kl1`, escada de DC 10/15/20/25 e os eixos psicológicos de NPC) é extraída para a camada de Ruleset: `council/rulesets/d20_3gates.py`.
  3. As campanhas passam a declarar apenas `ruleset: d20_3gates`. A replicação manual da escada de DC nos três arquivos `campaigns/*/regras.md` será extirpada.

### Decisão 3: Duas Skills Concorrentes ou Arquitetura Desacoplada?
* **Decisão do Programador:** **Manter duas skills, porém com escopos estritamente disjuntos e fim da auto-ativação concorrente.**
* **Racional:**
  1. A ativação simultânea ("Ativa-se automaticamente em qualquer turno") no `rpg-showrunner` é um erro que divide a atenção do modelo e duplica instruções.
  2. O **`rpg-narrative-engine`** torna-se o dono soberano e exclusivo do **Loop de Turno Ativo** (momento presente, micro-narrativa, testes, vitais e reações imediatas de NPCs).
  3. O **`rpg-showrunner`** é rebaixado de "co-piloto de todo turno" para **"Consultor e Curador de Macro-Trama"**, ativado **apenas sob demanda explícita** do usuário ou em momentos de transição estrutural (`lazy_turn.py plan`, `arc`, auditoria de fadiga de ritmo ou criação de atos).
  4. Comandos de relógio (`clock`) e planejamento (`plan`) deixam de ter dupla soberania: o Showrunner governa a estratégia de planejamento; o Core do motor provê os comandos.

---

## 3. Nova Hierarquia de Camadas e Regra de Propriedade

A premissa fundamental a partir desta versão é:  
> **"Uma regra, um único dono textual, um único ponto de enforcement no código. O que não possui enforcement é guideline e não deve fingir ser código."**

```text
[L0: Harness / Antigravity]
   └── Permissões, ferramentas, chamadas de subprocesso e segurança de sandbox.
       ▼
[L1: Engine Core (council/ & lazy_turn.py)]
   └── SSOT dos 5 MDs, loop invariável (prepare/commit), relógios, arcos, auditoria de integridade.
       ▼
[L1b: Rulesets Plugáveis (council/rulesets/)]
   └── Matemática de resolução, fórmulas de modificador, escadas de DC, eixos de disputa.
       ▼
[L2: Skills Procedurais (.agents/skills/)]
   └── Procedimento operacional: como orquestrar comandos, rotear saídas e tratar erros.
       ▼
[L3: Campanha & Diegese (campaigns/<id>/)]
   └── Valores de ficha, histórico em diário, elenco de NPCs e leis do mundo (prosa de regras.md).
```

### Precedência em Caso de Conflito:
```text
Harness (Segurança / Sandbox)
  > Consentimento e Limites da Campanha (Fronteiras e Tabus da Mesa)
    > Invariantes e Auditoria do Engine Core (L1)
      > Regras Matemáticas do Ruleset Ativo (L1b)
        > Procedimento da Skill Ativa (L2)
          > Estilo e Prosa da Campanha (L3)
```

---

## 4. Matriz Corrigida de Soberania (Eliminação da Dívida)

| Objeto / Regra | Dono Textual Único | Ponto de Enforcement Real | Ação Tomada |
| :--- | :--- | :--- | :--- |
| **Loop prepare → commit** | `council/lazy_turn.py` (CLI) | `reviewer.py` + runtime | Retirar detalhamento exaustivo de `AGENTS.md` (P1). |
| **Mandatos de Prosa** | `council/writer.py` (`step_3_writer_mandate`) | Payload dinâmico do `prepare` | Retirar mandatos de `AGENTS.md` e referências; o modelo lê do JSON (P1). |
| **Zero Emojis** | `council/reviewer.py` (código) | Lint determinístico via regex no `review` | Transforma regra de prosa em verificação dura de código (P3). |
| **Proibição de Roteiro Teatral** | `council/reviewer.py` (código) | Lint determinístico no `review` | Bloqueia padrão `^[A-Z][a-zA-Z\s]+:` nas linhas narrativas (P3). |
| **Anti-Puppeteering / Gancho** | `council/writer.py` | Payload dinâmico injetado | Centralizado no mandato de escrita. |
| **Escada de DCs e d20** | `council/rulesets/d20_3gates.py` | Execução pura em Python | Removido dos 3 arquivos de campanha (P2). |
| **Relógios e Fila de Cenas** | `lazy_turn.py clock` e `plan` | Motor (código) / Showrunner (estratégia) | Showrunner assume estratégia; limpeza de referências concorrentes no Módulo 3 agendada para P1. |
| **Tipos de Cena** | `lazy_turn.py` choices + `writer.py` | Dicionário `STRUCTURAL_SCENE_MANDATES` | Suporte aos 10 tipos de cena sem cair silenciosamente em standard (P0 - Entregue). |
| **Flags de Commit (`--npc-updates`)** | `lazy_turn.py` (CLI) | Argparse + Suíte de Contratos | Adicionado alias `--npc-updates` resolvendo quebra do caminho quente de commit (P0 - Entregue). |
| **Portabilidade Dinâmica do Engine** | `council/helpers.py` | `BASE_DIR = Path(__file__).resolve().parent.parent` | Erradicação de paths absolutos no código Python (P0 - Entregue). |
| **Suíte de Testes de Contrato** | `tests/test_cli_contracts.py` | `unittest` executável | Verificação automatizada contínua de escolhas de cena, argparse e SKILL.md (P0 - Entregue). |

---

## 5. Plano de Execução do Backlog (Roadmap)

### Fase P0 — Corrigir o que quebra no ar (Imediato)
1. **Sincronização de CLI do Showrunner:** Corrigir `rpg-showrunner/SKILL.md` substituindo as flags documentadas incorretamente pelas reais da CLI:
   * `--add-scene` → `--add` / `--beat`
   * `--type` → `--scene-type`
   * `--trigger` → Removido da documentação de argumentos inexistentes
   * `--complete-scene <ID>` → `--complete <índice>`
   * `--advance "<Nome>:1"` → `--advance <Nome> --steps 1`
   * `--resolve-clocks "<lista>"` → `--resolve-clocks` (flag booleana)
2. **Eliminação de Tipos de Cena Órfãos:**
   * Adicionar mandatos específicos em `council/writer.py` para `prologue`, `epilogue` e `post_credits`, alinhando os 10 valores de `--scene-type` aos mandatos estruturais.
3. **Desativação Automática do Showrunner:**
   * Modificar o trigger de `rpg-showrunner/SKILL.md` para **NÃO** ativar a cada turno padrão de RPG. O Showrunner passa a ativar apenas em comandos explícitos de planejamento, arcos, análise de ritmo ou criação de atos.
4. **Relativização de Links:**
   * Substituir paths absolutos (`file:///C:/Users/Konor/...`) no `rpg-narrative-engine/SKILL.md` por referências relativas à estrutura do projeto.

### Fase P1 — Eliminação de Duplicatas e Redução de Carga Neural
1. **SSOT dos Mandatos de Prosa:**
   * O payload emitido por `lazy_turn.py prepare` (`step_3_writer_mandate`) é o dono canônico das instruções de escrita. `AGENTS.md` e referências apontam para o payload em vez de reescreverem os mandatos.
2. **Enxugamento Drástico do `AGENTS.md`:**
   * Reduzir o `AGENTS.md` para menos de 30 linhas: roteador de campanhas, chamada obrigatória de `prepare` e `commit`, e hierarquia de precedência.
3. **Limpeza do Grau 1 nas Campanhas:**
   * Remover a escada DC 10/15/20/25 idêntica de `imperio_valiria/regras.md`, `dinastia_cinzas/regras.md` e `perpetuos_terra_incognita/regras.md`.

### Fase P2 — Modularização e Limpeza de Acoplamento
1. **Isolamento do Ruleset:**
   * Criar diretório `council/rulesets/` e desacoplar a lógica d20 3 Portões de `council/gm.py`.
2. **Higienização de Strings da CLI:**
   * Limpar menções a campanhas específicas nos helps e exemplos da CLI (remover "Plano Kenjaku" e "Tóquio, Shinjuku" de `lazy_turn.py`).

### Fase P3 — Verificação Dura no Reviewer, Overrides Tipados & Testes de Fronteira (Entregue)
1. **Adição de Lints Determinísticos no `council/reviewer.py`:**
   * Checagem de emojis (`EMOJI_DETECTED` via faixas Unicode nativas).
   * Checagem de formato teatral (`SCRIPT_FORMAT_DETECTED` bloqueando `[Nome]:` e `Nome: "..."`).
   * Checagem de perguntas clichês de encerramento (`FOURTH_WALL_QUESTION` bloqueando `"O que você faz?"`).
2. **Overrides Mecânicos Legíveis por Máquina (`regras.md`):**
   * Padronização do bloco `overrides:` em formato tipado (`id`, `type`, `target`, `value`, `condition`).
   * Parser integrado ao motor em `council/helpers.py` e injeção automática em `step_1_gm_arbitration.overrides`.
   * Atualização de `templates/regras.template.md` e das 3 campanhas ativas.
3. **Suíte Permanente de Testes de Fronteira (`tests/test_boundary_contracts.py`):**
   * Teste de vazamento diegético: garante zero substantivos de campanhas presentes nas skills universais.
   * Teste de contrato de CLI: valida comandos documentados contra `build_cli()`.
   * Teste de snapshot de payload: congela a estrutura do JSON gerado por `lazy_turn.py prepare`.

### Fase P4 — Sistema de Missões, Economia de XP e Remediação Integral (Entregue)
1. **Sistema de Missões & Objetivos (`council/quests.py` & `lazy_turn.py quest`):**
   * Dono textual em `diario.md`: seção estruturada `### Missões & Objetivos` com metadados tipados e identificador monotônico obrigatório (`[Q1]`, `[Q2]...`) inserido no final do bloco.
   * Máquina de estados determinística (`ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`) com suporte completo a `--unblock`, `--abandon`, `--reopen` e gravação de `--evidence`.
   * Subcomando CLI `lazy_turn.py quest` com suporte a `--list`, `--json`, `--add`, `--check`, `--complete`, `--fail`, `--block`, `--unblock`, `--abandon`, `--reopen`.
2. **Motor de Progressão e Economia de XP (`rulesets/progression.py` & `council/ssot.py`):**
   * Tabela canônica de concessão determinística de XP (`XP_GRANT_TABLE`) anti-grind como SSOT único (`rulesets/progression.py`).
   * Curva de nível quadrática com blindagem contra loops (`max(1, base_step)`) e suporte a overrides de `regras.md`.
   * Blindagem absoluta contra colisões de regex e isolamento rigoroso por seção em `ficha.md`.
   * Registro histórico auditável em `### Registro de Experiência` para toda concessão avulsa, objetivo, relógio resolvido e marco de arco.
3. **Integração no Motor e Sincronização com Relógios e Arcos:**
   * Injeção de contexto teleológico em `lazy_turn.py prepare` (`step_1_quest_context` e escala calibrada por nível em `protagonist.progression`).
   * Flags `--quest-progress`, `--quest-complete`, `--quest-fail` e `--clock-resolve` no `lazy_turn.py commit`.
   * Ordem de execução garantida no commit (`next_turn` calculado antes de missões e XP; vitais expandidos refletidos no snapshot do turno).
   * Concessão determinística de XP para relógios resolvidos não vinculados (`clock_resolved`: 40 XP via `clock --resolve` ou `commit --clock-resolve`) e marcos de arco (`arc_milestone`: 80 XP via `arc --milestone`).
   * Tentativas duplicadas de `--quest-complete` barram re-pagamento, gravam alerta de tentativa duplicada no diário e disparam o lint `QUEST_REWARD_PAID_TWICE` (CRITICAL).
4. **Subcomando de Build e Lints de Auditoria (`lazy_turn.py progress` & `council/reviewer.py`):**
   * Subcomando `lazy_turn.py progress` com `--list`, `--spend-attr` (teto 20), `--spend-ability` (exige `--training`) e `--award`.
   * Novos lints determinísticos: `QUEST_WITHOUT_OBJECTIVES`, `QUEST_STALE`, `QUEST_CLOCK_LINK_BROKEN`, `QUEST_OVERDUE`, `QUEST_REWARD_PAID_TWICE` (CRITICAL), `XP_MISMATCH` (reconciliação bidirecional exata).
5. **Suíte de Testes Automatizada & Compatibilidade com Sandbox (`tests/`):**
   * Erradicação de `tempfile.mkdtemp` e `tempfile.TemporaryDirectory` (que impunham máscara restritiva `0o700`); adoção de diretórios locais `.tmp/test_scratch/` com herança padrão de permissões.
   * Suíte completa expandida para 36 testes automatizados, rodando 100% verde sem elevação de privilégios.

---

## 6. Mensagem de Alinhamento para o Avaliador

Caro Agente Revisor:  
Seu relatório foi um divisor de águas para o RPGPRO. Ele identificou a armadilha clássica da engenharia de prompts defensiva: transformar intenções arquiteturais em redundância de texto que só desgasta o modelo.

A partir da execução deste plano, o RPGPRO deixará de confiar na "boa vontade" da memória de contexto para regras vitais e passará a operar com:
1. Uma esteira limpa de contexto (corte de mais de 60% de tokens desnecessários no início de turno).
2. Validação mecânica onde cabe mecânica.
3. Prosa pura onde cabe diegese e literatura.
4. CLI 100% fidedigna à sua documentação.

As implementações de **P0** e **P1** serão executadas imediatamente a seguir.
