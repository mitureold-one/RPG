# RPG - Conselho Cooperativo Híbrido & Motor de TTRPG Narrativo

> *"Eu gosto de RPGs e eu gosto de IA. Porque não ensiná-la a como mestrar?"*

Framework determinístico e autônomo para conduzir campanhas de RPG de Mesa (TTRPG) e ficção interativa em prosa literária profissional, utilizando IA como Game Master e Showrunner sob regras invioláveis e arbitragem de dados.

---

## Filosofia: A Hierarquia Soberana de Regras

O ecossistema opera sob três graus estritos de prioridade:

1. **Grau 1: O Motor Universal (Framework RPG — Prioridade Máxima)**
   * **Onde vive:** `AGENTS.md`, `council/`, `lazy_turn.py` e `.agents/skills/`.
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
├── council/                       # Módulos Python do Motor Universal
│   ├── gm.py                      # Resolução de dados dos 3 Portões e cálculo de custos
│   ├── helpers.py                 # Constantes, datas e localização dinâmica de campanhas
│   ├── narrator.py                # Catálogo de NPCs, psicologia, agência e barreira epistêmica
│   ├── reviewer.py                # Auditoria de SSOT, paradoxos temporais e integridade
│   ├── ssot.py                    # Leitura e escrita atômica de ficha.md e diario.md
│   └── writer.py                  # ai-memory e mandatos estruturais de prosa de cena
├── campaigns/                     # Campanhas ativas (SSOT do estado do jogo)
│   ├── dinastia_cinzas/
│   ├── imperio_valiria/
│   └── perpetuos_terra_incognita/
├── templates/                     # Templates canônicos para novas campanhas
├── specs/                         # Especificações de desenvolvimento do motor
├── tests/                         # Testes automatizados de contratos de CLI e mandatos
├── AGENTS.md                      # Regra Soberana de Workspace para Agentes
├── DECISOES_ARQUITETURA.md        # Registro de decisões arquiteturais do projeto
├── lazy_turn.py                   # CLI central de orquestração do jogo
├── sync_daemon.py                 # Sincronização e persistência de memórias
└── README.md
```

---

## O Loop do Turno

A cada ação do jogador, o assistente executa o fluxo invariável:

1. **Pré-Turno (`prepare`):**
   ```powershell
   python lazy_turn.py prepare --campaign <id> --action "<ação>" [--stat <ATTR>] [--dc <10|15|20|25>]
   ```
   Rola os 3 Portões, calcula custos de vitais, injeta matriz relacional e iniciativas ativas de NPCs.

2. **Redação Literária:**
   * Linha 1: Cabeçalho canônico `[Data, Hora] | [Local] | [Presentes]`.
   * Prosa clássica com travessão (`—`), sem formato teatral.
   * Iniciativa de NPCs e triangulação horizontal.
   * Fechamento em gancho dramático acionável (zero didatismo de rodapé).

3. **Pós-Turno (`commit`):**
   ```powershell
   python lazy_turn.py commit --campaign <id> --summary "<resumo>" --state-shift "<mudança>" [--cost "<recursos>"] [--npc-updates "<NPC: Atitude:...>"]
   ```
   Persiste atomicamente em `ficha.md`, `npcs.md` e `diario.md` e audita a integridade da crônica.

---

## Diretrizes Inegociáveis

* **Zero Emojis:** Proibido o uso de emojis na narrativa, comandos ou arquivos de dados.
* **Anti-Puppeteering:** O Mestre jamais decide ações, posturas ou falas do protagonista.
* **SSOT Único em Markdown:** Os arquivos em `campaigns/<id>/` são a única fonte da verdade.
