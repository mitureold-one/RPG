# Regras de Arbitragem & Sistema de Poder: Os Perpetuos: Terra Incognita

## 1. Calibração Diegética de Dificuldade & Overrides (Grau 2)
A escala mecânica de resolução adota o padrão universal do framework (Grau 1: DC 10 Fácil, DC 15 Média, DC 20 Difícil, DC 25 Extrema). Neste cenário específico, as faixas de desafio ancoram-se nas seguintes realidades diegéticas:

* **Pressão Leve (Faixa 10):** Dobrar a percepção de um mortal desprevenido, desvanecer em sombras comuns ou perscrutar a aura superficial de um sonho fraco.
* **Conflito Severo (Faixa 15):** Ocultar a presença contra a vigilância de arcontes do Sonhar, impor vertigem a magos veteranos ou atravessar fronteiras planares turbulentas.
* **Elite do Cenário (Faixa 20):** Impor o peso do Desconhecido sobre demônios maiores do Inferno, deuses pagãos enfraquecidos ou pesadelos rebeldes como o Coríntio.
* **Calamidade / Feito Lendário (Faixa 25):** Desafiar a vontade explícita de outro Perpétuo (Morpheus, Desejo, Destino) ou reescrever uma lei fundamental em solo neutro da Criação.

```yaml
system: d20_3gates
overrides:
  - id: observer_decay
    type: cost_multiplier
    target: ce
    value: 1.5
    condition: "Quanto mais um alvo compreende o Desconhecido, maior o custo de autoridade para dobrá-lo"
  - id: sovereign_realm_authority
    type: threshold_shift
    target: all_actions
    value: +5
    condition: "Dentro de Terra Incognita a autoridade do Desconhecido é absoluta; fora dela leis do hospedeiro aplicam-se"
```

---

## 2. Economia de Recursos & Sistema de Poder
* **HP (Integridade de Manifestação):** A estabilidade da forma física com a qual o Perpétuo interage com o plano material. Embora imortais, formas físicas podem ser dissipadas, forçando uma demorada e dolorosa recomposição.
* **Stamina (Presença & Fôlego):** A capacidade de sustentar esforço, resistir a atritos conceituais e manifestar-se continuadamente perante mentes mortais.
* **Energia / Magia (Autoridade Primordial):** A cota de poder do Domínio utilizada para invocar o Véu da Incógnita, dobrar limiares dimensionais ou selar segredos na mente do cosmos.

---

## 3. Votos, Pactos & Limitações do Universo
* **O Efeito Observador:** O Desconhecido existe enquanto não é compreendido; quanto mais alguém o decifra, mais esforço custa impor sua autoridade sobre essa consciência específica.
* **O Sangue da Família:** Jamais ferir letalmente ou tramar a morte de um irmão de sangue sem que as Fúrias cobrem a dívida.
* **A Hospitalidade do Limiar:** Em seu próprio reino (Terra Incognita), a autoridade do Desconhecido é absoluta, mas fora dele as leis locais do hospedeiro devem ser respeitadas ou dobradas com custo.
