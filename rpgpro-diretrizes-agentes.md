# RPGPRO --- Diretrizes de Mundo Autônomo e Direção Narrativa

**Tipo:** documento de arquitetura e comportamento para agentes\
**Status:** consolidação das decisões do brainstorming; ainda não é uma
especificação técnica final aprovada\
**Idioma:** português (Brasil)

> **Instrução para agentes:** use este documento como a fonte das
> decisões de comportamento já acordadas para a evolução do RPGPRO. Não
> trate propostas técnicas ainda não definidas como requisitos
> confirmados. Antes de implementar, inspecione o repositório e compare
> estas diretrizes com a arquitetura existente. Prefira evolução
> incremental a uma reescrita total.

## 1. Objetivo

Evoluir o RPGPRO para um sistema de RPG com mundo autônomo, memória
narrativa persistente, NPCs e facções que perseguem objetivos próprios,
simulação causal verificável e um diretor narrativo que mantém a
história em movimento sem retirar a liberdade do jogador.

O RPGPRO é uma camada determinística de orquestração, estado e auditoria
que trabalha com um agente/LLM externo. Não presuma que o repositório
execute chamadas a modelos diretamente, a menos que a inspeção atual
demonstre isso.

## 2. Princípios fundamentais

1.  **Autonomia quase total:** o mundo continua evoluindo sem a presença
    do protagonista.
2.  **Causalidade:** acontecimentos precisam respeitar fatos,
    capacidades, recursos, conhecimento, localização, pré-condições e
    regras da campanha.
3.  **IA propõe; o motor valida e resolve:** a IA não pode declarar
    arbitrariamente que uma ação impossível ou incerta teve sucesso.
4.  **Plano não é fato:** intenções e planos não são acontecimentos
    concluídos.
5.  **Histórico causal rastreável:** tentativas, resultados, efeitos e
    correções precisam ter origem e dependências identificáveis.
6.  **Histórico imutável no fluxo normal:** correções são novos
    registros; não se apagam silenciosamente acontecimentos anteriores.
7.  **Verdade separada de conhecimento:** verdade histórica,
    conhecimento do jogador e conhecimento dos personagens são camadas
    distintas.
8.  **Simulação global com profundidade seletiva:** o mundo inteiro pode
    avançar, mas só os elementos que precisam de análise causal recebem
    processamento profundo.
9.  **Progressão narrativa verificável:** atividade não equivale a
    avanço; o sistema deve observar mudanças reais.
10. **Memória em camadas:** prosa, diálogos, fatos estruturados e
    resumos derivados se complementam.
11. **Retomada segura:** limitar o orçamento de um ciclo não apaga
    trabalho nem duplica efeitos.
12. **Evolução incremental:** preservar e ampliar os componentes
    existentes sempre que viável; não reescrever o sistema sem evidência
    e aprovação.

## 3. Autonomia do mundo

### 3.1 Grau de autonomia --- decisão confirmada

O mundo tem autonomia quase total. Sem intervenção do protagonista,
podem ocorrer, se sustentados causalmente:

-   mortes de personagens;
-   alianças que se desfazem;
-   guerras e crises políticas;
-   missões que fracassam ou são concluídas;
-   planos de antagonistas que avançam;
-   quedas de lideranças e mudanças territoriais;
-   consequências irreversíveis fora de cena.

Não existe imunidade narrativa automática para o protagonista ou seus
aliados. A proteção de personagens deve decorrer das circunstâncias e
regras da campanha, não de uma obrigação narrativa de mantê-los vivos.

### 3.2 Modelo híbrido de resolução --- decisão confirmada

A IA propõe intenções, estratégias e ações. O motor verifica e resolve.

  -----------------------------------------------------------------------
  Responsabilidade                    Dono principal
  ----------------------------------- -----------------------------------
  Propor intenções, estratégias e     IA
  alternativas                        

  Verificar identidade e capacidades  Motor

  Verificar recursos, conhecimento,   Motor
  localização e pré-condições         

  Resolver segundo as regras da       Motor e regras aplicáveis
  campanha                            

  Registrar resultado e efeitos       Motor

  Selecionar o que narrar em seguida  Diretor narrativo
  -----------------------------------------------------------------------

### 3.3 Incerteza contextual --- decisão confirmada

-   Ações rotineiras com pré-condições satisfeitas podem ser resolvidas
    diretamente.
-   Ações incertas de baixo impacto podem receber resolução
    simplificada.
-   Ações relevantes e incertas devem usar testes adequados às regras da
    campanha.
-   Reutilizar o d20 quando for apropriado, sem forçá-lo a todos os
    sistemas.
-   Ações impossíveis devem ser rejeitadas, adaptadas ou adiadas.
-   Falhas podem impor custos e consequências justificados.
-   Resultados críticos precisam de fundamento nas regras, não de
    escolha arbitrária da IA.

## 4. Histórico causal, tentativas e correções

### 4.1 Registrar todas as tentativas --- decisão confirmada

Registrar tentativas bem-sucedidas, malsucedidas, rejeitadas, adiadas,
interrompidas, abandonadas e propostas novamente/duplicadas.

O sistema precisa distinguir pelo menos:

-   proposta;
-   tentativa efetivamente iniciada;
-   ação concluída;
-   efeitos secundários ainda pendentes;
-   ação rejeitada ou bloqueada;
-   plano pendente, reformulado ou abandonado.

Não tratar uma proposta como fato consumado.

### 4.2 Histórico imutável --- decisão confirmada

-   O fluxo normal não edita nem apaga registros históricos.
-   Correções são novos registros que referenciam os registros afetados.
-   Cada registro deve ter identificador estável e informação suficiente
    para rastrear origem e dependências.
-   Incluir versão do esquema e identificador do turno.
-   O estado atual é uma projeção derivada dos eventos e correções
    válidos.
-   Reprocessamento não pode duplicar efeitos.
-   Corrigir a verdade do mundo não altera automaticamente o
    conhecimento ou as crenças dos personagens.

### 4.3 Reavaliar dependências --- decisão confirmada

Ao corrigir um evento, identificar e reavaliar os registros que dependem
causalmente dele. Eventos independentes permanecem válidos. Reavaliar
apenas os efeitos afetados sempre que possível.

### 4.4 Irreversibilidade --- decisão confirmada, com detalhe técnico pendente

Preservar acontecimentos históricos concluídos. Não apagar
silenciosamente uma morte nem inventar uma ressurreição só porque sua
causa foi corrigida. Reavaliar efeitos reversíveis que dependam do erro,
distinguindo:

1.  verdade histórica;
2.  estado atual;
3.  conhecimento e crenças dos personagens.

**Pendente:** definir o tratamento técnico para uma correção que
contradiga a própria ocorrência de um evento irreversível. Não inventar
uma solução sem especificação.

### 4.5 Resolução por ciclos causais --- decisão confirmada

1.  Agrupar ações compatíveis no mesmo intervalo temporal.
2.  Identificar dependências e conflitos.
3.  Resolver ações que podem acontecer juntas.
4.  Reavaliar ações afetadas por mudanças de estado.
5.  Resolver conflitos respeitando tempo, regras e circunstâncias.
6.  Prevenir loops de reavaliação.
7.  Manter ações bloqueadas como pendentes, reformuladas ou abandonadas.
8.  Registrar todas as tentativas.

## 5. Tempo e simulação

### 5.1 Avanço temporal --- decisão confirmada

O mundo avança pelo tempo decorrido e por eventos importantes, não
necessariamente uma vez por turno do protagonista.

-   Ações de poucos segundos não devem provocar simulação desnecessária
    de dias.
-   Saltos temporais devem permitir a evolução de planos, missões,
    relógios e facções durante o intervalo.
-   Eventos críticos podem acionar reavaliação antecipada.
-   Viagens e outras atividades prolongadas podem incluir acontecimentos
    fora de cena.
-   Tempo de simulação e tempo de narração são coisas diferentes.

### 5.2 Simulação global por relevância causal --- decisão confirmada

O mundo inteiro pode avançar. O motor aprofunda apenas elementos que
exigem atenção causal.

-   Planos e eventos podem avançar em qualquer região.
-   Entidades afetadas por mudanças importantes recebem avaliação
    profunda.
-   Rotinas sem consequências relevantes podem ser atualizadas de modo
    simplificado.
-   Mudanças de estado podem disparar novas avaliações nos elementos
    dependentes.

### 5.3 Acionamento da simulação profunda --- decisão confirmada

Dois caminhos podem solicitar simulação profunda:

-   **Gatilhos determinísticos:** prazos, conflitos entre planos,
    mudanças críticas de estado, riscos relevantes e dependências
    afetadas.
-   **Solicitações da IA:** uma possível consequência importante ou
    situação inesperada que mereça análise adicional.

O motor valida a solicitação e registra o motivo. Solicitar uma análise
não prova que o evento sugerido seja verdadeiro nem determina seu
resultado.

### 5.4 Orçamento adaptativo e fila persistente --- decisão confirmada

-   Usar limites de processamento para evitar consumo excessivo e ciclos
    infinitos.
-   Priorizar eventos urgentes e dependências críticas.
-   Preservar em fila persistente o trabalho não concluído, incluindo
    motivo, prioridade, estado e dependências.
-   Retomar trabalho em ciclos posteriores sem duplicar efeitos.
-   Diferenciar uma ação ainda não executada de uma ação concluída cujos
    efeitos secundários continuam pendentes.
-   Atingir o limite de processamento não pode apagar um evento ou
    fingir que uma ação concluída não ocorreu.

Os valores concretos dos limites, critérios de prioridade e política de
retry ainda precisam ser especificados.

## 6. NPCs autônomos

### 6.1 Dois níveis de modelagem --- decisão confirmada

NPCs relevantes recebem estado persistente detalhado. NPCs secundários
recebem modelo simplificado e podem ser aprofundados se ganharem
relevância.

### 6.2 NPCs relevantes

Modelar, conforme aplicável:

-   objetivos e razões;
-   prioridades e conflitos entre objetivos;
-   planos em etapas, pré-requisitos, alternativas e condições de
    conclusão;
-   recursos e capacidades;
-   conhecimento, fontes e crenças;
-   relações: confiança, rivalidade, dependência, dívidas e lealdades;
-   localização, condição, compromissos e acontecimentos recentes.

NPCs secundários devem manter, no mínimo e conforme a campanha,
identidade, personalidade, objetivo imediato, relações essenciais,
conhecimento relevante e situação atual.

### 6.3 Planos são intenções

Um plano pode falhar, ser interrompido, tornar-se impossível ou ser
substituído. A existência de um plano não significa que o evento
ocorrerá.

### 6.4 Conhecimento individual

As decisões de cada personagem precisam respeitar as informações às
quais ele tem acesso. Quando útil, distinguir:

-   informação presenciada;
-   informação recebida de terceiros;
-   informação inferida;
-   crença não confirmada;
-   informação falsa ou desatualizada.

O esquema exato de confiança, proveniência e atualização do conhecimento
ainda está pendente.

## 7. Facções autônomas

### 7.1 Estratégia coletiva com política interna --- decisão confirmada

Cada facção tem objetivos e planos coletivos, mas lideranças e subgrupos
podem discordar, conspirar ou agir por conta própria quando isso for
relevante.

Modelar, conforme a importância:

-   objetivos oficiais e planos coletivos;
-   recursos, influência e limitações;
-   lideranças, autoridade e sucessão;
-   subgrupos, lealdades e interesses;
-   divergências, conspirações e disputas de poder;
-   informações compartilhadas e restritas.

Não representar uma facção como uma única pessoa com uma única opinião.
Evitar também simular detalhadamente todos os membros de organizações
irrelevantes.

## 8. Diretor narrativo

### 8.1 Seleção causal e narrativa --- decisão confirmada

O diretor escolhe acontecimentos para narrar considerando:

1.  urgência e risco de consequências irreversíveis;
2.  causalidade com eventos e decisões anteriores;
3.  impacto sobre personagens, facções, missões e mundo;
4.  relevância para os arcos;
5.  oportunidades significativas de decisão do jogador;
6.  coerência cronológica.

O diretor decide o que narrar, não reescreve o que aconteceu para forçar
um resultado dramático.

### 8.2 Perspectiva dramática controlada --- decisão confirmada

A narração pode mostrar eventos fora da presença do protagonista. O
sistema separa explicitamente:

-   o que aconteceu no mundo;
-   o que foi revelado ao jogador;
-   o que o protagonista sabe.

O conhecimento do jogador não é transferido automaticamente ao
personagem. O protagonista precisa descobrir a informação por meios
compatíveis com a campanha.

## 9. Arcos e progressão narrativa

### 9.1 Arcos com estrutura flexível --- decisão final confirmada

**Esta decisão substitui a escolha anterior por fases explícitas e
rígidas.**

Cada arco tem uma direção, marcos flexíveis e condições de conclusão,
mas pode se transformar de acordo com os acontecimentos.

-   Marcos orientam, sem impor sequência rígida.
-   Arcos podem terminar por diferentes resultados.
-   Conflitos secundários podem tornar-se centrais.
-   Arcos encerrados podem gerar novos conflitos.
-   Ações de NPCs, facções e protagonista podem alterar o rumo da
    história.

### 9.2 Detecção e recuperação de estagnação --- decisão confirmada

O motor deve detectar ausência prolongada de mudanças significativas,
mesmo quando há atividade superficial.

Ao detectar estagnação:

1.  examinar objetivos pendentes, planos, relógios, ameaças, facções e
    consequências adiadas;
2.  identificar bloqueios e fios narrativos capazes de produzir
    progressão;
3.  deixar o diretor selecionar uma intervenção causal coerente;
4.  validar e resolver a intervenção pelo motor;
5.  verificar se o estado realmente evoluiu.

A intervenção pode ser uma negociação, uma missão que falha, um plano
que entra em execução, uma mudança de alianças ou uma consequência já
sustentada pelo mundo.

Não inventar retroativamente uma causa só para criar drama. Se não
houver fio causal plausível, diagnosticar o bloqueio e propor uma saída
compatível com o estado existente.

## 10. Contexto e memória

### 10.1 Contexto por relevância causal --- decisão confirmada

O `prepare` monta três camadas:

1.  **Núcleo obrigatório:** regras, estado atual do protagonista, tempo,
    localização, arco ativo, objetivos relevantes e restrições
    importantes.
2.  **Contexto causal da cena:** NPCs e facções pertinentes, planos,
    missões, relógios, fatos anteriores e consequências que podem afetar
    a decisão.
3.  **Consulta sob demanda:** a IA consulta o estado persistente quando
    faltar informação.

A seleção não deve depender apenas de presença física na cena. Um
antagonista distante pode ser relevante se seu plano estiver prestes a
afetar a situação atual.

Distinguir informação desconhecida, informação indisponível no contexto
e informação inexistente. A ausência de um detalhe no prompt não
autoriza inventá-lo como fato.

### 10.2 Memória em camadas --- decisão confirmada

Manter três camadas complementares:

  -----------------------------------------------------------------------
  Camada                              Função
  ----------------------------------- -----------------------------------
  Registro original                   Preservar prosa e diálogos das
                                      cenas

  Histórico causal estruturado        Registrar fatos, tentativas,
                                      resultados, custos e dependências

  Memórias derivadas                  Resumir relações, objetivos, arcos
                                      e acontecimentos importantes
  -----------------------------------------------------------------------

Memórias derivadas precisam ser rastreáveis às fontes originais. Podem
ser atualizadas ou reconstruídas sem apagar o histórico. Uma crença de
personagem pode continuar registrada mesmo quando a verdade histórica
demonstra que ela está errada.

## 11. Fluxo integrado proposto

1.  Receber ação do protagonista ou avanço temporal.
2.  Montar contexto por relevância causal.
3.  Pedir à IA propostas de ações e eventos.
4.  Validar pré-condições, capacidades, recursos e conhecimento.
5.  Resolver conforme as regras da campanha.
6.  Registrar tentativas, resultados, custos e efeitos.
7.  Avançar o tempo e avaliar eventos pendentes.
8.  Reavaliar dependências e eventos importantes conforme orçamento e
    prioridade.
9.  Atualizar projeções de estado e memórias derivadas.
10. Detectar estagnação e avaliar a evolução dos arcos.
11. O diretor seleciona a próxima cena.
12. Narrar respeitando o controle de revelação.

**Nota:** esta sequência é conceitual. A ordem transacional exata entre
resolução, persistência, projeções e memória precisa ser especificada
durante o desenho técnico. Efeitos históricos não podem ser aplicados
duas vezes.

## 12. Pendências de especificação técnica

Não tratar os itens a seguir como decisões já tomadas:

1.  **Esquema persistente:** campos, IDs, relações, versionamento e
    armazenamento de eventos, NPCs, facções, planos, conhecimento e
    arcos.
2.  **Correções e reconstrução:** como reavaliar dependências e
    preservar efeitos irreversíveis sem contradizer o histórico.
3.  **Calendário e tempo:** calendários personalizados, avanço de datas,
    saltos temporais e agendamento futuro.
4.  **Orçamento e fila:** limites configuráveis, prioridade, retomada,
    retry e tratamento de falhas.
5.  **Memória e recuperação:** armazenamento da prosa, indexação de
    fatos, recuperação de fontes e atualização dos resumos.
6.  **Conhecimento individual:** proveniência, confiança, informação
    falsa/desatualizada e regras de atualização.
7.  **Testes comportamentais:** cenários reproduzíveis e critérios de
    aceitação.
8.  **Integração com a arquitetura atual:** identificar componentes,
    formatos e migrações reais após inspecionar o repositório.

## 13. Cenários de validação obrigatórios a planejar

  -----------------------------------------------------------------------
  Cenário                             Resultado esperado
  ----------------------------------- -----------------------------------
  Salto temporal de vários dias       Relógios, missões e planos evoluem
                                      de acordo com o tempo

  Conflito entre dois NPCs            Recursos, objetivos e
                                      circunstâncias determinam o
                                      resultado

  Mudança política fora de cena       A facção evolui sem a presença do
                                      protagonista

  Conhecimento restrito               Um personagem não usa informação
                                      que desconhece

  Correção de evento                  Somente dependências afetadas são
                                      reavaliadas

  Retomada da fila                    Efeitos concluídos não são
                                      duplicados

  Arco alterado por derrota           O arco muda de direção ou termina
                                      coerentemente

  Campanha estagnada                  O diretor encontra uma intervenção
                                      causal plausível

  Memória de longo prazo              Uma promessa ou decisão antiga é
                                      recuperada com sua fonte

  Calendário personalizado            Datas e durações permanecem
                                      consistentes nos saltos temporais
  -----------------------------------------------------------------------

## 14. Orientações para agentes de desenvolvimento

Antes de implementar:

1.  Inspecionar o estado atual do repositório, branches, mudanças
    locais, testes e documentação.
2.  Verificar cada afirmação arquitetural contra o código atual; não
    confiar cegamente em uma auditoria anterior.
3.  Identificar a menor mudança incremental que atende às decisões
    confirmadas.
4.  Separar requisitos confirmados de decisões técnicas pendentes.
5.  Planejar migrações e compatibilidade com campanhas existentes.
6.  Definir testes de comportamento antes de declarar a tarefa
    concluída.
7.  Preservar mudanças preexistentes do usuário; não sobrescrever nem
    descartar trabalho local sem autorização.
8.  Não alegar testes, commits, alterações ou sucesso sem evidência
    observada.
9.  Não começar uma implementação abrangente enquanto as decisões
    técnicas necessárias ainda estiverem indefinidas.
10. Solicitar aprovação humana quando uma decisão de implementação
    alterar materialmente o comportamento acordado ou introduzir
    trade-offs não aprovados.

### Fora de escopo por enquanto

-   Reescrever o RPGPRO do zero.
-   Obrigar todas as campanhas a usar d20.
-   Simular todos os NPCs com o mesmo nível de detalhe.
-   Fazer o diretor inventar acontecimentos sem base causal para manter
    o ritmo.
-   Tratar resumos derivados como fonte histórica autoritativa.
-   Implementar escolhas técnicas pendentes sem revisão.

## 15. Estado de aprovação

Este documento consolida as decisões de comportamento acordadas durante
o brainstorming. Ele serve como referência para agentes e como base para
uma especificação formal.

**Não significa, por si só, que a especificação técnica final ou o plano
de implementação estejam aprovados.** O próximo passo é revisar o
documento, inspecionar o repositório e detalhar os contratos e critérios
técnicos antes de implementar.
