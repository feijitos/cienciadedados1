"""
Realidade do ENEM 2025 e comparação com a previsão cega (etapa de 19/11 do PLANO_PREVISAO_2026.md).

1. Lê as notas do RESULTADOS 2025 (só depois do commit e do push de resultados/previsao_2025.json, conferidos aqui)
   e calcula as médias reais no universo aproximado (escola de conclusão preenchida, presentes nas cinco provas):
   por UF, por UF × tipo de escola e por prova. Grava os agregados em dados/processados/.
2. Compara as previsões A, B e C com a realidade (métricas da seção 5 do plano) e roda as sensibilidades fixadas
   na previsão. Grava resultados/validacao_2025.json.

A parte 2 (comparar) usa só arquivos versionados; o notebook Validacao_2023_2025.ipynb a chama sem os dados brutos.
Nada aqui altera a previsão nem os modelos congelados.

Uso (na raiz do repositório):
    python3.11 realidade_2025.py
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from src.dados import COLS_NOTAS, COLS_PRESENCA, SEED, unificar_presenca  # noqa: E402

PREVISAO = RAIZ / "resultados" / "previsao_2025.json"
REAL_UF = RAIZ / "dados" / "processados" / "enem2025_resultados_uf.csv"
REAL_ESC = RAIZ / "dados" / "processados" / "enem2025_resultados_uf_escola.csv"
IBGE = RAIZ / "dados" / "ibge_uf.csv"
SAIDA = RAIZ / "resultados" / "validacao_2025.json"
PROVAS = {"NU_NOTA_CN": "Ciências da Natureza", "NU_NOTA_CH": "Ciências Humanas", "NU_NOTA_LC": "Linguagens",
          "NU_NOTA_MT": "Matemática"}
CENARIOS = ["A", "B", "C", "C_mista_privada", "C_internet_em_branco", "C_presenca_calibrada"]
MIN_N = 5
N_BOOT = 5000


# --------------------------------------------------------------------------
# 1) Leitura das notas (exige o zip bruto e a previsão já enviada ao GitHub)
# --------------------------------------------------------------------------
def _git(*args) -> str:
    return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.strip()


def conferir_teste_cego():
    """A previsão tem de estar commitada, sem mudanças locais, e o commit tem de estar no GitHub."""
    rel = PREVISAO.relative_to(RAIZ).as_posix()
    assert _git("ls-files", rel) == rel, "previsao_2025.json não está no Git"
    assert subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel], cwd=RAIZ).returncode == 0, \
        "previsao_2025.json mudou depois do commit"
    commit = _git("log", "-n", "1", "--format=%H", "--", rel)
    remoto = _git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    assert subprocess.run(["git", "merge-base", "--is-ancestor", commit, remoto], cwd=RAIZ).returncode == 0, \
        f"o commit da previsão ({commit[:7]}) ainda não está em {remoto}"
    return commit


def ler_realidade(chunksize: int = 1_000_000):
    from baixar_ano import ANOS, UFS, _executavel_7z
    cols = {"SG_UF_PROVA": "string", "TP_DEPENDENCIA_ADM_ESC": "Int8",
            **{c: "Int8" for c in COLS_PRESENCA}, **{c: "float64" for c in COLS_NOTAS}}
    zip_ = RAIZ / "dados" / "brutos" / "microdados_enem_2025.zip"
    proc = subprocess.Popen([_executavel_7z(), "x", "-so", str(zip_), ANOS[2025]["resultados"]],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    partes, sem_nota = [], 0
    for b in pd.read_csv(proc.stdout, sep=";", encoding="latin-1", usecols=list(cols), dtype=cols, chunksize=chunksize):
        b = b[b["TP_DEPENDENCIA_ADM_ESC"].notna() & (unificar_presenca(b) == 1)].copy()
        b["NOTA_FINAL"] = b[COLS_NOTAS].mean(axis=1, skipna=False)
        sem_nota += int(b["NOTA_FINAL"].isna().sum())  # presentes sem alguma nota (em 2023: zero)
        b = b[b["NOTA_FINAL"].notna()]
        assert ((b[COLS_NOTAS] >= 0) & (b[COLS_NOTAS] <= 1000)).all().all(), "nota fora de [0, 1000]"
        b["ESCOLA"] = np.where(b["TP_DEPENDENCIA_ADM_ESC"] == 4, "Privada", "Pública")
        b["UF"] = b["SG_UF_PROVA"].astype(str)
        partes.append(b.groupby(["UF", "ESCOLA"]).agg(n=("NOTA_FINAL", "size"),
                                                      **{f"s_{c}": (c, "sum") for c in ["NOTA_FINAL", *COLS_NOTAS]}))
    if proc.wait() != 0:
        sys.exit("O 7-Zip terminou com erro ao ler o RESULTADOS.")
    s = pd.concat(partes).groupby(level=[0, 1]).sum()

    def medias(g):
        out = pd.DataFrame({"n": g["n"].astype(int)})
        for c in ["NOTA_FINAL", *COLS_NOTAS]:
            out[c] = g[f"s_{c}"] / g["n"]
        return out

    uf, esc = medias(s.groupby(level=0).sum()).reindex(UFS), medias(s)
    assert uf["n"].notna().all() and (esc["n"] >= MIN_N).all(), "UF sem alunos ou célula com menos de 5"
    return uf, esc, sem_nota


# --------------------------------------------------------------------------
# 2) Comparação (só arquivos versionados)
# --------------------------------------------------------------------------
def metricas(prev: pd.Series, real: pd.Series, n: pd.Series) -> dict:
    """Seção 5 do plano: MAE e RMSE (simples e ponderados por alunos), viés com sinal, Pearson e Spearman."""
    e, w = prev - real, n / n.sum()
    return {"UFs": int(len(e)), "MAE": float(e.abs().mean()), "MAE_ponderado": float((e.abs() * w).sum()),
            "RMSE": float(np.sqrt((e ** 2).mean())), "RMSE_ponderado": float(np.sqrt((e ** 2 * w).sum())),
            "vies": float(e.mean()), "vies_ponderado": float((e * w).sum()),
            "pearson": float(prev.corr(real)), "spearman": float(prev.rank().corr(real.rank()))}


def _r(d):
    return {k: (round(v, 6) if isinstance(v, float) else v) for k, v in d.items()}


def comparar(prev: dict, real_uf: pd.DataFrame, real_esc: pd.DataFrame) -> dict:
    p = pd.DataFrame(prev["por_uf"]).T
    ufs = list(p.index)
    real, n = real_uf.loc[ufs, "NOTA_FINAL"], real_uf.loc[ufs, "n"].astype(float)
    regiao = pd.read_csv(IBGE).set_index("UF")["REGIAO"]
    sem = prev["sensibilidades_da_comparacao"]["sem_ufs_acima_de_5pct"]
    vies_univ = p["vies_universo_estimado"].astype(float)
    variantes = {"principal": (ufs, real),
                 "sem_ufs_acima_de_5pct": ([u for u in ufs if u not in sem], real),
                 "realidade_menos_vies_universo": (ufs, real - vies_univ)}
    tabela = {v: {c: _r(metricas(p.loc[us, c].astype(float), r.loc[us], n.loc[us])) for c in CENARIOS}
              for v, (us, r) in variantes.items()}

    # incerteza com só 27 pontos: bootstrap das UFs para MAE(A) − MAE(C) no cenário principal
    eA, eC = (p["A"].astype(float) - real).abs().to_numpy(), (p["C"].astype(float) - real).abs().to_numpy()
    rng = np.random.default_rng(SEED)
    idx = rng.integers(0, len(ufs), size=(N_BOOT, len(ufs)))
    difs = eA[idx].mean(axis=1) - eC[idx].mean(axis=1)
    boot = {"MAE_A_menos_MAE_C": float(eA.mean() - eC.mean()), "IC95": [float(np.percentile(difs, 2.5)),
            float(np.percentile(difs, 97.5))], "prop_C_melhor": float((difs > 0).mean()), "reamostragens": N_BOOT}

    # quanto a mudança de perfil (B -> C) explica
    B, C = p["B"].astype(float), p["C"].astype(float)
    eB, eC_ = B - real, C - real
    nac_real = float((real * n).sum() / n.sum())
    nac = prev["nacional"]
    perfil = {"MAE_B": float(eB.abs().mean()), "MAE_C": float(eC_.abs().mean()),
              "reducao_MAE": float(1 - eC_.abs().mean() / eB.abs().mean()),
              "reducao_SSE": float(1 - (eC_ ** 2).sum() / (eB ** 2).sum()),
              "corr_mudanca_perfil_x_desvio_de_B": float((C - B).corr(real - B)),
              "nacional": {"real": nac_real, "B": nac["B"], "C": nac["C"], "real_menos_B": nac_real - nac["B"],
                           "C_menos_B": nac["C"] - nac["B"]}}

    # erros por UF e por região (cenário principal)
    erros = pd.DataFrame({"real": real, "n": n.astype(int), **{c: p[c].astype(float) - real for c in CENARIOS},
                          "REGIAO": regiao.reindex(ufs)})
    por_regiao = {r: {c: float(g[c].mean()) for c in ["A", "B", "C"]} | {"UFs": int(len(g))}
                  for r, g in erros.groupby("REGIAO")}

    # UF × tipo de escola (secundária: escola definida de forma diferente nos dois lados)
    e = pd.DataFrame(prev["por_uf_escola"]).T
    e.index = pd.MultiIndex.from_tuples([tuple(k.split("|")) for k in e.index])
    re_ = real_esc.reindex(e.index)
    esc = {c: _r(metricas(e[c].astype(float), re_["NOTA_FINAL"], re_["n"].astype(float))) for c in ["A", "B", "C"]}

    # provas: só a régua A; redação à parte
    ap = pd.DataFrame({u: v["A_por_prova"] for u, v in prev["por_uf"].items()}).T
    provas = {nome: _r(metricas(ap.loc[ufs, c].astype(float), real_uf.loc[ufs, c], n)) for c, nome in PROVAS.items()}
    redacao = _r(metricas(ap.loc[ufs, "NU_NOTA_REDACAO"].astype(float), real_uf.loc[ufs, "NU_NOTA_REDACAO"], n))

    # de onde vem a diferença nacional 2023 -> 2025: cada prova pesa 1/5 na nota final
    nac_prova = {c: float((real_uf.loc[ufs, c] * n).sum() / n.sum()) for c in COLS_NOTAS}
    nac_a = {c: float((ap.loc[ufs, c].astype(float) * n).sum() / n.sum()) for c in COLS_NOTAS}
    decomp = {c: {"real_2025": nac_prova[c], "A_2023": nac_a[c], "diferenca": nac_prova[c] - nac_a[c],
                  "contribuicao_nota_final": (nac_prova[c] - nac_a[c]) / len(COLS_NOTAS)} for c in COLS_NOTAS}
    padrao = {"corr_erro_C_x_media_real": float(erros["C"].corr(erros["real"])),
              "corr_erro_A_x_media_real": float(erros["A"].corr(erros["real"]))}

    conclusao_mantida = {v: {c: tabela[v][c]["MAE"] < tabela[v]["A"]["MAE"] for c in CENARIOS if c != "A"}
                         for v in tabela}
    return {
        "nota_final_por_uf": tabela, "bootstrap_A_vs_C": _r(boot) | {"IC95": [round(x, 6) for x in boot["IC95"]]},
        "mudanca_de_perfil": _r(perfil) | {"nacional": _r(perfil["nacional"])},
        "erros_por_uf": {u: _r(r.drop("REGIAO").to_dict()) | {"REGIAO": r["REGIAO"]} for u, r in erros.iterrows()},
        "erro_medio_por_regiao": {r: _r(v) for r, v in por_regiao.items()},
        "uf_x_escola": esc, "provas_regua_A": provas, "redacao_regua_A": redacao,
        "diferenca_nacional_por_prova": {c: _r(d) for c, d in decomp.items()}, "padrao_dos_erros": _r(padrao),
        "C_erra_menos_que_A": conclusao_mantida,
        "nacional": {"real": round(nac_real, 6), **{c: round(nac[c], 6) for c in CENARIOS}},
    }


def main():
    from congelar_modelo import carregar_congelados
    carregar_congelados()  # confere o SHA-256 dos modelos congelados (não são usados para prever aqui)
    commit = conferir_teste_cego()
    print(f"Teste cego conferido: previsão no commit {commit[:7]}, já no GitHub e sem mudanças locais.")
    uf, esc, sem_nota = ler_realidade()
    uf.rename_axis("UF").to_csv(REAL_UF, float_format="%.6f")
    esc.rename_axis(["UF", "ESCOLA"]).to_csv(REAL_ESC, float_format="%.6f")
    prev = json.loads(PREVISAO.read_text(encoding="utf-8"))
    res = comparar(prev, pd.read_csv(REAL_UF, index_col="UF"), pd.read_csv(REAL_ESC, index_col=["UF", "ESCOLA"]))
    res = {"previsao_commit": commit, "universo_real": "RESULTADOS 2025, escola de conclusão preenchida, presentes "
           "nas quatro provas objetivas e com as cinco notas", "alunos_real": int(uf["n"].sum()),
           "presentes_sem_alguma_nota": sem_nota, **res}
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    t = res["nota_final_por_uf"]["principal"]
    print(f"Real nacional {res['nacional']['real']:.1f} | MAE por UF: A {t['A']['MAE']:.2f}, B {t['B']['MAE']:.2f}, "
          f"C {t['C']['MAE']:.2f} | -> {SAIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
