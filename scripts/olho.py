"""Gera o gráfico de contribuições com um olho que pisca e olha, um por um,
para os dias em que houve contribuição.

Uso: GITHUB_TOKEN=... python scripts/olho.py <usuario> <pasta_saida>
Gera olho.svg (tema claro) e olho-dark.svg (tema escuro).
"""
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

CELULA, ESPACO = 12, 3
PASSO = CELULA + ESPACO
MARGEM_X = 10
TOPO_GRADE = 118
OLHO_X, OLHO_Y = None, 52  # x é calculado pelo centro da grade
OLHO_RX, OLHO_RY = 46, 26
IRIS_R, PUPILA_R = 18, 8
DESVIO_MAX = 16  # quanto a íris anda dentro do olho
SEG_POR_DIA = 1.3
MAX_ALVOS = 30

TEMAS = {
    "olho.svg": {
        "niveis": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "esclera": "#ffffff", "contorno": "#57606a", "iris": ("#7cc7ee", "#1f6f9c"),
        "pupila": "#0d1117", "brilho": "#0969da",
    },
    "olho-dark.svg": {
        "niveis": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "esclera": "#e6edf3", "contorno": "#30363d", "iris": ("#7cc7ee", "#2c9fd9"),
        "pupila": "#0d1117", "brilho": "#2c9fd9",
    },
}
NIVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
         "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}

CONSULTA = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}"""


def buscar_semanas(usuario, token):
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": usuario}}).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql", data=corpo,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        dados = json.load(resp)
    if "errors" in dados:
        raise SystemExit(dados["errors"])
    cal = dados["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [s["contributionDays"] for s in cal["weeks"]]


def escolher_alvos(dias):
    """Dias com contribuição em ordem cronológica, amostrados se forem muitos."""
    if len(dias) <= MAX_ALVOS:
        return dias
    passo = (len(dias) - 1) / (MAX_ALVOS - 1)
    return [dias[round(i * passo)] for i in range(MAX_ALVOS)]


def fmt(n):
    return f"{n:.2f}".rstrip("0").rstrip(".")


def gerar_svg(semanas, tema):
    largura = MARGEM_X * 2 + len(semanas) * PASSO - ESPACO
    altura = TOPO_GRADE + 7 * PASSO - ESPACO + 10
    ox = largura / 2

    celulas, ativos = [], []
    for i, semana in enumerate(semanas):
        for dia in semana:
            x = MARGEM_X + i * PASSO
            y = TOPO_GRADE + dia["weekday"] * PASSO
            nivel = NIVEL[dia["contributionLevel"]]
            celulas.append(f'<rect x="{x}" y="{y}" width="{CELULA}" height="{CELULA}" rx="2" '
                           f'fill="{tema["niveis"][nivel]}"/>')
            if dia["contributionCount"] > 0:
                ativos.append({**dia, "cx": x + CELULA / 2, "cy": y + CELULA / 2})

    alvos = escolher_alvos(ativos)
    partes = []

    if alvos:
        n = len(alvos)
        dur = n * SEG_POR_DIA + 1.5  # pausa olhando para frente no fim
        # Para cada alvo: chega (25% do trecho) e fica olhando (75%).
        tempos, iris, raio = [0], ["0 0"], [(ox, OLHO_Y)]
        for k, a in enumerate(alvos):
            dx, dy = a["cx"] - ox, a["cy"] - OLHO_Y
            d = math.hypot(dx, dy) or 1
            # O olho é mais largo que alto: o desvio vertical é menor.
            ix, iy = dx / d * DESVIO_MAX, dy / d * DESVIO_MAX * 0.45
            ini = k * SEG_POR_DIA
            tempos += [(ini + SEG_POR_DIA * 0.25) / dur, (ini + SEG_POR_DIA) / dur]
            iris += [f"{fmt(ix)} {fmt(iy)}"] * 2
            raio += [(a["cx"], a["cy"])] * 2
        tempos += [(n * SEG_POR_DIA + 0.4) / dur, 1]
        iris += ["0 0", "0 0"]
        raio += [(ox, OLHO_Y)] * 2
        kt = ";".join(fmt(t) if t < 1 else "1" for t in tempos)

        # Raio de visão: some quando o olho está olhando para frente.
        opac_raio = ["0"] + ["0.5", "0.5"] * n + ["0", "0"]
        partes.append(
            f'<line x1="{fmt(ox)}" y1="{OLHO_Y + OLHO_RY - 4}" stroke="{tema["brilho"]}" '
            f'stroke-width="2" stroke-dasharray="3 5" stroke-linecap="round">'
            f'<animate attributeName="x2" dur="{fmt(dur)}s" repeatCount="indefinite" keyTimes="{kt}" '
            f'values="{";".join(fmt(p[0]) for p in raio)}"/>'
            f'<animate attributeName="y2" dur="{fmt(dur)}s" repeatCount="indefinite" keyTimes="{kt}" '
            f'values="{";".join(fmt(p[1]) for p in raio)}"/>'
            f'<animate attributeName="opacity" dur="{fmt(dur)}s" repeatCount="indefinite" keyTimes="{kt}" '
            f'values="{";".join(opac_raio)}"/></line>')

        # Destaque no dia observado: acende enquanto o olho está nele.
        for k, a in enumerate(alvos):
            ini, fim = k * SEG_POR_DIA, (k + 1) * SEG_POR_DIA
            t0 = (ini + SEG_POR_DIA * 0.2) / dur
            t1 = (ini + SEG_POR_DIA * 0.3) / dur
            t2 = (fim - 0.1) / dur
            t3 = min(fim / dur, 0.999)
            kts = f"0;{fmt(t0)};{fmt(t1)};{fmt(t2)};{fmt(t3)};1"
            x, y = a["cx"] - CELULA / 2 - 2, a["cy"] - CELULA / 2 - 2
            partes.append(
                f'<rect x="{fmt(x)}" y="{fmt(y)}" width="{CELULA + 4}" height="{CELULA + 4}" rx="4" '
                f'fill="none" stroke="{tema["brilho"]}" stroke-width="2" opacity="0">'
                f'<title>{a["date"]}: {a["contributionCount"]} contribuições</title>'
                f'<animate attributeName="opacity" dur="{fmt(dur)}s" repeatCount="indefinite" '
                f'keyTimes="{kts}" values="0;0;1;1;0;0"/></rect>')

        mov_iris = (f'<animateTransform attributeName="transform" type="translate" dur="{fmt(dur)}s" '
                    f'repeatCount="indefinite" keyTimes="{kt}" values="{";".join(iris)}" '
                    f'calcMode="spline" keySplines="{";".join(["0.4 0 0.2 1"] * (len(tempos) - 1))}"/>')
    else:
        # Sem contribuições: o olho só passeia de um lado para o outro.
        mov_iris = ('<animateTransform attributeName="transform" type="translate" dur="6s" '
                    f'repeatCount="indefinite" values="0 0;-{DESVIO_MAX} 2;{DESVIO_MAX} 2;0 0"/>')

    # Piscada a cada 4 s: a pálpebra (clip) fecha e abre rapidamente.
    piscar = (f'<animate attributeName="ry" dur="4s" repeatCount="indefinite" '
              f'keyTimes="0;0.9;0.94;0.98;1" values="{OLHO_RY};{OLHO_RY};1;{OLHO_RY};{OLHO_RY}"/>')
    olho = f"""
  <clipPath id="palpebra"><ellipse cx="{fmt(ox)}" cy="{OLHO_Y}" rx="{OLHO_RX}" ry="{OLHO_RY}">{piscar}</ellipse></clipPath>
  <radialGradient id="cor-iris"><stop offset=".35" stop-color="{tema["iris"][0]}"/><stop offset="1" stop-color="{tema["iris"][1]}"/></radialGradient>
  <g clip-path="url(#palpebra)">
    <ellipse cx="{fmt(ox)}" cy="{OLHO_Y}" rx="{OLHO_RX}" ry="{OLHO_RY}" fill="{tema["esclera"]}"/>
    <g>{mov_iris}
      <circle cx="{fmt(ox)}" cy="{OLHO_Y}" r="{IRIS_R}" fill="url(#cor-iris)"/>
      <circle cx="{fmt(ox)}" cy="{OLHO_Y}" r="{PUPILA_R}" fill="{tema["pupila"]}"/>
      <circle cx="{fmt(ox + 5)}" cy="{OLHO_Y - 5}" r="3" fill="#ffffff" opacity=".85"/>
    </g>
  </g>
  <ellipse cx="{fmt(ox)}" cy="{OLHO_Y}" rx="{OLHO_RX}" ry="{OLHO_RY}" fill="none" stroke="{tema["contorno"]}" stroke-width="3">{piscar}</ellipse>"""

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(largura)}" height="{altura}" '
            f'viewBox="0 0 {fmt(largura)} {altura}">\n  '
            + "\n  ".join(celulas) + "\n  " + "\n  ".join(partes) + olho + "\n</svg>\n")


def main():
    usuario, saida = sys.argv[1], Path(sys.argv[2])
    semanas = buscar_semanas(usuario, os.environ["GITHUB_TOKEN"])
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tema in TEMAS.items():
        (saida / nome).write_text(gerar_svg(semanas, tema), encoding="utf-8")
        print(saida / nome)


if __name__ == "__main__":
    main()
