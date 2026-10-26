# Research & Technical Decisions: 013 — Fase 04: Contexto Causal no `prepare`

**Feature:** `phase-04-causal-context`  
**Spec:** [`spec.md`](spec.md) · **Plan:** [`plan.md`](plan.md)  
**Status:** Consolidado (decisões D1–D7 ratificadas)

---

## 1. Pesquisa e Resolução das Decisões Arquiteturais

### Decisão 1: Local e ciclo de vida do cache derivado (`estado.json`)
- **Decision:** Implementar `StateProjector` (`order=50`) integrado ao `ProjectionEngine`, gravando `estado.json` tanto em `projections/estado.json` quanto espelhado na raiz da campanha (`campaigns/<id>/estado.json`), com metadados `schema_version`, `last_seq` e `hash`.
- **Rationale:** Mantém o princípio soberano D1 de que o event log é a única fonte de verdade e qualquer projeção ou cache é descartável e reconstruível. Integrar ao pipeline de projeção existente garante que todo `commit` atualize o cache de forma atômica e transparente, eliminando a necessidade de reprocessar o log inteiro durante o `prepare`.
- **Alternatives considered:**
  - *Ler diretamente o JSONL em todo `prepare`:* Rejeitado porque a leitura e agregação sequencial do histórico tornaria o `prepare` O(N) com o crescimento de turnos, violando a exigência de latência abaixo de 150ms.
  - *Armazenar em SQLite:* Rejeitado para esta fase por complexidade desnecessária e risco de corrupção ou lock de arquivos binários adicionais em Windows/PowerShell; um JSON simples estruturado resolve sem dependências extras.

### Decisão 2: Modelo de pontuação e ordenação de relevância causal
- **Decision:** Algoritmo determinístico com pontuações inteiras puras:
  - Presença em cena: +1000
  - Foco explícito na ação: +500
  - Relógio de facção crítico: +300
  - Plano ativo iminente: +300
  - Vínculo com missão ativa: +250
  - Vínculo com arco ativo: +200
  - Ameaça ativa / rivalidade: +200
  - Dívida / favor pendente: +150
  - Consequência recente: +100
  - Distância física (fora da cena): −100
  - Limiar de corte: 200 pontos. Limites padrão: Top 5 NPCs, Top 3 Facções, Top 8 fatos e Top 5 consequências. Ordenação estável por `(-score, kind, id)`.
- **Rationale:** O uso de inteiros puros e regras aritméticas evita qualquer flutuação de ponto flutuante entre plataformas, garante reproducibilidade absoluta de hashes de contexto e fornece uma lista auditável de motivos (`reasons`) para cada inclusão.
- **Alternatives considered:**
  - *Embeddings vetoriais / busca semântica:* Rejeitado expressamente pelo ROADMAP (reservado para Fase 07); introduziria dependência pesada não determinística.
  - *Ordenação heurística por data ou menção em texto:* Rejeitado por ignorar antagonistas distantes com planos ativos e manter viés de presença física.

### Decisão 3: Política de mapeamento de Modo para Audiência e Visibilidade
- **Decision:** Mapeamento estrito derivado de `ContextRequest.mode`:
  - `gm` → audiência `universe`, propósito `arbitration` (visão total, fatos canônicos, segredos, metas).
  - `narrator` / `writer` → audiência `protagonist`, propósito `narration` / `prose` (apenas o que o protagonista crê/presencia; zero `player_meta`; zero planos secretos de terceiros).
  - `architect` / `director` → audiência `author`, propósito `structure` / `direction` (arcos, fios, relógios, omissões).
  - `reviewer` → audiência `audit`, propósito `audit` (apenas issues existentes, sem injeção de contexto novo).
- **Rationale:** Alinhamento rígido com a barreira epistêmica e a `KnowledgeView` entregues na Fase 03, prevenindo contaminação de metajogo ou onisciência espúria na geração de prosa.
- **Alternatives considered:**
  - *Deixar a IA decidir o que esconder via prompt:* Rejeitado; viola o princípio de arquitetura segura onde o motor não entrega à LLM o que ela não tem autorização para saber.

### Decisão 4: Superfície e semântica da Consulta sob Demanda (`ContextQueryService` e CLI `query`)
- **Decision:** Criar `ContextQueryService` em `application/context/query.py` com consultas específicas (`claim`, `npc`, `faction`, `quest`, `clock`) e comando CLI `lazy_turn.py query --campaign <id> --kind <kind> --id <id> --audience <aud> [--json]`.
- **Rationale:** Permite ao orquestrador ou mestre consultar detalhes específicos de entidades sem poluir o núcleo do payload do turno, respeitando a mesma matriz de visibilidade da Fase 03 e retornando disponibilidade explícita (`known`, `unknown`, `unavailable`, `inexistent`).
- **Alternatives considered:**
  - *CLI com query SQL flexível:* Rejeitado por abrir brechas contra a barreira epistêmica e acoplar a interface a detalhes de persistência.

### Decisão 5: Identidade e Fallback de Protagonista e Jogador
- **Decision:** Obter `player_id` e `protagonist_id` das configurações em `regras.md` (`system:` ou `context:`), com fallback automático e determinístico: `player_id = "player"` e `protagonist_id = slug(ficha.nome)` ou `slug(campaign_id + "_protagonist")`.
- **Rationale:** Permite campanhas personalizadas sem quebrar retrocompatibilidade com fichas existentes que não declaravam IDs explícitos.
- **Alternatives considered:**
  - *Exigir migração de fichas antigas:* Rejeitado em obediência à regra de compatibilidade e preservação do ecossistema existente.

### Decisão 6: Hash de Integridade e Rastreabilidade Causal
- **Decision:** Calcular `context_hash` via SHA-256 canônico sobre a tupla `(version, core.hash, causal.hash, omissions)` serializada com chaves ordenadas, sem campos transitórios. O hash é exposto em `context.context_hash` e aceito como parâmetro opcional em `commit --context-hash`.
- **Rationale:** Permite auditar exatamente se a ação do jogador ou narrativa foi decidida sob um contexto específico, detectando desvios ou decisões tomadas sobre premissas obsoletas.
- **Alternatives considered:**
  - *Hash completo de todo o JSON payload:* Rejeitado porque o payload inclui chaves legadas e marcações transitórias de tempo que gerariam instabilidade.

### Decisão 7: Tratamento de Staleness e Concorrência do Cache
- **Decision:** `ContextStateView` compara `state.last_seq` com `EventStore.last_seq(campaign_id)`. Se houver divergência ou arquivo ausente, invoca `rebuild_projections(..., emit_audit_event=False)`, recarrega o estado e marca `context.stale = true`. Se a reconstrução falhar, levanta `PrepareError` explícito.
- **Rationale:** Garante auto-cura transparente do cache sem jamais retornar silêncio ou dados corrompidos quando alguém fizer commit externo ou rollback.
- **Alternatives considered:**
  - *Retornar contexto parcial antigo:* Rejeitado como inaceitável; levaria a decisões baseadas em fatos revogados ou desatualizados.
