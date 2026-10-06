"""
Cálculo dos 20 KPIs do projeto (4 eixos × 5 indicadores).

A lógica é a mesma da Entrega 1, agora em função para ser reutilizada pelos dois notebooks.
Definições:
- Exatas = média de Ciências da Natureza e Matemática por aluno.
- Abstenção = TP_PRESENCA == 0 sobre a base completa; Presença = TP_PRESENCA == 1.
- Índice de Desigualdade Regional = coeficiente de variação (%) das médias estaduais da nota final.
- Gap de renda entre UFs = nota média da UF de maior renda per capita − nota média da UF de menor renda per capita.
"""

import pandas as pd

EIXO_A = "A) Desempenho Acadêmico"
EIXO_B = "B) Perfil Socioeconômico"
EIXO_C = "C) Cruzamento IBGE"
EIXO_D = "D) Operacional / Resumo"


def calcular_kpis(df: pd.DataFrame, df_pres: pd.DataFrame, df_ibge: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Devolve (df_kpis, auxiliares). `auxiliares` guarda as tabelas por UF usadas nos gráficos."""
    registro = []

    def kpi(eixo, nome, valor, unidade="", obs=""):
        registro.append({"Eixo": eixo, "KPI": nome, "Valor": valor, "Unidade": unidade, "Observação": obs})

    # ---------- Tabelas auxiliares por UF ----------
    media_uf = df_pres.groupby("UF")["NOTA_FINAL"].mean().rename("NOTA_MEDIA")
    tab_uf = (df_ibge.set_index("UF").join(media_uf)
              .join(df.groupby("UF").size().rename("INSCRITOS"))
              .join(df.groupby("UF")["RENDA_IDX"].mean().rename("RENDA_IDX_MEDIA")))
    tab_uf["DENSIDADE_100K"] = tab_uf["INSCRITOS"] / tab_uf["POPULACAO"] * 100_000

    A, B, C, D = EIXO_A, EIXO_B, EIXO_C, EIXO_D

    # ---------------- A) Desempenho Acadêmico ----------------
    kpi(A, "Média Geral por UF (melhor UF)", media_uf.max(), "pts",
        f"{media_uf.idxmax()} | pior: {media_uf.idxmin()} ({media_uf.min():.1f})")
    kpi(A, "Mediana da Redação", df_pres["NU_NOTA_REDACAO"].median(), "pts")
    exatas = (df_pres["NU_NOTA_CN"] + df_pres["NU_NOTA_MT"]) / 2
    kpi(A, "Desvio-padrão de Exatas (CN+MT)", exatas.std(), "pts")
    kpi(A, "Taxa de Notas > 700 (Nota Final)", (df_pres["NOTA_FINAL"] > 700).mean() * 100, "%")
    kpi(A, "Taxa de Zeros na Redação", (df_pres["NU_NOTA_REDACAO"] == 0).mean() * 100, "%")

    # ---------------- B) Perfil Socioeconômico ----------------
    renda_uf = tab_uf["RENDA_IDX_MEDIA"]
    kpi(B, "Média de Renda por UF (índice Q006, maior)", renda_uf.max(), "índice 0–16",
        f"{renda_uf.idxmax()} | menor: {renda_uf.idxmin()} ({renda_uf.min():.2f})")
    pct_escola = df["TP_ESCOLA"].value_counts(normalize=True) * 100
    kpi(B, "% Escola Pública", pct_escola["Pública"], "%", f"Privada: {pct_escola['Privada']:.1f}%")
    med_escola = df_pres.groupby("TP_ESCOLA")["NOTA_FINAL"].mean()
    kpi(B, "Razão de Notas Privada/Pública", med_escola["Privada"] / med_escola["Pública"], "razão",
        f"Privada {med_escola['Privada']:.1f} vs Pública {med_escola['Pública']:.1f}")
    dist_renda = df["FAIXA_RENDA"].value_counts(normalize=True).mul(100)
    kpi(B, "Distribuição por Faixa de Renda (% Baixa Renda)", dist_renda["Baixa Renda"], "%",
        f"Média: {dist_renda['Média Renda']:.1f}% | Alta: {dist_renda['Alta Renda']:.1f}%")
    kpi(B, "% Abstenção", df["FALTOU"].mean() * 100, "%")

    # ---------------- C) Cruzamento IBGE ----------------
    corr_idh = tab_uf["IDH_ESTADUAL"].corr(tab_uf["NOTA_MEDIA"])
    kpi(C, "Correlação IDH × Nota Média (Pearson, nível UF)", corr_idh, "r",
        f"n = {tab_uf['NOTA_MEDIA'].notna().sum()} UFs")
    uf_rico, uf_pobre = tab_uf["RENDA_PER_CAPITA"].idxmax(), tab_uf["RENDA_PER_CAPITA"].idxmin()
    kpi(C, "Gap de Nota: UF de maior vs menor renda per capita",
        tab_uf.loc[uf_rico, "NOTA_MEDIA"] - tab_uf.loc[uf_pobre, "NOTA_MEDIA"], "pts", f"{uf_rico} − {uf_pobre}")
    dens_nac = len(df) / df_ibge["POPULACAO"].sum() * 100_000
    kpi(C, "Densidade de Inscritos / 100 mil hab. (amostra)", dens_nac, "insc./100k",
        f"maior UF: {tab_uf['DENSIDADE_100K'].idxmax()} ({tab_uf['DENSIDADE_100K'].max():.2f})")
    abst_renda = df.groupby("FAIXA_RENDA", observed=True)["FALTOU"].mean() * 100
    kpi(C, "Taxa de Abstenção por Renda (Baixa − Alta)", abst_renda["Baixa Renda"] - abst_renda["Alta Renda"], "p.p.",
        f"Baixa {abst_renda['Baixa Renda']:.1f}% | Média {abst_renda['Média Renda']:.1f}% | Alta {abst_renda['Alta Renda']:.1f}%")
    kpi(C, "Índice de Desigualdade Regional (CV das médias por UF)", media_uf.std() / media_uf.mean() * 100, "%")

    # ---------------- D) Operacional / Resumo ----------------
    kpi(D, "Total de Inscritos na Amostra", len(df), "alunos")
    kpi(D, "Média Geral de Presença", df["PRESENTE"].mean() * 100, "%")
    baixa = df_pres[df_pres["FAIXA_RENDA"] == "Baixa Renda"]
    kpi(D, "% Alunos Baixa Renda com Nota > 600", (baixa["NOTA_FINAL"] > 600).mean() * 100, "%",
        f"base: {len(baixa):,} alunos")
    kpi(D, "Maior Nota Geral", df_pres["NOTA_FINAL"].max(), "pts")
    kpi(D, "Menor Nota Geral", df_pres["NOTA_FINAL"].min(), "pts")

    df_kpis = pd.DataFrame(registro)
    df_kpis.insert(0, "#", range(1, len(df_kpis) + 1))
    assert len(df_kpis) == 20, f"Esperados 20 KPIs, encontrados {len(df_kpis)}"

    auxiliares = {
        "media_uf": media_uf, "tab_uf": tab_uf, "med_escola": med_escola,
        "corr_idh": corr_idh, "abst_renda": abst_renda,
    }
    return df_kpis, auxiliares


def exibir_kpis(df_kpis: pd.DataFrame) -> None:
    """Exibe a tabela de KPIs agrupada por eixo (para uso em notebook)."""
    from IPython.display import display
    for eixo, grupo in df_kpis.groupby("Eixo", sort=True):
        print(f"\n{eixo}")
        display(grupo.drop(columns="Eixo").set_index("#").style.format({"Valor": "{:,.2f}"}))
