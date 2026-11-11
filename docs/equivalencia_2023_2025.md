# Equivalência de variáveis: ENEM 2023 × ENEM 2025

Etapa de 14–15/11 do `PLANO_PREVISAO_2026.md`. Compara, variável a variável, o que o modelo congelado de 2023
(`resultados/modelos/`) e o filtro do universo usam com o que existe nos microdados do ENEM 2025.

**Fontes:** dicionários oficiais do INEP, `Dicionário_Microdados_Enem_2023.xlsx` (zip de 2023) e
`Dicionário_Microdados_Enem_2025.xlsx` (zip de 2025, publicado em 15/09/2026), em
`https://download.inep.gov.br/microdados/microdados_enem_<ano>.zip`. Só os dicionários foram extraídos, lendo o
zip remoto por partes (70 a 80 KB de cada zip); os microdados ainda não foram baixados. Cópias locais em
`dados/brutos/dicionarios/` (fora do Git).

## Respostas curtas

1. **Dá para comparar por UF? Sim.** `SG_UF_PROVA` está nos dois arquivos de 2025, com as mesmas siglas. O
   universo do lado real precisa de uma aproximação (ver "Universo"), que deve ser conferida contando inscritos
   por UF nos dois arquivos logo depois do download.
2. **Dá para comparar por UF × tipo de escola? Sim, com ressalva.** O tipo de escola não vem mais da mesma
   variável nos dois lados: na previsão vem da pergunta Q023 (trajetória declarada pelo aluno, com opções
   mistas) e na realidade vem de `TP_DEPENDENCIA_ADM_ESC` (rede da escola de conclusão, pelo cadastro). As duas
   medem coisas parecidas, mas não iguais. Fica como comparação secundária (já é a primeira a ser cortada se o
   prazo apertar, seção 6 do plano).
3. **Quais variáveis do modelo se perdem? Nenhuma por completo.** Das 13 variáveis do modelo:
   - 11 têm equivalente direto com os mesmos códigos (renda per capita e faixa de renda, moradores, escolaridade
     da mãe e do pai, computadores, atraso escolar, IDHM, região, sexo, cor/raça). A renda mudou de nome
     (Q006 → Q007) e os computadores também (Q024 → Q021).
   - 2 mudam de definição e entram como aproximação, com teste de sensibilidade: **internet em casa** (2025 pergunta
     só por wi-fi) e **tipo de escola** (`TP_ESCOLA` deixou de existir; usar Q023).

## Como os arquivos mudaram

| | 2023 | 2025 |
|---|---|---|
| Arquivos | um só: `MICRODADOS_ENEM_2023.csv` (1,8 GB) | `PARTICIPANTES_2025.csv` (513 MB) e `RESULTADOS_2025.csv` (2,1 GB); zip de 1,04 GB |
| Perfil (questionário, conclusão, treineiro) | no arquivo único | só em PARTICIPANTES |
| Presença e notas | no arquivo único | só em RESULTADOS |
| Ligação aluno a aluno | sim (mesma linha) | **não**: `NU_SEQUENCIAL` de RESULTADOS é diferente de `NU_INSCRICAO` de PARTICIPANTES (nota 1 do dicionário de RESULTADOS) |
| Colunas comuns aos dois arquivos | — | só `NU_ANO` e local da prova (`CO_MUNICIPIO_PROVA`, `NO_MUNICIPIO_PROVA`, `CO_UF_PROVA`, `SG_UF_PROVA`) |
| Questionário | Q001 a Q025 | Q001 a Q023, **renumerado** a partir da Q006 |

## Tabela de equivalência

"Arquivo" é onde a variável está em 2025 (P = PARTICIPANTES, R = RESULTADOS).

| Variável | Nome em 2023 | Nome em 2025 | Arquivo | Códigos e faixas | O que fazer |
|---|---|---|---|---|---|
| UF da prova | `SG_UF_PROVA` | `SG_UF_PROVA` | P e R | Iguais (27 siglas). | Usar direto. Região e IDHM saem da UF por `dados/ibge_uf.csv`, como em 2023. |
| Conclusão do ensino médio | `TP_ST_CONCLUSAO` | `TP_ST_CONCLUSAO` | P | Iguais (1 a 4; 2 = concluirá no ano da prova). | Em P: filtrar `= 2`. R não tem: ver "Universo". |
| Treineiro | `IN_TREINEIRO` | `IN_TREINEIRO` | P | Iguais (0/1) e mesma definição (nota 3: quem não concluiu e não concluiria no ano). | Em P: filtrar `= 0` (com `TP_ST_CONCLUSAO = 2` já fica redundante, como em 2023). R não tem. |
| Tipo de escola | `TP_ESCOLA` (1 não respondeu, 2 pública, 3 privada) | **não existe** | — | — | Previsão: usar `Q023` (linha abaixo). Realidade: usar `TP_DEPENDENCIA_ADM_ESC` (linha abaixo). |
| Tipo de escola (previsão) | — | `Q023` "Em que tipo de escola você frequentou ou frequenta o Ensino Médio?" | P | Nova: A só pública; B e C parte pública, parte privada (sem/com bolsa integral); D e E só privada (sem/com bolsa integral); F não frequentou. | A → Pública; D, E → Privada; F e em branco → fora do universo. B, C (trajetória mista): **"Pública" atribuída explicitamente no código** (cenário principal) e "Privada" no teste de sensibilidade. A proporção de B e C (por UF e no total) fica na seção "Conferência pós-download". |
| Tipo de escola (realidade) | `TP_DEPENDENCIA_ADM_ESC` (também existia) | `TP_DEPENDENCIA_ADM_ESC` | R | Iguais: 1 federal, 2 estadual, 3 municipal, 4 privada. | 1, 2, 3 → Pública; 4 → Privada. É a rede da escola de conclusão (cadastro), não a declaração do aluno. |
| Presença | `TP_PRESENCA_CN`, `_CH`, `_LC`, `_MT` | iguais | R | Iguais: 0 faltou, 1 presente, 2 eliminado. | Realidade: mesma regra de 2023 (`unificar_presenca`). Previsão: P não tem presença, então a média por UF é ponderada pelo modelo de presença congelado (como previsto no plano). |
| Notas | `NU_NOTA_CN`, `_CH`, `_LC`, `_MT`, `_REDACAO` | iguais | R | Mesmas escalas (objetivas na TRI; redação de 0 a 1000). | `NOTA_FINAL` = média das 5, como em 2023. A redação não usa a TRI: comparar à parte (seção 5 do plano). |
| Escolaridade do pai | `Q001` | `Q001` | P | Iguais: A a G, H = "Não sei". | Usar direto (H vira ausente). |
| Escolaridade da mãe | `Q002` | `Q002` | P | Iguais: A a G, H = "Não sei". | Usar direto. |
| Moradores | `Q005` | `Q005` | P | Iguais: 1 a 20. | Usar direto. |
| Renda familiar | `Q006` | **`Q007`** | P | Mesmas 17 letras (A a Q) e **mesmos múltiplos do salário mínimo** em todas as faixas (2023: SM = R$ 1.320; 2025: SM = R$ 1.518). Conferido faixa a faixa. | Ler `Q007` e aplicar a mesma tabela de pontos médios convertida em salários mínimos (`PONTO_MEDIO_Q006` ÷ 1.320). Não usar os valores em R$ de 2025 divididos por 1.320. `FAIXA_RENDA` (A–D, E–H, I–Q) segue igual. **Atenção: em 2025 a `Q006` é "Você possui renda?" (A não, B sim). Ler `Q006` daria um erro silencioso.** Proteção: o código de 2025 tem asserts que exigem `Q007` só com A–Q (e mais de duas letras diferentes) e `Q006` só com A e B; se falharem, ele para. |
| Computadores em casa | `Q024` "tem computador?" | **`Q021`** "existe computador/notebook?" | P | Iguais: A nenhum a E quatro ou mais. | Usar `Q021`. A pergunta agora cita o notebook explicitamente; pode haver um pouco mais de "sim". |
| Internet em casa | `Q025` "tem acesso à Internet?" | **`Q020`** "existe acesso à internet por rede wi-fi?" | P | Iguais (A não, B sim), mas o conceito é **mais estreito** em 2025 (quem só tem dados móveis responde "não"). | Principal: `Q020` como aproximação. Sensibilidade: deixar sem valor (o Pipeline imputa a mediana do treino). Registrar a diferença entre as duas. |
| Sexo | `TP_SEXO` | `TP_SEXO` | P | Iguais (M, F). | Usar direto. |
| Cor/raça | `TP_COR_RACA` | `TP_COR_RACA` | P | 0 a 5 iguais; o código 6 ("Não dispõe da informação") só existe em 2023. | Usar direto; o mapeamento atual (0 e 6 → "Não declarada") já cobre. |
| Faixa etária | `TP_FAIXA_ETARIA` | `TP_FAIXA_ETARIA` | P | Iguais: 1 a 20, idade em 31/12 do ano da prova. | Usar direto. `ATRASO_ESCOLAR` (faixa 4 ou mais = 19 anos ou mais) não muda. |

## Universo: o filtro de 2023 em cada lado

Em 2023 o universo foi: concluintes no ano (`TP_ST_CONCLUSAO = 2`), não treineiros (`IN_TREINEIRO = 0`) e com
escola pública ou privada informada (`TP_ESCOLA` 2 ou 3). Em 2025 nenhum dos dois arquivos tem as três coisas.

- **Previsão (PARTICIPANTES):** `TP_ST_CONCLUSAO = 2`, `IN_TREINEIRO = 0` e `Q023` diferente de F. É o filtro mais
  próximo do de 2023.
- **Realidade (RESULTADOS):** não há conclusão nem treineiro. Aproximação: `TP_DEPENDENCIA_ADM_ESC` preenchida
  (escola de conclusão informada), presente nas quatro provas e com as cinco notas.
- **Conferência obrigatória no download (16–17/11):** contar, por UF, os inscritos no universo de P e os inscritos
  no universo aproximado de R (todos os inscritos, presentes ou não, nos dois lados). **Critério: diferença de até
  5% em cada UF = aproximação aceita.** Acima disso, listar as UFs e parar antes de prever. É uma comparação só de
  contagens, sem ligar alunos.
- **Teste cego preservado:** para essa conferência, o RESULTADOS é lido só nas colunas `SG_UF_PROVA` e
  `TP_DEPENDENCIA_ADM_ESC` (nenhuma nota, nenhuma presença). As notas só são lidas depois do commit de
  `resultados/previsao_2025.json` (seção 4 do plano).

## Decisões aprovadas (10/11/2026)

1. **Trajetória mista (Q023 B ou C):** "Pública" atribuída explicitamente no código no cenário principal; "Privada"
   no teste de sensibilidade. Registrar a proporção por UF e no total; **acima de 10% no total, avisar**, porque a
   comparação UF × tipo de escola fica fraca.
2. **Internet:** `Q020` (wi-fi) no cenário principal; em branco (imputado pela mediana do treino) na sensibilidade.
3. **Universo da realidade:** escola de conclusão preenchida em RESULTADOS, aceito se a diferença de inscritos por
   UF em relação a PARTICIPANTES for de até 5% em todas as UFs.
4. **Armadilha da renda:** asserts no código de 2025 para `Q007` (só A–Q) e `Q006` (só A e B).

## Conferência pós-download

<!-- início: gerado por baixar_ano.py (não editar à mão) -->
Ainda não executada. Roda com `python3.11 baixar_ano.py --ano 2025`.
<!-- fim: gerado por baixar_ano.py -->



## Outros pontos para as próximas etapas

- **COP30:** parte das provas de 2025 em Belém, Ananindeua e Marituba (PA) foi aplicada em versão específica
  (códigos de prova "BAM2", nota 2 do dicionário de RESULTADOS). As notas estão na mesma escala, mas o PA merece
  uma observação na análise.
- **Tamanho:** os dois CSVs somam 2,6 GB descompactados. Ler em blocos, como o `baixar_dados.py`, e guardar só a
  amostra de PARTICIPANTES e os agregados de RESULTADOS.
- **Redação dentro da nota final:** o alvo do modelo (`NOTA_FINAL`) inclui a redação, que não está na TRI. A
  comparação principal continua sendo a nota final (como foi treinada), com as provas objetivas à parte.
