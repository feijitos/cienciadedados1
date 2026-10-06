"""
Funções auxiliares de pré-processamento e avaliação de modelos (Entrega 2).
"""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (accuracy_score, f1_score, mean_absolute_error, precision_score, r2_score,
                             recall_score, roc_auc_score, root_mean_squared_error)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def montar_preprocessador(num: list[str], cat: list[str], referencias: dict[str, str]) -> ColumnTransformer:
    """
    ColumnTransformer com dois ramos:
    - numéricas: imputação pela mediana + StandardScaler (média 0, desvio 1)
    - categóricas: imputação pela moda + One-Hot Encoding, removendo a categoria de referência
      (evita colinearidade perfeita na regressão e deixa os coeficientes interpretáveis)
    Como fica dentro do Pipeline, mediana, moda, média e desvio são aprendidos só no treino.
    """
    ramo_num = Pipeline([
        ("imputar", SimpleImputer(strategy="median")),
        ("padronizar", StandardScaler()),
    ])
    ramo_cat = Pipeline([
        ("imputar", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(drop=[referencias[c] for c in cat], sparse_output=False)),
    ])
    return ColumnTransformer([("num", ramo_num, num), ("cat", ramo_cat, cat)], verbose_feature_names_out=False)


def metricas_regressao(y_true, y_pred) -> dict:
    return {
        "R²": r2_score(y_true, y_pred),
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": root_mean_squared_error(y_true, y_pred),
    }


def metricas_classificacao(modelo, X, y) -> dict:
    """Acurácia, precisão, recall, F1 (classe positiva = alto desempenho) e ROC-AUC."""
    pred = modelo.predict(X)
    proba = modelo.predict_proba(X)[:, 1]
    return {
        "Acurácia": accuracy_score(y, pred),
        "Precisão": precision_score(y, pred, zero_division=0),
        "Recall": recall_score(y, pred),
        "F1": f1_score(y, pred),
        "ROC-AUC": roc_auc_score(y, proba),
    }


def resumo_cv(busca, metricas: dict[str, str]) -> dict:
    """Média e desvio padrão da validação cruzada para a melhor combinação do GridSearchCV."""
    i = busca.best_index_
    res = busca.cv_results_
    saida = {}
    for rotulo, chave in metricas.items():
        saida[f"CV {rotulo} (média)"] = res[f"mean_test_{chave}"][i]
        saida[f"CV {rotulo} (dp)"] = res[f"std_test_{chave}"][i]
    return saida


def formatar_parametros(params: dict) -> str:
    """Hiperparâmetros escolhidos em texto curto (sem o prefixo do passo do Pipeline)."""
    partes = []
    for chave, valor in params.items():
        nome = chave.split("__", 1)[-1]
        if isinstance(valor, dict):
            valor = f"{{0: {valor[0]}, 1: {valor[1]}}}"
        partes.append(f"{nome}={valor}")
    return ", ".join(partes)


def taxa_base(y) -> float:
    """Proporção da classe positiva: referência mínima para a precisão."""
    return float(np.mean(y))


def tabela_coeficientes(pipeline, nome_passo: str = "modelo") -> pd.Series:
    """Coeficientes do modelo linear com os nomes das colunas após o ColumnTransformer."""
    nomes = pipeline.named_steps["prep"].get_feature_names_out()
    coefs = np.ravel(pipeline.named_steps[nome_passo].coef_)
    return pd.Series(coefs, index=nomes)
