"""Gera assets/banner.svg com o nome em Montserrat ExtraBold embutida.

A fonte vai embutida (subset, só as letras do nome) porque o GitHub exibe o SVG
como imagem e imagens não carregam fontes externas.

Uso: python scripts/banner.py caminho/Montserrat[wght].ttf
"""
import base64
import io
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

NOME = "Tarsio Chiconi"
PESO = 800
SAIDA = Path(__file__).resolve().parent.parent / "assets" / "banner.svg"


def fonte_base64(caminho):
    fonte = TTFont(caminho)
    if "fvar" in fonte:
        fonte = instancer.instantiateVariableFont(fonte, {"wght": PESO})
    opcoes = subset.Options()
    opcoes.flavor = "woff"
    opcoes.layout_features = ["kern", "liga"]
    sub = subset.Subsetter(opcoes)
    sub.populate(text=NOME)
    sub.subset(fonte)
    fonte.flavor = "woff"
    buf = io.BytesIO()
    fonte.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


def main():
    fonte = fonte_base64(sys.argv[1])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="854" height="200" viewBox="0 0 854 200">
  <defs>
    <style>
      @font-face {{ font-family: "Nome"; src: url(data:font/woff;base64,{fonte}) format("woff"); }}
      .nome {{ font-family: "Nome", "Montserrat", sans-serif; font-size: 54px; letter-spacing: 3px;
               animation: entra 1.4s ease-out both; }}
      .linha {{ animation: risca 1.6s .5s ease-out both; }}
      @keyframes entra {{ from {{ opacity: 0; transform: translateY(12px); }} to {{ opacity: 1; transform: none; }} }}
      @keyframes risca {{ from {{ stroke-dashoffset: 220; }} to {{ stroke-dashoffset: 0; }} }}
    </style>
    <linearGradient id="fundo" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="#0f2027"/>
      <stop offset=".5" stop-color="#203a43"/>
      <stop offset="1" stop-color="#2c5364"/>
    </linearGradient>
    <linearGradient id="texto" x1="0" x2="0" y1="0" y2="1">
      <stop offset="0" stop-color="#ffffff"/>
      <stop offset="1" stop-color="#9fd8f5"/>
    </linearGradient>
  </defs>
  <path fill="url(#fundo)" d="M0 0H854V168C760 146 690 140 600 150S420 180 300 172 110 140 0 156Z"/>
  <path fill="#ffffff" opacity=".04" d="M0 172C140 150 260 160 400 176S660 186 854 160V200H0Z"/>
  <text class="nome" x="427" y="96" text-anchor="middle" fill="url(#texto)">{NOME}</text>
  <line class="linha" x1="317" x2="537" y1="122" y2="122" stroke="#2c9fd9" stroke-width="3"
        stroke-linecap="round" stroke-dasharray="220"/>
</svg>
"""
    SAIDA.parent.mkdir(exist_ok=True)
    SAIDA.write_text(svg, encoding="utf-8")
    print(f"{SAIDA} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
