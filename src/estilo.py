"""
Paleta e estilo dos gráficos (Matplotlib/Seaborn), compartilhados pelos dois notebooks.

A paleta categórica (azul, laranja, verde-água) passou no validador de cores:
faixa de luminosidade, croma mínimo e separação para daltonismo (ΔE ≥ 8).
Como o verde-água tem contraste < 3:1 com o fundo, os gráficos que o usam levam rótulos de valor.
"""

import matplotlib.pyplot as plt
import seaborn as sns

# Categórica (identidade): ordem fixa, nunca reciclada
AZUL, LARANJA, VERDE_AGUA = "#2a78d6", "#eb6834", "#1baf7a"
CORES_ESCOLA = {"Privada": AZUL, "Pública": LARANJA}
CORES_MODELOS = {"Regressão Logística": AZUL, "Árvore de Decisão": LARANJA, "KNN": VERDE_AGUA}

# Sequencial (magnitude/ordem): um único matiz, do claro ao escuro
RAMPA_AZUL = ["#9ec5f4", "#3987e5", "#184f95"]  # Baixa, Média, Alta renda
CORES_RENDA = dict(zip(["Baixa Renda", "Média Renda", "Alta Renda"], RAMPA_AZUL))

# Divergente (correlação −1..+1): dois polos + meio neutro
CMAP_DIVERGENTE = sns.diverging_palette(30, 250, s=80, l=55, center="light", as_cmap=True)

# Tintas de texto e linhas de apoio
TINTA, TINTA_SECUNDARIA, CINZA_GRADE = "#0b0b0b", "#52514e", "#e1e0d9"
DESTAQUE = "#d03b3b"  # linhas de referência (média, mediana, limiar)


def aplicar_estilo() -> None:
    """Tema único: grade discreta, títulos em negrito, sem bordas superiores/direitas."""
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams.update({
        "figure.dpi": 110, "axes.titleweight": "bold", "axes.titlesize": 13,
        "axes.edgecolor": "#c3c2b7", "grid.color": CINZA_GRADE, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "text.color": TINTA, "axes.labelcolor": TINTA_SECUNDARIA,
        "xtick.color": TINTA_SECUNDARIA, "ytick.color": TINTA_SECUNDARIA,
    })
