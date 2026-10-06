"""
Carga dos dados (reais ou simulados) e ETL.

Fonte única usada pelos notebooks da Entrega 1 e da Entrega 2.
- Dados reais: amostra do ENEM 2023 (INEP) gerada por `baixar_dados.py` + `dados/ibge_uf.csv`.
- Simulação: mantida como fallback (`USAR_DADOS_REAIS = False`), com as mesmas colunas principais.
"""

from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42

RAIZ = Path(__file__).resolve().parent.parent
ARQ_AMOSTRA = RAIZ / "dados" / "processados" / "enem_amostra.parquet"
ARQ_META_AMOSTRA = RAIZ / "dados" / "processados" / "enem_amostra_meta.json"
ARQ_IBGE = RAIZ / "dados" / "ibge_uf.csv"

COLS_NOTAS = ["NU_NOTA_CN", "NU_NOTA_CH", "NU_NOTA_LC", "NU_NOTA_MT", "NU_NOTA_REDACAO"]
COLS_PRESENCA = ["TP_PRESENCA_CN", "TP_PRESENCA_CH", "TP_PRESENCA_LC", "TP_PRESENCA_MT"]
COLS_IBGE = ["UF", "REGIAO", "IDH_ESTADUAL", "RENDA_PER_CAPITA", "POPULACAO"]
# Colunas reais que não existem na simulação; ficam disponíveis para a modelagem
COLS_EXTRAS = ["TP_SEXO", "TP_COR_RACA", "TP_FAIXA_ETARIA", "Q001", "Q002", "Q005", "Q024", "Q025",
               "TP_STATUS_REDACAO"]
ORDEM_RENDA = ["Baixa Renda", "Média Renda", "Alta Renda"]


# ==========================================================================
# Simulação (fallback)
# ==========================================================================
def gerar_ibge() -> pd.DataFrame:
    """Indicadores estaduais (valores aproximados, uso didático)."""
    dados = [
        # UF, Região, IDH, Renda per capita (R$), População
        ("RO", "Norte", 0.725, 1600, 1_581_196), ("AC", "Norte", 0.710, 1300, 830_018),
        ("AM", "Norte", 0.700, 1200, 3_941_613), ("RR", "Norte", 0.707, 1500, 636_707),
        ("PA", "Norte", 0.690, 1100, 8_120_131), ("AP", "Norte", 0.688, 1300, 733_759),
        ("TO", "Norte", 0.731, 1500, 1_511_460),
        ("MA", "Nordeste", 0.676, 900, 6_776_699), ("PI", "Nordeste", 0.690, 1000, 3_271_199),
        ("CE", "Nordeste", 0.734, 1100, 8_794_957), ("RN", "Nordeste", 0.728, 1400, 3_302_729),
        ("PB", "Nordeste", 0.698, 1200, 3_974_687), ("PE", "Nordeste", 0.719, 1200, 9_058_931),
        ("AL", "Nordeste", 0.684, 1000, 3_127_683), ("SE", "Nordeste", 0.702, 1300, 2_210_004),
        ("BA", "Nordeste", 0.714, 1100, 14_141_626),
        ("MG", "Sudeste", 0.774, 1900, 20_538_718), ("ES", "Sudeste", 0.771, 1900, 3_833_712),
        ("RJ", "Sudeste", 0.762, 2300, 16_055_174), ("SP", "Sudeste", 0.806, 2400, 44_411_238),
        ("PR", "Sul", 0.769, 2000, 11_444_380), ("SC", "Sul", 0.792, 2500, 7_610_361),
        ("RS", "Sul", 0.771, 2300, 10_882_965),
        ("MS", "Centro-Oeste", 0.742, 2000, 2_757_013), ("MT", "Centro-Oeste", 0.736, 1900, 3_658_649),
        ("GO", "Centro-Oeste", 0.737, 1900, 7_056_495), ("DF", "Centro-Oeste", 0.814, 3500, 2_817_381),
    ]
    return pd.DataFrame(dados, columns=COLS_IBGE)


def gerar_enem(df_ibge: pd.DataFrame, n: int = 3000, rng=None) -> pd.DataFrame:
    """Amostra fictícia, mas estatisticamente coerente, de inscritos no ENEM."""
    if rng is None:
        rng = np.random.default_rng(SEED)
    ibge = df_ibge.set_index("UF")

    # UF sorteada proporcionalmente à população (suavizada)
    pesos = ibge["POPULACAO"] ** 0.8
    uf = rng.choice(ibge.index, size=n, p=(pesos / pesos.sum()).values)

    idh = ibge.loc[uf, "IDH_ESTADUAL"].values
    renda_pc = ibge.loc[uf, "RENDA_PER_CAPITA"].values
    renda_norm = (renda_pc - renda_pc.min()) / (renda_pc.max() - renda_pc.min())

    # Escola privada: mais provável em UFs com IDH maior (~10% a ~35%)
    p_priv = np.clip(0.10 + (idh - 0.67) * 1.8, 0.05, 0.45)
    privada = rng.random(n) < p_priv
    tp_escola = np.where(privada, "Privada", "Pública")

    # Q006 (A..Q): 17 faixas de renda familiar; depende de UF e escola
    idx_renda = np.clip(np.round(rng.normal(2.0 + 3.0 * renda_norm + 4.5 * privada, 2.0)), 0, 16).astype(int)
    q006 = np.array([chr(65 + i) for i in idx_renda])

    # Habilidade latente (padronizada): renda + escola + IDH + ruído individual
    z_renda = (idx_renda - idx_renda.mean()) / idx_renda.std()
    z_idh = (idh - idh.mean()) / idh.std()
    habilidade = 0.40 * z_renda + 0.30 * privada + 0.15 * z_idh + rng.normal(0, 0.80, n)

    def nota(media, sd, peso):
        return np.clip(media + peso * habilidade + rng.normal(0, sd, n), 0, 1000)

    cn, ch, lc, mt = nota(485, 55, 55), nota(520, 60, 55), nota(510, 50, 45), nota(530, 70, 75)
    red = np.clip(np.round((570 + 110 * habilidade + rng.normal(0, 110, n)) / 20) * 20, 0, 1000)
    red[rng.random(n) < 0.015] = 0  # redações anuladas / zeradas

    # Presença: ausência é mais frequente em rendas baixas
    p_falta = np.clip(0.30 - 0.012 * idx_renda - 0.05 * privada, 0.05, 0.45)
    sorteio = rng.random(n)
    presenca = np.where(sorteio < p_falta, 0, np.where(sorteio > 0.985, 2, 1))

    df = pd.DataFrame({
        "UF": uf, "TP_ESCOLA": tp_escola, "Q006": q006,
        "NU_NOTA_CN": cn.round(1), "NU_NOTA_CH": ch.round(1), "NU_NOTA_LC": lc.round(1),
        "NU_NOTA_MT": mt.round(1), "NU_NOTA_REDACAO": red, "TP_PRESENCA": presenca,
    })

    # Quem faltou ou foi eliminado não tem notas (NaN), como nos microdados reais
    cols_nota = [c for c in df.columns if c.startswith("NU_NOTA")]
    df.loc[df["TP_PRESENCA"] != 1, cols_nota] = np.nan

    # Pequena parcela de nulos aleatórios (falhas de registro) para exercitar o tratamento
    presentes = df.index[df["TP_PRESENCA"] == 1]
    falhas = rng.choice(presentes, size=int(0.01 * len(presentes)), replace=False)
    df.loc[falhas, "NU_NOTA_CN"] = np.nan
    return df


# ==========================================================================
# Dados reais
# ==========================================================================
def carregar_ibge_real(caminho: Path = ARQ_IBGE) -> pd.DataFrame:
    """Indicadores estaduais reais (Censo 2022, PNAD Contínua 2023, IDHM 2023)."""
    return pd.read_csv(caminho)[COLS_IBGE]


def unificar_presenca(bruto: pd.DataFrame) -> np.ndarray:
    """Converte as 4 colunas de presença do INEP em um único código.
    2 = eliminado em alguma prova | 1 = presente nas quatro | 0 = faltou a pelo menos um dia."""
    p = bruto[COLS_PRESENCA]
    return np.select([(p == 2).any(axis=1), (p == 1).all(axis=1)], [2, 1], default=0)


def carregar_enem_real(caminho: Path = ARQ_AMOSTRA) -> pd.DataFrame:
    """Lê a amostra estratificada e traduz as colunas do INEP para os nomes do projeto."""
    bruto = pd.read_parquet(caminho)
    df = pd.DataFrame({
        "UF": bruto["SG_UF_PROVA"].astype(str),
        "TP_ESCOLA": bruto["TP_ESCOLA"].map({2: "Pública", 3: "Privada"}).astype(str),
        "Q006": bruto["Q006"].astype(str),
    })
    for col in COLS_NOTAS:
        df[col] = bruto[col].astype("float64")
    df["TP_PRESENCA"] = unificar_presenca(bruto)
    for col in COLS_EXTRAS:
        df[col] = bruto[col]
    return df


def carregar_dados(usar_dados_reais: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devolve (df_ibge, df_enem) reais ou simulados."""
    if usar_dados_reais:
        return carregar_ibge_real(), carregar_enem_real()
    df_ibge = gerar_ibge()
    return df_ibge, gerar_enem(df_ibge, n=3000)


# ==========================================================================
# ETL
# ==========================================================================
def mapear_faixa_renda(q006: str) -> str:
    """A–D (até 2 SM) → Baixa | E–H (2 a 5 SM) → Média | I–Q (> 5 SM) → Alta. SM 2023 = R$ 1.320."""
    if q006 in list("ABCD"):
        return "Baixa Renda"
    if q006 in list("EFGH"):
        return "Média Renda"
    return "Alta Renda"


def etl(df_enem: pd.DataFrame, df_ibge: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    # 1) Diagnóstico de nulos
    if verbose:
        print("Nulos por coluna (antes do tratamento):")
        print(df_enem.isna().sum()[lambda s: s > 0].to_string(), "\n")

    # 2) Merge com validação de cardinalidade (muitos alunos -> uma UF)
    df = df_enem.merge(df_ibge, on="UF", how="left", validate="m:1")
    assert df["IDH_ESTADUAL"].notna().all(), "Há UFs sem correspondência no IBGE!"

    # 3) Nota final = média das 5 provas (NaN se faltar alguma)
    df["NOTA_FINAL"] = df[COLS_NOTAS].mean(axis=1, skipna=False)

    # 4) Faixa de renda categórica ordenada + índice numérico (A=0 ... Q=16)
    df["FAIXA_RENDA"] = pd.Categorical(df["Q006"].map(mapear_faixa_renda), categories=ORDEM_RENDA, ordered=True)
    df["RENDA_IDX"] = df["Q006"].map(lambda x: ord(x) - 65)

    # 5) Flags de presença e padronização de rótulos
    df["PRESENTE"] = (df["TP_PRESENCA"] == 1)
    df["FALTOU"] = (df["TP_PRESENCA"] == 0)
    return df


def recorte_presentes(df: pd.DataFrame) -> pd.DataFrame:
    """Recorte analítico: presentes com NOTA_FINAL válida (nulos acidentais são descartados)."""
    return df[df["PRESENTE"] & df["NOTA_FINAL"].notna()].copy()
