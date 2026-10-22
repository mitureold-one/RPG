# Interface Contracts: 008 — Remediação de Integridade (Missões & Progressão)

**Feature**: `fix-quest-progression`  
**Status**: Ready for Implementation  
**Created**: 2026-10-22  
**Context**: Contratos de interface CLI, esquemas de entrada/saída JSON e assinaturas de funções centrais.

---

## 1. Contratos CLI: `lazy_turn.py quest`

### 1.1 Adicionar Missão (`--add`)
```bash
python lazy_turn.py quest --campaign <id> --add "<Título>" [--type main|side|personal|faction] [--objective "<Objetivo Inicial>"] [--contractor "<NPC>"] [--clock "<Relógio>"] [--reward "<XP / Item>"] [--phase "<Fase>"]
```
* **Comportamento**:
  - Calcula o próximo ID monotônico $Q(\max(N) + 1)$.
  - Anexa a nova missão no **final** da seção `### Missões & Objetivos` em `diario.md`.
  - Retorna JSON ou texto confirmando a adição com o `quest_id` gerado.

### 1.2 Gerenciamento de Ciclo de Vida (`--unblock`, `--abandon`, `--complete`, `--fail`)
```bash
# Desbloquear missão travada
python lazy_turn.py quest --campaign <id> --unblock "<QID>"

# Abandonar missão com motivo opcional
python lazy_turn.py quest --campaign <id> --abandon "<QID>" [--reason "<Justificativa>"]

# Concluir com evidência diegética
python lazy_turn.py quest --campaign <id> --complete "<QID>" [--evidence "<Texto da Evidência>"]

# Declarar fracasso com motivo
python lazy_turn.py quest --campaign <id> --fail "<QID>" [--reason "<Motivo da Falha>"]
```

### 1.3 Saída JSON (`--json`)
Ao passar a flag `--json`, o retorno deve obedecer ao esquema:
```json
{
  "action": "quest_added|quest_completed|quest_failed|quest_blocked|quest_unblocked|quest_abandoned|objective_checked|objective_added",
  "quest_id": "Q1",
  "status": "ACTIVE|BLOCKED|COMPLETED|FAILED|ABANDONED",
  "title": "Título da Missão",
  "details": "Mensagem descritiva ou evidência anexada"
}
```

---

## 2. Contratos CLI: `lazy_turn.py commit`

### 2.1 Flags de Missão no Commit
```bash
python lazy_turn.py commit --campaign <id> --summary "<Resumo>" \
  [--quest-progress "<QID>:<IDX>[|<QID>:<IDX>]"] \
  [--quest-complete "<QID>[|<QID>]"] \
  [--quest-fail "<QID>[:<MOTIVO>]"]
```

* **Garantia de Execução (P0-1)**:
  - O cálculo `next_turn` é executado antes do bloco de missões.
  - O crédito de XP é aplicado em `ficha.md`.
  - Os vitais expandidos em caso de level-up são capturados no `vitals_snapshot` arquivado no turno.
  - A tentativa de pagar missão já carimbada com `XP Pago` aborta a concessão e emite aviso/issue `CRITICAL`.

---

## 3. Contratos CLI: `lazy_turn.py progress`

### 3.1 Concessão Direta de XP com Ledger (`--award`)
```bash
python lazy_turn.py progress --campaign <id> --award <QUANTIDADE> [--reason "<Motivo diegético>"]
```
* **Comportamento**:
  - Credita `<QUANTIDADE>` XP em `ficha.md` recalculando nível e pontos de atributo/habilidade.
  - Grava atomicamente uma entrada de auditoria na subseção `### Registro de Experiência` em `diario.md`:
    `* **[XP] +<QUANTIDADE> XP** (<Motivo>) | Turno <T>`

---

## 4. Assinaturas de Funções Python Internas

### 4.1 `council/quests.py`
```python
def format_quest_header(quest: Dict[str, Any]) -> str:
    """Retorna '* **[{id}] [{type}] {title}** | Fase: ... | Status: ...' garantindo ID explícito."""

def parse_quests_from_diario(diario_path: Path) -> List[Dict[str, Any]]:
    """Extrai missões com suporte a ID explícito [Q{N}] e fallback sequencial."""

def upsert_quest_in_diario(
    diario_path: Path,
    action: str,
    quest_id: Optional[str] = None,
    title: str = "",
    quest_type: str = "main",
    phase: str = "",
    contractor: str = "",
    clock: str = "",
    reward: str = "",
    objective: str = "",
    check_index: Optional[int] = None,
    reason: str = "",
    evidence: str = "",
    xp_paid: Optional[int] = None,
    current_turn: Optional[int] = None,
) -> Dict[str, Any]:
    """Realiza operações atômicas no diário com uma única escrita em disco."""
```

### 4.2 `rulesets/progression.py`
```python
def calculate_level_from_xp(total_xp: int, base_step: int = DEFAULT_BASE_STEP) -> Tuple[int, int]:
    """Retorna (current_level, next_threshold) garantindo base_step = max(1, base_step)."""

DEFAULT_QUEST_REWARDS: Dict[str, int] = {
    "MAIN": 150,
    "SIDE": 60,
    "PERSONAL": 50,
    "FACTION": 50,
}
```

### 4.3 `council/reviewer.py`
```python
def audit_campaign_integrity(campaign_id: str) -> Dict[str, Any]:
    """Audita os 5 arquivos SSOT incluindo reconciliação bidirecional em XP_MISMATCH e checagem de QUEST_REWARD_PAID_TWICE."""
```
