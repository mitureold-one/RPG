# Feature Specification: P2 — Separação de Sistema e Motor

**Feature Name**: `separate-system-engine-p2`  
**Status**: Draft  
**Created**: 2026-10-21  
**Target Backlog Phase**: P2 (Engine & Ruleset Separation, Schema Versioning & CLI Sanitization)

---

## 1. Executive Summary & Problem Statement

O RPGPRO foi concebido como um orquestrador agnóstico de RPG baseado em SSOT Markdown. No entanto, sua arquitetura atual ainda apresenta três formas críticas de acoplamento entre o **motor universal** (L1) e os **sistemas/cenários específicos** (L1b e L3):

1. **Acoplamento Férreo do Motor ao Sistema d20 de 3 Portões**: A lógica matemática do d20 (rolagens `1d20` / `2d20kh1` / `2d20kl1`, cálculo de modificador `(stat - 10) // 2`, escada de DC 10/15/20/25 e resolução de disputas PC vs NPC e NPC vs NPC) está embutida diretamente em `council/gm.py`. Isso impede que o RPGPRO suporte outros sistemas de regras (ex.: 3d6, d100, Dice Pool, PBTA, narrativistas puros) sem modificar o núcleo do motor.
2. **Ausência de Versionamento de Schema e Falhas Silenciosas em `find_campaign`**: Atualmente, `find_campaign` em `council/helpers.py` apenas verifica se o diretório da campanha existe e retorna caminhos estáticos sem validar a integridade ou a versão do schema dos arquivos canônicos. Campanhas corrompidas ou defasadas degradam silenciosamente em tempo de execução com exceções genéricas ou comportamentos imprevisíveis durante o loop de turno.
3. **Vazamento de Nomes de Cenários/Campanhas na CLI Universal**: A interface de linha de comando (`lazy_turn.py`) exibe textos de `--help` contendo referências acopladas a cenários específicos (ex: `'O Colapso em Shinjuku'`, `'Tóquio, Distrito de Shinjuku'`, `'Plano Kenjaku:1'`, `'Fleur'`, `'Cedric, Krum'`). Essa contaminação de diegeses particulares na ferramenta raiz viola a neutralidade do framework.

Esta especificação P2 define a extração da mecânica d20 para o módulo modular `rulesets/d20_3gates.py`, a declaração explícita de `system:` no manifesto da campanha, a obrigatoriedade de `schema_version` no cabeçalho do `diario.md` com validação estrita (falha ruidosa) em `find_campaign`, e a higienização completa dos textos de ajuda da CLI.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Execução Modular de Resolução via Ruleset Declarado
* **As a** Game Master ou jogador iniciando um turno em qualquer campanha,
* **I want** que o motor identifique o sistema de resolução declarado no manifesto da campanha (`system: d20_3gates`) e delegue as rolagens e disputas ao módulo de regras correspondente (`rulesets/d20_3gates.py`),
* **So that** o motor central (`council/gm.py` e `lazy_turn.py`) permaneça agnóstico a regras e novos sistemas possam ser plugados sem alterar o core do framework.
* **Acceptance Criteria**:
  - Toda a lógica matemática de `roll_3_gates`, resolução de variantes (vantagem/desvantagem), cálculo de modificadores de atributo, comparação de DC e resolução de disputas opostas (`roll_contest`) é isolada em `rulesets/d20_3gates.py`.
  - O manifesto da campanha declara explicitamente o campo `system:` (ex: `system: d20_3gates`).
  - O motor dinamicamente carrega/invoca o ruleset indicado pelo manifesto da campanha.
  - O resultado emitido por `lazy_turn.py prepare` mantém paridade funcional estrita com a mecânica dos 3 Portões já consolidada.

### User Scenario 2: Validação Rígida de Schema e Falha Ruidosa na Descoberta de Campanhas
* **As a** desenvolvedor ou Game Master executando comandos do CLI do RPGPRO,
* **I want** que a função `find_campaign` verifique a presença e a validade de `schema_version` no arquivo `diario.md` e falhe alto (*fail loudly*) com uma mensagem clara caso o arquivo esteja ausente, corrompido ou sem a versão de schema exigida,
* **So that** erros de compatibilidade e corrupção de estado sejam detectados imediatamente na inicialização, impedindo corrupção subsequente de estado.
* **Acceptance Criteria**:
  - Todo arquivo `diario.md` canônico contém uma declaração explícita de versão de schema (ex: `schema_version: 1` no bloco de metadados / frontmatter inicial).
  - Se `diario.md` não existir, estiver inacessível ou não declarar `schema_version` compatível, `find_campaign` aborta com erro explícito (`ValueError`, `RuntimeError` ou payload de erro fatal com diagnóstico legível), sem retornar caminhos fictícios ou falhar silenciosamente.
  - Todas as campanhas existentes no repositório (`dinastia_cinzas`, `imperio_valiria`, `perpetuos_terra_incognita`) e o template oficial `templates/diario.template.md` contêm `schema_version: 1`.

### User Scenario 3: CLI Estritamente Agnóstica e Higienizada
* **As a** usuário visualizando `--help` em qualquer comando ou subcomando de `lazy_turn.py`,
* **I want** todos os exemplos de ajuda focados em conceitos universais e genéricos de TTRPG,
* **So that** a interface de linha de comando não contenha referências a obras de ficção específicas ou nomes diegéticos locais.
* **Acceptance Criteria**:
  - Nenhuma menção a entidades particulares (como `Shinjuku`, `Kenjaku`, `Fleur`, `Cedric`, `Krum` ou IDs específicos) permanece nas strings de `help` do `build_cli()`.
  - Exemplos substituídos por arquétipos universais (ex: `--focus "Aliado, Mentor"`, `--clock-advance "Invasão:1"`, `--scene-name "O Cerco da Fortaleza"`, `--location "Cidadela Superior"`).
  - A suíte de testes automatizada valida que nenhuma string de help viola a neutralidade de cenários.

---

## 3. Functional Requirements

### 3.1 Extração do Ruleset Modular (`rulesets/d20_3gates.py`)
* **FR-01**: Criar o módulo `rulesets/d20_3gates.py` (ou `council/rulesets/d20_3gates.py` com alias em `rulesets/`), exportando a interface padrão de resolução mecânica:
  - `roll_action(action_label, variant, dc, stat_name, stat_val) -> dict` (ou compatível com `roll_3_gates`)
  - `roll_contest(pc_name, pc_stat, pc_val, npc_name, npc_stat, npc_val, ...) -> dict`
  - `extract_npc_modifier(npc_dict, stat_name) -> tuple`
  - `get_dc_table() -> dict`
* **FR-02**: `council/gm.py` deve atuar como orquestrador/despachante agnóstico ou reexportador de transição, delegando as chamadas mecânicas ao ruleset selecionado.
* **FR-03**: No manifesto de cada campanha (bloco estruturado em `regras.md` ou cabeçalho canônico da campanha), a propriedade `system:` deve declarar o identificador do ruleset ativo (ex: `system: d20_3gates`).
* **FR-04**: O gerador de novas campanhas (`init_campaign_from_templates` e `init-campaign`) deve instanciar campanhas com `system: d20_3gates` por padrão.

### 3.2 Metadados de Schema e Validação Ruidosa (`schema_version`)
* **FR-05**: Definir a constante universal `CURRENT_SCHEMA_VERSION = 1` no núcleo do motor (`council/helpers.py`).
* **FR-06**: Incluir o campo `schema_version: 1` no cabeçalho ou bloco de metadados de `diario.md` em todas as campanhas ativas (`dinastia_cinzas`, `imperio_valiria`, `perpetuos_terra_incognita`) e no template `templates/diario.template.md`.
* **FR-07**: Em `council/helpers.py`, refatorar `find_campaign(campaign_id)` para realizar a validação prévia de integridade:
  1. Verificar a existência do diretório da campanha.
  2. Verificar a existência e legibilidade de `diario.md`.
  3. Extrair e verificar `schema_version`:
     - Se `diario.md` não contiver `schema_version`, levantar erro explícito (ex.: `ValueError(f"Campanha '{campaign_id}' inválida: 'diario.md' não declara 'schema_version'.")`).
     - Se `schema_version` for superior à versão suportada pelo motor, levantar erro explícito de incompatibilidade (`IncompatibleSchemaError` ou `ValueError`).
* **FR-08**: Atualizar os comandos CLI em `lazy_turn.py` que invocam `find_campaign` para capturar e reportar erros de schema com clareza em formato legível e em formato JSON (`--json`).

### 3.3 Higienização da CLI (`lazy_turn.py`)
* **FR-09**: Substituir todos os exemplos nos parâmetros de `lazy_turn.py`:
  - `--focus`: remover referências como `Fleur` / `Cedric, Krum` e substituir por exemplos genéricos (ex: `'Vanguarda'` ou `'Capitão, Batedor'`).
  - `--clock-advance`: remover `Plano Kenjaku:1` e substituir por exemplo genérico (ex: `'Invasão:1'` ou `'Conspiração:2'`).
  - `--scene-name`: remover `'O Colapso em Shinjuku'` e substituir por exemplo genérico (ex: `'O Cerco das Muralhas'` ou `'O Confronto na Cidadela'`).
  - `--location`: remover `'Tóquio, Distrito de Shinjuku'` e substituir por exemplo genérico (ex: `'Fronteira Norte, Posto Avançado'` ou `'Câmara do Conselho'`).
  - `--campaign` em `init-campaign`: remover `'cyber_neo_tokyo'` e usar `'fantasia_reinos'` ou `'nova_campanha'`.
* **FR-10**: Garantir que nenhum texto de documentação da CLI dependa ou revele elementos canônicos de franquias externas.

---

## 4. Key Entities & Data Schemas

### 4.1 Schema de Cabeçalho do `diario.md`
```markdown
<!-- schema_version: 1 -->
# Diário da Crônica: {{TITULO_CAMPANHA}}
```
*OU via bloco YAML inicial:*
```markdown
---
schema_version: 1
---
# Diário da Crônica: {{TITULO_CAMPANHA}}
```

### 4.2 Schema do Manifesto de Mecânica em `regras.md`
```yaml:mechanics
system: d20_3gates
ruleset: d20_3gates
overrides: []
```

### 4.3 Interface do Ruleset Modular (`rulesets/d20_3gates.py`)
```python
def roll_3_gates(label: str, variant: str = "normal", dc: int = 15, stat_name: str = "", stat_val: int = 10) -> dict: ...
def extract_npc_contest_modifier(npc: dict, stat_requested: str = "") -> tuple: ...
def roll_contest(...) -> dict: ...
```

---

## 5. Success Criteria

* **SC-01 (Desacoplamento de Ruleset)**: O arquivo `rulesets/d20_3gates.py` opera de forma autocontida para a resolução de dados do sistema d20 3 Portões. `council/gm.py` e `lazy_turn.py` importam e consomem o ruleset desacoplado sem regressão funcional.
* **SC-02 (Enforcement Ruidoso de Schema)**: Nenhuma campanha sem `schema_version` válido em `diario.md` é aceita por `find_campaign`. Testes automatizados confirmam que campanhas sem versão disparam erro impeditivo imediato com mensagem orientativa.
* **SC-03 (Neutralidade da CLI)**: A suíte de testes comprova que nenhuma string de ajuda (`--help`) de `lazy_turn.py` contém nomes de campanhas ou termos diegéticos de cenários específicos.
* **SC-04 (Compatibilidade e Testes)**: 100% da suíte de testes de contratos e execução (`python -m unittest discover tests`) executa com sucesso após a migração.

---

## 6. Assumptions & Dependencies

- O padrão universal atual continuará sendo `d20_3gates`, garantindo retrocompatibilidade com todas as campanhas em andamento.
- A extração de `rulesets/d20_3gates.py` preserva os mesmos nomes de campos no JSON retornado (`natural`, `modifier`, `total`, `tier`, `summary`, etc.), para não quebrar a injeção em `step_3_writer_mandate`.
- O formato do `schema_version` deve ser suportado com tolerância tanto para comentário HTML (`<!-- schema_version: 1 -->`) quanto frontmatter YAML (`--- \n schema_version: 1 \n ---`), facilitando edição humana sem conflito com parsers markdown.
