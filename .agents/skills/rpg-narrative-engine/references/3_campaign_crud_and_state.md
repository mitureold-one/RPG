# Módulo 3: Gestão de Estado, SSOT Markdown, Sessão Zero & Relógios

Este documento é a **autoridade única e soberana** sobre os arquivos Markdown da campanha, o protocolo de pesquisa web na Sessão Zero, a persistência atômica e o motor de progressão Tri-Scale com relógios narrativos.

---

## 1. Topologia Canônica da Campanha (`campaigns/<campaign_id>/`)

Cada campanha reside exclusivamente em sua pasta em `campaigns/<campaign_id>/` contendo 5 arquivos Markdown fundamentais:

```
campaigns/<campaign_id>/
├── ficha.md       # Estado do Protagonista (Vitais, Atributos, Habilidades, Inventário)
├── diario.md      # Crônica Viva (Cena Ativa, Relógios de Facção, Histórico de Turnos)
├── npcs.md        # Catálogo Completo de NPCs (Perfis Psicológicos, Vontades e Atritos)
├── mundo.md       # Cenário (Geografia, Facções, Linha do Tempo Canônica, Leis Sociais)
└── regras.md      # Arbitragem (CDs de referência, economia de recursos e leis da mesa)
```

> [!IMPORTANT]
> **FONTE ÚNICA DA VERDADE (ZERO ARQUIVOS PARALELOS):**
> Nunca crie arquivos `.json` de estado ou `.archive.md` paralelos. Toda a persistência é feita exclusivamente nestes arquivos `.md`, garantindo legibilidade humana e ingestão no `ai-memory`.

### Inicialização Padronizada via Templates (`templates/` e `init-campaign`)
Para garantir conformidade imediata com o auditor SSOT (`CLEAN`), existe um diretório canônico de templates em `templates/`:
- `templates/ficha.template.md`
- `templates/diario.template.md`
- `templates/npcs.template.md`
- `templates/mundo.template.md`
- `templates/regras.template.md`

Ao iniciar uma nova campanha, utilize o comando canônico do CLI:
```powershell
python lazy_turn.py init-campaign --campaign <campaign_id> --title "Título da Campanha"
```
Isso gera automaticamente os 5 arquivos com todos os 8 campos canônicos de NPC, relógios pré-configurados e vitais perfeitamente sincronizados.

---

## 2. Anatomia dos Arquivos Markdown

### `ficha.md` (Vitais, Atributos, Vínculos e Marcos Pessoais)
```markdown
# Ficha do Protagonista: Nome

### Identidade
* **Nome:** Nome do Personagem
* **Conceito / Arquétipo:** Descrição sucinta

### Vitais & Recursos
* **HP:** 25 / 25
* **Stamina:** 20 / 20
* **Energia / Magia:** 30 / 30

### Atributos
* **FOR:** 12
* **DES:** 14
* **CON:** 14
* **INT:** 13
* **VON:** 13
* **MAG:** 15

### Vínculos, Laços & Reputação
* **Aliados & Mentores:** [Aliado]: Respeito mútuo forjado em combate.
* **Rivais & Desafetos:** [Rival]: Divergência de métodos e disputa por território.
* **Reputação com Facções:** [Facção A] (Neutro), [Facção B] (Sob Suspeita).

### Marcos de Evolução Pessoal (Milestones do Protagonista)
* **Marco 1:** [Turno 1]: Superou o incidente inicial e assumiu a liderança.
```

### `diario.md` (Cabeçalho de Cena, Relógios, Marcos e Histórico)
```markdown
# Diário da Crônica: Título da Campanha

## Cena 1: Nome da Cena
* **Data & Local:** 08 de Junho de 2018, 23:15 — Tóquio, Docas de Shibaura.
* **Presentes:** Nome, Aliado, Rival.
* **Fatos:** Situação inicial da cena.
* **Vitais:** HP 25/25, Stamina 20/20, Energia / Magia 30/30.

### Relógios de Ameaça & Prazos
* **[Conspiração do Clã]:** 2/4 (Gatilho: Golpe de Estado na assembleia) [ACTIVE]

### Arco Dramático Ativo
* **Título:** Arco 1: O Despertar
* **Pergunta Central:** Como os protagonistas conterão a oposição inicial?
* **Fase:** Preparação

### Planejamento de Trama & Fila de Cenas
* **Fila de Cenas Agendadas:**
  * [ ] **[interlude]** (Atores: Antagonistas): Conspiração de bastidores ou avanço de planos sem a presença do protagonista.
* **Marcos Futuros do Arco:**
  * Ruptura das defesas no porto e revelação da conspiração.

### Marcos da Crônica (Histórico de Arcos & Milestones)
* **Marco 0 (Prólogo):** [08 de Junho de 2018, 23:15]: Incidente nas docas de Shibaura.

### Histórico de Turnos
* **Turno 1:** Resumo factual da ação e consequência. Vitais: HP 25/25, Stamina 18/20, Energia / Magia 28/30.
  * **Mudança de Estado:** Guarda do galpão nocauteado; alarme silenciado.
```

---

## 3. Protocolo de Sessão Zero: Pesquisa Web para Obras Conhecidas

Quando o jogador iniciar uma campanha baseada em **obra existente** (anime, mangá, livro, filme, jogo ou período histórico):

1. **Pesquisa Prévia Obrigatória (`search_web` / `read_url_content`):**
   - **Cronologia & Linha do Tempo:** Descubra as datas exatas (dia, mês e ano) dos eventos do cânone. A data inicial em `diario.md` **deve ser anterior** aos arcos futuros para evitar o paradoxo temporal (`TEMPORAL_PARADOX`). Registre a cronologia em `mundo.md`.
   - **Barreira de Conhecimento por Arco:** Documente em `mundo.md` e `npcs.md` quais identidades, planos e artefatos ainda são segredo naquele momento da história.
   - **Terminologia & Facções:** Valide termos técnicos, patentes e poderes da obra.
2. **Criação Inicial Fora do Loop de Turnos:**
   - Execute no Modo Arquiteto (`--mode architect`). A criação de lore inicial não consome turnos de jogo.

---

## 4. O Motor Tri-Scale & Relógios Narrativos (`lazy_turn.py clock`)

Para impedir que a narrativa ande em círculos, a campanha opera em três escalas dinâmicas:

1. **Escala de Cena:** O conflito local imediato (resolvido a cada turno com mudança tangível de estado).
2. **Escala de Arco:** A pergunta dramática central da saga (`Preparação` $\to$ `Confrontação` $\to$ `Clímax`).
3. **Escala de Mundo (Relógios de Facção):** O avanço dos planos de vilões e aliados fora da visão do protagonista.

### Comandos de Relógio (`lazy_turn.py clock`):
```powershell
# Listar relógios da campanha:
python lazy_turn.py clock --campaign <id> --list

# Cadastrar novo relógio com gatilho claro:
python lazy_turn.py clock --campaign <id> --add "Ritual do Culto" --max 4 --trigger "Invocação da entidade no templo"

# Avançar segmentos:
python lazy_turn.py clock --campaign <id> --advance "Ritual do Culto" --steps 1

# Marcar como resolvido ou desarmado:
python lazy_turn.py clock --campaign <id> --resolve "Ritual do Culto"
```

---

## 5. Ciclo de Vida do Turno: Leitura, Gravação e Auditoria

- **Leitura Segura (`prepare`):** Lê `ficha.md`, `diario.md` e `npcs.md` de forma atômica e roda pré-auditoria contra descompassos e paradoxos.
- **Gravação Atômica (`commit`):**
  - Deduz vitais em `ficha.md` conforme `--cost`.
  - Em `--scene-type timeskip`, se não houver dano explícito, restaura automaticamente os recursos vitais ao máximo.
  - Avança o calendário em minutos (`+15m`, `+2h`) ou intervalos temporais (`+14d`, `+2m`, `+1y`).
  - Avança relógios com `--clock-advance "Nome:Passos"`.
  - Registra a mudança tangível de estado com `--state-shift`.
  - Anexa o turno ao `diario.md` com a tag apropriada (`[INTERLÚDIO]`, `[SALTO TEMPORAL]`, `[DOSSIÊ]`, etc.).
  - Executa auditoria automática pós-commit (`CLEAN`).
- **Auditoria Dedicada (`review`):**
  - Detecta dessincronia de vitais (`VITALS_DESYNC`), anomalias em perfis de NPC (`INCOMPLETE_NPC_PROFILE`), saltos de turnos (`TURN_SEQUENCE_GAP`), relógios rompidos (`CLOCK_BREACHED`), inércia narrativa (`NARRATIVE_STAGNATION`), ausência de relógios ativos no arco (`MISSING_ACTIVE_CLOCKS`) e fadiga de ritmo linear (`PACING_FATIGUE`).

---

## 6. Planejamento de Trama & Modo Diretor (`lazy_turn.py plan`)

Para combater a condução passiva e reativa do Mestre, o motor conta com um gerenciador de fila de cenas integrado ao `diario.md`:

```powershell
# Listar plano de trama, marcos futuros e status de ritmo:
python lazy_turn.py plan --campaign <id> --list

# Agendar uma nova cena na fila (interlúdio, dossiê, timeskip, etc.):
python lazy_turn.py plan --campaign <id> --add "Conspiração de rivais nos bastidores" --scene-type interlude --actors "Antagonista A, Antagonista B"

# Adicionar um novo marco futuro ao arco:
python lazy_turn.py plan --campaign <id> --milestone "Confronto na torre do relógio antes do solstício"

# Marcar uma cena da fila como concluída:
python lazy_turn.py plan --campaign <id> --complete 0
```

Quando houver uma cena agendada pendente, o `lazy_turn.py prepare` notificará o Mestre no payload com a recomendação da próxima quebra de perspectiva. Caso ocorram 4 ou mais turnos padrão consecutivos em tempo real, o motor acionará o alerta de `FADIGA DE RITMO LINEAR`, exigindo proatividade do Mestre.
