"""
Previsões A, B e C para o ENEM 2025 (teste cego da validação fora do tempo; seção 4 do PLANO_PREVISAO_2026.md).

    A. Repetição: média real de 2023 por UF (arquivo completo de 2023, universo verdadeiro).
    B. Modelo congelado + perfil de 2023: média prevista por UF, ponderada pela chance de presença (amostra de 2023).
    C. Modelo congelado + perfil de 2025: idem, com a amostra de PARTICIPANTES 2025 e as equivalências de
       docs/equivalencia_2023_2025.md (renda = Q007; computadores = Q021; internet = Q020; escola = Q023).

Sensibilidades de C: trajetória mista (Q023 B/C) como "Privada"; internet em branco (imputada pelo Pipeline);
"presença calibrada" (o logit do modelo de presença congelado é deslocado por UF para bater a taxa real de presença
de 2025, lida no RESULTADOS só pelas colunas TP_PRESENCA_*; o arquivo do modelo não muda).
Sensibilidades da comparação, fixadas aqui antes da realidade: sem as UFs acima de 5% na conferência do universo, e
realidade descontada do viés de universo estimado (calibrar_universo.py).

Teste cego: nenhuma nota de 2025 é lida aqui. resultados/previsao_2025.json tem de ser commitado e enviado antes de
qualquer leitura das notas do RESULTADOS.

Uso (na raiz do repositório):
    python3.11 prever_2025.py
"""

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.special import expit

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from baixar_ano import ANOS, UFS, _executavel_7z, conferir_codigos  # noqa: E402
from congelar_modelo import CAT, NUM, carregar_congelados, dados_2023  # noqa: E402
from src.dados import COLS_NOTAS, COLS_PRESENCA, carregar_ibge_real, mapear_faixa_renda, unificar_presenca  # noqa: E402
from src.features import criar_features  # noqa: E402

AMOSTRA_2025 = RAIZ / "dados" / "processados" / "enem2025_participantes.parquet"
META_2025 = RAIZ / "dados" / "processados" / "enem2025_participantes_meta.json"
CALIBRACAO = RAIZ / "resultados" / "calibracao_universo_2023.json"
ZIP_2023 = RAIZ / "dados" / "brutos" / "microdados_enem_2023.zip"
CSV_2023 = "microdados_enem_2023/DADOS/MICRODADOS_ENEM_2023.csv"
ZIP_2025 = RAIZ / "dados" / "brutos" / "microdados_enem_2025.zip"
SAIDA = RAIZ / "resultados" / "previsao_2025.json"
ESCOLAS = ["Pública", "Privada"]
MIN_N = 5  # nenhum grupo com menos de 5 alunos no resultado


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Perfil de 2025 nas variáveis do modelo
# --------------------------------------------------------------------------
def perfil_2025(a: pd.DataFrame, mista: str = "Pública", internet: str = "Q020") -> pd.DataFrame:
    """Traduz a amostra de PARTICIPANTES 2025 para as variáveis de 2023 (docs/equivalencia_2023_2025.md)."""
    conferir_codigos(a, "amostra 2025")  # Q006 só A/B, Q007 só A-Q, demais dentro do dicionário
    assert a["Q007"].nunique() > 2, "Q007 parece a pergunta sim/não, não a renda"
    assert mista in ESCOLAS and internet in ("Q020", "em branco")
    escola = a["Q023"].map({"A": "Pública", "B": mista, "C": mista, "D": "Privada", "E": "Privada"})
    assert escola.notna().all(), "Q023 fora de A-E na amostra"
    d = pd.DataFrame({
        "UF": a["SG_UF_PROVA"].astype(str),
        "Q006": a["Q007"].astype(str),   # renda familiar: Q007 de 2025 = Q006 de 2023 (mesmas faixas em SM)
        "Q005": a["Q005"], "Q001": a["Q001"].astype(str), "Q002": a["Q002"].astype(str),
        "Q024": a["Q021"].astype(str),   # computadores: Q021 de 2025 = Q024 de 2023
        "Q025": a["Q020"].astype(str),   # internet: Q020 (wi-fi) de 2025 ~ Q025 de 2023
        "TP_FAIXA_ETARIA": a["TP_FAIXA_ETARIA"], "TP_COR_RACA": a["TP_COR_RACA"], "TP_SEXO": a["TP_SEXO"].astype(str),
        "TP_ESCOLA": escola})
    d = d.merge(carregar_ibge_real(), on="UF", how="left", validate="m:1")
    assert d["IDH_ESTADUAL"].notna().all(), "UF sem correspondência no IBGE"
    d["NOTA_FINAL"] = np.nan
    d["FAIXA_RENDA"] = d["Q006"].map(mapear_faixa_renda)
    f = criar_features(d)
    if internet == "em branco":
        f["TEM_INTERNET"] = np.nan  # o Pipeline imputa a mediana do treino
    assert f[NUM + CAT].drop(columns=["ESC_MAE", "ESC_PAI", "TEM_INTERNET"]).notna().all().all()
    return f


# --------------------------------------------------------------------------
# Médias previstas, ponderadas pela chance de presença
# --------------------------------------------------------------------------
def prever(f, reg, pres, delta=None, grupos=("UF",)):
    X = f[NUM + CAT]
    z = pres.decision_function(X)  # logit da chance de estar presente nas 5 provas
    if delta is not None:
        z = z + f["UF"].map(delta).to_numpy()
    t = pd.DataFrame({**{g: f[g].to_numpy() for g in grupos}, "y": reg.predict(X), "p": expit(z)})
    t["py"] = t["p"] * t["y"]
    g = t.groupby(list(grupos)).agg(n=("y", "size"), soma_p=("p", "sum"), soma_py=("py", "sum"), presenca=("p", "mean"))
    g["prevista"] = g["soma_py"] / g["soma_p"]
    return g[["n", "prevista", "presenca"]], float(t["py"].sum() / t["p"].sum())


def deltas_presenca(f, pres, taxa_real):
    """Deslocamento no logit, por UF, para que a presença prevista média bata a taxa real de 2025."""
    z = pd.Series(pres.decision_function(f[NUM + CAT]), index=f.index)
    return {u: brentq(lambda dl: float(expit(z[f["UF"] == u] + dl).mean()) - taxa_real[u], -10, 10) for u in UFS}


# --------------------------------------------------------------------------
# Dados reais permitidos: 2023 completo e presença de 2025 (sem notas de 2025)
# --------------------------------------------------------------------------
def real_2023(chunksize=500_000):
    """Médias reais de 2023 no universo verdadeiro (cinco provas): por UF, por UF × escola e por prova."""
    cols = {"SG_UF_PROVA": "string", "TP_ST_CONCLUSAO": "Int8", "IN_TREINEIRO": "Int8", "TP_ESCOLA": "Int8",
            **{c: "Int8" for c in COLS_PRESENCA}, **{c: "float64" for c in COLS_NOTAS}}
    partes = []
    with zipfile.ZipFile(ZIP_2023) as z, z.open(CSV_2023) as fh:
        for b in pd.read_csv(fh, sep=";", encoding="latin-1", usecols=list(cols), dtype=cols, chunksize=chunksize):
            u = ((b["TP_ST_CONCLUSAO"] == 2) & (b["IN_TREINEIRO"] == 0) & b["TP_ESCOLA"].isin([2, 3])).fillna(False)
            b = b[u & (unificar_presenca(b) == 1)].copy()
            b["NOTA_FINAL"] = b[COLS_NOTAS].mean(axis=1, skipna=False)
            b = b[b["NOTA_FINAL"].notna()]
            b["ESCOLA"] = b["TP_ESCOLA"].map({2: "Pública", 3: "Privada"}).astype(str)
            partes.append(b[["SG_UF_PROVA", "ESCOLA", "NOTA_FINAL", *COLS_NOTAS]])
    return pd.concat(partes, ignore_index=True).rename(columns={"SG_UF_PROVA": "UF"})


def presenca_real_2025(chunksize=1_000_000):
    """Taxa de presença nos dois dias (= cinco provas; em 2023 os dois grupos coincidem) por UF, no universo
    aproximado de RESULTADOS. Lê SÓ UF, rede da escola e TP_PRESENCA_*: nenhuma nota."""
    cols = {"SG_UF_PROVA": "string", "TP_DEPENDENCIA_ADM_ESC": "Int8", **{c: "Int8" for c in COLS_PRESENCA}}
    assert not any(c.startswith(("NU_NOTA", "TX_", "TP_STATUS")) for c in cols), "coluna de nota na leitura"
    proc = subprocess.Popen([_executavel_7z(), "x", "-so", str(ZIP_2025), ANOS[2025]["resultados"]],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    partes = []
    for b in pd.read_csv(proc.stdout, sep=";", encoding="latin-1", usecols=list(cols), dtype=cols, chunksize=chunksize):
        b = b[b["TP_DEPENDENCIA_ADM_ESC"].notna()]
        assert b[COLS_PRESENCA].notna().all().all(), "presença em branco no universo aproximado"
        assert set(np.unique(b[COLS_PRESENCA].to_numpy(dtype=int))) <= {0, 1, 2}, "presença fora do dicionário"
        partes.append(pd.DataFrame({"UF": b["SG_UF_PROVA"], "n": 1, "presentes": (unificar_presenca(b) == 1).astype(int)})
                      .groupby("UF").sum())
    if proc.wait() != 0:
        sys.exit("O 7-Zip terminou com erro ao ler o RESULTADOS.")
    g = pd.concat(partes).groupby(level=0).sum().reindex(UFS)
    return g["presentes"] / g["n"], g


def main():
    if SAIDA.exists():
        sys.exit(f"{SAIDA.relative_to(RAIZ)} já existe: a previsão registrada não é refeita.")
    reg, pres, meta_mod = carregar_congelados()  # confere o SHA-256 dos modelos congelados
    meta25 = json.loads(META_2025.read_text(encoding="utf-8"))
    calib = json.loads(CALIBRACAO.read_text(encoding="utf-8"))

    # A: repetição (2023 real, universo verdadeiro)
    r23 = real_2023()
    a_uf = r23.groupby("UF")["NOTA_FINAL"].agg(["mean", "size"])
    for u in UFS:  # mesma média da calibração (mesma fonte, mesma regra)
        assert abs(a_uf.loc[u, "mean"] - calib["por_uf"][u]["media_verdadeiro"]) < 1e-4, u
    a_esc = r23.groupby(["UF", "ESCOLA"])["NOTA_FINAL"].agg(["mean", "size"])
    a_prova = r23.groupby("UF")[COLS_NOTAS].mean()

    # B: modelo + perfil de 2023 (todos os inscritos da amostra de 2023)
    todos23, _ = dados_2023()
    b_uf, b_nac = prever(todos23, reg, pres)
    b_esc, _ = prever(todos23, reg, pres, grupos=("UF", "TP_ESCOLA"))

    # C: modelo + perfil de 2025, cenário principal e sensibilidades
    amostra = pd.read_parquet(AMOSTRA_2025)
    f = perfil_2025(amostra)
    c_uf, c_nac = prever(f, reg, pres)
    c_esc, _ = prever(f, reg, pres, grupos=("UF", "TP_ESCOLA"))
    c_priv, c_priv_nac = prever(perfil_2025(amostra, mista="Privada"), reg, pres)
    c_net, c_net_nac = prever(perfil_2025(amostra, internet="em branco"), reg, pres)
    taxa, contagem = presenca_real_2025()
    delta = deltas_presenca(f, pres, taxa)
    c_cal, c_cal_nac = prever(f, reg, pres, delta=delta)
    assert all(abs(c_cal.loc[u, "presenca"] - taxa[u]) < 1e-6 for u in UFS), "calibração da presença não bateu"
    for tab in (b_esc, c_esc):
        assert (tab["n"] >= MIN_N).all(), "grupo UF × escola com menos de 5 alunos"

    ufs_sens = meta25["conferencia_universo"]["ufs_acima_do_limite"]
    r6 = lambda v: round(float(v), 6)  # noqa: E731
    saida = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "teste_cego": "Gravado e commitado antes de qualquer leitura das notas do RESULTADOS 2025. Do RESULTADOS foram "
                      "lidas só SG_UF_PROVA, TP_DEPENDENCIA_ADM_ESC e TP_PRESENCA_*.",
        "modelos": {k: meta_mod[k]["sha256"] for k in ("regressao", "presenca")},
        "amostra_2025": {"arquivo": AMOSTRA_2025.name, "sha256": _sha256(AMOSTRA_2025), "linhas": int(len(amostra))},
        "alvo": "NOTA_FINAL (média das 5 provas) dos presentes nas 5 provas, por UF",
        "definicoes": {
            "A": "repetição: média real de 2023 por UF (arquivo completo, universo verdadeiro)",
            "B": "modelo congelado + perfil de 2023 (amostra de 2023, todos os inscritos), ponderado pela presença prevista",
            "C": "modelo congelado + perfil de 2025 (amostra de 2025), ponderado pela presença prevista",
            "C_mista_privada": "C com Q023 B/C como Privada (principal: Pública)",
            "C_internet_em_branco": "C com TEM_INTERNET em branco, imputado pela mediana do treino (principal: Q020)",
            "C_presenca_calibrada": "C com o logit da presença deslocado por UF (delta_logit) para bater a taxa real "
                                    "de presença de 2025 no universo aproximado; modelo congelado inalterado",
        },
        "sensibilidades_da_comparacao": {
            "sem_ufs_acima_de_5pct": ufs_sens,
            "realidade_menos_vies_universo_estimado": "subtrair por UF vies_universo_estimado da média real de 2025",
        },
        "nacional": {"A": r6(r23["NOTA_FINAL"].mean()), "B": r6(b_nac), "C": r6(c_nac),
                     "C_mista_privada": r6(c_priv_nac), "C_internet_em_branco": r6(c_net_nac),
                     "C_presenca_calibrada": r6(c_cal_nac),
                     "presenca_prevista_modelo": r6(c_uf["presenca"].mul(c_uf["n"]).sum() / c_uf["n"].sum()),
                     "presenca_real_2025": r6(contagem["presentes"].sum() / contagem["n"].sum())},
        "por_uf": {u: {
            "n_amostra_2025": int(c_uf.loc[u, "n"]), "n_amostra_2023": int(b_uf.loc[u, "n"]),
            "A": r6(a_uf.loc[u, "mean"]), "B": r6(b_uf.loc[u, "prevista"]), "C": r6(c_uf.loc[u, "prevista"]),
            "C_mista_privada": r6(c_priv.loc[u, "prevista"]), "C_internet_em_branco": r6(c_net.loc[u, "prevista"]),
            "C_presenca_calibrada": r6(c_cal.loc[u, "prevista"]),
            "presenca_prevista_modelo": r6(c_uf.loc[u, "presenca"]), "presenca_real_2025": r6(taxa[u]),
            "delta_logit": r6(delta[u]), "inscritos_universo_aproximado_2025": int(contagem.loc[u, "n"]),
            "vies_universo_estimado": calib["por_uf"][u]["vies_2025_estimado"],
            "A_por_prova": {c: r6(a_prova.loc[u, c]) for c in COLS_NOTAS},
            "sensibilidade_sem_esta_uf": u in ufs_sens} for u in UFS},
        "por_uf_escola": {f"{u}|{e}": {"A": r6(a_esc.loc[(u, e), "mean"]), "B": r6(b_esc.loc[(u, e), "prevista"]),
                                       "C": r6(c_esc.loc[(u, e), "prevista"]), "n_amostra_2025": int(c_esc.loc[(u, e), "n"])}
                          for u in UFS for e in ESCOLAS},
    }
    SAIDA.write_text(json.dumps(saida, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Previsão gravada em {SAIDA.relative_to(RAIZ)}. Nacional: A {saida['nacional']['A']:.1f} | "
          f"B {b_nac:.1f} | C {c_nac:.1f} | C presença calibrada {c_cal_nac:.1f}")


if __name__ == "__main__":
    main()
