# Research & Technical Decisions: P3 Transformação de Regra em Verificação

**Feature**: `rule-verification-p3`  
**Status**: Completed  
**Created**: 2026-10-21  
**Target Backlog Phase**: P3 (Reviewer Lints, Typed Overrides & Boundary Testing)

---

## 1. Decision 1: Detecção de Emojis em Prosa (Stdlib vs Dependência Externa)

### Decision
Utilizar expressão regular (`re`) baseada em faixas de código Unicode nativas do Python padrão (`re.compile(...)`), sem instalar bibliotecas externas como `emoji`.

### Rationale
* O princípio *Ponytail* e a arquitetura do RPGPRO priorizam zero dependências externas quando a biblioteca padrão resolve o problema de forma robusta.
* As faixas Unicode de pictogramas, símbolos e emojis (como `\U0001F600-\U0001F64F`, `\U0001F300-\U0001F5FF`, `\U0001F680-\U0001F6FF`, `\U0001F700-\U0001F77F`, `\U0001F780-\U0001F7FF`, `\U0001F800-\U0001F8FF`, `\U0001F900-\U0001F9FF`, `\U0001FA00-\U0001FA6F`, `\U0001FA70-\U0001FAFF`, `\u2600-\u26FF`, `\u2700-\u27BF`) são determinísticas e cobrem a totalidade dos emojis gerados por LLMs comerciais.
* O custo de execução de uma varredura regex sobre os últimos turnos narrados é inferior a 1 ms por execução de `lazy_turn.py review`.

### Alternatives Considered
* **Biblioteca `emoji` (`pip install emoji`)**: Rejeitada por violar a regra de estrita dependência padrão (Stdlib First) e exigir gerenciamento de ambiente virtual adicional para um único lint.
* **Heurística baseada em `ord(char) > 127`**: Rejeitada por gerar falsos positivos em caracteres acentuados do português (`ç`, `ã`, `é`, `ó`, etc.) e pontuações tipográficas como o travessão em-dash (`—`, `\u2014`).

---

## 2. Decision 2: Detecção de Formato Teatral / Script (`[Nome]:`)

### Decision
Aplicar regex de linha inteira com âncoras multiline (`re.MULTILINE`) para identificar linhas narrativas que começam com notação teatral de diálogo:
1. `r"^\s*\[[A-Za-zÀ-ÖØ-öø-ÿ\s]{2,30}\]\s*:"` (ex.: `[Kon-El]:`, `[Kallista]:`)
2. `r"^\s*[A-ZÀ-ÖØ-ß][A-Za-zÀ-ÖØ-öø-ÿ\s]{1,25}\s*:\s*[\"“']"` (ex.: `Lyra: "Não recue."` ou `Eldrin: 'Vamos.'`)

### Rationale
* O RPGPRO estabelece como diretriz literária que o diálogo deve ser inserido organicamente na prosa com travessão (`—`), evitando o modelo de roteiro teatral de RPG amador.
* O lint deve ignorar seções de cabeçalho Markdown (ex: `### Nome:`), blocos YAML ou chaves de metadados (`Status:`, `Vitais:`), aplicando a restrição apenas em blocos de texto narrativo ou parágrafos de resumo de turno.

### Alternatives Considered
* **Classificação semântica via chamada secundária de LLM**: Rejeitada por introduzir latência, custo de tokens e não-determinismo em uma checagem que é sintaticamente óbvia.
* **Proibição de qualquer dois-pontos (`:`)**: Rejeitada por quebrar usos legítimos de dois-pontos na língua portuguesa (introdução de listas, explicações ou orações apositivas).

---

## 3. Decision 3: Detecção de Perguntas Clichês de Encerramento (Quarta Parede)

### Decision
Verificar a terminação do resumo de turno (`last_turn_summary`) e das últimas sentenças narradas contra uma lista compilada de expressões clichês de mestre de RPG que quebram a quarta parede e transferem a narrativa de volta com fórmulas vazias:
* `r"(?i)(?:o\s+que\s+(?:você|voce|vc)\s+(?:faz|fará|vai\s+fazer|decide|escolhe)|qual\s+(?:é\s+a\s+sua|a\s+sua|é\s+sua|sua)\s+(?:ação|decisão|escolha)|como\s+(?:você|voce|vc)\s+(?:reage|responde))(?:\s*\?|\s*$)"`

### Rationale
* O mandato de escrita (`step_3_writer_mandate`) instrui explicitamente a encerrar a cena com o impacto sensorial e um gancho diegético aberto, sem recorrer ao bordão "O que você faz?".
* O lint determinístico assegura que a entrega narrativa mantenha a gravidade literária proposta pelo RPGPRO.

### Alternatives Considered
* **Bloquear qualquer ponto de interrogação (`?`)**: Rejeitada porque diálogos ou pensamentos internos do protagonista podem conter perguntas diegéticas legítimas (ex.: *"Será que o selo resistiria?"*).

---

## 4. Decision 4: Schema Tipado de Overrides Mecânicos em `regras.md`

### Decision
Padronizar a propriedade `overrides:` dentro do bloco ````yaml` de `regras.md` como uma lista de dicionários estruturados, contendo:
```yaml
system: d20_3gates
overrides:
  - id: string
    type: cost_multiplier | resistance | immunity | threshold_shift | stat_penalty
    target: string (ex: stamina, hp, mana_detection, psionic)
    value: float | int | string | boolean
    condition: string
```

### Rationale
* Permite que o motor de arbitragem (`council/gm.py`, `lazy_turn.py prepare`) extraia os modificadores diretamente via parser YAML seguro (`yaml.safe_load` ou parser minimalista de chave-valor nativo se sem dependências) e os injete no passo `step_1_gm_arbitration.overrides`.
* A formalização dos campos encerra a ambiguidade de descrições livres em texto, viabilizando no futuro cálculos automáticos de consumo de recursos.

### Alternatives Considered
* **Tabela Markdown de Modificadores**: Rejeitada porque parsing de tabelas Markdown é sujeito a ruídos de formatação e mais propenso a inconsistências do que YAML estruturado.
* **Arquivo JSON separado por campanha (`overrides.json`)**: Rejeitada para preservar o princípio de SSOT em Markdown: `regras.md` centraliza tanto as leis diegéticas do mundo quanto as diretivas tipadas da mesa.

---

## 5. Decision 5: Arquitetura da Suíte de Testes de Fronteira

### Decision
Estruturar três testes de fronteira autocontidos dentro de `tests/test_boundary_contracts.py` (ou integrados em `tests/test_cli_contracts.py`):
1. **Teste de Vazamento Diegético (`test_boundary_no_diegetic_leaks_in_skills`)**:
   - Carrega todas as campanhas em `campaigns/`.
   - Extrai automaticamente tokens e nomes próprios de protagonistas (`ficha.md`), NPCs registrados (`npcs.md`) e termos-chave de facções/locais (`mundo.md`).
   - Varre todos os arquivos `.md` e `.py` em `.agents/skills/` (e skills globais).
   - Valida que nenhum termo diegético exclusivo está presente nas skills.
2. **Teste de Contrato de CLI com Documentação (`test_boundary_cli_docs_contract`)**:
   - Inspeciona dinamicamente os subcomandos e argumentos do `lazy_turn.build_cli()`.
   - Extrai comandos documentados em `README.md`, `DECISOES_ARQUITETURA.md` e nos `SKILL.md`.
   - Verifica se todas as flags usadas existem no parser e se nenhum comando documentado gera erro de argumento.
3. **Teste de Snapshot de Payload (`test_boundary_prepare_payload_snapshot`)**:
   - Executa `lazy_turn.cmd_prepare` em modo determinístico com parâmetros congelados.
   - Compara o conjunto de chaves de topo (`step_1_gm_arbitration`, `step_2_engine_state`, `step_3_writer_mandate`, `step_4_post_turn_commit_template`), seus subcampos essenciais e os tipos de dados contra um schema JSON canônico congelado.

### Rationale
* Garante isolamento estrito entre camadas (L1/L1b agnósticos vs L3 diegético).
* Assegura que refatorações ou expansões do motor não quebrem silenciosamente os agentes consumidores nem a interface de linha de comando.
