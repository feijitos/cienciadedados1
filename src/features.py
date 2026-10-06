"""
Feature engineering para a modelagem da Entrega 2.

Todas as transformações aqui são **determinísticas e linha a linha**: não usam estatísticas
da base (médias, desvios, frequências). Por isso podem ser aplicadas antes da divisão
treino/teste sem vazamento de dados. Imputação, padronização e One-Hot, que aprendem com os
dados, ficam dentro do Pipeline (ver notebook da Entrega 2).
"""

import numpy as np
import pandas as pd

SALARIO_MINIMO_2023 = 1320.0
LIMIAR_ALTO_DESEMPENHO = 700

# Ponto médio (R$) de cada faixa de renda familiar do Q006 (ENEM 2023).
# Faixa Q é aberta ("acima de R$ 26.400"): usamos 1,25 × limite inferior, convenção comum para classe aberta.
PONTO_MEDIO_Q006 = {
    "A": 0.0, "B": 660.0, "C": 1650.0, "D": 2310.0, "E": 2970.0, "F": 3630.0, "G": 4620.0,
    "H": 5940.0, "I": 7260.0, "J": 8580.0, "K": 9900.0, "L": 11220.0, "M": 12540.0,
    "N": 14520.0, "O": 17820.0, "P": 23100.0, "Q": 33000.0,
}

# Escolaridade do pai (Q001) / mãe (Q002): A (nunca estudou) ... G (pós-graduação); H = "Não sei" -> ausente
ESCOLARIDADE = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4, "F": 5, "G": 6}

# Q024 (computadores em casa): A = nenhum ... E = quatro ou mais
N_COMPUTADORES = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}

COR_RACA = {0: "Não declarada", 1: "Branca", 2: "Preta", 3: "Parda", 4: "Amarela", 5: "Indígena",
            6: "Não declarada"}


def criar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta as variáveis derivadas e o alvo da classificação. Devolve uma cópia."""
    out = df.copy()

    # Alvo da classificação: nota final acima de 700
    out["ALTO_DESEMPENHO"] = (out["NOTA_FINAL"] > LIMIAR_ALTO_DESEMPENHO).astype(int)

    # Colunas que só existem nos dados reais (a simulação não tem questionário completo)
    if "Q005" in out:
        moradores = out["Q005"].astype(float).clip(lower=1)
        renda_familiar = out["Q006"].map(PONTO_MEDIO_Q006)
        # Renda per capita familiar em salários mínimos (renda da faixa ÷ moradores)
        out["RENDA_PC_SM"] = renda_familiar / moradores / SALARIO_MINIMO_2023
        # Log suaviza a assimetria forte da renda (poucos valores muito altos)
        out["LOG_RENDA_PC"] = np.log1p(out["RENDA_PC_SM"])
        out["N_MORADORES"] = moradores
    if "Q002" in out:
        out["ESC_MAE"] = out["Q002"].astype(str).map(ESCOLARIDADE)  # "Não sei" vira NaN
        out["ESC_PAI"] = out["Q001"].astype(str).map(ESCOLARIDADE)
    if "Q024" in out:
        out["N_COMPUTADORES"] = out["Q024"].astype(str).map(N_COMPUTADORES)
        out["TEM_INTERNET"] = (out["Q025"].astype(str) == "B").astype(int)
    if "TP_FAIXA_ETARIA" in out:
        # Concluinte com 19 anos ou mais (faixa 4+) indica distorção idade-série
        out["ATRASO_ESCOLAR"] = (out["TP_FAIXA_ETARIA"].astype(int) >= 4).astype(int)
    if "TP_COR_RACA" in out:
        out["COR_RACA"] = out["TP_COR_RACA"].astype(int).map(COR_RACA)
    if "TP_SEXO" in out:
        out["SEXO"] = out["TP_SEXO"].astype(str).map({"F": "Feminino", "M": "Masculino"})

    # Rótulos categóricos como texto simples (o OneHotEncoder trabalha melhor assim)
    out["FAIXA_RENDA"] = out["FAIXA_RENDA"].astype(str)
    return out


def flag_outliers_iqr(serie: pd.Series, k: float = 1.5) -> tuple[pd.Series, float, float]:
    """Sinaliza valores fora de [Q1 − k·IQR, Q3 + k·IQR]. Devolve (máscara, limite_inf, limite_sup)."""
    q1, q3 = serie.quantile([0.25, 0.75])
    iqr = q3 - q1
    lim_inf, lim_sup = q1 - k * iqr, q3 + k * iqr
    return (serie < lim_inf) | (serie > lim_sup), lim_inf, lim_sup
