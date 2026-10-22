# Architectural Research: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature**: `factions-and-reputation`  
**Status**: Completed  
**Created**: 2026-10-22  
**Context**: Implementação da Fase 3 do ecossistema RPGPRO (Facções, Reputação Numérica, Favores/Débitos e Agência Off-Screen).

---

## 1. Decisão 1: Dono Textual Único e Estrutura SSOT das Facções

* **Contexto**: O RPGPRO proíbe dispersão de estado e exige conformidade com a soberania dos 5 arquivos Markdown (`mundo.md`, `ficha.md`, `npcs.md`, `diario.md`, `regras.md`).
* **Decisão**:
  - `mundo.md` é o **dono textual único da existência e natureza das facções** sob a seção canônica `## 4. Facções, Forças Ativas & Alianças`. Cada facção é declarada com tag identificadora `[TAG]`, nome canônico, Poder (1 a 5), Escala (Local, Regional, Continental, Global) e relógio de projeto vinculado.
  - `ficha.md` é o **dono textual único do status do protagonista com as facções** sob `### Vínculos, Laços & Matriz Relacional -> * **Reputação com Facções:**`.
  - `npcs.md` governa a afiliação política individual (`* **Facção / Afiliação:** [TAG] Nome`).
  - `diario.md` guarda o histórico cronológico imutável de mutações de reputação sob `### Registro de Reputação & Facções` e executa os relógios de facção.
* **Alternativas Consideradas**:
  - *Criar um 6º arquivo Markdown (`faccoes.md`)*: Rejeitado. Violaría a Regra de Ouro dos 5 arquivos canônicos do RPGPRO, aumentando a carga neural e fragmentando o SSOT.
  - *Armazenar reputação inteiramente em `mundo.md`*: Rejeitado. `mundo.md` descreve a diegese objetiva do cenário, não a ficha pessoal do herói.

---

## 2. Decisão 2: Escala Numérica de Reputação e Mapeamento de Testes

* **Contexto**: A reputação nas campanhas legadas era descrita qualitativamente (ex.: `Favorável / Respeitado`), impedindo avaliações determinísticas de dificuldade e reações mecânicas de NPCs.
* **Decisão**:
  - Adoção de uma **escala discreta de 7 escalões simétricos de `-3` a `+3`**:
    - `+3`: **Venerado** (Lealdade absoluta, acesso a segredos e reforços armados).
    - `+2`: **Aliado** (Apoio ativo, concessão de favores, refúgio).
    - `+1`: **Amigável** (Hospitalidade, disposição a negociar).
    - `0`: **Neutro** (Prudência profissional, relações estritamente transacionais).
    - `-1`: **Suspeito** (Vigilância velada, recusa de tréguas fáceis).
    - `-2`: **Hostil** (Inimizade declarada, recusa de diálogo, emboscadas).
    - `-3`: **Jurado de Morte** (Ordens de captura/execução sumária, perseguição implacável).
  - Mapeamento mecânico imediato para o sistema D20 3 Portões:
    - O valor da reputação atua como modificador direto situacional na DC de testes sociais ou concede Vantagem/Desvantagem no `step_1_gm_arbitration`.
* **Alternativas Consideradas**:
  - *Escala contínua percentual (0 a 100)*: Rejeitada. Gera atrito de cálculo, granularidade excessiva sem valor narrativo e perde clareza semântica no Markdown.
  - *Apenas rótulos binários (Amigo / Inimigo)*: Rejeitada. Incapaz de modelar a progressão de desconfiança e degradação política gradual.

---

## 3. Decisão 3: Moeda Social Auditável (Favores & Débitos)

* **Contexto**: O protagonista frequentemente realiza missões para facções ou contrai empréstimos e refúgios sem que haja uma métrica para saber o que a facção lhe deve ou vice-versa.
* **Decisão**:
  - Cada facção na ficha mantém dois contadores inteiros não-negativos: `Favores` ($\ge 0$) e `Débitos` ($\ge 0$).
  - **Favores**: Concedidos pelo cumprimento de missões ou sacrifícios pela facção. Podem ser consumidos pelo herói via CLI ou commit para obter suprimentos, apoio militar, anistia ou intervenções políticas.
  - **Débitos**: Contraídos por falhas, quebra de acordos ou resgates providenciados pela facção. Servem de alavanca para chantagem, imposição de missões compulsórias ou cobranças armadas.
* **Alternativas Consideradas**:
  - *Armazenar favores em ouro/riqueza*: Rejeitado. Favores políticos e de sangue não se confundem com moeda corrente de inventário.

---

## 4. Decisão 4: Automação Reativa de Contratos (`commit --quest-*`)

* **Contexto**: A especificação 007 implementou o metadado `Contratante:` em missões, mas ele operava isolado da ficha.
* **Decisão**:
  - Conclusão com sucesso (`commit --quest-complete <QID>`): Se a missão possui `Contratante: <Facção>`, credita automaticamente `+1` de reputação (travado em +3) e `+1` Favor na ficha, gravando o evento no ledger de `diario.md`.
  - Fracasso de missão (`commit --quest-fail <QID>`): Se possui contratante, aplica penalidade de `-1` de reputação (travado em -3) e incrementa `+1` Débito.
* **Alternativas Consideradas**:
  - *Exigir que o usuário passe manualmente `--faction-rep` em todo commit de missão*: Rejeitado. Violaría o princípio de automação determinística e geraria esquecimentos frequentes.

---

## 5. Decisão 5: Simulação do Turno de Facções Off-Screen (`faction --tick`)

* **Contexto**: O Showrunner precisa que o mundo respire e ameace o protagonista mesmo quando este passa semanas em descanso (`timeskip`), mas sem alucinar eventos arbitrários.
* **Decisão**:
  - Cada facção possui um atributo numérico de **Poder** (1 a 5, default 3).
  - O comando `lazy_turn.py faction --campaign <id> --tick` examina os relógios narrativos ativos associados às facções em `mundo.md`:
    - Facções com Poder 4 e 5: avançam seu relógio de projeto em +1 segmento garantido por tick.
    - Facções com Poder 2 e 3: avançam seu relógio se houver estado de conflito ou inércia no arco.
    - Facções com Poder 1: relógio avança apenas com estímulo diegético direto na cena.
  - Relógios que atingem o teto entram em estado `BREACHED` e geram alertas críticos imediatos no relatório de mundo, forçando uma reação do Mestre na próxima cena.
* **Alternativas Consideradas**:
  - *Simulador estocástico com rolagens de dados ocultas para cada facção*: Rejeitado. O RPGPRO opera de forma determinística e reproduzível; o atributo de Poder e o estado da trama fornecem previsibilidade auditável.

---

## 6. Decisão 6: Padrão de Leitura e Escrita Atômica (Single-Write Pattern)

* **Contexto**: A especificação 008 eliminou as escritas intermediárias em `quests.py` para evitar corrupção em caso de exceções no meio do processo.
* **Decisão**:
  - Em `council/factions.py`, toda operação (`add_faction`, `update_reputation`, `tick`) carrega os arquivos em memória, faz a computação e validação completa, e realiza no máximo uma única gravação (`write_text`) por arquivo ao final.
