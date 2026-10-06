# Registro de decisões e incoerências

Este arquivo registra as decisões técnicas do projeto e as incoerências encontradas nos dados ou no código. Para cada item há o que foi encontrado, o que foi feito e o motivo.

---

## Sprint 1: carga de dados reais

### D1. Edição do ENEM: 2023, e não 2025 nem 2024
- **Encontrado:** o INEP já publicou os microdados do ENEM 2025 (set/2026) e do 2024. Nas duas edições, os dados vêm em dois arquivos: `RESULTADOS_*.csv` (notas) e `PARTICIPANTES_*.csv` (questionário socioeconômico). Segundo o dicionário oficial, `NU_SEQUENCIAL` (resultados) é "distinta da NU_INSCRICAO disponível na base de Participantes, de modo que não é possível utilizá-la para relacionar as duas bases".
- **Feito:** usamos o **ENEM 2023**, a edição mais recente em que nota, renda familiar (`Q006`) e tipo de escola (`TP_ESCOLA`) estão no mesmo registro.
- **Por quê:** a pergunta central do projeto (renda e tipo de escola → nota) e os modelos da Entrega 2 exigem esse cruzamento no nível do aluno.

### D2. Universo de análise: concluintes de 2023
- **Encontrado:** no ENEM 2023, `TP_ESCOLA` só é preenchido para quem concluiria o ensino médio em 2023 (`TP_ST_CONCLUSAO = 2`). Para os demais 2.532.796 inscritos (egressos, treineiros etc.) o valor é 1 = "Não respondeu". Contagem na base completa: 1 → 2.532.796; 2 (Pública) → 1.166.540; 3 (Privada) → 234.619. Outros 5 registros têm `TP_ST_CONCLUSAO = 2` com `TP_ESCOLA = 1`.
- **Feito:** o universo são os **concluintes de 2023, não treineiros, com escola informada**: 1.401.159 de 3.933.955 inscritos. O funil completo está em `dados/processados/enem_amostra_meta.json`.
- **Por quê:** os KPIs da Entrega 1 e o One-Hot de `TP_ESCOLA` precisam das categorias Pública/Privada. Incluir "Não respondeu" misturaria populações bem diferentes (egressos de anos anteriores × concluintes).

### D3. Amostra estratificada por UF (4%)
- **Feito:** `baixar_dados.py` lê o CSV de dentro do zip em blocos de 500 mil linhas (`sep=";"`, `encoding="latin-1"`, `usecols` e `dtype` explícitos), aplica o filtro de D2 e sorteia **4% de cada UF** (`groupby(UF).sample(frac=0.04, random_state=42)`). Resultado: **56.048 linhas**, salvas em `dados/processados/enem_amostra.parquet` (≈1,1 MB, versionado).
- **Por quê:** a alocação proporcional preserva o peso de cada UF. Com 4%, a menor UF (RR) ainda tem 129 alunos na amostra, o que basta para médias estaduais, e a modelagem da Entrega 2 (GridSearchCV com KNN) roda em minutos. O arquivo pequeno permite rodar os notebooks sem baixar os 550 MB.

### D4. UF do aluno = UF da prova
- **Encontrado:** desde 2022 o INEP não divulga a UF/município de residência. A UF da escola (`SG_UF_ESC`) só existe para parte dos concluintes.
- **Feito:** `UF` = `SG_UF_PROVA`.
- **Por quê:** é a única UF disponível para todos. Quase sempre coincide com a de residência, mas isso é uma limitação a declarar.

### D5. Presença unificada (`TP_PRESENCA`)
- **Encontrado:** nos dados reais a presença vem em 4 colunas (`TP_PRESENCA_CN/CH/LC/MT`). O notebook usava uma só (`TP_PRESENCA`: 0/1/2).
- **Feito:** 2 = eliminado em alguma prova; 1 = presente nas quatro; 0 = caso contrário (faltou a pelo menos um dos dois dias).
- **Por quê:** mantém a lógica dos KPIs de presença e abstenção. "Faltou a um dos dias" conta como abstenção porque, sem as 5 notas, não há `NOTA_FINAL`.

### D6. Indicadores estaduais reais (`dados/ibge_uf.csv`)
| Indicador | Fonte | Ano | Como foi obtido |
|---|---|---|---|
| População residente | IBGE, Censo Demográfico | 2022 | API SIDRA, tabela 4709, variável 93 |
| Rendimento médio mensal real domiciliar per capita (R$) | IBGE, PNAD Contínua anual | 2023 | API SIDRA, tabela 7531, variável 10824, classe "Total" |
| IDHM | PNUD/Ipea/FJP, Radar IDHM 2012–2024 (Atlas Brasil) | 2023 | Transcrito da Tabela 5 (p. 125) do relatório (o PNUD não tem API para essa tabela) |
| Região | IBGE | n/a | Pela UF |

- **Por quê usar 2023 em renda e IDHM:** é o mesmo ano do ENEM. A população vem do Censo 2022, a contagem oficial mais próxima.

### D7. Incoerências encontradas no código/dados da Entrega 1
1. **Rótulo "IDH estadual (IBGE)" no Gráfico 3.** O IDHM é calculado pelo PNUD/Ipea/FJP, não pelo IBGE. *Feito:* o rótulo passou a ser "IDHM estadual (PNUD/Atlas Brasil)". O nome do eixo de KPIs "C) Cruzamento IBGE" foi mantido para não mudar a estrutura dos 20 KPIs, e a nota metodológica explica a fonte.
2. **Valores "aproximados" do IBGE na simulação.** A população da simulação já era do Censo 2022, exceto MG: 20.538.718 (divulgação preliminar) contra 20.539.989 no SIDRA atual. O IDH simulado correspondia à série antiga do IDHM 2021. A renda per capita era arredondada. *Feito:* a simulação ficou intacta (é só fallback) e os dados reais vêm do SIDRA/PNUD.
3. **Nulos "acidentais" em presentes.** A seção de ETL previa remover presentes com nota faltante (falha de registro). Nos dados reais do ENEM 2023 isso **não acontece**: todo nulo de nota corresponde a falta ou eliminação. *Feito:* a regra continua no código (a simulação gera esses casos) e o texto explica a diferença.
4. **`Q006` como categoria.** O `ord(x) - 65` do ETL espera texto. O Parquet guarda `Q006` como `category`. *Feito:* o carregador converte para `str` antes do ETL, o que preserva a lógica de `RENDA_IDX`.
5. **KPI 13 (densidade de inscritos por 100 mil hab.).** Com dados reais, ele é calculado **sobre a amostra de 4% dos concluintes**, não sobre todos os inscritos. *Feito:* a lógica não mudou, como pedido, e o rótulo já dizia "(amostra)". Para estimar o valor no universo, basta dividir por 0,04.

### D8. Simulação mantida como fallback
- `USAR_DADOS_REAIS = True/False` no início do notebook. As funções `gerar_ibge()` e `gerar_enem()` não foram alteradas.

---

## Sprint 2: pré-processamento e modelagem

### D9. Funções extraídas para `src/` (fonte única)
- **Feito:** carga, ETL e KPIs saíram do notebook da Entrega 1 e foram para `src/dados.py` e `src/kpis.py`. Feature engineering, pré-processamento/avaliação e estilo dos gráficos ficam em `src/features.py`, `src/modelagem.py` e `src/estilo.py`. **Os dois notebooks importam desses módulos.**
- **Verificação de equivalência:** com a simulação, `src` reproduz exatamente os DataFrames do notebook original (`df_ibge`, `df_enem`, `df`, `df_pres` e `df_kpis`, comparados com `pd.testing.assert_frame_equal`). Com dados reais, os 20 KPIs são idênticos aos da Sprint 1.
- **Por quê:** evita duas cópias do mesmo código, que poderiam divergir. Os 20 KPIs e os gráficos 1–5 mantêm a mesma lógica.
- **Ajuste em `gerar_enem()`:** o gerador aleatório passou de parâmetro padrão global (`rng=rng`) para `rng=None`, que cria `default_rng(SEED)`. O resultado é idêntico ao do notebook original executado do início.

### D10. Paleta de cores validada
- **Encontrado:** a paleta original (`#2F5D8A`, `#C0504D`, `#E8B04B`) não passou no validador de cores: o azul tem croma abaixo do mínimo (lê-se como cinza) e o amarelo fica fora da faixa de luminosidade, com contraste de 1,9:1.
- **Feito:** paleta categórica azul/laranja/verde-água (aprovada em separação para daltonismo, ΔE ≥ 8), rampa sequencial azul para as faixas de renda (que são ordinais) e mapa divergente para correlações, tudo em `src/estilo.py`. Os gráficos 1–5 só mudaram de cor.

### D11. Universo da modelagem e alvo
- Modelagem sobre os **presentes com as 5 notas** (42.032 alunos). Alvo da regressão: `NOTA_FINAL`. Alvo da classificação: `ALTO_DESEMPENHO = NOTA_FINAL > 700` (4,05% de positivos).
- **Divisão única 80/20**, estratificada pelo alvo da classificação, `random_state = 42`, usada por todos os modelos (inclusive a regressão), para que todos sejam avaliados nos mesmos alunos de teste.

### D12. Features e exclusões
- **Incluídas:** `LOG_RENDA_PC`, `N_MORADORES`, `ESC_MAE`, `ESC_PAI`, `N_COMPUTADORES`, `TEM_INTERNET`, `ATRASO_ESCOLAR`, `IDH_ESTADUAL` (numéricas) e `TP_ESCOLA`, `REGIAO`, `FAIXA_RENDA`, `SEXO`, `COR_RACA` (One-Hot).
- **Excluídas:** as notas das provas, porque compõem o alvo (vazamento), e `RENDA_PER_CAPITA` da UF, que tem r = 0,96 com o IDHM entre as 27 UFs. Com as duas no modelo, os coeficientes ficariam instáveis.
- **Categorias de referência explícitas** no One-Hot (Pública, Nordeste, Baixa Renda, Feminino, Branca), em vez da primeira em ordem alfabética. Assim, cada coeficiente é uma comparação com um grupo de referência claro.
- **Colinearidade conhecida:** `LOG_RENDA_PC` e `FAIXA_RENDA` vêm do mesmo `Q006`. A `FAIXA_RENDA` foi mantida porque o One-Hot dessa variável é pedido explicitamente. O notebook avisa que os coeficientes de renda não devem ser lidos isoladamente (Média +12,0 > Alta +8,7 é efeito da repartição com `LOG_RENDA_PC`).
- **"Não sei" na escolaridade dos pais** (`Q001`/`Q002` = H) vira ausente e é imputado pela mediana **dentro do Pipeline**.
- **Faixa aberta do Q006** (Q, acima de R$ 26.400): ponto médio = 1,25 × limite inferior = R$ 33.000.

### D13. Desbalanceamento: grau de rebalanceamento como hiperparâmetro
- **Encontrado no protótipo:** com `class_weight="balanced"` (peso ~24 para a classe 1), o recall chegava a ~0,80, mas a precisão caía para ~0,15 (F1 ≈ 0,25).
- **Feito:** o peso da classe positiva (3, 6, 10 ou `"balanced"`) virou hiperparâmetro do GridSearchCV na Logística e na Árvore. No KNN, que não aceita pesos, o `sampling_strategy` do `RandomUnderSampler` (0,1, 0,2, 0,5 ou 1,0) entra no `imblearn.Pipeline`, de modo que o undersampling só acontece no treino de cada dobra. O CV escolheu peso 6 (Logística e Árvore) e proporção 0,2 (KNN), e o F1 subiu para ~0,34.
- **Por quê:** "tratar o desbalanceamento" não deve significar forçar 50/50. O nível de compensação que maximiza o F1 é escolhido pelos dados.
- **Nova dependência:** `imbalanced-learn`.

### D14. Grade do KNN
- **Encontrado:** com a grade inicial (15–101 e depois 51–201), o melhor `n_neighbors` sempre ficava na borda.
- **Feito:** uma varredura de 51 a 601 mostrou pico de CV F1 em k = 201 (0,350) e queda a partir de 301. A grade final é `[51, 101, 201, 301, 401]`, com o ótimo no interior.

### D15. Seleção do modelo final pela validação cruzada, não pelo teste
- **Encontrado:** a primeira versão do texto escolhia o "melhor modelo" pelo F1 do **conjunto de teste**. Isso é uma forma de vazamento na seleção de modelos.
- **Feito:** a seleção usa o **CV F1**. Se a diferença entre o melhor e o pior modelo for menor que o maior desvio padrão da CV, há empate técnico, e escolhemos a Regressão Logística por interpretabilidade. A regra é calculada no notebook. Resultado: KNN 0,350, Logística 0,344, Árvore 0,339 (amplitude 0,011 < dp 0,021) → empate → **Regressão Logística**.

### D16. Moda de notas contínuas
- **Encontrado:** a moda de Matemática (arredondada) é **0**, por causa de 204 alunos que zeraram. É o único valor inteiro que se repete muito numa nota contínua de TRI.
- **Feito:** o valor foi mantido (é o resultado correto do cálculo) e a tabela ganhou a **classe modal** (intervalos de 20 pontos), com um texto gerado que explica a diferença.

### D17. Outliers mantidos
- Sinalizados por IQR (coluna `OUTLIER_IQR`), **não removidos**: todas as notas estão no domínio válido, os extremos são resultados reais (redações anuladas, desempenhos muito altos) e removê-los apagaria parte da classe positiva.

### D18. Textos com números gerados por código
- Todo texto do notebook da Entrega 2 que cita resultados (leitura dos coeficientes, diagnóstico de overfitting, seleção de modelo e os 4 insights) é montado com `Markdown(f"...")` a partir das variáveis. As afirmações qualitativas ("há/não há overfitting", "empate técnico") também são decididas por condições no código. Os números finais ficam em `resultados/metricas_entrega2.json`, que serve de fonte para o README e para `docs/`.

### D19. `n_jobs=-1` e mensagens do joblib no Windows
- Com processamento paralelo, o *resource tracker* do joblib/loky imprime `KeyError` no stderr do terminal ao encerrar, no Windows. É um problema conhecido da biblioteca: **não aparece nas saídas do notebook** e não afeta os resultados (que são determinísticos: `random_state = 42` em split, CV, árvore e undersampling).
