"""
Gera o dashboard estático "Socioeconomia vs. Desempenho no ENEM" (um único index.html).

Usa as mesmas funções dos notebooks (src.dados, src.kpis, src.estilo), calcula tudo em Python
e grava HTML + JavaScript puro, que o GitHub Pages serve sem backend.

Uso (na raiz do repositório):
    python gerar_dashboard.py                      # grava docs/index.html
    python gerar_dashboard.py --saida index.html   # outro caminho
    python gerar_dashboard.py --offline            # embute o Plotly.js (+4 MB), sem depender de CDN
"""

import argparse
import html
import json
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs, get_plotlyjs_version
from plotly.subplots import make_subplots

from src.dados import ORDEM_RENDA, carregar_dados, etl, recorte_presentes
from src.estilo import AZUL, CORES_ESCOLA, CORES_MODELOS, CORES_RENDA, DESTAQUE, LARANJA, RAMPA_AZUL
from src.features import criar_features
from src.kpis import calcular_kpis

RAIZ = Path(__file__).resolve().parent
FONTE = "Public Sans, system-ui, sans-serif"
CFG = {"responsive": True, "displaylogo": False}
PROVAS = {"NOTA_FINAL": "Nota final", "NU_NOTA_CN": "Ciências da Natureza", "NU_NOTA_CH": "Ciências Humanas",
          "NU_NOTA_LC": "Linguagens", "NU_NOTA_MT": "Matemática", "NU_NOTA_REDACAO": "Redação"}
CORES_REGIAO = {"Norte": "#1baf7a", "Nordeste": "#8e5bd3", "Sudeste": "#c9a227", "Sul": "#d6428f",
                "Centro-Oeste": "#4a5568"}


def _br(v, casas=1):
    """Número no padrão brasileiro (1.234,5)."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


def _base(fig, altura=480):
    fig.update_layout(
        height=altura, separators=",.", font=dict(family=FONTE, color="#14202e", size=13),
        margin=dict(l=55, r=15, t=75, b=55), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=-0.2), hoverlabel=dict(font_family=FONTE))
    fig.update_xaxes(gridcolor="#e3e7ec", zeroline=False)
    fig.update_yaxes(gridcolor="#e3e7ec", zeroline=False)
    return fig


def _menu(botoes):
    return [dict(type="dropdown", buttons=botoes, x=0, xanchor="left", y=1.16, yanchor="bottom",
                 bgcolor="white", bordercolor="#c5ccd6")]


# --------------------------------------------------------------------------
# Gráficos
# --------------------------------------------------------------------------
def grafico_uf(df_pres, tab_uf):
    """Barras por UF, coloridas por região; o menu troca a prova."""
    med = df_pres.groupby("UF")[list(PROVAS)].mean()
    ordem = med["NOTA_FINAL"].sort_values(ascending=False).index
    grupos = [(r, [u for u in ordem if tab_uf.loc[u, "REGIAO"] == r]) for r in CORES_REGIAO]
    grupos = [(r, ufs) for r, ufs in grupos if ufs]

    fig = go.Figure()
    for r, ufs in grupos:
        fig.add_bar(x=ufs, y=med.loc[ufs, "NOTA_FINAL"].round(1), name=r, marker_color=CORES_REGIAO[r],
                    hovertemplate="<b>%{x}</b><br>%{y:.1f} pts<extra>" + r + "</extra>")
    botoes = []
    for col, rotulo in PROVAS.items():
        botoes.append(dict(label=rotulo, method="update", args=[
            {"y": [med.loc[ufs, col].round(1).tolist() for _, ufs in grupos]},
            {"yaxis.range": [float(med[col].min() - 30), float(med[col].max() + 15)],
             "yaxis.title.text": f"{rotulo} (média, pts)"}]))
    _base(fig).update_layout(barmode="overlay", updatemenus=_menu(botoes), xaxis=dict(categoryorder="array",
                             categoryarray=list(ordem)), yaxis=dict(title="Nota final (média, pts)",
                             range=[float(med["NOTA_FINAL"].min() - 30), float(med["NOTA_FINAL"].max() + 15)]))
    return fig


def grafico_idh(tab_uf):
    """Bolhas (tamanho = população). O menu alterna entre IDHM e renda per capita no eixo x."""
    t = tab_uf.dropna(subset=["NOTA_MEDIA"])
    eixos = {"IDH_ESTADUAL": "IDHM 2023", "RENDA_PER_CAPITA": "Renda per capita 2023 (R$)"}
    sizeref = 2 * t["POPULACAO"].max() / 40 ** 2
    subs = [(r, t[t["REGIAO"] == r]) for r in CORES_REGIAO]
    subs = [(r, s) for r, s in subs if len(s)]

    fig = go.Figure()
    for r, s in subs:
        fig.add_scatter(
            x=s["IDH_ESTADUAL"], y=s["NOTA_MEDIA"].round(1), mode="markers+text", text=s.index,
            textposition="top center", textfont=dict(size=10), name=r,
            customdata=s[["IDH_ESTADUAL", "RENDA_PER_CAPITA", "POPULACAO"]],
            marker=dict(size=s["POPULACAO"], sizemode="area", sizeref=sizeref, color=CORES_REGIAO[r],
                        opacity=0.85, line=dict(width=1, color="white")),
            hovertemplate=("<b>%{text}</b><br>Nota média: %{y:.1f}<br>IDHM: %{customdata[0]:.3f}"
                           "<br>Renda per capita: R$ %{customdata[1]:,.0f}<br>População: %{customdata[2]:,.0f}"
                           "<extra>" + r + "</extra>"))
    botoes, retas = [], {}
    for col, rotulo in eixos.items():
        a, b = np.polyfit(t[col], t["NOTA_MEDIA"], 1)
        xr = np.array([t[col].min(), t[col].max()])
        retas[col] = (xr.tolist(), (a * xr + b).tolist())
        r_ = np.corrcoef(t[col], t["NOTA_MEDIA"])[0, 1]
        botoes.append(dict(label=f"{rotulo.split(' 2023')[0]} (r = {r_:.2f})".replace(".", ","), method="update", args=[
            {"x": [s[col].tolist() for _, s in subs] + [retas[col][0]],
             "y": [s["NOTA_MEDIA"].round(1).tolist() for _, s in subs] + [retas[col][1]]},
            {"xaxis.title.text": rotulo, "xaxis.autorange": True}]))
    fig.add_scatter(x=retas["IDH_ESTADUAL"][0], y=retas["IDH_ESTADUAL"][1], mode="lines", name="Tendência linear",
                    line=dict(color=DESTAQUE, dash="dash", width=2), hoverinfo="skip")
    _base(fig, 520).update_layout(updatemenus=_menu(botoes), xaxis_title=eixos["IDH_ESTADUAL"],
                                  yaxis_title="Nota final média da UF (pts)")
    return fig


def grafico_renda(df_pres, aux):
    """Esquerda: nota média por faixa de renda e escola. Direita: abstenção por faixa de renda."""
    fig = make_subplots(rows=1, cols=2, column_widths=[0.62, 0.38], horizontal_spacing=0.1,
                        subplot_titles=("Nota final média dos presentes", "Alunos que faltaram (%)"))
    g = df_pres.groupby(["FAIXA_RENDA", "TP_ESCOLA"], observed=True)["NOTA_FINAL"].agg(["mean", "size"])
    for escola in ["Pública", "Privada"]:
        s = g.xs(escola, level="TP_ESCOLA").reindex(ORDEM_RENDA)
        fig.add_trace(go.Bar(x=ORDEM_RENDA, y=s["mean"].round(1), name=escola, marker_color=CORES_ESCOLA[escola],
                             customdata=s["size"], hovertemplate="<b>%{x}</b><br>Média: %{y:.1f} pts"
                             "<br>Alunos: %{customdata:,.0f}<extra>" + escola + "</extra>"), row=1, col=1)
    abst = aux["abst_renda"].reindex(ORDEM_RENDA)
    fig.add_trace(go.Bar(x=ORDEM_RENDA, y=abst.round(1), marker_color=[CORES_RENDA[f] for f in ORDEM_RENDA],
                         text=[f"{v:.1f}%".replace(".", ",") for v in abst], textposition="outside",
                         showlegend=False, hovertemplate="<b>%{x}</b><br>%{y:.1f}% faltaram<extra></extra>"),
                  row=1, col=2)
    _base(fig).update_layout(margin=dict(l=55, r=15, t=45, b=55))
    fig.update_yaxes(title_text="pts", row=1, col=1)
    fig.update_yaxes(title_text="%", range=[0, float(abst.max() * 1.2)], row=1, col=2)
    return fig


def grafico_distribuicao(df_pres):
    """% de alunos por faixa de 25 pontos, por tipo de escola; o menu troca a prova."""
    bins = np.arange(0, 1001, 25)
    centros = ((bins[:-1] + bins[1:]) / 2).tolist()
    faixas = [f"{a}–{b}" for a, b in zip(bins[:-1], bins[1:])]

    def dens(col):
        out = []
        for e in ["Pública", "Privada"]:
            v = df_pres.loc[df_pres["TP_ESCOLA"] == e, col]
            out.append((np.histogram(v, bins=bins)[0] / len(v) * 100).round(2).tolist())
        return out

    fig = go.Figure()
    for e, y in zip(["Pública", "Privada"], dens("NOTA_FINAL")):
        fig.add_scatter(x=centros, y=y, mode="lines", name=e, fill="tozeroy", customdata=faixas,
                        line=dict(color=CORES_ESCOLA[e], width=2), fillcolor=_rgba(CORES_ESCOLA[e], 0.18),
                        hovertemplate="Faixa %{customdata} pts<br>%{y:.1f}% dos alunos<extra>" + e + "</extra>")
    botoes = [dict(label=rot, method="restyle", args=[{"y": dens(col)}]) for col, rot in PROVAS.items()]
    _base(fig).update_layout(updatemenus=_menu(botoes), xaxis_title="Nota (pts)",
                             yaxis_title="% dos alunos da rede", hovermode="x unified")
    return fig


# --------------------------------------------------------------------------
# Página
# --------------------------------------------------------------------------
MIN_N = 30  # células com menos alunos ficam em branco (evita médias instáveis)
ESC_ROTULOS = ["Nunca estudou", "Fund. 1 incompleto", "Fund. 1 completo", "Fund. 2 completo",
               "Médio completo", "Superior completo", "Pós-graduação"]


def grafico_mae_renda(dm):
    """Mapa de calor: nota média por escolaridade da mãe × faixa de renda."""
    g = dm.dropna(subset=["ESC_MAE"]).groupby(["ESC_MAE", "FAIXA_RENDA"])["NOTA_FINAL"].agg(["mean", "size"])
    media = g["mean"].unstack().reindex(index=range(7), columns=ORDEM_RENDA)
    n = g["size"].unstack().reindex(index=range(7), columns=ORDEM_RENDA).fillna(0)
    media = media.where(n >= MIN_N)
    fig = go.Figure(go.Heatmap(
        z=media.values.round(1), x=ORDEM_RENDA, y=ESC_ROTULOS, customdata=n.values, hoverongaps=False,
        colorscale=[[0, RAMPA_AZUL[0]], [0.5, RAMPA_AZUL[1]], [1, RAMPA_AZUL[2]]], texttemplate="%{z:.0f}",
        colorbar=dict(title="pts"), xgap=2, ygap=2,
        hovertemplate="Mãe: %{y}<br>Renda: %{x}<br>Nota média: %{z:.1f} pts<br>Alunos: %{customdata:,.0f}<extra></extra>"))
    _base(fig, 440).update_layout(margin=dict(l=130, r=15, t=20, b=45), legend=None)
    return fig


def grafico_recursos(dm):
    """Nota média por nº de computadores em casa, com e sem internet."""
    g = dm.dropna(subset=["N_COMPUTADORES"]).groupby(["N_COMPUTADORES", "TEM_INTERNET"])["NOTA_FINAL"].agg(["mean", "size"])
    fig = go.Figure()
    for flag, nome, cor in [(1, "Com internet", RAMPA_AZUL[2]), (0, "Sem internet", RAMPA_AZUL[0])]:
        s = g.xs(flag, level="TEM_INTERNET").reindex(range(5))
        s["mean"] = s["mean"].where(s["size"].fillna(0) >= MIN_N)
        fig.add_bar(x=["0", "1", "2", "3", "4 ou mais"], y=s["mean"].round(1), name=nome, marker_color=cor,
                    customdata=s["size"].fillna(0), hovertemplate="<b>%{x} computador(es)</b><br>Média: %{y:.1f} pts"
                    "<br>Alunos: %{customdata:,.0f}<extra>" + nome + "</extra>")
    _base(fig, 420).update_layout(xaxis_title="Computadores em casa", yaxis_title="Nota final média (pts)")
    return fig


def grafico_coeficientes(res):
    """Coeficientes da Regressão Linear (efeito em pontos na nota final)."""
    itens = sorted(res["regressao_linear"]["coeficientes"].items(), key=lambda kv: kv[1])
    nomes, vals = [k for k, _ in itens], [v for _, v in itens]
    fig = go.Figure(go.Bar(x=vals, y=nomes, orientation="h", marker_color=[AZUL if v > 0 else LARANJA for v in vals],
                           hovertemplate="<b>%{y}</b><br>%{x:+.1f} pts<extra></extra>"))
    _base(fig, max(420, 24 * len(nomes))).update_layout(margin=dict(l=170, r=15, t=20, b=45),
                                                        xaxis_title="Efeito na nota final (pts)")
    return fig


def grafico_modelos(res):
    """Métricas dos três classificadores no conjunto de teste."""
    metricas = ["Precisão", "Recall", "F1", "ROC-AUC"]
    fig = go.Figure()
    for nome, d in res["classificacao"].items():
        fig.add_bar(x=metricas, y=[round(d["teste"][m], 3) for m in metricas], name=nome,
                    marker_color=CORES_MODELOS.get(nome), text=[f"{d['teste'][m]:.2f}".replace(".", ",") for m in metricas],
                    textposition="outside", hovertemplate="<b>%{x}</b>: %{y:.3f}<extra>" + nome + "</extra>")
    fig.add_hline(y=res["base"]["taxa_alto_desempenho"], line_dash="dash", line_color=DESTAQUE,
                  annotation_text="taxa base (precisão de um palpite aleatório)", annotation_position="top left")
    _base(fig, 440).update_layout(yaxis=dict(range=[0, 1.1], title="valor no teste"), margin=dict(l=55, r=15, t=20, b=55))
    return fig


def _secao(titulo, texto, *figs):
    return f"<section><h2>{titulo}</h2><p>{texto}</p>{''.join(figs)}</section>"


def _fmt_kpi(v, un):
    casas = 0 if un == "alunos" else 2 if un in ("r", "razão", "índice 0–16") else 1
    return _br(v, casas), ("%" if un == "%" else "" if un in ("r", "razão") else f" {un}")


def html_kpis(df_kpis):
    blocos = []
    for eixo, g in df_kpis.groupby("Eixo", sort=True):
        cards = ""
        for r in g.to_dict("records"):
            valor, un = _fmt_kpi(r["Valor"], r["Unidade"])
            cards += (f'<div class="kpi"><div class="v">{valor}<small>{html.escape(un)}</small></div>'
                      f'<div class="n">{html.escape(r["KPI"])}</div>'
                      f'<div class="o">{html.escape(str(r["Observação"]))}</div></div>')
        blocos.append(f'<h3>{html.escape(eixo)}</h3><div class="grid">{cards}</div>')
    return "".join(blocos)


PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Socioeconomia vs. Desempenho no ENEM</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;600;800&display=swap" rel="stylesheet">
__PLOTLY__
<style>
:root{--ink:#14202e;--mut:#5b6776;--line:#d9dee5;--bg:#f4f6f9;--az:#2a78d6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 "Public Sans",system-ui,sans-serif}
.w{max-width:1120px;margin:0 auto;padding:0 20px}
header{padding:56px 0 30px;border-bottom:4px solid var(--az);background:#fff}
h1{font-size:clamp(2.1rem,6vw,3.8rem);line-height:1.04;letter-spacing:-.02em;font-weight:800;margin:0 0 16px;max-width:19ch}
header p{margin:0;max-width:68ch;color:var(--mut)}
h2{font-size:1.5rem;margin:0 0 4px;letter-spacing:-.01em}
h3{font-size:1.05rem;margin:28px 0 10px}
main{padding:12px 0 40px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:8px;padding:14px 16px}
.v{font-size:1.9rem;font-weight:800;letter-spacing:-.02em;line-height:1.1}
.v small{font-size:.8rem;font-weight:600;color:var(--mut);margin-left:3px}
.n{font-size:.88rem;margin-top:6px;font-weight:600}
.o{font-size:.8rem;color:var(--mut);margin-top:3px;min-height:1.2em}
section{background:#fff;border:1px solid var(--line);border-radius:12px;padding:22px 20px 14px;margin-top:22px}
section>p{margin:0 0 6px;color:var(--mut);max-width:75ch}
footer{padding:0 0 40px;color:var(--mut);font-size:.85rem}
footer p{max-width:80ch}
@media (max-width:560px){header{padding-top:36px}section{padding:16px 10px 8px}}
</style></head><body>
<header><div class="w"><h1>Socioeconomia vs. Desempenho no ENEM</h1>
<p>Microdados do ENEM 2023 (INEP) cruzados com indicadores estaduais do IBGE e do PNUD. __AMOSTRA__</p></div></header>
<main class="w">
<h2 style="margin-top:28px">Indicadores-chave</h2>
__KPIS__
<section><h2>Nota por UF</h2><p>Escolha a prova no menu. As cores indicam a região e o valor aparece ao passar o mouse.</p>__G1__</section>
<section><h2>IDHM, renda e nota média</h2><p>Cada bolha é uma UF e o tamanho segue a população. Troque o eixo no menu. A correlação é entre 27 médias estaduais (ecológica) e não vale para alunos individuais.</p>__G2__</section>
<section><h2>Renda, escola e abstenção</h2><p>A nota considera só quem fez as cinco provas. A abstenção é calculada sobre todos os inscritos da amostra.</p>__G3__</section>
<section><h2>Distribuição das notas</h2><p>Percentual de alunos de cada rede em faixas de 25 pontos. Compare as redes em qualquer prova pelo menu.</p>__G4__</section>
__PERFIL__
__MODELOS__
</main>
<footer><div class="w"><p>Fontes: INEP (Microdados do ENEM 2023); IBGE (Censo 2022 e PNAD Contínua 2023, via SIDRA); PNUD, Ipea e FJP (Radar IDHM, 2023). A UF é a da prova, não a de residência. Os resultados mostram associação, não causa.</p></div></footer>
</body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", default=str(RAIZ / "docs" / "index.html"))
    ap.add_argument("--offline", action="store_true", help="embute o Plotly.js no HTML")
    args = ap.parse_args()

    df_ibge, df_enem = carregar_dados(True)
    df = etl(df_enem, df_ibge, verbose=False)
    df_pres = recorte_presentes(df)
    df_kpis, aux = calcular_kpis(df, df_pres, df_ibge)

    def div(fig):
        return fig.to_html(full_html=False, include_plotlyjs=False, config=CFG)

    plotly_js = (f"<script>{get_plotlyjs()}</script>" if args.offline else
                 f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js" charset="utf-8"></script>')
    dm = criar_features(df_pres)
    perfil = _secao("Escolaridade da mãe e renda",
                    "Nota final média por escolaridade da mãe e faixa de renda. Células com menos de "
                    f"{MIN_N} alunos ficam em branco; o mouse mostra o número de alunos.", div(grafico_mae_renda(dm)))
    perfil += _secao("Computador e internet em casa",
                     "Nota final média pelo número de computadores em casa, separando quem tem e quem não tem internet.",
                     div(grafico_recursos(dm)))

    modelos, arq_res = "", RAIZ / "resultados" / "metricas_entrega2.json"
    if arq_res.exists():
        res = json.loads(arq_res.read_text(encoding="utf-8"))
        lin, taxa = res["regressao_linear"]["teste"], res["base"]["taxa_alto_desempenho"] * 100
        modelos = _secao("Modelos preditivos: o que pesa na nota",
                         f"Regressão Linear sobre a nota final (R² = {_br(lin['R²'], 3)}, erro médio de {_br(lin['MAE'])} pts "
                         "no teste). As variáveis numéricas são padronizadas, então o coeficiente é o efeito de 1 desvio "
                         "padrão. Mostra associação, não causa.", div(grafico_coeficientes(res)))
        modelos += _secao("Quem passa de 700 pontos",
                          f"Classificação de alto desempenho ({_br(taxa)}% dos alunos), métricas no conjunto de teste. "
                          f"Modelo escolhido na Entrega 2: {html.escape(res['insights']['modelo_final'])}.",
                          div(grafico_modelos(res)))
    else:
        print(f"Aviso: {arq_res.relative_to(RAIZ)} não encontrado; a seção de modelos foi omitida "
              "(rode o notebook da Entrega 2 para gerá-lo).")

    pagina = (PAGINA.replace("__PLOTLY__", plotly_js)
              .replace("__AMOSTRA__", f"Amostra de {_br(len(df), 0)} concluintes do ensino médio, "
                                      f"{_br(len(df_pres), 0)} com as cinco provas.")
              .replace("__KPIS__", html_kpis(df_kpis))
              .replace("__G1__", div(grafico_uf(df_pres, aux["tab_uf"])))
              .replace("__G2__", div(grafico_idh(aux["tab_uf"])))
              .replace("__G3__", div(grafico_renda(df_pres, aux)))
              .replace("__G4__", div(grafico_distribuicao(df_pres)))
              .replace("__PERFIL__", perfil)
              .replace("__MODELOS__", modelos))

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(pagina, encoding="utf-8")
    print(f"Dashboard gerado: {saida} ({saida.stat().st_size / 1e3:,.0f} KB)")


if __name__ == "__main__":
    main()
