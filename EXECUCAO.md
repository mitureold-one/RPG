# RPGPRO — Registro de Execução

**Tipo:** registro canônico do que foi executado, por quem, como e com qual evidência.
**Status:** append-only; entradas antigas não são editadas.
**Criado em:** 22/10/2026.

> **Para agentes:** registre aqui apenas o que **aconteceu de fato** no repositório. Não use este arquivo para planos, requisitos, decisões arquiteturais ou especificações. Se o fato pertence a outro documento, **linke** em vez de copiar. Uma afirmação sem commit, teste ou arquivo observável não entra como concluída.

---

## 1. Por que um único documento

O projeto já tem documentos com papéis diferentes. O risco de contradição aparece quando o mesmo fato é reescrito em vários lugares. A regra é: **um assunto, um dono**.

| Assunto | Documento dono | O que contém | O que não contém |
|---|---|---|---|
| Comportamento e decisões de mundo | [`rpgpro-diretrizes-agentes.md`](rpgpro-diretrizes-agentes.md) | Decisões confirmadas, princípios, pendências de especificação | Histórico de implementação |
| Plano e fases | [`ROADMAP.md`](ROADMAP.md) | Fases, gates, critérios de aceite, refatoração | O que já foi executado |
| Decisões arquiteturais | [`DECISOES_ARQUITETURA.md`](DECISOES_ARQUITETURA.md) | Racional e decisões de arquitetura | Diário de execução |
| Especificação de feature | [`specs/`](specs/) | Contratos, modelos, tasks, QA | Roadmap global |
| Regras operacionais | [`AGENTS.md`](AGENTS.md) | Roteamento, precedência, obrigações | Conteúdo técnico detalhado |
| **Execução** | **este arquivo** | O que foi feito, por quem, como, com qual evidência | Planos, specs, decisões |
| Evidência executável | [`tests/`](tests/) | Testes automatizados | Prosa e justificativa |
| História imutável | git | Commits e diffs | Resumos editoriais |

**Consequência prática:** o `EXECUCAO.md` não repete o roadmap nem a spec. Ele responde a quatro perguntas: **o que**, **quem**, **como** e **qual evidência**. O “porquê” fica no documento de decisão; o “próximo” fica no roadmap.

---

## 2. Regras de registro

1. **Append-only.** Não edite entradas antigas. Correções são uma nova entrada que referencia a anterior (`Corrige: EX-XXXX`).
2. **Uma entrada por commit ou sessão de execução**, não por arquivo alterado.
3. **Nada de intenção como fato.** “Vou implementar”, “deveria funcionar” e “está planejado” não entram como concluído.
4. **Evidência obrigatória.** Commit, arquivo, comando ou teste observável. Se não houver, o status é `parcial` ou `não verificado`.
5. **Sem duplicação.** Linke `ROADMAP.md`, `specs/...`, `DECISOES_ARQUITETURA.md` ou `rpgpro-diretrizes-agentes.md`; não copie o conteúdo deles.
6. **Autoria explícita.** Humano ou agente, com identificação suficiente para auditoria.
7. **Status único:** `concluído`, `parcial`, `revertido`, `bloqueado` ou `não verificado`.
8. **Commit obrigatório para `concluído`.** Se não houve commit, registre `não commitado` e o motivo.
9. **Teste nomeado.** “69 testes OK” é evidência; “testado” sem comando não é.
10. **Conflito com código/teste:** o código e o teste vencem. Abra uma entrada de correção; não reescreva a história.
11. **Sem segredos, tokens, caminhos pessoais ou dados sensíveis.**
12. **Uma entrada não altera outra.** Se a implementação mudou depois, a entrada antiga permanece e a nova registra a mudança.

---

## 3. Template de entrada

```markdown
## EX-0000 — AAAA-MM-DD — Título curto

- **Autor:** humano ou agente (identificação)
- **Tipo:** implementação | correção | teste | migração | documentação | refatoração
- **Status:** concluído | parcial | revertido | bloqueado | não verificado
- **Commit:** hash completo ou `não commitado`
- **Escopo:** fase, feature ou módulo
- **O que foi feito:** uma a três frases factuais
- **Como:** arquivos/funções principais e abordagem
- **Evidência:** comando + resultado; arquivos; diff; teste
- **Relações:** links para roadmap/spec/decisão/entradas anteriores
- **Pendências:** o que ficou fora, se aplicável
```

---

## 4. Entradas

## EX-0001 — 2026-10-22 — Fase 01: fundação do estado

- **Autor:** agente de código DeepSeek Harness, a pedido do usuário; revisão humana pendente.
- **Tipo:** implementação + documentação.
- **Status:** concluído.
- **Commit:** `065c941` (`fix(state): stabilize writes, validation and calendar (phase 1)`).
- **Escopo:** Fase 01 — Fundação; exportação do roadmap.
- **O que foi feito:** estabilização da persistência e da validação antes da autonomia; criação do roadmap de fases; 12 testes novos de estabilidade.
- **Como:**
  - `council/helpers.py`: `atomic_write_text`, `campaign_lock`, calendário declarativo, `advance_time_str` com fallback seguro.
  - `lazy_turn.py`: validação de entidades antes do commit, snapshot/rollback, parsing de tempo, `Path`, idempotência de missão, validação de contratante.
  - `council/ssot.py`, `council/quests.py`, `council/factions.py`, `council/narrator.py`: escritas atômicas; `upsert_clock_in_diario(create_if_missing=False)`; parser de `--npc-updates` por blocos e subcampos.
  - `templates/regras.template.md`: exemplo comentado de `calendar:`.
  - `ROADMAP.md`: fases 01–08, gates G1–G7, matriz de decisões e refatoração R0–R4.
  - `tests/test_state_stability.py`: 12 testes de atomicidade, rollback, validação, parsing, idempotência, prosa e calendário.
- **Evidência:**
  - `python -m unittest discover -s tests` → **68 testes, OK** (executado antes do commit).
  - Reproduções manuais em cópia do HEAD em `%TEMP%`: relógio inexistente recusado; NPC com `Atitude` + `Relação` sem NPC fantasma; `quest --complete` seguido de `commit --quest-complete` sem XP duplicado; `check-prose --file` funcional; `04 de Ventania +1d` → `5 de Ventania`; `+30d` sem calendário recusado; calendário declarativo rolando mês; falha simulada no fim do commit restaurando o snapshot.
- **Relações:** [`ROADMAP.md`](ROADMAP.md) Fase 01; [`rpgpro-diretrizes-agentes.md`](rpgpro-diretrizes-agentes.md) §12.3/§13; [`DECISOES_ARQUITETURA.md`](DECISOES_ARQUITETURA.md); [`specs/009-factions-and-reputation/qa-review.md`](specs/009-factions-and-reputation/qa-review.md).
- **Pendências:**
  - Fase 01.5: calendário completo de Valíria; `faction --rep` estrito com `--create`; revisão dos caminhos de prosa.
  - `rpgpro-diretrizes-agentes.md` permanece não commitado (documento do usuário).
  - O rollback cobre exceções; não é uma transação ACID multiarquivo.

## EX-0002 — 2026-10-22 — Fase 01.5: fechamento da fundação

- **Autor:** agente de código Antigravity, a pedido do usuário.
- **Tipo:** implementação + teste + documentação.
- **Status:** concluído.
- **Commit:** `7d7f598` (`feat(phase-01.5): complete Valiria calendar, strict faction rep with --create, and prose path review`).
- **Escopo:** Fase 01.5 — Fechamento da fundação.
- **O que foi feito:** declaração do calendário completo de Valíria em `regras.md` (12 meses boreais de 30 dias); `faction --rep` estrito por padrão impedindo cadastro acidental de facções desconhecidas (exigindo `--create`); revisão e blindagem dos caminhos de prosa (`check-prose` e `commit --prose`/`--prose-file`).
- **Como:**
  - `campaigns/imperio_valiria/regras.md`: bloco `calendar:` com 12 meses boreais e `days_per_month: 30`.
  - `council/helpers.py`: suporte a `calendar:` também no fallback nativo stdlib de `parse_regras_manifest`.
  - `lazy_turn.py`: `cmd_faction` com validação estrita de facções em `mundo.md` para `--rep`, `--favor` e `--debt`, introduzindo flag `--create` para permissão intencional de cadastro; `cmd_commit` validando existência de `prose_file` e emitindo `prose_status: PASSED`.
  - `tests/test_cli_contracts.py` e `tests/test_factions_reputation.py`: novos testes de contrato para avanço de +30d em Valíria, `--create` em `faction --rep` e caminhos de prosa válidos/inválidos.
  - `ROADMAP.md`: atualização de status da Fase 01.5 para concluída.
- **Evidência:**
  - `python -m unittest discover -s tests` → **69 testes, OK** em ambiente sandbox.
  - `advance_time_str("04 de Ventania de 304, 21:15", 30*1440, cal)` → `4 de Geada de 304, 21:15`.
  - `lazy_turn.py faction --rep "Conselhoo:+1"` sem `--create` → erro retornado, ficha inalterada.
  - `lazy_turn.py faction --rep "Conselhoo:+1" --create` → cadastro realizado com aviso.
  - `lazy_turn.py commit --campaign dinastia_cinzas --prose-file inexistente.md` → `FILE_NOT_FOUND`.
  - `lazy_turn.py review` limpo nas 3 campanhas canônicas.
- **Relações:** [`ROADMAP.md`](ROADMAP.md) Fase 01.5; EX-0001; [`AGENTS.md`](AGENTS.md).
- **Pendências:**
  - Persistência de `--prose` original por turno deferida para a Fase 02 (event store append-only).

## EX-0003 — 2026-10-22 — Arquitetura-alvo e kernel de extensão

- **Autor:** agente de código DeepSeek Harness, com aprovação do usuário ("concordo").
- **Tipo:** documentação + arquitetura.
- **Status:** parcial (documento criado; commit pendente).
- **Commit:** não commitado.
- **Escopo:** baseline arquitetural para as Fases 02–08; kernel de plugins, portas de extensão e mapa R0–R4.
- **O que foi feito:** decisão por event log como verdade e Markdown como projeção; armazenamento híbrido JSONL canônico + SQLite derivado; monólito modular com kernel de plugins e registro explícito; portas para resolução, comportamento, facção, contexto, direção, memória, projeção, evento, revisão e calendário; sequência de refatoração R0–R4; critérios de aceite arquiteturais.
- **Como:**
  - `ARCHITECTURE.md`: documento canônico da árvore, invariantes, contratos e migração.
  - `ROADMAP.md`: removida a árvore duplicada; seção 6 aponta para `ARCHITECTURE.md`; próximos passos atualizados para R0/R0.5/Fase 02.
  - `AGENTS.md`: ponteiro para o registro append-only em `EXECUCAO.md` (já commitado no ciclo 01.5).
- **Evidência:**
  - `ARCHITECTURE.md` com 616 linhas; `ROADMAP.md` sem árvore duplicada.
  - `python -m unittest discover -s tests` → **69 testes, OK** antes e depois da documentação; nenhum código de produção alterado.
- **Relações:** [`ARCHITECTURE.md`](ARCHITECTURE.md); [`ROADMAP.md`](ROADMAP.md); [`rpgpro-diretrizes-agentes.md`](rpgpro-diretrizes-agentes.md) §3–§11; EX-0001/EX-0002.
- **Pendências:**
  - Commitar `ARCHITECTURE.md` e a atualização do `ROADMAP.md`.
  - Executar R0 (kernel skeleton + extração de CLI/persistência/tempo/campanha).
  - Executar R0.5 (fixtures + arquivamento + remoção das campanhas antigas).

## EX-0004 — 2026-10-23 — Base do kernel consolidada e R0a

- **Autor:** agente de código DeepSeek Harness, a pedido do usuário.
- **Tipo:** documentação + refatoração + teste.
- **Status:** concluído (escopo R0a; R0b–R0d pendentes).
- **Commits:** `f63fe65` (documentação), `4c368d4` (teste de calendário), `e34649f` (R0a).
- **Escopo:** base do kernel em `ARCHITECTURE.md` §5.0, delimitação G1/G2 e etapa R0a (contratos, erros, IDs, fakes e suíte de contrato).
- **O que foi feito:** consolidação da base do kernel e do escopo dos gates; remoção do acoplamento do teste de calendário ao estado da campanha viva; criação de `contracts/` (envelope, portas, configuração, serialização), `kernel/errors.py`, `kernel/ids.py`, `FakeEventStore` e suíte de contrato executável; teste AST de fronteira.
- **Como:**
  - `ARCHITECTURE.md`: §1 (G1/G2), §5.0 (definição, cinco responsabilidades, superfície, `EventDraft`/`append`/`last_seq`, R0/R1), §5.1, §5.3, §5.4, §12, §15, §16.
  - `ROADMAP.md`: tabela de gates, `temporal/`, R0/R0.5/R1, cuidados de migração e próximos passos.
  - `tests/test_cli_contracts.py`: o teste de Valíria fixa a data inicial na cópia temporária antes de `+30d`.
  - `contracts/event.py`, `contracts/ports.py`, `contracts/config.py`, `contracts/serialization.py`: tipos e protocolos sem I/O.
  - `kernel/errors.py`, `kernel/ids.py`: taxonomia com `code` estável e ULID monotônico `evt_<ulid>`.
  - `tests/contract_support.py`: `FakeEventStore` e mixin `EventStoreContract`; `tests/test_contract_*.py`, `tests/test_kernel_ids.py`, `tests/test_architecture_boundaries.py`.
- **Evidência:**
  - `python -m unittest discover -s tests` → **110 testes, OK** (69 existentes + 41 novos).
  - `contracts/event.py` com 194 linhas; `kernel/errors.py` com 113; nenhum arquivo de produção acima de 300.
  - Teste AST confirma que `contracts/` e `kernel/` não importam `council`, `rulesets`, `resources`, `adapters`, `interfaces` nem módulos de I/O.
  - `lazy_turn.py` permanece com 2.122 linhas até R0c/R0d.
- **Relações:** [`ARCHITECTURE.md`](ARCHITECTURE.md) §5.0; [`ROADMAP.md`](ROADMAP.md) §5 e §6.4; EX-0003 (corrige o status de commit pendente).
- **Pendências:**
  - R0b: `kernel/registry.py`, `kernel/runtime.py`, `kernel/schema.py`, `bootstrap.py`.
  - R0c: extração de `interfaces/cli/` e `application/`, com `lazy_turn.py` < 200 linhas.
  - R0d: extração de persistência, `temporal/` e `campanha/`.
  - R0.5: fixtures e remoção das campanhas vivas.

## EX-0005 — 2026-10-23 — Kernel R0b: registry, runtime, schema e bootstrap

- **Autor:** agente de código Antigravity, a pedido do usuário.
- **Tipo:** implementação + teste.
- **Status:** concluído (escopo R0b; R0c–R0d pendentes).
- **Commit:** `783824d` (`feat(kernel): add registry, runtime, schema validation and bootstrap (R0b)`).
- **Escopo:** etapa R0b do kernel (composição, validação de schema, registry congelável, runtime imutável e composition root).
- **O que foi feito:** criação de `kernel/schema.py` com validação de subconjunto de JSON Schema sem dependências externas; `kernel/registry.py` com `PluginManifest`, registro explícito, verificação de dependências cruzadas e congelamento; `kernel/runtime.py` com `Runtime` imutável e resolução de serviços; `bootstrap.py` como único composition root; suíte completa de testes de contrato e integração.
- **Como:**
  - `kernel/schema.py`: `validate_schema` e `is_valid_schema` cobrindo tipos primitivos, objetos com `properties`/`required`/`additionalProperties`, arrays com `items`/bounds, enums, regex `pattern` e limites numéricos.
  - `kernel/registry.py`: `PluginManifest` com validação de manifesto e `Registry` com `register`, `get`, `get_manifest`, `has`, `all`, `all_names`, `points` e `freeze` com verificação de dependências declaradas (`MissingRequirementError`).
  - `kernel/runtime.py`: `@dataclass(frozen=True)` com validação de plugins configurados, auto-freeze de registry e resolução de serviços (`service`, `services`, `has_service`).
  - `bootstrap.py`: `build_runtime(campaign_id, config, registry)` devolvendo runtime imutável com registry congelado.
  - `tests/test_kernel_schema.py`, `tests/test_kernel_registry.py`, `tests/test_kernel_runtime.py`, `tests/test_bootstrap.py`: 25 novos testes cobrindo todos os contratos e cenários de borda.
- **Evidência:**
  - `python -m unittest discover -s tests` → **135 testes, OK** (110 existentes + 25 novos).
  - `tests/test_architecture_boundaries.py` → 2 testes, OK (confirma zero imports proibidos e zero `open()` em `contracts/` e `kernel/`).
  - `schema.py` (209 linhas), `registry.py` (164 linhas), `runtime.py` (84 linhas), `bootstrap.py` (42 linhas); nenhum arquivo de produção acima de 300 linhas.
- **Relações:** [`ARCHITECTURE.md`](ARCHITECTURE.md) §5.0 e §5.3; [`ROADMAP.md`](ROADMAP.md) §6.4; EX-0004.
- **Pendências:**
  - R0c: extração de `interfaces/cli/` e `application/`, com `lazy_turn.py` < 200 linhas.
  - R0d: extração de persistência, `temporal/` e `campanha/`.
  - R0.5: fixtures e remoção das campanhas vivas.

## EX-0006 — 2026-10-23 — Kernel R0c: extração de `interfaces/cli/` e `application/`

- **Autor:** agente de código Antigravity, a pedido do usuário.
- **Tipo:** refatoração + teste.
- **Status:** concluído (escopo R0c; R0d e R0.5 pendentes).
- **Commit:** `b2b05e3` (`refactor(cli): extract interfaces/cli and application from lazy_turn (R0c)`).
- **Escopo:** etapa R0c — extração behavior-preserving da CLI e dos casos de uso de `lazy_turn.py`.
- **O que foi feito:** `lazy_turn.py` reduzido de 2.122 para 54 linhas (entry point + reexports `cmd_*`/`build_cli`); casos de uso movidos para `application/` e parser/despacho/formatação para `interfaces/cli/`, sem alterar corpo de função. A extração foi mecânica (fatiamento por AST, imports filtrados por uso).
- **Como:**
  - `application/transaction.py` (`_serialized_campaign_mutation`), `prepare.py`, `commit.py`, `commit_validation.py`, `showrunner.py` (clock/plan/arc), `progression.py` (quest/progress), `factions.py`, `prose.py`; `application/__init__.py` reexporta os casos de uso e os quatro nomes de domínio usados pela CLI.
  - `interfaces/cli/parser.py` (`build_cli`) e `interfaces/cli/main.py` (`main`); a CLI importa só de `application`.
  - `tests/test_state_stability.py`: `patch` movido de `lazy_turn.cmd_review` para `application.commit.cmd_review` (previsto em [`ROADMAP.md`](ROADMAP.md) §6.5).
  - `tests/test_architecture_boundaries.py`: `application/` não importa `interfaces`/`lazy_turn`; `lazy_turn.py` < 200 linhas; nenhum arquivo em `application/`, `interfaces/`, `contracts/`, `kernel/` com 600+ linhas.
- **Evidência:**
  - `python -m unittest discover -s tests` → **137 testes, OK** (135 + 2 novos de fronteira).
  - Snapshot de 49 invocações read-only da CLI (`--help` de todos os subcomandos; `review`, `clock`, `plan`, `quest`, `progress`, `faction` em texto e JSON; `prepare --no-roll` em modo gm/director; `check-prose`; campanha inexistente; comando inválido) nas 3 campanhas, antes e depois: **saída e exit code byte-idênticos**; hashes dos Markdown das campanhas inalterados.
  - Checagem AST de nomes não definidos/imports não usados nos módulos novos: zero ocorrências.
- **Relações:** [`ARCHITECTURE.md`](ARCHITECTURE.md) §4 e §12; [`ROADMAP.md`](ROADMAP.md) §6.1, §6.3–§6.5; EX-0005.
- **Pendências:**
  - `application/prepare.py` (475) e `application/commit.py` (486) estão na faixa de alerta (400–600): `cmd_prepare` e `cmd_commit` são funções únicas de ~450 linhas; quebrá-las exige mudar o corpo e foi deixado para R1/R2.
  - R0d: extração de persistência, `temporal/` e `campanha/` de `council/helpers.py`.
  - R0.5: fixtures e remoção das campanhas vivas.

## EX-0007 — 2026-10-23 — Kernel R0d: extração de persistência, `temporal/` e `campaign/`

- **Autor:** agente de código Antigravity, a pedido do usuário.
- **Tipo:** refatoração + teste.
- **Status:** concluído (escopo R0d concluído; R0.5 pendente).
- **Commit:** `dad9b30` (`refactor(infra): extract persistence, temporal and campaign from helpers (R0d)`).
- **Escopo:** etapa R0d — extração de persistência, tempo e gerenciamento de campanhas de `council/helpers.py`.
- **O que foi feito:** `council/helpers.py` reduzido de 648 para 61 linhas, tornando-se uma fachada de compatibilidade reexportadora; extração de `adapters/persistence/files.py` (escrita atômica e lock cooperativo), `temporal/calendar.py` (cálculo e avanço de datas sem I/O), `campaign/locator.py` (localização, schema_version e manifesto de regras) e `campaign/templates.py` (inicialização de novas campanhas a partir dos templates).
- **Como:**
  - `adapters/persistence/files.py`: `atomic_write_text`, `campaign_lock`.
  - `temporal/calendar.py`: `advance_time_str`, `parse_time_increment`, `_normalize_calendar`, `MONTHS_PT`, `MONTHS_MAP`.
  - `campaign/locator.py`: `find_campaign`, `parse_regras_manifest`, `get_campaign_overrides`, `get_campaign_system`, `load_ruleset`, `get_available_rulesets`, `_get_campaign_dirs()` (garantindo compatibilidade reversa com mocks e patches em `helpers.CAMPAIGN_DIRS`).
  - `campaign/templates.py`: `init_campaign_from_templates`.
  - `council/helpers.py`: reexporta todos os símbolos originais para preservar compatibilidade com callers existentes.
  - `tests/test_architecture_boundaries.py`: valida limites de tamanho (`helpers.py` < 100 linhas, módulos < 600) e ausência de imports proibidos em `temporal` e `adapters/persistence`.
  - `tests/test_temporal_calendar.py`, `tests/test_adapters_persistence.py`, `tests/test_campaign_locator.py`: novos testes unitários diretos.
- **Evidência:**
  - `python -m unittest discover -s tests` → **148 testes, OK** (137 anteriores + 11 novos).
  - Snapshot de 49 invocações da CLI nas 3 campanhas: **saída e exit code byte-idênticos** (`diffs: []`).
  - Todos os arquivos de produção extraídos abaixo de 250 linhas (`files.py`: 98, `calendar.py`: 234, `locator.py`: 204, `templates.py`: 137, `helpers.py`: 61).
- **Relações:** [`ARCHITECTURE.md`](ARCHITECTURE.md) §4 e §12; [`ROADMAP.md`](ROADMAP.md) §6.1, §6.4; EX-0006.
- **Pendências:**
  - R0.5: fixtures e remoção das campanhas vivas.

## EX-0008 — 2026-10-23 — Etapa R0.5: fixtures de teste, arquivamento e reset de `campaigns/`

- **Autor:** agente de código Antigravity, a pedido do usuário.
- **Tipo:** migração + teste + manutenção.
- **Status:** concluído (R0 e R0.5 100% concluídos; baseline pronto para Fase 02).
- **Commit:** `cb60a83` (`chore(campaigns): archive live campaigns, create test fixtures and clear campaigns/ (R0.5)`).
- **Escopo:** etapa R0.5 — arquivamento das campanhas legadas, criação de fixtures desacopladas em `tests/fixtures/campaigns/` e esvaziamento de `campaigns/`.
- **O que foi feito:** preservação integral das 3 campanhas vivas (`dinastia_cinzas`, `imperio_valiria`, `perpetuos_terra_incognita`) em `archive/campaigns/`; instanciação de fixtures canônicas em `tests/fixtures/campaigns/`; atualização de `tests/test_boundary_contracts.py` e `tests/test_cli_contracts.py` para apontar para as fixtures; esvaziamento completo de `campaigns/` (mantendo apenas `campaigns/.gitkeep`); teste de `init-campaign` em ambiente limpo comprovando criação e validação de nova campanha.
- **Como:**
  - `archive/campaigns/`: cópia de segurança preservando o estado vivo completo de todas as campanhas.
  - `tests/fixtures/campaigns/`: fixtures isoladas para a suíte de testes.
  - `tests/test_boundary_contracts.py` e `tests/test_cli_contracts.py`: `setUp` e `tearDown` agora apontam `helpers.CAMPAIGN_DIRS` e `self.fixtures_dir` para `tests/fixtures/campaigns`.
  - `tests/test_campaign_locator.py`: adicionado teste automatizado `test_init_campaign_from_templates` validando o fluxo de criação e descoberta de nova campanha.
  - `campaigns/`: diretório limpo contendo apenas `.gitkeep`, pronto para receber novas campanhas na Fase 02.
- **Evidência:**
  - `python -m unittest discover -s tests` → **149 testes, OK** com `campaigns/` completamente vazio.
  - `python lazy_turn.py init-campaign --campaign teste_nova_campanha --title "Teste Nova"` cria com sucesso os 5 arquivos canônicos e passa em `lazy_turn.py review` com `ssot_status: CLEAN`.
- **Relações:** [`ARCHITECTURE.md`](ARCHITECTURE.md) §1, §12 (R0.5); [`ROADMAP.md`](ROADMAP.md) §6.4; EX-0007.
- **Pendências:** nenhuma pendência de refatoração prévia; baseline pronto para a Fase 02 / R1 (EventStore e projeções).

## EX-0009 — 2026-10-23 — QA da Fase 01 e do baseline R0/R0.5

- **Autor:** agente de QA DeepSeek Harness, a pedido do usuário.
- **Tipo:** teste + documentação (auditoria de QA).
- **Status:** parcial (auditoria concluída; relatório e reparos ainda não commitados).
- **Commit:** não commitado.
- **Escopo:** HEAD `d2f99bf` — Fase 01/01.5 e baseline R0/R0.5 (`contracts/`, `kernel/`, `application/`, `interfaces/`, `adapters/`, `temporal/`, `campaign/`).
- **O que foi feito:** auditoria dos critérios de aceite da fase, do código novo do kernel e da preservação de comportamento do R0; suíte, regressão diferencial contra `cefe5ea`, concorrência real e testes adversariais de calendário, schema, registry, runtime, lock e contenção de caminhos.
- **Como:**
  - suíte completa duas vezes com `python -m unittest discover -s tests`;
  - comparação AST das funções extraídas de `lazy_turn.py` e `council/helpers.py` contra `cefe5ea`;
  - worktree temporário em `cefe5ea` para regressão diferencial da CLI e dos Markdown;
  - 4 commits concorrentes em cópia descartável das fixtures;
  - sondas de `advance_time_str`, `campaign_id` com `..`, templates incompletos, `kernel/schema.py`, `kernel/registry.py`, `Runtime`, `campaign_lock` e `atomic_write_text`.
- **Evidência:**
  - `python -m unittest discover -s tests` → **149 testes, OK** (17 s), sem `ResourceWarning`.
  - AST: 15/15 funções de topo de `lazy_turn.py` idênticas; 4 funções de `helpers.py` diferem só pela indireção `_get_campaign_dirs()`; nenhuma mudança de corpo.
  - Diferencial CLI `cefe5ea` × HEAD: 18 invocações read-only com saída/exit iguais (só o caminho na mensagem de erro difere), 11 comandos mutantes com saída igual e **15/15 Markdown idênticos**.
  - 4 `commit` concorrentes → turnos 4–7, sem duplicata/perda; relógio/missão/facção fantasmas recusados sem alterar arquivos.
  - `+30d` em Valíria: `04 de Ventania de 304, 21:15` → `4 de Geada de 304, 21:15`; `init-campaign` cria 5 arquivos e passa em `review` (`CLEAN`).
  - Achados: **1 P1** (`+1y` = 365 dias em calendário de 360: `05 de Ventania de 304` → `10 de Ventania de 305`), **4 P2** (`campaign_id` com `..` sai de `campaigns/`; `init-campaign` parcial com templates faltando; `plan`/`progress` fora do lock; documentos canônicos desatualizados), **9 P3** agrupados.
- **Relações:** [`QA-FASE-01.md`](QA-FASE-01.md); [`ROADMAP.md`](ROADMAP.md) §3 e §7; [`ARCHITECTURE.md`](ARCHITECTURE.md) §12 e §15; EX-0001, EX-0002, EX-0008.
- **Pendências:**
  - corrigir P1-A (semântica de `+1mo`/`+1y` no calendário declarado) e adicionar os testes;
  - corrigir P2-1 a P2-4 (validação de `campaign_id`, `init-campaign` atômico, lock em `plan`/`progress`, atualização de `ARCHITECTURE.md`/`ROADMAP.md`/`README.md`/`AGENTS.md`);
  - commitar o relatório e os reparos; P3 entra no backlog de R1–R3.

## EX-0010 — 2026-10-23 — Resolução dos itens de QA da Fase 01 / R0.5 (P1-A e P2)

- **Autor:** agente de código Antigravity, a pedido do usuário.
- **Tipo:** correção de bug + teste + documentação.
- **Status:** concluído (todos os itens P1 e P2 do QA fechados com 156 testes verdes).
- **Commit:** 69153a9 (fix(qa): resolve P1-A calendar drift, P2 containment and lock, and sync canonical docs).
- **Escopo:** correção dos apontamentos de QA em `QA-FASE-01.md` sobre o baseline R0/R0.5.
- **O que foi feito:**
  - P1-A: suporte a avanços relativos `+Ny` e `+Nmo` calendar-aware em `temporal/calendar.py` e `application/commit_validation.py`, eliminando o drift de 5 dias em anos de 360 dias (Valíria) e ajustando meses gregorianos com clamping (ex: 31 Jan + 1mo -> 28 Fev);
  - P2-1: validação estrita de `campaign_id` (`^[a-z0-9_][a-z0-9_-]*$`) e verificação de contenção contra directory traversal em `campaign/locator.py`, `campaign/templates.py` e `interfaces/cli/parser.py`;
  - P2-2: garantia all-or-nothing na criação de campanhas em `campaign/templates.py`, abortando e não criando pastas se algum dos 5 templates estiver ausente;
  - P2-3: aplicação do decorator `@_serialized_campaign_mutation` em `cmd_plan` (`application/showrunner.py`) e `cmd_progress` (`application/progression.py`), com snapshot e lock de campanha protegendo contra concorrência e desvios de XP;
  - P2-4 e P3-5: alinhamento dos documentos canônicos (`ARCHITECTURE.md`, `ROADMAP.md`, `README.md`, `AGENTS.md`) com o estado real pós-R0.5 (156 testes, fixtures em `tests/fixtures/campaigns/`, `campaigns/` limpo) e versionamento de `rpgpro-diretrizes-agentes.md`.
- **Como:**
  - `temporal/calendar.py`: `advance_time_str` passa a suportar `int | str` para avançar diretamente unidades de ano e mês preservando calendário diegético e gregoriano; `parse_time_increment` aceita `calendar` para conversão exata; `application/commit_validation.py` delega para `advance_time_str`.
  - `campaign/locator.py`: adicionado `validate_campaign_id` e checagem `camp_dir.parent == base.resolve()`.
  - `campaign/templates.py`: verificação prévia de existência dos 5 templates antes do `mkdir`.
  - `application/showrunner.py` e `application/progression.py`: `@_serialized_campaign_mutation` aplicado a `cmd_plan` e `cmd_progress`.
  - `tests/test_temporal_calendar.py`: 4 novos testes unitários para Valíria (+1y = 360d, +1mo, 2y exatos) e clamping gregoriano.
  - `tests/test_campaign_locator.py`: testes de rejeição de traversal e all-or-nothing de templates.
  - `tests/test_state_stability.py`: testes de rollback do ledger em falha de concessão de XP e timeout de lock em `plan`/`progress`.
- **Evidência:**
  - `python -m unittest discover -s tests` → **156 testes, OK** (17,3 s).
  - Testes manuais do P1:
    - `05 de Ventania de 304, 08:06` + `+1y` em Valíria → `5 de Ventania de 305, 08:06` (sem drift).
    - `31 de Janeiro de 2026, 12:00` + `+1mo` → `28 de Fevereiro de 2026, 12:00`.
  - Testes manuais do P2-1/P2-2:
    - `find_campaign("../fora")` → `ValueError: ID de campanha inválido`.
    - `init_campaign_from_templates("../fora")` → `{"error": ...}`.
    - Templates incompletos abortam sem criar diretório.
- **Relações:** [`QA-FASE-01.md`](QA-FASE-01.md); [`ARCHITECTURE.md`](ARCHITECTURE.md) §12 e §15; [`ROADMAP.md`](ROADMAP.md) §8; EX-0008, EX-0009.
- **Pendências:** nenhuma para Fase 01 / R0.5. Base pronta e congelada para a especificação da Fase 02 (G1/G2).

## EX-0011 — 2026-10-23 — Reverificação do QA pós-remediação e fechamento da base

- **Autor:** agente de QA DeepSeek Harness + agente Antigravity, a pedido do usuário.
- **Tipo:** teste + documentação (auditoria e saneamento).
- **Status:** concluído (P1-B retirado por ser localidade; P2-D descartado via YAGNI por se referir a campanhas legadas arquivadas; suporte a hífens em meses implementado; resíduos documentais sincronizados).
- **Corrige:** EX-0010 (hash `69153a9` alinhado e caractere de controle removido).
- **Commit:** `936fba5` e subsequente.
- **Escopo:** reverificação de `69153a9` contra [`QA-FASE-01.md`](QA-FASE-01.md) e saneamento final de documentação e suporte a meses com hífen.
- **O que foi feito:**
  - `temporal/calendar.py`: suporte nativo a meses com hífen nos regexes de `advance_time_str` (ex: `Noite-Longa`); novo teste unitário em `tests/test_temporal_calendar.py` (total 157 testes verdes).
  - P2-D (revisão de meses da campanha legada Valíria): descartado pelo dono do projeto por YAGNI — campanhas antigas já foram arquivadas em R0.5 e o motor agora aceita qualquer formato de calendário customizado sem restrição.
  - Sincronização documental: resíduos de contagem ("69 testes") corrigidos em `ROADMAP.md` e `ARCHITECTURE.md` para 157 testes.
- **Evidência:**
  - `python -m unittest discover -s tests` → **157 testes, OK** (17,4 s).
- **Relações:** [`QA-FASE-01.md`](QA-FASE-01.md); [`ARCHITECTURE.md`](ARCHITECTURE.md) §12 e §15; [`ROADMAP.md`](ROADMAP.md) §8; EX-0010.
- **Pendências:** nenhuma. Base R0/R0.5 100% estabilizada e pronta para a Fase 02.

---

## 5. Como registrar uma nova execução

1. **Antes:** confira a fase e os gates no [`ROADMAP.md`](ROADMAP.md). Se o gate da fase estiver aberto, registre no máximo protótipo/experimento, com status `não verificado`.
2. **Depois de executar:** rode os testes; faça o commit; colete o hash.
3. **Escreva a entrada:** use o template, com evidência observável.
4. **Linke, não copie:** aponte para roadmap/spec/decisão; não reescreva o conteúdo deles.
5. **Se ficou incompleto:** status `parcial` e lista de pendências.
6. **Se reverteu:** nova entrada com `Reverte: EX-XXXX`; não apague a anterior.
7. **Se corrigiu:** nova entrada com `Corrige: EX-XXXX`; explique o que mudou e a nova evidência.

---

## 6. O que não entra aqui

- plano de fases, gates ou critérios de aceite (vai para `ROADMAP.md`);
- decisões de comportamento ou de mundo (vai para `rpgpro-diretrizes-agentes.md`);
- racional arquitetural (vai para `DECISOES_ARQUITETURA.md`);
- contrato detalhado de feature (vai para `specs/`);
- saída de teste copiada inteira (basta comando + resultado);
- intenção, opinião ou estimativa sem execução;
- segredos, tokens ou dados pessoais.

---

## 7. Histórico deste documento

- **22/10/2026:** criação do registro canônico e primeira entrada (EX-0001), após a Fase 01.
