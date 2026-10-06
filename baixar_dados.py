"""
Coleta de dados do projeto ENEM × IBGE.

Etapas (todas reprodutíveis, SEED = 42):
  1. Baixa os microdados do ENEM 2023 (INEP) para dados/brutos/.
  2. Lê o CSV de dentro do .zip em blocos (chunksize), define o universo de
     análise e gera uma amostra estratificada por UF -> dados/processados/enem_amostra.parquet
  3. Monta dados/ibge_uf.csv com indicadores estaduais reais:
       - População residente (Censo 2022, SIDRA tabela 4709)
       - Rendimento médio mensal real domiciliar per capita (PNAD Contínua 2023, SIDRA tabela 7531)
       - IDHM 2023 (Radar IDHM 2012-2024, PNUD/Ipea/FJP, Tabela 5)
       - Região

Uso:
    python baixar_dados.py            # executa as três etapas
    python baixar_dados.py --so-ibge  # apenas a tabela do IBGE
    python baixar_dados.py --so-enem  # apenas download + amostra do ENEM

Por que ENEM 2023 e não 2024/2025? A partir de 2024 o INEP passou a publicar
notas (RESULTADOS) e questionário (PARTICIPANTES) em arquivos separados, sem
chave de ligação. Sem essa ligação não há como cruzar renda/tipo de escola com
nota no nível do aluno. Detalhes em docs/DECISOES.md.
"""

import argparse
import json
import sys
import zipfile
from pathlib import Path

import pandas as pd
import requests

SEED = 42
ANO_ENEM = 2023
FRACAO_AMOSTRA = 0.04  # 4% de cada UF (alocação proporcional)

RAIZ = Path(__file__).resolve().parent
DIR_BRUTOS = RAIZ / "dados" / "brutos"
DIR_PROCESSADOS = RAIZ / "dados" / "processados"
ARQ_ZIP = DIR_BRUTOS / f"microdados_enem_{ANO_ENEM}.zip"
ARQ_AMOSTRA = DIR_PROCESSADOS / "enem_amostra.parquet"
ARQ_META = DIR_PROCESSADOS / "enem_amostra_meta.json"
ARQ_IBGE = RAIZ / "dados" / "ibge_uf.csv"

URL_ENEM = f"https://download.inep.gov.br/microdados/microdados_enem_{ANO_ENEM}.zip"
CSV_DENTRO_DO_ZIP = f"microdados_enem_{ANO_ENEM}/DADOS/MICRODADOS_ENEM_{ANO_ENEM}.csv"

# Colunas lidas do CSV do INEP (o arquivo completo tem 76 colunas e ~1,8 GB)
COLUNAS_ENEM = [
    "NU_INSCRICAO", "TP_FAIXA_ETARIA", "TP_SEXO", "TP_COR_RACA", "TP_ST_CONCLUSAO",
    "TP_ESCOLA", "IN_TREINEIRO", "SG_UF_PROVA",
    "TP_PRESENCA_CN", "TP_PRESENCA_CH", "TP_PRESENCA_LC", "TP_PRESENCA_MT",
    "NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO", "TP_STATUS_REDACAO",
    "Q001", "Q002", "Q005", "Q006", "Q024", "Q025",
]

# Tipos explícitos: reduzem memória e evitam inferência errada entre blocos
TIPOS_ENEM = {
    "NU_INSCRICAO": "int64", "TP_FAIXA_ETARIA": "Int8", "TP_SEXO": "category", "TP_COR_RACA": "Int8",
    "TP_ST_CONCLUSAO": "Int8", "TP_ESCOLA": "Int8", "IN_TREINEIRO": "Int8", "SG_UF_PROVA": "category",
    "TP_PRESENCA_CN": "Int8", "TP_PRESENCA_CH": "Int8", "TP_PRESENCA_LC": "Int8", "TP_PRESENCA_MT": "Int8",
    "NU_NOTA_CN": "float32", "NU_NOTA_CH": "float32", "NU_NOTA_LC": "float32", "NU_NOTA_MT": "float32",
    "NU_NOTA_REDACAO": "float32", "TP_STATUS_REDACAO": "Int8",
    "Q001": "category", "Q002": "category", "Q005": "Int8", "Q006": "category",
    "Q024": "category", "Q025": "category",
}

# Código IBGE da UF -> (sigla, região)
UFS = {
    11: ("RO", "Norte"), 12: ("AC", "Norte"), 13: ("AM", "Norte"), 14: ("RR", "Norte"),
    15: ("PA", "Norte"), 16: ("AP", "Norte"), 17: ("TO", "Norte"),
    21: ("MA", "Nordeste"), 22: ("PI", "Nordeste"), 23: ("CE", "Nordeste"), 24: ("RN", "Nordeste"),
    25: ("PB", "Nordeste"), 26: ("PE", "Nordeste"), 27: ("AL", "Nordeste"), 28: ("SE", "Nordeste"),
    29: ("BA", "Nordeste"),
    31: ("MG", "Sudeste"), 32: ("ES", "Sudeste"), 33: ("RJ", "Sudeste"), 35: ("SP", "Sudeste"),
    41: ("PR", "Sul"), 42: ("SC", "Sul"), 43: ("RS", "Sul"),
    50: ("MS", "Centro-Oeste"), 51: ("MT", "Centro-Oeste"), 52: ("GO", "Centro-Oeste"),
    53: ("DF", "Centro-Oeste"),
}

# IDHM 2023 por UF, transcrito da Tabela 5 (p. 125) de:
# PNUD, Ipea e FJP. "Radar IDHM: evolução do IDHM e de seus componentes no período
# de 2012 a 2024". Brasília, maio de 2026 (dados do Atlas do Desenvolvimento Humano no Brasil).
# O PNUD não oferece API para essa tabela, por isso os valores estão fixos aqui.
IDHM_2023 = {
    "DF": 0.870, "SP": 0.836, "SC": 0.821, "PR": 0.812, "RJ": 0.813, "RS": 0.806, "GO": 0.809,
    "MT": 0.795, "MG": 0.803, "ES": 0.803, "TO": 0.789, "MS": 0.790, "RO": 0.768, "RR": 0.769,
    "RN": 0.763, "CE": 0.773, "AM": 0.764, "PE": 0.754, "PI": 0.761, "SE": 0.748, "PB": 0.757,
    "AP": 0.767, "BA": 0.740, "PA": 0.753, "AC": 0.740, "AL": 0.739, "MA": 0.740,
}

URL_SIDRA_POP = "https://apisidra.ibge.gov.br/values/t/4709/n3/all/v/93/p/2022"
URL_SIDRA_RENDA = "https://apisidra.ibge.gov.br/values/t/7531/n3/all/v/10824/p/2023/c1019/49243"


# --------------------------------------------------------------------------
# 1) Download dos microdados
# --------------------------------------------------------------------------
def baixar_enem(forcar: bool = False) -> Path:
    """Baixa o .zip do INEP (~550 MB) em blocos, sem carregar tudo na memória."""
    DIR_BRUTOS.mkdir(parents=True, exist_ok=True)
    if ARQ_ZIP.exists() and not forcar:
        print(f"[ENEM] Zip já existe: {ARQ_ZIP.relative_to(RAIZ)}")
        return ARQ_ZIP

    print(f"[ENEM] Baixando {URL_ENEM}")
    temporario = ARQ_ZIP.with_suffix(".part")
    with requests.get(URL_ENEM, stream=True, timeout=120) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        baixado = 0
        with open(temporario, "wb") as f:
            for bloco in r.iter_content(chunk_size=1 << 20):
                f.write(bloco)
                baixado += len(bloco)
                if total:
                    print(f"\r       {baixado / total:6.1%} de {total / 1e6:,.0f} MB", end="")
    print()
    if total and temporario.stat().st_size != total:
        raise RuntimeError("Download incompleto: tamanho diferente do informado pelo servidor.")
    temporario.replace(ARQ_ZIP)
    return ARQ_ZIP


# --------------------------------------------------------------------------
# 2) Leitura em blocos + amostra estratificada por UF
# --------------------------------------------------------------------------
def gerar_amostra(fracao: float = FRACAO_AMOSTRA, chunksize: int = 500_000) -> pd.DataFrame:
    """
    Universo de análise: concluintes do ensino médio em 2023 (TP_ST_CONCLUSAO = 2),
    não treineiros, que informaram escola pública ou privada (TP_ESCOLA 2 ou 3).
    No ENEM 2023 o INEP só preenche TP_ESCOLA para esse grupo; os demais aparecem
    como "Não respondeu" (ver docs/DECISOES.md).
    """
    funil = {"linhas_lidas": 0, "concluintes_2023": 0, "nao_treineiros": 0, "escola_informada": 0}
    blocos = []

    with zipfile.ZipFile(ARQ_ZIP) as z, z.open(CSV_DENTRO_DO_ZIP) as f:
        leitor = pd.read_csv(f, sep=";", encoding="latin-1", usecols=COLUNAS_ENEM,
                             dtype=TIPOS_ENEM, chunksize=chunksize)
        for i, bloco in enumerate(leitor, start=1):
            funil["linhas_lidas"] += len(bloco)
            bloco = bloco[bloco["TP_ST_CONCLUSAO"] == 2]
            funil["concluintes_2023"] += len(bloco)
            bloco = bloco[bloco["IN_TREINEIRO"] == 0]
            funil["nao_treineiros"] += len(bloco)
            bloco = bloco[bloco["TP_ESCOLA"].isin([2, 3])]
            funil["escola_informada"] += len(bloco)
            blocos.append(bloco)
            print(f"\r[ENEM] Bloco {i:>2}: {funil['linhas_lidas']:,} linhas lidas", end="")
    print()

    universo = pd.concat(blocos, ignore_index=True)
    # Categorias podem divergir entre blocos; reunificamos antes de amostrar
    for col in universo.select_dtypes("object").columns:
        universo[col] = universo[col].astype("category")

    # Amostra estratificada: mesma fração em cada UF (alocação proporcional)
    amostra = (universo.groupby("SG_UF_PROVA", observed=True, group_keys=False)
               .sample(frac=fracao, random_state=SEED)
               .reset_index(drop=True))

    universo_uf = universo["SG_UF_PROVA"].value_counts().sort_index()
    amostra_uf = amostra["SG_UF_PROVA"].value_counts().sort_index()

    DIR_PROCESSADOS.mkdir(parents=True, exist_ok=True)
    amostra.to_parquet(ARQ_AMOSTRA, index=False)
    meta = {
        "fonte": f"INEP - Microdados do ENEM {ANO_ENEM}",
        "url": URL_ENEM,
        "seed": SEED,
        "fracao_por_uf": fracao,
        "funil": funil,
        "linhas_amostra": int(len(amostra)),
        "universo_por_uf": {str(k): int(v) for k, v in universo_uf.items()},
        "amostra_por_uf": {str(k): int(v) for k, v in amostra_uf.items()},
    }
    ARQ_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[ENEM] Funil: {funil}")
    print(f"[ENEM] Amostra: {len(amostra):,} linhas -> {ARQ_AMOSTRA.relative_to(RAIZ)}")
    return amostra


# --------------------------------------------------------------------------
# 3) Indicadores estaduais (IBGE / PNUD)
# --------------------------------------------------------------------------
def _consultar_sidra(url: str, nome_coluna: str) -> pd.DataFrame:
    """Consulta a API do SIDRA e devolve [CO_UF, nome_coluna]."""
    resposta = requests.get(url, timeout=60)
    resposta.raise_for_status()
    linhas = resposta.json()[1:]  # a primeira linha é o cabeçalho descritivo
    return pd.DataFrame({
        "CO_UF": [int(l["D1C"]) for l in linhas],
        nome_coluna: [float(l["V"]) for l in linhas],
    })


def montar_ibge() -> pd.DataFrame:
    pop = _consultar_sidra(URL_SIDRA_POP, "POPULACAO")
    renda = _consultar_sidra(URL_SIDRA_RENDA, "RENDA_PER_CAPITA")

    df = pd.DataFrame(
        [(cod, sigla, regiao) for cod, (sigla, regiao) in UFS.items()],
        columns=["CO_UF", "UF", "REGIAO"],
    )
    df = df.merge(pop, on="CO_UF", validate="1:1").merge(renda, on="CO_UF", validate="1:1")
    df["POPULACAO"] = df["POPULACAO"].astype("int64")
    df["IDH_ESTADUAL"] = df["UF"].map(IDHM_2023)
    assert df.notna().all().all() and len(df) == 27, "Tabela do IBGE incompleta"

    # Fonte e ano de cada indicador ficam no próprio arquivo
    df["ANO_POPULACAO"] = 2022
    df["FONTE_POPULACAO"] = "IBGE - Censo Demográfico 2022 (SIDRA tabela 4709, variável 93)"
    df["ANO_RENDA"] = 2023
    df["FONTE_RENDA"] = ("IBGE - PNAD Contínua anual, rendimento médio mensal real domiciliar "
                         "per capita a preços médios do ano, R$ (SIDRA tabela 7531, variável 10824)")
    df["ANO_IDH"] = 2023
    df["FONTE_IDH"] = "PNUD/Ipea/FJP - Radar IDHM 2012-2024 (Atlas Brasil), Tabela 5, maio/2026"

    df.to_csv(ARQ_IBGE, index=False, encoding="utf-8")
    print(f"[IBGE] {len(df)} UFs -> {ARQ_IBGE.relative_to(RAIZ)}")
    return df


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--so-ibge", action="store_true", help="gera apenas dados/ibge_uf.csv")
    grupo.add_argument("--so-enem", action="store_true", help="baixa o ENEM e gera apenas a amostra")
    parser.add_argument("--forcar-download", action="store_true", help="baixa o zip mesmo se já existir")
    args = parser.parse_args(argv)

    if not args.so_ibge:
        baixar_enem(forcar=args.forcar_download)
        gerar_amostra()
    if not args.so_enem:
        montar_ibge()


if __name__ == "__main__":
    sys.exit(main())
