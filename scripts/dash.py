"""Gera um painel estilo dashboard com os dados do GitHub.

Com um token pessoal (PERFIL_TOKEN no workflow) entram também os repositórios
e contribuições privados; só números aparecem, nunca nomes de repositórios.

Uso: GITHUB_TOKEN=... python scripts/dash.py <usuario> <pasta_saida>
Gera dash.svg (tema claro) e dash-dark.svg (tema escuro).
"""
import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

LARGURA = 854
FONTE = 'system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif'
MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
SEMANA = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"]
MAX_LINGUAGENS = 5

TEMAS = {
    "dash.svg": {
        "card": "#ffffff", "borda": "#d0d7de", "texto": "#1f2328", "texto2": "#59636e",
        "mudo": "#818b98", "grade": "#eaeef2", "base": "#d0d7de", "barra": "#2a78d6",
        "trilho": "#eaeef2",
    },
    "dash-dark.svg": {
        "card": "#161b22", "borda": "#30363d", "texto": "#e6edf3", "texto2": "#9198a1",
        "mudo": "#6e7681", "grade": "#21262d", "base": "#30363d", "barra": "#3987e5",
        "trilho": "#21262d",
    },
}

CONSULTA = """
query($login: String!) {
  user(login: $login) {
    repositories(ownerAffiliations: OWNER, isFork: false, first: 100) {
      nodes { isPrivate languages(first: 10) { edges { size node { name } } } }
    }
    contributionsCollection {
      totalCommitContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount } }
      }
    }
  }
}"""


def buscar(usuario, token):
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": usuario}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=corpo,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        dados = json.load(resp)
    if "errors" in dados:
        raise SystemExit(dados["errors"])
    return dados["data"]["user"]


def plural(n, palavra):
    return f"{n} {palavra}{'' if n == 1 else 's'}"


def resumir(user):
    col = user["contributionsCollection"]
    dias = [d for s in col["contributionCalendar"]["weeks"] for d in s["contributionDays"]]

    por_mes = defaultdict(int)
    for d in dias:
        por_mes[d["date"][:7]] += d["contributionCount"]
    # Últimos 12 meses, terminando no mês atual.
    hoje = date.fromisoformat(dias[-1]["date"])
    meses = []
    for k in range(11, -1, -1):
        a, m = divmod(hoje.year * 12 + hoje.month - 1 - k, 12)
        meses.append((MESES[m], por_mes.get(f"{a}-{m + 1:02d}", 0)))

    semana = [0] * 7
    for d in dias:
        semana[d["weekday"]] += d["contributionCount"]

    linguagens = Counter()
    repos = user["repositories"]
    privados = any(r["isPrivate"] for r in repos["nodes"])
    for r in repos["nodes"]:
        for e in r["languages"]["edges"]:
            linguagens[e["node"]["name"]] += e["size"]
    total_bytes = sum(linguagens.values()) or 1
    top = linguagens.most_common(MAX_LINGUAGENS)
    resto = total_bytes - sum(v for _, v in top)
    ling = [(n, v / total_bytes * 100) for n, v in top]
    if resto > 0:
        ling.append(("Outras", resto / total_bytes * 100))

    return {
        "kpis": [
            (str(col["contributionCalendar"]["totalContributions"]), "Contribuições", "últimos 12 meses"),
            (str(col["totalCommitContributions"]), "Commits", "últimos 12 meses"),
            (str(sum(1 for d in dias if d["contributionCount"])), "Dias ativos", "últimos 12 meses"),
            (str(len(repos["nodes"])), "Repositórios",
             plural(sum(1 for r in repos["nodes"] if r["isPrivate"]), "privado") if privados else "públicos"),
        ],
        "meses": meses,
        "semana": list(zip(SEMANA, semana)),
        "linguagens": ling,
    }


def t(x, y, texto, tema, cor="texto", tam=12, peso=400, ancora="start"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" fill="{tema[cor]}" font-size="{tam}" '
            f'font-weight="{peso}" text-anchor="{ancora}">{escape(texto)}</text>')


def card(x, y, w, h, tema, titulo=None):
    s = (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{tema["card"]}" '
         f'stroke="{tema["borda"]}"/>')
    if titulo:
        s += t(x + 16, y + 26, titulo, tema, "texto", 13, 600)
    return s


def barra_v(x, base, w, h, cor):
    """Barra vertical com topo arredondado (4px) e base reta, ancorada no eixo."""
    if h <= 0:
        return ""
    r = min(4, w / 2, h)
    return (f'<path d="M{x:.1f} {base:.1f}V{base - h + r:.1f}Q{x:.1f} {base - h:.1f} {x + r:.1f} {base - h:.1f}'
            f'H{x + w - r:.1f}Q{x + w:.1f} {base - h:.1f} {x + w:.1f} {base - h + r:.1f}V{base:.1f}Z" fill="{cor}"/>')


def grafico_colunas(x, y, w, h, dados, tema, titulo, legenda_eixo):
    """Colunas de uma série; rótulo direto só no maior valor e no último."""
    partes = [card(x, y, w, h, tema, titulo), t(x + w - 16, y + 26, legenda_eixo, tema, "mudo", 11, ancora="end")]
    topo, base = y + 52, y + h - 30
    area = base - topo
    maximo = max((v for _, v in dados), default=0) or 1
    passo = (w - 32) / len(dados)
    larg = min(28, passo - 8)
    # Grade: linha do meio e do máximo, bem discretas.
    for frac in (0.5, 1):
        gy = base - area * frac
        partes.append(f'<line x1="{x + 16}" x2="{x + w - 16}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{tema["grade"]}"/>')
        partes.append(t(x + 16, gy - 4, f"{maximo * frac:g}", tema, "mudo", 10))
    i_max = max(range(len(dados)), key=lambda i: dados[i][1])
    for i, (rotulo, v) in enumerate(dados):
        cx = x + 16 + passo * i + passo / 2
        hb = area * v / maximo
        partes.append(barra_v(cx - larg / 2, base, larg, hb, tema["barra"]))
        partes.append(t(cx, base + 16, rotulo, tema, "mudo", 10, ancora="middle"))
        if v and i in (i_max, len(dados) - 1):
            partes.append(t(cx, base - hb - 5, str(v), tema, "texto2", 11, 600, "middle"))
    partes.append(f'<line x1="{x + 16}" x2="{x + w - 16}" y1="{base}" y2="{base}" stroke="{tema["base"]}"/>')
    return "".join(partes)


def grafico_linguagens(x, y, w, h, dados, tema):
    """Barras horizontais com nome e % escritos: a cor não precisa identificar nada."""
    partes = [card(x, y, w, h, tema, "Linguagens nos repositórios")]
    if not dados:
        return "".join(partes) + t(x + 16, y + 60, "Sem dados públicos ainda", tema, "mudo", 12)
    col_nome, col_barra = x + 16, x + 140
    larg = w - (col_barra - x) - 60
    linha = (h - 52) / max(len(dados), 1)
    for i, (nome, pct) in enumerate(dados):
        cy = y + 52 + linha * i + linha / 2
        partes.append(t(col_nome, cy + 4, nome, tema, "texto2", 12))
        partes.append(f'<rect x="{col_barra}" y="{cy - 5:.1f}" width="{larg}" height="10" rx="4" fill="{tema["trilho"]}"/>')
        partes.append(f'<rect x="{col_barra}" y="{cy - 5:.1f}" width="{max(larg * pct / 100, 4):.1f}" height="10" '
                      f'rx="4" fill="{tema["barra"]}"/>')
        partes.append(t(x + w - 16, cy + 4, f"{pct:.0f}%", tema, "texto", 12, 600, "end"))
    return "".join(partes)


def gerar_svg(r, tema):
    p = []
    # Linha 1: indicadores.
    gap, w_kpi = 12, (LARGURA - 3 * 12) / 4
    for i, (valor, nome, sub) in enumerate(r["kpis"]):
        x = i * (w_kpi + gap)
        p.append(card(x + .5, .5, w_kpi - 1, 88, tema))
        p.append(t(x + 16, 26, nome, tema, "texto2", 12, 500))
        p.append(t(x + 16, 62, valor, tema, "texto", 30, 700))
        p.append(t(x + 16, 79, sub, tema, "mudo", 10))
    # Linha 2: contribuições por mês.
    p.append(grafico_colunas(.5, 100.5, LARGURA - 1, 200, r["meses"], tema,
                             "Contribuições por mês", "últimos 12 meses"))
    # Linha 3: linguagens e dia da semana.
    meia = (LARGURA - gap) / 2
    p.append(grafico_linguagens(.5, 312.5, meia - 1, 190, r["linguagens"], tema))
    p.append(grafico_colunas(meia + gap + .5, 312.5, meia - 1, 190, r["semana"], tema,
                             "Por dia da semana", "total no período"))
    altura = 504
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{altura}" '
            f'viewBox="0 0 {LARGURA} {altura}" font-family=\'{FONTE}\'>'
            f'<title>Painel de atividade no GitHub</title>{"".join(p)}</svg>\n')


def main():
    usuario, saida = sys.argv[1], Path(sys.argv[2])
    r = resumir(buscar(usuario, os.environ["GITHUB_TOKEN"]))
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tema in TEMAS.items():
        (saida / nome).write_text(gerar_svg(r, tema), encoding="utf-8")
        print(saida / nome)


if __name__ == "__main__":
    main()
