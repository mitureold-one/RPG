# Architectural Research: 010 — Fase 02: História Causal & Refatoração R1

**Feature:** `phase-02-causal-history`  
**Status:** Completed  
**Created:** 2026-10-24  
**Context:** Resolução das decisões de engenharia, trade-offs e requisitos técnicos para a implementação da Fase 02 do [`ROADMAP.md`](../../ROADMAP.md) e etapa R1 da refatoração de arquitetura, fundamentada nos gates G1 e G2 ratificados com ajustes ([`checklists/g1-g2-ratification.md`](checklists/g1-g2-ratification.md)).

---

## 1. Decisão 1: Formato de Persistência Canônica do EventStore e Resiliência a Falhas (G1-D1, G1-D2, C1)

* **Contexto:** O R0 introduziu o protocolo `EventStore` com `FakeEventStore` em memória. A Fase 02 exige um `EventStore` durável em disco com semântica de append-only estrita, ordenação monotônica por campanha, isolamento concorrente e resiliência contra crashes durante a escrita de lotes parciais.
* **Decisão:**
  - O repositório canônico de verdade é uma sequência de segmentos JSONL particionados por campanha em `campaigns/<id>/events/<segment_index:06d>.jsonl` (ex.: `000001.jsonl`).
  - O mecanismo atômico de lote utiliza marcadores explícitos por segmento:
    1. Linha de abertura: `{"record":"batch","state":"open","batch_id":"bat_<ulid>","first_seq":N,"event_count":K}`
    2. K linhas de eventos: `{"record":"event","event_id":"evt_<ulid>","campaign_id":"...","seq":N+i,...}`
    3. Linha de confirmação: `{"record":"batch","state":"committed","batch_id":"bat_<ulid>","last_seq":N+K-1,"hash":"sha256:..."}`
  - Leitura e Reconstrução: Qualquer leitor ignora eventos pertencentes a lotes sem marcador `batch.committed`.
  - Critério C1 (Recuperação no Append): Antes de aceitar um novo append em um segmento que possui um lote incompleto (sem `committed`), o store trunca o arquivo até a posição do último `committed` válido verificado.
  - O `index.sqlite` é um artefato puramente derivado e opcional no R1: todas as operações fundamentais (`append`, `read`, `last_seq`, `rebuild`) operam diretamente via varredura sequencial dos segmentos JSONL com lock de arquivo cooperativo.
* **Racional:**
  - Marcadores de lote em JSONL com flush e fsync garantem atomicidade all-or-nothing sem criar milhares de arquivos minúsculos (o que ocorreria se cada lote fosse um arquivo isolado).
  - A recuperação prévia (truncamento de cauda não confirmada) impede a formação de "buracos" ou "fantasmas" na sequência monotônica e garante que nenhum dado parcial seja lido após crash.
* **Alternativas Consideradas:**
  - *Um arquivo JSONL por lote (`events/batch_000001.jsonl` com `os.replace`)*: Descartado porque satura o sistema de arquivos com dezenas de milhares de arquivos em campanhas longas e dificulta rotação e snapshots de segmento.
  - *SQLite como fonte primária de verdade*: Rejeitado categoricamente pela Decisão D2 do [`ARCHITECTURE.md`](../../ARCHITECTURE.md); SQLite pode corromper binariamente e não é inspecionável com ferramentas de texto padrão como git/grep.

---

## 2. Decisão 2: Hashes Criptográficos e Validação de Integridade (G1-D6, FR-G1-10)

* **Contexto:** Integridade e auditoria de cada evento e de lotes inteiros exigem hashes reproduzíveis e determinísticos.
* **Decisão:**
  - Adoção de **dois hashes distintos e independentes**, ambos prefixados com `sha256:`:
    1. **Hash do Evento:** SHA-256 calculado sobre os bytes UTF-8 da serialização JSON canônica do envelope de evento puro (sem o campo operacional `record`).
    2. **Hash do Lote:** SHA-256 calculado sobre a concatenação em bytes dos JSONs canônicos dos eventos do lote ordenados por `seq`, gravado no registro `batch.committed`.
  - Serialização Canônica: Utiliza o módulo padrão `json` com `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")`.
* **Racional:**
  - Separar o hash individual do evento do hash do lote permite auditoria granular (verificar se um evento foi adulterado isoladamente) e auditoria de bloco (verificar se o lote foi gravado íntegro sem omissão de itens).
* **Alternativas Consideradas:**
  - *Hash encadeado estilo blockchain (cada evento aponta para o hash do anterior)*: Rejeitado por complexidade desnecessária para o R1 (YAGNI/Ponytail), já que a sequência monotônica contígua e o hash do lote cobrem integralmente o risco de adulteração.

---

## 3. Decisão 3: Obrigatoriedade de Tempo de Jogo e Proibição de Defaults pelo Store (G1-D4, FR-G1-05)

* **Contexto:** No R0, o `FakeEventStore` usava `"01 de Janeiro de 304, 00:00"` como default quando `game_time` não era fornecido, mascarando possíveis falhas na camada de aplicação.
* **Decisão:**
  - `game_time` (`str`, texto não-vazio) e `game_time_sort` (`int`, minutos decorridos $\ge 0$) tornam-se **estritamente obrigatórios** em todo `EventDraft`.
  - Se um draft for enviado ao `EventStore.append()` sem `game_time` ou com `game_time_sort is None`, o store rejeita a transação imediatamente com `ValueError` tipado, sem consumir sequência nem gravar nada em disco.
  - A responsabilidade de calcular o tempo de jogo canônico e seus minutos ordenáveis é da camada de aplicação (`application/`), utilizando o `CalendarProvider` da campanha.
* **Racional:**
  - O store é infraestrutura de persistência pura; inventar tempo fictício mascara descompassos narrativos e viola a rastreabilidade causal.

---

## 4. Decisão 4: Catálogo Mínimo v1, Schemas e Upcasters (G1-D9, G1-D10, G1-D7)

* **Contexto:** É imperativo que 100% das mutações hoje existentes nos 5 arquivos Markdown sejam cobertas por eventos tipados e validados, sem que o kernel precise de blocos `if event_type == ...`.
* **Decisão:**
  - Congelamento do catálogo mínimo de 23 tipos de eventos v1 (especificados na seção 2.2 da spec 010):
    * Ciclo de Vida da Campanha: `campaign.created`
    * Execução de Comandos: `command.executed`
    * Loop Narrativo de Turno: `turn.proposed`, `turn.rejected`, `action.resolved`, `turn.committed`
    * Relógios: `clock.created`, `clock.advanced`, `clock.resolved`
    * Missões: `quest.created`, `quest.objective_completed`, `quest.completed`, `quest.failed`, `quest.status_changed`
    * Showrunner & Cenas: `arc.updated`, `scene.planned`, `scene.completed`
    * NPCs & Facções: `npc.updated`, `faction.reputation_changed`
    * Ficha do Protagonista: `protagonist.progression_changed`, `protagonist.sheet_changed`
    * Prosa & Artefatos: `prose.recorded`
    * Correções & Auditoria: `correction.issued`, `correction.recomputed`, `projection.rebuilt`
  - Cada `EventType` é registrado explicitamente no `bootstrap.py` com `payload_schema` estrito e mapa de `upcasters: dict[int, Callable]`.
  - O kernel valida o draft contra o `payload_schema` do tipo registrado. Tipos desconhecidos são rejeitados com `RpgError("UNKNOWN_EVENT_TYPE")`.
  - Eventos lidos com `schema_version` inferior à atual passam pela cadeia de upcasters $N \to N+1$. Eventos com versão futura são rejeitados com `SchemaError`.
* **Racional:**
  - Evita mutações silenciosas de estado e garante evolução de esquemas à prova de quebras retroativas.

---

## 5. Decisão 5: Grafo de Dependências Causal e Referências Intra-Lote (G2-D2, C2, FR-G2-09)

* **Contexto:** O passado é causal, não meramente cronológico. Eventos declaram dependências através de `meta.dependencies: list[str]`. No entanto, em um mesmo turno (ex.: `commit_turn`), múltiplos eventos dependem uns dos outros dentro do próprio lote a ser persistido (ex.: `turn.committed` depende de `turn.proposed` e de `action.resolved`).
* **Decisão:**
  - O grafo é um Grafo Acíclico Dirigido (DAG). Ciclos e referências a eventos inexistentes são rejeitados na validação prévia ao append.
  - **Suporte a Dependências Intra-Lote (Critério C2):** A validação do append constrói um índice transitório contendo todos os `event_id` já confirmados no log somados aos `event_id` provisórios dos eventos anteriores do próprio lote em validação.
  - É permitido a um evento depender de um evento que o precede no mesmo lote. É proibido depender de eventos futuros do mesmo lote (dependência para frente) ou de si mesmo (auto-referência).
  - Profundidade máxima do grafo configurada em 64 níveis; profundidades maiores geram `DependencyDepthError`.
* **Racional:**
  - Permite que um turno atômico expresse causalidade interna sem a necessidade de gravar lotes separados no disco para cada etapa do pipeline narrativo.

---

## 6. Decisão 6: Reavaliação Seletiva de Correções e Contradições Causais (G2-D1, G2-D3, C4, FR-G2-11)

* **Contexto:** Erros narrativos ou de cálculo ocorrem. Em vez de sobrescrever o passado (mutação de Markdown), uma correção é emitida como `correction.issued`.
* **Decisão:**
  - O evento original nunca é alterado ou deletado.
  - O subsistema de correção identifica todos os nós dependentes no grafo causal (expansão transitiva do DAG a partir de `corrects`).
  - Efeitos compensáveis (ex.: XP atribuído incorretamente, saldo de atributo/habilidade) geram eventos compensatórios com `meta.correction_id`.
  - **Tratamento de Contradições Causais (Critério C4):** Se uma correção invalida a premissa de um fato posterior não-revertível automaticamente (ex.: o protagonista sobreviveu porque um teste passou, mas a correção altera o teste para falha crítica), o motor **não altera silenciosamente o passado** nem alucina novos resultados.
  - O sistema emite `correction.recomputed` registrando explicitamente a anotação de inconsistência (`inconsistency_detected: true`, lista de eventos afetados), marcando a campanha com pendência de revisão até que o Mestre/Humano emita decisão explícita via CLI.
* **Racional:**
  - Preserva a verdade histórica e impede que simulações automáticas corrompam a lógica dramática já consolidada.

---

## 7. Decisão 7: Motor de Projeções Determinístico, Checkpoints e Auditoria Externa (G2-D4, G2-D10, C3, FR-G2-10)

* **Contexto:** `diario.md`, `ficha.md` e `npcs.md` passam a ser projeções derivadas dos eventos. O `rebuild` deve reconstruí-las do zero ou de snapshots, gerando Markdown idêntico ao produzido no fluxo normal.
* **Decisão:**
  - Os `Projector`s implementam a porta `contracts.ports.Projector` e são organizados por arquivo e ordem (`order`).
  - O `ProjectionWriter` aplica as seções geradas, atualiza atomicamente os arquivos de projeção via arquivo temporário e `os.replace`, e calcula o `projection_hash` (SHA-256 dos conteúdos dos Markdown canônicos).
  - Um checkpoint de projeção armazena `last_seq` e `projection_hash`.
  - **Isolamento do Evento de Auditoria (Critério C3):** O evento `projection.rebuilt` registra a realização do rebuild, o intervalo de sequências (`from_seq`, `to_seq`) e o `projection_hash` verificado. Esse evento é gravado **estritamente após** o cálculo e validação do hash das projeções e **não altera** o hash das projeções verificadas.
  - Reconstruções repetidas sobre o mesmo conjunto de eventos de estado produzem o mesmo hash byte a byte.
* **Racional:**
  - Garante a integridade matemática da projeção sem efeito colateral reflexivo (o observador não altera o estado observado).

---

## 8. Decisão 8: Fila Esqueleto Append-Only e Prosa Imutável (G1-D11, G2-D5, G2-D7)

* **Contexto:** Trabalho assíncrono não concluído precisa de registro e a prosa literária gerada precisa ser perene e recuperável.
* **Decisão:**
  - `queue.jsonl`: Arquivo append-only em `campaigns/<id>/queue.jsonl`. Registra trabalhos com `wrk_<ulid>`, tipo, payload e status `pending`. Finalização ocorre via novo append de registro com status `done` ou `failed` referenciando `work_id`. Nenhuma linha antiga é editada. Orçamento adaptativo e retries automáticos ficam postergados para G4/Fase 05.
  - Prosa Original: Armazenada imutável em `campaigns/<id>/artifacts/prose/turn_{seq:06d}-{hash}.md`. O evento `prose.recorded` referencia apenas o caminho relativo e o hash SHA-256 do texto. Correções de turno nunca reescrevem arquivos de prosa antigos.
* **Racional:**
  - Respeita o princípio append-only universal e mantém o desacoplamento entre armazenamento bruto de texto e metadados de domínio.
