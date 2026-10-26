# Quickstart & Validation Guide: 011 — Fechamento dos 5 Achados P2 do QA da Fase 02/R1

**Feature**: `close-phase02-qa-p2`  
**Status**: Verified — 211 testes; P2-1 a P2-5 e P1-C validados em 26/10/2026.
**Created**: 2026-10-26

---

## 1. Pré-requisitos
- Python 3.11+ (100% Standard Library, sem dependências externas).
- Diretório de trabalho na raiz do repositório (`c:\Users\Konor\Documents\RPGPRO`).

---

## 2. Cenários Executáveis de Validação dos 5 P2

### Cenário P2-1: Perda de `diario.md` e Recuperação via `rebuild`
```powershell
$env:RPGPRO_CAMPAIGNS_DIR = "$env:TEMP\qa_p2_verify\campaigns"
python lazy_turn.py init-campaign --campaign qa_p2 --title "Crônica P2"
python lazy_turn.py clock --campaign qa_p2 --add "Cerco" --max 4 --trigger "Queda do portão"
python lazy_turn.py commit --campaign qa_p2 --summary "O vigia avista tochas na colina." --time +1h --clock-advance "Cerco:1"

# Remover diario.md da raiz e reconstruir a partir de events/
Remove-Item "$env:RPGPRO_CAMPAIGNS_DIR\qa_p2\diario.md"
python lazy_turn.py rebuild --campaign qa_p2 --json
python lazy_turn.py review --campaign qa_p2
```
**Resultado Esperado**:
- `rebuild` localiza `qa_p2` via `events/`, recria `diario.md` byte-idêntico a `projections/diario.md`, e `review` retorna `ssot_status: CLEAN`.

### Cenário P2-2: Verificação de Zero Snapshots `*_after` no Event Log
```powershell
python -c "
import os, json, pathlib
ev_dir = pathlib.Path(os.environ['RPGPRO_CAMPAIGNS_DIR']) / 'qa_p2' / 'events'
for seg in ev_dir.glob('*.jsonl'):
    for line in seg.read_text(encoding='utf-8').splitlines():
        obj = json.loads(line)
        if obj.get('record') == 'event':
            meta = obj.get('meta') or {}
            assert not any(k in meta for k in ('diario_after', 'ficha_after', 'npcs_after')), f'Blob encontrado em {obj}'
print('OK: Zero snapshots *_after em meta!')
"
```
**Resultado Esperado**:
- Nenhum evento possui `diario_after`, `ficha_after` ou `npcs_after`, e `rebuild --force` mantém raiz == `projections/` byte a byte.

### Cenário P2-3: Compensação Causal de Relógio, Missão e Arco com Reprojeção Imediata
```powershell
python lazy_turn.py quest --campaign qa_p2 --add "Defender o Portão" --type main --objective "Trancar as comportas"
python lazy_turn.py quest --campaign qa_p2 --fail Q1 --reason "Erro de comando"
# Corrigir relógio, missão e fase do arco
python lazy_turn.py correct --campaign qa_p2 --event evt_... --reason "Retificação de arbitragem" --clock "Cerco:-1" --quest "Q1:ACTIVE" --arc-stage "Preparação" --json
```
**Resultado Esperado**:
- O relógio `Cerco` volta para `0/4 [ACTIVE]`, a missão `Q1` volta para `Status: ACTIVE` e a fase do arco passa para `Preparação` imediatamente em `diario.md` e `projections/diario.md`.

### Cenário P2-4 e P2-5: Fronteiras Arquiteturais e Suíte Completa
```powershell
python -m unittest tests.test_architecture_boundaries -v
python -m unittest discover -s tests -p "test_*.py"
```
**Resultado Esperado**:
- Todos os testes (incluindo os novos testes de P2-1 a P2-4) passam com `OK`, e `application/commit.py`, `adapters/persistence/event_store.py` e `council/reviewer.py` possuem menos de 300 linhas cada.
