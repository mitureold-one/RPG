# RPG - Conselho Cooperativo Híbrido & Motor de TTRPG Narrativo

> *"Eu gosto de RPGs e eu gosto de IA. Porque não ensiná-la a como mestrar?"*

Framework determinístico e autônomo para conduzir campanhas de RPG de Mesa (TTRPG) e ficção interativa em prosa literária profissional, utilizando IA como Game Master e Showrunner sob regras invioláveis e arbitragem de dados.

---

## Filosofia: A Hierarquia Soberana de Regras

O ecossistema opera sob três graus estritos de prioridade:

1. **Grau 1: O Motor Universal (Framework RPG — Prioridade Máxima)**
   * **Onde vive:** `AGENTS.md`, `contracts/`, `kernel/`, `application/`, `interfaces/`, `council/`, `lazy_turn.py` e `.agents/skills/`.
   * **Escopo:** 100% agnóstico a gênero ou cenário. Governa o Loop de Turno determinístico, Barreira Epistêmica (anti-metagaming), Proibição de Titiritagem (Anti-Puppeteering), Prosa Clássica com Travessão, Relógios de Facção, Transições de Arco, Auditoria e SSOT único em Markdown.
   * **Grau 1b (Rulesets Plugáveis):** Resolução matemática de testes (ex: d20 3 Portões, modificadores, escada de DC e eixos de NPC).
2. **Grau 2: As Leis do Cenário & Campanha Ativa (Diegese — Prioridade Alta)**
   * **Onde vive:** `campaigns/<id>/mundo.md` e `campaigns/<id>/regras.md`.
   * **Escopo:** Cosmologia, sistemas de poder/fisiologia, facções, moralidade, tabus sociais e leis locais daquela campanha específica. O Framework aplica essas regras sem misturá-las à sua própria mecânica universal.
3. **Grau 3: Os Personagens & Matriz Relacional (Psicologia — Prioridade Situacional)**
   * **Onde vive:** `campaigns/<id>/npcs.md` e `campaigns/<id>/ficha.md`.
   * **Escopo:** Análise de pesos psicológicos (Hexágono de Personalidade, Vontades Próprias e Fraquezas) para cada NPC.

---

## Estrutura do Repositório

```text
RPGPRO/
├── .agents/
│   └── skills/
│       ├── rpg-narrative-engine/  # Skill de GM, disciplina de prosa e loop de turno
│       └── rpg-showrunner/        # Skill sob demanda: macro-trama, relógios e ritmo
├── contracts/                     # Contratos abstratos (envelope de eventos, portas, config)
├── kernel/                        # Kernel de composição (registry, runtime, schema)
├── application/                   # Casos de uso (prepare, commit, transaction, showrunner, progress)
├── interfaces/cli/                # Parser argparse e despacho de comandos da CLI
├── adapters/persistence/          # Escrita atômica e locks cooperativos de arquivo
├── temporal/                      # Calendários declarativos e avanço temporal
├── campaign/                      # Localização, validação e templates de campanhas
├── council/                       # Fachada e lógica de domínio (gm, reviewer, narrator, ssot)
├── campaigns/                     # Campanhas ativas (limpo com .gitkeep; use init-campaign)
├── archive/campaigns/             # Campanhas legadas arquivadas
├── templates/                     # Templates canônicos para novas campanhas
├── tests/                         # Testes automatizados (210 testes, sem campanhas vivas)
│   └── fixtures/campaigns/        # Fixtures isoladas para suíte de testes
├── AGENTS.md                      # Regra Soberana de Workspace para Agentes
├── ARCHITECTURE.md                # Arquitetura canônica, portas de extensão e gates
├── ROADMAP.md                     # Roadmap estratégico e critérios de aceite
├── EXECUCAO.md                    # Registro append-only de execuções e auditorias
├── lazy_turn.py                   # Ponto de entrada CLI (54 linhas)
└── sync_daemon.py                 # Sincronização e persistência de memórias
```

---

## O Loop do Turno

A cada turno de ação, o assistente orquestra o ciclo invariável via CLI e obedece aos mandatos dinâmicos de escrita:

1. **Pré-Turno (`prepare`):** Resolve a mecânica de dados e vitais, emitindo o payload determinístico `step_3_writer_mandate`.
2. **Redação Literária:** Redige a narrativa obedecendo estritamente ao `step_3_writer_mandate` injetado pelo engine para o modo e `--scene-type` ativo.
3. **Pós-Turno (`commit`):** Persiste o estado factual atomicamente em `ficha.md`, `npcs.md` e `diario.md`, executando a auditoria automática de integridade.

---

## Diretrizes Inegociáveis

* **Zero Emojis:** Proibido o uso de emojis na narrativa, comandos ou arquivos de dados.
* **Anti-Puppeteering:** O Mestre jamais decide ações, posturas ou falas do protagonista.
* **SSOT Único em Markdown:** Os arquivos em `campaigns/<id>/` são a única fonte da verdade.
