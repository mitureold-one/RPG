# Regras de Arbitragem & Sistema de Poder: {{TITULO_CAMPANHA}}

## 1. Calibração Diegética de Dificuldade & Overrides (Grau 2)
A escala mecânica de resolução adota o padrão universal do framework (Grau 1: DC 10 Fácil, DC 15 Média, DC 20 Difícil, DC 25 Extrema). Neste cenário específico, as faixas de desafio ancoram-se nas seguintes realidades diegéticas:

* **Pressão Leve (Faixa 10):** {{CALIBRACAO_FAIXA_10}}
* **Conflito Severo (Faixa 15):** {{CALIBRACAO_FAIXA_15}}
* **Elite do Cenário (Faixa 20):** {{CALIBRACAO_FAIXA_20}}
* **Calamidade / Feito Lendário (Faixa 25):** {{CALIBRACAO_FAIXA_25}}

```yaml
system: d20_3gates
# calendar:
#   months: ["Ventania", "Geada", "Desgelo"]
#   days_per_month: 30
overrides:
  - id: exemplo_modificador
    type: cost_multiplier
    target: stamina
    value: 1.0
    condition: "Condição diegética de ativação do modificador"
```

---

## 2. Economia de Recursos & Sistema de Poder
* **HP (Pontos de Vida):** Integridade física e tolerância a danos letais.
* **Stamina:** Vigor muscular, fôlego e esforço físico continuado.
* **{{RECURSO_ESPECIAL}}:** {{DESCRICAO_E_CUSTOS_DE_HABILIDADES_ESPECIAIS}}.

---

## 3. Votos, Pactos & Limitações do Universo (Grau 2 - Diegese)
* {{REGRA_ESPECIAL_DO_UNIVERSO_1}}
* {{REGRA_ESPECIAL_DO_UNIVERSO_2}}
