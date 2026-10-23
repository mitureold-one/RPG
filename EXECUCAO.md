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
