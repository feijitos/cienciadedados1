"""
Congela os modelos de 2023 usados na validação fora do tempo (ENEM 2023 -> ENEM 2025).

Salva em resultados/modelos/:
    regressao_nota_final.joblib  Pipeline da Regressão Linear da Entrega 2 (mesma divisão, mesmas variáveis)
    presenca.joblib              Regressão Logística para P(presente nas 5 provas | perfil), treinada em 2023
    modelos.json                 data, versões das bibliotecas, SEED, variáveis, métricas e SHA-256 dos arquivos

Antes de salvar, confere que a regressão retreinada reproduz exatamente (6 casas decimais) as métricas e os
coeficientes de resultados/metricas_entrega2.json; se não reproduzir, para sem salvar nada.
Depois de congelados, os modelos não são reajustados: o script se recusa a sobrescrevê-los.

Uso (na raiz do repositório):
    python3.11 congelar_modelo.py

O dashboard (gerar_dashboard.py) importa daqui a divisão treino/teste e o cálculo de previsto x real por UF.
"""

import hashlib
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import KFold, cross_validate, train_test_split
from sklearn.pipeline import Pipeline

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from src.dados import SEED, carregar_dados, etl, recorte_presentes  # noqa: E402
from src.features import criar_features  # noqa: E402
from src.modelagem import metricas_regressao, montar_preprocessador  # noqa: E402

ARQ_METRICAS = RAIZ / "resultados" / "metricas_entrega2.json"
DIR_MODELOS = RAIZ / "resultados" / "modelos"
ARQ_REGRESSAO = DIR_MODELOS / "regressao_nota_final.joblib"
ARQ_PRESENCA = DIR_MODELOS / "presenca.joblib"
ARQ_META = DIR_MODELOS / "modelos.json"

# Variáveis e categorias de referência: as mesmas da célula 18 do notebook da Entrega 2
_BASE = json.loads(ARQ_METRICAS.read_text(encoding="utf-8"))["base"]
NUM, CAT = _BASE["features_num"], _BASE["features_cat"]
REFERENCIAS = {"TP_ESCOLA": "Pública", "REGIAO": "Nordeste", "FAIXA_RENDA": "Baixa Renda",
               "SEXO": "Feminino", "COR_RACA": "Branca"}


# --------------------------------------------------------------------------
# Dados e divisões (reutilizados pelo dashboard)
# --------------------------------------------------------------------------
def dados_2023():
    """(todos os inscritos da amostra com as variáveis derivadas, só os presentes com as 5 notas)."""
    df_ibge, df_enem = carregar_dados(True)
    df = etl(df_enem, df_ibge, verbose=False)
    todos = criar_features(df)
    todos["PRESENTE_5"] = (df["PRESENTE"] & df["NOTA_FINAL"].notna()).astype(int)
    return todos, criar_features(recorte_presentes(df))


def divisao_regressao(dm):
    """Mesma divisão do notebook: 80/20, estratificada pelo alvo da classificação (nota > 700), SEED = 42."""
    return train_test_split(dm[NUM + CAT], dm["NOTA_FINAL"], dm["ALTO_DESEMPENHO"],
                            test_size=0.20, stratify=dm["ALTO_DESEMPENHO"], random_state=SEED)


def divisao_presenca(todos):
    """Divisão 80/20 de todos os inscritos, estratificada pela presença nas 5 provas, SEED = 42."""
    return train_test_split(todos[NUM + CAT], todos["PRESENTE_5"], test_size=0.20,
                            stratify=todos["PRESENTE_5"], random_state=SEED)


def previsto_real_por_uf(modelo, dm):
    """Conjunto de teste de 2023: média prevista e média real da nota final em cada UF."""
    _, X_test, _, y_test, _, _ = divisao_regressao(dm)
    t = pd.DataFrame({"UF": dm.loc[X_test.index, "UF"], "previsto": modelo.predict(X_test), "real": y_test})
    g = t.groupby("UF").agg(n=("real", "size"), previsto=("previsto", "mean"), real=("real", "mean"))
    g["erro"] = g["previsto"] - g["real"]  # positivo = o modelo prevê acima do real
    return g


def metricas_por_uf(g):
    """Métricas da seção 5 do plano: MAE, RMSE (simples e ponderados por alunos), viés, Pearson e Spearman."""
    e, w = g["erro"], g["n"] / g["n"].sum()
    return {"UFs": int(len(g)), "alunos": int(g["n"].sum()), "menor_n": int(g["n"].min()),
            "MAE": float(e.abs().mean()), "MAE_ponderado": float((e.abs() * w).sum()),
            "RMSE": float(np.sqrt((e ** 2).mean())), "RMSE_ponderado": float(np.sqrt((e ** 2 * w).sum())),
            "vies": float(e.mean()), "pearson": float(g["previsto"].corr(g["real"])),
            "spearman": float(g["previsto"].rank().corr(g["real"].rank()))}


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def carregar_congelados():
    """Carrega os modelos congelados e confere o SHA-256 de cada arquivo com o registrado em modelos.json."""
    meta = json.loads(ARQ_META.read_text(encoding="utf-8"))
    for chave, arq in (("regressao", ARQ_REGRESSAO), ("presenca", ARQ_PRESENCA)):
        assert _sha256(arq) == meta[chave]["sha256"], f"{arq.name} mudou depois de congelado"
    return joblib.load(ARQ_REGRESSAO), joblib.load(ARQ_PRESENCA), meta


# --------------------------------------------------------------------------
# Treino
# --------------------------------------------------------------------------
def treinar_regressao(dm):
    """Retreina a regressão como no notebook e confere com metricas_entrega2.json. Devolve (modelo, métricas)."""
    X_train, X_test, y_train, y_test, _, _ = divisao_regressao(dm)
    reg = Pipeline([("prep", montar_preprocessador(NUM, CAT, REFERENCIAS)), ("modelo", LinearRegression())])
    reg.fit(X_train, y_train)
    cv = cross_validate(reg, X_train, y_train, cv=KFold(5, shuffle=True, random_state=SEED),
                        scoring={"r2": "r2", "mae": "neg_mean_absolute_error", "rmse": "neg_root_mean_squared_error"})
    novo = {
        "teste": metricas_regressao(y_test, reg.predict(X_test)),
        "treino": metricas_regressao(y_train, reg.predict(X_train)),
        "cv_media": {"R²": cv["test_r2"].mean(), "MAE": -cv["test_mae"].mean(), "RMSE": -cv["test_rmse"].mean()},
        "cv_dp": {"R²": cv["test_r2"].std(), "MAE": cv["test_mae"].std(), "RMSE": cv["test_rmse"].std()},
        "coeficientes": dict(zip(reg.named_steps["prep"].get_feature_names_out(), reg.named_steps["modelo"].coef_)),
    }
    ref = json.loads(ARQ_METRICAS.read_text(encoding="utf-8"))["regressao_linear"]
    difs = [f"{b}.{k}: JSON {v} x agora {round(float(novo[b][k]), 6)}"
            for b in ref for k, v in ref[b].items() if round(float(novo[b][k]), 6) != v]
    if difs or (len(X_train), len(X_test)) != (_BASE["treino"], _BASE["teste"]):
        sys.exit("A regressão retreinada NÃO reproduz metricas_entrega2.json. Nada foi salvo.\n" + "\n".join(difs))
    metr = {b: {k: round(float(v), 6) for k, v in novo[b].items()} for b in ("teste", "treino", "cv_media", "cv_dp")}
    return reg, metr, (len(X_train), len(X_test))


def treinar_presenca(todos, reg):
    """P(presente nas 5 provas | perfil) com Regressão Logística (mesmas variáveis e pré-processamento da regressão).
    Além das métricas usuais, testa a correção que será usada em 2025: no teste, a média por UF da nota prevista
    ponderada pela chance de presença (todos os inscritos) deve ficar perto da média prevista só entre os presentes."""
    X_train, X_test, y_train, y_test = divisao_presenca(todos)
    pres = Pipeline([("prep", montar_preprocessador(NUM, CAT, REFERENCIAS)),
                     ("modelo", LogisticRegression(max_iter=2000, random_state=SEED))])
    pres.fit(X_train, y_train)
    p = pres.predict_proba(X_test)[:, 1]
    decis = pd.qcut(p, 10, labels=False, duplicates="drop")
    calib = pd.DataFrame({"d": decis, "p": p, "y": y_test.to_numpy()}).groupby("d").agg(previsto=("p", "mean"),
                                                                                          observado=("y", "mean"))

    t = pd.DataFrame({"UF": todos.loc[X_test.index, "UF"], "nota": reg.predict(X_test), "p": p, "y": y_test})
    por_uf = t.groupby("UF").apply(lambda g: pd.Series({
        "presentes": g.loc[g["y"] == 1, "nota"].mean(),            # o que se quer estimar
        "ponderada": np.average(g["nota"], weights=g["p"]),         # correção pela chance de presença
        "sem_correcao": g["nota"].mean()}), include_groups=False)    # todos os inscritos, sem peso
    metr = {
        "teste": {"ROC-AUC": round(float(roc_auc_score(y_test, p)), 6),
                  "Brier": round(float(brier_score_loss(y_test, p)), 6),
                  "log_loss": round(float(log_loss(y_test, p)), 6),
                  "taxa_observada": round(float(y_test.mean()), 6), "media_prevista": round(float(p.mean()), 6),
                  "maior_desvio_calibracao_decis": round(float((calib["previsto"] - calib["observado"]).abs().max()), 6)},
        "teste_correcao_por_uf": {
            "descricao": "MAE entre UFs da média prevista da nota em relação à média prevista só entre os presentes",
            "MAE_ponderada_pela_presenca": round(float((por_uf["ponderada"] - por_uf["presentes"]).abs().mean()), 6),
            "MAE_sem_correcao": round(float((por_uf["sem_correcao"] - por_uf["presentes"]).abs().mean()), 6)},
    }
    return pres, metr, (len(X_train), len(X_test))


def main():
    if ARQ_REGRESSAO.exists() or ARQ_PRESENCA.exists() or ARQ_META.exists():
        sys.exit(f"Os modelos já estão congelados em {DIR_MODELOS.relative_to(RAIZ)}; nada foi alterado. "
                 "Congelado quer dizer que não se reajusta: apague a pasta à mão só se tiver certeza.")
    todos, dm = dados_2023()
    reg, metr_reg, (n_tr, n_te) = treinar_regressao(dm)
    print(f"Regressão: reproduz metricas_entrega2.json (R² teste = {metr_reg['teste']['R²']:.3f})")
    pres, metr_pres, (p_tr, p_te) = treinar_presenca(todos, reg)
    print(f"Presença: ROC-AUC teste = {metr_pres['teste']['ROC-AUC']:.3f}")
    uf = metricas_por_uf(previsto_real_por_uf(reg, dm))

    DIR_MODELOS.mkdir(parents=True, exist_ok=True)
    joblib.dump(reg, ARQ_REGRESSAO)
    joblib.dump(pres, ARQ_PRESENCA)
    meta = {
        "congelado_em": datetime.now().isoformat(timespec="seconds"),
        "regra": "Modelos congelados: não reajustar. Toda previsão de 2025 usa estes arquivos (conferir o SHA-256).",
        "versoes": {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__,
                    "pandas": pd.__version__, "joblib": joblib.__version__},
        "SEED": SEED, "dados": "Amostra ENEM 2023 (4% de cada UF), dados/processados/",
        "variaveis": {"numericas": NUM, "categoricas": CAT, "referencias": REFERENCIAS},
        "regressao": {"arquivo": ARQ_REGRESSAO.name, "sha256": _sha256(ARQ_REGRESSAO),
                      "modelo": "Pipeline(preprocessador, LinearRegression())", "alvo": "NOTA_FINAL (média das 5 provas)",
                      "universo": "presentes com as 5 notas", "divisao": "80/20 estratificada por ALTO_DESEMPENHO",
                      "treino": n_tr, "teste": n_te, "metricas": metr_reg,
                      "teste_por_uf": {k: round(v, 6) if isinstance(v, float) else v for k, v in uf.items()}},
        "presenca": {"arquivo": ARQ_PRESENCA.name, "sha256": _sha256(ARQ_PRESENCA),
                     "modelo": "Pipeline(preprocessador, LogisticRegression(max_iter=2000))",
                     "alvo": "PRESENTE_5 (presente nos dois dias e com as 5 notas)", "universo": "todos os inscritos da amostra",
                     "divisao": "80/20 estratificada por PRESENTE_5", "treino": p_tr, "teste": p_te, **metr_pres},
    }
    ARQ_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Congelados em {DIR_MODELOS.relative_to(RAIZ)}: {ARQ_REGRESSAO.name}, {ARQ_PRESENCA.name}, {ARQ_META.name}")


if __name__ == "__main__":
    main()
