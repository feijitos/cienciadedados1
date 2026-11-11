# CLAUDE.md

Projeto de Ciência de Dados: socioeconomia × desempenho no ENEM 2023 (INEP + IBGE), de Marcos Feijó e Pedro Klein.
Trabalho em andamento: validação fora do tempo do modelo de 2023 com o ENEM 2025. O plano completo está em
`PLANO_PREVISAO_2026.md`, na raiz; leia-o inteiro antes de mexer em qualquer coisa.

## Regras fixas

- **Python nesta máquina:** use `python3.11` (o executável fica em
  `%LOCALAPPDATA%\Microsoft\WindowsApps\python3.11.exe`). Os atalhos `python` e `py` não funcionam.
  scikit-learn 1.9.1, imbalanced-learn e joblib estão instalados na área do usuário dessa Python.
- **Não alterar** os notebooks das entregas (`Entrega1_ENEM_IBGE.ipynb`, `Entrega2_ENEM_IBGE.ipynb`), `src/`,
  `baixar_dados.py` nem `ferramentas/` sem pedido explícito. Código novo vai em arquivos novos.
- **Dados brutos** (inclusive os de 2025) vão em `dados/brutos/`, que fica fora do Git.
- **Nenhum número digitado à mão** em página ou relatório: tudo sai dos dados.
- **Rodar `python3.11 ferramentas/verificar_entrega.py` antes de cada commit.**
- **Testar o site** (`docs/index.html`, gerado por `python3.11 gerar_dashboard.py`) em 375 px e em tela grande,
  nos temas claro e escuro.
- **Mudanças grandes em branch;** sem push na `main` sem pedido.
- **Modelos congelados** em `resultados/modelos/` (criados por `congelar_modelo.py`): não reajustar nem
  sobrescrever. Toda previsão usa esses arquivos; `carregar_congelados()` confere o SHA-256.
- O Marcos é iniciante: explicar em linguagem simples e pedir confirmação antes de ações difíceis de desfazer.
