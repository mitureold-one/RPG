# Módulo 2: Mecânica de Dados & Arbitragem (Modelo de 3 Portões)

Este documento é a **autoridade única e soberana** sobre testes, probabilidades, cálculo de dificuldades (DC), variantes e regras de arbitragem mecânica imparcial.

---

## 1. Quando Rolar Dados?

* **Ações sem Resistência / Cotidianas (`--no-roll`):** Movimentação comum, observação desimpedida ou diálogos sem coação/engano não exigem dados.
* **Ações sob Pressão, Risco ou Oposição:** Ataques, manobras de esquiva, uso de habilidades místicas sob atrito, furtividade contra guardas ou intimidação exigem resolução determinística via `lazy_turn.py prepare` para garantir imparcialidade (*anti-sycophancy*).

---

## 2. A Arquitetura dos 3 Portões (`3-Gate Roll Model`)

O `lazy_turn.py prepare` resolve a mecânica combinando três etapas determinísticas:

```
[Portão 1: Circunstância] ──► [Portão 2: Dados (1d20/2d20)] ──► [Portão 3: Modificador + DC]
 (normal / adv / disadv)          (Mantém maior/menor)              (Total vs DC -> Tier)
```

1. **Portão 1 — Circunstância (`--variant`):**
   * `normal`: Rolagem padrão (`1d20`).
   * `advantage` (`adv`): Posição tática superior, emboscada, fraqueza explorada do adversário ou terreno favorável (`2d20`, mantém o maior).
   * `disadvantage` (`disadv`): Ferimento grave, exaustão física, cegueira momentânea ou desvantagem de terreno (`2d20`, mantém o menor).
2. **Portão 2 — Atributo Testado (`--stat`):**
   * Consulta a `ficha.md` (`FOR`, `DES`, `CON`, `INT`, `VON`, `MAG`) e extrai o modificador:
     $$\text{Modificador} = \lfloor(\text{Valor} - 10) / 2\rfloor$$
3. **Portão 3 — Comparação com DC (`--dc`):**
   * Compara o $\text{Total} = \text{Dado} + \text{Modificador}$ com a Classe de Dificuldade para determinar o desfecho.

---

## 3. Escala Canônica de Dificuldades (DC)

| Dificuldade | DC | Cenário Típico de Aplicação |
| :--- | :---: | :--- |
| **Fácil** | **10** | Ações sob leve pressão; esquivar de golpe telegrafado; intimidar capanga despreparado. |
| **Média** | **15** | Combate contra combatente treinado; manobra acrobática em terreno instável; concentração sob dor. |
| **Difícil** | **20** | Confronto contra a elite; resistir a técnica devastadora à queima-roupa; quebrar selo complexo. |
| **Extrema** | **25** | Feito quase milagroso; reagir a anomalia cósmica, calamidade natural ou técnica suprema. |

---

## 4. Tiers de Desfecho & Consequências Obrigatórias

O resultado do dado rege imperativamente a **Batida 3 da Prosa** e a **Diretriz de Custo**:

* **Dádiva / Triunfo Crítico (`20 natural` ou $\text{Total} \ge \text{DC} + 5$):**
  * Sucesso retumbante. O objetivo é alcançado com impacto superior e abertura de vantagem tática gratuita.
* **Sucesso Pleno ($\text{Total} \ge \text{DC}$):**
  * O objetivo é cumprido conforme pretendido, pagando apenas os custos normais da ação (se houver).
* **Sucesso com Custo ($\text{DC} - 4 \le \text{Total} < \text{DC}$):**
  * Sucesso parcial com complicação imediata: o golpe acerta mas o inimigo contra-ataca, a porta abre mas faz barulho, ou gasta-se recurso extra de vitais.
* **Falha ($\text{Total} < \text{DC} - 4$):**
  * Revés direto. A ação é bloqueada, desviada ou ineficaz, e a iniciativa/vantagem passa para a oposição.
* **Catástrofe (`1 natural` ou $\text{Total} \le \text{DC} - 5$):**
  * Desastre crítico. Dano substancial sofrido, perda de equipamento, armadilha disparada ou situação dramaticamente piorada.

---

## 5. Disputas Opostas de Dados (PC vs NPC e NPC vs NPC)

Quando ocorre um confronto direto de vontades, espadas, debate político ou autoridade — seja entre o protagonista e um NPC, seja **entre dois NPCs** nos bastidores ou em cena aberta —, a mecânica escala para uma **Disputa Oposta de Dados**:

```powershell
# Confronto Protagonista vs NPC:
python lazy_turn.py prepare --campaign <id> --action "<ação>" --stat <ATTR> --contest-npc "<Nome_NPC>" [--npc-stat <Eixo>]

# Confronto Horizontal entre dois NPCs (Triangulação Autônoma / Interlúdios):
python lazy_turn.py prepare --campaign <id> --action "<cena/confronto>" --contest-npc "<NPC_1>" --vs-npc "<NPC_2>" [--npc-stat <Eixo_1>] [--vs-stat <Eixo_2>]
# Ou sintaxe equivalente:
python lazy_turn.py prepare --campaign <id> --action "<cena/confronto>" --contest-npc "<NPC_1> vs <NPC_2>"
```

### Resolução Determinística (Delta = Total A - Total B):
* **Modificadores dos NPCs:** Extraídos agnosticamente de `npcs.md` através dos eixos psicológicos do Hexágono (`Composure`, `Boldness`, `Drive`, `Diligence`, `Warmth`, `Empathy`) ou classificação de Grau de elite.
* **Dádiva / Triunfo Esmagador de A (`Delta >= +8` ou `A nat 20`):** Domínio absoluto de A; B perde a posição, recua desestabilizado(a) ou cede incondicionalmente.
* **Vitória de A (`Delta entre +1 e +7`):** Sucesso de A; com atrito tático se $Delta \le 3$.
* **Impasse Tenso (`Delta == 0`):** Choque de forças idêntico; espadas travadas ou debate insolúvel; tensão mútua elevada ao ápice.
* **Resistência Vitoriosa de B (`Delta entre -1 e -7`):** B frustra a investida de A, mantém a guarda e contra-ataca; B ganha vantagem de posicionamento/argumentação.
* **Catástrofe de A / Triunfo Esmagador de B (`Delta <= -8` ou `B nat 20` ou `A nat 1`):** B subjuga completamente a manobra de A, impõe seus termos e vira o rumo da cena.

> [!NOTE]
> Em disputas **NPC vs NPC**, o resultado mecânico não deduz recursos do protagonista. O vencedor ganha a dianteira dramática, altera a balança de poder entre facções e ambos os NPCs recebem atualizações obrigatórias de atitude no template pós-turno (`--npc-updates`).

> [!CRITICAL]
> **LEI DA IMPARCIALIDADE:** O Mestre jamais "suaviza" uma Catástrofe por simpatia ao jogador nem "anula" uma Dádiva para proteger os planos da trama. O dado define a verdade mecânica.
