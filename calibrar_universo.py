"""
Calibração, só com dados de 2023, do universo aproximado usado no lado da realidade de 2025.

Em 2025 o arquivo RESULTADOS não tem situação de conclusão nem treineiro; o universo da realidade é aproximado por
"escola de conclusão preenchida" (TP_DEPENDENCIA_ADM_ESC). O arquivo único de 2023 tem as duas coisas, então dá
para medir quanto a nota final média por UF muda ao trocar o universo verdadeiro pelo aproximado:

    verdadeiro: concluintes em 2023, não treineiros, escola pública ou privada informada, cinco provas
    aproximado: escola de conclusão preenchida, cinco provas

Critério aprovado: MAE das diferenças por UF abaixo de ~3 pontos = aproximação justificada (o erro do modelo por
UF no teste é lido de resultados/modelos/modelos.json). Nenhum dado de 2025 com nota é lido aqui.

Saídas: resultados/calibracao_universo_2023.json e a seção "Calibração com 2023" de docs/equivalencia_2023_2025.md.

Uso (na raiz do repositório, com dados/brutos/microdados_enem_2023.zip baixado):
    python3.11 calibrar_universo.py
"""

import json
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from src.dados import COLS_NOTAS, unificar_presenca  # noqa: E402

ZIP_2023 = RAIZ / "dados" / "brutos" / "microdados_enem_2023.zip"
CSV_2023 = "microdados_enem_2023/DADOS/MICRODADOS_ENEM_2023.csv"
META_2023 = RAIZ / "dados" / "processados" / "enem_amostra_meta.json"
META_2025 = RAIZ / "dados" / "processados" / "enem2025_participantes_meta.json"
MODELOS = RAIZ / "resultados" / "modelos" / "modelos.json"
SAIDA = RAIZ / "resultados" / "calibracao_universo_2023.json"
DOC = RAIZ / "docs" / "equivalencia_2023_2025.md"
LIMITE_MAE = 3.0  # pontos: abaixo disso a aproximação fica justificada
COLS = {"SG_UF_PROVA": "string", "TP_ST_CONCLUSAO": "Int8", "IN_TREINEIRO": "Int8", "TP_ESCOLA": "Int8",
        "TP_DEPENDENCIA_ADM_ESC": "Int8", "TP_PRESENCA_CN": "Int8", "TP_PRESENCA_CH": "Int8",
        "TP_PRESENCA_LC": "Int8", "TP_PRESENCA_MT": "Int8", **{c: "float64" for c in COLS_NOTAS}}


def acumular(chunksize: int = 500_000) -> pd.DataFrame:
    """Por UF: inscritos e (soma, n) da nota final nos dois universos, e a sobreposição entre eles."""
    partes = []
    with zipfile.ZipFile(ZIP_2023) as z, z.open(CSV_2023) as f:
        leitor = pd.read_csv(f, sep=";", encoding="latin-1", usecols=list(COLS), dtype=COLS, chunksize=chunksize)
        for i, b in enumerate(leitor, start=1):
            verdadeiro = ((b["TP_ST_CONCLUSAO"] == 2) & (b["IN_TREINEIRO"] == 0) & b["TP_ESCOLA"].isin([2, 3])).fillna(False)
            aproximado = b["TP_DEPENDENCIA_ADM_ESC"].notna()
            nota = b[COLS_NOTAS].mean(axis=1, skipna=False)  # NOTA_FINAL, como em src.dados.etl
            cinco = pd.Series(unificar_presenca(b) == 1, index=b.index) & nota.notna()
            d = pd.DataFrame({"UF": b["SG_UF_PROVA"],
                              "insc_verdadeiro": verdadeiro.astype(int), "insc_aproximado": aproximado.astype(int),
                              "insc_ambos": (verdadeiro & aproximado).astype(int),
                              "n_verdadeiro": (verdadeiro & cinco).astype(int), "n_aproximado": (aproximado & cinco).astype(int),
                              "s_verdadeiro": nota.where(verdadeiro & cinco, 0.0),
                              "s_aproximado": nota.where(aproximado & cinco, 0.0)})
            partes.append(d.groupby("UF").sum())
            print(f"\r[2023] bloco {i:>2}", end="")
    print()
    return pd.concat(partes).groupby(level=0).sum()


def _br(v, casas=1):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sinal(v, casas=1):
    return ("+" if v > 0 else "−" if v < 0 else "") + _br(abs(v), casas)


def main():
    t = acumular()
    meta23 = json.loads(META_2023.read_text(encoding="utf-8"))
    # a leitura tem que reproduzir o universo de 2023 do projeto, UF por UF
    assert t["insc_verdadeiro"].astype(int).to_dict() == meta23["universo_por_uf"], "universo de 2023 não confere"

    t["media_verdadeiro"] = t["s_verdadeiro"] / t["n_verdadeiro"]
    t["media_aproximado"] = t["s_aproximado"] / t["n_aproximado"]
    t["diferenca"] = t["media_aproximado"] - t["media_verdadeiro"]  # positivo = aproximado acima do verdadeiro
    t["dif_inscritos"] = t["insc_aproximado"] / t["insc_verdadeiro"] - 1
    mae, maior = float(t["diferenca"].abs().mean()), t["diferenca"].abs().idxmax()
    erro_modelo = json.loads(MODELOS.read_text(encoding="utf-8"))["regressao"]["teste_por_uf"]["MAE"]
    tot_v, tot_a = t[["s_verdadeiro", "n_verdadeiro"]].sum(), t[["s_aproximado", "n_aproximado"]].sum()
    dif_nacional = tot_a["s_aproximado"] / tot_a["n_aproximado"] - tot_v["s_verdadeiro"] / tot_v["n_verdadeiro"]

    meta25 = json.loads(META_2025.read_text(encoding="utf-8"))
    conf25 = pd.DataFrame(meta25["conferencia_universo"]["por_uf"]).T
    corr_lacunas = float(t["dif_inscritos"].corr(conf25["diferenca"].astype(float)))
    # Estimativa (hipótese, não medida): viés = parcela que falta × lacuna de nota entre quem tem e quem não tem escola
    # preenchida. A lacuna vem de 2023; a parcela que falta, da conferência de 2025 (diferença líquida de inscritos).
    t["falta_2023"] = 1 - t["insc_ambos"] / t["insc_verdadeiro"]
    t["lacuna"] = t["diferenca"] / t["falta_2023"]
    t["falta_2025"] = (-conf25["diferenca"].astype(float)).clip(lower=0).reindex(t.index)
    t["vies_2025_est"] = t["falta_2025"] * t["lacuna"]
    mae_est, maior_est = float(t["vies_2025_est"].abs().mean()), t["vies_2025_est"].abs().idxmax()
    u23 = int(t["insc_verdadeiro"].sum())
    u25 = int(sum(meta25["universo_por_uf"].values()))

    res = {
        "criterio": f"MAE das diferenças por UF < {LIMITE_MAE} pontos = aproximação justificada",
        "MAE": round(mae, 6), "vies_medio": round(float(t["diferenca"].mean()), 6),
        "maior_diferenca": {"UF": maior, "pontos": round(float(t.loc[maior, "diferenca"]), 6)},
        "diferenca_nacional": round(float(dif_nacional), 6),
        "erro_modelo_por_uf_MAE": erro_modelo, "justificada": mae < LIMITE_MAE,
        "dif_inscritos_total": round(float(t["insc_aproximado"].sum() / u23 - 1), 6),
        "corr_lacuna_inscritos_2023_x_2025": round(corr_lacunas, 6),
        "universo_2023": u23, "universo_2025": u25, "crescimento_universo": round(u25 / u23 - 1, 6),
        "cobertura_2023": round(float(t["insc_ambos"].sum() / u23), 6),
        "estimativa_2025": {"hipotese": "a lacuna de nota de 2023 entre quem tem e quem não tem escola preenchida se "
                                        "mantém em 2025; a parcela que falta é a diferença líquida de inscritos",
                            "MAE": round(mae_est, 6), "maior": {"UF": maior_est,
                                                                "pontos": round(float(t.loc[maior_est, "vies_2025_est"]), 6)}},
        "por_uf": {u: {"media_verdadeiro": round(float(r["media_verdadeiro"]), 6),
                       "media_aproximado": round(float(r["media_aproximado"]), 6),
                       "diferenca": round(float(r["diferenca"]), 6),
                       "n_verdadeiro": int(r["n_verdadeiro"]), "n_aproximado": int(r["n_aproximado"]),
                       "inscritos_verdadeiro": int(r["insc_verdadeiro"]), "inscritos_aproximado": int(r["insc_aproximado"]),
                       "inscritos_ambos": int(r["insc_ambos"]), "dif_inscritos": round(float(r["dif_inscritos"]), 6),
                       "falta_2023": round(float(r["falta_2023"]), 6), "lacuna": round(float(r["lacuna"]), 6),
                       "falta_2025": round(float(r["falta_2025"]), 6), "vies_2025_estimado": round(float(r["vies_2025_est"]), 6)}
                   for u, r in t.iterrows()},
    }
    SAIDA.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")

    linhas = [
        "Gerado por `calibrar_universo.py` (só dados de 2023). Nota final média por UF no universo verdadeiro "
        "(concluintes, não treineiros, escola informada, cinco provas) × no universo aproximado (escola de conclusão "
        "preenchida, cinco provas).", "",
        f"**MAE das diferenças por UF: {_br(mae, 2)} pontos** (critério: abaixo de {_br(LIMITE_MAE, 0)}), contra "
        f"{_br(erro_modelo, 1)} pontos de erro do modelo por UF. "
        + ("**Aproximação justificada.**" if mae < LIMITE_MAE else "**Acima do critério: ver o viés por UF abaixo.**"),
        f"Viés médio: {_sinal(res['vies_medio'], 2)} pontos; maior diferença: {maior} ({_sinal(t.loc[maior, 'diferenca'], 2)}); "
        f"diferença nacional: {_sinal(dif_nacional, 2)} pontos.",
        f"Inscritos: em 2023 a escola de conclusão estava preenchida para só {_br(res['cobertura_2023'] * 100, 1)}% do "
        f"universo verdadeiro (o aproximado tem {_sinal(res['dif_inscritos_total'] * 100, 1)}%); em 2025 a diferença "
        "líquida é bem menor (seção anterior). A correlação entre a lacuna de inscritos por UF de 2023 e a de 2025 é "
        f"{_br(corr_lacunas, 2)}: o mecanismo da falta mudou, e o viés de 2023 não serve como correção direta para 2025.",
        f"**Estimativa para 2025 (hipótese, não medida):** supondo que a lacuna de nota entre quem tem e quem não tem "
        f"escola preenchida seja a de 2023, o viés por UF em 2025 seria a parcela que falta × essa lacuna: MAE de "
        f"{_br(mae_est, 2)} pontos, maior em {maior_est} ({_sinal(t.loc[maior_est, 'vies_2025_est'], 2)}).",
        f"Universo de PARTICIPANTES: {_br(u23, 0)} em 2023 e {_br(u25, 0)} em 2025 "
        f"({_sinal(res['crescimento_universo'] * 100, 1)}%).", "",
        "| UF | Média verdadeiro 2023 | Média aproximado 2023 | Viés 2023 (pts) | Falta 2023 | Lacuna (pts) | "
        "Falta 2025 | Viés 2025 estimado (pts) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for u, r in t.iterrows():
        linhas.append(f"| {u} | {_br(r['media_verdadeiro'])} | {_br(r['media_aproximado'])} | {_sinal(r['diferenca'], 2)} | "
                      f"{_br(r['falta_2023'] * 100, 1)}% | {_sinal(r['lacuna'], 1)} | {_br(r['falta_2025'] * 100, 1)}% | "
                      f"{_sinal(r['vies_2025_est'], 2)} |")
    ini, fim = "<!-- início: gerado por calibrar_universo.py (não editar à mão) -->", "<!-- fim: gerado por calibrar_universo.py -->"
    doc = DOC.read_text(encoding="utf-8")
    assert ini in doc and fim in doc, "marcadores da calibração não encontrados no documento"
    DOC.write_text(re.sub(re.escape(ini) + ".*?" + re.escape(fim), lambda _: f"{ini}\n" + "\n".join(linhas) + f"\n{fim}",
                          doc, flags=re.S), encoding="utf-8")
    print(f"MAE = {mae:.2f} pts (erro do modelo por UF = {erro_modelo:.1f}); maior: {maior} {t.loc[maior, 'diferenca']:+.2f}; "
          f"{'JUSTIFICADA' if mae < LIMITE_MAE else 'ACIMA DO CRITÉRIO'}")
    print(f"-> {SAIDA.relative_to(RAIZ)} e seção atualizada em {DOC.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
