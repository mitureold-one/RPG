# Data Model: 009 — Sistema de Facções, Reputação Numérica e Turno de Mundo Off-Screen

**Feature**: `factions-and-reputation`  
**Status**: Completed  
**Created**: 2026-10-22  
**Context**: Esquema de entidades, formatos em Markdown e regras de transição de estado da Fase 3.

---

## 1. Entidades de Domínio

### 1.1 `Faction` (Declaração em `mundo.md`)
Representa uma organização, ordem de cavalaria, guilda, corte ou força autônoma do cenário.

* **Arquivo Dono**: `mundo.md`
* **Seção**: `## 4. Facções, Forças Ativas & Alianças`
* **Campos**:
  * `tag` (`str`, obrigatório): Identificador único em caixa alta (ex.: `CONSELHO_LORDES`, `GUARDA_MEIA_NOITE`).
  * `name` (`str`, obrigatório): Nome legível e diegético da facção.
  * `description` (`str`, opcional): Filosofia, interesses, estrutura e poder militar/político.
  * `power` (`int`, obrigatório, 1 a 5, padrão 3): Capacidade da facção de impor sua vontade e avançar projetos autônomos.
  * `scale` (`str`, obrigatório, valores: `local`, `regional`, `continental`, `global`, padrão `regional`): Raio de influência geográfica e diplomática.
  * `clock` (`str`, opcional): Nome do relógio de ameaça ou projeto ativo em `diario.md` associado à facção.
  * `rivals` (`list[str]`, opcional): Lista de facções rivais diretas.

#### Formato Markdown Canônico em `mundo.md`:
```markdown
## 4. Facções, Forças Ativas & Alianças

* **[CONSELHO_LORDES] Conselho dos Lordes de Cinzas:** Nobres tradicionalistas que exigem a coroação de Aemon e a manutenção dos privilégios senhoriais. | Poder: 4 | Escala: Regional | Relógio: Conspiração da Corte
* **[GUARDA_MEIA_NOITE] A Guarda da Meia-Noite:** Tropa veterana de elite liderada por Lorde Malakor. | Poder: 3 | Escala: Local | Relógio: Golpe da Guarda de Malakor

### Dinâmica Inter-Facções & Disputas
* **Conselho vs Guarda:** Disputa armada clandestina pelo controle dos portões da fortaleza antes que os sinos fúnebres dobrem.
```

---

### 1.2 `FactionReputation` (Vínculo do Protagonista em `ficha.md`)
Representa o nível de lealdade, favores e atrito acumulados pelo protagonista com uma facção específica.

* **Arquivo Dono**: `ficha.md`
* **Seção**: `### Vínculos, Laços & Matriz Relacional -> * **Reputação com Facções:**`
* **Campos**:
  * `tag` (`str`, inferido ou explícito): Tag identificadora da facção.
  * `name` (`str`, obrigatório): Nome correspondente da facção.
  * `score` (`int`, obrigatório, [-3, +3], padrão 0): Grau numérico de alinhamento.
  * `tier` (`str`, computado): Nome do escalão correspondente ao `score`.
  * `favors` (`int`, $\ge 0$, padrão 0): Quantidade de favores políticos que o herói pode cobrar.
  * `debts` (`int`, $\ge 0$, padrão 0): Quantidade de débitos cobráveis pela facção.

#### Formato Markdown Estruturado (Canônico):
```markdown
### Vínculos, Laços & Matriz Relacional
* **Aliados & Cônjuges/Afetos:** Lady Vespera: Amante e aliada de sangue possessiva.
* **Rivais, Amores Proibidos & Desafetos:** Lorde Malakor: Comandante militar rival.
* **Reputação com Facções:**
  * **[CONSELHO_LORDES] Conselho dos Lordes de Cinzas:** +2 (Aliado) | Favores: 1 | Débitos: 0
  * **[GUARDA_MEIA_NOITE] A Guarda da Meia-Noite:** -2 (Hostil) | Favores: 0 | Débitos: 1
```

#### Formato Legado Tolerado (Compatibilidade com Campanhas 001..008):
```markdown
* **Reputação com Facções:** Conselho dos Lordes de Cinzas (Favorável / Respeitado), A Guarda da Meia-Noite (Sob Suspeita)
```
*Parser:* Converte automaticamente rótulos textuais legados para os escalões mais próximos (`Favorável` $\rightarrow$ `+1`, `Sob Suspeita` $\rightarrow$ `-1`, `Inimigo` $\rightarrow$ `-2`, etc.) sem falhar.

---

### 1.3 `FactionLedgerEntry` (Histórico de Reputação em `diario.md`)
Registro auditável e cronológico de cada alteração de reputação, favor ou débito.

* **Arquivo Dono**: `diario.md`
* **Seção**: `### Registro de Reputação & Facções`
* **Campos**:
  * `turn` (`int`, obrigatório): Número do turno no qual a mutação foi consolidada.
  * `faction` (`str`, obrigatório): Nome da facção afetada.
  * `delta_rep` (`int`): Variação de reputação (ex.: `+1`, `-1`).
  * `new_score` (`int`): Saldo resultante após a variação.
  * `new_tier` (`str`): Nome do escalão após a variação.
  * `delta_favor` (`int`): Variação de favores (`+1`, `-1`).
  * `delta_debt` (`int`): Variação de débitos (`+1`, `-1`).
  * `reason` (`str`): Justificativa diegética ou ação geradora.
  * `quest_id` (`str`, opcional): ID da missão vinculada (`Q1`, `Q2`), se decorrente de contrato.

#### Formato Markdown no Diário:
```markdown
### Registro de Reputação & Facções
* **[Turno 4]** Conselho dos Lordes de Cinzas: +1 Reputação (+1 -> +2 [Aliado]) | Favores: +1 | Motivo: Resgate dos reféns no pátio | Missão: Q1
* **[Turno 5]** A Guarda da Meia-Noite: -1 Reputação (-1 -> -2 [Hostil]) | Débitos: +1 | Motivo: Quebra do bloqueio militar
```

---

## 2. Máquina de Estados e Tabela de Escalões

A reputação opera em uma reta discreta com limites rígidos (clamping) em `[-3, +3]`:

```
[-3: Jurado de Morte] <-> [-2: Hostil] <-> [-1: Suspeito] <-> [0: Neutro] <-> [+1: Amigável] <-> [+2: Aliado] <-> [+3: Venerado]
```

### Regras de Transição:
1. **Clamping Estrito**: Qualquer operação que tente elevar a reputação acima de `+3` ou reduzi-la abaixo de `-3` é travada no teto/piso correspondente.
2. **Favores e Débitos Não-Negativos**: Favores e débitos nunca podem ser negativos. Tentar decrementar saldo zero retorna erro de validação.
3. **Mapeamento de Modificadores em Testes Sociais (D20 3 Portões)**:

| Score | Escalão | Modificador na DC | Modificador de Variante | Efeito de Representação em Cena |
| :---: | :--- | :---: | :---: | :--- |
| **+3** | Venerado | **DC -3** | `advantage` | Acesso irrestrito, lealdade inabalável, proteção armada ativa. |
| **+2** | Aliado | **DC -2** | normal | Cooperação ativa, refúgio seguro, atendimento a favores. |
| **+1** | Amigável | **DC -1** | normal | Receptividade cordial, disposição aberta para negociar. |
| **0** | Neutro | **DC +0** | normal | Postura formal, ceticismo pragmático, transações justas. |
| **-1** | Suspeito | **DC +1** | normal | Barreiras burocráticas, desconfiança velada, exigência de garantias. |
| **-2** | Hostil | **DC +3** | `disadvantage` | Recusa de diálogo, emboscadas armadas, tratamento como inimigo declarado. |
| **-3** | Jurado de Morte | **DC +5** | `disadvantage` | Caçadas públicas, tentativas ativas de execução, expulsão imediata. |
