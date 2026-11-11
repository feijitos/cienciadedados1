# Plano de ação: expectativa × realidade (modelo do ENEM 2023 testado no ENEM 2025)

Documento de passagem de contexto. Quem continuar o trabalho (pessoa ou assistente) deve ler este arquivo inteiro antes de mexer em qualquer coisa.

Autores do projeto: Marcos Feijó e Pedro Klein. Repositório: https://github.com/feijitos/cienciadedados1. Site: https://feijitos.github.io/cienciadedados1/

Atualizado em 10/11/2026. Entrega final: **23/11/2026**.

## 1. A ideia, em uma frase

Usar o modelo treinado com o ENEM 2023 para prever as notas médias do ENEM 2025 a partir do perfil dos inscritos de 2025 (expectativa), e comparar com as notas reais de 2025 (realidade).

O nome técnico é **validação fora do tempo**. O modelo só viu um ano, então não aprende tendência. A pergunta é: as relações entre perfil socioeconômico e nota, medidas em 2023, continuam valendo dois anos depois?

### Por que 2025 e não 2026

- As notas do ENEM 2026 têm previsão (não oficial) para 27/01/2027, e os microdados só saem meses depois (os de 2025 já estavam públicos em julho de 2026). Nada de 2026 sai antes da entrega.
- Os microdados de 2025 já são públicos e trazem notas por tipo de escola e por UF.
- Os indicadores do IBGE/PNUD do projeto (Censo 2022, PNAD 2023, IDHM 2023) não mudam. Não há dado novo do IBGE a esperar.
- 2026 fica como continuação em 2027 (seção 9), usando o mesmo código.

## 2. Onde o projeto está hoje

- Dados: amostra de 56.048 concluintes do ENEM 2023 (4% de cada UF, SEED = 42); 42.032 com as cinco provas.
- Regressão (nota final): Regressão Linear, R² = 0,299, MAE = 62,7, RMSE = 79,6 no teste. 8 variáveis numéricas e 5 categóricas (ver `resultados/metricas_entrega2.json`).
- Classificação (nota > 700): Regressão Logística, F1 = 0,336, ROC-AUC = 0,872.
- Dashboard: `gerar_dashboard.py` gera `docs/index.html` (Plotly, estático, GitHub Pages). Fonte: Lato.
- Primeira tela só com a manchete: concluída e já na `main` (a branch `primeira-tela` foi juntada e apagada).
- **Etapas de 12–13/11 concluídas** (branch `validacao-2025`):
  - `CLAUDE.md` na raiz com as regras da seção 8.
  - Modelos congelados em `resultados/modelos/` por `congelar_modelo.py`, com `modelos.json` (data, versões, SEED,
    variáveis, métricas e SHA-256 dos arquivos). A regressão retreinada reproduziu exatamente
    `metricas_entrega2.json` (33 valores, 6 casas decimais). O script se recusa a sobrescrever os modelos.
  - Modelo de presença P(presente nas 5 provas | perfil): ROC-AUC = 0,71 no teste, taxa prevista 74,9% × observada
    75,0%. No teste, a correção pela chance de presença reduz o erro da média por UF de **7,9 para 1,8 pontos**.
  - Dashboard, seção "O que os modelos dizem": previsto × real por UF e mapa dos erros no teste de 2023. O erro
    médio por UF é de **9,3 pontos** (6,4 ponderado por alunos); correlação de posições = 0,85; maiores erros em
    TO (+26,9) e RN (−16,7). RR tem só 20 alunos no teste (média instável, avisado no site).
  - Para rodar, scikit-learn 1.9.1, imbalanced-learn e joblib foram instalados na área do usuário da `python3.11`.

## 3. Obstáculos que definem o desenho

1. **Sem ligação aluno a aluno.** Desde 2024 o INEP publica notas (RESULTADOS) e questionário (PARTICIPANTES) em arquivos separados, sem chave. A comparação é por **médias de grupo**: UF com certeza; UF × tipo de escola se a coluna existir nos dois arquivos.
2. **Os dados de 2025 já são públicos.** Não dá para provar que a previsão veio antes dos dados. A saída é um **teste cego por procedimento** (seção 4, passo 3): o modelo é congelado, a previsão é calculada e commitada usando só o arquivo de participantes, e só depois o arquivo de resultados é aberto. O histórico do Git registra a ordem.
3. **Presença.** O modelo foi treinado com quem fez as cinco provas. O arquivo de participantes inclui quem faltou, e quem falta tem renda mais baixa (29,6% × 9,9% em 2023). Sem correção, a previsão por UF sai mais baixa que a realidade.
4. **Mudanças no questionário e no público.** As perguntas, códigos e faixas de renda podem ter mudado entre 2023 e 2025. Tem que ser conferido no dicionário antes de qualquer código.

## 4. Como a previsão é feita

1. **Congelar o modelo de 2023:** salvar com `joblib` o Pipeline da regressão e um modelo de presença P(presente nas 5 provas | perfil), treinado em 2023, em `resultados/modelos/`. Ao lado, um JSON com data, versões das bibliotecas, SEED, variáveis e métricas. Depois disso, nada é reajustado.
2. **Preparar 2025:** amostra de 4% por UF (SEED = 42) do arquivo PARTICIPANTES, com o mesmo universo de 2023 (concluintes no ano, não treineiros, escola pública ou privada informada) e as mesmas variáveis derivadas (`src/features.py`).
3. **Prever (teste cego):** aplicar o modelo a cada inscrito, tirar a média prevista por grupo ponderada pela chance de presença (se o arquivo trouxer a presença, usar a coluna e dispensar o modelo de presença). Gravar em `resultados/previsao_2025.json`, fazer commit e push **antes** de abrir o arquivo RESULTADOS.
4. **Realidade:** só então ler RESULTADOS 2025, aplicar o mesmo filtro (concluintes, cinco provas) e calcular as médias reais por grupo.

### Três previsões, para separar as fontes de erro

| Previsão | Como é feita | O que mede |
|---|---|---|
| A. Repetição | Média de cada UF em 2025 = média real de 2023 | Régua mínima: o modelo precisa ser melhor que isso |
| B. Modelo + perfil de 2023 | Modelo aplicado ao perfil de 2023 | O que se espera se nada mudou |
| C. Modelo + perfil de 2025 | Modelo aplicado ao perfil real de 2025 | Se as relações de 2023 ainda valem |

Diferença entre B e C = efeito da mudança de perfil dos inscritos. O erro que sobra em C = mudança nas relações ou algo que o modelo não enxerga (regra da prova, política local, composição de quem faz a prova).

## 5. Métricas da comparação

Por UF (27 pontos) e, se possível, por UF × tipo de escola, para a nota final e para cada prova objetiva:

- erro médio absoluto (MAE) e RMSE, simples e ponderados pelo número de alunos;
- viés (erro médio com sinal): o modelo erra para cima ou para baixo?
- correlação previsto × real (Pearson) e de posições (Spearman): acerta a ordem dos estados?
- tabela com A, B e C lado a lado.

A redação fica separada: não usa a TRI, então não é comparável entre anos como as provas objetivas.

## 6. Cronograma até 23/11

| Datas | Etapa | Entregável |
|---|---|---|
| 10–11/11 | Primeira tela só com a manchete | Merge da branch `primeira-tela` (**concluído**) |
| 12–13/11 | `CLAUDE.md` + branch `validacao-2025` + congelar o modelo | `resultados/modelos/` com JSON de metadados (**concluído**) |
| 12–13/11 | Gráfico previsto × real por UF no teste de 2023 e mapa dos erros | Seção nova em "O que os modelos dizem" (**concluído**) |
| 14–15/11 | Ler os dicionários de 2025, montar a tabela de equivalência de colunas e de códigos | `docs/equivalencia_2023_2025.md` |
| 16–17/11 | `baixar_ano.py --ano 2025`: download e amostra dos dois arquivos | `dados/processados/enem2025_participantes.parquet` e `enem2025_resultados_uf.csv` (já agregado) |
| 18/11 | Previsões A, B e C (teste cego) | `resultados/previsao_2025.json`, commitado antes da realidade |
| 19/11 | Realidade e métricas | Notebook `Validacao_2023_2025.ipynb` e `resultados/validacao_2025.json` |
| 20–21/11 | Seção no site "Expectativa × realidade: 2025" | Previsto × real por UF, mapa do erro, tabela A/B/C, frase-síntese gerada dos dados |
| 22/11 | README, verificação, merge na `main` | Site publicado |
| 23/11 | Entrega | — |

Se o prazo apertar, cortar nesta ordem: UF × tipo de escola (fica só UF), depois as provas individuais (fica só nota final). A previsão C por UF e a comparação com A não podem ser cortadas.

## 7. Riscos e como tratar

| Risco | O que fazer |
|---|---|
| Colunas, códigos ou faixas de renda diferentes entre 2023 e 2025 | Tabela de equivalência; sem equivalência, tirar a variável, reajustar nada e registrar o efeito |
| Filtro de "concluintes com escola informada" não reproduzível | Usar o mais próximo e aplicar o mesmo filtro em previsto e real |
| Arquivo de 2025 grande demais para a memória | Ler em blocos (como o `baixar_dados.py`) e guardar só a amostra e os agregados |
| Mudanças de regra ou de público do ENEM entre 2023 e 2025 | Pesquisar e registrar no notebook como explicação possível do erro |
| Só 27 pontos por comparação | Reportar com cautela; não tirar conclusão forte de diferenças pequenas |
| Modelo explica 30% da variação individual | Deixar claro que a previsão é de médias por grupo, não de alunos |
| Publicar dado individual | Só agregados; nenhum grupo com menos de 5 alunos no HTML |

## 8. Regras fixas do projeto

- Python nesta máquina: `python3.11` (o executável fica em `%LOCALAPPDATA%\Microsoft\WindowsApps\python3.11.exe`; os atalhos `python` e `py` não funcionam). O caminho completo, com o nome do usuário, não vai para o Git: o `verificar_entrega.py` reprova caminhos absolutos da máquina.
- Não alterar os notebooks das entregas, `src/`, `baixar_dados.py` nem `ferramentas/` sem pedido explícito. Código novo vai em arquivos novos.
- Arquivos brutos de 2025 vão em `dados/brutos/` (fora do Git).
- Nenhum número digitado à mão em página ou relatório: tudo sai dos dados.
- Rodar `ferramentas/verificar_entrega.py` antes de cada commit.
- Testar o site em 375 px e em tela grande, nos temas claro e escuro.
- Mudanças grandes em branch; sem push na `main` sem pedido.
- O Marcos é iniciante: explicar em linguagem simples e pedir confirmação antes de ações difíceis de desfazer.

## 9. Continuação em 2027 (fora da entrega)

- Antes de sair qualquer dado de 2026: calcular as previsões A e B para 2026 com o mesmo modelo congelado e commitar `resultados/previsao_2026.json`. Essa sim é uma previsão registrada antes dos dados.
- Quando os microdados de 2026 saírem (provavelmente no meio de 2027), rodar `baixar_ano.py --ano 2026` e o mesmo notebook com o ano trocado.
- Página de microdados do INEP: https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem

## 10. Pendências antigas

Nenhuma pendência aberta.

- Fonte: o site passou da Schibsted Grotesk para a Lato (já na `main`), com a escala tipográfica revista.
- Vírgula decimal espaçada e último item do menu cortado em ~800 px: corrigidos na reestilização da primeira tela.
- Conhecido, fora do escopo: se a janela é aberta larga e depois encolhida até a largura de celular, o mapa do
  Plotly não encolhe junto (quem abre direto no celular não é afetado).

## 11. Prompt para começar a próxima sessão

```text
Leia PLANO_PREVISAO_2026.md na raiz do repositório. Execute as etapas de 14–15/11 do cronograma (seção 6) na branch validacao-2025. Antes de editar, me mostre um plano curto e espere meu ok. Não toque na main.
```
