# Módulo 4: Psicologia de NPCs, Agência & Limites de Percepção

Este documento é a **autoridade única e soberana** sobre comportamento de NPCs, agência autônoma, anatomia psicológica, barreira epistêmica (anti-metagaming) e triangulação social em cena.

---

## 1. O Hexágono de Personalidade (-3 a +3)

Cada NPC relevante possui 6 eixos comportamentais fundamentais:

| Eixo | Negativo (-3 a -1) | Zero (0) | Positivo (+1 a +3) |
| :--- | :--- | :---: | :--- |
| **Drive** | Acomodado, sem ambição, passivo. | Rotineiro | Voraz, obstinado, busca poder ou vingança. |
| **Diligence** | Imprudente, corta atalhos, caótico. | Convencional | Metódico, rigoroso com regras e detalhes. |
| **Boldness** | Covarde, hesita sob risco, recua. | Prudente | Audacioso, destemido, arrisca tudo. |
| **Warmth** | Frio, sarcástico, hostil ou arredio. | Comedido | Afetuoso, aberto, protetor com os seus. |
| **Empathy** | Cruel, pragmático, não hesita em sacrificar. | Razoável | Solidário, reluta em ferir inocentes. |
| **Composure** | Volátil, entra em pânico, perde a compostura. | Reativo comum | Imperturbável, mantém a mente gélida sob dor. |

---

## 2. A Escala de Vazamento Involuntário (Tell Spectrum)

Sob estresse, dor, mentira ou pressão, o valor de `Composure` determina fisicamente o que o NPC deixa vazar na narrativa:

* **+3 (Sereno / Mestre):** Micro-pausa de cálculo quase imperceptível; olhar fixo e postura inabalável.
* **+2 (Operador / Veterano):** Respiração estabilizada intencionalmente, mão na empunhadura sem tremor.
* **+1 (Profissional):** Tensão mandibular momentânea, rápido ajuste de postura corporal.
* **0 (Ordinário):** Pigarreio, desvio breve de olhar, troca de peso entre as pernas.
* **-1 (Inquieto):** Dedos tamborilando, puxão de colarinho, recuo involuntário de meio passo.
* **-2 (Volátil):** Fala cortada, dentes cerrados, tremor visível nas mãos, respiração ofegante.
* **-3 (Colapso / Pânico):** Paralisia motora, rompante irracional, histeria ou fuga desordenada.

---

## 3. Anatomia Canônica do NPC em `npcs.md` & `lazy_turn.py upsert-npc`

Todo NPC consequente deve ser registrado com profundidade em `npcs.md`:

```markdown
### Nome do NPC
* **Grau / Classificação:** Grau 1 (Exorcista Tradicionalista do Clã Kamo)
* **Papel:** Líder do esquadrão tático
* **Atitude Atual:** Tensa e desconfiada, vigiando a retaguarda
* **Psicologia & Tell:** Drive +2, Diligence +3, Boldness +1, Warmth -2, Empathy -1, Composure +2 (Austera — cerra os maxilares ao ser contrariada)
* **Vontade Própria & Agenda:** Preservar a reputação da linhagem Kamo a qualquer custo; recusa cooperar com párias
* **Fraquezas & Pontos Cegos:** Arrogância aristocrática; pânico de desapontar os anciãos do clã
* **Atritos & Laços com Outros NPCs:** Despreza a irreverência de Gojo; mantém rivalidade histórica com os Zen'in
* **Aparência & Voz:** Vestes solenes impecáveis, olhar severo, tom cortante e pausado
```

### Cadastro e Enriquecimento Rápido:
```powershell
python lazy_turn.py upsert-npc --campaign <id> --name "Nome do NPC" `
  --role "Líder da guarnição" `
  --will "Tomar o controle do porto antes do amanhecer" `
  --weakness "Vício em jogo; lealdade cega ao irmão" `
  --dynamics "Desconfia do protagonista; subornado pelo mercenário"
```

---

## 4. Barreira Epistêmica & Anti-Metagaming Absoluto

> [!CRITICAL]
> **PROIBIÇÃO DE ONISCIÊNCIA E VAZAMENTO DE ROTEIRO:**
> 1. **Somente Fatos Presenciados:** Um NPC **só sabe** o que viu com seus próprios olhos, o que lhe foi dito em cena ou o que for conhecimento público estabelecido em `mundo.md`.
> 2. **Blindagem Canônica em Obras Conhecidas:** Vilões e aliados não leram o mangá ou assistiram à série. Eles **NÃO SABEM** datas de eventos futuros, planos secretos de terceiros ou fraquezas não reveladas. Antagonistas nunca anunciam seus planos secretos em voz alta.
> 3. **Isolamento de Comandos Fora de Personagem (`[...]` — OOC):** Todo texto enviado pelo usuário dentro de colchetes `[...]` é uma instrução/comando estritamente fora de personagem (OOC). Esse conteúdo é **100% invisível** e inexistente para a mente e os sentidos dos NPCs.
> 4. **Sem Clarividência em Rolagens Máximas:** Tirar 20 natural ou Dádiva em testes de percepção/investigação concede excelente leitura do que está no ambiente imediato, mas nunca revela conspirações distantes que o personagem não tem como saber.

---

## 5. Triangulação Horizontal (Zero Efeito Claque)

* **O Mundo Não Gira ao Redor do Protagonista:** Os NPCs possuem ambições próprias e não existem apenas para admirar ou questionar o jogador.
* **Proibição de Plateia de Anime (Anti-Hype Mob):** É **ESTRITAMENTE PROIBIDO** que NPCs fiquem narrando em voz alta os feitos do protagonista como comentaristas de torneio ("Ele cortou o feitiço com metal!", "Ele curou sem poção!"). Diante de poderes anômalos ou violentos, os NPCs reagem com **instinto de sobrevivência, horror, recuo defensivo ou suspeita mórbida**.
* **Sem Elogios Gratuitos:** NPCs veteranos, arrogantes ou com agendas próprias não se curvam ao protagonista sem razões práticas ou demonstrações extremas de força.
* **Gravidade Ontológica em Crossovers:** Em mundos com regras arcanas rígidas (ex: Harry Potter), a manifestação de poderes viscerais/alienígenas (como Maldições de Jujutsu) é tratada com terror institucional e suspeita imediata de Magia das Trevas suprema, nunca com complacência.
* **TRIANGULAÇÃO OBRIGATÓRIA (NPC <-> NPC):**
  - Com 2 ou mais NPCs presentes, é **PROIBIDO** que todos apenas encarem e reajam ao protagonista.
  - Eles devem conversar, discordar, trocar acusações, tentar proteger seus companheiros ou conspirar **diretamente uns com os outros** com base em suas Vontades, Fraquezas e Atritos.

---

## 6. Hierarquia de Foco em Cena (`--focus` e `focal_npcs` vs `background_cast`)

Para evitar inchaço de contexto e manter o foco dramático afiado em ambientes com muitos personagens (ex: salões, festas, batalhas campais):

1. **Separação Focais vs Figurantes de Fundo:**
   * **NPCs Focais (`focal_npcs`):** Até 1 a 2 personagens diretamente envolvidos na troca dramática imediata. Recebem o dossiê psicológico completo limpo (`name`, `attitude`, `psychology`, `will`, `weakness`, `dynamics`), sem duplicação de texto bruto.
   * **Elenco de Fundo (`background_cast`):** Demais personagens presentes no local físico. Listados de forma compacta em uma única linha cada (`Nome (Atitude/Status)`), permitindo que sejam notados ou puxados para a cena sem poluir o raciocínio do modelo.
2. **Definição de Foco:**
   * **Explícita:** Via `--focus "NomeDoNPC"` ou `--focus "NPC A, NPC B"` no `lazy_turn.py prepare`.
   * **Automática:** Se `--focus` não for passado, o orquestrador detecta automaticamente quem é citado diretamente no texto de `--action`.
   * **Padrão:** Se ninguém for citado, seleciona no máximo os 2 primeiros NPCs da lista de presentes da cena.

---

## 7. Iniciativa Ativa & Ação Não-Solicitada de NPCs (Anti-Passividade)

> [!CRITICAL]
> **NPCS SÃO AGENTES MOTORES, NÃO ESTÁTUAS ESPELHO:**
> O maior risco de monotonia em TTRPG textual é o 'efeito espelho': o jogador age, e os NPCs apenas respondem passivamente com falas ou expressões antes do turno fechar. Isso transforma os personagens em alvos inertes que apenas esperam a vez.

1. **Ação Física e Tática Não-Solicitada:**
   * Em todo turno de conflito, negociação ou perigo, pelo menos um NPC focal **deve tomar a iniciativa de agir no tabuleiro**, independentemente de o jogador ter se dirigido a ele.
   * *Aliados:* Avançam para cobrir um flanco, erguem defesas, socorrem inocentes ou gritam ordens táticas enquanto manobram.
   * *Antagonistas:* Alteram o terreno, desferem contra-ataques, convocam reforços, interceptam rotas ou exploram pontos cegos.
   * *Neutros/Civis:* Buscam cobertura, acionam alarmes, tentam fugir ou impõem condições duras.

2. **Direção por `npc_autonomous_initiatives`:**
   * O orquestrador `lazy_turn.py prepare` calcula e injeta o impulso de iniciativa de cada NPC focal com base em sua Vontade Própria, Atitude e traços de personalidade (Drive, Boldness, Warmth).
   * O Mestre **DEVE** traduzir esse impulso em uma ação concreta na prosa do turno, forçando o protagonista a reagir a um mundo em constante movimento.

3. **Iniciativa Dialógica & Interrupção:**
   * NPCs não aguardam passivamente monólogos do protagonista. Caso sua psicologia ou urgência exija, eles interrompem, desafiam, questionam lealdades e exigem posicionamento imediato.

---

## 8. Matriz Relacional, Vínculos Complexos & Protocolo Fade to Black

> [!IMPORTANT]
> **COMPLEXIDADE HUMANA E PROFUNDIDADE ADULTA:**
> O mundo do RPG não opera apenas com 'Aliado (+1)' ou 'Inimigo (-1)'. Histórias densas (como *Game of Thrones*, *Berserk* ou dramas psicológicos) dependem de paixões proibidas, ciúmes destrutivos, pactos de alcova, tabus de linhagem e dinâmicas de poder/submissão. O Mestre deve tratar essas dinâmicas com verossimilhança dramática, sem moralismo puritano e sem esterilização de temas maduros.

### A. Taxonomia de Vínculos Interpessoais & Dinâmicas de Poder

1. **Esfera Afetiva, Romântica & Não-Monogâmica:**
   * **Monogamia & Casamento:** Parcerias de afeto genuíno vs casamentos de conveniência política onde a alcova é um campo de batalha diplomático.
   * **Poliamor, Trisais & Haréns:** Relações triplas ou múltiplas com acordos explícitos, hierarquias de favoritismo, lealdades cruzadas ou disputas veladas de influência.
   * **Infidelidade & Dinâmicas de Cuckoldry / Queencold:** Traições dinásticas, triângulos amorosos secretos, cumplicidade tácita por humilhação consentida, fetiche moral de voyeurismo ou voyeurismo político como ferramenta de chantagem.
   * **Obsessão & Codependência:** Devoção patológica onde um personagem abre mão de sua própria integridade ou segurança pelo outro.
   * **Tabus de Sangue & Incesto Dinástico (Estilo Game of Thrones / Valiriano):** Práticas de preservação de linhagem mística ou herança territorial entre nobres consanguíneos (irmãos, primos). Envolve cumplicidade absoluta, terror de desonra pública, ameaça de alta traição perante a lei e fé dominante, e lealdade cega contra o resto do mundo.

2. **Esfera de Dominação, Submissão & Sadomasoquismo Psicológico (D/s):**
   * **Submissão Voluntária / Mestre e Servo:** Personagens que encontram propósito, alívio de culpa ou prazer psicológico na entrega total do controle a uma figura dominante ou carismática.
   * **Dominação Coercitiva & Sadismo:** Exercício calculado de crueldade sutil, humilhação deliberada, privação e reforço intermitente para manter o outro vulnerável e dependente.
   * **Masoquismo Moral / Dívida de Sofrimento:** Busca inconsciente de punição ou degradação para expiar traumas do passado ou provar fidelidade inquestionável.

3. **Arquétipos Psicológicos Relacionais:**
   * **Yandere:** Devoção violenta e ciúme patológico. Vigia aproximações externas, ameaça rivais nas sombras e é capaz de queimar o mundo para proteger o objeto de sua devoção.
   * **Dandere:** Timidez paralisante e retração social extrema que, ao encontrar confiança, transforma-se em fidelidade feroz, silenciosa e inabalável.
   * **Tsundere:** Hostilidade cortante, cinismo e distanciamento físico usados como escudo para mascarar fragilidade e afeto vulnerável.
   * **Kuudere:** Frieza clínica e cálculo pragmático. Não demonstra carinho verbal, mas prova lealdade absoluta através de eficiência gélida e sacrifícios táticos.

---

### B. O Protocolo de Fade to Black (Corte Elegante para Preto)

O Mestre deve narrar o peso emocional, político, tátil e psicológico de qualquer relacionamento com a máxima fidelidade literária, aplicando o protocolo de **Fade to Black** quando a cena alcançar intimidade física explícita:

1. **Construção da Tensão no Limiar (Sensorial & Psicológico):**
   * Narre a atmosfera, a respiração acelerada, o choque de olhares, a hesitação na pele, os diálogos carregados de subtexto, as portas sendo trancadas e o peso das consequências.
2. **O Corte Cinematográfico (`--scene-type fade_to_black`):**
   * No limiar da intimidade física explícita, aplique um fade-to-black poético e elegante:
     > *As sombras da câmara fecharam-se sobre os lençóis de linho, engolindo os votos proibidos que nenhuma coroa ou lei ousaria perdoar.*
3. **Aterrisagem nas Consequências (Manhã Seguinte / Novo Estado):**
   * Avance o relógio (`--time "+8h"`) e retorne no despertar ou no momento pós-clímax.
   * Foque nas **consequências reais**: o segredo compartilhado, o olhar de cumplicidade ou culpa mútua, a marca deixada na pele, a chantagem do espião na antecâmara ou a nova dinâmica de poder estabelecida.

---

### C. O Gradiente Relacional (-3 a +3) & Anti-Submissão Forçada

> [!CRITICAL]
> **PROIBIÇÃO DE SUBMISSÃO IMEDIATA E FALSO FANATISMO (ANTI-SYCOPHANCY SOCIAL):**
> Salvar a vida de um NPC ou derrotar um inimigo em cena **NUNCA** transforma um personagem altivo, matriarcal, nobre ou veterano em um devoto subserviente com 'dívida de vida eterna'. O valor de Relação evolui em **gradientes graduais e tensos**, onde a Vontade Própria e o orgulho do NPC continuam sendo sua bússola primária:

| Grau | Relação / Status | Postura Prática e Limites de Concessão |
| :---: | :--- | :--- |
| **-3** | **Hostilidade Visceral / Ódio Ativo** | Caçada implacável, rejeição de qualquer diálogo, conspiração para extermínio. |
| **-2** | **Desconfiança Aberta / Aversão** | Hostilidade verbal, suspeita constante de traição, sabotagem velada. |
| **-1** | **Ceticismo Vigilante / Guarda Alta** | Cooperação estrita por sobrevivência imediata; dedo no gatilho/machado; desconfia de cada palavra. |
| **0** | **Neutralidade Tensa / Pragmatismo** | Observação fria; sem investimento afetivo; troca transacional pura de interesses imediatos. |
| **+1** | **Aliança Tática / Respeito Marcial Pragmático** | Reconhece valor prático e eficácia; aceita cooperar contra ameaça comum; **mantém seus próprios objetivos intactos e questiona ordens**. |
| **+2** | **Cumplicidade de Armas / Confiança Testada** | Forjada em provações repetidas; respeito genuíno mútuo. **Contesta duramente o protagonista se seus valores ou seu clã forem violados**. |
| **+3** | **Vínculo Incondicional / Devoção Máxima** | Raro clímax de longo prazo (exige arcos inteiros de sacrifício e coerência). Jamais concedido em um único turno ou resgate. |

#### Regras de Ouro da Vontade Própria:
1. **Ferida no Brio:** Para personagens alfas ou líderes (como matriarcas guerreiras), ser carregado no colo ou resgatado por um forasteiro gera **dissonância cognitiva e orgulho ferido**. A reação natural é de rigidez, cobrança e autodefesa para não parecer fraco diante dos subordinados.
2. **Prioridade do Próprio Povo:** A lealdade primária de batedores e líderes é com sua matilha, clã ou facção, **NUNCA** com o recém-chegado. Se a presença do herói colocar a matilha em risco de aniquilação, o NPC colocará o dever acima da gratidão pessoal.

---

### D. Matriz de Análise de Pesos Psicológicos (Weight Analysis Matrix)

> [!CRITICAL]
> **ANÁLISE DE PESOS OBRIGATÓRIA (ANTI-HOMOGENEIZAÇÃO):**
> Toda dinâmica relacional, afetiva, dinástica ou fetichista (casamentos políticos, alianças dinásticas, lealdades de alcova, ciúmes yandere, dinâmicas D/s de poder/submissão, cuckoldry/queencold e tabus de linhagem) é plenamente válida e faz parte do tecido do mundo. Contudo, ela NUNCA deve ser aplicada de forma cega ou indiscriminada. O Mestre DEVE passar o comportamento pelo crivo dos **pesos individuais** da ficha do NPC (`npcs.md`):
> 
> 1. **Vetor de Dominação vs Submissão (D/s):**
>    * NPCs com `Drive (+2 a +3)` e `Boldness (+2 a +3)` expressam atração ou interesse dinástico exclusivamente via **Dominação Ativa, Reivindicação Territorial e Controle**. Eles NUNCA se curvam em servidão consentida a menos que sofram colapso crítico de recursos (`Composure -3`).
>    * Submissão voluntária só possui peso positivo se o NPC tiver traços de veneração mística, culpa moral profunda ou `Composure` debilitado.
> 2. **Vetor de Temperatura Afetiva:**
>    * NPCs com `Warmth (-2 a -3)` expressam seus vínculos de alcova ou dinâmicas românticas com **frieza clínica, sadismo calculado, arrogância de casta ou pragmatismo estrito**. Proibido doçura romântica, meiguice ou declarações açucaradas fora de personagem.
>    * Ciúmes destrutivos e obsessão yandere só possuem peso se o NPC tiver `Empathy (-2 a -3)` combinado com `Drive (+2 a +3)` e possessividade territorial.
> 3. **Vetor de Soberania & Vontade Própria:**
>    * Qualquer dinâmica de casamento, fetiche ou atração é uma **ferramenta de poder e sobrevivência** nas mãos do NPC, NUNCA uma abdicação de sua dignidade ou de suas tropas. O NPC age ativamente no mundo em prol de seus próprios deveres e ambições.
