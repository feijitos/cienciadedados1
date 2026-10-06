# Slides de Machine Learning (apresentação de 10 min)

Três slides para o trecho de modelagem, com cerca de 3 minutos no total. Cada slide traz título, conteúdo, gráfico sugerido e fala do apresentador. Os números vêm de `resultados/metricas_entrega2.json`.

---

## Slide 1: Origem social explica 30% da nota

**Conteúdo**
- Regressão Linear para prever a `NOTA_FINAL` a partir de 13 variáveis socioeconômicas e estaduais.
- **R² = 0,299** no teste (validação cruzada: 0,309 ± 0,006). **Erro médio: 62,7 pontos.**
- Maiores associações, mantidas as demais variáveis constantes:
  - escola privada: **+43,4 pontos**;
  - renda per capita (+1 desvio padrão): **+12,7**;
  - computadores em casa: **+11,5**;
  - escolaridade da mãe: **+7,7**;
  - atraso escolar: **−10,3**;
  - alunos pretos: **−21,6** e indígenas: **−35,6**, em relação a brancos.

**Gráficos:** 9 (coeficientes) e, menor ao lado, 8 (real × previsto).

**Fala (~60 s):** "Com o que sabemos da família e da escola, explicamos 30% da variação da nota. É muito para um fenômeno social, mas deixa 70% para o que esses dados não medem: esforço, qualidade da escola, preparação. A escola privada vale 43 pontos *depois* de descontar renda e escolaridade dos pais, menos da metade dos 101 pontos de diferença bruta."

---

## Slide 2: Quem passa de 700? Três modelos, empate técnico

**Conteúdo**
- Alvo: `NOTA_FINAL > 700`, apenas **4,05%** dos alunos (classe rara).
- Tratamento do desbalanceamento: o peso da classe rara (Logística, Árvore) e a proporção de undersampling (KNN) entram como hiperparâmetros no `GridSearchCV` + `StratifiedKFold(5)`, otimizando F1.

| Modelo | CV F1 | F1 teste | Recall | Precisão | ROC-AUC |
|---|---|---|---|---|---|
| Regressão Logística | 0,344 ± 0,019 | 0,336 | 0,499 | 0,253 | 0,872 |
| Árvore (prof. 5) | 0,339 ± 0,021 | 0,319 | 0,525 | 0,229 | 0,862 |
| KNN (k = 201) | 0,350 ± 0,019 | 0,336 | 0,440 | 0,272 | 0,864 |

- Diferença entre os modelos na CV (0,011) < desvio da CV (0,021): **empate técnico**. Escolhemos a **Regressão Logística** por ser interpretável.

**Gráficos:** 14 (comparativo de métricas) e 10 (matrizes de confusão).

**Fala (~60 s):** "Acurácia não serve aqui: dizer 'ninguém passa de 700' acerta 96%. Por isso olhamos F1, precisão e recall. A Regressão Logística encontra metade dos alunos acima de 700, e 1 em cada 4 que ela aponta realmente chega lá. Um palpite aleatório acertaria 1 em 25. Os três modelos ficam dentro da margem de erro uns dos outros, então ficamos com o mais explicável."

---

## Slide 3: Sem overfitting e com limites claros

**Conteúdo**
- **Overfitting controlado:** a árvore com profundidade 20 chega a F1 = 0,818 no treino, mas cai para 0,209 na validação. Com a profundidade 5 escolhida pela CV, o treino tem 0,350 e o teste 0,319.
- Gap de F1 treino − teste de no máximo 0,030 (Árvore) nos três modelos escolhidos.
- **Sem vazamento:** a divisão 80/20 vem antes de tudo, e imputação, `StandardScaler`, One-Hot e undersampling são aprendidos só no treino (Pipeline).
- **Limites:**
  - associação ≠ causa;
  - correlação estadual IDHM × nota (r = 0,71) é ecológica: no modelo individual, o IDHM perde o efeito;
  - universo = inscritos concluintes do ENEM 2023.

**Gráfico:** 11 (curva de overfitting da árvore).

**Fala (~60 s):** "Este gráfico mostra o que acontece quando deixamos a árvore crescer: ela decora o treino e piora fora dele. A validação cruzada escolheu profundidade 5, onde treino e teste ficam próximos. Conclusão: a origem social aumenta muito a chance de alto desempenho, de 1,2% na escola pública para 15,1% na privada, mas não define o destino de nenhum aluno."
