# Regras de Arbitragem & Sistema de Poder: Crônicas de Valíria: O Filho de Krypton

## 1. Calibração Diegética de Dificuldade & Overrides (Grau 2)
A escala mecânica de resolução adota o padrão universal do framework (Grau 1: DC 10 Fácil, DC 15 Média, DC 20 Difícil, DC 25 Extrema). Neste cenário específico, as faixas de desafio ancoram-se nas seguintes realidades diegéticas:

* **Pressão Leve (Faixa 10):** Manobras de esgrima simples, salto sobre terrenos acidentados ou intimidação de adversários sem experiência militar.
* **Conflito Severo (Faixa 15):** Romper armaduras encantadas por mana, resistir ao impacto de feitiços de impacto médio ou convencer matriarcas desconfiadas.
* **Elite do Cenário (Faixa 20):** Duelo direto contra Comandantes de Esquadrão das Lâminas de Éter, matriarcas alfa bestiais ou demônios de alto escalão.
* **Calamidade / Feito Lendário (Faixa 25):** Proezas sobre-humanas cósmicas, erguer estruturas de dezenas de toneladas, resistir a bombardeios de cerco ou suplantar a vontade de divindades arcanas.

```yaml
system: d20_3gates
overrides:
  - id: mana_sensor_immunity
    type: immunity
    target: mana_detection
    value: true
    condition: "Artefatos de medição mágica leem Kon-El como valor zero (ausência de mana)"
  - id: torquasm_vo_defense
    type: resistance
    target: mental_influence
    value: immune
    condition: "Imunidade inata a encantos de submissão e feromônios de domínio via disciplina mental kryptoniana"
```

---

## 2. Economia de Recursos & Fisiologia Kryptoniana
* **HP (Pontos de Vida):** Integridade tecidual e densidade celular kryptoniana. Dano letal só é infligido por armas de pureza abissal extrema, magia de corte conceitual ou impacto de tonelagem sísmica.
* **Stamina:** Vigor celular e fôlego muscular. Praticamente inesgotável sob radiação estelar direta, mas consumido em esforços contínuos de aceleração extrema.
* **Bioenergia Solar (RAD):** Reserva de radiação armazenada na matriz celular de Kon-El. Alimenta surtos de aceleração, visão térmica incipiente, saltos maciços e regeneração celular acelerada. Não emite circuitos de mana.

---

## 3. Leis Especiais de Arbitragem (Grau 2 - Diegese)
* **A Falácia do Sensor de Mana:** Todo feitiço, artefato ou cristal que meça auras arcanas registrará Kon-El como tendo valor zero. Isso leva as guerreiras locais a subestimarem grosseiramente sua resistência, assumindo que ele é frágil e vulnerável até testemunharem o choque de seus golpes físicos.
* **Torquasm-Vo & Defesa Psíquica:** Kon-El possui imunidade inata a encantos de submissão, feromônios de domínio e feitiços de charme cortesão através da disciplina meditativa nativa de Krypton.
