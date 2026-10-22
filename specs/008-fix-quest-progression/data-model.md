# Data Model: 008 — Remediação de Integridade: Missões & Progressão

**Feature**: `fix-quest-progression`  
**Status**: Ready for Implementation  
**Created**: 2026-10-22  
**Context**: Modelo de dados formalizado para cabeçalho monotônico de missões, máquina de estados completa e ledger de auditoria de experiência.

---

## 1. Estrutura Textual da Missão em `diario.md`

### 1.1 Sintaxe do Cabeçalho Canônico Monotônico
Toda missão gravada em `diario.md` sob a seção `### Missões & Objetivos` segue obrigatoriamente a sintaxe:

```markdown
* **[{ID}] [{TYPE}] {Title}** | Fase: {Fase} | Status: {Status} | Contratante: {Contratante} | Relógio: {Relógio} | Recompensa: {Recompensa} | Último Progresso: {Último Progresso} | XP Pago: {XP Pago}
```

#### Campos do Cabeçalho:
| Campo | Tipo / Formato | Obrigatório | Descrição / Regra |
| :--- | :--- | :--- | :--- |
| **`ID`** | String monotônica `Q{N}` ($N \ge 1$) | **Sim** | Identificador permanente. Calculado como $\max(N) + 1$. Imutável. |
| **`TYPE`** | Enum (`MAIN`, `SIDE`, `PERSONAL`, `FACTION`) | **Sim** | Classificação da missão. Define recompensa padrão (150, 60, 50, 50 XP). |
| **`Title`** | String livre | **Sim** | Nome diegético da missão. |
| **`Fase`** | String livre | Não | Estágio narrativo (ex: `Início`, `Investigação`, `Clímax`). |
| **`Status`** | Enum (`ACTIVE`, `BLOCKED`, `COMPLETED`, `FAILED`, `ABANDONED`) | **Sim** | Estado corrente na máquina de estados da missão. |
| **`Contratante`**| String livre | Não | Nome do NPC, facção ou entidade contratante. |
| **`Relógio`** | String livre | Não | Nome do relógio de ameaça vinculado em `diario.md`. |
| **`Recompensa`** | String (ex: `150 XP` ou `150 XP + Espada`) | Não | Descrição do ganho ao concluir. |
| **`Último Progresso`**| String (ex: `Turno 12`) | Não | Turno no qual ocorreu o último avanço ou alteração. |
| **`XP Pago`** | Inteiro ($N \ge 0$) | Condicional | Presente apenas se a recompensa em XP já foi creditada na ficha. Impede duplicidade. |

### 1.2 Sub-elementos da Missão
Abaixo do cabeçalho da missão, são permitidos sub-bullets com indentação de 2 a 4 espaços:

```markdown
* **[Q1] [MAIN] O Trono de Pedra-Negra** | Status: ACTIVE | Recompensa: 150 XP | Último Progresso: Turno 3
  * [x] Interrogar o mensageiro capturado
  * [ ] Descobrir o paradeiro do selo real
  * [ ] Confrontar o traidor no conselho
  * **Evidência:** Confissão obtida por escrito pelo mensageiro antes de sua fuga.
```

- **Objetivos**: Linhas iniciando com `* [ ] ` (pendente) ou `* [x] ` (concluído). A contagem e índice são baseados em 1 (`Q1:1`, `Q1:2`).
- **Evidência**: Linha informativa `* **Evidência:** {texto}` anexada na conclusão ou fracasso de missão com documentação diegética.

---

## 2. Máquina de Estados de Missões

### 2.1 Diagrama de Transição de Estados
```text
           ┌──────────┐
           │ (Criação)│
           └────┬─────┘
                │ add
                ▼
          ┌───────────┐
     ┌───►│  ACTIVE   │◄──────────────┐
     │    └─┬───────┬─┘               │
     │      │       │                 │
unblock     │block  │abandon / fail   │reopen
     │      │       │                 │
     │    ┌─▼───────┴─┐               │
     └───┤  BLOCKED  ├──────────┐     │
          └───┬───────┘          │     │
              │                  │     │
              │abandon / fail    │     │
              ▼                  │     │
       ┌─────────────┐           │     │
       │  ABANDONED  │           │     │
       └─────────────┘           ▼     │
              ▲            ┌───────────┴─┐
              │            │  COMPLETED  │
              └────────────┤     ou      ├─┘
                           │   FAILED    │
                           └─────────────┘
```

### 2.2 Transições e Ações da CLI:
| Estado Inicial | Ação / Comando | Estado Final | Efeito Mecânico / Auditoria |
| :--- | :--- | :--- | :--- |
| *(novo)* | `quest --add` | `ACTIVE` | Gera ID `Q{max(N)+1}` no final da seção. |
| `ACTIVE` | `quest --check` ou `--quest-progress` | `ACTIVE` | Marca `[x]`, concede XP de objetivo (+40 ou +15 XP) e atualiza `Último Progresso`. |
| `ACTIVE` | `quest --block --reason "..."` | `BLOCKED` | Congela avanço; registra motivo. |
| `BLOCKED` | `quest --unblock` | `ACTIVE` | Restaura elegibilidade a progresso e conclusão. |
| `ACTIVE` / `BLOCKED` | `quest --abandon --reason "..."` | `ABANDONED` | Encerra missão sem recompensa; documenta desistência/impossibilidade. |
| `ACTIVE` | `quest --complete` ou `--quest-complete` | `COMPLETED` | Carimba `XP Pago: <val>`, credita XP da missão na ficha, anexa `--evidence` se fornecida. |
| `ACTIVE` | `quest --fail` ou `--quest-fail` | `FAILED` | Registra falha e motivo diegético. Sem XP. |
| `COMPLETED` / `FAILED` | `quest --reopen` | `ACTIVE` | Reversão manual excepcional pelo mestre. |

---

## 3. Modelo do Ledger de Experiência em `diario.md`

Para permitir a auditoria bidirecional rigorosa (`XP_MISMATCH`) sem criação de arquivos auxiliares fora dos 5 SSOT, os créditos de XP concedidos fora de missões diretas (ou como histórico transparente) são registrados na subseção `### Registro de Experiência` em `diario.md`:

```markdown
### Registro de Experiência
* **[XP] +50 XP** (Superação de emboscada na floresta) | Turno 3
* **[XP] +40 XP** (Relógio 'Conspiração' resolvido) | Turno 4
```

### Regra de Reconciliação do Reviewer (`XP_MISMATCH`):
$$\text{XP Auditável} = \sum (\text{XP Pago de Missões}) + \sum (\text{XP de Objetivos Concluídos}) + \sum (\text{XP do Registro de Experiência})$$

Se $\text{XP Auditável} > 0$ e $\text{XP Total na Ficha} \ne \text{XP Auditável}$:
- O linter `XP_MISMATCH` emite issue `HIGH` detalhando a diferença exata.

---

## 4. Invariantes de Dados & Integridade

1. **Monotonicidade de IDs**: Uma vez que uma missão é nomeada `Q3`, ela nunca será renomeada para `Q1` ou `Q2`, mesmo que `Q1` seja deletada.
2. **Imutabilidade de XP Pago**: Uma vez que o cabeçalho contenha `XP Pago: N`, nenhuma chamada subsequente a `--quest-complete` ou recálculo concederá pontos adicionais. Qualquer tentativa emite issue `CRITICAL`.
3. **Escrita Atômica**: Qualquer operação em `council/quests.py` ou `lazy_turn.py progress` lê o arquivo, processa em memória e realiza no máximo uma gravação única no disco.
