"""
Gera o dashboard estático "Socioeconomia vs. Desempenho no ENEM" (um único index.html).

Usa as mesmas funções dos notebooks (src.dados, src.kpis, src.features, src.estilo), calcula tudo em
Python e grava HTML + JavaScript puro, que o GitHub Pages serve sem backend. Todo número citado no
texto sai das variáveis calculadas aqui (df_kpis, aux, res), nunca digitado à mão.

Uso (na raiz do repositório):
    python gerar_dashboard.py                      # grava docs/index.html
    python gerar_dashboard.py --saida index.html   # outro caminho
    python gerar_dashboard.py --offline            # embute o Plotly.js (+4 MB), sem depender de CDN
"""

import argparse
import html
import json
import re
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
from plotly.offline import get_plotlyjs, get_plotlyjs_version

from src.dados import ORDEM_RENDA, carregar_dados, etl, recorte_presentes
from src.estilo import (AZUL, CINZA_GRADE, CORES_ESCOLA, CORES_MODELOS, CORES_RENDA, LARANJA, RAMPA_AZUL, TINTA,
                        TINTA_SECUNDARIA, VERDE_AGUA)
from src.features import criar_features
from src.kpis import calcular_kpis

RAIZ = Path(__file__).resolve().parent
REPO = "https://github.com/feijitos/cienciadedados1"
FONTE = "Archivo, system-ui, sans-serif"
# Sem zoom por arrasto, roda do mouse ou duplo clique: no celular o dedo tem que rolar a página.
# O hover/toque e os menus continuam funcionando.
CFG = {"responsive": True, "displaylogo": False, "displayModeBar": False, "scrollZoom": False,
       "doubleClick": False, "showTips": False}
PROVAS = {"NOTA_FINAL": "Nota final", "NU_NOTA_CN": "Ciências da Natureza", "NU_NOTA_CH": "Ciências Humanas",
          "NU_NOTA_LC": "Linguagens", "NU_NOTA_MT": "Matemática", "NU_NOTA_REDACAO": "Redação"}

# Superfície e tintas de apoio (claro). As versões escuras ficam em ESCURO, mais abaixo.
SUPERFICIE, EIXO = "#fcfcfb", "#c3c2b7"

# Regiões: cinco tons da mesma família da paleta de src/estilo.py, sem azul e laranja (que já
# significam privada/pública). Passaram no validador de cores em todos os pares (claro e escuro);
# como a separação para daltonismo fica entre 6 e 8, cada região também tem um símbolo próprio.
REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
CORES_REGIAO = {"Norte": "#008300", "Nordeste": "#eda100", "Centro-Oeste": "#e34948", "Sudeste": "#6250d6",
                "Sul": "#1baf7a"}
SIMBOLOS_REGIAO = {"Norte": "circle", "Nordeste": "diamond", "Centro-Oeste": "triangle-up", "Sudeste": "square",
                   "Sul": "hexagon"}

# Cor clara -> cor escura. O JavaScript da página troca as cores dos gráficos com este mapa.
ESCURO = {TINTA: "#f0efec", TINTA_SECUNDARIA: "#c3c2b7", CINZA_GRADE: "#2c2c2a", EIXO: "#383835",
          SUPERFICIE: "#1a1a19", AZUL: "#3987e5", LARANJA: "#d95926", VERDE_AGUA: "#199e70",
          CORES_REGIAO["Nordeste"]: "#c98500", CORES_REGIAO["Sudeste"]: "#9085e9"}


# --------------------------------------------------------------------------
# Formatação (padrão brasileiro)
# --------------------------------------------------------------------------
def _br(v, casas=1):
    """Número no padrão brasileiro (1.234,5)."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _num(v, casas=1):
    """Notas e pontos: tira o ',0' desnecessário (640, não 640,0)."""
    s = _br(v, casas)
    return s.rstrip("0").rstrip(",") if "," in s else s


def _pct(v):
    """Percentual: 2 casas abaixo de 10% (4,05%), 1 casa nos demais (24,8%)."""
    return _br(v, 2 if abs(v) < 10 else 1) + "%"


def _sinal(v):
    return ("+" if v > 0 else "−" if v < 0 else "") + _num(abs(v))


def _obs_br(s):
    """Converte números escritos em formato inglês nas observações dos KPIs (25,894 -> 25.894; 494.4 -> 494,4)."""
    s = re.sub(r"(\d),(\d{3})", r"\1§\2", str(s))
    s = re.sub(r"(\d)\.(\d)", r"\1,\2", s)
    return s.replace("§", ".").replace(" | ", "; ")


def _rgba(hex_, a):
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{a})"


# --------------------------------------------------------------------------
# Base dos gráficos
# --------------------------------------------------------------------------
def _base(fig, altura=440, t=20):
    fig.update_layout(
        template="none", height=altura, separators=",.", font=dict(family=FONTE, color=TINTA, size=13), dragmode=False,
        margin=dict(l=50, r=16, t=t, b=50), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", x=0, xanchor="left", y=-0.14, yanchor="top", font=dict(color=TINTA_SECUNDARIA)),
        hoverlabel=dict(bgcolor=SUPERFICIE, bordercolor=EIXO, font=dict(family=FONTE, color=TINTA, size=13)))
    eixo = dict(gridcolor=CINZA_GRADE, linecolor=EIXO, zeroline=False, tickfont=dict(color=TINTA_SECUNDARIA),
                title=dict(font=dict(color=TINTA_SECUNDARIA, size=12)), ticks="", fixedrange=True)
    fig.update_xaxes(**eixo)
    fig.update_yaxes(**eixo)
    return fig


def _menu(botoes):
    return [dict(type="dropdown", buttons=botoes, x=0, xanchor="left", y=1.0, yanchor="bottom", pad=dict(b=8),
                 bgcolor=SUPERFICIE, bordercolor=EIXO, font=dict(color=TINTA, size=12), showactive=True)]


def _responsivo(fig, movel, desktop, dados_movel=None, dados_desktop=None):
    """Guarda em layout.meta os ajustes que o JavaScript aplica em telas estreitas (e desfaz nas largas).
    `dados_*` é uma lista de (alterações, índices dos traços)."""
    fig.update_layout(meta=dict(movel=dict(layout=movel, data=dados_movel or []),
                                desktop=dict(layout=desktop, data=dados_desktop or [])))
    return fig


def _anot(texto, x, y, **kw):
    base = dict(text=texto, x=x, y=y, showarrow=False, font=dict(color=TINTA_SECUNDARIA, size=12))
    base.update(kw)
    return base


# --------------------------------------------------------------------------
# A) Território
# --------------------------------------------------------------------------
def grafico_uf(df_pres, tab_uf):
    """Pontos por UF (com haste até a média nacional), símbolo e cor por região; o menu troca a prova."""
    med = df_pres.groupby("UF")[list(PROVAS)].mean()
    nac = df_pres[list(PROVAS)].mean()
    regiao = tab_uf["REGIAO"]

    def estado(col):
        ordem = med[col].sort_values(ascending=False).index.tolist()
        m = float(nac[col])
        hx, hy = [], []
        for u in ordem:
            hx += [m, float(med.loc[u, col]), None]
            hy += [u, u, None]
        por_reg = {r: [u for u in ordem if regiao[u] == r] for r in REGIOES}
        xs = {r: med.loc[ufs, col].round(1).tolist() for r, ufs in por_reg.items()}
        cd = {r: (med.loc[ufs, col] - m).round(1).tolist() for r, ufs in por_reg.items()}
        extremos = []
        for u in (ordem[0], ordem[-1]):
            v = float(med.loc[u, col])
            dir_ = v >= m  # rótulo do lado oposto à haste
            extremos.append(dict(x=v, y=u, text=f"<b>{u}</b> {_num(v)}", xanchor="left" if dir_ else "right",
                                 xshift=9 if dir_ else -9))
        lo, hi = float(med[col].min()), float(med[col].max())
        faixa = [lo - (hi - lo) * 0.34, hi + (hi - lo) * 0.3]  # folga para os rótulos dos extremos (também no celular)
        return ordem, m, (hx, hy), por_reg, xs, cd, extremos, faixa

    ordem, m, (hx, hy), por_reg, xs, cd, ext, faixa = estado("NOTA_FINAL")
    fig = go.Figure()
    fig.add_scatter(x=hx, y=hy, mode="lines", line=dict(color=EIXO, width=2), hoverinfo="skip", showlegend=False)
    for r in REGIOES:
        fig.add_scatter(x=xs[r], y=por_reg[r], customdata=cd[r], mode="markers", name=r,
                        marker=dict(color=CORES_REGIAO[r], symbol=SIMBOLOS_REGIAO[r], size=12,
                                    line=dict(color=SUPERFICIE, width=1.5)),
                        hovertemplate="<b>%{y}</b><br>%{x:.1~f} pts<br>%{customdata:+.1~f} em relação à média nacional"
                                      "<extra>" + r + "</extra>")
    anots = [_anot(f"Média nacional: {_num(m)}", m, 1, yref="paper", yanchor="bottom", xanchor="left", xshift=4,
                   bgcolor=SUPERFICIE)]
    # fundo da cor do papel: nenhuma linha (grade ou haste) passa por cima do número; o JS troca a cor no tema escuro
    anots += [_anot(e.pop("text"), e.pop("x"), e.pop("y"), font=dict(color=TINTA, size=12), bgcolor=SUPERFICIE,
                    borderpad=2, **e) for e in ext]

    botoes = []
    for col, rotulo in PROVAS.items():
        o, mm, (bx, _), _, bxs, bcd, bext, bfaixa = estado(col)
        lay = {"yaxis.categoryarray": o, "xaxis.range": bfaixa, "shapes[0].x0": mm, "shapes[0].x1": mm, "annotations[0].x": mm,
               "annotations[0].text": f"Média nacional: {_num(mm)}", "xaxis.title.text": f"{rotulo} (média, pts)"}
        for i, e in enumerate(bext, start=1):
            lay.update({f"annotations[{i}].{k}": v for k, v in e.items()})
        hy_col = []
        for u in o:
            hy_col += [u, u, None]
        botoes.append(dict(label=rotulo, method="update", args=[
            {"x": [bx] + [bxs[r] for r in REGIOES], "y": [hy_col] + [[u for u in o if regiao[u] == r] for r in REGIOES],
             "customdata": [[]] + [bcd[r] for r in REGIOES]}, lay]))

    _base(fig, 27 * 23 + 120, t=56).update_layout(
        updatemenus=_menu(botoes), annotations=anots,
        shapes=[dict(type="line", x0=m, x1=m, y0=0, y1=1, yref="paper", line=dict(color=TINTA_SECUNDARIA, width=1, dash="dot"))],
        xaxis=dict(title=dict(text="Nota final (média, pts)"), range=faixa),
        yaxis=dict(type="category", categoryorder="array", categoryarray=ordem, autorange="reversed", showgrid=False,
                   tickfont=dict(color=TINTA, size=12)),
        legend=dict(y=-0.07), margin=dict(l=40, r=16, t=56, b=60))
    # no celular o rótulo da média entra no gráfico, à esquerda da linha (o topo à esquerda da média fica livre,
    # porque a primeira linha é a melhor UF); assim não sai pela borda nem fica sob o menu
    return _responsivo(fig, movel={"annotations[0].xanchor": "right", "annotations[0].xshift": -4, "annotations[0].font.size": 10,
                                   "annotations[0].yanchor": "top",
                                   "annotations[1].font.size": 10, "annotations[2].font.size": 10},
                       desktop={"annotations[0].xanchor": "left", "annotations[0].xshift": 4, "annotations[0].font.size": 12,
                                "annotations[0].yanchor": "bottom",
                                "annotations[1].font.size": 12, "annotations[2].font.size": 12})


def _colide(caixa, cx, cy, r):
    px, py = min(max(cx, caixa[0]), caixa[2]), min(max(cy, caixa[1]), caixa[3])
    return (px - cx) ** 2 + (py - cy) ** 2 < r ** 2


def _posicoes_rotulos(xs, ys, diam, larg=900.0, alt=370.0):
    """Escolhe, ponto a ponto, uma posição de rótulo que não cubra outros rótulos nem outras bolhas.
    Trabalha num plano de tamanho nominal (larg × alt px). Sem espaço livre, o rótulo fica só no hover (None)."""
    xs, ys, diam = (np.asarray(a, float) for a in (xs, ys, diam))

    def norm(v, n):
        lo, hi = v.min(), v.max()
        pad = (hi - lo) * 0.06 or 1
        return (v - lo + pad) / (hi - lo + 2 * pad) * n

    px, py = norm(xs, larg), norm(ys, alt)
    W, H = 24, 17
    cand = [("top center", 0, 1), ("bottom center", 0, -1), ("middle right", 1, 0), ("middle left", -1, 0),
            ("top right", .75, .75), ("top left", -.75, .75), ("bottom right", .75, -.75), ("bottom left", -.75, -.75)]
    caixas, out = [], [None] * len(xs)
    for i in np.argsort(-diam, kind="stable"):
        r = diam[i] / 2
        for nome, dx, dy in cand:
            cx, cy = px[i] + dx * (r + W / 2 + 2), py[i] + dy * (r + H / 2 + 1)
            b = (cx - W / 2, cy - H / 2, cx + W / 2, cy + H / 2)
            if b[0] < 0 or b[2] > larg or b[1] < 0 or b[3] > alt:
                continue
            if any(not (b[2] <= c[0] or b[0] >= c[2] or b[3] <= c[1] or b[1] >= c[3]) for c in caixas):
                continue
            if any(j != i and _colide(b, px[j], py[j], diam[j] / 2) for j in range(len(xs))):
                continue
            caixas.append(b)
            out[i] = nome
            break
    return out


def grafico_idh(tab_uf):
    """Bolhas (tamanho = população). O menu alterna entre IDHM e renda per capita no eixo x."""
    t = tab_uf.dropna(subset=["NOTA_MEDIA"]).copy()
    eixos = {"IDH_ESTADUAL": ("IDHM 2023", ".2f", ""), "RENDA_PER_CAPITA": ("Renda per capita 2023", ",.0f", "R$ ")}
    D = 38  # diâmetro (px) da maior bolha
    sizeref = 2 * t["POPULACAO"].max() / D ** 2
    diam = np.maximum(6, D * np.sqrt(t["POPULACAO"] / t["POPULACAO"].max()))
    subs = [(r, t[t["REGIAO"] == r]) for r in REGIOES]

    def estado(col):
        pos = dict(zip(t.index, _posicoes_rotulos(t[col], t["NOTA_MEDIA"], diam)))
        textos = [[u if pos[u] else "" for u in s.index] for _, s in subs]
        posicoes = [[pos[u] or "top center" for u in s.index] for _, s in subs]
        a, b = np.polyfit(t[col], t["NOTA_MEDIA"], 1)
        xr = np.array([t[col].min(), t[col].max()])
        r_ = float(np.corrcoef(t[col], t["NOTA_MEDIA"])[0, 1])
        return textos, posicoes, (xr.tolist(), (a * xr + b).tolist()), r_

    textos, posicoes, reta, r_idh = estado("IDH_ESTADUAL")
    fig = go.Figure()
    for (r, s), tx, ps in zip(subs, textos, posicoes):
        fig.add_scatter(
            x=s["IDH_ESTADUAL"], y=s["NOTA_MEDIA"].round(1), mode="markers+text", text=tx, textposition=ps,
            textfont=dict(size=11, color=TINTA_SECUNDARIA), name=r,
            customdata=[[float(a), float(b), int(c), u] for a, b, c, u in
                        zip(s["IDH_ESTADUAL"], s["RENDA_PER_CAPITA"], s["POPULACAO"], s.index)],
            marker=dict(size=s["POPULACAO"], sizemode="area", sizeref=sizeref, sizemin=6, color=CORES_REGIAO[r],
                        symbol=SIMBOLOS_REGIAO[r], opacity=0.88, line=dict(width=1.5, color=SUPERFICIE)),
            hovertemplate=("<b>%{customdata[3]}</b><br>Nota média: %{y:.1~f} pts<br>IDHM: %{customdata[0]:.3f}"
                           "<br>Renda per capita: R$ %{customdata[1]:,.0f}<br>População: %{customdata[2]:,.0f}"
                           "<extra>" + r + "</extra>"))
    fig.add_scatter(x=reta[0], y=reta[1], mode="lines", name="Tendência linear", showlegend=False,
                    line=dict(color=TINTA_SECUNDARIA, dash="dash", width=1.5), hoverinfo="skip")

    def anot_r(reta_, r_):
        return dict(x=reta_[0][1], y=reta_[1][1], text=f"r = {_br(r_, 2)}")

    botoes = []
    for col, (rotulo, fmt, pre) in eixos.items():
        tx, ps, rt, r_ = estado(col)
        a = anot_r(rt, r_)
        botoes.append(dict(label=f"{rotulo.split(' 2023')[0]} (r = {_br(r_, 2)})", method="update", args=[
            {"x": [s[col].tolist() for _, s in subs] + [rt[0]], "y": [s["NOTA_MEDIA"].round(1).tolist() for _, s in subs] + [rt[1]],
             "text": tx + [[]], "textposition": ps + ["top center"]},
            {"xaxis.title.text": rotulo, "xaxis.autorange": True, "xaxis.tickformat": fmt, "xaxis.tickprefix": pre,
             "annotations[0].x": a["x"], "annotations[0].y": a["y"], "annotations[0].text": a["text"]}]))
    a = anot_r(reta, r_idh)
    _base(fig, 520, t=46).update_layout(
        updatemenus=_menu(botoes), xaxis=dict(title=dict(text=eixos["IDH_ESTADUAL"][0]), tickformat=".2f"),
        yaxis_title="Nota final média da UF (pts)",
        annotations=[_anot(a["text"], a["x"], a["y"], xanchor="right", yanchor="bottom", yshift=8,
                           font=dict(color=TINTA, size=13))])
    n = len(REGIOES)
    return _responsivo(fig, movel={"margin.l": 44}, desktop={"margin.l": 50},
                       dados_movel=[({"mode": "markers"}, list(range(n)))],
                       dados_desktop=[({"mode": "markers+text"}, list(range(n)))])


# --------------------------------------------------------------------------
# B) Renda e escola
# --------------------------------------------------------------------------
def grafico_nota_renda(df_pres):
    """Nota média por faixa de renda, separando escola pública e privada (barras a partir de zero)."""
    g = df_pres.groupby(["FAIXA_RENDA", "TP_ESCOLA"], observed=True)["NOTA_FINAL"].agg(["mean", "size"])
    fig = go.Figure()
    for escola in ["Pública", "Privada"]:
        s = g.xs(escola, level="TP_ESCOLA").reindex(ORDEM_RENDA)
        fig.add_bar(x=ORDEM_RENDA, y=s["mean"].round(1), name=escola, marker=dict(color=CORES_ESCOLA[escola], line=dict(width=0)),
                    customdata=s["size"], text=[_num(v, 0) for v in s["mean"]], textposition="outside",
                    textfont=dict(color=TINTA_SECUNDARIA, size=12), cliponaxis=False,
                    hovertemplate="<b>%{x}</b><br>Média: %{y:.1~f} pts<br>Alunos: %{customdata:,.0f}<extra>" + escola + "</extra>")
    _base(fig, 400).update_layout(bargap=0.3, bargroupgap=0.08, legend=dict(y=-0.12),
                                  yaxis=dict(title=dict(text="Nota final média (pts)"), range=[0, float(g["mean"].max() * 1.12)]))
    return fig


def grafico_abstencao(aux, abst_geral):
    """Abstenção por faixa de renda, com a média geral marcada."""
    abst = aux["abst_renda"].reindex(ORDEM_RENDA)
    fig = go.Figure(go.Bar(x=ORDEM_RENDA, y=abst.round(2), marker=dict(color=[CORES_RENDA[f] for f in ORDEM_RENDA], line=dict(width=0)),
                           text=[_pct(v) for v in abst], textposition="outside", cliponaxis=False,
                           textfont=dict(color=TINTA, size=13), showlegend=False,
                           hovertemplate="<b>%{x}</b><br>%{y:.1f}% faltaram<extra></extra>"))
    _base(fig, 400).update_layout(
        bargap=0.35, yaxis=dict(title=dict(text="% dos inscritos que faltaram"), range=[0, float(abst.max() * 1.25)], ticksuffix="%"),
        shapes=[dict(type="line", xref="paper", x0=0, x1=1, y0=abst_geral, y1=abst_geral,
                     line=dict(color=TINTA_SECUNDARIA, width=1, dash="dot"))],
        annotations=[_anot(f"Média geral: {_pct(abst_geral)}", 1, abst_geral, xref="paper", xanchor="right",
                           yanchor="bottom", yshift=2)])
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
                        line=dict(color=CORES_ESCOLA[e], width=2), fillcolor=_rgba(CORES_ESCOLA[e], 0.16),
                        hovertemplate="%{y:.2f}% dos alunos<extra>" + e + "</extra>")
    botoes = [dict(label=rot, method="restyle", args=[{"y": dens(col)}]) for col, rot in PROVAS.items()]
    _base(fig, 420, t=46).update_layout(
        updatemenus=_menu(botoes), xaxis=dict(title=dict(text="Nota (pts), faixas de 25 pontos"), range=[200, 950]),
        yaxis=dict(title=dict(text="% dos alunos da rede"), ticksuffix="%"), hovermode="x unified",
        legend=dict(y=-0.22), margin=dict(b=70),
        shapes=[dict(type="line", x0=700, x1=700, y0=0, y1=1, yref="paper", line=dict(color=TINTA_SECUNDARIA, width=1, dash="dot"))],
        annotations=[_anot("700 pontos", 700, 1, yref="paper", xanchor="left", yanchor="top", xshift=4)])
    return fig


# --------------------------------------------------------------------------
# C) Família e casa
# --------------------------------------------------------------------------
MIN_N = 30  # células com menos alunos ficam em branco (evita médias instáveis)
ESC_ROTULOS = ["Nunca estudou", "Fund. 1 incompleto", "Fund. 1 completo", "Fund. 2 completo",
               "Médio completo", "Superior completo", "Pós-graduação"]
COMP_ROTULOS = ["0", "1", "2", "3", "4 ou mais"]


def tabela_mae_renda(dm):
    g = dm.dropna(subset=["ESC_MAE"]).groupby(["ESC_MAE", "FAIXA_RENDA"])["NOTA_FINAL"].agg(["mean", "size"])
    media = g["mean"].unstack().reindex(index=range(7), columns=ORDEM_RENDA)
    n = g["size"].unstack().reindex(index=range(7), columns=ORDEM_RENDA).fillna(0)
    return media.where(n >= MIN_N), n


TEXTO_CLARO, TEXTO_ESCURO = "#ffffff", "#141414"  # fora do mapa ESCURO: as células não mudam de cor com o tema


def _luminancia(hex_):
    """Luminância relativa (WCAG) de uma cor #rrggbb."""
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _cor_na_escala(escala, t):
    """Cor (#rrggbb) na posição t ∈ [0, 1] de uma escala [[pos, cor], ...], interpolando em RGB como o Plotly."""
    for (p0, c0), (p1, c1) in zip(escala, escala[1:]):
        if t <= p1:
            f = 0 if p1 == p0 else (t - p0) / (p1 - p0)
            rgb = [round(int(c0[i:i + 2], 16) + f * (int(c1[i:i + 2], 16) - int(c0[i:i + 2], 16))) for i in (1, 3, 5)]
            return "#" + "".join(f"{v:02x}" for v in rgb)
    return escala[-1][1]


def _texto_contraste(fundo):
    """Texto claro ou escuro, o que tiver mais contraste com o fundo."""
    l = _luminancia(fundo)
    contraste = {TEXTO_CLARO: 1.05 / (l + 0.05), TEXTO_ESCURO: (l + 0.05) / (_luminancia(TEXTO_ESCURO) + 0.05)}
    return max(contraste, key=contraste.get)


def grafico_mae_renda(media, n):
    """Mapa de calor: nota média por escolaridade da mãe × faixa de renda.
    Os números são anotações por célula, com a cor do texto escolhida pela luminância da cor da célula."""
    escala = [[0, RAMPA_AZUL[0]], [0.5, RAMPA_AZUL[1]], [1, RAMPA_AZUL[2]]]
    z = media.values.round(1)
    zmin, zmax = float(np.nanmin(z)), float(np.nanmax(z))
    rotulos = []
    for i, esc in enumerate(ESC_ROTULOS):
        for j, faixa in enumerate(ORDEM_RENDA):
            if np.isnan(z[i, j]):
                continue
            fundo = _cor_na_escala(escala, (z[i, j] - zmin) / (zmax - zmin))
            rotulos.append(dict(x=faixa, y=esc, text=_num(media.values[i, j], 0), showarrow=False,
                                font=dict(color=_texto_contraste(fundo), size=13)))
    fig = go.Figure(go.Heatmap(
        z=z, x=ORDEM_RENDA, y=ESC_ROTULOS, customdata=n.values, hoverongaps=False, colorscale=escala,
        zmin=zmin, zmax=zmax, colorbar=dict(title=dict(text="pts"), thickness=10, outlinewidth=0,
                                            tickfont=dict(color=TINTA_SECUNDARIA)), xgap=2, ygap=2,
        hovertemplate="Mãe: %{y}<br>Renda: %{x}<br>Nota média: %{z:.1~f} pts<br>Alunos: %{customdata:,.0f}<extra></extra>"))
    _base(fig, 440).update_layout(margin=dict(l=130, r=16, t=10, b=40), xaxis=dict(side="bottom", showgrid=False),
                                  yaxis=dict(showgrid=False), annotations=rotulos)
    return _responsivo(fig, movel={"margin.l": 112, "font.size": 11}, desktop={"margin.l": 130, "font.size": 13},
                       dados_movel=[({"showscale": False}, [0])], dados_desktop=[({"showscale": True}, [0])])


def tabela_recursos(dm):
    g = dm.dropna(subset=["N_COMPUTADORES"]).groupby(["N_COMPUTADORES", "TEM_INTERNET"])["NOTA_FINAL"].agg(["mean", "size"])
    g["mean"] = g["mean"].where(g["size"] >= MIN_N)
    return g


def grafico_recursos(g):
    """Nota média por nº de computadores em casa, com e sem internet."""
    fig = go.Figure()
    for flag, nome, cor in [(0, "Sem internet", RAMPA_AZUL[0]), (1, "Com internet", RAMPA_AZUL[2])]:
        s = g.xs(flag, level="TEM_INTERNET").reindex(range(5))
        fig.add_bar(x=COMP_ROTULOS, y=s["mean"].round(1), name=nome, marker=dict(color=cor, line=dict(width=0)),
                    customdata=s["size"].fillna(0), hovertemplate="<b>%{x} computador(es)</b><br>Média: %{y:.1~f} pts"
                    "<br>Alunos: %{customdata:,.0f}<extra>" + nome + "</extra>")
    _base(fig, 400).update_layout(bargap=0.3, bargroupgap=0.08, xaxis=dict(type="category", title=dict(text="Computadores em casa")),
                                  yaxis=dict(title=dict(text="Nota final média (pts)"), rangemode="tozero"),
                                  legend=dict(y=-0.2))
    return fig


# --------------------------------------------------------------------------
# D) Modelos
# --------------------------------------------------------------------------
NOMES_NUM = {"LOG_RENDA_PC": "Renda per capita (log)", "N_MORADORES": "Moradores no domicílio",
             "ESC_MAE": "Escolaridade da mãe", "ESC_PAI": "Escolaridade do pai", "N_COMPUTADORES": "Computadores em casa",
             "TEM_INTERNET": "Internet em casa", "ATRASO_ESCOLAR": "Atraso escolar (19 anos ou mais)",
             "IDH_ESTADUAL": "IDHM do estado"}
NOMES_CAT = {"TP_ESCOLA": "Escola", "REGIAO": "Região", "FAIXA_RENDA": "Faixa de renda", "SEXO": "Sexo", "COR_RACA": "Cor/raça"}


def nomes_coeficientes(coefs, dm):
    """Traduz os nomes técnicos do One-Hot: devolve {nome técnico: (rótulo do eixo, rótulo curto)}.
    A categoria de referência é a que não aparece entre os coeficientes."""
    presentes = {}
    for k in coefs:
        for cat in NOMES_CAT:
            if k.startswith(cat + "_"):
                presentes.setdefault(cat, set()).add(k[len(cat) + 1:])
    refs = {cat: sorted(set(dm[cat].dropna().astype(str).unique()) - niveis) for cat, niveis in presentes.items()}
    out = {}
    for k in coefs:
        if k in NOMES_NUM:
            out[k] = (NOMES_NUM[k], NOMES_NUM[k])
            continue
        cat = next(c for c in NOMES_CAT if k.startswith(c + "_"))
        nivel, ref = k[len(cat) + 1:], ", ".join(refs[cat])
        if cat != "REGIAO":
            nivel, ref = nivel.lower(), ref.lower()
        if cat == "TP_ESCOLA":
            curto = f"Escola {nivel}"
        else:
            curto = f"{NOMES_CAT[cat]}: {nivel}"
        out[k] = (f"{curto}<br><span style='font-size:11px'>ref.: {ref}</span>", f"{curto} (ref.: {ref})")
    return out


def grafico_coeficientes(res, nomes):
    """Coeficientes da Regressão Linear (pontos na nota final, mantidas as demais variáveis)."""
    itens = sorted(res["regressao_linear"]["coeficientes"].items(), key=lambda kv: kv[1])
    rot = [nomes[k][0] for k, _ in itens]
    vals = [v for _, v in itens]
    fig = go.Figure(go.Bar(x=vals, y=rot, orientation="h", marker=dict(color=[AZUL if v > 0 else LARANJA for v in vals], line=dict(width=0)),
                           text=[_sinal(v) for v in vals], textposition="outside", cliponaxis=False,
                           textfont=dict(color=TINTA_SECUNDARIA, size=11), customdata=[nomes[k][1] for k, _ in itens],
                           hovertemplate="<b>%{customdata}</b><br>%{x:+.1f} pts<extra></extra>"))
    lim = max(abs(v) for v in vals) * 1.18
    _base(fig, 31 * len(vals) + 70).update_layout(
        bargap=0.28, margin=dict(l=10, r=16, t=10, b=46),
        xaxis=dict(title=dict(text="Associação com a nota final (pts)"), range=[-lim, lim], zeroline=True,
                   zerolinecolor=EIXO, zerolinewidth=1),
        yaxis=dict(automargin=True, showgrid=False, tickfont=dict(color=TINTA, size=12)))
    return _responsivo(fig, movel={"yaxis.tickfont.size": 10, "xaxis.range": [-lim * 1.45, lim * 1.45]},
                       desktop={"yaxis.tickfont.size": 12, "xaxis.range": [-lim, lim]})


def grafico_modelos(res):
    """Métricas dos três classificadores no conjunto de teste, com a taxa base marcada à direita."""
    metricas = ["Precisão", "Recall", "F1", "ROC-AUC"]
    taxa = res["base"]["taxa_alto_desempenho"]
    fig = go.Figure()
    for nome, d in res["classificacao"].items():
        fig.add_bar(x=metricas, y=[round(d["teste"][m], 3) for m in metricas], name=nome,
                    marker=dict(color=CORES_MODELOS.get(nome), line=dict(width=0)),
                    text=[_br(d["teste"][m], 2) for m in metricas], textposition="outside", cliponaxis=False,
                    textfont=dict(color=TINTA_SECUNDARIA, size=11),
                    hovertemplate="<b>%{x}</b>: %{y:.3f}<extra>" + nome + "</extra>")
    _base(fig, 420).update_layout(
        bargap=0.25, bargroupgap=0.08, yaxis=dict(range=[0, 1.05], title=dict(text="valor no conjunto de teste"), tickformat=".1f"),
        margin=dict(l=50, r=96, t=10, b=50), legend=dict(y=-0.12),
        shapes=[dict(type="line", xref="paper", x0=0, x1=1, y0=taxa, y1=taxa, line=dict(color=TINTA_SECUNDARIA, width=1, dash="dot"))],
        annotations=[_anot(f"taxa base<br>{_pct(taxa * 100)}", 1, taxa, xref="paper", xanchor="left", yanchor="middle",
                           xshift=6, align="left")])
    return _responsivo(fig, movel={"margin.r": 70, "annotations[0].font.size": 10},
                       desktop={"margin.r": 96, "annotations[0].font.size": 12})


# --------------------------------------------------------------------------
# Página
# --------------------------------------------------------------------------
def _figura(titulo, sub, div, classe=""):
    return (f'<figure class="graf {classe}"><figcaption><h3>{titulo}</h3><p>{sub}</p></figcaption>'
            f'<div class="plot">{div}</div></figure>')


def _secao(id_, num, cor, titulo, dek, conteudo):
    return (f'<section id="{id_}" class="secao" aria-labelledby="t-{id_}">'
            f'<header class="sec-cab"><span class="bola bola-g" data-c="{cor}" aria-hidden="true">{num}</span>'
            f'<div><h2 id="t-{id_}">{titulo}</h2><p>{dek}</p></div></header>{conteudo}</section>')


def _fmt_kpi(v, un):
    if un == "%":
        return _pct(v), ""
    if un == "alunos":
        return _br(v, 0), " alunos"
    if un == "r":
        return _br(v, 2), ""
    if un == "razão":
        return _br(v, 2), "×"
    if un == "índice 0–16":
        return _br(v, 2), " (índice 0–16)"
    if un == "insc./100k":
        return _num(v), " por 100 mil hab."
    return _num(v), f" {un}"


def html_kpis(df_kpis):
    blocos = []
    for i, (eixo, g) in enumerate(df_kpis.groupby("Eixo", sort=True)):
        letra, nome = eixo.split(") ", 1)
        linhas = ""
        for r in g.to_dict("records"):
            valor, un = _fmt_kpi(r["Valor"], r["Unidade"])
            obs = _obs_br(r["Observação"]) if str(r["Observação"]).strip() else ""
            linhas += (f'<tr><th scope="row"><span class="kpi-i">{r["#"]}</span>{html.escape(r["KPI"])}</th>'
                       f'<td class="kpi-v">{valor}<small>{html.escape(un)}</small></td>'
                       f'<td class="kpi-o">{html.escape(obs)}</td></tr>')
        blocos.append(f'<details class="eixo"{" open" if i == 0 else ""}><summary>'
                      f'<span class="bola" aria-hidden="true">{html.escape(letra)}</span>'
                      f'<span class="eixo-nome">Eixo {html.escape(letra)}: {html.escape(nome)}</span>'
                      f'<span class="eixo-n">{len(g)} indicadores</span></summary>'
                      f'<table class="kpis"><tbody>{linhas}</tbody></table></details>')
    return "".join(blocos)


CSS = """
:root{--papel:#fcfcfb;--tinta:#0b0b0b;--suave:#52514e;--linha:#e1e0d9;--linha-f:#c3c2b7;--foco:#2a78d6;
--c-azul:#2f62b0;--c-amarelo:#f2c12e;--c-branco:#ffffff;--c-rosa:#e48bb1;--c-cinza:#9a9d9f;--marca:#0b0b0b;
--f-tit:"Archivo",system-ui,sans-serif;--f-txt:"Source Serif 4",Georgia,serif;color-scheme:light}
@media (prefers-color-scheme:dark){:root{--papel:#1a1a19;--tinta:#f0efec;--suave:#c3c2b7;--linha:#2c2c2a;
--linha-f:#47463f;--foco:#86b6ef;--c-azul:#4f82cf;--c-amarelo:#e0b12a;--c-branco:#1a1a19;--c-rosa:#d47ba1;
--c-cinza:#7d8083;--marca:#f0efec;color-scheme:dark}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
@media (prefers-reduced-motion:no-preference){html{scroll-behavior:smooth}}
body{margin:0;background:var(--papel);color:var(--tinta);font:17px/1.6 var(--f-txt);overflow-wrap:break-word}
a{color:inherit;text-decoration-thickness:1px;text-underline-offset:3px}
:focus-visible{outline:3px solid var(--foco);outline-offset:3px;border-radius:2px}
.w{max-width:1080px;margin:0 auto;padding:0 24px}
h1,h2,h3,summary,.menu,.num{font-family:var(--f-tit)}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}

/* bolinhas do cartão-resposta */
.bola{display:inline-grid;place-items:center;flex:none;width:1.6em;height:1.6em;border-radius:50%;
border:1.5px solid var(--tinta);font:600 .8rem/1 var(--f-tit);color:var(--tinta)}
.bola[data-c]{border-color:transparent;color:#0b0b0b}
.bola[data-c=azul]{background:var(--c-azul);color:#fff}.bola[data-c=amarelo]{background:var(--c-amarelo)}
.bola[data-c=branco]{background:var(--c-branco);border-color:var(--tinta);color:var(--tinta)}
.bola[data-c=rosa]{background:var(--c-rosa)}.bola[data-c=cinza]{background:var(--c-cinza)}
.bola-g{width:2.4rem;height:2.4rem;font-size:1.05rem;font-weight:700}

/* menu fixo */
.menu{position:sticky;top:0;z-index:10;background:var(--papel);border-bottom:1px solid var(--linha)}
.menu .w{display:flex;align-items:center;gap:20px;height:56px}
.marca{font-weight:700;font-stretch:85%;text-decoration:none;white-space:nowrap;font-size:1rem}
.menu ol{display:flex;gap:4px;list-style:none;margin:0 0 0 auto;padding:0;overflow-x:auto;scrollbar-width:none}
.menu ol::-webkit-scrollbar{display:none}
.menu a.it{display:flex;align-items:center;gap:8px;padding:6px 10px;text-decoration:none;font-size:.9rem;
color:var(--suave);white-space:nowrap;border-radius:6px}
.menu a.it:hover,.menu a.it[aria-current=true]{color:var(--tinta)}
.menu a.it[aria-current=true] .bola{box-shadow:0 0 0 2px var(--papel),0 0 0 3.5px var(--tinta)}
.menu .bola{font-size:.72rem}

/* abertura */
.abertura{padding:64px 0 40px;border-bottom:1px solid var(--linha)}
.abertura h1{font-size:clamp(2rem,1.1rem + 3.4vw,3.7rem);line-height:1.02;font-weight:800;font-stretch:78%;
letter-spacing:-.015em;margin:0 0 22px;max-width:21ch;text-wrap:balance}
.abertura .dek{font-size:1.15rem;color:var(--suave);max-width:60ch;margin:0}
.gabarito{list-style:none;margin:44px 0 0;padding:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));
border-top:2px solid var(--tinta)}
.gabarito li{padding:18px 20px 4px 0;min-width:0}
.gabarito li+li{padding-left:20px;border-left:1px solid var(--linha)}
.gabarito a{display:block;text-decoration:none}
.gabarito a:hover .leg{text-decoration:underline}
.gabarito .topo{display:flex;align-items:center;gap:10px;color:var(--suave);font:500 .85rem/1.2 var(--f-tit)}
.gabarito .bola{width:1.35em;height:1.35em;font-size:.72rem;background:var(--marca);border-color:var(--marca);color:var(--papel)}
.num{display:block;font-size:clamp(2.1rem,1.4rem + 2vw,3rem);font-weight:750;font-stretch:88%;line-height:1;
letter-spacing:-.02em;margin:14px 0 8px;font-variant-numeric:lining-nums}
.num small{font-size:.42em;font-weight:600;letter-spacing:0;margin-left:4px;color:var(--suave)}
.leg{display:block;font-size:.95rem;line-height:1.45;color:var(--suave)}

/* seções e gráficos */
.secao{padding:56px 0 8px;border-bottom:1px solid var(--linha);scroll-margin-top:56px}
.sec-cab{display:flex;gap:16px;align-items:flex-start;margin-bottom:12px}
.sec-cab h2{font-size:clamp(1.6rem,1.2rem + 1.4vw,2.2rem);line-height:1.1;font-weight:750;font-stretch:85%;margin:2px 0 8px}
.sec-cab p{margin:0;max-width:64ch;color:var(--suave)}
.graf{margin:36px 0 28px;min-width:0}
.graf figcaption{max-width:70ch}
.graf h3{font-size:1.28rem;line-height:1.25;font-weight:650;margin:0 0 6px;text-wrap:balance}
.graf figcaption p{margin:0 0 10px;font-size:.95rem;color:var(--suave)}
.plot{min-width:0}
.plot,.plot .js-plotly-plot,.plot .js-plotly-plot *{touch-action:pan-y}
.par{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:40px}
.par .graf{margin-bottom:20px}

/* indicadores */
.eixo{border-top:1px solid var(--linha)}
.eixo:last-child{border-bottom:1px solid var(--linha)}
.eixo summary{display:flex;align-items:center;gap:12px;padding:16px 0;cursor:pointer;list-style:none;font-size:1.08rem;font-weight:600}
.eixo summary::-webkit-details-marker{display:none}
.eixo summary::after{content:"";margin-left:8px;width:9px;height:9px;border-right:2px solid var(--suave);
border-bottom:2px solid var(--suave);transform:rotate(45deg) translateY(-3px)}
.eixo[open] summary::after{transform:rotate(-135deg) translateY(-2px)}
.eixo[open] summary .bola{background:var(--marca);border-color:var(--marca);color:var(--papel)}
.eixo-n{margin-left:auto;font-size:.85rem;font-weight:500;color:var(--suave)}
.kpis{width:100%;border-collapse:collapse;margin:0 0 20px;font-size:.95rem}
.kpis th,.kpis td{text-align:left;vertical-align:baseline;padding:11px 12px 11px 0;border-top:1px solid var(--linha)}
.kpis th{font-weight:400;width:46%}
.kpi-i{display:inline-block;min-width:2.2em;color:var(--suave);font:500 .8rem var(--f-tit)}
.kpi-v{font:700 1.2rem/1.2 var(--f-tit);white-space:nowrap;font-variant-numeric:tabular-nums}
.kpi-v small{font-size:.75rem;font-weight:500;color:var(--suave);margin-left:2px}
.kpi-o{color:var(--suave);font-size:.88rem}

footer{padding:40px 0 56px;color:var(--suave);font-size:.92rem}
footer p{max-width:72ch;margin:0 0 10px}

@media (max-width:860px){.gabarito{grid-template-columns:repeat(2,minmax(0,1fr))}
.gabarito li:nth-child(3){padding-left:0;border-left:0}
.gabarito li:nth-child(n+3){border-top:1px solid var(--linha)}
.par{grid-template-columns:minmax(0,1fr);gap:0}}
@media (max-width:640px){.w{padding:0 16px}.menu .w{gap:10px}.menu .rot{position:absolute;width:1px;height:1px;
overflow:hidden;clip:rect(0 0 0 0)}.menu a.it{padding:6px 5px}
.abertura{padding:40px 0 28px}.gabarito li,.gabarito li+li{padding:16px 12px 4px 0;border-left:0}
.gabarito li:nth-child(even){padding-left:12px;border-left:1px solid var(--linha)}
.secao{padding-top:40px}.bola-g{width:2rem;height:2rem;font-size:.9rem}
.kpis tr{display:grid;grid-template-columns:1fr auto;border-top:1px solid var(--linha);padding:10px 0}
.kpis th,.kpis td{border:0;padding:0}.kpis th{width:auto}.kpi-v{text-align:right;padding-left:12px}
.kpi-o{grid-column:1/-1;padding-top:2px}.eixo-n{display:none}.eixo summary::after{margin-left:auto}}
"""

JS = """
(function(){
var ESCURO=__ESCURO__;
var escuro=matchMedia('(prefers-color-scheme: dark)'), movel=matchMedia('(max-width: 640px)');
function graficos(){return [].slice.call(document.querySelectorAll('.js-plotly-plot'));}
function hex2(n){return ('0'+n.toString(16)).slice(-2);}
function mapear(s){
  if(typeof s!=='string')return null; var t=s.trim().toLowerCase();
  if(/^#[0-9a-f]{6}$/.test(t))return ESCURO[t]||null;
  var m=t.match(/^rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?\\)$/);
  if(m){var d=ESCURO['#'+hex2(+m[1])+hex2(+m[2])+hex2(+m[3])];
    if(d)return 'rgba('+parseInt(d.slice(1,3),16)+','+parseInt(d.slice(3,5),16)+','+parseInt(d.slice(5,7),16)+','+(m[4]||1)+')';}
  return null;}
var PULAR={meta:1,args:1,args2:1,template:1,x:1,y:1,z:1,customdata:1,text:1,hovertemplate:1,colorscale:1};
function coletar(o,p,out){
  if(o==null)return;
  if(typeof o==='string'){var d=mapear(o);if(d)out[p]=[o,d];return;}
  if(ArrayBuffer.isView(o))return;
  if(Array.isArray(o)){
    if(o.length&&typeof o[0]==='string'){var mud=false,n=o.map(function(s){var d=mapear(s);if(d){mud=true;return d;}return s;});
      if(mud)out[p]=[o.slice(),n];return;}
    o.forEach(function(v,i){if(v&&typeof v==='object')coletar(v,p+'['+i+']',out);});return;}
  if(typeof o==='object')for(var k in o){if(k[0]==='_'||PULAR[k])continue;coletar(o[k],p?p+'.'+k:k,out);}}
function preparar(gd){
  if(gd._temas)return gd._temas;
  var L={},lay={claro:{},escuro:{}};coletar(gd.layout,'',L);
  for(var p in L){lay.claro[p]=L[p][0];lay.escuro[p]=L[p][1];}
  var dat=gd.data.map(function(tr){var o={},c={},e={};coletar(tr,'',o);for(var p in o){c[p]=[o[p][0]];e[p]=[o[p][1]];}return {claro:c,escuro:e};});
  return gd._temas={lay:lay,dat:dat,atual:'claro'};}
function tema(gd){
  var t=preparar(gd),nome=escuro.matches?'escuro':'claro'; if(t.atual===nome)return; t.atual=nome;
  t.dat.forEach(function(d,i){if(Object.keys(d[nome]).length)Plotly.restyle(gd,d[nome],[i]);});
  if(Object.keys(t.lay[nome]).length)Plotly.relayout(gd,t.lay[nome]);}
function tamanho(gd){
  var m=gd.layout&&gd.layout.meta,k=movel.matches?'movel':'desktop'; if(!m||!m[k]||gd._tam===k)return; gd._tam=k;
  (m[k].data||[]).forEach(function(par){Plotly.restyle(gd,par[0],par[1]);});
  if(m[k].layout&&Object.keys(m[k].layout).length)Plotly.relayout(gd,m[k].layout);}
function tudo(){graficos().forEach(function(gd){tamanho(gd);tema(gd);});}
window.addEventListener('load',function(){
  tudo();
  if(document.fonts&&document.fonts.ready)document.fonts.ready.then(function(){graficos().forEach(function(gd){Plotly.Plots.resize(gd);});});
});
(escuro.addEventListener?escuro.addEventListener('change',tudo):escuro.addListener(tudo));
(movel.addEventListener?movel.addEventListener('change',tudo):movel.addListener(tudo));
var links=[].slice.call(document.querySelectorAll('.menu a.it'));
if('IntersectionObserver' in window){
  var obs=new IntersectionObserver(function(es){es.forEach(function(e){if(!e.isIntersecting)return;
    links.forEach(function(a){a.setAttribute('aria-current',a.getAttribute('href')==='#'+e.target.id?'true':'false');});});},
    {rootMargin:'-45% 0px -50% 0px'});
  document.querySelectorAll('.secao').forEach(function(s){obs.observe(s);});}
})();
"""

PAGINA = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ENEM 2023: renda, escola e nota</title>
<meta name="description" content="__DESCRICAO__">
<meta name="color-scheme" content="light dark">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wdth,wght@62..125,400..800&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap" rel="stylesheet">
__PLOTLY__
<style>__CSS__</style></head><body>
<nav class="menu" aria-label="Seções"><div class="w">
<a class="marca" href="#inicio">ENEM 2023 × IBGE</a>
<ol>__MENU__</ol></div></nav>
<main>
<section id="inicio" class="abertura"><div class="w">
<h1>__MANCHETE__</h1>
<p class="dek">__DEK__</p>
<ol class="gabarito">__DESTAQUES__</ol>
</div></section>
<div class="w">
__SECOES__
</div>
</main>
<footer><div class="w">
<p>Fontes: INEP (Microdados do ENEM 2023); IBGE (Censo 2022 e PNAD Contínua 2023, via SIDRA); PNUD, Ipea e FJP (Radar IDHM, 2023). A UF é a da prova, não a de residência. Os resultados mostram associação, não causa.</p>
<p>__AMOSTRA__ Todos os números desta página são calculados pelo script <code>gerar_dashboard.py</code> com as mesmas funções dos notebooks.</p>
<p>Código, notebooks e dados: <a href="__REPO__">github.com/feijitos/cienciadedados1</a>.</p>
</div></footer>
<script>__JS__</script>
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
    dm = criar_features(df_pres)
    kpi = df_kpis.set_index("#")["Valor"]

    def div(fig):
        return fig.to_html(full_html=False, include_plotlyjs=False, config=CFG)

    plotly_js = (f"<script>{get_plotlyjs()}</script>" if args.offline else
                 f'<script src="https://cdn.plot.ly/plotly-{get_plotlyjs_version()}.min.js" charset="utf-8"></script>')

    # ---------- números usados no texto (todos calculados) ----------
    esc = aux["med_escola"]
    dif_escola = esc["Privada"] - esc["Pública"]
    abst = aux["abst_renda"]
    r_idh = aux["corr_idh"]
    n_ufs = int(aux["tab_uf"]["NOTA_MEDIA"].notna().sum())
    baixa_600 = kpi[18]
    media_uf = aux["media_uf"]
    melhor, pior = media_uf.idxmax(), media_uf.idxmin()
    reg_med = df_pres.groupby("REGIAO")["NOTA_FINAL"].mean().sort_values(ascending=False)
    forca = "forte" if abs(r_idh) >= 0.7 else "moderada" if abs(r_idh) >= 0.4 else "fraca"
    r_renda = aux["tab_uf"]["RENDA_PER_CAPITA"].corr(aux["tab_uf"]["NOTA_MEDIA"])
    acima700 = df_pres.groupby("TP_ESCOLA")["NOTA_FINAL"].apply(lambda s: (s > 700).mean() * 100)

    manchete = (f"No ENEM 2023, os alunos da escola privada tiraram {_num(dif_escola)} pontos a mais que os da pública, e só "
                f"{_pct(baixa_600)} dos alunos de baixa renda passaram de 600")
    dek = (f"Cruzamos as notas de {_br(len(df_pres), 0)} concluintes do ensino médio que fizeram as cinco provas "
           f"(numa amostra de {_br(len(df), 0)} inscritos nos microdados do INEP) com indicadores dos estados do IBGE "
           "e do PNUD. A desigualdade aparece na escola, na renda da família e no estado onde o aluno faz a prova.")

    destaques = [
        ("renda", 2, "Escola", f'{_sinal(dif_escola)}<small>pts</small>',
         f"de vantagem média da escola privada ({_num(esc['Privada'])}) sobre a pública ({_num(esc['Pública'])})"),
        ("renda", 2, "Abstenção", _pct(abst["Baixa Renda"]),
         f"dos inscritos de baixa renda faltaram à prova, contra {_pct(abst['Alta Renda'])} na alta renda"),
        ("territorio", 1, "Território", f"r = {_br(r_idh, 2)}",
         f"é a correlação entre o IDHM e a nota média dos {n_ufs} estados"),
        ("renda", 2, "Baixa renda", _pct(baixa_600), "dos alunos de baixa renda passaram de 600 pontos na nota final"),
    ]
    html_dest = "".join(
        f'<li><a href="#{a}"><span class="topo"><span class="bola" aria-hidden="true">{chr(65 + i)}</span>{rot}</span>'
        f'<strong class="num">{n}</strong><span class="leg">{leg}</span></a></li>'
        for i, (a, _, rot, n, leg) in enumerate(destaques))

    # ---------- seção 1: território ----------
    s1 = _figura(f"{reg_med.index[0]} e {reg_med.index[1]} lideram; {pior} tem a menor média, "
                 f"{_num(media_uf.max() - media_uf.min())} pontos atrás de {melhor}",
                 "Nota média de cada UF, ligada à média nacional. Use o menu para ver cada prova; o título se refere à "
                 "nota final. Cor e símbolo indicam a região.", div(grafico_uf(df_pres, aux["tab_uf"])))
    s1 += _figura(f"Quanto maior o IDHM do estado, maior a nota média: correlação {forca} (r = {_br(r_idh, 2)})",
                  f"Cada bolha é uma UF e o tamanho segue a população. Com a renda per capita no eixo, r = {_br(r_renda, 2)}. "
                  f"A correlação é entre {n_ufs} médias estaduais e não vale para alunos individuais. Siglas que não cabem "
                  "aparecem ao passar o mouse.", div(grafico_idh(aux["tab_uf"])))

    # ---------- seção 2: renda e escola ----------
    g_er = df_pres.groupby(["FAIXA_RENDA", "TP_ESCOLA"], observed=True)["NOTA_FINAL"].mean().unstack()
    gaps = (g_er["Privada"] - g_er["Pública"]).reindex(ORDEM_RENDA)
    if (gaps > 0).all():
        t_er = (f"Em todas as faixas de renda a escola privada fica à frente, por {_num(gaps.min())} a "
                f"{_num(gaps.max())} pontos")
    else:
        t_er = "A diferença entre escola privada e pública muda conforme a faixa de renda"
    s2 = '<div class="par">' + _figura(
        t_er, "Nota final média dos presentes por faixa de renda familiar. Barras a partir de zero.",
        div(grafico_nota_renda(df_pres)))
    s2 += _figura(f"{_pct(abst['Baixa Renda'])} dos inscritos de baixa renda faltaram; na alta renda, {_pct(abst['Alta Renda'])}",
                  f"Abstenção sobre todos os inscritos da amostra. A diferença é de {_num(kpi[14])} pontos percentuais.",
                  div(grafico_abstencao(aux, kpi[10]))) + "</div>"
    s2 += _figura(f"Na rede pública, {_pct(acima700['Pública'])} passam de 700 pontos; na privada, {_pct(acima700['Privada'])}",
                  "Percentual de alunos de cada rede em faixas de 25 pontos. Use o menu para comparar as redes em cada prova; "
                  "o título se refere à nota final.", div(grafico_distribuicao(df_pres)))

    # ---------- seção 3: família e casa ----------
    media_mr, n_mr = tabela_mae_renda(dm)
    pilha = media_mr.stack()
    (i_min, f_min), (i_max, f_max) = pilha.idxmin(), pilha.idxmax()
    i_min, i_max = int(i_min), int(i_max)
    s3 = _figura(f"De {_num(pilha.min(), 0)} a {_num(pilha.max(), 0)} pontos: escolaridade da mãe e renda andam junto com a nota",
                 f"A média mais baixa aparece com mãe em “{ESC_ROTULOS[i_min].lower()}” e {f_min.lower()}; a mais alta, com "
                 f"mãe em “{ESC_ROTULOS[i_max].lower()}” e {f_max.lower()}. Células com menos de {MIN_N} alunos ficam em branco.",
                 div(grafico_mae_renda(media_mr, n_mr)))
    g_rec = tabela_recursos(dm)
    pr = g_rec["mean"].dropna()
    (c_min, w_min), (c_max, w_max) = pr.idxmin(), pr.idxmax()

    def lar(c, w):
        c = int(c)
        comp = "nenhum computador" if c == 0 else f"{COMP_ROTULOS[c]} computador{'es' if c > 1 else ''}"
        return f"{comp} {'e com' if w else 'e sem'} internet"

    s3 += _figura(f"Em casa com {lar(c_max, w_max)}, a média chega a {_num(pr.max(), 0)}; com {lar(c_min, w_min)}, "
                  f"fica em {_num(pr.min(), 0)}",
                  "Nota final média pelo número de computadores em casa, separando quem tem e quem não tem internet. "
                  f"Barras ausentes têm menos de {MIN_N} alunos.",
                  div(grafico_recursos(g_rec)))

    secoes = [("territorio", 1, "azul", "Território", "Onde o aluno faz a prova",
               "As médias estaduais se separam em dois blocos, e o desenvolvimento do estado acompanha a nota.", s1),
              ("renda", 2, "amarelo", "Renda e escola", "Renda e escola",
               "A rede de ensino e a renda da família pesam na nota e também em quem chega a fazer a prova.", s2),
              ("familia", 3, "branco", "Família e casa", "Família e casa",
               "O que o aluno tem em casa, da escolaridade da mãe ao computador, segue o mesmo padrão.", s3)]

    # ---------- seção 4: modelos ----------
    arq_res = RAIZ / "resultados" / "metricas_entrega2.json"
    if arq_res.exists():
        res = json.loads(arq_res.read_text(encoding="utf-8"))
        lin = res["regressao_linear"]["teste"]
        coefs = res["regressao_linear"]["coeficientes"]
        nomes = nomes_coeficientes(coefs, dm)
        topo = max(coefs, key=lambda k: abs(coefs[k]))
        f1 = {n: d["teste"]["F1"] for n, d in res["classificacao"].items()}
        s4 = _figura(f"{nomes[topo][1]} é a variável com maior peso: {_sinal(coefs[topo])} pontos na nota final, "
                     "com as demais constantes",
                     f"Coeficientes da Regressão Linear (R² = {_br(lin['R²'], 2)}, erro médio de {_num(lin['MAE'])} pts no "
                     "teste). Cada barra é a associação de uma variável com a nota, controlando todas as outras; não é causa. "
                     "As variáveis numéricas são padronizadas (efeito de 1 desvio-padrão) e as categorias se comparam à "
                     "referência indicada.", div(grafico_coeficientes(res, nomes)))
        s4 += _figura(f"Os três modelos ficam próximos, com F1 entre {_br(min(f1.values()), 2)} e {_br(max(f1.values()), 2)}; "
                      f"o modelo escolhido foi {html.escape(res['insights']['modelo_final'])}",
                      f"Classificação de quem passa de 700 pontos ({_pct(res['base']['taxa_alto_desempenho'] * 100)} dos alunos). "
                      "Métricas no conjunto de teste. A taxa base é a precisão de um palpite aleatório.",
                      div(grafico_modelos(res)))
        secoes.append(("modelos", 4, "rosa", "Modelos", "O que os modelos dizem",
                       "Dois modelos da Entrega 2: uma regressão para a nota e classificadores para quem passa de 700.", s4))
    else:
        print(f"Aviso: {arq_res.relative_to(RAIZ)} não encontrado; a seção de modelos foi omitida "
              "(rode o notebook da Entrega 2 para gerá-lo).")

    secoes.append(("indicadores", len(secoes) + 1, "cinza", "Indicadores", "Os 20 indicadores",
                   "Os KPIs do projeto, em quatro eixos, com os mesmos valores dos notebooks.", html_kpis(df_kpis)))

    menu = "".join(f'<li><a class="it" href="#{i}"><span class="bola" data-c="{c}" aria-hidden="true">{n}</span>'
                   f'<span class="rot">{curto}</span></a></li>' for i, n, c, curto, _, _, _ in secoes)
    corpo = "".join(_secao(i, n, c, t, d, s) for i, n, c, _, t, d, s in secoes)

    pagina = (PAGINA.replace("__PLOTLY__", plotly_js)
              .replace("__CSS__", CSS)
              .replace("__JS__", JS.replace("__ESCURO__", json.dumps({k.lower(): v for k, v in ESCURO.items()})))
              .replace("__DESCRICAO__", html.escape(manchete + "."))
              .replace("__MENU__", menu)
              .replace("__MANCHETE__", html.escape(manchete) + ".")
              .replace("__DEK__", html.escape(dek))
              .replace("__DESTAQUES__", html_dest)
              .replace("__SECOES__", corpo)
              .replace("__AMOSTRA__", f"Amostra de {_br(len(df), 0)} concluintes do ensino médio, "
                                      f"{_br(len(df_pres), 0)} com as cinco provas.")
              .replace("__REPO__", REPO))

    saida = Path(args.saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(pagina, encoding="utf-8")
    print(f"Dashboard gerado: {saida} ({saida.stat().st_size / 1e3:,.0f} KB)")


if __name__ == "__main__":
    main()
