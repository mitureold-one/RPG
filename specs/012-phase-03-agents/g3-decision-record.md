# G3 — Contrato Epistêmico e Fronteiras de Estado

**Projeto:** RPGPRO
**Fase de destino:** Fase 03 — Agentes
**Tipo:** Decision Record / Gate
**Status:** **Ratificado em 26/10/2026, com emendas**
**Ratifica:** proposta G3 apresentada pelo dono em 26/10/2026
**Checklist:** [`checklists/g3-ratification.md`](checklists/g3-ratification.md)
**Implementação:** condicionada à spec 012, ao `plan.md`/`tasks.md` da Fase 03 e ao R2; este registro não altera código.

---

## 1. Contexto

A Fase 03 introduz agentes com objetivos, planos, intenções, conhecimento, crenças, relações e participação em facções. Esses componentes só são seguros se houver uma fronteira explícita entre:

1. a verdade canônica do mundo;
2. as alegações que circulam no mundo;
3. o que cada agente conhece;
4. o que cada agente acredita;
5. o que a IA propõe;
6. o que o motor admite como estado ou fato.

Sem essa separação, agentes usam informação que desconhecem, crenças viram fatos e planos viram acontecimentos. O G3 fecha essas fronteiras antes dos contratos completos da Fase 03.

---

## 2. Decisões ratificadas

### G3-D01 — Verdade canônica, alegação e crença

A verdade canônica permanece separada das alegações e crenças.

- **Fato canônico:** acontecimento ou estado admitido pelo mecanismo canônico, referenciado por evento/consulta de estado.
- **Alegação:** afirmação que pode ser verdadeira, falsa, desconhecida ou indeterminada.
- **Crença:** avaliação de um agente sobre uma alegação.
- A existência de uma alegação não comprova sua veracidade.
- A confiança de um agente não altera a verdade canônica.
- A IA não converte alegação ou crença em fato por afirmar que é verdade.

**Emenda ratificada:** não existe uma segunda tabela de “fatos”. Um fato é o evento canônico ou o estado derivado dele. Alegações que não correspondem a um evento/estado usam `claim_id` próprio e permanecem alegações.

### G3-D02 — Conhecer não é acreditar

O modelo separa:

- `awareness`: `known | unknown`;
- `stance`: `believed | disbelieved | uncertain`.

Um agente pode conhecer uma alegação e rejeitá-la, aceitá-la, considerá-la incerta ou desconhecê-la. O sistema não infere que o agente acredita em tudo o que ouviu.

### G3-D03 — Proveniência

Todo conhecimento utilizável deve ter proveniência suficiente:

- conteúdo ou `claim_id`;
- origem/fonte;
- forma de aquisição: observação, testemunho, documento, comunicação, inferência ou mecanismo admitido;
- momento de aquisição;
- confiança;
- atualidade;
- informações que sustentam ou contradizem.

**Emenda ratificada:** proveniência usa referências estáveis (`source_type`, `source_id`, `channel`, `derived_from`), não texto livre. A confiança da fonte é distinta da confiança da conclusão.

### G3-D04 — Atualidade e revisão

Estados mínimos do registro epistêmico:

- `current`;
- `outdated`;
- `contested`;
- `refuted`.

Semântica ratificada:

- `current`: não há supersessão ou contradição aceita que retire a informação do estado corrente;
- `outdated`: a informação foi válida, mas não representa necessariamente a situação atual; **não é sinônimo de falsa**;
- `contested`: há evidências conflitantes aceitas, sem resolução única;
- `refuted`: o agente aceitou evidência contrária; o registro histórico permanece.

Revisões são append-only. O estado corrente é uma projeção determinística; nenhuma revisão apaga o registro anterior.

### G3-D05 — Inferências provisórias

Uma inferência preserva:

- conclusão;
- premissas, por ID;
- proveniência das premissas;
- agente responsável;
- método;
- confiança;
- momento.

Uma inferência não altera a verdade canônica. Se sustentar uma proposta de ação, o motor verifica se ela é admissível. Inferência sem premissas, com premissa inexistente ou com ciclo de proveniência é inválida.

### G3-D06 — Conhecimento individual e coletivo

O conhecimento de um NPC é separado do conhecimento de uma facção ou subgrupo.

- `holder_id` é tipado: NPC, facção, subgrupo, protagonista ou jogador.
- Uma informação conhecida por um membro não se propaga automaticamente.
- Compartilhamento exige mecanismo explícito.
- Conhecimento coletivo registra origem, escopo, confiança, atualidade e divergências.
- A facção não é onisciente e não fala com uma única opinião.

### G3-D07 — Segredos e visibilidade

A disponibilidade de informação é distinta para:

- mundo canônico;
- NPC;
- facção/subgrupo;
- protagonista como personagem;
- jogador como participante externo.

O conhecimento do jogador não implica conhecimento do protagonista. O conhecimento do protagonista não implica conhecimento dos NPCs. Um segredo registrado no log não autoriza exposição narrativa indiscriminada.

**Emenda ratificada:** a Fase 04 deve consumir uma `KnowledgeView(holder, audience, purpose)`, não o log bruto. A visibilidade é contrato de leitura, não apenas convenção de prosa.

### G3-D08 — Proposta e admissão

A IA pode propor interpretações, crenças, objetivos, revisões de plano e intenções. Proposta não é estado canônico.

- A admissão valida a proposta nos contratos aplicáveis.
- Aceitar objetivo/plano altera estado operacional, não prova alcance/execução.
- Fatos do mundo só são produzidos por mecanismos canônicos.
- Proposta rejeitada não altera estado; se auditada, é registrada como não canônica e ignorada pelo replay.

### G3-D09 — Integridade causal

Toda alteração canônica tem justificativa rastreável. O sistema impede:

- crença alterar fato diretamente;
- inferência registrada como observação;
- plano tratado como ação executada;
- proposta tratada como resultado;
- conhecimento ampliado sem aquisição válida;
- revisão de crença apagar o histórico.

### G3-D10 — Identidade da alegação e resolvedor de verdade

Toda alegação tem `claim_id` estável e proposição minimamente estruturada:

```text
Claim
  claim_id: clm_<ulid>
  proposition: {subject, predicate, object, scope}
  claim_type: occurrence | state | prediction | normative | counterfactual
  valid_from / valid_to: opcional
  source_event_id: opcional
  fact_ref: opcional
```

Resolvedor de verdade:

```text
resolve_claim(claim, at_time, world_view) -> TRUE | FALSE | UNKNOWN | INDETERMINATE
```

- `occurrence`: evento canônico aceito;
- `state`: projeção/consulta do estado no tempo;
- `prediction`/`counterfactual`: `UNKNOWN` ou `INDETERMINATE`;
- `normative`: não é truth-apt.

O resolvedor é do motor; a IA não escreve o resultado da verdade.

### G3-D11 — Registro de conhecimento e crença

```text
KnowledgeRecord
  holder_id
  claim_id
  awareness: known | unknown
  stance: believed | disbelieved | uncertain
  confidence: inteiro determinístico (0..10000)
  status: current | outdated | contested | refuted
  provenance: [ProvenanceRef]
  acquired_at
  derived_from: [ids]
  supersedes: [ids]
  visibility: escopo
```

Regras:

- confiança não é verdade;
- múltiplas fontes e crenças contraditórias coexistem;
- o registro é imutável; revisões são novos eventos;
- a visão corrente é projeção determinística;
- `confidence` usa inteiro/basis points, sem float, para replay estável.

### G3-D12 — Proveniência referenciável e integridade

```text
ProvenanceRef
  source_type: "event" | "npc" | "faction" | "document" | "inference" | "system" | "player" | "protagonist" | "subgroup"
  source_id
  channel
  acquired_at
  confidence
  derived_from: [ids]
```

- `source_id` referencia evento, NPC, facção, documento, inferência, jogador, protagonista ou subgrupo.
- **Emenda de Paridade de Atores:** `source_type` inclui formalmente `player`, `protagonist` e `subgroup` em simetria estrita com `HolderRef.kind`, assegurando que eventos de compartilhamento (`knowledge.shared`) registrem fidedignamente a proveniência sem truncamento ou mapeamento artificial.
- `derived_from` não pode formar ciclo.
- Premissa ausente/refutada não é promovida a fato.
- A cadeia de proveniência é auditável e reconstruível.

### G3-D13 — Persistência, replay e snapshots

Ratificado:

- o event log é a **única fonte de verdade**;
- estado operacional de agentes é reconstruível por replay;
- snapshots são **cache opcional**, com `last_seq`, `projection_version` e hash; nunca fonte concorrente;
- rebuild de snapshot + eventos deve ser byte-idêntico ao replay completo;
- propostas não admitidas são efêmeras ou registradas como não canônicas; replay as ignora;
- `npcs.md`/`mundo.md` são projeções/configuração, não verdade independente;
- nenhum store paralelo para conhecimento/agentes.

### G3-D14 — Conhecimento coletivo e visibilidade

- Conhecimento de facção é registro com `holder_id` de facção/subgrupo, `shared_by`, `scope` e base de compartilhamento.
- Compartilhar não é copiar automaticamente para todos os membros.
- A liderança não é onisciente; autoridade para agir é validada separadamente.
- `KnowledgeView` filtra por holder, audiência e propósito; a Fase 04 consome essa view.
- Segredos do jogador, protagonista e NPCs têm escopos distintos.

### G3-D15 — Correção e crenças

- Corrigir um fato canônico **não reescreve automaticamente** a crença de um agente.
- A crença histórica permanece; ela pode ser marcada como `outdated`/`contested` quando o agente adquire a correção.
- A mudança de crença exige evento epistêmico próprio (`knowledge.revised`/equivalente).
- Inferência baseada em premissa refutada permanece histórica; não vira fato.
- A correção deve considerar dependências epistêmicas e ser compatível com `correction.issued`/`correction.recomputed` da Fase 02.

---

## 3. Fronteiras arquiteturais

O G3 não implementa:

- domínio completo de agentes;
- objetivos/planos completos;
- scheduler global;
- política completa de avaliação;
- armazenamento paralelo ao event log;
- a Fase 03 antes da spec/plan/tasks.

A Fase 05 continua responsável pelo `world_tick`, orçamento, prioridade, retry e coordenação das avaliações. A Fase 03 expõe avaliação de agente e contratos epistêmicos; não assume o scheduler.

---

## 4. Critérios de aceitação

### AT01 — Fato vs crença
NPC acredita que o rei morreu; o rei está vivo. A crença permanece; o fato canônico não muda.

### AT02 — Conhecer sem acreditar
NPC recebe alegação e a considera falsa. A alegação conhecida permanece sem obrigar crença.

### AT03 — Proveniência
NPC afirma conhecer segredo. O sistema encontra origem/mecanismo de aquisição admitido.

### AT04 — Informação falsa
NPC acredita em relato falso. A crença influencia decisões sem virar verdade canônica.

### AT05 — Desatualização
Informação histórica difere da situação vigente; ambas são distinguíveis.

### AT06 — Inferência
NPC deduz suspeito por evidências indiretas. A conclusão é inferência com premissas, não fato.

### AT07 — Conhecimento coletivo
Membro descobre segredo não compartilhado; demais membros não passam a conhecê-lo.

### AT08 — Segredo do jogador
Jogador conhece fato que o protagonista desconhece; o protagonista não o utiliza sem aquisição válida.

### AT09 — Proposta não admitida
Proposta de crença/objetivo/plano é rejeitada; não altera estado canônico nem operacional aceito.

### AT10 — Reconstrução e correção
Sequência altera conhecimento; correção posterior preserva fatos válidos, estado reconstruído e proveniência.

### AT11 — Fontes contraditórias
Duas fontes conflitantes coexistem com proveniência e confiança; o motor não escolhe a verdade sozinho.

### AT12 — Desatualizado não é falso
Informação antiga continua registrada; a situação atual é diferente e a distinção é explícita.

### AT13 — Inferência com premissa refutada
Premissa é corrigida; a inferência permanece histórica e não é promovida a fato.

### AT14 — Facção dividida
Conhecimento compartilhado pela liderança não aparece automaticamente em todos os membros; divergência interna permanece.

### AT15 — Correção não reescreve crença
Corrigir o fato não altera a crença; a crença só muda quando o agente adquire a correção.

### AT16 — Replay e snapshot
Estado epistêmico reconstruído é byte-idêntico ao replay; proposta rejeitada não entra no estado.

### AT17 — Visibilidade
`KnowledgeView` impede que segredo de NPC/facção vaze para o protagonista, jogador ou contexto errado.

Cada teste deve registrar eventos, estado reconstruído e projeção; qualidade de prosa não é critério.

---

## 5. Condições de implementação

1. Este G3 está ratificado; a Fase 03 pode ser especificada.
2. A spec 012 deve definir eventos, schemas, upcasters e projeções compatíveis com a Fase 02.
3. O R2 deve preceder o crescimento de `narrator.py`/`factions.py`/`quests.py`.
4. O scheduler continua na Fase 05.
5. Nenhuma implementação começa antes de `spec.md`, `plan.md` e `tasks.md` da Fase 03 serem aprovados.

---

## 6. Registro de ratificação

Ratificado em 26/10/2026 com as emendas G3-D10 a G3-D15 incorporadas. O checklist item a item está em [`checklists/g3-ratification.md`](checklists/g3-ratification.md).

**Relações:** [`ROADMAP.md`](../../ROADMAP.md) §3/§5; [`ARCHITECTURE.md`](../../ARCHITECTURE.md); [`specs/010-phase-02-causal-history/spec.md`](../010-phase-02-causal-history/spec.md); [`EXECUCAO.md`](../../EXECUCAO.md).
