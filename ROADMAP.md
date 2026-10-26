# RPGPRO — Roadmap de Evolução

**Status:** documento de direção técnica e narrativa; não é uma especificação final aprovada.
**Snapshot:** commit `df514d6` (Fases 01, 01.5 e 02/R1).
**Fontes:** [`ARCHITECTURE.md`](ARCHITECTURE.md), [`rpgpro-diretrizes-agentes.md`](rpgpro-diretrizes-agentes.md), [`DECISOES_ARQUITETURA.md`](DECISOES_ARQUITETURA.md), [`AGENTS.md`](AGENTS.md), auditoria arquitetural de 22/10/2026.

> **Regra de leitura:** este roadmap separa **decisões de comportamento confirmadas** de **decisões técnicas pendentes**. Não trate um gate pendente como requisito já resolvido. A ordem das fases segue dependências causais, não preferência estética.

---

## 1. Visão e princípios

O RPGPRO é uma camada determinística de orquestração, estado e auditoria para um agente/LLM externo. O repositório não executa chamadas a modelos; ele fornece contratos, resolução mecânica, persistência e auditoria.

Princípios que governam todas as fases:

1. **Autonomia quase total:** o mundo continua evoluindo sem o protagonista.
2. **Causalidade:** eventos respeitam fatos, capacidades, recursos, conhecimento, localização, pré-condições e regras.
3. **IA propõe; o motor valida e resolve:** a IA não declara sucesso de ação impossível ou incerta.
4. **Plano não é fato:** intenção, tentativa e acontecimento são estados distintos.
5. **Histórico causal rastreável:** tentativas, resultados, efeitos e correções têm origem e dependências.
6. **Histórico imutável no fluxo normal:** correções são novos registros; o passado não é apagado silenciosamente.
7. **Verdade separada de conhecimento:** mundo, jogador e personagens são camadas distintas.
8. **Simulação global com profundidade seletiva:** o mundo avança; só o que exige análise causal recebe avaliação profunda.
9. **Progressão verificável:** atividade não é avanço; o motor observa mudanças reais.
10. **Memória em camadas:** prosa original, histórico causal estruturado e resumos derivados.
11. **Retomada segura:** limite de ciclo não apaga trabalho nem duplica efeitos.
12. **Evolução incremental:** preservar o que funciona; não reescrever sem evidência.

---

## 2. Estado atual

### 2.1 Fase 01 — Fundação: concluída neste ciclo

Entregue:

- escrita atômica (`atomic_write_text`) e lock cooperativo por campanha;
- snapshot e restauração de `ficha.md`, `diario.md`, `npcs.md` e `mundo.md` em falha inesperada de commit;
- validação prévia de relógios, missões e facções no `commit`, sem criar entidades fantasmas;
- `clock --advance`/`--resolve` deixam de criar relógio inexistente;
- parsing de `--npc-updates` com separação correta de subcampos (`Atitude:`, `Relação:`, `Vínculos:`);
- idempotência de conclusão de missão feita pela CLI e depois pelo commit;
- `check-prose --file` e `commit --prose-file` funcionais;
- calendário declarativo (`calendar:` em `regras.md`) e fallback conservador para avanços dentro do mês;
- 68 testes automatizados verdes na Fase 01 (69 com a Fase 01.5), incluindo 12 testes de estabilidade.

Limites conhecidos:

- o rollback cobre exceções; não é uma transação ACID multiarquivo;
- persistência de `--prose` original por turno deferida para o event store da Fase 02.

### 2.2 Fase 01.5 — Fechamento da fundação: concluída neste ciclo

Entregue:

- calendário completo de Valíria declarado em `regras.md` (12 meses boreais de 30 dias, ciclo de 360 dias);
- `faction --rep` (e favores/débitos) estrito por padrão: typos barram mutação na ficha e ledger; flag `--create` explícita para cadastros avulsos intencionais;
- revisão e blindagem dos caminhos de prosa (`check-prose` e `commit --prose-file`/`--prose`) com checagem de existência de arquivo e emissão de `prose_status: PASSED`;
- 69 testes automatizados verdes sob sandbox.

### 2.3 O que ainda não existe

- log de eventos imutável e projeções;
- correções com reavaliação de dependências;
- proposta/tentativa validada pelo motor;
- NPCs com objetivos, planos, recursos e conhecimento individual;
- facções com liderança, subgrupos e política interna;
- tick de mundo por tempo, com orçamento e fila;
- diretor narrativo causal;
- arcos flexíveis por marcos e condições;
- memória derivada rastreável e recuperação por fonte;
- separação explícita entre conhecimento do jogador e do protagonista.

---

## 3. Fases

### Fase 01 — Fundação

**Objetivo:** construir sobre estado consistente.
**Status:** concluída.
**Entregáveis:** atomicidade, lock, rollback, validação de entidades, parsing, idempotência, calendário parcial, testes.
**Critério de aceite:** suíte verde; nenhum typo cria relógio/missão/facção; commit com falha simulada restaura o snapshot; prosa por arquivo funciona.

### Fase 01.5 — Fechamento da fundação

**Objetivo:** eliminar as últimas pontas antes da história causal.
**Status:** concluída.

**Entregáveis:**

- calendário completo de Valíria em `regras.md`;
- `faction --rep` estrito por padrão, com `--create` explícito para cadastro intencional;
- revisão dos caminhos de prosa e dos testes de contrato;
- decisão sobre persistir `--prose` já na Fase 02 (recomendado: sim).

**Dependência:** dados do calendário de Valíria.
**Critério de aceite:** `+30d` em Valíria funciona com calendário declarado; typo de facção não cria registro; suíte verde.

### Fase 02 — História causal

**Status:** **aprovada** em 26/10/2026 — G1/G2 ratificados, C1–C4 aprovados, 211 testes e QA final aprovado (`EX-0021`; `specs/010` e `specs/011`).

**Objetivo:** registrar tentativas, resultados, custos, efeitos e correções sem perder o passado.

**Entregáveis:**

- schema de evento com `event_id`, `turno`, `versão`, tipo, ator, alvo, pré-condições, resultado, custos, dependências e estado (`proposta`, `tentativa`, `concluída`, `rejeitada`, `adiada`, `abandonada`);
- store append-only (JSONL canônico; SQLite opcional, conforme G1);
- projector que reconstrói `diario.md`/estado atual a partir dos eventos válidos;
- correções como novos eventos que referenciam os afetados;
- grafo de dependências v1 e reavaliação seletiva;
- fila esqueleto para trabalho não concluído;
- registro da prosa original por turno/cena.

**Dependências:** Fase 01; gates G1 e G2.
**Critério de aceite:** evento ida-e-volta; rebuild de projeção sem duplicar efeitos; correção reavalia só dependências afetadas; prosa antiga recuperável; teste de retomada sem duplicação.

### Fase 03 — Agentes

**Status:** pronta para planejamento; implementação bloqueada até a ratificação do G3.

**Objetivo:** NPCs e facções com estado persistente, objetivos e conhecimento próprio.

**Entregáveis:**

- modelo de dois níveis: NPC relevante (detalhado) e secundário (simplificado, promovível);
- objetivos de curto/médio/longo prazo, prioridades, planos em etapas, pré-requisitos, alternativas e condições de conclusão;
- recursos, capacidades, localização, condição e compromissos;
- conhecimento com proveniência, confiança e crenças; informação falsa/desatualizada;
- relações com confiança, rivalidade, dependência, dívidas e lealdades;
- facção com objetivos coletivos, liderança, autoridade, sucessão, subgrupos, divergências e conspirações;
- validação de capacidade/recurso/conhecimento antes de aceitar uma proposta.

**Dependências:** Fase 02; gate G3.
**Critério de aceite:** NPC com objetivo produz ação planejada sem o protagonista; NPC não usa fato que desconhece; facção não é tratada como opinião única; plano não vira fato automaticamente.

### Fase 04 — Contexto causal

**Objetivo:** o `prepare` montar contexto por relevância causal, não por presença.

**Entregáveis:**

- três camadas: núcleo obrigatório, contexto causal da cena, consulta sob demanda;
- injeção de arco, relógios, missões, planos, fatos, consequências e conhecimento;
- seleção de NPCs/facções por ameaça, plano, dívida, relação ou impacto iminente, mesmo à distância;
- distinção explícita entre desconhecido, indisponível e inexistente;
- consulta ao estado persistente quando o núcleo não bastar.

**Dependências:** Fases 02 e 03.
**Critério de aceite:** antagonista distante com plano iminente entra no contexto; `prepare` não inventa fato ausente; jogador e protagonista recebem camadas diferentes; snapshot de payload estável.

### Fase 05 — Simulação

**Objetivo:** o mundo evoluir por tempo e eventos, com profundidade seletiva.

**Entregáveis:**

- `world_tick(elapsed_minutes)` acionado por tempo, viagem, descanso e eventos críticos;
- planos e relógios avançam proporcionalmente ao tempo;
- avaliação global por relevância: profunda só para entidades afetadas;
- gatilhos determinísticos e solicitações da IA validadas e registradas;
- orçamento adaptativo, prioridade, retry e fila persistente;
- retomada idempotente sem duplicar efeitos;
- calendário completo e agendamento futuro.

**Dependências:** Fases 02, 03 e 04; gate G4.
**Critério de aceite:** `+7d` avança planos/relógios; evento off-screen tem causa; limite de orçamento não apaga evento concluído; retomada não duplica; calendário permanece consistente.

### Fase 06 — Direção

**Objetivo:** escolher o que narrar sem inventar causalidade.

**Entregáveis:**

- diretor que pontua urgência, risco irreversível, causalidade, impacto, relevância de arco, oportunidade de decisão e cronologia;
- arcos flexíveis com marcos e condições de conclusão, substituindo fases rígidas;
- detecção de estagnação semântica com intervenção causal plausível;
- controle de revelação: mundo, revelado ao jogador, conhecido pelo protagonista;
- separação entre conhecimento do jogador e do personagem.

**Dependências:** Fases 04 e 05; gate G5.
**Critério de aceite:** todo turno tem decisão registrada; nenhum conflito novo sem elo causal; arco pode mudar de direção/terminar por resultado; estagnação gera intervenção sustentada, não aleatória.

### Fase 07 — Memória derivada

**Objetivo:** resumos rastreáveis e recuperação de longo prazo.

**Entregáveis:**

- três camadas: prosa original, histórico causal estruturado, memórias derivadas;
- resumos de relações, objetivos, arcos e acontecimentos com links para fontes;
- reconstrução/atualização de resumos sem apagar o histórico;
- recuperação por fonte, turno, entidade ou ID de evento;
- crenças mantidas mesmo quando a verdade histórica as contradiz.

**Dependências:** Fases 02 e 03; gate G6.
**Critério de aceite:** promessa antiga recuperada com fonte; resumo sem fonte é rejeitado; corrigir a verdade não altera automaticamente a crença; memória offline não impede recuperação local.

### Fase 08 — Migração e E2E

**Objetivo:** provar que o sistema funciona nas campanhas reais.

**Entregáveis:**

- migração das três campanhas;
- os dez cenários de comportamento do documento de diretrizes;
- benchmark de tokens, latência e crescimento;
- compatibilidade com campanhas antigas e com o SSOT Markdown.

**Dependências:** todas as fases; gate G7.
**Critério de aceite:** 3 campanhas `CLEAN` com o novo estado; 10 cenários verdes; custo dentro do orçamento; nenhum dado histórico perdido.

---

## 4. Decisões confirmadas × fases

| Decisão | Fase | Lacuna atual |
|---|---|---|
| §3.1 Autonomia quase total | 05 | Só relógios e tick manual |
| §3.2 IA propõe; motor valida/resolve | 02–05 | `commit` confia em texto livre |
| §3.3 Incerteza contextual | 05 | d20 opcional decidido pelo modelo |
| §4.1 Registrar todas as tentativas | 02 | Só turno resumido |
| §4.2 Histórico imutável + projeção | 02 | Markdown mutável |
| §4.3 Reavaliar dependências | 02 | Inexistente |
| §4.4 Irreversibilidade | 02 | Pendente de detalhe técnico |
| §4.5 Ciclos causais | 02/05 | Inexistente |
| §5.1 Tempo decorrido e eventos | 05 | `--time` parcial; mundo não avança |
| §5.2 Simulação global por relevância | 05 | Inexistente |
| §5.3 Gatilhos determinísticos + IA | 05 | Inexistente |
| §5.4 Orçamento e fila persistente | 05 | Inexistente |
| §6.1–6.3 NPCs, planos, dois níveis | 03 | Schema único, sem planos |
| §6.4 Conhecimento individual | 03/07 | Lista global de termos |
| §7.1 Facções com política interna | 03 | Uma linha por facção |
| §8.1 Diretor causal | 06 | Heurística de palavras-chave |
| §8.2 Perspectiva controlada | 06/07 | Inexistente |
| §9.1 Arcos flexíveis | 06 | `arc --stage` rígido |
| §9.2 Estagnação e intervenção | 06 | Comparação de strings |
| §10.1 Contexto em três camadas | 04 | Payload sem arco/planos |
| §10.2 Memória em três camadas | 02/07 | Resumo de uma linha |
| §11 Fluxo integrado | 04–06 | `prepare` → prosa → `commit` |
| §13 Cenários obrigatórios | 08 | 69 testes de contrato |

---

## 5. Gates de especificação

Não iniciar a fase inteira antes de resolver o gate correspondente.

| Gate | Decisão necessária | Bloqueia |
|---|---|---|
| **G1** | Ratificar envelope e IDs; fechar payloads, serialização/versionamento e retenção | Fase 02 |
| **G2** | Correções, dependências, reconstrução e efeitos sobre a história persistida | Fase 02 |
| **G3** | Schema de conhecimento, proveniência, confiança, crença falsa | Fase 03 |
| **G4** | Limites de orçamento, prioridade, retry, retomada | Fase 05 |
| **G5** | Modelo de arco, critérios do diretor, revelação | Fase 06 |
| **G6** | Armazenamento da prosa, indexação, reconstrução de resumos | Fase 02/07 |
| **G7** | Harness de cenários e critérios objetivos | Fase 08 |

G1 não reabre o que o [`ARCHITECTURE.md`](ARCHITECTURE.md) já fixou: JSONL canônico, `evt_<ulid>` e o envelope do evento. Ele ratifica essas escolhas e fecha o que ainda está aberto. G2 é o dono exclusivo da política de correção e reconstrução; nenhum dos dois invade o escopo do outro.

**Status em 26/10/2026:** Fase 02/R1 concluída e aprovada; G1 e G2 **ratificados com ajustes**; ver [`specs/010-phase-02-causal-history/spec.md`](specs/010-phase-02-causal-history/spec.md), [`specs/011-close-phase02-qa-p2/spec.md`](specs/011-close-phase02-qa-p2/spec.md) e [`EX-0021`](EXECUCAO.md). G3–G7 seguem abertos; a Fase 03 depende do G3.

Enquanto um gate estiver aberto, a fase correspondente pode ter protótipo e testes de contrato, mas não deve ser declarada concluída.

---

## 6. Arquitetura e refatoração

### 6.1 Hotspots atuais

| Arquivo | Linhas | Responsabilidades | Alvo |
|---|---:|---|---|
| [`lazy_turn.py`](lazy_turn.py) | 2.101 | CLI, argparse, comandos, payload, validação, tempo | `interfaces/cli/` + `application/`; entry point < 200 linhas |
| [`council/ssot.py`](council/ssot.py) | 797 | ficha, diário, relógios, arco, fila, progressão | `resources/` (estado) + projeções |
| [`council/factions.py`](council/factions.py) | 853 | parse, reputação, ledger, tick, contexto | `resources/factions/` |
| [`council/reviewer.py`](council/reviewer.py) | 688 | prosa, integridade, tempo, facções, missões, XP | `review/` |
| [`council/narrator.py`](council/narrator.py) | 600 | NPC, vínculos, iniciativa, barreira, updates | `resources/npcs/` |
| [`council/quests.py`](council/quests.py) | 506 | parser, ciclo de vida, ledger | `resources/quests/` |
| [`council/helpers.py`](council/helpers.py) | 637 | paths, manifest, templates, tempo, atomic, lock | `kernel/`, `persistence/`, `temporal/`, `campaign/` |

### 6.2 Estrutura-alvo

A árvore canônica, as portas de extensão, as regras de dependência e o kernel vivem em [`ARCHITECTURE.md`](ARCHITECTURE.md). Este roadmap não duplica a árvore para evitar duas versões contraditórias.

### 6.3 Regras de desenho

- 150–300 linhas por arquivo como alvo; 400 como alerta; 600 como falha de revisão.
- Uma razão para mudar por arquivo; nada de `utils.py`.
- Direção de dependência e proibições: ver [`ARCHITECTURE.md`](ARCHITECTURE.md) §4.
- Domínio não importa CLI; plugin não faz I/O; aplicação é dona da transação.
- `council/__init__.py` só reexporta; sem lógica.
- `lazy_turn.cmd_*` continua existindo como alias para não quebrar testes e chamadas externas.
- Não fragmentar funções de 20 linhas em arquivos separados; agrupar por caso de uso.

### 6.4 Sequência de refatoração

| Etapa | Quando | O que move | Critério de aceite |
|---|---|---|---|
| **R0** | Antes da Fase 02 (Concluído) | criar `contracts/` + `kernel/` + `bootstrap.py` + suíte de contrato com fakes; extrair CLI, persistência, `temporal/` e campanha de `lazy_turn.py`/`helpers.py`; sem emissão de eventos | 157 testes automatizados verdes; `lazy_turn.py` com 54 linhas; Markdown idêntico; contratos exercitados com fakes |
| **R0.5** | Antes da Fase 02 | arquivar campanhas, criar fixtures, atualizar testes, apagar `campaigns/*` | suíte verde sem campanhas reais; `init-campaign` funciona |
| **R1** | Com a Fase 02 (Concluído) | `ssot.py` → `resources/`; `EventStore` JSONL + índice; `Projector`s; `EventType`s e upcasters | nenhum arquivo > 300; evento ida-e-volta; rebuild de projeção; implementações aprovadas na suíte de contrato |
| **R2** | Com a Fase 03/04 | `narrator.py` → `resources/npcs/`; `factions.py` → `resources/factions/`; `quests.py` → `resources/quests/`; `context/` | módulos < 300; sem ciclos; `BehaviorPolicy`/`FactionPolicy`/`ContextProvider` testados |
| **R3** | Com a Fase 05/06 | `reviewer.py` → `review/`; `world/` com simulação, budget, diretor e estagnação | lints independentes; diretor determinístico; orçamento testado |
| **R4** | Com a Fase 07 | `memory/` e `knowledge/` | proveniência rastreável; resumos reconstruíveis |

**R0 é a única refatoração que pode ser feita já**, porque é behavior-preserving e não depende dos gates. As demais acompanham as fases.

### 6.5 Cuidados de migração

- Commitar a Fase 01 antes de `git mv`; caso contrário a refatoração mistura histórico.
- Manter os nomes públicos (`cmd_prepare`, `parse_ficha_md`, etc.) reexportados; os testes atuais são o contrato.
- Atualizar `patch(...)` de testes que apontam para `lazy_turn.cmd_review` se o comando for movido.
- Uma etapa por vez, suíte verde; não mover dezenas de arquivos em um commit.
- Contratos antes de adaptadores: nenhum store real entra antes da suíte de contrato com fakes.
- `temporal/` substitui `time/` para não colidir com o módulo padrão `time`.
- Teste que copia campanha viva deve pinar os campos que assume; caso contrário o resultado depende do estado de jogo.
- Medir linhas por arquivo, ciclos de import, tempo da suíte e duplicação de escrita.

---

## 7. Testes e critérios de aceite

### 7.1 Estado atual

- 211 testes automatizados verdes (incluindo suíte de estabilidade, suíte de contratos com fakes e `JsonlEventStore`, validação de schema/registry/runtime, C1–C4 e todos os cenários da Fase 02/R1 com aprovação integral de QA).
- Os testes de comportamento de agentes (Fase 03) ainda não existem.

### 7.2 Cenários obrigatórios da Fase 08

1. Salto temporal de vários dias: relógios, missões e planos evoluem.
2. Conflito entre dois NPCs: recursos, objetivos e circunstâncias determinam o resultado.
3. Mudança política fora de cena: facção evolui sem o protagonista.
4. Conhecimento restrito: personagem não usa informação que desconhece.
5. Correção de evento: só dependências afetadas são reavaliadas.
6. Retomada da fila: efeitos concluídos não são duplicados.
7. Arco alterado por derrota: muda de direção ou termina coerentemente.
8. Campanha estagnada: diretor encontra intervenção causal plausível.
9. Memória de longo prazo: promessa antiga recuperada com fonte.
10. Calendário personalizado: datas e durações consistentes em saltos.

Cada cenário deve ter estado inicial, ação/tempo, comportamento esperado e asserção objetiva em JSON/Markdown. Qualidade de prosa não é critério de aprovação.

---

## 8. Próximos passos imediatos

1. **Fase 01 e 01.5 concluídas:** fundação de estabilidade, calendário declarativo e blindagem de prosa (`EX-0001`/`EX-0002`).
2. **R0 concluído:** contratos (`contracts/`), kernel de extensão (`kernel/`), `bootstrap.py` e extração modular de CLI, persistência, `temporal/` e `campaign/` (`EX-0004` a `EX-0007`).
3. **R0.5 concluído:** arquivamento de campanhas em `archive/campaigns/`, fixtures em `tests/fixtures/campaigns/`, `campaigns/` limpo com `.gitkeep` (`EX-0008`).
4. **Auditoria QA concluída:** correções de drift de calendário P1-A, contenção de `campaign_id` P2-1, all-or-nothing de templates P2-2, e lock transacional em plan/progress P2-3 (`EX-0009` / `QA-FASE-01.md`).
5. **Fase 02/R1 concluída e aprovada (26/10/2026):** G1/G2, spec 010 (C1–C4), remediação P2 da spec 011, 211 testes e QA final aprovado (`EX-0021`).
6. **Próximo passo — Fase 03/Agentes:** ratificar o G3 (schema de conhecimento, proveniência, confiança e crença falsa) e abrir a spec 012; a fase não pode ser declarada concluída antes do G3.
7. **R2 em paralelo à Fase 03/04:** decompor `narrator.py`, `factions.py`, `quests.py` e `context/` em módulos menores; depois seguir R3/R4.

---

## 9. Fora de escopo por enquanto

- reescrever o RPGPRO do zero;
- obrigar todas as campanhas a usar d20;
- simular todos os NPCs com o mesmo nível de detalhe;
- diretor inventar acontecimentos sem base causal;
- tratar resumos derivados como fonte histórica autoritativa;
- implementar escolhas técnicas pendentes sem revisão;
- declarar uma fase concluída sem teste de comportamento observado.

---

## 10. Histórico de decisões

- **22/10/2026:** auditoria arquitetural e narrativa; separação entre implementado, prompt-only e ausente.
- **22/10/2026:** Fase 01 implementada (atomicidade, validação, parsing, idempotência, calendário).
- **22/10/2026:** consolidação das diretrizes de mundo autônomo em [`rpgpro-diretrizes-agentes.md`](rpgpro-diretrizes-agentes.md).
- **22/10/2026:** roadmap revisado para história causal, agentes, contexto, simulação, direção e memória derivada.
