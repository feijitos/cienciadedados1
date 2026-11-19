# Quanto da nota do ENEM vem da origem do aluno? Um modelo de 2023 testado no ENEM de 2025

O modelo foi treinado com o ENEM 2023, congelado, e usado para prever a nota média de cada estado em 2025 **antes de abrir as notas reais**. Depois a previsão foi conferida com a realidade. Os dados mostraram coisas que o modelo não via.

**[Dashboard interativo](https://feijitos.github.io/cienciadedados1/)** · [Notebook da validação](Validacao_2023_2025.ipynb) · [Pergunte ao projeto](#pergunte-ao-projeto)

Autores: Marcos Feijó e Pedro Klein. Projeto de Ciência de Dados (CEUB, 2026) sobre microdados públicos do INEP e indicadores do IBGE e do PNUD.

## O que os dados mostram

1. **A desigualdade começa antes da prova.** Entre alunos de baixa renda, **29,6%** faltam à prova. Entre os de alta renda, **9,9%**. Mesmo contando só quem foi, a nota média vai de **506,2** (baixa renda) a **620,5** (alta renda).
2. **A diferença entre escola privada e pública é grande, mas mais da metade dela some quando se comparam alunos parecidos.** A nota média é **616,1** na rede privada e **515,2** na pública. Controlando renda, escolaridade dos pais e acesso a recursos, a escola privada fica associada a **+43,4 pontos**. Na rede privada, **15,1%** dos alunos passam de 700 pontos. Na pública, **1,15%**.
3. **Renda não é destino.** **14,3%** dos alunos de baixa renda tiraram mais de 600 pontos.
4. **De 2023 para 2025, uma prova explica três quartos da queda da nota final** (no universo do estudo, que na realidade de 2025 é aproximado, ver abaixo). A média da redação foi de **630,5** para **582,7**, e só ela tirou **9,5** pontos da nota final. As provas objetivas se compensaram: Linguagens subiu **11,9** pontos, Humanas caiu **13,4** e Matemática caiu **16,8**. A redação não usa a TRI, então não dá para saber se caiu o desempenho ou mudou o critério de correção.
5. **O modelo errou para cima em 22 das 27 UFs e em todas as regiões (na média de cada uma).** Ele previu média nacional de **532,5** para 2025, e a real foi **524,1**. O erro médio por região foi de **+2,2** pontos no Sul a **+13,2** no Norte. E foi maior onde a nota real é menor (correlação **−0,66** entre o erro e a nota real dos estados). O projeto mede esse padrão, mas não sabe explicá-lo.

Esses números vêm de [`resultados/metricas_entrega2.json`](resultados/metricas_entrega2.json) (2023) e de [`resultados/validacao_2025.json`](resultados/validacao_2025.json) (2025). Nenhum número deste README foi digitado sem origem nos arquivos de resultados.

## O teste: previsão cega

1. **Congelar:** o modelo de 2023 (regressão da nota final e modelo de presença) foi salvo em `resultados/modelos/` com SHA-256. Nada foi reajustado depois.
2. **Prever:** só com o arquivo de participantes de 2025 (perfil socioeconômico, sem notas), o modelo previu a nota média de cada UF. A previsão foi commitada e enviada ao GitHub no commit `3eee3c2`.
3. **Conferir:** só então as notas de 2025 foram abertas (**1.288.485** alunos no universo da realidade).

Os microdados de 2025 já eram públicos, então o teste é cego **por procedimento**, e não por cronologia. O histórico do Git registra a ordem.

Para separar as fontes de erro, foram feitas três previsões e comparado o erro médio absoluto por UF (27 pontos):

| Previsão | O que faz | Erro médio por UF (pontos) |
|---|---|---|
| A. Repetição | A média de 2025 é a média real de 2023 | 12,98 |
| B. Modelo com o perfil de 2023 | O que se esperaria se nada tivesse mudado | 12,85 |
| C. Modelo com o perfil de 2025 | Se as relações de 2023 ainda valem | 10,66 |

**Leitura honesta:** a previsão C erra menos que repetir 2023 em todos os cenários de sensibilidade testados. Mas a vantagem média é de **2,33** pontos, com intervalo de 95% de **−0,37** a **5,04**, e o intervalo inclui zero. Em **95,2%** das **5.000** reamostragens (bootstrap) a previsão C ganhou. Com só 27 estados, não dá para chamar a diferença de conclusiva.

## O que este projeto não prova

- **Não prova causa.** Os coeficientes medem associação. A escola privada, por exemplo, carrega junto a renda e a escolaridade da família, mesmo controladas.
- **Correlação de estados não vale para alunos.** O IDHM tem correlação de **0,71** com a nota média das UFs, mas são 27 médias. No modelo individual, o IDHM perde o efeito (**−7,3** pontos por desvio padrão) depois de controlar o perfil do aluno e a região.
- **O modelo prevê médias de grupo, não alunos.** Ele explica **29,9%** da variância da nota individual (R² = 0,299).
- **Não há ligação aluno a aluno em 2025.** Desde 2024 o INEP publica notas e questionário em arquivos separados, sem chave de ligação. A comparação é por médias de UF.
- **O universo de 2025 é aproximado.** O arquivo de resultados não traz conclusão do ensino médio nem treineiro. A aproximação foi calibrada com 2023 e testada em cenários de sensibilidade (detalhes em [`docs/equivalencia_2023_2025.md`](docs/equivalencia_2023_2025.md)).
- **Explicações possíveis, não testadas:** a mudança no público do ENEM (o programa Pé-de-Meia não existia em 2023) e a mudança no critério da redação. Estão registradas como hipóteses, não como resultado.

## Pergunte ao projeto

O repositório inclui um agente que responde perguntas sobre o projeto **usando só os arquivos de resultados**. Ele cita de qual arquivo veio cada número, separa fato de hipótese e diz quando a resposta não está nos dados.

```bash
cd cienciadedados1
claude        # abre o Claude Code na pasta do projeto
```

Depois, dentro do Claude Code:

```text
/pergunte o modelo funcionou?
/pergunte por que o erro é maior no Norte?
/pergunte isso prova que escola privada causa nota maior?
```

A definição do agente está em [`.claude/agents/pergunte-ao-projeto.md`](.claude/agents/pergunte-ao-projeto.md). Ele só lê arquivos: não altera nada no repositório.

### Outros agentes do projeto

Cada agente cuida de uma tarefa e segue as regras do [`CLAUDE.md`](CLAUDE.md), como o teste cego e o modelo congelado.

| Agente | Comando | O que faz |
|---|---|---|
| `agente-dados` | `/novo-ano 2026` | Confere dicionários, universo e mudanças entre anos antes de qualquer previsão |
| `auditor-do-modelo` | `/auditar` | Procura vazamento, confere a ordem do teste cego e refaz os erros por UF |
| `agente-dashboard` | `/atualizar-dashboard` | Regenera a página e testa em celular e tela grande |
| `professor-da-banca` | `/ensaio` | Ensaia a apresentação com perguntas difíceis, uma por vez |
| `agente-2026` | `/checar-2026` | Registra a previsão de 2026 antes dos dados e verifica se o INEP já publicou |

## Dashboard

**[feijitos.github.io/cienciadedados1](https://feijitos.github.io/cienciadedados1/)** é uma página estática (GitHub Pages, sem servidor) com os 20 KPIs e gráficos interativos em Plotly: nota por UF e região, IDHM e renda × nota, nota por faixa de renda e tipo de escola, abstenção por renda, coeficientes da regressão, comparação dos classificadores e a seção "Expectativa × realidade: 2025" com o previsto × real por UF. A página é gerada por [`gerar_dashboard.py`](gerar_dashboard.py).

## Como foi feito

| Etapa | Arquivo |
|---|---|
| Coleta e amostra de 2023 (4% por UF) e indicadores do IBGE | [`baixar_dados.py`](baixar_dados.py) |
| Análise, 20 KPIs, features e modelos (regressão linear e logística, árvore, KNN) | [`Entrega1_ENEM_IBGE.ipynb`](Entrega1_ENEM_IBGE.ipynb), [`Entrega2_ENEM_IBGE.ipynb`](Entrega2_ENEM_IBGE.ipynb), `src/` |
| Congelar o modelo de 2023 | [`congelar_modelo.py`](congelar_modelo.py) |
| Baixar e amostrar 2025 e conferir o universo | [`baixar_ano.py`](baixar_ano.py) |
| Calibrar o universo aproximado com 2023 | [`calibrar_universo.py`](calibrar_universo.py) |
| Previsão cega | [`prever_2025.py`](prever_2025.py) |
| Realidade e comparação | [`realidade_2025.py`](realidade_2025.py), [`Validacao_2023_2025.ipynb`](Validacao_2023_2025.ipynb) |
| Dashboard | [`gerar_dashboard.py`](gerar_dashboard.py) |
| Verificação automática de números, requisitos e repositório | [`ferramentas/verificar_entrega.py`](ferramentas/verificar_entrega.py) |

Decisões e incoerências encontradas pelo caminho estão em [`docs/DECISOES.md`](docs/DECISOES.md). A equivalência de variáveis entre 2023 e 2025 está em [`docs/equivalencia_2023_2025.md`](docs/equivalencia_2023_2025.md). O plano completo da validação está em [`PLANO_PREVISAO_2026.md`](PLANO_PREVISAO_2026.md).

### Como rodar

Requer Python 3.12.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

jupyter notebook   # abra os notebooks e execute "Run All"
```

A amostra processada de 2023 e a tabela estadual já estão no repositório, então os notebooks rodam sem baixar nada. A Entrega 1 roda em alguns segundos e a Entrega 2 em 1 a 2 minutos. Para refazer a validação de 2025, os microdados brutos precisam ser baixados do INEP (ficam em `dados/brutos/`, fora do Git): `baixar_ano.py --ano 2025`, `calibrar_universo.py`, `prever_2025.py` e `realidade_2025.py`, nessa ordem. O modelo congelado já está em `resultados/modelos/`. Três cuidados:

- `calibrar_universo.py` e `prever_2025.py` precisam também do zip do ENEM 2023 (`dados/brutos/microdados_enem_2023.zip`), baixado por [`baixar_dados.py --so-enem`](baixar_dados.py) (com essa opção, a tabela do IBGE não é regravada).
- O arquivo RESULTADOS de 2025 vem compactado em Deflate64, que o Python não abre. Para lê-lo é preciso ter o [7-Zip](https://www.7-zip.org/) instalado. Isso vale para `baixar_ano.py`, `prever_2025.py` (que lê dele só as colunas de presença, nenhuma nota) e `realidade_2025.py`.
- `prever_2025.py` se recusa a refazer a previsão se `resultados/previsao_2025.json` já existir. É de propósito: esse arquivo é o registro do teste cego, gravado antes de abrir as notas, e não pode ser sobrescrito.

Para conferir requisitos, coerência dos números e higiene do repositório:

```bash
python ferramentas/verificar_entrega.py
```

## Fontes de dados

| Base | Fonte | Ano | Uso |
|---|---|---|---|
| Microdados do ENEM | [INEP](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem) | 2023 e 2025 | Notas, presença, tipo de escola e questionário socioeconômico |
| População residente | IBGE, Censo Demográfico ([SIDRA, tabela 4709](https://sidra.ibge.gov.br/tabela/4709)) | 2022 | Densidade de inscritos |
| Rendimento médio mensal real domiciliar per capita | IBGE, PNAD Contínua ([SIDRA, tabela 7531](https://sidra.ibge.gov.br/tabela/7531)) | 2023 | Gap de nota entre UFs |
| IDHM | PNUD, Ipea e FJP, *Radar IDHM 2012–2024* (Atlas Brasil), Tabela 5 | 2023 | Correlação estadual e variável dos modelos |

## Contexto acadêmico

Projeto Prático de Ciência de Dados do CEUB, em duas entregas: a Entrega 1 (28/09/2026) cobre ETL, estatísticas descritivas, 20 KPIs e os Gráficos 1 a 5. A Entrega 2 (23/11/2026) cobre análise exploratória, engenharia de variáveis, os quatro modelos, a avaliação, os Gráficos 6 a 14 e a validação com o ENEM 2025.

Amostra de 2023: **56.048** concluintes do ensino médio (4% de cada UF), dos quais **42.032** fizeram as cinco provas. Para identificar quem passa de 700 pontos (4,05% dos alunos), os três classificadores empatam tecnicamente na validação cruzada. O modelo escolhido, a Regressão Logística, tem no teste F1 = 0,336, ROC-AUC = 0,872, recall = 0,499 e precisão = 0,253.

| Modelo (teste) | Acurácia | Precisão | Recall | F1 | ROC-AUC | CV F1 (média ± dp) |
|---|---|---|---|---|---|---|
| Regressão Logística | 0,920 | 0,253 | 0,499 | 0,336 | 0,872 | 0,344 ± 0,019 |
| Árvore de Decisão | 0,909 | 0,229 | 0,525 | 0,319 | 0,862 | 0,339 ± 0,021 |
| KNN | 0,929 | 0,272 | 0,440 | 0,336 | 0,864 | 0,350 ± 0,019 |

| # | Conceito da disciplina | Onde |
|---|---|---|
| 1 | Coleta de Dados | `baixar_dados.py`, Seção 2 da Entrega 2 |
| 2 | Limpeza e Pré-processamento | Seção 3 (ETL, nulos, integração) e Seção 7 (imputação, `StandardScaler`, One-Hot) da Entrega 2 |
| 3 | Estatísticas Descritivas | Seção 4 das duas entregas (média, mediana, moda, desvio, IQR) |
| 4 | KPIs | 20 KPIs em 4 eixos (`src/kpis.py`) |
| 5 | Visualização e Storytelling | 14 gráficos + Seção 11 (insights) da Entrega 2 + dashboard interativo |
| 6 | Feature Engineering | Seção 6 da Entrega 2 (`src/features.py`) |
| 7 | Modelagem Preditiva | Regressão Linear e Logística, Árvore de Decisão e KNN (Seções 8 a 10) |

A avaliação usa precisão, recall, F1, matriz de confusão, validação cruzada estratificada e curva de overfitting. Clusterização e regras de associação estão fora do escopo.

## Limitações da amostra de 2023

- A amostra é aleatória e estratificada, mas o universo (inscritos concluintes do ENEM 2023) **se autosseleciona**: não representa todos os jovens.
- A UF considerada é a **da prova**, não a de residência (o INEP não divulga a residência desde 2022).
- A renda é autodeclarada em faixas.
