"""
Microdados do ENEM de um ano posterior a 2023 (hoje: 2025) para a validação fora do tempo.

Etapas (ver PLANO_PREVISAO_2026.md e docs/equivalencia_2023_2025.md):
    1. download do zip do INEP para dados/brutos/ (fora do Git), conferindo o tamanho;
    2. PARTICIPANTES: leitura em blocos, asserts dos códigos (inclusive a armadilha da renda: em 2025 a renda
       familiar é a Q007, e a Q006 é "Você possui renda?"), universo e amostra de 4% por UF (SEED = 42);
    3. conferência do universo: inscritos por UF no universo de PARTICIPANTES x no universo aproximado de
       RESULTADOS (escola de conclusão preenchida). Aceito se a diferença for de até 5% em todas as UFs.

Teste cego: aqui o RESULTADOS é lido só nas colunas SG_UF_PROVA e TP_DEPENDENCIA_ADM_ESC. Nenhuma nota e nenhuma
presença são lidas antes do commit de resultados/previsao_<ano>.json.

O RESULTADOS de 2025 vem compactado em Deflate64, que o zipfile do Python não abre; o arquivo é lido pelo 7-Zip
(7z.exe) direto para o pandas, sem ser extraído no disco.

Uso (na raiz do repositório):
    python3.11 baixar_ano.py --ano 2025
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))
from src.dados import SEED  # noqa: E402

DIR_BRUTOS = RAIZ / "dados" / "brutos"
DIR_PROCESSADOS = RAIZ / "dados" / "processados"
DOC_EQUIVALENCIA = RAIZ / "docs" / "equivalencia_2023_2025.md"
FRACAO_AMOSTRA = 0.04  # a mesma de 2023
LIMITE_DIFERENCA_UF = 0.05  # conferência do universo: até 5% de diferença por UF
LIMITE_MISTA = 0.10  # trajetória mista acima de 10% no total enfraquece a comparação UF x tipo de escola
UFS = ["AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA", "PB", "PE", "PI",
       "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO"]

# Colunas de PARTICIPANTES usadas pelo modelo e pelo filtro (equivalências em docs/equivalencia_2023_2025.md)
COLS_PARTICIPANTES = {
    "NU_INSCRICAO": "int64", "TP_FAIXA_ETARIA": "Int8", "TP_SEXO": "string", "TP_COR_RACA": "Int8",
    "TP_ST_CONCLUSAO": "Int8", "IN_TREINEIRO": "Int8", "SG_UF_PROVA": "string",
    "Q001": "string", "Q002": "string", "Q005": "Int8",
    "Q006": "string",  # 2025: "Você possui renda?" (A/B); lida só para o assert da armadilha
    "Q007": "string",  # 2025: renda mensal da família (A a Q), equivalente à Q006 de 2023
    "Q020": "string", "Q021": "string", "Q023": "string",
}
CODIGOS = {  # códigos válidos de cada coluna (dicionário de 2025); valores em branco são permitidos
    "TP_ST_CONCLUSAO": {1, 2, 3, 4}, "IN_TREINEIRO": {0, 1}, "SG_UF_PROVA": set(UFS), "TP_SEXO": {"M", "F"},
    "TP_COR_RACA": {0, 1, 2, 3, 4, 5}, "TP_FAIXA_ETARIA": set(range(1, 21)), "Q005": set(range(1, 21)),
    "Q001": set("ABCDEFGH"), "Q002": set("ABCDEFGH"), "Q006": set("AB"), "Q007": set("ABCDEFGHIJKLMNOPQ"),
    "Q020": set("AB"), "Q021": set("ABCDE"), "Q023": set("ABCDEF"),
}
ESCOLA_INFORMADA, MISTA = set("ABCDE"), set("BC")  # Q023: F = não frequentou (fora do universo)

ANOS = {
    2025: {"url": "https://download.inep.gov.br/microdados/microdados_enem_2025.zip",
           "participantes": "microdados_enem_2025/DADOS/PARTICIPANTES_2025.csv",
           "resultados": "microdados_enem_2025/DADOS/RESULTADOS_2025.csv"},
}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 22), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(ano: int) -> Path:
    """Baixa o zip (retomando um .part interrompido) e confere o tamanho com o informado pelo servidor."""
    url = ANOS[ano]["url"]
    zip_ = DIR_BRUTOS / Path(url).name
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0 (compatible; baixar-ano)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        total = int(r.headers["Content-Length"])
    if zip_.exists() and zip_.stat().st_size == total:
        print(f"[{ano}] Zip já existe e tem o tamanho certo: {zip_.relative_to(RAIZ)} ({total / 1e6:,.0f} MB)")
        return zip_
    DIR_BRUTOS.mkdir(parents=True, exist_ok=True)
    parte = zip_.with_name(zip_.name + ".part")
    feito = parte.stat().st_size if parte.exists() else 0
    if feito < total:
        print(f"[{ano}] Baixando {url} a partir de {feito / 1e6:,.0f} MB de {total / 1e6:,.0f} MB")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; baixar-ano)",
                                                   "Range": f"bytes={feito}-"})
        with urllib.request.urlopen(req, timeout=120) as r, open(parte, "ab") as f:
            while bloco := r.read(1 << 20):
                f.write(bloco)
    if parte.stat().st_size != total:
        sys.exit(f"Download incompleto ({parte.stat().st_size:,} de {total:,} bytes); rode de novo para retomar.")
    parte.replace(zip_)
    return zip_


def conferir_codigos(bloco: pd.DataFrame, onde: str) -> None:
    """Para o programa se aparecer código fora do dicionário (inclusive a troca Q006/Q007 da renda)."""
    for col, validos in CODIGOS.items():
        if col not in bloco:
            continue
        achados = set(bloco[col].dropna().unique().tolist())
        fora = achados - validos
        assert not fora, f"{onde}: {col} tem códigos fora do dicionário: {sorted(map(str, fora))[:10]}"


def participantes(ano: int, zip_: Path, chunksize: int = 500_000):
    """Universo (concluintes no ano, não treineiros, Q023 de A a E) e amostra de 4% por UF."""
    funil = {"linhas_lidas": 0, f"concluintes_{ano}": 0, "nao_treineiros": 0, "q023_respondida": 0,
             "escola_informada_q023_A_a_E": 0}
    q023_concl, letras_q007, blocos = pd.Series(dtype="int64"), set(), []
    with zipfile.ZipFile(zip_) as z, z.open(ANOS[ano]["participantes"]) as f:
        leitor = pd.read_csv(f, sep=";", encoding="latin-1", usecols=list(COLS_PARTICIPANTES),
                             dtype=COLS_PARTICIPANTES, chunksize=chunksize)
        for i, b in enumerate(leitor, start=1):
            conferir_codigos(b, f"PARTICIPANTES bloco {i}")
            letras_q007 |= set(b["Q007"].dropna().unique())
            funil["linhas_lidas"] += len(b)
            b = b[b["TP_ST_CONCLUSAO"] == 2]
            funil[f"concluintes_{ano}"] += len(b)
            b = b[b["IN_TREINEIRO"] == 0]
            funil["nao_treineiros"] += len(b)
            q023_concl = q023_concl.add(b["Q023"].fillna("em branco").value_counts(), fill_value=0)
            funil["q023_respondida"] += int(b["Q023"].notna().sum())
            b = b[b["Q023"].isin(ESCOLA_INFORMADA)]
            funil["escola_informada_q023_A_a_E"] += len(b)
            blocos.append(b)
            print(f"\r[{ano}] PARTICIPANTES bloco {i:>2}: {funil['linhas_lidas']:,} linhas", end="")
    print()
    # armadilha da renda: a Q007 tem que ser a pergunta de faixas (muitas letras), não a de sim/não
    assert len(letras_q007) > 2, f"Q007 com só {sorted(letras_q007)}: parece a pergunta sim/não, não a renda"

    universo = pd.concat(blocos, ignore_index=True)
    amostra = (universo.groupby("SG_UF_PROVA", group_keys=False)
               .sample(frac=FRACAO_AMOSTRA, random_state=SEED).reset_index(drop=True))
    por_uf = universo.groupby("SG_UF_PROVA").agg(universo=("Q023", "size"),
                                                  mista=("Q023", lambda s: int(s.isin(MISTA).sum())))
    return universo, amostra, funil, q023_concl, por_uf


def _executavel_7z() -> str:
    for c in (shutil.which("7z"), r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if c and Path(c).exists():
            return c
    sys.exit("7-Zip não encontrado: ele é necessário para ler o RESULTADOS (Deflate64).")


def conferir_resultados(ano: int, zip_: Path, chunksize: int = 1_000_000) -> pd.DataFrame:
    """Inscritos por UF em RESULTADOS: total e com escola de conclusão preenchida (por rede).
    Lê SÓ SG_UF_PROVA e TP_DEPENDENCIA_ADM_ESC (teste cego: nenhuma nota, nenhuma presença)."""
    cols = {"SG_UF_PROVA": "string", "TP_DEPENDENCIA_ADM_ESC": "Int8"}
    proc = subprocess.Popen([_executavel_7z(), "x", "-so", str(zip_), ANOS[ano]["resultados"]],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    contagens, linhas = [], 0
    leitor = pd.read_csv(proc.stdout, sep=";", encoding="latin-1", usecols=list(cols), dtype=cols, chunksize=chunksize)
    for i, b in enumerate(leitor, start=1):
        assert set(b["SG_UF_PROVA"].dropna().unique()) <= set(UFS), "RESULTADOS: UF fora do dicionário"
        assert set(b["TP_DEPENDENCIA_ADM_ESC"].dropna().unique()) <= {1, 2, 3, 4}, "RESULTADOS: rede fora do dicionário"
        linhas += len(b)
        dep = b["TP_DEPENDENCIA_ADM_ESC"]
        contagens.append(pd.DataFrame({"UF": b["SG_UF_PROVA"], "total": 1, "escola": dep.notna().astype(int),
                                       "publica": dep.isin([1, 2, 3]).astype(int), "privada": dep.isin([4]).astype(int)})
                         .groupby("UF").sum())
        print(f"\r[{ano}] RESULTADOS bloco {i:>2}: {linhas:,} linhas (só UF e rede da escola)", end="")
    print()
    if proc.wait() != 0:
        sys.exit("O 7-Zip terminou com erro ao ler o RESULTADOS.")
    return pd.concat(contagens).groupby(level=0).sum().reindex(UFS, fill_value=0)


def _pct(v, casas=1):
    return f"{v * 100:.{casas}f}".replace(".", ",") + "%"


def _int(v):
    return f"{int(v):,}".replace(",", ".")


def secao_doc(ano, funil, q023, tab, total_mista, ok_uf, ruins):
    """Texto da seção "Conferência pós-download" (gerado; nenhum número digitado à mão)."""
    tot = tab[["participantes", "resultados"]].sum()
    dif_tot = tot["resultados"] / tot["participantes"] - 1
    linhas = [f"Gerado por `baixar_ano.py --ano {ano}`. Universo de PARTICIPANTES: concluintes em {ano}, não treineiros, "
              "Q023 de A a E. Universo aproximado de RESULTADOS: escola de conclusão preenchida. Os dois contam "
              "inscritos (presentes ou não).", "",
              "**Funil de PARTICIPANTES:** " + "; ".join(f"{k.replace('_', ' ')}: {_int(v)}" for k, v in funil.items()) + ".",
              "", "**Q023 entre concluintes não treineiros:** " +
              "; ".join(f"{k}: {_int(v)}" for k, v in q023.sort_index().items()) + ".", "",
              f"**Resultado:** diferença total de {_pct(dif_tot)}; " +
              ("**aproximação aceita** (todas as UFs com diferença de até 5%)." if ok_uf else
               f"**aproximação NÃO aceita**: {len(ruins)} UF(s) acima de 5% ({', '.join(ruins)}). Parar antes de prever."),
              f"Trajetória mista (Q023 B ou C): {_pct(total_mista)} do universo de PARTICIPANTES" +
              (" (**acima de 10%: a comparação UF × tipo de escola fica fraca**)." if total_mista > LIMITE_MISTA else
               " (abaixo do limite de 10%)."), "",
              "| UF | Universo PARTICIPANTES | Universo aproximado RESULTADOS | Diferença | Trajetória mista | Situação |",
              "|---|---:|---:|---:|---:|---|"]
    for uf, r in tab.iterrows():
        linhas.append(f"| {uf} | {_int(r['participantes'])} | {_int(r['resultados'])} | {_pct(r['diferenca'])} | "
                      f"{_pct(r['mista_pct'])} | {'ok' if abs(r['diferenca']) <= LIMITE_DIFERENCA_UF else '**acima de 5%**'} |")
    linhas.append(f"| **Total** | {_int(tot['participantes'])} | {_int(tot['resultados'])} | {_pct(dif_tot)} | "
                  f"{_pct(total_mista)} | |")
    return "\n".join(linhas)


def atualizar_doc(texto):
    doc = DOC_EQUIVALENCIA.read_text(encoding="utf-8")
    ini, fim = "<!-- início: gerado por baixar_ano.py (não editar à mão) -->", "<!-- fim: gerado por baixar_ano.py -->"
    assert ini in doc and fim in doc, "marcadores da seção gerada não encontrados no documento"
    novo = re.sub(re.escape(ini) + ".*?" + re.escape(fim), lambda _: f"{ini}\n{texto}\n{fim}", doc, flags=re.S)
    DOC_EQUIVALENCIA.write_text(novo, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ano", type=int, required=True, choices=sorted(ANOS))
    ano = ap.parse_args().ano

    zip_ = baixar(ano)
    universo, amostra, funil, q023, por_uf = participantes(ano, zip_)
    DIR_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    arq_amostra = DIR_PROCESSADOS / f"enem{ano}_participantes.parquet"
    amostra.to_parquet(arq_amostra, index=False)
    print(f"[{ano}] Amostra: {len(amostra):,} de {len(universo):,} -> {arq_amostra.relative_to(RAIZ)}")

    res = conferir_resultados(ano, zip_)
    tab = pd.DataFrame({"participantes": por_uf["universo"].reindex(UFS, fill_value=0),
                        "resultados": res["escola"], "mista": por_uf["mista"].reindex(UFS, fill_value=0)})
    tab["diferenca"] = tab["resultados"] / tab["participantes"] - 1
    tab["mista_pct"] = tab["mista"] / tab["participantes"]
    ruins = tab.index[tab["diferenca"].abs() > LIMITE_DIFERENCA_UF].tolist()
    ok_uf = not ruins
    total_mista = float(tab["mista"].sum() / tab["participantes"].sum())

    meta = {
        "fonte": f"INEP - Microdados do ENEM {ano}", "url": ANOS[ano]["url"], "zip_bytes": zip_.stat().st_size,
        "zip_sha256": _sha256(zip_), "seed": SEED, "fracao_por_uf": FRACAO_AMOSTRA, "funil": funil,
        "q023_concluintes_nao_treineiros": {k: int(v) for k, v in q023.sort_index().items()},
        "linhas_amostra": int(len(amostra)),
        "universo_por_uf": {u: int(v) for u, v in tab["participantes"].items()},
        "amostra_por_uf": {u: int(v) for u, v in amostra["SG_UF_PROVA"].value_counts().reindex(UFS, fill_value=0).items()},
        "asserts": "Q006 só A/B; Q007 só A-Q e com mais de 2 letras; demais colunas dentro do dicionário",
        "conferencia_universo": {
            "criterio": "diferença de até 5% por UF entre o universo de PARTICIPANTES e o de RESULTADOS",
            "aceita": ok_uf, "ufs_acima_do_limite": ruins,
            "resultados_total_linhas": int(res["total"].sum()),
            "por_uf": {u: {"participantes": int(r["participantes"]), "resultados": int(r["resultados"]),
                           "diferenca": round(float(r["diferenca"]), 6), "mista": int(r["mista"]),
                           "mista_pct": round(float(r["mista_pct"]), 6),
                           "resultados_publica": int(res.loc[u, "publica"]), "resultados_privada": int(res.loc[u, "privada"])}
                       for u, r in tab.iterrows()},
            "mista_total_pct": round(total_mista, 6), "mista_acima_de_10pct": total_mista > LIMITE_MISTA,
        },
    }
    arq_meta = DIR_PROCESSADOS / f"enem{ano}_participantes_meta.json"
    arq_meta.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    atualizar_doc(secao_doc(ano, funil, q023, tab, total_mista, ok_uf, ruins))
    print(f"[{ano}] Metadados -> {arq_meta.relative_to(RAIZ)}; seção atualizada em {DOC_EQUIVALENCIA.relative_to(RAIZ)}")
    print(f"[{ano}] Conferência do universo: {'ACEITA' if ok_uf else 'NÃO ACEITA: ' + ', '.join(ruins)}; "
          f"trajetória mista = {total_mista:.1%}")


if __name__ == "__main__":
    main()
