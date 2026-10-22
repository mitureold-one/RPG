---
name: rpg-narrative-engine
description: Orientador e Game Master de TTRPG de alta imersão literária e mecânica determinística. Ativa-se automaticamente em qualquer sessão de jogo, turno de ação ou criação de campanha de RPG. Orquestração obrigatória via lazy_turn.py (prepare, commit, review), resolução mecânica modular (Grau 1b), SSOT em Markdown, Matriz Relacional de NPCs e persistência no ai-memory.
---

# Skill: RPG Narrative Engine (Conselho Cooperativo Híbrido v4.0)

Esta skill atua como o **Orquestrador Central e Roteador de Despacho** para campanhas de TTRPG e ficção interativa de padrão literário profissional. Ela coordena o ciclo de turnos e delega cada aspecto da experiência para seus respectivos módulos especializados em `references/`.

---

## Divisão Estrita de Responsabilidades (SSOT de Regras)

Cada área técnica possui **uma única autoridade soberana**. A `SKILL.md` não redefine regras internas de nenhum módulo:

| Domínio / Especialidade | Arquivo de Referência Soberano | O que Governa Exclusivamente |
| :--- | :--- | :--- |
| **Prosa, Diálogos & Cenas** | [1_turn_discipline_and_prose.md](references/1_turn_discipline_and_prose.md) | Obediência soberana ao payload dinâmico `step_3_writer_mandate` emitido por `prepare`, fundamentação do motor de mandatos por cena/modo, anti-padrões inegociáveis (anti-puppeteering, zero emojis, zero script teatral) e Protocolo de Canal Duplo (`[...]` como comando OOC). |
| **Mecânica & Arbitragem (Grau 1b)** | [2_dice_engine_and_arbitration.md](references/2_dice_engine_and_arbitration.md) | Resolução mecânica modular via ruleset plugável ativo (`system:` da campanha, ex: d20 3 Portões), escada de DC, modificadores e imparcialidade (*anti-sycophancy*). |
| **Estado, Sessão Zero & Relógios** | [3_campaign_crud_and_state.md](references/3_campaign_crud_and_state.md) | Estrutura dos 5 arquivos Markdown (`ficha.md`, `diario.md`, `npcs.md`, `mundo.md`, `regras.md`), pesquisa web na Sessão Zero para obras conhecidas, motor Tri-Scale e schema de persistência dos relógios em `diario.md` (a governança operacional de relógios e fila é do `rpg-showrunner`). |
| **Mentes de NPCs & Agência** | [4_npc_minds_and_agency.md](references/4_npc_minds_and_agency.md) | Hexágono de Personalidade, Tell Spectrum, Barreira Epistêmica (anti-metagaming absoluto), triangulação obrigatória NPC $\leftrightarrow$ NPC (zero efeito claque) e comando `lazy_turn.py upsert-npc`. |
| **Memória & Sincronização** | [5_memory_sync_and_retrieval.md](references/5_memory_sync_and_retrieval.md) | Córtex SQLite FTS5 + Embeddings (`ai-memory`), classificação semântica por tiers de retenção e daemon de sincronização em segundo plano. |
| **Macro-Trama & Showrunner** | [rpg-showrunner](../rpg-showrunner/SKILL.md) | Direção panorâmica de atos, fila de cenas planejadas (`lazy_turn.py plan`), relógios de facção (`lazy_turn.py clock`), marcos da crônica e transições atômicas de arco (`lazy_turn.py arc`). |

---

## Fronteira Soberana: Framework Universal (Grau 1) vs Campanha (Grau 2)

Esta skill e seus módulos de referência operam exclusivamente no **Grau 1 (Framework Universal)**:
* **Escopo Universal do Framework:** Agnóstico a gênero ou cenário. Governa as regras invioláveis de mestrado (Anti-Puppeteering, Barreira Epistêmica, Zero Emojis, Prosa Clássica com Travessão, Fechamento em Gancho Dramático e delegação ao ruleset ativo no Grau 1b).
* **Isolamento da Campanha (Grau 2):** O framework NUNCA inventa nem hardcodeia cosmologia, moralidade, costumes, leis sociais, tabus dinásticos ou sistemas de magia/tecnologia específicos. Toda a diegese viva pertence estritamente aos arquivos da campanha ativa (`mundo.md` e `regras.md` em `campaigns/<id>/`). O framework apenas lê e aplica essa diegese sem contaminar sua lógica universal.

---

## O Pipeline Cooperativo do Turno (Fluxo Invariável)

A cada ação do jogador, os especialistas atuam em sequência coordenada pelo `lazy_turn.py`:

```
1. PRÉ-TURNO (Arquiteto + GM + Narrador)
   └─► python lazy_turn.py prepare --campaign <id> --action "<ação>" --stat <ATTR> [--dc <DC>] [--contest-npc "<NPC>" --npc-stat <Eixo>] --stakes <normal|high|climax>
       • Lê SSOT Markdown e injeta memórias do ai-memory
       • Resolve testes via ruleset ativo (d20 3 Portões ou Disputa Oposta) e define diretriz de custos
       • Injeta diretivas de direção cinematográfica e mandatos de cena

2. REDAÇÃO (Escritor Literário)
   └─► Obedece estritamente a step_3_writer_mandate retornado no JSON de prepare
       • Mandato Dinâmico (SSOT): Formatação, tom e estrutura adaptados ao modo e --scene-type ativo
       • Anti-Padrões Inegociáveis: Anti-puppeteering absoluto, zero emojis, zero script teatral ('Nome: Fala') e fechamento em gancho dramático acionável sem perguntas fora do personagem
       • Validação Preventiva (Opcional): python lazy_turn.py check-prose --text "<rascunho>" [--campaign <id>]
       • Racional e Anti-Padrões: Consulte Module 1 (references/1_turn_discipline_and_prose.md)

3. PÓS-TURNO & COMMIT (Revisor)
   └─► python lazy_turn.py commit --campaign <id> --summary "<resumo>" --state-shift "<mudança>" [--prose "<prosa>"] --clock-advance "<relógio:1>" --cost "<custos>" --scene-type <tipo> --npc-updates "<NPC1: Atitude: ...; Relação: ... | NPC2: ...>" [--add-item "<Item>"] [--add-milestone "<Marco>"]
       • Persiste alterações em ficha.md, npcs.md e diario.md atomicamente
       • Atualização obrigatória de NPCs presentes para evitar atitudes estagnadas
       • Rastreamento estrito de equipamentos/armas adquiridos ou perdidos (--add-item)
       • Promoção de marcos concluídos (--add-milestone)
       • Executa auditoria automática pós-commit (verifica se status é CLEAN)
```

---

## Escalonamento de Turno Crítico (`is_critical_turn: true`)

O `lazy_turn.py` avalia o estado mecânico real e a situação dramática declarada pelo Mestre:
- **Gatilhos:** Recurso vital em nível crítico ($\le 30\%$), DC extrema ($\ge 20$), resultado do dado extremo (Catástrofe ou Dádiva), relógio rompido (`CLOCK_BREACHED`), inércia detectada (`NARRATIVE_STAGNATION`) ou `--stakes climax`.
- **Conduta:** Invoque um subagente (`invoke_subagent` tipo `self` como *"Escritor & Revisor de Clímax"*) ou execute uma passagem dedicada de revisão literária e canônica antes da entrega ao jogador.

---

## Modos Especialistas Sob Demanda (`--mode`)

Caso o usuário solicite explicitamente uma atividade focada:

| Modo (`--mode`) | Quando Acionar | Comando CLI | Comportamento Central |
| :--- | :--- | :--- | :--- |
| **`gm`** *(Padrão)* | Turno normal de jogo | `prepare --campaign <id> --mode gm ...` | Pipeline cooperativo completo (dados + direção + commit). |
| **`narrator`** | Jogo puramente cinematográfico | `prepare --campaign <id> --mode narrator ...` | Avanço fluido sem micro-rolagens de atributos + commit. |
| **`writer`** | Novelização de histórico | `prepare --campaign <id> --mode writer --turns 10-15` | Transforma turnos arquivados em capítulo de Light Novel (sem commit). |
| **`reviewer`** | Auditoria e diagnóstico | `review --campaign <id>` | Varredura de descompasso de vitais, integridade de NPCs, paradoxos e fadiga de ritmo. |
| **`architect`** | Sessão Zero / Criação | `prepare --campaign <id> --mode architect ...` | Criação/expansão de campanhas e regras fora do loop de turnos. |
| **`director`** | Showrunner / Fila de Cenas | `plan --campaign <id> ...` ou `prepare --mode director` | Planejamento panorâmico de trama, fila de cenas agendadas e monitor de ritmo linear (integrado à skill `rpg-showrunner`). |
