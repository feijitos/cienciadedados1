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

## Decisões depois da conferência (10/11/2026)

A conferência abaixo reprovou a aproximação pelo critério de 5% em parte das UFs (a falta é sempre do mesmo lado:
o universo de RESULTADOS sai menor em todas as UFs). Decidido:

1. **Calibrar a aproximação com 2023**, que tem as duas definições no mesmo arquivo (seção "Calibração com 2023").
   Se o MAE das diferenças por UF ficar abaixo de ~3 pontos, a aproximação fica justificada; se ficar acima, o viés
   por UF de 2023 é avaliado antes de decidir se vira correção no lado da realidade de 2025.
2. **Comparação principal com as 27 UFs**, e uma **sensibilidade sem as UFs acima de 5%** na conferência.

## Conferência pós-download

<!-- início: gerado por baixar_ano.py (não editar à mão) -->
Gerado por `baixar_ano.py --ano 2025`. Universo de PARTICIPANTES: concluintes em 2025, não treineiros, Q023 de A a E. Universo aproximado de RESULTADOS: escola de conclusão preenchida. Os dois contam inscritos (presentes ou não).

**Funil de PARTICIPANTES:** linhas lidas: 4.810.772; concluintes 2025: 1.811.344; nao treineiros: 1.811.344; q023 respondida: 1.811.344; escola informada q023 A a E: 1.810.641.

**Q023 entre concluintes não treineiros:** A: 1.455.957; B: 58.124; C: 28.491; D: 211.093; E: 56.976; F: 703.

**Resultado:** diferença total de -4,0%; **aproximação NÃO aceita**: 11 UF(s) acima de 5% (AL, DF, GO, MA, MS, MT, PA, PI, PR, RJ, RR). Parar antes de prever.
Trajetória mista (Q023 B ou C): 4,8% do universo de PARTICIPANTES (abaixo do limite de 10%).

| UF | Universo PARTICIPANTES | Universo aproximado RESULTADOS | Diferença | Trajetória mista | Situação |
|---|---:|---:|---:|---:|---|
| AC | 10.057 | 9.642 | -4,1% | 2,4% | ok |
| AL | 36.532 | 32.527 | -11,0% | 4,2% | **acima de 5%** |
| AM | 49.994 | 48.966 | -2,1% | 2,7% | ok |
| AP | 9.064 | 8.665 | -4,4% | 3,3% | ok |
| BA | 138.622 | 133.968 | -3,4% | 5,0% | ok |
| CE | 118.490 | 114.807 | -3,1% | 3,1% | ok |
| DF | 27.048 | 25.473 | -5,8% | 5,9% | **acima de 5%** |
| ES | 33.798 | 32.791 | -3,0% | 3,7% | ok |
| GO | 72.648 | 67.427 | -7,2% | 5,9% | **acima de 5%** |
| MA | 69.791 | 65.792 | -5,7% | 3,4% | **acima de 5%** |
| MG | 175.008 | 170.828 | -2,4% | 3,9% | ok |
| MS | 22.681 | 21.478 | -5,3% | 4,8% | **acima de 5%** |
| MT | 34.532 | 32.671 | -5,4% | 5,1% | **acima de 5%** |
| PA | 83.561 | 76.543 | -8,4% | 3,8% | **acima de 5%** |
| PB | 40.906 | 39.251 | -4,0% | 4,5% | ok |
| PE | 89.935 | 87.835 | -2,3% | 5,5% | ok |
| PI | 38.979 | 36.876 | -5,4% | 3,4% | **acima de 5%** |
| PR | 92.085 | 86.784 | -5,8% | 5,2% | **acima de 5%** |
| RJ | 108.170 | 102.489 | -5,3% | 7,8% | **acima de 5%** |
| RN | 31.426 | 31.021 | -1,3% | 4,3% | ok |
| RO | 21.063 | 20.612 | -2,1% | 4,3% | ok |
| RR | 4.937 | 4.571 | -7,4% | 3,5% | **acima de 5%** |
| RS | 67.441 | 64.948 | -3,7% | 4,6% | ok |
| SC | 51.370 | 50.591 | -1,5% | 5,6% | ok |
| SE | 23.016 | 22.498 | -2,3% | 5,6% | ok |
| SP | 345.137 | 335.937 | -2,7% | 5,4% | ok |
| TO | 14.350 | 14.037 | -2,2% | 4,2% | ok |
| **Total** | 1.810.641 | 1.739.028 | -4,0% | 4,8% | |
<!-- fim: gerado por baixar_ano.py -->

## Calibração com 2023

<!-- início: gerado por calibrar_universo.py (não editar à mão) -->
Gerado por `calibrar_universo.py` (só dados de 2023). Nota final média por UF no universo verdadeiro (concluintes, não treineiros, escola informada, cinco provas) × no universo aproximado (escola de conclusão preenchida, cinco provas).

**MAE das diferenças por UF: 11,01 pontos** (critério: abaixo de 3), contra 9,3 pontos de erro do modelo por UF. **Acima do critério: ver o viés por UF abaixo.**
Viés médio: +10,92 pontos; maior diferença: BA (+22,24); diferença nacional: +10,63 pontos.
Inscritos: em 2023 a escola de conclusão estava preenchida para só 68,4% do universo verdadeiro (o aproximado tem −31,6%); em 2025 a diferença líquida é bem menor (seção anterior). A correlação entre a lacuna de inscritos por UF de 2023 e a de 2025 é 0,04: o mecanismo da falta mudou, e o viés de 2023 não serve como correção direta para 2025.
**Estimativa para 2025 (hipótese, não medida):** supondo que a lacuna de nota entre quem tem e quem não tem escola preenchida seja a de 2023, o viés por UF em 2025 seria a parcela que falta × essa lacuna: MAE de 1,39 pontos, maior em AL (+3,01).
Universo de PARTICIPANTES: 1.401.159 em 2023 e 1.810.641 em 2025 (+29,2%).

| UF | Média verdadeiro 2023 | Média aproximado 2023 | Viés 2023 (pts) | Falta 2023 | Lacuna (pts) | Falta 2025 | Viés 2025 estimado (pts) |
|---|---:|---:|---:|---:|---:|---:|---:|
| AC | 510,1 | 519,0 | +8,86 | 39,8% | +22,3 | 4,1% | +0,92 |
| AL | 512,0 | 520,4 | +8,33 | 30,4% | +27,4 | 11,0% | +3,01 |
| AM | 491,4 | 497,5 | +6,04 | 29,3% | +20,6 | 2,1% | +0,42 |
| AP | 508,7 | 523,4 | +14,76 | 42,0% | +35,1 | 4,4% | +1,55 |
| BA | 527,0 | 549,2 | +22,24 | 50,0% | +44,4 | 3,4% | +1,49 |
| CE | 505,3 | 504,1 | −1,21 | 9,9% | −12,2 | 3,1% | −0,38 |
| DF | 554,3 | 565,2 | +10,99 | 23,1% | +47,6 | 5,8% | +2,77 |
| ES | 554,5 | 564,9 | +10,41 | 27,7% | +37,5 | 3,0% | +1,12 |
| GO | 534,9 | 545,7 | +10,80 | 34,1% | +31,7 | 7,2% | +2,27 |
| MA | 497,4 | 505,9 | +8,52 | 37,8% | +22,5 | 5,7% | +1,29 |
| MG | 562,6 | 581,2 | +18,69 | 38,9% | +48,0 | 2,4% | +1,15 |
| MS | 531,1 | 543,3 | +12,17 | 33,2% | +36,6 | 5,3% | +1,94 |
| MT | 524,3 | 535,9 | +11,60 | 33,2% | +34,9 | 5,4% | +1,88 |
| PA | 511,8 | 525,6 | +13,88 | 42,0% | +33,0 | 8,4% | +2,77 |
| PB | 526,9 | 535,5 | +8,54 | 30,9% | +27,6 | 4,0% | +1,12 |
| PE | 528,6 | 539,7 | +11,14 | 34,7% | +32,1 | 2,3% | +0,75 |
| PI | 515,3 | 529,4 | +14,05 | 38,2% | +36,8 | 5,4% | +1,99 |
| PR | 541,8 | 550,5 | +8,78 | 31,6% | +27,8 | 5,8% | +1,60 |
| RJ | 555,7 | 568,8 | +13,13 | 31,5% | +41,7 | 5,3% | +2,19 |
| RN | 541,7 | 559,0 | +17,37 | 33,5% | +51,9 | 1,3% | +0,67 |
| RO | 513,8 | 519,2 | +5,39 | 28,9% | +18,7 | 2,1% | +0,40 |
| RR | 526,2 | 533,4 | +7,23 | 29,0% | +24,9 | 7,4% | +1,85 |
| RS | 557,2 | 568,3 | +11,16 | 32,3% | +34,5 | 3,7% | +1,28 |
| SC | 557,2 | 566,1 | +8,84 | 25,6% | +34,5 | 1,5% | +0,52 |
| SE | 525,4 | 538,9 | +13,45 | 42,0% | +32,0 | 2,3% | +0,72 |
| SP | 557,3 | 566,2 | +8,88 | 26,0% | +34,1 | 2,7% | +0,91 |
| TO | 509,4 | 520,2 | +10,83 | 41,9% | +25,9 | 2,2% | +0,56 |
<!-- fim: gerado por calibrar_universo.py -->

## Crescimento do universo e o Pé-de-Meia

O universo de PARTICIPANTES cresceu muito de 2023 para 2025 (números na seção "Calibração com 2023"). Uma
explicação possível é o **Pé-de-Meia**:

- **Verificado:** o programa foi instituído pela Lei nº 14.818/2024 (MEC, "Pé-de-Meia: pagamentos começam nesta
  terça-feira (25)", fev/2025), de 16/01/2024, regulamentada pelo Decreto nº 11.901, de 26/01/2024 (texto do
  decreto publicado pela Secretaria de Educação do Espírito Santo). Ou seja, **não existia no ENEM 2023**.
- **Verificado:** no ENEM 2025, estudantes do ensino médio público beneficiários do programa, concluintes em 2025,
  recebem um bônus de R$ 200 se fizerem **os dois dias de prova** (MEC, "Enem: estudantes da rede pública ganham
  R$ 200 do Pé-de-Meia", jun/2025, e "Participante do Pé-de-Meia pode ganhar R$ 200 extra se fizer Enem", nov/2025).
- **Indicado, não nomeado explicitamente:** a primeira edição com o bônus foi o ENEM 2024 (a notícia de fev/2025
  anuncia o depósito de R$ 200 "aos que participaram dos dois dias do Enem" junto com o pagamento a quem concluiu o
  ensino médio em 2024).
- **Hipótese não verificada:** que o programa explique o crescimento do universo. Não foi medido aqui.

Consequências para a validação: (1) o público de 2025 tem mais alunos da rede pública com o perfil do programa, o
que muda a composição (efeito que a previsão C captura); (2) como o bônus exige **presença nos dois dias**, a
presença desses alunos pode ser maior do que o modelo de presença de 2023 prevê, o que tenderia a deixar a previsão
por UF mais baixa que a realidade. Registrar como explicação possível do erro no notebook.

Fontes:
- https://www.gov.br/mec/pt-br/assuntos/noticias/2025/fevereiro/pe-de-meia-pagamentos-comecam-nesta-terca-feira-25
- https://www.gov.br/mec/pt-br/assuntos/noticias/2025/junho/enem-estudantes-da-rede-publica-ganham-r-200-do-pe-de-meia
- https://www.gov.br/mec/pt-br/assuntos/noticias/2025/novembro/participante-do-pe-de-meia-pode-ganhar-r-200-extra-se-fizer-enem
- Decreto nº 11.901/2024 (regulamenta a Lei nº 14.818/2024), cópia publicada pela SEDU-ES:
  https://sedu.es.gov.br/Media/pdf%20e%20Arquivos/Decreto%20n%C2%BA%2011.901,%20de%2026.01.2024,%20regulamenta%20a%20Lei%20n%C2%BA%2014.818,%20de%2016.01.2024,%20que%20institui%20e%20cria%20o%20Programa%20P%C3%A9-de-Meia.pdf



## Outros pontos para as próximas etapas

- **COP30:** parte das provas de 2025 em Belém, Ananindeua e Marituba (PA) foi aplicada em versão específica
  (códigos de prova "BAM2", nota 2 do dicionário de RESULTADOS). As notas estão na mesma escala, mas o PA merece
  uma observação na análise.
- **Tamanho:** os dois CSVs somam 2,6 GB descompactados. Ler em blocos, como o `baixar_dados.py`, e guardar só a
  amostra de PARTICIPANTES e os agregados de RESULTADOS.
- **Redação dentro da nota final:** o alvo do modelo (`NOTA_FINAL`) inclui a redação, que não está na TRI. A
  comparação principal continua sendo a nota final (como foi treinada), com as provas objetivas à parte.
