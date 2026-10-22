# Feature Specification: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature Name**: `factions-and-reputation`  
**Status**: Ready for Planning  
**Created**: 2026-10-22  
**Target Backlog Phase**: P5 (Fase 3 do Roadmap RPGPRO: Ecologia Política, Vínculos Numéricos e Dinâmica Off-Screen)  
**Base Analisada**: `campaigns/*/mundo.md`, `campaigns/*/ficha.md`, `campaigns/*/npcs.md`, `campaigns/*/diario.md`, `council/quests.py`, `rulesets/progression.py`, `council/reviewer.py`, `lazy_turn.py`, `templates/`.

---

## 1. Executive Summary & Problem Statement

O ecossistema RPGPRO estabelece como diretriz soberana que a fidelidade e a integridade de uma crônica de RPG não devem depender da memória estocástica ou da complacência de Modelos de Linguagem:
> *"Uma regra, um único dono textual, um único ponto de enforcement no código. O que não possui enforcement é guideline e não deve fingir ser código."*

Com a entrega e homologação das Fases 1 e 2 (Especificações 007 e 008 — Missões, Progressão XP e Relógios de Ameaça), o motor adquiriu uma economia rígida de objetivos e evolução mecânica do protagonista. No entanto, o universo ao redor do herói permanece estático e reativo: **as facções e organizações do cenário existem apenas como prosa descritiva em `mundo.md`, a lealdade do protagonista em `ficha.md` é qualitativa e sem consequência de regras, e o mundo não se move fora do foco imediato da câmera (off-screen)**.

### 1.1 O que o motor já cobre (Invariantes a Preservar)
* **SSOT em 5 Arquivos Markdown**: `diario.md`, `ficha.md`, `npcs.md`, `mundo.md`, `regras.md`.
* **Sistema de Missões & XP**: Metadados estruturados, IDs monotônicos `[Q{N}]`, campo `Contratante:` e vínculo a relógios de ameaça (`council/quests.py`, `rulesets/progression.py`).
* **Relógios Narrativos Determinísticos**: Mecanismos de avanço, ruptura (`BREACHED`) e resolução (`RESOLVED`) em `diario.md`.
* **Auditoria Contínua**: 15 verificações determinísticas e lints literários em `council/reviewer.py`.

### 1.2 Diagnóstico das Lacunas da Fase 3
1. **Reputação Puramente Decorativa**:
   * Em `ficha.md`, o bullet `* **Reputação com Facções:**` armazena texto livre sem lastro mecânico (ex.: `Conselho dos Lordes (Favorável / Respeitado)`). O motor não possui escala numérica, não rastreia atrito político e é incapaz de alterar dificuldades de testes sociais ou posturas de NPCs com base em alianças.
2. **Ausência de Moeda Social (Favores & Débitos)**:
   * O protagonista não acumula favores diegéticos para cobrar de aliados nem débitos que facções possam cobrar sob forma de chantagem ou missões compulsórias.
3. **Descompasso entre Contratos e Lealdade**:
   * Concluir ou falhar missões com `Contratante: <Facção>` não repercute sobre a reputação com aquela organização; o herói pode trair abertamente uma ordem sem que sua ficha reflita hostilidade.
4. **Mundo Inerte Fora da Cena (Falta de Turno Off-Screen)**:
   * As facções em `mundo.md` não possuem estatísticas de agência, poder ou objetivos autônomos. Quando a crônica salta dias ou semanas (`timeskip` / `interlude`), o mundo ao redor do protagonista não avança seus projetos a menos que o Mestre manipule manualmente cada relógio.
5. **Vulnerabilidade de Integridade Relacional**:
   * Não há linter verificando se um NPC em `npcs.md` pertence a uma facção cadastrada em `mundo.md`, nem se a atitude de um soldado da guarda é inconsistente com a hostilidade jurada do protagonista contra aquela corporação.

### 1.3 Solução Proposta
A presente especificação implementa a **Fase 3 (Facções, Reputação Numérica e Dinâmica de Mundo)**:
1. **Dono Textual Canônico de Facções em `mundo.md`**: Padronização da seção `## 4. Facções, Forças Ativas & Alianças` com identificadores tipados `[TAG]`, atributos de Poder (1 a 5), Escala (Local, Regional, Continental, Global) e relógios vinculados de projeto.
2. **Escala Numérica Discreta de Reputação em `ficha.md`**: Sistema simétrico de 7 escalões (-3 a +3) com rastreamento auditável de Favores e Débitos.
3. **Mapeamento Mecânico Social no `prepare` e `commit`**: Injeção da reputação relevante no payload de arbitragem do turno (`step_1_faction_context`), aplicando bônus/penalidades situacionais diretos e orientando o mandato do escritor.
4. **Subcomando CLI `lazy_turn.py faction`**: Operações completas de consulta, alteração pontual de reputação/favores e simulação do "Turno de Facções Off-Screen" (`faction --tick`).
5. **Ledger Auditável no Diário e Lints Determinísticos no Revisor**: Seção `### Registro de Reputação & Facções` em `diario.md` e quatro novos linters de integridade relacional em `council/reviewer.py`.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Consulta e Cadastro Estruturado de Facções
* **As a** Game Master ou jogador orquestrando a crônica,
* **I want** listar e gerenciar as facções do cenário via CLI com atributos claros de Poder, Escala e projetos ativos em `mundo.md`,
* **So that** as organizações políticas do mundo tenham peso concreto e visibilidade unificada.
* **Acceptance Criteria**:
  - `python lazy_turn.py faction --campaign <id> --list` exibe todas as facções cadastradas em `mundo.md`, seu Poder, Escala, relógio vinculado e a reputação atual do protagonista.
  - `python lazy_turn.py faction --campaign <id> --add "Nome da Facção" --power 3 --scale regional --clock "Relógio X" --desc "..."` cadastra atomicamente a nova facção na seção `## 4. Facções, Forças Ativas & Alianças` de `mundo.md`.
  - O sistema tolera formatos legados puramente textuais de `mundo.md`, inferindo tags e valores padrão sem quebrar a execução.

### User Scenario 2: Rastreamento Numérico de Reputação, Favores e Débitos
* **As a** motor de jogo processando decisões políticas do protagonista,
* **I want** alterar numericamente o nível de reputação (-3 a +3) e o saldo de favores/débitos em `ficha.md` de forma auditável,
* **So that** alianças e inimizades gerem consequências mecânicas duradouras e todo ajuste fique registrado no histórico do diário.
* **Acceptance Criteria**:
  - A escala de reputação compreende exatamente 7 escalões: `-3` (Jurado de Morte), `-2` (Hostil), `-1` (Suspeito), `0` (Neutro), `+1` (Amigável), `+2` (Aliado), `+3` (Venerado). Tentativas de ultrapassar o limite são travadas em [-3, +3].
  - `lazy_turn.py faction --campaign <id> --rep "Nome Facção:+1" --reason "Ajuda militar"` atualiza a ficha e anexa imediatamente uma linha sob `### Registro de Reputação & Facções` em `diario.md`.
  - Operações com `--favor "+1"` e `--debt "+1"` mantêm inteiros não-negativos na ficha do protagonista.
  - A estrutura em `ficha.md` suporta sub-bullets detalhados (`* **[TAG] Nome:** +2 (Aliado) | Favores: 1 | Débitos: 0`) e faz parsing transparente do formato em linha única legado.

### User Scenario 3: Impacto Automático de Missões sobre a Reputação
* **As a** jogador cumprindo contratos para uma corporação,
* **I want** que concluir uma missão (`commit --quest-complete`) aumente minha reputação com o contratante, e falhar (`commit --quest-fail`) gere atrito e débito,
* **So that** o cumprimento de objetivos tenha repercussão diplomática direta no mundo.
* **Acceptance Criteria**:
  - Quando uma missão com metadado `Contratante: <Facção>` é concluída com sucesso via `lazy_turn.py commit --quest-complete <QID>`, a reputação com a facção contratante recebe automaticamente +1 ponto e +1 favor, registrando o evento no ledger de reputação.
  - Quando a missão fracassa via `lazy_turn.py commit --quest-fail <QID>`, a reputação com o contratante é reduzida em -1 ponto e o saldo de débitos recebe +1.
  - Se a missão não possuir contratante vinculado ou a facção for neutra/independente, nenhuma mutação de facção ocorre.

### User Scenario 4: Injeção de Contexto Político no Turno de Jogo (`prepare`)
* **As a** Modelo de Linguagem atuando como Game Master na preparação de cena,
* **I want** receber no payload JSON do `prepare` o alinhamento das facções presentes e as penalidades/bônus aplicáveis a NPCs daquela bandeira,
* **So that** a prosa e as dificuldades dos testes respeitem rigorosamente o status diplomático do protagonista.
* **Acceptance Criteria**:
  - O payload de `lazy_turn.py prepare` contém a chave `step_1_faction_context` com:
    - Lista de facções ativas na cena ou presentes via NPCs em foco.
    - Reputação numérica e escalão nominal correspondente.
    - Modificador de Dificuldade Social: bônus de `-2` na DC para aliados (+2/+3), neutro para 0/+1, e penalidade de `+2` a `+4` na DC (ou Desvantagem) para facções suspeitas ou hostis (-1 a -3).
    - Diretiva de barreira atitudinal para o escritor (ex.: proibir cordialidade espontânea de membros de facções hostis sem justificativa de fachada).

### User Scenario 5: Turno de Facções Off-Screen (`faction --tick`)
* **As a** Showrunner ou Game Master simulando a passagem do tempo ou bastidores do mundo,
* **I want** executar um tick autônomo de facções,
* **So that** os relógios de conspiração e planos das organizações avancem conforme seu Poder e dinamismo, sem depender da presença direta do herói.
* **Acceptance Criteria**:
  - O comando `python lazy_turn.py faction --campaign <id> --tick` avança relógios narrativos vinculados a facções ativas com base em seu atributo de Poder (ex.: Poder 4/5 avança com maior probabilidade/frequência).
  - Emite um relatório factual das movimentações de bastidores para ser aproveitado em cenas de interlúdio, dossiê ou salto temporal.
  - Não viola a regra de ruptura de relógio: relógios que atingem o limite máximo transitam para `BREACHED` e geram alerta no relatório sem executar resoluções mágicas.

### User Scenario 6: Auditoria de Integridade Política e Lints do Revisor
* **As a** guardião do cânone executando `lazy_turn.py review`,
* **I want** que o revisor detecte facções fantasmas, NPCs órfãos e incongruências entre reputação e atitude de NPCs,
* **So that** nenhuma alucinação ou inconsistência diplomática permaneça no SSOT.
* **Acceptance Criteria**:
  - `FACTION_UNKNOWN`: Disparado com severidade `HIGH` se a ficha citar reputação com uma facção que não existe em `mundo.md`.
  - `FACTION_ORPHANED_NPC`: Disparado com severidade `MEDIUM` se um NPC em `npcs.md` declarar afiliação a uma facção inexistente.
  - `FACTION_ATTITUDE_DESYNC`: Disparado com severidade `HIGH` se um NPC tiver postura amigável/vulnerável com o herói pertencendo a uma facção com reputação `-2` (Hostil) ou `-3` (Jurado de Morte), sem menção a traição, amor proibido ou disfarce em suas fraquezas/vontade.
  - `FACTION_REP_MISMATCH`: Disparado com severidade `HIGH` se o valor de reputação na ficha divergir da soma das transições registradas no histórico do diário.

---

## 3. Functional Requirements

### 3.1 Modelo de Dados e Parsers de Facção em `mundo.md`
* **FR-01**: Criar o módulo `council/factions.py` com dataclasses/dicionários tipados para manipulação de facções.
* **FR-02**: Implementar `parse_factions_from_mundo(mundo_path: Path) -> List[Dict[str, Any]]`:
  - Extrair facções declaradas sob `## 4. Facções, Forças Ativas & Alianças`.
  - Mapear campos: `tag` (ex.: `CONSELHO_LORDES`), `name` (ex.: `Conselho dos Lordes de Cinzas`), `description`, `power` (inteiro 1 a 5, default 3), `scale` (local, regional, continental, global), `clock` (nome do relógio vinculado) e `rivals` (facções rivais declaradas).
* **FR-03**: Implementar `upsert_faction_in_mundo(mundo_path: Path, ...)`:
  - Inserir ou atualizar atomicamente facções em `mundo.md`, garantindo escrita única (`write_text`).

### 3.2 Reputação, Favores e Débitos em `ficha.md`
* **FR-04**: Implementar `parse_reputation_from_ficha(ficha_path: Path) -> Dict[str, Dict[str, Any]]`:
  - Ler a seção `### Vínculos, Laços & Matriz Relacional`.
  - Suportar tanto a lista estruturada por bullets quanto a linha única legada `* **Reputação com Facções:** ...`.
  - Normalizar cada entrada para: `{"score": int (-3 a +3), "tier": str, "favors": int (>=0), "debts": int (>=0)}`.
* **FR-05**: Implementar `update_reputation_in_ficha(ficha_path: Path, faction_name: str, score_delta: int = 0, favors_delta: int = 0, debts_delta: int = 0) -> Dict[str, Any]`:
  - Atualizar o saldo de reputação (limitado a [-3, +3]), favores e débitos.
  - Atualizar a etiqueta nominal canônica correspondente ao valor.
  - Gravar atomicamente na seção de vínculos de `ficha.md`.

### 3.3 Ledger de Reputação e Automação de Missões
* **FR-06**: Implementar `append_faction_ledger_entry(diario_path: Path, faction_name: str, rep_delta: int, new_score: int, reason: str, turn: int = None, favor_delta: int = 0, debt_delta: int = 0)`:
  - Registrar a entrada sob a seção `### Registro de Reputação & Facções` em `diario.md` (criando a seção antes do Histórico de Turnos caso ausente).
* **FR-07**: Integrar ao `lazy_turn.py cmd_commit`:
  - Processar argumentos `--faction-rep`, `--faction-favor`, `--faction-debt`.
  - Quando `--quest-complete <QID>` for disparado para missão que tenha `Contratante:` cadastrado:
    - Localizar a facção contratante em `mundo.md`.
    - Creditar automaticamente `score_delta=+1` e `favors_delta=+1` na reputação da ficha.
    - Gravar entrada explicativa no ledger do diário.
  - Quando `--quest-fail <QID>` for disparado para missão com contratante:
    - Aplicar `score_delta=-1` e `debts_delta=+1`.
    - Gravar entrada de penalidade no ledger do diário.

### 3.4 Subcomando CLI `lazy_turn.py faction`
* **FR-08**: Registrar o subparser `faction` em `build_cli()` com opções:
  - `--campaign <id>` (obrigatório).
  - `--list` / `--json` (consulta completa).
  - `--add <nome>` com `--power <1-5>`, `--scale <str>`, `--clock <nome>`, `--desc <texto>`.
  - `--rep <Facção:delta>` com `--reason <texto>`.
  - `--favor <Facção:delta>` e `--debt <Facção:delta>`.
  - `--tick` (execução do turno de facções off-screen).
* **FR-09**: Implementar `cmd_faction(...)` em `lazy_turn.py` orquestrando as chamadas de domínio e formatação tabular / JSON.

### 3.5 Turno de Facções Off-Screen (`faction --tick`)
* **FR-10**: No processamento do `--tick`:
  - Percorrer as facções cadastradas em `mundo.md` que possuam relógio vinculado com status `ACTIVE` em `diario.md`.
  - Avaliar o avanço determinístico de cada relógio com base no nível de Poder da facção:
    - Poder 4-5: avanço de +1 passo garantido no tick.
    - Poder 2-3: avanço de +1 passo se houver gatilho de inércia ou conflito ativo.
    - Poder 1: relógio avança apenas com estímulo diegético direto.
  - Retornar um resumo estruturado com os relógios avançados e potenciais rupturas (`BREACHED`) para alimentação dos mandatos de cena do Showrunner/Mestre.

### 3.6 Injeção de Contexto Teleológico e Político no `prepare`
* **FR-11**: Atualizar `lazy_turn.py cmd_prepare`:
  - Analisar os NPCs presentes e em foco na cena, bem como o local geográfico.
  - Identificar as facções associadas a esses elementos.
  - Injetar no payload JSON a chave `step_1_faction_context`:
    - Facções em cena e seus níveis de reputação com o protagonista.
    - Modificador social sugerido para testes interpessoais.
    - Diretriz de contenção: alertar o Mestre/Escritor se o herói tentar negociar com facção hostil sem recursos extraordinários de barganha ou disfarce.

### 3.7 Lints Determinísticos de Integridade em `council/reviewer.py`
* **FR-12**: Implementar `check_factions_integrity(campaign_id, info)` em `council/reviewer.py`:
  - `FACTION_UNKNOWN` (`HIGH`): Ficha lista reputação com facção ausente em `mundo.md`.
  - `FACTION_ORPHANED_NPC` (`MEDIUM`): NPC afiliado a facção inexistente.
  - `FACTION_ATTITUDE_DESYNC` (`HIGH`): NPC com atitude amigável para protagonista com reputação `-2` ou `-3` sem exceção psicológica (ex.: fraqueza ou vínculo proibido).
  - `FACTION_REP_MISMATCH` (`HIGH`): Total de reputação na ficha não condiz com a soma das mutações históricas do ledger.

---

## 4. Key Entities & Data Schemas

### 4.1 Declaração Canônica de Facções (`mundo.md`)
```markdown
## 4. Facções, Forças Ativas & Alianças

* **[CONSELHO_LORDES] Conselho dos Lordes de Cinzas:** Nobres tradicionalistas que exigem a coroação de Aemon e a manutenção dos privilégios senhoriais. | Poder: 4 | Escala: Regional | Relógio: Conspiração da Corte
* **[GUARDA_MEIA_NOITE] A Guarda da Meia-Noite:** Tropa veterana de elite liderada por Lorde Malakor. | Poder: 3 | Escala: Local | Relógio: Golpe da Guarda de Malakor

### Dinâmica Inter-Facções & Disputas
* **Conselho vs Guarda:** Disputa armada clandestina pelo controle dos portões da fortaleza antes que os sinos fúnebres dobrem.
```

### 4.2 Reputação na Ficha do Personagem (`ficha.md`)
```markdown
### Vínculos, Laços & Matriz Relacional
* **Aliados & Cônjuges/Afetos:** Lady Vespera: Amante e aliada de sangue possessiva.
* **Rivais, Amores Proibidos & Desafetos:** Lorde Malakor: Comandante militar rival.
* **Reputação com Facções:**
  * **[CONSELHO_LORDES] Conselho dos Lordes de Cinzas:** +2 (Aliado) | Favores: 1 | Débitos: 0
  * **[GUARDA_MEIA_NOITE] A Guarda da Meia-Noite:** -2 (Hostil) | Favores: 0 | Débitos: 1
```

### 4.3 Tabela dos 7 Escalões Canônicos de Reputação

| Reputação | Escalão Nominal | Modificador em Testes Sociais | Atitude Padrão de Membros da Facção |
| :---: | :--- | :---: | :--- |
| **+3** | **Venerado** | DC -3 (ou Vantagem Maior) | Devoção cega, proteção armada, acesso a segredos de Estado. |
| **+2** | **Aliado** | DC -2 | Solidariedade ativa, refúgio seguro, concessão de favores. |
| **+1** | **Amigável** | DC -1 | Disposição para diálogo, hospitalidade e comércio preferencial. |
| **0** | **Neutro** | DC +0 (Padrão) | Prudência profissional, relações estritamente transacionais. |
| **-1** | **Suspeito** | DC +1 | Desconfiança, recusa de concessões, vigilância velada. |
| **-2** | **Hostil** | DC +3 (ou Desvantagem) | Inimizade aberta, recusa de trégua, hostilidade armada em território da facção. |
| **-3** | **Jurado de Morte** | DC +5 (ou Impossível) | Caçadas ativas, contratos de assassinato, captura e execução sumária. |

### 4.4 Registro Histórico de Facção em `diario.md`
```markdown
### Registro de Reputação & Facções
* **[Turno 4]** Conselho dos Lordes de Cinzas: +1 Reputação (0 -> +1 [Amigável]) | Favores: +1 | Motivo: Resgate dos reféns no pátio | Missão: Q1
* **[Turno 5]** A Guarda da Meia-Noite: -1 Reputação (-1 -> -2 [Hostil]) | Débitos: +1 | Motivo: Quebra do bloqueio militar
```

---

## 5. Non-Functional Requirements & Safety Invariants

* **Invariante de Soberania SSOT**: `mundo.md` governa a existência de facções; `ficha.md` governa a reputação e saldos do herói; `diario.md` guarda o histórico e os relógios.
* **Invariante de Escrita Atômica**: Toda operação em `factions.py` realiza no máximo uma leitura e uma escrita atômica (`write_text`) por arquivo afetado.
* **Invariante de Sandbox & Portabilidade**: Todo teste automatizado deve utilizar exclusivamente a Python Standard Library e diretórios temporários sob `.tmp/test_scratch/` com permissão herdada (zero chamadas a `tempfile.mkdtemp` ou `tempfile.TemporaryDirectory`).
* **Tolerância a Campanhas Legadas**: Arquivos `ficha.md` com reputação declarada em linha única ou `mundo.md` sem identificadores `[TAG]` devem ser interpretados sem erro e enriquecidos progressivamente.

---

## 6. Success Criteria & Verification Suite

1. **Gate 1 (CLI Faction Lifecycle)**:
   - Cadastrar facção via `faction --add` grava em `mundo.md` no formato estruturado.
   - Listar via `faction --list --json` expõe facções, atributos, relógios e reputação do herói.
2. **Gate 2 (Alteração de Reputação & Idempotência de Ledger)**:
   - `faction --rep "Nome:+1"` atualiza o escalão na ficha e crava entrada com data/turno em `diario.md`.
   - Limites `-3` e `+3` são estritamente respeitados.
3. **Gate 3 (Gatilho Automático via Commit)**:
   - Executar `commit --quest-complete <QID>` para missão com contratante avança a reputação e favores na ficha e registra no ledger.
   - Executar `commit --quest-fail <QID>` aplica penalidade e gera débito.
4. **Gate 4 (Turno Off-Screen)**:
   - `faction --tick` avalia facções ativas e avança relógios correspondentes ao seu Poder.
5. **Gate 5 (Injeção no Prepare)**:
   - `lazy_turn.py prepare` exibe `step_1_faction_context` com modificadores corretos baseados na reputação.
6. **Gate 6 (Lints do Revisor)**:
   - Forçar uma facção desconhecida na ficha dispara `FACTION_UNKNOWN` (`HIGH`).
   - Adulterar a reputação na ficha sem registro correspondente no diário dispara `FACTION_REP_MISMATCH` (`HIGH`).
   - Associar um NPC a facção inexistente dispara `FACTION_ORPHANED_NPC` (`MEDIUM`).
7. **Gate 7 (Suíte Completa sem Regressões)**:
   - Todos os 36 testes preexistentes continuam 100% aprovados, e novos testes unitários e de integração adicionados cobrem a Fase 3 sem quebra no sandbox.
