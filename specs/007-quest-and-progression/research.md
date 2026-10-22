# Technical Research & Architecture Decisions: Sistema de Missões e Progressão (XP)

**Feature**: `quest-and-progression`  
**Date**: 2026-10-22  
**Status**: Completed & Approved  

---

## 1. Context & Objectives

A especificação `specs/007-quest-and-progression/spec.md` estabelece a necessidade de introduzir uma economia de progresso e gramática de objetivos no RPGPRO sem quebrar as invariantes soberanas:
- **SSOT em 5 Arquivos Markdown** (`diario.md`, `ficha.md`, `npcs.md`, `mundo.md`, `regras.md`).
- **Zero Emojis e Anti-Puppeteering**.
- **Um dono textual, um único ponto de enforcement no código**.
- **Compatibilidade Retroativa Total com as campanhas ativas**.
- **Integração Sincronizada com os Relógios de Ameaça existentes**.

---

## 2. Key Architectural Decisions (Research Findings)

### Decision 1: Dono Textual e Local de Armazenamento de Missões
* **Decisão**: A seção `### Missões & Objetivos` viverá exclusivamente em `diario.md`, posicionada logo após `### Relógios de Ameaça & Prazos` e antes de `### Histórico de Turnos`.
* **Racional**:
  - Preserva a regra sagrada dos 5 arquivos canônicos (nenhum 6º arquivo é criado).
  - Como a seção se situa no cabeçalho do diário, o parsing permanece $O(1)$ em relação ao crescimento do histórico de turnos.
  - Missões e Relógios ficam adjacentes fisicamente em `diario.md`, facilitando a inspeção humana e a correlação textual.
* **Alternativas Rejeitadas**:
  - *Arquivo `missoes.md` separado*: Rejeitado por violar o invariante de 5 arquivos SSOT e exigir reengenharia dos backups e snapshots.
  - *Armazenar em `ficha.md`*: Rejeitado porque `ficha.md` é a verdade do personagem (atributos, vitais, inventário); missões envolvem o mundo, prazos, relógios e contratantes externos.

---

### Decision 2: Mitigação das Colisões de Expressões Regulares em `ficha.md`
* **Problema Identificado**:
  1. `PE` já é chave de vital (Energia/Magia em `normalize_vital_key`).
  2. O regex de vitais em `council/ssot.py:43` captura qualquer linha `**Rótulo:** N / M`, mesmo fora da seção de vitais.
  3. O regex de atributos em `council/ssot.py:64` captura `[A-ZÀ-Ú]{2,5}` seguido de número (ex.: `**XP:** 410`).
* **Decisão**:
  - **Fase 1 (Nomenclatura Blindada)**: Gravar em `ficha.md` como:
    ```markdown
    ### Progressão
    * **Nível:** 1
    * **Experiência (XP):** 0
    * **Próximo Nível:** 250
    * **Pontos de Atributo:** 0
    * **Pontos de Habilidade:** 0
    ```
    - O rótulo `Experiência (XP)` não casa com atributos porque possui minúsculas após a primeira maiúscula (`Experiência`).
    - Não utiliza barra `/`, o que impede a ativação do regex de vitais `N / M`.
  - **Fase 2 (Escopo Estrito de Seções)**:
    - Refatorar os parsers em `council/ssot.py` para isolar os blocos de texto por títulos Markdown (`### Vitais & Recursos`, `### Atributos`, `### Progressão`), prevenindo qualquer contaminação futura.
* **Alternativas Rejeitadas**:
  - *Gravar XP como `XP: 0/250`*: Rejeitado de forma absoluta, pois transformaria XP em recurso debitável por `--cost` e dispararia falhas em `VITALS_DESYNC`.

---

### Decision 3: Interação Bidirecional com os Relógios Narrativos Existentes
* **Decisão**:
  1. **Vínculo Opcional**: Cada missão pode vincular-se a um relógio via metadado `Relógio: <Nome>`.
  2. **Pressão no `prepare`**: Quando um relógio associado atingir $cur \ge max - 1$, o motor emite em `step_1_quest_context` uma diretriz de urgência crítica.
  3. **Ruptura não-automática**: `CLOCK_BREACHED` gera o lint `QUEST_OVERDUE` e exige que o fracasso ou plano de contingência seja arbitrado pelo GM no `commit` via `--quest-fail` ou novo objetivo. O motor não apaga nem falha missões no escuro.
  4. **Dedup de XP (Anti-Double-Dipping)**: Concluir uma missão que desarma seu relógio nominal concede o XP da missão e absorve o bônus isolado de `clock_resolved`.
  5. **Auditoria de Arco**: `lazy_turn.py arc --resolve-clocks` audita se há missões ativas atreladas aos relógios sendo arquivados e emite aviso caso fiquem órfãs.
* **Alternativas Rejeitadas**:
  - *Fechar missão automaticamente quando o relógio rompe*: Rejeitado porque a perda de uma missão é material narrativo central e precisa ser narrada diegeticamente.
  - *Auto-avanço de missões por palavras-chave*: Rejeitado porque avanço de missão movimenta XP real e não pode depender de correspondência textual probabilística.

---

### Decision 4: Economia de XP e Curva de Nível
* **Decisão**:
  - O XP é acumulativo e estritamente unidirecional (nunca é gasto).
  - A moeda de gasto são os `Pontos de Atributo` (+1 por nível) e `Pontos de Habilidade` (+1 a cada 2 níveis).
  - A curva quadrática canônica é:
    $$\text{XP}_{\text{limiar}}(L) = 250 \times \frac{(L - 1) \times L}{2}$$
    - N2: 250 | N3: 750 | N4: 1500 | N5: 2500 | N10: 11250 XP.
  - Suporta override tipado em `regras.md` (`type: xp_curve`, `target: level_threshold`, `value: 250`).
* **Tabela de Concessão Determinística**:
  - `obj_main`: 40 XP
  - `obj_side`: 15 XP
  - `quest_side`: 60 XP
  - `quest_main`: 150 XP
  - `quest_personal`: 50 XP
  - `clock_resolved`: 40 XP (quando não associado à conclusão simultânea da missão)
  - `clock_breached`: 30 XP (sobreviver à crise da ruptura)
  - `arc_milestone`: 80 XP
  - `discovery`: 25 XP
  - `adversity`: 20 XP
  - `turn`: 0 XP

---

### Decision 5: Idempotência Estrita e Rastreabilidade
* **Decisão**:
  - Toda missão concluída recebe a tag `XP Pago: <valor>` em sua linha de cabeçalho no diário.
  - Qualquer re-execução de `--quest-complete` para uma missão com `XP Pago` é um no-op mecânico e gera o lint `QUEST_REWARD_PAID_TWICE`.
  - O reviewer audita `XP_MISMATCH` comparando o log de concessões históricas com a ficha.

---

### Decision 6: Mapeamento de Módulos e Superfície de CLI
* **Decisão**:
  - Módulo `council/quests.py`: Funções puras de parse, formatação e atualização atômica de missões.
  - Módulo `rulesets/progression.py`: Cálculo da curva, validação de códigos de concessão e progressão de nível.
  - Módulo `council/ssot.py`: Adição de `parse_progression_from_ficha` e `update_progression_in_ficha`.
  - Subcomandos de CLI em `lazy_turn.py`:
    - `lazy_turn.py quest ...`
    - `lazy_turn.py progress ...`
    - Flags adicionais em `commit`: `--quest-progress`, `--quest-complete`, `--quest-fail`.
