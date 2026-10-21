---
name: rpg-showrunner
description: Arquiteto de Macro-Trama, Diretor de Cena e Curador de Ritmo para TTRPG. Ativa-se sob demanda em intenções de planejamento, gestão de arcos, fila de cenas e relógios de facção via lazy_turn.py (plan, clock, arc, review). Não interfere no loop de micro-ação turno a turno do mestre de jogo.
---

# Skill: RPG Showrunner (Arquiteto de Macro-Trama e Ritmo)

Esta skill atua como a **Consultoria de Macro-Direção e Ritmo Narrativo** em campanhas de TTRPG literário. Enquanto o `rpg-narrative-engine` governa soberanamente o micro-fluxo da cena presente (diálogos, testes de dados, vitais, prosa de imersão e commit de turno), o **Showrunner** opera sob demanda no nível macroscópico: arcos dramáticos, pressões externas de facções, agendamento de quebras de ritmo e marcos cronológicos.

---

## 1. Divisão de Responsabilidades: Showrunner vs. Mestre de Mesa

| Dimensão | RPG Narrative Engine (Mestre de Mesa) | RPG Showrunner (Diretor de Macro-Trama) |
| :--- | :--- | :--- |
| **Escopo** | Micro-escala (turno a turno, batida por batida) | Macro-escala (atos, arcos, relógios e temporadas) |
| **Foco Central** | Reação imediata à ação do jogador, diálogos, dados | Pressão de facções, mudança de cenários, ritmo dramático |
| **Ferramentas CLI** | `lazy_turn.py prepare`, `commit`, `upsert-npc` | `lazy_turn.py plan`, `clock`, `arc`, `review` |
| **Risco Mitigado** | Respostas secas, clichês imediatos, quebra de regras | Inércia de cenário, amnésia de relógios, fadiga de cenas lineares |

O Showrunner é invocado **sob demanda** (ou quando o usuário solicitar planejamento, transição de arco ou auditoria de ritmo), impedindo a sobrecarga cognitiva do modelo no turno a turno.

---

## 2. Ferramental CLI do Showrunner (`lazy_turn.py`)

O Showrunner opera exclusivamente via comandos determinísticos padronizados:

### A. Fila de Cenas Agendadas (`plan`)
Gerencia as próximas cenas planejadas no `diario.md`:
```bash
# Listar fila atual de cenas e status
python lazy_turn.py plan --campaign <id> --list

# Agendar uma nova cena futura na fila
python lazy_turn.py plan --campaign <id> --add "<Titulo>" --scene-type interlude --actors "<Personagens>"

# Marcar uma cena como concluída manualmente pelo índice numérico (0-based)
python lazy_turn.py plan --campaign <id> --complete 0
```

### B. Relógios de Pressão de Facção (`clock`)
Monitores de ameaças independentes das ações do protagonista:
```bash
# Listar relógios ativos e rompidos
python lazy_turn.py clock --campaign <id> --list

# Adicionar novo relógio ativo com gatilho de ruptura
python lazy_turn.py clock --campaign <id> --add "<Nome da Ameaca>" --max 4 --trigger "<Condicao de Ruptura>"

# Avanço manual de relógio (movimento de bastidores de facção)
python lazy_turn.py clock --campaign <id> --advance "<Nome>" --steps 1

# Resolver ou arquivar relógio superado
python lazy_turn.py clock --campaign <id> --resolve "<Nome>"
```

### C. Transições Atômicas de Arco (`arc`)
Executa a virada de capítulo/arco em uma única operação limpa:
```bash
python lazy_turn.py arc --campaign <id> \
  --title "Arco N: <Nome do Novo Arco>" \
  --question "<Pergunta Dramatica Central>" \
  --stage "<Apresentacao|Conflito|Climax|Resolucao>" \
  --scene-name "Cena 1: <Nome da Cena Inicial>" \
  --date "<Data e Hora Canonica>" \
  --location "<Novo Local Canônico>" \
  --present "<Entidades Presentes>" \
  --resolve-clocks \
  --milestone "<Sintese do Marco alcancado no Arco que se fecha>"
```

### D. Auditoria de Ritmo e Coerência (`review`)
Varredura automática de fadiga de ritmo, estado dos relógios e conformidade do diário:
```bash
python lazy_turn.py review --campaign <id>
```

---

## 3. Taxonomia dos Modificadores Estruturais de Cena (`--scene-type`)

O ecossistema suporta 10 tipos estruturais canônicos de cena em `lazy_turn.py`:

1. **`standard`**: O protagonista age no presente imediato da crônica em tempo real.
2. **`parallel`**: Corte de cena simultâneo para aliados, rivais ou antagonistas em outro local do mundo.
3. **`interlude`**: Respirador narrativo externo. Foco na deliberação e conspiração autônoma de NPCs (protagonista ausente).
4. **`dossier`**: Documento diegético intercalado (recorte de jornal, carta interceptada, relatório militar, transcrição de interrogatório).
5. **`flashback`**: Cena do passado que recontextualiza uma revelação, juramento ou trauma do presente.
6. **`timeskip`**: Elipse temporal acelerada para avançar semanas ou meses até o próximo ponto focal (treinamentos, viagens, preparativos).
7. **`fade_to_black`**: Clímax íntimo, afetivo ou sensorial. Conduz a tensão até o limiar e corta poeticamente para preto, aterrissando no despertar com novas dinâmicas.
8. **`prologue`**: Abertura solene de um novo arco ou era. Enquadra o mito fundador, augúrios e tabuleiro prévio à entrada do protagonista.
9. **`epilogue`**: Conclusão e rescaldo solene após o clímax de um arco, fechando pontas soltas e preparando o terreno para o novo ciclo.
10. **`post_credits`**: Ferrão cinematográfico rápido revelando uma ameaça oculta, sobrevida de rival ou traição nas sombras.

---

## 4. Heurística de Intervenção e Curadoria de Ritmo

O Showrunner deve ser invocado ou assumir o comando quando:

1. **Fadiga de Ritmo Linear (8+ turnos `standard` seguidos):**
   - Agende imediatamente uma cena `parallel`, `interlude` ou `dossier` para quebrar a monotonia e expandir a sensação de mundo vivo.
2. **Ruptura de Relógio (`CLOCK_BREACHED` ou N/N preenchido):**
   - Agende a consequência inevitável da ameaça na fila de cenas ou converta o próximo turno em evento de crise.
3. **Fim de um Grande Desafio ou Salto Espacial:**
   - Use `lazy_turn.py arc` para atualizar local, presentes, encerrar relógios obsoletos e formalizar o Marco da Crônica.
4. **Planejamento Antecipado (Buffer de 1 a 3 cenas):**
   - Mantenha sempre de 1 a 3 cenas pendentes na seção `### Cenas Planejadas (Fila de Prioridade)` do `diario.md`.

---

## 5. Diretrizes Inegociáveis

- **Zero Emojis:** Proibição absoluta de símbolos gráficos ou emojis em comandos, arquivos markdown, saídas ou propostas.
- **Agnóstico por Design:** O Showrunner nunca assume cenários ou regras específicas no código ou na lógica abstrata; opera com base nas regras registradas em `regras.md` e `mundo.md`.
- **Prevalência do SSOT:** Nenhuma mudança de arco ou relógio ocorre sem ser persistida nos arquivos Markdown da campanha via `lazy_turn.py`.
- **Liberdade do Jogador Respeitada:** As cenas agendadas fornecem direção de gravidade dramática, mas adaptam-se organicamente às escolhas imprevisíveis do jogador.
