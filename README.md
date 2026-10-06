# Fatores Socioeconômicos no Desempenho do ENEM × Indicadores Estaduais do IBGE

Projeto Prático de Ciência de Dados (CEUB, 2026). O projeto cruza os **microdados do ENEM 2023 (INEP)** com **indicadores estaduais do IBGE e do PNUD** para medir quanto da nota no ENEM se associa à origem socioeconômica do aluno e ao contexto do estado. A análise percorre o ciclo completo de ciência de dados: coleta, limpeza, estatística descritiva, 20 KPIs, visualização, feature engineering, modelagem preditiva e avaliação.

| Entrega | Notebook | Conteúdo |
|---|---|---|
| 1 (28/09/2026) | [`Entrega1_ENEM_IBGE.ipynb`](Entrega1_ENEM_IBGE.ipynb) | ETL, estatísticas descritivas, 20 KPIs e Gráficos 1–5 |
| 2 (23/11/2026) | [`Entrega2_ENEM_IBGE.ipynb`](Entrega2_ENEM_IBGE.ipynb) | EDA complementar, feature engineering, Regressão Linear, Regressão Logística, Árvore de Decisão, KNN, avaliação e Gráficos 6–14 |

## Principais resultados

Amostra de **56.048** concluintes do ensino médio (4% de cada UF), dos quais **42.032** fizeram as cinco provas.

- **Escola:** nota final média de **616,1** na rede privada contra **515,2** na pública (razão 1,20). Controlando renda, escolaridade dos pais e acesso a recursos, a escola privada fica associada a **+43,4 pontos**, menos da metade da diferença bruta.
- **Renda:** a abstenção é de **29,6%** na baixa renda e **9,9%** na alta renda. Entre os presentes, a média vai de **506,2** (baixa renda) a **620,5** (alta renda).
- **Território:** entre as 27 UFs, IDHM e nota média têm **r = 0,71**, mas a correlação é ecológica. No modelo individual, o IDHM perde o efeito (**−7,3 pontos** por desvio padrão) depois de controlar o perfil do aluno e a região.
- **Modelos:** a Regressão Linear explica **29,9%** da variância da nota (R² = 0,299; MAE = 62,7 pontos). Para identificar quem passa de 700 pontos (4,05% dos alunos), os três classificadores empatam tecnicamente na validação cruzada (F1 entre 0,339 e 0,350). O modelo escolhido, a **Regressão Logística**, tem no teste F1 = 0,336, ROC-AUC = 0,872, recall = 0,499 e precisão = 0,253.

| Modelo (teste) | Acurácia | Precisão | Recall | F1 | ROC-AUC | CV F1 (média ± dp) |
|---|---|---|---|---|---|---|
| Regressão Logística | 0,920 | 0,253 | 0,499 | 0,336 | 0,872 | 0,344 ± 0,019 |
| Árvore de Decisão | 0,909 | 0,229 | 0,525 | 0,319 | 0,862 | 0,339 ± 0,021 |
| KNN | 0,929 | 0,272 | 0,440 | 0,336 | 0,864 | 0,350 ± 0,019 |

Os números vêm de [`resultados/metricas_entrega2.json`](resultados/metricas_entrega2.json), que o notebook da Entrega 2 grava ao ser executado.

## Fontes de dados

| Base | Fonte | Ano | Uso |
|---|---|---|---|
| Microdados do ENEM | [INEP](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem) (`microdados_enem_2023.zip`) | 2023 | Notas, presença, tipo de escola e questionário socioeconômico |
| População residente | IBGE, Censo Demográfico ([SIDRA, tabela 4709](https://sidra.ibge.gov.br/tabela/4709)) | 2022 | Densidade de inscritos |
| Rendimento médio mensal real domiciliar per capita | IBGE, PNAD Contínua ([SIDRA, tabela 7531](https://sidra.ibge.gov.br/tabela/7531)) | 2023 | Gap de nota entre UFs |
| IDHM | PNUD, Ipea e FJP, *Radar IDHM 2012–2024* (Atlas Brasil), Tabela 5 | 2023 | Correlação estadual e feature dos modelos |

**Por que o ENEM 2023 e não 2024 ou 2025?** A partir de 2024, o INEP publica notas e questionário socioeconômico em arquivos separados, sem chave de ligação. Com isso, não é possível cruzar renda com nota no nível do aluno. Detalhes em [`docs/DECISOES.md`](docs/DECISOES.md).

## Como rodar

Requer Python 3.12.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

jupyter notebook   # abra os notebooks e execute "Run All"
# ou, sem abrir o navegador:
jupyter nbconvert --to notebook --execute --inplace Entrega1_ENEM_IBGE.ipynb
jupyter nbconvert --to notebook --execute --inplace Entrega2_ENEM_IBGE.ipynb
```

A amostra processada (`dados/processados/enem_amostra.parquet`, ~1 MB) e a tabela estadual (`dados/ibge_uf.csv`) **já estão no repositório**, então os notebooks rodam sem baixar nada. A Entrega 1 roda em cerca de 20 segundos e a Entrega 2 em 1 a 2 minutos.

Para conferir requisitos, coerência dos números e higiene do repositório depois de executar os notebooks:

```bash
python ferramentas/verificar_entrega.py
```

Para rodar sem os dados reais, mude `USAR_DADOS_REAIS = False` na primeira célula de código. Os notebooks passam a usar a simulação reprodutível da Entrega 1. A Entrega 2 continua funcionando nesse modo, mas com menos variáveis.

## Como baixar e reprocessar os dados

```bash
python baixar_dados.py             # download do ENEM + amostra + tabela do IBGE
python baixar_dados.py --so-ibge   # apenas dados/ibge_uf.csv (API do SIDRA)
python baixar_dados.py --so-enem   # apenas download e amostra do ENEM
```

O script:
1. baixa `microdados_enem_2023.zip` (~550 MB) do INEP para `dados/brutos/` (pasta fora do Git);
2. lê o CSV de 1,8 GB **de dentro do zip, em blocos** (`pd.read_csv(sep=";", encoding="latin-1", usecols=..., dtype=..., chunksize=500_000)`), mantém os concluintes de 2023 com escola informada (1.401.159 de 3.933.955 inscritos) e sorteia **4% de cada UF** (`SEED = 42`);
3. consulta a API do SIDRA (população e renda per capita) e grava `dados/ibge_uf.csv` com fonte e ano de cada indicador.

**Passo manual (se o download automático falhar):** baixe `microdados_enem_2023.zip` na [página de microdados do ENEM](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem), salve em `dados/brutos/` sem descompactar e rode `python baixar_dados.py --so-enem`.

## Estrutura de pastas

```
├── Entrega1_ENEM_IBGE.ipynb      # Entrega 1: ETL, descritivas, 20 KPIs, Gráficos 1–5
├── Entrega2_ENEM_IBGE.ipynb      # Entrega 2: EDA, features, modelos, avaliação, Gráficos 6–14
├── baixar_dados.py               # coleta: INEP (download + amostra) e IBGE (API SIDRA)
├── requirements.txt
├── ferramentas/
│   └── verificar_entrega.py      # checagem automática de requisitos, números e repositório
├── src/
│   ├── dados.py                  # carga real/simulada, ETL e recorte de presentes
│   ├── kpis.py                   # cálculo dos 20 KPIs
│   ├── features.py               # feature engineering e outliers por IQR
│   ├── modelagem.py              # Pipeline/ColumnTransformer e métricas
│   └── estilo.py                 # paleta e tema dos gráficos
├── dados/
│   ├── ibge_uf.csv               # indicadores das 27 UFs (com fonte e ano)
│   ├── processados/
│   │   ├── enem_amostra.parquet  # amostra estratificada (56.048 linhas)
│   │   └── enem_amostra_meta.json# funil de filtros e contagens por UF
│   └── brutos/                   # zip do INEP (ignorado pelo Git)
├── resultados/
│   └── metricas_entrega2.json    # números gerados pela Entrega 2
└── docs/
    ├── DECISOES.md               # decisões técnicas e incoerências encontradas
    ├── roteiro_relatorio.md      # estrutura do relatório em PDF
    ├── slides_ml.md              # 3 slides de Machine Learning (apresentação de 10 min)
    └── VERIFICACAO.md            # checklist da verificação final
```

## Conceitos da disciplina

| # | Conceito | Onde |
|---|---|---|
| 1 | Coleta de Dados | `baixar_dados.py`, Seção 2 da Entrega 2 |
| 2 | Limpeza e Pré-processamento | Seção 3 (ETL, nulos, integração) e Seção 7 (imputação, `StandardScaler`, One-Hot) da Entrega 2 |
| 3 | Estatísticas Descritivas | Seção 4 das duas entregas (média, mediana, moda, desvio, IQR) |
| 4 | KPIs | 20 KPIs em 4 eixos (`src/kpis.py`) |
| 5 | Visualização e Storytelling | 14 gráficos + Seção 11 (insights) da Entrega 2 |
| 6 | Feature Engineering | Seção 6 da Entrega 2 (`src/features.py`) |
| 7 | Modelagem Preditiva | Regressão Linear e Logística, Árvore de Decisão e KNN (Seções 8–10) |

A avaliação usa precisão, recall, F1, matriz de confusão, validação cruzada estratificada e curva de overfitting. Clusterização e regras de associação estão fora do escopo.

## Limitações

- A correlação IDHM × nota é **ecológica** (27 médias estaduais) e não vale para alunos individuais.
- A amostra é aleatória e estratificada, mas o universo (inscritos concluintes do ENEM 2023) **se autosseleciona**: não representa todos os jovens.
- A UF considerada é a **da prova**, não a de residência (o INEP não divulga a residência desde 2022).
- Renda autodeclarada em faixas. Os coeficientes medem **associação**, não causa.
