# Verificação final da entrega

**Data:** 05/10/2026 · **Commit verificado:** o que contém este arquivo ("Verificacao final e entrega") · **Ferramenta:** [`ferramentas/verificar_entrega.py`](../ferramentas/verificar_entrega.py)

Legenda: ✔ passou · ✘ falhou (nenhum item ficou em ✘ na rodada final)

## 1. Ambiente limpo

| | Item | Evidência |
|---|---|---|
| ✔ | venv novo, criado fora do repositório, com **apenas** `pip install -r requirements.txt` | Python 3.12.10, 115 pacotes resolvidos (pandas 3.0.6, scikit-learn 1.9.1, imbalanced-learn 0.14.2, numpy 2.5.3, matplotlib 3.11.2, seaborn 0.13.2, nbconvert 7.17.1) |
| ✔ | Kernel do Jupyter = o do venv novo | `jupyter kernelspec list` → `python3` em `venv_verif\share\jupyter\kernels\python3`, sem kernel de usuário ou do sistema |
| ✔ | Coleta reproduzida (`python baixar_dados.py`) | funil 3.933.955 → 1.401.164 → 1.401.159 → amostra de 56.048. Parquet, `ibge_uf.csv` (API SIDRA consultada de novo) e metadados regenerados **byte a byte iguais** aos versionados (`git status` sem alterações em `dados/`) |
| ✔ | `jupyter nbconvert --to notebook --execute --inplace Entrega1_ENEM_IBGE.ipynb` | 12 s, 10 células de código executadas, 0 erros |
| ✔ | `jupyter nbconvert --to notebook --execute --inplace Entrega2_ENEM_IBGE.ipynb` | 1 min 41 s, 22 células de código executadas, 0 erros |
| ✔ | Zero erros e zero tracebacks **nas saídas** dos notebooks | verificador: `erros=0, tracebacks=0` nos dois |
| ✔ | Resultados determinísticos | `resultados/metricas_entrega2.json` idêntico em todas as execuções (venv de trabalho e venv limpo) |

**Observação:** durante a execução da Entrega 2, o terminal mostra 7 mensagens `KeyError` do *resource tracker* do joblib/loky. É um problema conhecido do processamento paralelo (`n_jobs=-1`) no Windows, que ocorre ao encerrar os processos auxiliares. As mensagens ficam no stderr do `nbconvert` e **não aparecem nas saídas do notebook** nem afetam os resultados (ver `docs/DECISOES.md`, D19).

## 2. Requisitos do professor (contagem programática)

| | Requisito | Evidência |
|---|---|---|
| ✔ | ≥ 2 datasets públicos reais | INEP (microdados ENEM 2023) + IBGE (Censo 2022, PNAD Contínua 2023) + PNUD (IDHM 2023) |
| ✔ | ≥ 20 KPIs | `assert len(df_kpis) == 20` nos dois notebooks; 20 linhas nas tabelas exibidas (E1 e E2); 20 no JSON |
| ✔ | ≥ 8 gráficos (Matplotlib/Seaborn) | 14 imagens: 5 na Entrega 1 e 9 na Entrega 2 (a Entrega 2 sozinha já cumpre o mínimo) |
| ✔ | Regressão Linear treinada e avaliada | R² teste = 0,299; MAE = 62,7; RMSE = 79,6; CV R² = 0,309 ± 0,006 |
| ✔ | Regressão Logística (GridSearchCV + StratifiedKFold(5)) | F1 teste = 0,336; CV F1 = 0,344 ± 0,019 |
| ✔ | Árvore de Decisão (GridSearchCV + StratifiedKFold(5)) | F1 teste = 0,319; CV F1 = 0,339 ± 0,021; árvore resumida plotada |
| ✔ | KNN (GridSearchCV + StratifiedKFold(5)) | F1 teste = 0,336; CV F1 = 0,350 ± 0,019 |
| ✔ | Avaliação: precisão, recall, F1, matriz de confusão, CV, overfitting | tabela comparativa, Gráfico 10 (matrizes), Gráfico 11 (curva treino × validação), gap treino − teste |
| ✔ | Conceito 1: Coleta | `baixar_dados.py` (`chunksize`, API SIDRA, `requests`) |
| ✔ | Conceito 2: Limpeza, ausentes, normalização, integração | `SimpleImputer`, `StandardScaler`, `merge(validate="m:1")`, checagem de duplicatas |
| ✔ | Conceito 3: Média, mediana, moda, desvio padrão | tabela da Seção 4 da Entrega 2 (+ classe modal e IQR) |
| ✔ | Conceito 4: KPIs | `calcular_kpis()` |
| ✔ | Conceito 5: Visualização e storytelling | 14 gráficos + 4 insights gerados a partir das variáveis |
| ✔ | Conceito 6: Feature engineering | `criar_features()` (renda per capita, escolaridade dos pais, atraso escolar etc.) |
| ✔ | Conceito 7a/7b: Linear, Logística, Árvore, KNN | os quatro modelos presentes e avaliados |
| ✔ | Fora do escopo não implementado | nenhuma ocorrência de K-Means, DBSCAN ou Apriori no código |

## 3. Coerência dos números

| | Item | Evidência |
|---|---|---|
| ✔ | README cita valores gerados | 47 números decimais/de milhar, todos encontrados nas saídas dos notebooks ou nos JSONs |
| ✔ | `docs/roteiro_relatorio.md` | 59 números verificados, incluindo os 20 KPIs |
| ✔ | `docs/slides_ml.md` | 40 números verificados |
| ✔ | `docs/DECISOES.md` | 38 números verificados (3 valores de protótipo listados explicitamente como exploratórios, D20) |
| ✔ | Tabelas de modelos idênticas ao JSON | linhas da tabela do README e números dos slides comparados célula a célula com `metricas_entrega2.json` |
| ✔ | O verificador detecta erro | teste negativo: "0,437" e "612,9" inseridos nos slides são apontados como SEM ORIGEM |
| ✔ | Insights do notebook não digitados à mão | gerados com `Markdown(f"...")` a partir das variáveis |
| ✔ | Nenhum placeholder esquecido | busca pelos marcadores de pendência listados em `verificar_entrega.py` (siglas em maiúsculas e frases como "inserir aqui") em `.md`, `.py`, `.csv`, `.json` e nas células e saídas dos notebooks |

## 4. Repositório

| | Item | Evidência |
|---|---|---|
| ✔ | Nenhum arquivo acima de 50 MB | maior: `Entrega2_ENEM_IBGE.ipynb` (1,2 MB), seguido de `enem_amostra.parquet` (1,0 MB) |
| ✔ | `dados/brutos/` fora do Git | `.gitignore` + nenhum arquivo `dados/brutos/*` em `git ls-files` (o zip de 550 MB ficou só na máquina local) |
| ✔ | Nenhuma credencial | busca por `api_key`, `secret`, `password`, `senha`, `token`, `ghp_…`, `AKIA…` |
| ✔ | Nenhum caminho absoluto da máquina | busca por pastas de usuário com caminho absoluto (Windows, Linux e macOS) em código, documentos e saídas dos notebooks. Os caminhos do projeto são relativos à raiz (`Path(__file__)`) |
| ✔ | README renderiza corretamente | renderização local com `mistune`: 4/4 tabelas reconhecidas, blocos de código fechados, links locais existentes |

## 5. Revisão de código

| | Item | Evidência |
|---|---|---|
| ✔ | Sem células mortas ou duplicadas | 0 células de código vazias e 0 com conteúdo repetido nos dois notebooks |
| ✔ | Imports no topo | só a primeira célula de código de cada notebook importa. Imports sem uso removidos (`np` e `SEED` na E1, `CORES_ESCOLA` na E2) |
| ✔ | Comentários em português | busca heurística por palavras funcionais em inglês nos comentários: 0 ocorrências |
| ✔ | `SEED = 42` em tudo que é aleatório | 10 chamadas aleatórias verificadas (`train_test_split`, `KFold`, `StratifiedKFold`, `DecisionTreeClassifier`, `LogisticRegression`, `RandomUnderSampler`, `.sample`, `default_rng`, `np.random.seed`), todas com `SEED` |
| ✔ | Fallback de simulação funciona | os dois notebooks executados com `USAR_DADOS_REAIS = False`: 0 erros (5 e 9 gráficos) |
| ✔ | Equivalência da refatoração | `src/` reproduz os DataFrames do notebook original da Entrega 1 (`assert_frame_equal`) |

## Falhas encontradas e corrigidas durante a verificação

| Achado | Correção |
|---|---|
| A primeira versão deste arquivo citava literalmente os marcadores de pendência e o padrão de caminho absoluto procurados. Ao rodar o verificador depois do commit, com o arquivo já rastreado, ele foi apontado como ✘ | Texto reescrito sem os termos literais; verificação repetida até passar |
| Falsos positivos do verificador: "Todo nulo…" (português) casava com o marcador em inglês, e a própria regex de inglês casava consigo mesma | Marcadores passaram a ser *case-sensitive*; a linha da regex foi excluída da checagem |
| `docs/DECISOES.md` citava contagens da base completa que não estavam salvas em nenhum arquivo | `baixar_dados.py` passou a gravá-las em `enem_amostra_meta.json` |
| Arredondamento duplo (JSON com 4 casas → texto com 3 casas: 0,4985 virava 0,498 e não 0,499) | JSON passou a guardar 6 casas |

## Como repetir

```bash
python -m venv venv_verif && venv_verif\Scripts\activate   # Linux/macOS: source venv_verif/bin/activate
pip install -r requirements.txt
jupyter nbconvert --to notebook --execute --inplace Entrega1_ENEM_IBGE.ipynb
jupyter nbconvert --to notebook --execute --inplace Entrega2_ENEM_IBGE.ipynb
python ferramentas/verificar_entrega.py
```
