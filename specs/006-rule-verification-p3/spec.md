# Feature Specification: P3 — Transformação de Regra em Verificação

**Feature Name**: `rule-verification-p3`  
**Status**: Completed  
**Created**: 2026-10-21  
**Target Backlog Phase**: P3 (Reviewer Lints, Machine-Readable Overrides & Boundary Testing)

---

## 1. Executive Summary & Problem Statement

O ecossistema RPGPRO estabelece como diretriz soberana que diretrizes críticas de qualidade não devem depender da memória estocástica dos Modelos de Linguagem:  
> *"Uma regra, um único dono textual, um único ponto de enforcement no código. O que não possui enforcement é guideline e não deve fingir ser código."*

Embora as fases P0, P1 e P2 tenham resolvido o acoplamento da CLI, eliminado duplicatas nas skills e desacoplado o ruleset matemático do motor, três fragilidades de integridade ainda persistem no sistema:

1. **Regras de Prosa sem Verificação Mecânica**: As regras de estilo literário ("Zero Emojis", "Proibição de Roteiro Teatral / Falas em Formato Script" e "Proibição de Perguntas de Encerramento Quebrando a Quarta Parede como 'O que você faz?'") continuam como mandatos puramente textuais. Sem um lint automatizado em `reviewer.py`, desvios nessas regras passam despercebidos até corromperem o histórico do diário de campanha.
2. **Overrides Mecânicos Ambíguos em `regras.md`**: Os arquivos `regras.md` contêm um bloco `overrides:` preenchido com descrições em linguagem natural arbitrária (`effect: "..."`). Sem tipagem ou propriedades legíveis por máquina (ex.: multiplicadores de custo de recursos, imunidades, resistências de dano/efeito), o motor não consegue validar nem aplicar esses modificadores programaticamente na arbitragem de turno.
3. **Ausência de Testes de Fronteira Contínuos**:
   - Não há teste impedindo que nomes diegéticos, substantivos próprios ou termos de campanhas específicas vazem para as instruções universais das skills.
   - Não há verificação automatizada comparando o `--help` da CLI com a documentação de referência para impedir comandos órfãos ou flags obsoletas.
   - Não há snapshot de payload assegurando que o contrato de saída do `lazy_turn.py prepare` permaneça estável e imune a alterações acidentais de formato.

Esta especificação formaliza a introdução de lints determinísticos de prosa no auditor de crônicas (`reviewer.py`), a padronização do bloco de mecânicas tipadas (`overrides`) em `regras.md`, e a criação de uma suíte de testes de fronteira para garantir neutralidade universal, conformidade de CLI e estabilidade do payload de turno.

---

## 2. User Scenarios & Acceptance Criteria

### User Scenario 1: Auditoria Rígida de Estilo e Lints Literários no Review
* **As a** Game Master ou jogador auditando o diário de crônica após um ou mais turnos narrados,
* **I want** que o comando `lazy_turn.py review` aponte violações objetivas de estilo literário (presença de emojis, diálogos formatados como roteiro teatral `[Nome]:` e perguntas clichês de encerramento como "O que você faz?"),
* **So that** a integridade literária e imersiva seja garantida por verificações de código determinísticas antes da consolidação do cânone.
* **Acceptance Criteria**:
  - `council/reviewer.py` detecta qualquer caractere de emoji nos resumos ou narrativas de turnos recentes e sinaliza um issue com tipo `EMOJI_DETECTED`.
  - Linhas narrativas que utilizem notação de roteiro teatral (ex.: `Nome: "fala"` ou `[Nome]: fala`) em vez de travessão literário são detectadas com tipo `SCRIPT_FORMAT_DETECTED`.
  - Sentenças finais apelando para perguntas de encerramento de quarta parede (ex.: "O que você faz?", "O que fará agora?", "Qual a sua ação?") são detectadas com tipo `FOURTH_WALL_QUESTION`.
  - A execução de `lazy_turn.py review` relata essas inconformidades no relatório consolidado com severidade explícita e recomendação de correção.

### User Scenario 2: Overrides Mecânicos Estruturados e Legíveis por Máquina
* **As a** criador de campanha ou desenvolvedor do RPGPRO,
* **I want** definir regras mecânicas específicas da campanha (multiplicadores de custo de recursos, resistências e penalidades de atrito) em um bloco estruturado e tipado dentro de `regras.md`,
* **So that** o motor de jogo consiga inspecionar, auditar e disponibilizar essas regras no payload de arbitragem sem depender de interpretação livre de texto poético.
* **Acceptance Criteria**:
  - O bloco `yaml` em `regras.md` suporta uma lista ou mapa tipado de `overrides` com atributos explícitos (ex.: tipo de regra, recurso afetado, fator multiplicador, resistência/imunidade).
  - As campanhas ativas (`dinastia_cinzas`, `imperio_valiria`, `perpetuos_terra_incognita`) e o template `regras.template.md` adotam o novo formato padronizado.
  - A função de descoberta e leitura da campanha carrega e expõe esses overrides tipados na etapa de preparação de turno (`lazy_turn.py prepare`), mantendo a separação entre mecânica tipada e prosa de contexto diegético.

### User Scenario 3: Blindagem por Testes de Fronteira (Vazamento, CLI e Payload)
* **As a** mantenedor do framework RPGPRO,
* **I want** testes automatizados de fronteira que verifiquem vazamentos diegéticos, consistência de documentação de CLI e invariância de snapshot de payload,
* **So that** nenhuma regressão silenciosa contamine a neutralidade das skills ou quebre contratos de integração do motor.
* **Acceptance Criteria**:
  - **Teste de Vazamento**: A suíte de testes extrai os substantivos próprios e entidades diegéticas das 3 campanhas ativas e valida que nenhuma skill (local ou global) contém referências diretas a esses termos particulares.
  - **Teste de Contrato de CLI**: A suíte compara exaustivamente as opções de comando expostas no `--help` do `lazy_turn.py` com todas as chamadas e exemplos citados nas documentações markdown e skills, acusando divergências.
  - **Teste de Snapshot de Payload**: A suíte valida que o payload JSON gerado por `lazy_turn.py prepare` mantém conformidade estrita com um snapshot de chaves e estruturas obrigatórias, alertando sobre qualquer mutação acidental.

---

## 3. Functional Requirements

### 3.1 Lints Determinísticos de Prosa no Reviewer (`council/reviewer.py`)
* **FR-01**: Implementar o detector de emojis `EMOJI_DETECTED` em `council/reviewer.py`:
  - Varrer o texto dos turnos recentes e resumos registrados em `diario.md`.
  - Disparar issue com `severity: MEDIUM` (ou `HIGH`) apontando o turno e o trecho com emoji.
* **FR-02**: Implementar o detector de formato teatral `SCRIPT_FORMAT_DETECTED` em `council/reviewer.py`:
  - Identificar padrões de início de linha ou diálogos que utilizem o formato `^[A-Z][a-zA-Z\s]{1,25}:` ou `^\[[^\]]+\]:` em blocos de prosa do diário, violando a regra de travessão literário (`—`).
  - Disparar issue detalhando a linha em desacordo.
* **FR-03**: Implementar o detector de pergunta de quarta parede `FOURTH_WALL_QUESTION` em `council/reviewer.py`:
  - Identificar variações clichês de fechamento de cena (ex.: `"O que você faz?"`, `"O que fará a seguir?"`, `"Qual sua decisão?"`, `"Como você reage?"`) ao final do resumo de turno ou trecho narrativo.
  - Disparar issue recomendando encerramento com gancho diegético ou impacto sensorial em vez de formulação clichê.

### 3.2 Bloco de Overrides Tipados em `regras.md`
* **FR-04**: Definir a especificação tipada do bloco `overrides:` em `regras.md`:
  - Cada override deve declarar campos semânticos estruturados:
    - `id`: identificador alfanumérico único do override (ex.: `exhaustion_multiplier`, `mana_immunity`, `stamina_cost_surge`).
    - `type`: categoria do modificador (ex.: `cost_multiplier`, `resistance`, `immunity`, `threshold_shift`, `stat_penalty`).
    - `target`: recurso, tipo de dano ou atributo afetado (ex.: `stamina`, `hp`, `mana_detection`, `mental_influence`).
    - `value`: valor numérico ou qualificador tipado (ex.: `2.0`, `immune`, `-2`).
    - `condition`: escopo ou contexto de aplicação em prosa curta (ex.: `"sob esforço continuado"`, `"frente a medições mágicas"`).
* **FR-05**: Atualizar o parser de regras da campanha (`council/ssot.py` e/ou `council/helpers.py`) para ler o bloco `overrides:` tipado e repassá-lo na estrutura de dados da campanha.
* **FR-06**: Integrar os overrides tipados ao resultado emitido por `lazy_turn.py prepare` (sob metadados de regras do `step_1_gm_arbitration`), permitindo que agentes e revisores auditem os modificadores ativos na cena.
* **FR-07**: Atualizar `templates/regras.template.md` e os arquivos de campanha (`campaigns/dinastia_cinzas/regras.md`, `campaigns/imperio_valiria/regras.md`, `campaigns/perpetuos_terra_incognita/regras.md`) para o novo esquema estruturado.

### 3.3 Testes de Fronteira e Blindagem de Contratos (`tests/test_boundary_contracts.py` ou expansão de `tests/`)
* **FR-08**: Criar teste automatizado de **Vazamento Diegético**:
  - Extrair o catálogo de substantivos próprios e nomes-chave (protagonistas, NPCs canônicos, locais primários) das três campanhas existentes.
  - Verificar recursivamente todos os arquivos das skills do RPGPRO (`.agents/skills/` e diretório de skills de usuário se presente).
  - Falhar o teste caso qualquer termo diegético exclusivo conste nas instruções operacionais das skills.
* **FR-09**: Criar teste automatizado de **Contrato de CLI vs Documentação**:
  - Inspecionar a árvore de argumentos gerada por `lazy_turn.py build_cli()` (subcomandos, argumentos posicionais e flags opcionais).
  - Inspecionar todos os blocos de comando `python lazy_turn.py ...` em `README.md`, `DECISOES_ARQUITETURA.md` e arquivos de skills.
  - Garantir que nenhum comando documentado invoque flags inexistentes ou descontinuadas e que nenhuma flag documentada com `--help` esteja divergente.
* **FR-10**: Criar teste automatizado de **Snapshot do Payload de Preparação**:
  - Executar `lazy_turn.py prepare` para uma campanha canônica de referência em modo previsível (`--no-roll`).
  - Comparar a estrutura de chaves de primeiro nível e dos passos obrigatórios (`step_1_gm_arbitration`, `step_2_engine_state`, `step_3_writer_mandate`, `step_4_post_turn_commit_template`) contra um esquema canônico congelado (snapshot de schema).
  - Falhar o teste caso ocorra remoção, renomeação ou alteração inesperada de estrutura no contrato de saída.

---

## 4. Key Entities & Data Schemas

### 4.1 Schema de Overrides Tipados em `regras.md`
```yaml
system: d20_3gates
overrides:
  - id: exhaustion_friction
    type: cost_multiplier
    target: stamina
    value: 2.0
    condition: "Esforço físico extremo continuado sem repouso"
  - id: mana_sensor_immunity
    type: immunity
    target: mana_detection
    value: true
    condition: "Artefatos ou feitiços de medição mágica"
```

### 4.2 Schema dos Novos Issues de Lint no `council/reviewer.py`
```python
# Emoji Detectado
{
    "type": "EMOJI_DETECTED",
    "severity": "MEDIUM",
    "detail": "Caractere emoji detectado no Turno 12 ('🔥'): o estilo literário do RPGPRO exige prosa textual pura sem emojis.",
}

# Formato Script / Teatral Detectado
{
    "type": "SCRIPT_FORMAT_DETECTED",
    "severity": "HIGH",
    "detail": "Linha em formato de roteiro teatral detectada no Turno 12 ('Kon-El: Não recue.'): utilize travessão literário (—) e diálogo integrado à narrativa.",
}

# Pergunta de Quarta Parede Detectada
{
    "type": "FOURTH_WALL_QUESTION",
    "severity": "MEDIUM",
    "detail": "Pergunta de quebra de quarta parede detectada no encerramento do Turno 12 ('O que você faz?'): encerre com gancho sensorial ou consequência dramática aberta.",
}
```

### 4.3 Schema de Referência do Snapshot do Payload (`lazy_turn.py prepare`)
```json
{
  "campaign": "string",
  "system": "string",
  "step_1_gm_arbitration": {
    "action": "string",
    "ruleset": "string",
    "dc_ladder": "object",
    "overrides": "array"
  },
  "step_2_engine_state": {
    "scene_type": "string",
    "vitals": "object",
    "inventory": "array",
    "active_clocks": "array"
  },
  "step_3_writer_mandate": {
    "prose_guidelines": "array",
    "active_scene_mandate": "object"
  },
  "step_4_post_turn_commit_template": {
    "command_template": "string"
  }
}
```

---

## 5. Success Criteria

* **SC-01 (Auditoria Mecânica de Estilo)**: O comando `lazy_turn.py review` identifica com 100% de precisão textos de teste contendo emojis, formato script (`Nome:`) e perguntas clichês de quarta parede, emitindo os diagnósticos esperados.
* **SC-02 (Padronização dos Overrides)**: Todas as 3 campanhas ativas e o template de regras contêm o bloco `overrides:` no formato tipado legível por máquina, consumido e exportado pelo motor sem falhas.
* **SC-03 (Imunidade a Vazamento Diegético)**: O teste de vazamento confirma que 0% das instruções contidas nas skills universais referenciam substantivos próprios das campanhas específicas.
* **SC-04 (Alinhamento Estrito da CLI com a Documentação)**: 100% dos comandos exemplificados nas documentações executam validação de sintaxe e correspondência de flags com o CLI construído em `lazy_turn.py`.
* **SC-05 (Estabilidade do Contrato de Turno)**: O teste de snapshot de payload garante que o formato JSON emitido por `lazy_turn.py prepare` permanece estável e protegido contra mutações não intencionais.
* **SC-06 (Conformidade de Testes Globais)**: Toda a suíte de testes (`python -m unittest discover tests`) executa com 100% de sucesso.

---

## 6. Assumptions & Dependencies

- Os lints de prosa serão aplicados primordialmente sobre os resumos e conteúdos de turnos recentes do `diario.md`, preservando a velocidade do comando `review`.
- A regex de detecção de emojis deve abranger faixas Unicode padrão para emojis e pictogramas sem gerar falsos positivos em pontuações tipográficas comuns (aspas, travessões, reticências).
- O formato de overrides em `regras.md` permanece retrocompatível caso uma campanha ainda declare apenas campos em texto livre temporariamente, emitindo aviso de modernização sem interromper o loop se os dados puderem ser convertidos.
- Os testes de fronteira farão parte da suíte permanente do repositório em `tests/`, garantindo que futuras adições passem por verificação contínua no CI/desenvolvimento local.
