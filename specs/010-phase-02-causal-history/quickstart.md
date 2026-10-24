# Quickstart & Verification Guide: 010 — Fase 02: História Causal & Refatoração R1

**Feature:** `phase-02-causal-history`  
**Status:** Ready for Verification  
**Created:** 2026-10-24  
**Context:** Guia executável passo a passo para validação dos 11 cenários de aceite e dos quatro critérios complementares C1–C4 do R1/Fase 02.

---

## 1. Pré-Requisitos e Baseline

Antes de iniciar qualquer validação de código ou migração do R1, certifique-se de que a suíte base de 157 testes está totalmente verde:

```bash
python -m unittest discover -s tests
```
*Critério de Aceite:* 157 testes executados com status `OK`.

---

## 2. Cenários de Validação Prática do R1

Para validar as garantias de persistência, projeção e correção sem afetar campanhas em andamento, todas as validações devem utilizar uma campanha isolada de teste:

```bash
python lazy_turn.py init-campaign --campaign _qa_causal_r1 --title "Crônica de Teste Causal" --protagonist "Aemon"
```

---

### Cenário 1: Evento Ida-e-Volta (FR-G1-01, FR-G1-06)
**Objetivo:** Persistir rascunhos de eventos e lê-los de volta preservando identidade, sequência contígua e timestamps UTC.
1. Executar criação da campanha e emissão de lote inicial via Python/CLI.
2. Ler eventos via `store.read("_qa_causal_r1")`.
3. **Verificação:**
   - Eventos retornam com IDs `evt_<ulid>`, `seq` monotônicos (1, 2, ...), `recorded_at` em formato UTC (`Z`).
   - `last_seq` coincide com o `seq` do último evento do stream.

---

### Cenário 2: Lote Atômico sob Crash & Recuperação Automática (Critério C1, FR-G1-09)
**Objetivo:** Simular interrupção abrupta de escrita em três pontos críticos e comprovar que nenhum leitor observa lotes parciais e que o store trunca caudas órfãs.
1. Interrupção A: Após gravar `batch.open` e 2 de 3 eventos, sem gravar `batch.committed`.
   - Ler com `store.read()`: nenhum evento do lote incompleto é retornado; `last_seq` permanece no estado anterior.
2. Iniciar nova gravação de lote válido via `store.append()`:
   - **Verificação:** O store detecta o marcador `batch.open` pendente, trunca o arquivo até o último `batch.committed` prévio e grava o novo lote.
   - Nenhuma linha órfã ou buraco na numeração de `seq` é criado.

---

### Cenário 3: Reconstrução de Projeção Byte-Idêntica (FR-G2-04, FR-G2-05)
**Objetivo:** Reconstruir `diario.md`, `ficha.md` e `npcs.md` exclusivamente a partir do stream de eventos.
1. Apagar os arquivos gerados em `campaigns/_qa_causal_r1/projections/`.
2. Executar o rebuild do motor:
   ```bash
   python lazy_turn.py rebuild --campaign _qa_causal_r1
   ```
3. **Verificação:**
   - Os arquivos Markdown são recriados.
   - O hash SHA-256 de cada arquivo é byte-idêntico ao gerado durante a execução normal.
   - Nenhum XP, relógio narrativo ou missão é duplicado no processo.

---

### Cenário 4: Correção Seletiva e Reavaliação de Dependentes (FR-G2-01, FR-G2-03)
**Objetivo:** Corrigir concessão indevida de XP sem alterar o passado ou afetar projeções não relacionadas.
1. Emitir uma correção para o evento de concessão de XP:
   ```bash
   python lazy_turn.py correct --campaign _qa_causal_r1 --event <evt_id_xp> --reason "XP duplicado" --delta-xp -100
   ```
2. **Verificação:**
   - O evento original continua no JSONL; um novo evento `correction.issued` e um evento compensatório `protagonist.progression_changed` são persistidos.
   - As projeções de `npcs.md` e os relógios permanecem byte-idênticos; apenas o saldo de XP em `ficha.md` é atualizado.

---

### Cenário 5: Prosa Original Recuperável & Hash Auditável (FR-G2-06)
**Objetivo:** Garantir a persistência e imutabilidade do texto literário narrado.
1. Ao realizar um turno, verificar a gravação em `campaigns/_qa_causal_r1/artifacts/prose/turn_000001-<hash>.md`.
2. Verificar que o evento `prose.recorded` contém o `text_path` e `text_hash` exatos.
3. Emitir correção sobre o turno.
4. **Verificação:** O arquivo de prosa original permanece inalterado em disco; uma anotação é adicionada ao diário.

---

### Cenário 6: Retomada Idempotente sem Duplicação (FR-G2-07)
**Objetivo:** Provar que reenvio de lote ou retomada após interrupção antes da projeção é idempotente.
1. Persistir lote atômico com sucesso no JSONL, simulando falha antes de gravar as projeções.
2. Ao religar o sistema, executar ciclo de avanço ou reaplicar lote:
   - **Verificação:** O store rejeita duplicatas com `DuplicateBatchError` e os projectors aplicam o checkpoint pendente sem duplicar linhas.

---

### Cenário 7: Versionamento de Schema e Upcasters (FR-G1-07)
**Objetivo:** Ler evento com versão antiga aplicando upcaster determinístico e rejeitar versão futura.
1. Injetar evento de teste com `schema_version: 1` para um tipo com versão corrente 2.
2. Ler via store: o upcaster $1 \to 2$ converte o payload na versão atual.
3. Injetar evento fictício com `schema_version: 99`:
   - **Verificação:** Leitura falha imediatamente com `SchemaError`.

---

### Cenário 8: Segmentação de Arquivos e Snapshots Periódicos (FR-G1-08)
**Objetivo:** Validar a criação de múltiplos segmentos e recuperação a partir de snapshot.
1. Gravar eventos até exceder o limite de 1.000 eventos ou 1 MB.
2. Verificar abertura automática de `events/000002.jsonl`.
3. Gerar snapshot em `snapshots/000500.json`.
4. Executar rebuild a partir do snapshot:
   - **Verificação:** O rebuild carrega o snapshot e aplica apenas os eventos com `seq > 500`.

---

### Cenário 9: Validação de Dependências Intra-Lote (Critério C2, FR-G2-09)
**Objetivo:** Submeter lote onde eventos dependem de eventos que os antecedem no mesmo lote.
1. Criar lote contendo `[draft_1 (turn.proposed), draft_2 (action.resolved dep draft_1), draft_3 (turn.committed dep draft_2)]`.
2. Submeter via `store.append()`:
   - **Verificação:** Lote é aceito e validado com sucesso.
3. Criar lote onde `draft_1` tenta referenciar `draft_2` (dependência para frente):
   - **Verificação:** Store rejeita com `DependencyError`.

---

### Cenário 10: Auditoria de Rebuild sem Autoinfluência (Critério C3, FR-G2-10)
**Objetivo:** Comprovar que `projection.rebuilt` não altera o hash das projeções que auditou.
1. Executar `rebuild_projections()`.
2. Coletar o `projection_hash` verificado dos arquivos em disco.
3. O serviço emite o evento `projection.rebuilt` no event log contendo esse hash.
4. Recalcular o hash das projeções em disco:
   - **Verificação:** O hash dos arquivos Markdown permanece idêntico; a emissão do evento de auditoria no store não altera os arquivos de projeção.

---

### Cenário 11: Correção Contraditória com Registro de Inconsistência (Critério C4, FR-G2-11)
**Objetivo:** Submeter correção que invalida um fato posterior irreversível e validar o isolamento histórico.
1. Submeter correção que torna nula a vitória de um combate de 3 turnos atrás.
2. **Verificação:**
   - O motor não reescreve os turnos posteriores nem recalcula narrativas.
   - Emite evento com `inconsistency_detected: true` e lista dos IDs afetados.
   - O comando `lazy_turn.py review` acusa a pendência de intervenção humana até que uma decisão explícita seja homologada.
