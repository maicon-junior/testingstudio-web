"""
relatorio_pdf.py - Gera o laudo em PDF (A4), uma aba do site por secao.

O app monta o conteudo de cada aba como uma lista de BLOCOS e este modulo
desenha: titulos, paragrafos, quadros de numeros, tabelas que quebram linha
(com o cabecalho repetido em cada pagina), codigo, o grafo de fluxo de
controle, as reguas da fronteira, as barras das suites de mutacao e os
pareceres. Nada depende do navegador, por isso nao ha cortes nem deslocamentos.

Blocos aceitos (tuplas):
  ("h2", texto) ("h3", texto) ("p", texto) ("nota", texto)
  ("metricas", [(rotulo, valor), ...])
  ("tabela", DataFrame)
  ("codigo", texto)
  ("grafo", grafo, nos_cobertos, arestas_cobertas)
  ("regua", {"fronteira", "lado", "epsilon", "pontos": [(rotulo, valor, valido)], "invalido", "valido"})
  ("barras", [(nome, casos, ms, mortos, total)])
  ("parecer", titulo, veredito, texto, assinatura)
  ("ia", titulo, texto, rodape)
"""

import io
import math
import re
from decimal import Decimal
from pathlib import Path

from reportlab.graphics.shapes import Circle, Drawing, Line, Polygon, Rect, String, PolyLine
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, CondPageBreak, Flowable, Frame, KeepTogether, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle, XPreformatted)

PASTA_FONTES = Path(__file__).resolve().parent / "fontes_pdf"
LARGURA, ALTURA = A4
MARGEM_X, MARGEM_TOPO, MARGEM_BASE = 16 * mm, 20 * mm, 18 * mm
UTIL = LARGURA - 2 * MARGEM_X

TINTA = colors.HexColor("#131c28")
SUAVE = colors.HexColor("#536175")
LINHA = colors.HexColor("#d5dde8")
RELEVO = colors.HexColor("#eef3f9")
ZEBRA = colors.HexColor("#f7f9fc")
OK = colors.HexColor("#12803a")
RUIM = colors.HexColor("#bf322e")
ALERTA = colors.HexColor("#8a5a00")
VALIDO = colors.HexColor("#2a78d6")
INVALIDO = colors.HexColor("#eb6834")

COLUNAS_DE_CODIGO = {"Asserção", "Original", "Mutante (alterado)", "Comandos", "Comando", "Trecho", "Caminho",
                     "Caminho completo", "Nós percorridos", "Arestas percorridas"}
_NUMERO = re.compile(r"^-?[\d.]+(,\d+)?%?$|^NULL$|^—$")

_FONTES_PRONTAS = False


def _registrar_fontes() -> None:
    """DejaVu tem todos os simbolos do laudo (ε, ≤, ×, ✓, ✕, →)."""
    global _FONTES_PRONTAS
    if _FONTES_PRONTAS:
        return
    pdfmetrics.registerFont(TTFont("Texto", str(PASTA_FONTES / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("Texto-Negrito", str(PASTA_FONTES / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Codigo", str(PASTA_FONTES / "DejaVuSansMono.ttf")))
    from reportlab.lib.fonts import addMapping
    addMapping("Texto", 0, 0, "Texto")
    addMapping("Texto", 1, 0, "Texto-Negrito")
    addMapping("Texto", 0, 1, "Texto")
    addMapping("Texto", 1, 1, "Texto-Negrito")
    _FONTES_PRONTAS = True


def _esc(texto) -> str:
    return (str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _mistura(cor: str, outra: str, t: float) -> colors.Color:
    a = [int(cor[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(outra[i:i + 2], 16) for i in (1, 3, 5)]
    return colors.Color(*[(x + (y - x) * t) / 255 for x, y in zip(a, b)])


class _Estilos:
    def __init__(self, destaque: str):
        self.destaque = colors.HexColor(destaque)
        self.destaque_suave = _mistura(destaque, "#ffffff", 0.88)
        base = dict(fontName="Texto", textColor=TINTA)
        self.titulo = ParagraphStyle("titulo", fontSize=19, leading=23, spaceAfter=2, fontName="Texto-Negrito",
                                     textColor=TINTA)
        self.subtitulo = ParagraphStyle("subtitulo", fontSize=10, leading=13, textColor=SUAVE, fontName="Texto",
                                        spaceAfter=8)
        self.h2 = ParagraphStyle("h2", fontSize=13, leading=16, spaceBefore=10, spaceAfter=4,
                                 fontName="Texto-Negrito", textColor=TINTA)
        self.h3 = ParagraphStyle("h3", fontSize=10.5, leading=13, spaceBefore=7, spaceAfter=3,
                                 fontName="Texto-Negrito", textColor=self.destaque)
        self.p = ParagraphStyle("p", fontSize=9, leading=12.6, spaceAfter=5, **base)
        self.nota = ParagraphStyle("nota", fontSize=7.8, leading=10.4, spaceAfter=5, fontName="Texto",
                                   textColor=SUAVE)
        self.cel = ParagraphStyle("cel", fontSize=7.4, leading=9.2, **base)
        self.cel_num = ParagraphStyle("cel_num", parent=self.cel, alignment=TA_RIGHT)
        self.cel_cod = ParagraphStyle("cel_cod", parent=self.cel, fontName="Codigo", fontSize=6.8, leading=8.6)
        self.cab = ParagraphStyle("cab", fontSize=7, leading=8.6, fontName="Texto-Negrito", textColor=SUAVE)
        self.cab_num = ParagraphStyle("cab_num", parent=self.cab, alignment=TA_RIGHT)
        self.metrica_rot = ParagraphStyle("mrot", fontSize=7.4, leading=9, fontName="Texto", textColor=SUAVE)
        self.metrica_val = ParagraphStyle("mval", fontSize=14, leading=17, fontName="Texto-Negrito", textColor=TINTA)
        self.codigo = ParagraphStyle("codigo", fontName="Codigo", fontSize=7.2, leading=9.2, textColor=TINTA)


class _MarcaDaSecao(Flowable):
    """Invisivel: avisa ao cabecalho de qual aba e a pagina."""

    def __init__(self, nome: str):
        super().__init__()
        self.nome = nome

    def wrap(self, *_):
        return 0, 0

    def draw(self):
        self.canv._secao_atual = self.nome


# ==========================================================================
# Tabelas
# ==========================================================================
def _largura_texto(texto: str, fonte: str, tamanho: float) -> float:
    return pdfmetrics.stringWidth(texto, fonte, tamanho)


def _palavras_da_celula(valor: str):
    """Celulas de situacao (Aprovado, Reprovado...) nao podem quebrar: contam como uma palavra so."""
    curta = len(valor.strip()) <= 16 and _cor_do_estado(valor.strip()) is not None
    return [valor.strip()] if curta else valor.split()


def _larguras(textos, colunas, codigo, tamanho, numericas=()):
    """Larguras que cabem na pagina: cada coluna recebe o minimo (a maior palavra)
    e o que sobra e dividido conforme o tamanho natural do conteudo (texto antes de numero)."""
    minimos, naturais = [], []
    for j, coluna in enumerate(colunas):
        fonte = "Codigo" if coluna in codigo else "Texto"
        valores = [str(linha[j]) for linha in textos]
        palavras = [p for v in valores for p in _palavras_da_celula(v)] or [""]
        fonte_palavra = "Codigo" if coluna in codigo else "Texto-Negrito"
        maior_palavra = max([_largura_texto(p, fonte_palavra, tamanho) for p in palavras] +
                            [_largura_texto(p, "Texto-Negrito", tamanho - 0.4) for p in str(coluna).split()])
        natural = max([_largura_texto(v, "Texto-Negrito" if _cor_do_estado(v.strip()) else fonte, tamanho)
                       for v in valores] + [_largura_texto(str(coluna), "Texto-Negrito", tamanho - 0.4)])
        minimos.append(min(max(maior_palavra, 20) + 10, UTIL * 0.32))
        naturais.append(min(max(natural + 10, minimos[-1]), UTIL * 0.55))
    if sum(naturais) <= UTIL:
        sobra = UTIL - sum(naturais)
        pesos = [0 if j in numericas else n for j, n in enumerate(naturais)]
        if not sum(pesos):
            pesos = naturais
        return [n + sobra * p / sum(pesos) for n, p in zip(naturais, pesos)]
    if sum(minimos) >= UTIL:
        return [m * UTIL / sum(minimos) for m in minimos]
    sobra = UTIL - sum(minimos)
    extras = [max(n - m, 0) for n, m in zip(naturais, minimos)]
    total = sum(extras) or 1
    return [m + sobra * e / total for m, e in zip(minimos, extras)]


def _cor_do_estado(texto: str):
    if texto.startswith("✓") or texto in ("Morto", "Atendido"):
        return OK
    if texto.startswith("✕") or texto == "Reprovado":
        return RUIM
    if texto.startswith("!") or texto == "Vivo":
        return ALERTA
    return None


def tabela(df, est: _Estilos):
    if df is None or len(df) == 0:
        return Paragraph("Nada a mostrar.", est.nota)
    colunas = [str(c) for c in df.columns]
    textos = [["" if (v is None or (isinstance(v, float) and math.isnan(v))) else str(v) for v in linha]
              for linha in df.itertuples(index=False)]
    largas = len(colunas) > 9
    tamanho = 6.6 if largas else 7.4
    while tamanho > 5.4:
        minimo_total = sum(min(max(max([_largura_texto(p, "Texto-Negrito", tamanho) for l in textos
                                          for p in _palavras_da_celula(str(l[j]))] + [0]), 20) + 10, UTIL * 0.32)
                           for j in range(len(colunas)))
        if minimo_total <= UTIL:
            break
        tamanho -= 0.4
    cel = ParagraphStyle("c", parent=est.cel, fontSize=tamanho, leading=tamanho * 1.24)
    cel_num = ParagraphStyle("cn", parent=cel, alignment=TA_RIGHT)
    cel_cod = ParagraphStyle("cc", parent=est.cel_cod, fontSize=tamanho - 0.6, leading=(tamanho - 0.6) * 1.26)
    numericas = {j for j in range(len(colunas))
                 if all(_NUMERO.match(l[j].strip()) or not l[j].strip() for l in textos) and any(l[j].strip() for l in textos)}
    larguras = _larguras(textos, colunas, COLUNAS_DE_CODIGO, tamanho, numericas)
    cab = ParagraphStyle("cb", parent=est.cab, fontSize=tamanho - 0.4, leading=(tamanho - 0.4) * 1.22)
    cab_num = ParagraphStyle("cbn", parent=cab, alignment=TA_RIGHT)
    dados = [[Paragraph(_esc(c), cab_num if j in numericas else cab) for j, c in enumerate(colunas)]]
    estilo = [("BACKGROUND", (0, 0), (-1, 0), RELEVO), ("LINEBELOW", (0, 0), (-1, 0), 0.8, LINHA),
              ("LINEBELOW", (0, 1), (-1, -1), 0.35, LINHA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
              ("TOPPADDING", (0, 0), (-1, -1), 3.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),
              ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
              ("BOX", (0, 0), (-1, -1), 0.6, LINHA)]
    for i, linha in enumerate(textos, start=1):
        celulas = []
        for j, valor in enumerate(linha):
            estilo_cel = cel_num if j in numericas else (cel_cod if colunas[j] in COLUNAS_DE_CODIGO else cel)
            cor = _cor_do_estado(valor.strip())
            texto = _esc(valor)
            if cor is not None:
                texto = f'<font color="{cor.hexval()}"><b>{texto}</b></font>'
            celulas.append(Paragraph(texto, estilo_cel))
        dados.append(celulas)
        if i % 2 == 0:
            estilo.append(("BACKGROUND", (0, i), (-1, i), ZEBRA))
    t = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
    t.setStyle(TableStyle(estilo))
    return t


def _metricas(itens, est: _Estilos):
    por_linha = 4 if len(itens) != 5 else 5
    linhas, estilo = [], []
    for k in range(0, len(itens), por_linha):
        grupo = itens[k:k + por_linha]
        linhas.append([[Paragraph(_esc(r), est.metrica_rot), Paragraph(_esc(v), est.metrica_val)] for r, v in grupo]
                      + [""] * (por_linha - len(grupo)))
    largura = UTIL / por_linha
    t = Table(linhas, colWidths=[largura] * por_linha, hAlign="LEFT")
    for i, linha in enumerate(linhas):
        for j, celula in enumerate(linha):
            if celula != "":
                estilo.append(("BACKGROUND", (j, i), (j, i), est.destaque_suave))
                estilo.append(("BOX", (j, i), (j, i), 2.5, colors.white))
    estilo += [("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 6),
               ("BOTTOMPADDING", (0, 0), (-1, -1), 6), ("LEFTPADDING", (0, 0), (-1, -1), 7)]
    t.setStyle(TableStyle(estilo))
    return t


def _codigo(texto: str, est: _Estilos):
    """Codigo com quebra das linhas longas (sem cortar nada na margem)."""
    limite = int(UTIL / pdfmetrics.stringWidth("M", "Codigo", 7.2)) - 2
    linhas = []
    for linha in texto.split("\n"):
        while len(linha) > limite:
            linhas.append(linha[:limite])
            linha = "      ↳ " + linha[limite:]
        linhas.append(linha)
    caixa = Table([[XPreformatted(_esc("\n".join(linhas)), est.codigo)]], colWidths=[UTIL])
    caixa.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), RELEVO), ("BOX", (0, 0), (-1, -1), 0.5, LINHA),
                               ("LEFTPADDING", (0, 0), (-1, -1), 7), ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return caixa


def _cartao(conteudo, est: _Estilos, cor_borda=None):
    t = Table([[conteudo]], colWidths=[UTIL])
    estilo = [("BOX", (0, 0), (-1, -1), 0.6, LINHA), ("LEFTPADDING", (0, 0), (-1, -1), 9),
              ("RIGHTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7),
              ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]
    if cor_borda is not None:
        estilo.append(("LINEBEFORE", (0, 0), (0, -1), 3, cor_borda))
    t.setStyle(TableStyle(estilo))
    return t


def _parecer(titulo, veredito, texto, assinatura, est: _Estilos):
    cor = {"Aprovado": OK, "Aprovado com ressalvas": ALERTA, "Reprovado": RUIM}.get(veredito, SUAVE)
    partes = [Paragraph(f'<font color="{est.destaque.hexval()}"><b>{_esc(titulo)}</b></font>'
                        f'  ·  <font color="{cor.hexval()}"><b>{_esc(veredito)}</b></font>', est.p)]
    partes += [Paragraph(_esc(par), est.p) for par in texto.split("\n") if par.strip()]
    partes.append(Paragraph(_esc(assinatura), est.nota))
    return _cartao(partes, est, cor)


def _markdown_simples(texto: str, est: _Estilos):
    """O texto da IA vem em Markdown: titulos, listas e negrito viram paragrafos do PDF."""
    saida = []
    for linha in texto.split("\n"):
        bruta = linha.strip()
        if not bruta:
            continue
        conteudo = _esc(bruta.lstrip("#").strip() if bruta.startswith("#") else bruta)
        conteudo = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", conteudo)
        if bruta.startswith("#"):
            saida.append(Paragraph(f"<b>{conteudo}</b>", est.p))
        elif re.match(r"^([-*•]|\d+\.)\s", bruta):
            item = re.sub(r"^([-*•]|\d+\.)\s+", "", conteudo)
            marcador = bruta.split()[0] if bruta[0].isdigit() else "•"
            saida.append(Paragraph(item, ParagraphStyle("li", parent=est.p, leftIndent=12, bulletIndent=2),
                                   bulletText=marcador))
        else:
            saida.append(Paragraph(conteudo, est.p))
    return saida


# ==========================================================================
# Desenhos: grafo, regua e barras
# ==========================================================================
def _seta(d: Drawing, x1, y1, x2, y2, cor, tracejado=False, largura=1.0):
    d.add(Line(x1, y1, x2, y2, strokeColor=cor, strokeWidth=largura, strokeDashArray=[3, 2] if tracejado else None))
    ang = math.atan2(y2 - y1, x2 - x1)
    tam = 5.5
    p1 = (x2 - tam * math.cos(ang - 0.42), y2 - tam * math.sin(ang - 0.42))
    p2 = (x2 - tam * math.cos(ang + 0.42), y2 - tam * math.sin(ang + 0.42))
    d.add(Polygon([x2, y2, p1[0], p1[1], p2[0], p2[1]], fillColor=cor, strokeColor=cor, strokeWidth=0.5))


def desenho_do_grafo(grafo, nos_cobertos, arestas_cobertas, est: _Estilos):
    """Grafo de fluxo de controle em camadas: de cima (entrada) para baixo (saida).
    Losango = no predicativo; circulo duplo = saida; tracejado laranja = nao coberto."""
    nos = grafo["nos"]
    arestas = grafo["arestas"]
    entrada = grafo["entrada"]
    saindo = {}
    for indice, (a, b, _) in enumerate(arestas):
        saindo.setdefault(a, []).append((b, indice))
    # arestas de volta (lacos): as que apontam para um no ainda na pilha da busca em profundidade
    de_volta, visitados, pilha = set(), set(), set()

    def busca(no):
        visitados.add(no)
        pilha.add(no)
        for destino, indice in sorted(saindo.get(no, [])):
            if destino in pilha:
                de_volta.add(indice)
            elif destino not in visitados:
                busca(destino)
        pilha.discard(no)

    busca(entrada)
    for no in sorted(nos):
        if no not in visitados:
            busca(no)
    camada = {n: 0 for n in nos}
    for _ in range(len(nos)):
        for indice, (a, b, _) in enumerate(arestas):
            if indice not in de_volta and camada[b] < camada[a] + 1:
                camada[b] = camada[a] + 1
    niveis = {}
    for n in sorted(nos):
        niveis.setdefault(camada[n], []).append(n)
    altura_nivel, raio = 44, 10.5
    altura = (max(niveis) + 1) * altura_nivel + 24
    d = Drawing(UTIL, altura)
    pos = {}
    for nivel, grupo in niveis.items():
        passo = UTIL / (len(grupo) + 1)
        for k, n in enumerate(grupo, 1):
            pos[n] = (passo * k, altura - 18 - nivel * altura_nivel)
    falta = colors.HexColor("#eb6834")
    pistas = {False: 0, True: 0}
    for indice, (a, b, rotulo) in enumerate(arestas):
        coberta = arestas_cobertas is None or indice in arestas_cobertas
        cor = est.destaque if coberta else falta
        (x1, y1), (x2, y2) = pos[a], pos[b]
        pula = camada[b] - camada[a] > 1
        if indice in de_volta or (x1 == x2 and y2 >= y1) or pula:
            # a pista passa por fora de todos os nos das camadas atravessadas
            entre = [pos[n][0] for n in nos if min(camada[a], camada[b]) <= camada[n] <= max(camada[a], camada[b])]
            direita = indice in de_volta or x1 > UTIL / 2
            pistas[direita] += 1
            afastamento = 22 + 9 * pistas[direita]
            meio_x = (max(entre) + afastamento) if direita else (min(entre) - afastamento)
            meio_x = min(max(meio_x, 8), UTIL - 8)
            d.add(PolyLine([x1 + (raio if meio_x > x1 else -raio), y1, meio_x, y1, meio_x, y2],
                           strokeColor=cor, strokeWidth=1, strokeDashArray=None if coberta else [3, 2]))
            _seta(d, meio_x, y2, x2 + (raio if meio_x > x2 else -raio), y2, cor, not coberta)
            texto_x, texto_y = meio_x + 3, (y1 + y2) / 2
        else:
            dist = math.hypot(x2 - x1, y2 - y1) or 1
            ux, uy = (x2 - x1) / dist, (y2 - y1) / dist
            _seta(d, x1 + ux * raio, y1 + uy * raio, x2 - ux * (raio + 1), y2 - uy * (raio + 1), cor, not coberta)
            texto_x, texto_y = (x1 + x2) / 2 + 4, (y1 + y2) / 2 + 2
        if rotulo:
            d.add(String(texto_x, texto_y, rotulo, fontName="Texto-Negrito", fontSize=7, fillColor=cor))
    for n, (x, y) in pos.items():
        no = nos[n]
        coberto = nos_cobertos is None or n in nos_cobertos
        cor = est.destaque if coberto else falta
        tracejado = None if coberto else [3, 2]
        if no["tipo"] == "decisao":
            r = raio + 2.5
            d.add(Polygon([x, y + r, x + r, y, x, y - r, x - r, y], fillColor=est.destaque_suave, strokeColor=cor,
                          strokeWidth=1.3, strokeDashArray=tracejado))
        else:
            d.add(Circle(x, y, raio, fillColor=colors.white, strokeColor=cor, strokeWidth=1.3,
                         strokeDashArray=tracejado))
            if no["tipo"] == "saida" or n == grafo["saida"]:
                d.add(Circle(x, y, raio - 2.6, fillColor=None, strokeColor=cor, strokeWidth=0.9))
        d.add(String(x, y - 3.2, str(n), fontName="Texto-Negrito", fontSize=8.5, fillColor=TINTA, textAnchor="middle"))
    xe, ye = pos[entrada]
    d.add(Circle(xe, ye + 17, 2.4, fillColor=TINTA, strokeColor=TINTA))
    _seta(d, xe, ye + 15, xe, ye + raio + 1, TINTA)
    return d


def _fmt(valor) -> str:
    if valor is None:
        return "NULL"
    casas = max(0, -valor.as_tuple().exponent) if isinstance(valor, Decimal) else 2
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def desenho_da_regua(dados, est: _Estilos):
    """Regua de uma fronteira em escala logaritmica dos dois lados (como no site)."""
    fronteira, lado, epsilon = dados["fronteira"], dados["lado"], float(dados["epsilon"])
    pontos = dados["pontos"]
    largura, altura, esq, dir_ = UTIL, 118, 26, 26
    c = epsilon / 5
    deslocamentos = [float(v - fronteira) for _, v, _ in pontos]
    maior = max([abs(x) for x in deslocamentos] + [epsilon]) * 4

    def f(x):
        return math.copysign(math.log10(1 + abs(x) / c), x)

    def X(x):
        return esq + (f(x) - f(-maior)) / (f(maior) - f(-maior)) * (largura - esq - dir_)

    d = Drawing(largura, altura)
    zero = X(0)
    cor_esq, cor_dir = (INVALIDO, VALIDO) if lado == "min" else (VALIDO, INVALIDO)
    d.add(Rect(X(-maior), 46, zero - X(-maior), 16, fillColor=cor_esq, strokeColor=None))
    d.add(Rect(zero, 46, X(maior) - zero, 16, fillColor=cor_dir, strokeColor=None))
    d.add(Line(zero, 40, zero, 68, strokeColor=TINTA, strokeWidth=1, strokeDashArray=[2, 2]))
    marcas, potencia = [0.0], epsilon
    while potencia <= maior:
        marcas += [potencia, -potencia]
        potencia = round(potencia * 10, 6)
    ultimo = -999.0
    for marca in sorted(marcas):
        x = X(marca)
        if x - ultimo < 30:
            continue
        ultimo = x
        valor = (fronteira + Decimal(str(marca))).quantize(Decimal(str(dados["epsilon"])))
        d.add(String(x, 32, _fmt(valor), fontName="Texto", fontSize=6.5, fillColor=SUAVE, textAnchor="middle"))
    ancoras = {"min": {"Off-Point": ("end", -6), "On-Point": ("start", 6)},
               "max": {"On-Point": ("end", -6), "Off-Point": ("start", 6)}}[lado]
    anterior, alto = None, False
    for (rotulo, valor, _), desl in sorted(zip(pontos, deslocamentos), key=lambda par: par[1]):
        x = X(desl)
        nome = rotulo.split(" (")[0]
        ancora, dx = ancoras.get(nome, ("middle", 0))
        alto = (not alto) if anterior is not None and x - anterior < 80 else False
        anterior = x
        y = 104 if alto else 86
        d.add(String(x + dx, y, nome, fontName="Texto-Negrito", fontSize=7.6, fillColor=TINTA, textAnchor=ancora))
        d.add(String(x + dx, y - 10, _fmt(valor), fontName="Texto", fontSize=7, fillColor=SUAVE, textAnchor=ancora))
        if alto:
            d.add(Line(x, y - 13, x, 60, strokeColor=LINHA, strokeWidth=0.6))
        d.add(Circle(x, 54, 4.4, fillColor=colors.white, strokeColor=TINTA, strokeWidth=1.3))
    texto_esq, texto_dir = ((dados["invalido"], dados["valido"]) if lado == "min" else
                            (dados["valido"], dados["invalido"]))
    d.add(Rect(esq - 10, 9, 6, 6, fillColor=cor_esq, strokeColor=None))
    d.add(String(esq, 9.5, texto_esq, fontName="Texto", fontSize=6.8, fillColor=SUAVE))
    d.add(Rect(largura - dir_ + 4, 9, 6, 6, fillColor=cor_dir, strokeColor=None))
    d.add(String(largura - dir_, 9.5, texto_dir, fontName="Texto", fontSize=6.8, fillColor=SUAVE, textAnchor="end"))
    return d


def desenho_das_barras(linhas, est: _Estilos):
    """Escore de mutacao de cada suite, em barras horizontais."""
    altura_linha = 22
    d = Drawing(UTIL, altura_linha * len(linhas) + 6)
    x_barra, larg_barra = UTIL * 0.36, UTIL * 0.44
    for k, (nome, casos, ms, mortos, total) in enumerate(linhas):
        y = d.height - (k + 1) * altura_linha + 4
        d.add(String(0, y + 6, nome, fontName="Texto-Negrito", fontSize=7.8, fillColor=TINTA))
        d.add(String(0, y - 2.5, f"{casos} caso{'s' if casos != 1 else ''}", fontName="Texto", fontSize=6.6,
                     fillColor=SUAVE))
        d.add(Rect(x_barra, y + 1, larg_barra, 8, fillColor=RELEVO, strokeColor=None, rx=4, ry=4))
        cor = OK if (ms or 0) >= 100 else (ALERTA if (ms or 0) >= 80 else RUIM)
        if ms:
            d.add(Rect(x_barra, y + 1, larg_barra * min(ms, 100) / 100, 8, fillColor=cor, strokeColor=None, rx=4, ry=4))
        texto = "—" if not casos or ms is None else f"{ms:.1f}%".replace(".", ",")
        d.add(String(UTIL, y + 6, texto, fontName="Texto-Negrito", fontSize=8, fillColor=TINTA, textAnchor="end"))
        d.add(String(UTIL, y - 2.5, f"{mortos} de {total} mortos", fontName="Texto", fontSize=6.6, fillColor=SUAVE,
                     textAnchor="end"))
    return d


# ==========================================================================
# Documento
# ==========================================================================
def _blocos_para_fluxo(blocos, est: _Estilos):
    fluxo = []
    for bloco in blocos:
        tipo = bloco[0]
        if tipo == "h2":
            fluxo += [CondPageBreak(60 * mm), Paragraph(_esc(bloco[1]), est.h2)]
        elif tipo == "h3":
            fluxo += [CondPageBreak(35 * mm), Paragraph(_esc(bloco[1]), est.h3)]
        elif tipo == "p":
            fluxo.append(Paragraph(_esc(bloco[1]).replace("\n", "<br/>"), est.p))
        elif tipo == "nota":
            fluxo.append(Paragraph(_esc(bloco[1]), est.nota))
        elif tipo == "metricas":
            fluxo += [_metricas(bloco[1], est), Spacer(1, 6)]
        elif tipo == "tabela":
            fluxo += [tabela(bloco[1], est), Spacer(1, 7)]
        elif tipo == "codigo":
            fluxo += [_codigo(bloco[1], est), Spacer(1, 7)]
        elif tipo == "grafo":
            fluxo += [KeepTogether([desenho_do_grafo(bloco[1], bloco[2], bloco[3], est)]), Spacer(1, 6)]
        elif tipo == "regua":
            fluxo += [KeepTogether([desenho_da_regua(bloco[1], est)]), Spacer(1, 4)]
        elif tipo == "barras":
            fluxo += [KeepTogether([desenho_das_barras(bloco[1], est)]), Spacer(1, 6)]
        elif tipo == "parecer":
            fluxo += [_parecer(bloco[1], bloco[2], bloco[3], bloco[4], est), Spacer(1, 7)]
        elif tipo == "ia":
            conteudo = [Paragraph(f'<font color="{est.destaque.hexval()}"><b>{_esc(bloco[1])}</b></font>', est.p)]
            conteudo += _markdown_simples(bloco[2], est) + [Paragraph(_esc(bloco[3]), est.nota)]
            fluxo += [_cartao(conteudo, est, est.destaque), Spacer(1, 7)]
    return fluxo


def gerar_pdf(secoes, identificacao: dict, destaque: str = "#1a56b8", titulo: str = "Laudo de qualidade") -> bytes:
    """secoes: [(nome_da_aba, blocos)]. Cada aba comeca numa pagina nova."""
    _registrar_fontes()
    est = _Estilos(destaque)
    saida = io.BytesIO()
    rodape = f"{identificacao.get('arquivo', '')} · {identificacao.get('funcao', '')} · gerado em {identificacao.get('quando', '')}"

    def moldura(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(est.destaque)
        canvas.setLineWidth(1.6)
        canvas.line(MARGEM_X, ALTURA - 12 * mm, MARGEM_X + 22 * mm, ALTURA - 12 * mm)
        canvas.setFont("Texto-Negrito", 8)
        canvas.setFillColor(TINTA)
        canvas.drawString(MARGEM_X, ALTURA - 10.4 * mm, "TestingStudio")
        canvas.setFont("Texto", 8)
        canvas.setFillColor(SUAVE)
        canvas.drawRightString(LARGURA - MARGEM_X, ALTURA - 10.4 * mm,
                               f"{titulo} · {getattr(canvas, '_secao_atual', '')}")
        canvas.setStrokeColor(LINHA)
        canvas.setLineWidth(0.5)
        canvas.line(MARGEM_X, 12 * mm, LARGURA - MARGEM_X, 12 * mm)
        canvas.setFont("Texto", 7)
        canvas.drawString(MARGEM_X, 8.4 * mm, rodape[:130])
        canvas.drawRightString(LARGURA - MARGEM_X, 8.4 * mm, f"página {doc.page}")
        canvas.restoreState()

    doc = BaseDocTemplate(saida, pagesize=A4, leftMargin=MARGEM_X, rightMargin=MARGEM_X, topMargin=MARGEM_TOPO,
                          bottomMargin=MARGEM_BASE, title=f"{titulo} — {identificacao.get('funcao', '')}",
                          author="TestingStudio")
    quadro = Frame(MARGEM_X, MARGEM_BASE, UTIL, ALTURA - MARGEM_TOPO - MARGEM_BASE, id="corpo",
                   leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="pagina", frames=[quadro], onPageEnd=moldura)])

    ident = Table([[Paragraph(f"<b>{_esc(r)}</b><br/>{_esc(v)}", est.cel) for r, v in (
        ("Programa", identificacao.get("arquivo", "")), ("Função testada", identificacao.get("funcao", "")),
        ("Tamanho", identificacao.get("tamanho", "")), ("Analisado em", identificacao.get("quando", "")))]],
        colWidths=[UTIL * 0.32, UTIL * 0.3, UTIL * 0.14, UTIL * 0.24])
    ident.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.6, LINHA), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINHA),
                               ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                               ("LEFTPADDING", (0, 0), (-1, -1), 6)]))
    fluxo = []
    for k, (nome, blocos) in enumerate(secoes):
        if k:
            fluxo.append(PageBreak())
        fluxo += [_MarcaDaSecao(nome), Paragraph(_esc(nome), est.titulo),
                  Paragraph(f"{_esc(titulo)} · {_esc(identificacao.get('funcao', ''))}", est.subtitulo), ident,
                  Spacer(1, 8)]
        fluxo += _blocos_para_fluxo(blocos, est)
    doc.build(fluxo)
    return saida.getvalue()
