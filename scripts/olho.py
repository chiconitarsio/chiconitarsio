"""Gera o gráfico de contribuições com o olho-radar do Licita IA andando sobre ele.

O olho (mascote do Licita IA: a íris é um radar com varredura dourada) passeia pela faixa acima
da grade, pisca, olha em volta e, nas paradas, olha para os dias com mais contribuições, que
acendem como um ponto no radar. O ciclo tem ainda três cenas: papéis caem na cabeça dele (que
os arruma ao lado), ele lê um caderno de editais e encontra um segundo olho, dourado.

Só SVG e CSS: o GitHub mostra o README como imagem, sem JavaScript. Com movimento reduzido, o
olho fica parado no meio e o dia de mais contribuições fica marcado.

Uso: GITHUB_TOKEN=... python scripts/olho.py <usuario> <pasta_saida>
Gera olho.svg (tema claro) e olho-dark.svg (tema escuro).
"""
import json
import math
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Grade de contribuições.
CELULA, ESPACO = 12, 3
PASSO = CELULA + ESPACO
MARGEM_X = 10
TOPO_GRADE = 152
ALTURA_RODAPE = 30

# Olho: desenhado num quadro de 400 x 200 e reduzido para OLHO_L de largura na figura.
OLHO_L = 160
OLHO_A = OLHO_L / 2
AMIGO_L = OLHO_L * 0.62  # o olho dourado do encontro
CONTORNO = "M25 100 A233 233 0 0 1 375 100 A233 233 0 0 1 25 100 Z"

# Curvas de movimento (as mesmas do site e do relatório).
ANDAR = "cubic-bezier(.45,.05,.35,1)"
OLHAR = "cubic-bezier(.3,.7,.3,1)"
QUEDA = "cubic-bezier(.5,0,1,1)"

TEMAS = {
    "olho.svg": {
        "niveis": ["#ebeff5", "#c5d6ec", "#8cb0db", "#3f72ab", "#12355b"],
        "texto": "#59636e", "linha": "#1d4f84", "ouro": "#c9a24c", "fundo_olho": "#ffffff",
        "marinho": "#0b2340", "papel": "#ffffff", "papel_linha": "#5a6474",
        "amigo_linha": "#b07d1a", "amigo_pupila": "#1d4f84", "sombra": ("#0b2340", ".2"),
    },
    "olho-dark.svg": {
        "niveis": ["#151c27", "#17375c", "#22538a", "#4b84c4", "#9cc0ea"],
        "texto": "#9198a1", "linha": "#9cc0ea", "ouro": "#e0b75a", "fundo_olho": "#0b2340",
        "marinho": "#0b2340", "papel": "#102238", "papel_linha": "#93a1b5",
        "amigo_linha": "#e0b75a", "amigo_pupila": "#9cc0ea", "sombra": ("#000000", ".5"),
    },
}
NIVEL = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
         "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
MESES = "jan fev mar abr mai jun jul ago set out nov dez".split()


def tokens():
    """Token pessoal (inclui atividade privada) primeiro; o do Actions como reserva."""
    return [t for t in (os.environ.get("PERFIL_TOKEN"), os.environ.get("GITHUB_TOKEN")) if t]


def consultar(corpo, lista):
    for i, token in enumerate(lista):
        req = urllib.request.Request(
            "https://api.github.com/graphql", data=corpo,
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as erro:
            if erro.code != 401 or i == len(lista) - 1:
                raise
            print("::warning::PERFIL_TOKEN inválido ou expirado; usando só dados públicos.")


CONSULTA = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount contributionLevel } }
      }
    }
  }
}"""


def buscar_calendario(usuario, token):
    corpo = json.dumps({"query": CONSULTA, "variables": {"login": usuario}}).encode()
    dados = consultar(corpo, token)
    if "errors" in dados:
        raise SystemExit(dados["errors"])
    cal = dados["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    return [s["contributionDays"] for s in cal["weeks"]], cal["totalContributions"]


def fmt(n):
    if isinstance(n, str):
        return n
    texto = f"{n:.2f}".rstrip("0").rstrip(".")
    return "0" if texto in ("-0", "") else texto


# ---------------------------------------------------------------- linha do tempo (keyframes)

class Canal:
    """Uma peça animada ao longo do ciclo: pontos (segundo, declaração CSS, curva do trecho).

    A curva de um ponto vale para o trecho até o ponto seguinte; sem curva, vale a do canal.
    """

    def __init__(self, nome, inicial, curva, css=None):
        self.nome, self.curva, self.css = nome, curva, css or (lambda v: v)
        self.inicial = self.atual = inicial
        self.pontos = [[0.0, self.css(inicial), None]]

    def ponto(self, t, decl, curva=None):
        ult = self.pontos[-1]
        if abs(ult[0] - t) < 1e-6:
            ult[1] = decl
            ult[2] = curva or ult[2]
        elif t < ult[0]:
            raise ValueError(f"{self.nome}: evento em {t:.2f}s antes do anterior ({ult[0]:.2f}s)")
        else:
            self.pontos.append([t, decl, curva])

    def valor(self, t, v, curva=None):
        self.ponto(t, self.css(v), curva)
        self.atual = v

    def ir(self, t, v, dur, curva=None):
        """Fica no valor atual até t e vai até v em dur segundos."""
        ult = self.pontos[-1]
        if abs(ult[0] - t) < 1e-6:
            ult[2] = curva
        else:
            self.ponto(t, self.css(self.atual), curva)
        self.valor(t + dur, v)

    def keyframes(self, ciclo):
        if self.atual != self.inicial:
            raise ValueError(f"{self.nome}: o ciclo não volta ao estado inicial")
        self.ponto(ciclo, self.pontos[0][1])
        quadros = []
        for t, decl, curva in self.pontos:
            pct = f"{100 * t / ciclo:.3f}".rstrip("0").rstrip(".")
            extra = f"; animation-timing-function: {curva}" if curva else ""
            quadros.append(f"  {pct}% {{ {decl}{extra} }}")
        return (f"@keyframes k-{self.nome} {{\n" + "\n".join(quadros) + "\n}\n"
                f".{self.nome} {{ animation: k-{self.nome} {ciclo:.2f}s {self.curva} infinite; }}")


def translate(v):
    return f"transform: translate({fmt(v[0])}px, {fmt(v[1])}px)"


def palpebra(v):
    return f"transform: translateX({fmt(v[0])}px) scaleY({fmt(v[1])})"


def passo(v):
    # Balanço da caminhada: sobe um pouco e inclina sobre a base do olho.
    cx, cy = OLHO_L / 2, OLHO_A
    return (f"transform: translate({fmt(cx)}px, {fmt(cy + v[0])}px) rotate({fmt(v[1])}deg) "
            f"translate({fmt(-cx)}px, {fmt(-cy)}px)")


def papel(x, y, r, opacidade=None):
    op = f"opacity: {opacidade}; " if opacidade is not None else ""
    return f"{op}transform: translate({x}px, {y}px) rotate({r}deg)"


# Cena dos papéis (7 s), copiada do site: três editais caem, o olho pisca a cada um, franze a
# pálpebra e a sobrancelha, olha para cima contrariado e arruma a pilha à direita.
PAPEIS_DUR = 7.0
PAPEIS_PALPEBRA = [(0, 0, 1), (8.5, 0, 1), (9.5, 0, .78), (11, 0, 1), (13.5, 0, 1),
                   (14.5, 0, .78), (16, 0, 1), (18.5, 0, 1), (19.5, 0, .72), (23, 0, .55),
                   (25, -4, .55), (27, 4, .55), (29, -2, .55), (31, 0, .55), (50, 0, .55),
                   (62, 0, .8), (70, 0, 1), (100, 0, 1)]
PAPEIS_IRIS = [(0, 0, 0), (4, 0, 0), (12, -6, -10), (22, 0, -16), (48, 0, -16), (56, 44, 2),
               (70, 44, 2), (80, 0, 0), (100, 0, 0)]
PAPEIS_SOBRANCELHA = [(0, 0, 0), (19, 0, 0), (24, 1, 24), (50, 1, 24), (62, 0, 0), (100, 0, 0)]
PAPEIS = [
    [(0, papel(170, -200, -35, 0), QUEDA), (1, "opacity: 1", None),
     (9, papel(176, -6, -17), "ease-out"), (10.5, papel(176, -11, -19), "ease-in"),
     (12, papel(176, -6, -17), "ease-in-out"), (50, papel(176, -6, -17), "ease-in-out"),
     (58, papel(400, 74, 0, 1), None), (88, papel(400, 74, 0, 1), None),
     (100, papel(400, 74, 0, 0), None)],
    [(0, papel(236, -210, 32, 0), QUEDA), (4, papel(236, -210, 32, 0), QUEDA),
     (5, "opacity: 1", None), (14, papel(218, -12, 14), "ease-out"),
     (15.5, papel(218, -17, 16), "ease-in"), (17, papel(218, -12, 14), "ease-in-out"),
     (55, papel(218, -12, 14), "ease-in-out"), (63, papel(402, 69, 0, 1), None),
     (88, papel(402, 69, 0, 1), None), (100, papel(402, 69, 0, 0), None)],
    [(0, papel(190, -220, -12, 0), QUEDA), (9, papel(190, -220, -12, 0), QUEDA),
     (10, "opacity: 1", None), (19, papel(198, -26, -5), "ease-out"),
     (20.5, papel(198, -31, -7), "ease-in"), (22, papel(198, -26, -5), "ease-in-out"),
     (60, papel(198, -26, -5), "ease-in-out"), (68, papel(404, 64, 0, 1), None),
     (88, papel(404, 64, 0, 1), None), (100, papel(404, 64, 0, 0), None)],
]

# Cena da leitura (6,4 s), copiada do relatório: um caderno de editais aparece, a íris lê
# linha a linha, pisca e olha para quem está lendo.
LEITURA_DUR = 6.4
LIVRO_FORA = "opacity: 0; transform: translate(200px, 250px) scale(.5)"
LIVRO_ABERTO = "opacity: 1; transform: translate(200px, 205px) scale(1)"
LEITURA_LIVRO = [(0, LIVRO_FORA), (10, LIVRO_ABERTO), (84, LIVRO_ABERTO), (100, LIVRO_FORA)]
LEITURA_IRIS = [(0, 0, 0), (8, 0, 0), (12, -36, 14), (24, 34, 14), (27, -36, 20), (39, 34, 20),
                (42, -36, 26), (54, 30, 26), (60, 0, -6), (72, 0, -6), (78, -20, 18), (90, 0, 0),
                (100, 0, 0)]
LEITURA_PALPEBRA = [(0, 1), (8, 1), (12, .8), (56, .8), (60, 1), (64, .08), (67, 1), (100, 1)]


def paradas(largura):
    """Onde o olho para (canto superior esquerdo do olho na figura)."""
    return {
        "meio": (largura / 2 - OLHO_L / 2, 34),
        "direita": (largura - OLHO_L - 40, 30),   # olha os dias mais recentes
        "papeis": (largura * .36, 40),           # a pilha vai para a direita do olho
        "leitura": (36, 32),
        "encontro": (largura * .6, 36),          # o amigo chega pela direita
    }


def roteiro(largura, alvos):
    """Monta o ciclo inteiro e devolve (duração, canais). `alvos`: três células (cx, cy) ou None."""
    p = paradas(largura)
    canais = {}

    def canal(nome, inicial, curva, css=None):
        canais[nome] = Canal(nome, inicial, curva, css)
        return canais[nome]

    anda = canal("anda", p["meio"], ANDAR, translate)
    balanco = canal("passo", (0, 0), "ease-in-out", passo)
    iris = canal("iris", (0, 0), OLHAR, translate)
    pal = canal("palpebra", (0, 1), "linear", palpebra)
    sobr = canal("sobrancelha", (0, 0), "ease-in-out",
                 lambda v: f"opacity: {fmt(v[0])}; transform: translateY({fmt(v[1])}px)")
    folhas = [canal(f"papel-{k + 1}", quadros[0][1], "ease") for k, quadros in enumerate(PAPEIS)]
    livro = canal("livro", LIVRO_FORA, OLHAR)
    amigo = canal("amigo", 0, "ease", lambda v: f"opacity: {fmt(v)}")
    amigo_x = canal("amigo-x", 60, OLHAR, lambda v: f"transform: translateX({fmt(v)}px)")
    amigo_iris = canal("amigo-iris", (-40, 0), OLHAR, translate)
    amigo_pal = canal("amigo-palpebra", (0, 1), "linear", palpebra)
    marcas = {}
    for k, alvo in enumerate(alvos):
        if alvo:
            marcas[k] = (canal(f"alvo-{k}", 0, "ease-out", lambda v: f"opacity: {fmt(v)}"),
                         canal(f"onda-{k}", (0, 1), "linear",
                               lambda v: f"opacity: {fmt(v[0])}; transform: scale({fmt(v[1])})"))

    pos = p["meio"]

    def olhar(t, v, olho=iris):
        olho.ir(t, v, .45)

    def piscar(t, quem=pal):
        quem.ir(t, (0, .06), .135, "ease-in-out")
        quem.ir(t + .165, (0, 1), .135, "ease-in-out")

    def andar(t, destino):
        """Anda até o destino olhando para onde vai; devolve o instante em que a íris se acalma."""
        nonlocal pos
        dx, dy = destino[0] - pos[0], destino[1] - pos[1]
        dist = math.hypot(dx, dy) or 1
        dur = 2.2 + dist / 260
        olhar(t, (dx / dist * 40, dy / dist * 20))
        anda.ir(t, destino, dur)
        passos = max(2, round(dur / .5))
        for i in range(passos):
            meio_passo = dur / passos / 2
            balanco.ir(t + 2 * i * meio_passo, (-3.5, 2.5 if i % 2 == 0 else -2.5), meio_passo)
            balanco.ir(t + (2 * i + 1) * meio_passo, (0, 0), meio_passo)
        pos = destino
        olhar(t + dur + .1, (0, 0))
        return t + dur + .55

    def mirar(t, k):
        """Olha para a célula k e a faz acender como um ponto no radar."""
        alvo = alvos[k]
        if not alvo:
            olhar(t, (-18, 20))
            return
        ex, ey = pos[0] + OLHO_L / 2, pos[1] + OLHO_A / 2
        dx, dy = alvo[0] - ex, alvo[1] - ey
        dist = math.hypot(dx, dy) or 1
        olhar(t, (dx / dist * 44, dy / dist * 22))
        borda, onda = marcas[k]
        borda.ir(t + .45, 1, .25)
        borda.ir(t + 2.1, 0, .35)
        for inicio in (t + .45, t + 1.25):
            onda.ir(inicio, (.9, 1), .02)
            onda.ir(inicio + .02, (0, 2.8), .75, "ease-out")
            onda.valor(inicio + .8, (0, 1))

    def cena(canal_, inicio, dur, quadros, css, curva=None):
        for q in quadros:
            canal_.valor(inicio + q[0] / 100 * dur, css(q[1:]), curva)

    t = .5
    # 1. Vai à direita e olha os dias mais recentes, com piscadas e olhadas em volta.
    t = andar(t, p["direita"])
    piscar(t + .3)
    mirar(t + .7, 0)
    olhar(t + 2.9, (-34, -12))
    piscar(t + 3.6)
    olhar(t + 4.0, (30, -14))
    mirar(t + 4.8, 1)
    olhar(t + 7.0, (0, 0))
    # 2. Cena dos papéis.
    t = andar(t + 7.6, p["papeis"])
    s = t + .2
    cena(pal, s, PAPEIS_DUR, PAPEIS_PALPEBRA, tuple)
    cena(iris, s, PAPEIS_DUR, PAPEIS_IRIS, tuple, "ease-in-out")
    cena(sobr, s, PAPEIS_DUR, PAPEIS_SOBRANCELHA, tuple)
    for folha, quadros in zip(folhas, PAPEIS):
        folha.ponto(s, quadros[0][1], quadros[0][2])
        for pct, decl, curva in quadros[1:]:
            folha.ponto(s + pct / 100 * PAPEIS_DUR, decl, curva)
        folha.ponto(s + PAPEIS_DUR + .02, folha.inicial)  # volta ao alto, invisível
    # 3. Cena da leitura.
    t = andar(s + PAPEIS_DUR + .4, p["leitura"])
    s = t + .2
    for pct, decl in LEITURA_LIVRO:
        livro.ponto(s + pct / 100 * LEITURA_DUR, decl)
    cena(iris, s, LEITURA_DUR, LEITURA_IRIS, tuple, "ease-in-out")
    cena(pal, s, LEITURA_DUR, LEITURA_PALPEBRA, lambda v: (0, v[0]))
    # 4. Encontro: o olho dourado chega pela direita, os dois se olham, piscam e olham o leitor.
    t = andar(s + LEITURA_DUR + .3, p["encontro"])
    s = t + .2
    amigo.ir(s, 1, .6)
    amigo_x.ir(s, 0, 1.1)
    olhar(s, (44, 0))
    piscar(s + 1.5)
    piscar(s + 2.1, amigo_pal)
    olhar(s + 2.7, (-40, -14), amigo_iris)
    olhar(s + 2.7, (44, -10))
    olhar(s + 3.3, (0, 8), amigo_iris)
    olhar(s + 3.3, (0, 8))
    piscar(s + 4.3)
    piscar(s + 4.3, amigo_pal)
    olhar(s + 5.0, (-40, 0), amigo_iris)
    olhar(s + 5.0, (40, 0))
    amigo.ir(s + 5.6, 0, .6)
    amigo_x.ir(s + 5.6, 60, 1.1)
    olhar(s + 5.6, (40, 0), amigo_iris)
    amigo_iris.valor(s + 6.8, (-40, 0))  # já invisível
    olhar(s + 6.8, (0, 0))
    # 5. Volta ao meio e procura mais um dia na grade.
    t = andar(s + 7.4, p["meio"])
    piscar(t + .2)
    mirar(t + .6, 2)
    olhar(t + 2.9, (-24, 10))
    piscar(t + 3.6)
    piscar(t + 3.98)
    olhar(t + 4.4, (0, 0))
    return t + 5.2, canais


# ---------------------------------------------------------------- desenho

def olho_svg():
    """O olho-radar (macro olho() do site), com sobrancelha, papéis e caderno das cenas."""
    papel_desenho = ('<rect x="-22" y="-28" width="44" height="56" rx="3"/>'
                     '<path d="M-13 -17 H13 M-13 -8 H13 M-13 1 H13 M-13 10 H6"/>')
    folhas = "".join(f'<g class="papel papel-{k}">{papel_desenho}</g>' for k in (1, 2, 3))
    return f"""<svg x="0" y="0" width="{fmt(OLHO_L)}" height="{fmt(OLHO_A)}" viewBox="0 0 400 200" overflow="visible">
        <defs><clipPath id="recorte"><path d="{CONTORNO}"/></clipPath></defs>
        <g class="palpebra">
          <path class="contorno" d="{CONTORNO}" filter="url(#sombra)"/>
          <g clip-path="url(#recorte)">
            <g class="iris">
              <g transform="translate(200 100)">
                <g class="aneis"><circle r="60"/><circle r="46"/><circle r="32"/><circle r="18"/></g>
                <path class="mira" d="M-60 0 H60 M0 -60 V60"/>
                <g class="varredura">
                  <circle r="60" fill="none" stroke="none"/>
                  <path d="M0 0 L-45.96 -38.57 A60 60 0 0 1 0 -60 Z"/>
                  <path d="M0 0 L-25.36 -54.38 A60 60 0 0 1 0 -60 Z"/>
                  <path d="M0 0 L-10.42 -59.09 A60 60 0 0 1 0 -60 Z"/>
                  <line x2="0" y2="-60"/>
                </g>
                <circle class="ponto ponto-1" cx="32.9" cy="-19" r="3.2"/>
                <circle class="ponto ponto-2" cx="-12" cy="20.8" r="2.6"/>
                <circle class="pupila" r="7"/>
              </g>
            </g>
          </g>
        </g>
        <path class="sobrancelha" d="M118 2 Q200 30 282 2"/>
        {folhas}
        <g class="livro">
          <path class="pag" d="M0 -26 Q-42 -36 -84 -26 V26 Q-42 16 0 26 Z"/>
          <path class="pag" d="M0 -26 Q42 -36 84 -26 V26 Q42 16 0 26 Z"/>
          <path class="lin" d="M-72 -14 H-14 M-72 -2 H-14 M-72 10 H-30 M14 -14 H72 M14 -2 H72 M14 10 H56"/>
          <path class="lombada" d="M0 -26 V26"/>
        </g>
      </svg>
      <g class="amigo"><g class="amigo-x">
        <svg x="{fmt(OLHO_L + 4)}" y="{fmt(OLHO_A * .14)}" width="{fmt(AMIGO_L)}" height="{fmt(AMIGO_L / 2)}" viewBox="0 0 400 200" overflow="visible">
          <defs><clipPath id="recorte-amigo"><path d="{CONTORNO}"/></clipPath></defs>
          <g class="amigo-palpebra">
            <path class="contorno" d="{CONTORNO}" filter="url(#sombra)"/>
            <g clip-path="url(#recorte-amigo)">
              <g class="amigo-iris">
                <g transform="translate(200 100)">
                  <g class="aneis"><circle r="60"/><circle r="40"/><circle r="22"/></g>
                  <circle class="pupila" r="9"/>
                </g>
              </g>
            </g>
          </g>
        </svg>
      </g></g>"""


def estilo(c, ciclo, canais, inicio):
    animacoes = "\n".join(canal.keyframes(ciclo) for canal in canais.values())
    return f"""
    .contorno {{ fill: {c["fundo_olho"]}; stroke: {c["linha"]}; stroke-width: 6; stroke-linejoin: round; }}
    .aneis circle, .mira {{ fill: none; stroke: {c["linha"]}; stroke-width: 2; }}
    .aneis circle:first-child {{ stroke-width: 3.5; }}
    .mira {{ opacity: .45; }}
    .varredura path {{ fill: {c["ouro"]}; fill-opacity: .18; }}
    .varredura line {{ stroke: {c["ouro"]}; stroke-width: 3.5; stroke-linecap: round; }}
    .pupila, .ponto {{ fill: {c["ouro"]}; }}
    .pupila {{ stroke: {c["marinho"]}; stroke-width: 2; }}
    .palpebra, .amigo-palpebra {{ transform-origin: 200px 100px; }}
    .varredura {{ transform-box: fill-box; transform-origin: center; animation: gira 5s linear infinite; }}
    .ponto {{ opacity: 0; animation: acende 10s linear infinite; }}
    .ponto-1 {{ animation-delay: .83s; }}
    .ponto-2 {{ animation-delay: 7.92s; }}
    @keyframes gira {{ to {{ transform: rotate(1turn); }} }}
    @keyframes acende {{ 0% {{ opacity: 0; }} 2% {{ opacity: 1; }} 45%, 100% {{ opacity: 0; }} }}
    .sobrancelha {{ fill: none; stroke: {c["linha"]}; stroke-width: 9; stroke-linecap: round; opacity: 0; }}
    .papel {{ opacity: 0; }}
    .papel rect {{ fill: {c["papel"]}; stroke: {c["ouro"]}; stroke-width: 2.5; }}
    .papel path {{ fill: none; stroke: {c["papel_linha"]}; stroke-width: 3; stroke-linecap: round; }}
    .livro {{ opacity: 0; }}
    .livro .pag {{ fill: {c["papel"]}; stroke: {c["linha"]}; stroke-width: 3; stroke-linejoin: round; }}
    .livro .lin {{ fill: none; stroke: {c["papel_linha"]}; stroke-width: 2.5; stroke-linecap: round; }}
    .livro .lombada {{ stroke: {c["ouro"]}; stroke-width: 4; stroke-linecap: round; }}
    .amigo {{ opacity: 0; }}
    .amigo .contorno, .amigo .aneis circle {{ stroke: {c["amigo_linha"]}; }}
    .amigo .pupila {{ fill: {c["amigo_pupila"]}; }}
    .anda {{ transform: translate({fmt(inicio[0])}px, {fmt(inicio[1])}px); }}
    .alvo {{ opacity: 0; fill: none; stroke: {c["ouro"]}; stroke-width: 2; }}
    .onda {{ opacity: 0; fill: none; stroke: {c["ouro"]}; stroke-width: 1.5; transform-box: fill-box; transform-origin: center; }}
    .rotulo {{ font: 12px -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif; fill: {c["texto"]}; }}
{animacoes}
    @media (prefers-reduced-motion: reduce) {{
      * {{ animation: none !important; }}
      .varredura {{ transform: rotate(40deg); }}
      .ponto, .fixo {{ opacity: 1; }}
    }}
    """


def escolher_alvos(ativos, largura):
    """Três dias para o olho olhar: dois na parada da direita e um no meio (os de mais
    contribuições ao alcance de cada parada, sem repetir)."""
    p = paradas(largura)
    usados = []

    def melhor(parada, minimo_dx=0):
        cx = p[parada][0] + OLHO_L / 2
        perto = [a for a in ativos if abs(a["cx"] - cx) <= 240 and a not in usados
                 and all(abs(a["cx"] - u["cx"]) >= minimo_dx for u in usados)]
        if not perto:
            perto = [a for a in ativos if a not in usados]
        if not perto:
            return None
        escolhido = max(perto, key=lambda a: (a["contributionCount"], a["date"]))
        usados.append(escolhido)
        return escolhido

    return [melhor("direita"), melhor("direita", PASSO), melhor("meio")]


def gerar_svg(semanas, total, tema, usuario):
    largura = MARGEM_X * 2 + len(semanas) * PASSO - ESPACO
    fim_grade = TOPO_GRADE + 7 * PASSO - ESPACO
    altura = fim_grade + ALTURA_RODAPE

    celulas, ativos, inicios_mes = [], [], []
    for i, semana in enumerate(semanas):
        x = MARGEM_X + i * PASSO
        mes = int(semana[0]["date"][5:7])
        if not inicios_mes or inicios_mes[-1][1] != mes:
            inicios_mes.append((i, mes))
        for dia in semana:
            y = TOPO_GRADE + dia["weekday"] * PASSO
            nivel = NIVEL[dia["contributionLevel"]]
            celulas.append(f'<rect x="{x}" y="{y}" width="{CELULA}" height="{CELULA}" rx="2" '
                           f'fill="{tema["niveis"][nivel]}"/>')
            if dia["contributionCount"] > 0:
                ativos.append({**dia, "cx": x + CELULA / 2, "cy": y + CELULA / 2})

    # Nome do mês sobre a semana em que ele começa (o primeiro sai se o mês seguinte vier logo).
    if len(inicios_mes) > 1 and inicios_mes[1][0] - inicios_mes[0][0] < 3:
        inicios_mes.pop(0)
    meses = [f'<text class="rotulo" x="{MARGEM_X + i * PASSO}" y="{TOPO_GRADE - 7}">{MESES[mes - 1]}</text>'
             for i, mes in inicios_mes if i < len(semanas) - 2]

    alvos = escolher_alvos(ativos, largura)
    ciclo, canais = roteiro(largura, [(a["cx"], a["cy"]) if a else None for a in alvos])

    # Com movimento reduzido, fica marcado o dia de mais contribuições entre os escolhidos.
    maior = max((a for a in alvos if a), key=lambda a: a["contributionCount"], default=None)
    marcas = []
    for k, a in enumerate(alvos):
        if not a:
            continue
        fixo = " fixo" if a is maior else ""
        marcas.append(
            f'<rect class="alvo alvo-{k}{fixo}" x="{fmt(a["cx"] - 8)}" y="{fmt(a["cy"] - 8)}" '
            f'width="16" height="16" rx="4"/>'
            f'<circle class="onda onda-{k}" cx="{fmt(a["cx"])}" cy="{fmt(a["cy"])}" r="8"/>')

    # Rodapé: total à esquerda, legenda "menos ... mais" à direita.
    y_rot = fim_grade + 21
    palavra = "contribuição" if total == 1 else "contribuições"
    direita = largura - MARGEM_X
    legenda = [f'<text class="rotulo" x="{direita}" y="{y_rot}" text-anchor="end">mais</text>']
    x0 = direita - 32 - 5 * 13 + 3
    for n, cor in enumerate(tema["niveis"]):
        legenda.append(f'<rect x="{x0 + n * 13}" y="{y_rot - 10}" width="10" height="10" rx="2" fill="{cor}"/>')
    legenda.append(f'<text class="rotulo" x="{x0 - 6}" y="{y_rot}" text-anchor="end">menos</text>')
    numero = f"{total:,}".replace(",", ".")
    rodape = (f'<text class="rotulo" x="{MARGEM_X}" y="{y_rot}">{numero} {palavra} no último ano</text>'
              + "".join(legenda))

    inicio = paradas(largura)["meio"]
    sombra_cor, sombra_op = tema["sombra"]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="titulo">
  <title id="titulo">Olho-radar do Licita IA passeando sobre as contribuições de {usuario} no último ano</title>
  <style>{estilo(tema, ciclo, canais, inicio)}</style>
  <defs>
    <filter id="sombra" x="-20%" y="-30%" width="140%" height="180%">
      <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="{sombra_cor}" flood-opacity="{sombra_op}"/>
    </filter>
  </defs>
  {"".join(meses)}
  {"".join(celulas)}
  {"".join(marcas)}
  {rodape}
  <g class="anda"><g class="passo">
      {olho_svg()}
  </g></g>
</svg>
"""


def main():
    usuario, saida = sys.argv[1], Path(sys.argv[2])
    semanas, total = buscar_calendario(usuario, tokens())
    saida.mkdir(parents=True, exist_ok=True)
    for nome, tema in TEMAS.items():
        (saida / nome).write_text(gerar_svg(semanas, total, tema, usuario), encoding="utf-8")
        print(saida / nome)


if __name__ == "__main__":
    main()
