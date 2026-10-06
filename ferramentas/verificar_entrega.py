"""
Verificação automática da entrega final (requisitos, coerência dos números, higiene do repositório).

Uso (na raiz do projeto, depois de executar os dois notebooks):
    python ferramentas/verificar_entrega.py

Sai com código 1 se alguma verificação falhar. O resultado alimenta docs/VERIFICACAO.md.
"""

import html
import json
import re
import subprocess
import sys
from pathlib import Path

import mistune
import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))  # permite importar src/ ao rodar o script de qualquer pasta
from src.dados import gerar_ibge  # noqa: E402
NB1, NB2 = RAIZ / "Entrega1_ENEM_IBGE.ipynb", RAIZ / "Entrega2_ENEM_IBGE.ipynb"
RESULTADOS = RAIZ / "resultados" / "metricas_entrega2.json"
DOCS_COM_NUMEROS = [RAIZ / "README.md", RAIZ / "docs" / "roteiro_relatorio.md", RAIZ / "docs" / "slides_ml.md",
                    RAIZ / "docs" / "DECISOES.md"]

falhas = []


def checar(condicao: bool, descricao: str, evidencia: str = "") -> None:
    print(f"[{'OK' if condicao else 'FALHOU'}] {descricao}" + (f" | {evidencia}" if evidencia else ""))
    if not condicao:
        falhas.append(descricao)


def carregar(nb_path: Path) -> dict:
    return json.loads(nb_path.read_text(encoding="utf-8"))


def textos_saida(nb: dict) -> list[str]:
    """Todas as saídas textuais (stream, texto, markdown, HTML sem tags)."""
    textos = []
    for c in nb["cells"]:
        for o in c.get("outputs", []):
            if o["output_type"] == "stream":
                textos.append("".join(o["text"]))
            if o["output_type"] == "error":
                textos.append("Traceback " + o["ename"])
            for tipo in ("text/plain", "text/markdown", "text/html"):
                if tipo in o.get("data", {}):
                    t = "".join(o["data"][tipo])
                    textos.append(html.unescape(re.sub(r"<[^>]+>", " ", t)) if tipo == "text/html" else t)
    return textos


def codigo(nb: dict) -> list[str]:
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def markdown(nb: dict) -> str:
    return "\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "markdown")


def n_imagens(nb: dict) -> int:
    return sum("image/png" in o.get("data", {}) for c in nb["cells"] for o in c.get("outputs", []))


nb1, nb2 = carregar(NB1), carregar(NB2)
res = json.loads(RESULTADOS.read_text(encoding="utf-8"))

# =====================================================================
print("\n=== 1. Execução dos notebooks ===")
for nome, nb in (("Entrega 1", nb1), ("Entrega 2", nb2)):
    cods = [c for c in nb["cells"] if c["cell_type"] == "code"]
    executadas = all(c.get("execution_count") for c in cods)
    erros = sum(o["output_type"] == "error" for c in cods for o in c.get("outputs", []))
    tracebacks = sum("Traceback" in t for t in textos_saida(nb))
    checar(executadas, f"{nome}: todas as células de código executadas", f"{len(cods)} células")
    checar(erros == 0 and tracebacks == 0, f"{nome}: zero erros e zero tracebacks nas saídas",
           f"erros={erros}, tracebacks={tracebacks}")

# =====================================================================
print("\n=== 2. Requisitos do professor ===")
# KPIs: assert no código + 20 linhas nas tabelas exibidas
for nome, nb in (("Entrega 1", nb1), ("Entrega 2", nb2)):
    tem_assert = any("assert len(df_kpis) == 20" in c for c in codigo(nb))
    linhas_kpi = set()
    for c in nb["cells"]:
        if "exibir_kpis(df_kpis)" in "".join(c["source"]):
            for o in c.get("outputs", []):
                h = "".join(o.get("data", {}).get("text/html", ""))
                linhas_kpi |= set(re.findall(r'<th id="T_\w+_level0_row\d+" class="row_heading level0 row\d+" >(\d+)</th>', h))
    checar(tem_assert and len(linhas_kpi) == 20, f"{nome}: 20 KPIs (assert + tabela exibida)",
           f"KPIs exibidos = {len(linhas_kpi)}")
checar(len(res["kpis"]) == 20, "resultados JSON: 20 KPIs", f"{len(res['kpis'])}")

img1, img2 = n_imagens(nb1), n_imagens(nb2)
checar(img1 + img2 >= 8 and img2 >= 8, "≥ 8 gráficos (Matplotlib/Seaborn)",
       f"Entrega 1 = {img1}, Entrega 2 = {img2}, total = {img1 + img2}")

saida2 = "\n".join(textos_saida(nb2))
for modelo in ("Regressão Logística", "Árvore de Decisão", "KNN"):
    treinado = re.search(rf"{modelo}\s+\d+ combinações × 5 dobras \| melhor:", saida2) is not None
    avaliado = modelo in res["classificacao"] and {"Precisão", "Recall", "F1"} <= set(res["classificacao"][modelo]["teste"])
    checar(treinado and avaliado, f"Modelo treinado (GridSearchCV) e avaliado: {modelo}",
           f"F1 teste = {res['classificacao'].get(modelo, {}).get('teste', {}).get('F1', 'n/a')}")
checar("R²" in res["regressao_linear"]["teste"] and "LinearRegression()" in "\n".join(codigo(nb2)),
       "Modelo treinado e avaliado: Regressão Linear", f"R² teste = {res['regressao_linear']['teste']['R²']}")

# Conceitos 1-7: evidência no código (notebook da Entrega 2 + módulos + coleta)
fonte = "\n".join(codigo(nb2)) + "\n".join(p.read_text(encoding="utf-8") for p in
                                          [RAIZ / "baixar_dados.py", *sorted((RAIZ / "src").glob("*.py"))])
md2 = markdown(nb2)
conceitos = {
    "1 Coleta de Dados": [r"chunksize=", r"apisidra\.ibge\.gov\.br", r"requests\.get\("],
    "2 Limpeza/Pré-processamento (ausentes, normalização, integração)":
        [r"SimpleImputer", r"StandardScaler", r'validate="m:1"', r"duplicated\(\)"],
    "3 Estatísticas descritivas (média, mediana, moda, dp)": [r"\.mean\(\)", r"\.median\(\)", r"\.mode\(\)", r"\.std\(\)"],
    "4 KPIs": [r"calcular_kpis\(", r"assert len\(df_kpis\) == 20"],
    "5 Visualização/Storytelling": [r"plt\.subplots", r"Principais insights"],
    "6 Feature Engineering": [r"criar_features\(", r"LOG_RENDA_PC"],
    "7a Regressão Linear e Logística": [r"LinearRegression\(", r"LogisticRegression\("],
    "7b Árvore de Decisão e KNN": [r"DecisionTreeClassifier\(", r"KNeighborsClassifier\("],
    "Avaliação (precisão, recall, F1, matriz, CV, overfitting)":
        [r'"precision"', r'"recall"', r'"f1"', r"ConfusionMatrixDisplay", r"StratifiedKFold\(", r"validation_curve\("],
}
for conceito, padroes in conceitos.items():
    ausentes = [p for p in padroes if not re.search(p, fonte + md2)]
    checar(not ausentes, f"Conceito {conceito}", "ausente: " + ", ".join(ausentes) if ausentes else "")
fora_escopo = [p for p in ("KMeans", "DBSCAN", "apriori") if re.search(p, fonte, re.I)]
checar(not fora_escopo, "Fora do escopo não implementado (K-Means, DBSCAN, Apriori)", ", ".join(fora_escopo))

# =====================================================================
print("\n=== 3. Coerência dos números (README e docs × notebooks) ===")


def numeros_json(obj):
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield float(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from numeros_json(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from numeros_json(v)
    elif isinstance(obj, str):  # números dentro de textos (hiperparâmetros, observações dos KPIs)
        for m in re.findall(r"\d+(?:\.\d+)?", obj.replace(",", "")):
            yield float(m)


meta = json.loads((RAIZ / "dados" / "processados" / "enem_amostra_meta.json").read_text(encoding="utf-8"))
universo = set(numeros_json(res)) | set(numeros_json(meta))
for t in textos_saida(nb1) + textos_saida(nb2):  # números exibidos nos notebooks (formato en-US)
    for m in re.findall(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\d+", t):
        universo.add(float(m.replace(",", "")))
universo |= {v * 100 for v in list(universo) if abs(v) <= 1}  # frações exibidas como %

# Tabela estadual real e valores da simulação (citados em docs/DECISOES.md ao comparar as duas)
for tabela in (pd.read_csv(RAIZ / "dados" / "ibge_uf.csv"), gerar_ibge()):
    universo |= set(tabela.select_dtypes("number").to_numpy().ravel().astype(float))

# Resultados do protótipo exploratório (antes do ajuste do desbalanceamento), registrados
# apenas em docs/DECISOES.md (D13) para justificar a decisão; não fazem parte dos notebooks finais.
EXPLORATORIOS = {0.15: "precisão com class_weight='balanced' no protótipo (D13)",
                 0.80: "recall com class_weight='balanced' no protótipo (D13)",
                 0.25: "F1 com class_weight='balanced' no protótipo (D13)"}

# Constantes de método citadas nos textos (não são resultados): justificativa ao lado
CONSTANTES = {
    1.25: "multiplicador da faixa aberta do Q006",
    1.8: "tamanho do CSV do INEP em GB",
    26400.0: "limite inferior da faixa Q do Q006 (R$)",
    33000.0: "ponto médio adotado para a faixa Q (R$)",
    1320.0: "salário mínimo de 2023 (R$)",
    3.12: "versão do Python",
}


def numeros_ptbr(texto: str):
    """Números em formato brasileiro com decimais (ex.: 0,336 | 616,1) ou milhar (56.048)."""
    for m in re.finditer(r"(?<![\w.,/])(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+,\d+)(?![\d/])", texto):
        bruto = m.group(1)
        casas = len(bruto.split(",")[1]) if "," in bruto else 0
        yield bruto, float(bruto.replace(".", "").replace(",", ".")), casas


def confere(valor: float, casas: int) -> bool:
    tol = 0.5 * 10 ** (-casas) + 1e-9
    return any(abs(abs(u) - valor) <= tol for u in universo) or any(abs(c - valor) < 1e-9 for c in CONSTANTES)


for doc in DOCS_COM_NUMEROS:
    texto = doc.read_text(encoding="utf-8")
    encontrados = list(numeros_ptbr(texto))
    sem_origem = sorted({b for b, v, c in encontrados if not confere(v, c)
                         and not (doc.name == "DECISOES.md" and any(abs(e - v) < 1e-9 for e in EXPLORATORIOS))})
    checar(not sem_origem, f"{doc.relative_to(RAIZ)}: números rastreáveis aos notebooks/JSON",
           f"{len(encontrados)} números verificados" + (f"; SEM ORIGEM: {sem_origem}" if sem_origem else ""))

# Insights do notebook são gerados a partir das variáveis (não digitados)
celula_insights = next(c for c in codigo(nb2) if "insights = f\"\"\"" in c)
checar("display(Markdown(insights))" in celula_insights, "Insights gerados por f-string a partir das variáveis")

# Marcadores em maiúsculas (case-sensitive: "Todo" em português não é placeholder) + frases típicas
placeholders = re.compile(r"\bTODO\b|\bFIXME\b|\bTBD\b|\bXX+\b|(?i:inserir aqui|lorem ipsum)")
achados = []
arquivos_texto = [p for p in RAIZ.rglob("*") if p.suffix in {".md", ".py", ".txt", ".csv", ".json"}
                  and ".venv" not in p.parts and "brutos" not in p.parts and ".git" not in p.parts]
for p in arquivos_texto:
    if p.name == "verificar_entrega.py":
        continue
    for i, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if placeholders.search(linha):
            achados.append(f"{p.relative_to(RAIZ)}:{i}")
for nb_path, nb in ((NB1, nb1), (NB2, nb2)):
    fontes = "\n".join("".join(c["source"]) for c in nb["cells"])
    if placeholders.search(fontes) or any(placeholders.search(t) for t in textos_saida(nb)):
        achados.append(nb_path.name)
checar(not achados, "Nenhum placeholder esquecido (TODO, XX, inserir aqui...)", ", ".join(achados))

# =====================================================================
print("\n=== 4. Repositório ===")
rastreados = subprocess.run(["git", "ls-files"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout.split()
grandes = [(f, (RAIZ / f).stat().st_size) for f in rastreados if (RAIZ / f).stat().st_size > 50 * 1024 ** 2]
maior = max(rastreados, key=lambda f: (RAIZ / f).stat().st_size)
checar(not grandes, "Nenhum arquivo versionado acima de 50 MB",
       f"maior: {maior} ({(RAIZ / maior).stat().st_size / 1024 ** 2:.1f} MB)")
checar(not any(f.startswith("dados/brutos/") for f in rastreados), "dados/brutos/ fora do versionamento",
       f"{len(rastreados)} arquivos rastreados")

segredo = re.compile(r"(api[_-]?key|secret|password|senha|token)\s*[=:]\s*['\"][^'\"]{6,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}", re.I)
caminho_abs = re.compile(r"[A-Za-z]:[\\/]+Users|/home/\w+|/Users/\w+|\\\\Users\\\\", re.I)
problemas_seg, problemas_cam = [], []
for f in rastreados:
    p = RAIZ / f
    if p.suffix in {".parquet", ".png"} or p.name == "verificar_entrega.py":
        continue
    texto = p.read_text(encoding="utf-8", errors="ignore")
    if p.suffix == ".ipynb":  # ignora imagens embutidas em base64
        texto = re.sub(r'"image/png": "[^"]*"', "", texto)
    if segredo.search(texto):
        problemas_seg.append(f)
    if caminho_abs.search(texto):
        problemas_cam.append(f)
checar(not problemas_seg, "Nenhuma credencial no código", ", ".join(problemas_seg))
checar(not problemas_cam, "Nenhum caminho absoluto da máquina local", ", ".join(problemas_cam))

# README: renderização (mistune) — cercas de código fechadas, tabelas reconhecidas, links locais existentes
readme = (RAIZ / "README.md").read_text(encoding="utf-8")
html_readme = mistune.create_markdown(plugins=["table"])(readme)
cercas = readme.count("```")
tabelas_md = len(re.findall(r"^\|.*\|\s*\n\|[-| :]+\|\s*$", readme, re.M))
tabelas_html = html_readme.count("<table>")
links_locais = [l for l in re.findall(r"\]\(([^)#]+)\)", readme) if not l.startswith("http")]
quebrados = [l for l in links_locais if not (RAIZ / l).exists()]
checar(cercas % 2 == 0 and tabelas_md == tabelas_html and not quebrados, "README renderiza corretamente",
       f"{tabelas_html}/{tabelas_md} tabelas, {cercas // 2} blocos de código, {len(links_locais)} links locais"
       + (f"; quebrados: {quebrados}" if quebrados else ""))

# =====================================================================
print("\n=== 5. Revisão de código ===")
for nome, nb in (("Entrega 1", nb1), ("Entrega 2", nb2)):
    fontes = [s.strip() for s in codigo(nb)]
    vazias = sum(1 for s in fontes if not s)
    duplicadas = len(fontes) - len(set(fontes))
    checar(vazias == 0 and duplicadas == 0, f"{nome}: sem células vazias ou duplicadas",
           f"vazias={vazias}, duplicadas={duplicadas}")
    fora_do_topo = [i for i, s in enumerate(fontes[1:], 1) if re.search(r"^\s*(import \w|from [\w.]+ import )", s, re.M)]
    checar(not fora_do_topo, f"{nome}: imports apenas na primeira célula de código", str(fora_do_topo or ""))

# Toda chamada aleatória com SEED
aleatorias = re.compile(r"(train_test_split|KFold|StratifiedKFold|DecisionTreeClassifier|LogisticRegression|"
                        r"RandomUnderSampler|\.sample|default_rng|np\.random\.seed)\(")
def chamada_completa(texto: str, inicio_args: int) -> str:
    """Devolve os argumentos de uma chamada, respeitando parênteses aninhados."""
    nivel, i = 1, inicio_args
    while nivel and i < len(texto):
        nivel += {"(": 1, ")": -1}.get(texto[i], 0)
        i += 1
    return texto[inicio_args: i - 1]


sem_seed, n_chamadas = [], 0
for nome, texto in [("Entrega2", "\n".join(codigo(nb2))), ("baixar_dados.py", (RAIZ / "baixar_dados.py").read_text(encoding="utf-8")),
                    *[(p.name, p.read_text(encoding="utf-8")) for p in (RAIZ / "src").glob("*.py")]]:
    for m in aleatorias.finditer(texto):
        n_chamadas += 1
        argumentos = chamada_completa(texto, m.end())
        if "SEED" not in argumentos:
            sem_seed.append(f"{nome}: {m.group(1)}({argumentos[:40]})")
checar(not sem_seed, "SEED aplicada em toda rotina aleatória",
       f"{n_chamadas} chamadas verificadas" + (f"; sem SEED: {sem_seed}" if sem_seed else ""))

# Comentários em português (heurística: palavras funcionais em inglês)
ingles = re.compile(r"#.*\b(the|and|with|this|that|should|returns?|which|because)\b", re.I)
comentarios_en = []
for p in [RAIZ / "baixar_dados.py", *(RAIZ / "src").glob("*.py"), RAIZ / "ferramentas" / "verificar_entrega.py"]:
    for i, linha in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
        if ingles.search(linha) and not linha.lstrip().startswith("ingles = re.compile"):
            comentarios_en.append(f"{p.name}:{i}")
for nome, nb in (("Entrega1", nb1), ("Entrega2", nb2)):
    for s in codigo(nb):
        for linha in s.splitlines():
            if ingles.search(linha):
                comentarios_en.append(f"{nome}: {linha.strip()[:50]}")
checar(not comentarios_en, "Comentários em português", "; ".join(comentarios_en))

print("\n" + ("TODAS AS VERIFICAÇÕES PASSARAM" if not falhas else f"{len(falhas)} FALHA(S): " + " | ".join(falhas)))
sys.exit(1 if falhas else 0)
