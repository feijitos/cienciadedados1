# Roteiro do relatório (PDF)

Estrutura sugerida para o relatório da entrega final, seguindo os cinco itens obrigatórios do enunciado: descrição do dataset, ferramentas, metodologia, insights, gráficos e indicadores. Todos os números abaixo saem dos notebooks executados (`resultados/metricas_entrega2.json`). **Se os notebooks forem executados de novo com outros dados, atualize os números a partir desse arquivo.**

Extensão sugerida: 10 a 14 páginas, contando os gráficos.

---

## 1. Introdução (½ página)
- **Pergunta:** quanto do desempenho no ENEM se associa à origem socioeconômica do aluno e ao contexto do estado?
- **Por que importa:** o ENEM é a principal porta de entrada no ensino superior público. Se a nota reflete sobretudo a origem social, o exame reproduz desigualdades.
- **Estrutura do relatório:** uma frase por seção.

## 2. Descrição dos datasets (1 página)
*Rubrica: escolha do dataset (10 pts)*

| Base | Fonte | Ano | Registros usados |
|---|---|---|---|
| Microdados do ENEM | INEP | 2023 | 56.048 (amostra de 4% por UF, a partir de 1.401.159 concluintes) |
| População residente | IBGE, Censo 2022 (SIDRA 4709) | 2022 | 27 UFs |
| Renda domiciliar per capita | IBGE, PNAD Contínua (SIDRA 7531) | 2023 | 27 UFs |
| IDHM | PNUD/Ipea/FJP, Radar IDHM, Tabela 5 | 2023 | 27 UFs |

Pontos a explicar:
- **Universo:** concluintes do ensino médio em 2023 com escola pública ou privada informada. Só para eles o INEP preenche `TP_ESCOLA` (`docs/DECISOES.md`, D2).
- **Por que 2023:** a partir de 2024, notas e questionário vêm em arquivos sem chave de ligação (D1).
- **Variáveis principais:** notas das 5 provas, presença (4 colunas), tipo de escola, renda familiar (`Q006`), escolaridade dos pais (`Q001`/`Q002`), moradores (`Q005`), computador e internet (`Q024`/`Q025`), sexo, cor/raça e faixa etária.
- **Integração:** chave `UF` (UF da prova), merge muitos-para-um validado.

## 3. Ferramentas utilizadas (¼ página)
- **Python 3.12** em notebooks Jupyter.
- **pandas/pyarrow:** leitura em blocos do CSV de 1,8 GB, Parquet e ETL.
- **requests:** download do INEP e API do SIDRA.
- **Matplotlib/Seaborn:** 14 gráficos.
- **scikit-learn:** `Pipeline`, `ColumnTransformer`, modelos, `GridSearchCV` e métricas.
- **imbalanced-learn:** undersampling dentro do Pipeline.
- **Git/GitHub:** versionamento.

## 4. Metodologia (2–3 páginas)
*Rubrica: pré-processamento (15), EDA (15), conceitos (20)*

1. **Coleta:** `baixar_dados.py` lê o CSV oficial em blocos de 500 mil linhas e faz amostragem estratificada por UF (4%, `SEED = 42`). Os dados do IBGE vêm pela API do SIDRA.
2. **Limpeza:**
   - 0 inscrições duplicadas e 0 notas fora de [0, 1000];
   - nulos de nota: 14.016 alunos sem alguma nota por falta ou eliminação (nulos **estruturais**, não imputados) e 0 presentes sem nota;
   - redação zerada sempre com situação diferente de "sem problemas";
   - presença unificada a partir das 4 colunas do INEP (D5).
3. **Estatística descritiva:** média, mediana, moda (e classe modal) e desvio padrão de cada prova. Outliers por IQR são sinalizados e mantidos (D17).
4. **KPIs:** 20 indicadores em 4 eixos (tabela na Seção 6 deste roteiro).
5. **Feature engineering:**
   - renda per capita em salários mínimos (com log);
   - escolaridade da mãe e do pai em escala ordinal;
   - número de computadores, internet;
   - atraso escolar (19 anos ou mais);
   - cor/raça e sexo com rótulos legíveis.
6. **Pré-processamento sem vazamento:**
   - divisão 80/20 estratificada (33.625 treino / 8.407 teste);
   - `Pipeline` + `ColumnTransformer`: imputação (mediana/moda), `StandardScaler` e One-Hot com categoria de referência;
   - explicar por que o `StandardScaler` é obrigatório no KNN (distância euclidiana).
7. **Modelos:**
   - Regressão Linear (alvo: `NOTA_FINAL`);
   - Regressão Logística, Árvore de Decisão e KNN (alvo: `NOTA_FINAL > 700`, 4,05% de positivos);
   - `GridSearchCV` + `StratifiedKFold(5)`, otimizando F1;
   - o grau de rebalanceamento (peso da classe ou proporção do undersampling) entra como hiperparâmetro (D13).
8. **Avaliação:**
   - CV média ± desvio;
   - acurácia, precisão, recall, F1 e ROC-AUC no teste;
   - matrizes de confusão;
   - comparação treino × teste e curva de profundidade da árvore (overfitting).

## 5. Resultados e principais insights (3 páginas)
*Rubrica: storytelling (10)*

Use os quatro insights da Seção 11 do notebook da Entrega 2, cada um com o gráfico que o sustenta:

| Insight | Números | Gráficos |
|---|---|---|
| **1. A escola explica parte, mas não sozinha** | Privada 616,1 × pública 515,2 (razão 1,20); passam de 700: 15,1% (privada) × 1,2% (pública); efeito controlado da escola privada: +43,4 pontos (43% da diferença bruta de 100,9) | 2, 9 |
| **2. A renda pesa duas vezes** | Abstenção 29,6% (baixa renda) × 9,9% (alta), diferença de 19,8 p.p.; nota média 506,2 × 620,5; 14,3% dos alunos de baixa renda passam de 600 | 5, 7 |
| **3. Território: correlação ecológica** | IDHM × nota média por UF: r = 0,71; médias de 494,4 (AM) a 561,2 (MG); no modelo individual, IDHM = −7,3 pontos por desvio padrão | 1, 3, 9 |
| **4. Origem social capta a tendência, não o aluno** | Regressão Linear: R² = 0,299, MAE = 62,7; Regressão Logística no teste: F1 = 0,336, ROC-AUC = 0,872, recall = 0,499, precisão = 0,253 (taxa base 4,1%) | 8, 10, 14 |

## 6. Gráficos e indicadores (2–3 páginas)
*Rubrica: KPIs (15), gráficos (15)*

**Tabela dos 20 KPIs** (Entrega 1, `src/kpis.py`):

| # | KPI | Valor |
|---|---|---|
| 1 | Média geral por UF (melhor UF) | 561,16 pts (MG; pior: AM, 494,4) |
| 2 | Mediana da redação | 640,00 pts |
| 3 | Desvio padrão de Exatas (CN+MT) | 98,81 pts |
| 4 | Taxa de notas > 700 | 4,05% |
| 5 | Taxa de zeros na redação | 4,11% |
| 6 | Maior média de renda por UF (índice Q006) | 5,27 (SC; menor: CE, 1,82) |
| 7 | % escola pública | 83,43% (privada: 16,6%) |
| 8 | Razão de notas privada/pública | 1,20 |
| 9 | % baixa renda | 65,82% (média: 22,6%; alta: 11,6%) |
| 10 | % abstenção | 24,85% |
| 11 | Correlação IDHM × nota média (UF) | 0,71 |
| 12 | Gap de nota entre a UF de maior e a de menor renda per capita | 58,01 pts (DF − MA) |
| 13 | Densidade de inscritos por 100 mil hab. (amostra) | 27,60 (maior: CE, 49,55) |
| 14 | Abstenção baixa − alta renda | 19,76 p.p. |
| 15 | Índice de desigualdade regional (CV das médias por UF) | 4,28% |
| 16 | Total de inscritos na amostra | 56.048 |
| 17 | Presença | 74,99% |
| 18 | % baixa renda com nota > 600 | 14,30% |
| 19 | Maior nota final | 820,38 pts |
| 20 | Menor nota final | 57,62 pts |

**Gráficos (14):**

| # | Gráfico | Notebook |
|---|---|---|
| 1 | Média da nota final por UF | Entrega 1 |
| 2 | Nota final por tipo de escola (boxplot) | Entrega 1 |
| 3 | IDHM × nota média por UF | Entrega 1 |
| 4 | Distribuição das notas de redação | Entrega 1 |
| 5 | Faixa de renda por região | Entrega 1 |
| 6 | Distribuição das notas e outliers (IQR) | Entrega 2 |
| 7 | Heatmap de correlação | Entrega 2 |
| 8 | Regressão Linear: real × previsto | Entrega 2 |
| 9 | Coeficientes da Regressão Linear | Entrega 2 |
| 10 | Matrizes de confusão | Entrega 2 |
| 11 | Overfitting da árvore × profundidade | Entrega 2 |
| 12 | Árvore de decisão resumida | Entrega 2 |
| 13 | Importância das variáveis | Entrega 2 |
| 14 | Comparativo de métricas entre modelos | Entrega 2 |

Para exportar uma figura em alta resolução, acrescente `fig.savefig("figura.png", dpi=200, bbox_inches="tight")` antes do `plt.show()` da célula.

## 7. Limitações (½ página)
Copie e resuma a Seção 13 do notebook da Entrega 2:
- correlação ecológica;
- universo autosselecionado;
- edição de 2023;
- UF da prova;
- renda em faixas;
- variáveis estaduais constantes dentro da UF;
- associação ≠ causa.

## 8. Conclusão (¼ página)
A origem socioeconômica explica cerca de 30% da variação da nota e multiplica a chance de alto desempenho (15,1% na rede privada contra 1,2% na pública), mas não determina o resultado individual. O território importa sobretudo pela composição social de quem faz a prova.

## Anexo
Tabela "Conceito da disciplina → seção do notebook" (Seção 12 da Entrega 2) e link do repositório.
