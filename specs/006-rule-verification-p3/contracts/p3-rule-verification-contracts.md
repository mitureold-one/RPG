# Interface Contracts: P3 Transformação de Regra em Verificação

**Feature**: `rule-verification-p3`  
**Status**: Completed  
**Created**: 2026-10-21  
**Target Backlog Phase**: P3 (Reviewer Lints, Typed Overrides & Boundary Testing)

---

## 1. Reviewer Prose Lints API Contract (`council/reviewer.py`)

### 1.1 Função Modular de Lint de Prosa
```python
def check_prose_lints(text: str, context_label: str = "diario.md") -> list[dict]:
    """Varre um texto em busca de violações de estilo literário do RPGPRO.
    
    Retorna uma lista de issues contendo:
      - type: "EMOJI_DETECTED" | "SCRIPT_FORMAT_DETECTED" | "FOURTH_WALL_QUESTION"
      - severity: "MEDIUM" | "HIGH"
      - detail: str
    """
```

### 1.2 Regras de Detecção
1. **Emoji Lint**:
   - Padrão: correspondência com caracteres das faixas Unicode `\U0001F300-\U0001FAFF`, `\u2600-\u27BF`.
   - Se encontrado: emite issue `EMOJI_DETECTED` com o caractere e contexto.
2. **Script Format Lint**:
   - Padrão: linhas iniciando com `[Nome]:` ou `Nome: "..."` / `Nome: '...'`.
   - Se encontrado: emite issue `SCRIPT_FORMAT_DETECTED` indicando a linha infratora.
3. **Fourth Wall Question Lint**:
   - Padrão: sentenças finais contendo perguntas clichês de mestre ("O que você faz?", "O que fará agora?").
   - Se encontrado: emite issue `FOURTH_WALL_QUESTION`.

---

## 2. SSOT Campaign Overrides Contract (`regras.md` & `council/ssot.py`)

### 2.1 Parser do Manifesto de Mecânica
```python
def parse_regras_manifest(regras_path: Path) -> dict:
    """Extrai o bloco YAML de mecânica de regras.md.
    
    Retorna:
    {
        "system": str,               # Default: "d20_3gates"
        "ruleset": str,              # Default: "d20_3gates"
        "overrides": list[dict],     # Lista de modificadores tipados
    }
    """
```

### 2.2 Injeção no Payload de Preparação (`lazy_turn.py prepare`)
O payload gerado deve expor a lista de overrides tipados diretamente em `step_1_gm_arbitration`:
```python
prep_payload["step_1_gm_arbitration"]["overrides"] = [
    {
        "id": "exhaustion_friction",
        "type": "cost_multiplier",
        "target": "stamina",
        "value": 2.0,
        "condition": "Esforço extremo continuado sem repouso"
    }
]
```

---

## 3. Boundary Testing Contracts (`tests/test_boundary_contracts.py`)

### 3.1 Contrato de Imunidade a Vazamento Diegético
* **Entrada**: Nomes próprios, títulos e locais extraídos de `campaigns/*/{ficha.md,npcs.md,mundo.md}`.
* **Alvo**: Todos os arquivos Markdown e Python sob `.agents/skills/` e caminhos globais de skills.
* **Critério de Falha**: Se qualquer substantivo próprio característico de uma campanha for encontrado nos arquivos de skill, o teste falha listando arquivo e termo vazado.

### 3.2 Contrato de CLI com Documentação
* **Entrada**: Árvore de comandos gerada por `lazy_turn.build_cli()` e blocos de código em arquivos `.md`.
* **Critério de Falha**: Qualquer comando exemplificado em documentações que falhe na validação de argumentos ou invoque flags descontinuadas gera falha no teste.

### 3.3 Contrato de Snapshot do Payload
* **Entrada**: Execução congelada de `lazy_turn.cmd_prepare(campaign_id, action, no_roll=True)`.
* **Critério de Falha**: Divergência na lista de chaves de topo ou alteração nos campos essenciais de arbitragem, estado ou mandatos.
