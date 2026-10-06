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
