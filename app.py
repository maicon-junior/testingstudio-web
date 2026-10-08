"""
TestingStudio Web - Auditoria de teste do CAD0001 (Sprints 1 a 4)
Disciplina: Teste de Software I | Prof. Frank Piffer

  Sprint 1 - Caixa-preta: classes de equivalencia (PCE) e valor limite (AVL) com Epsilon.
  Sprint 2 - Caixa-branca: grafo de fluxo de controle, nos, arestas e V(G) de McCabe.
  Sprint 3 - Fluxo de dados (pares Def-Uso) e teste de mutacao (escore MS).
  Sprint 4 - Validacao com gabaritos das aulas, laboratorio de exercicios e pitch.

Este arquivo cuida da PAGINA (leitura do .txt, tabelas, graficos, Gemini).
Os calculos das Sprints 2 a 4 e o interpretador de 4GL ficam em motor.py.

Abrir no computador:  dois cliques em Abrir_TestingStudio.bat   (ou: python iniciar.py)
Publicar online:      veja o LEIA-ME.txt. A chave do Gemini fica no servidor, em "Secrets".
"""

import hashlib
import html
import json
import os
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

import motor

PASTA = Path(__file__).resolve().parent
ARQUIVO_EXEMPLO = "cad0001_item_calculo.txt"
FUNCAO_ALVO = "cad0001_calcula_valor"          # unidade sob teste
FRONTEIRA = Decimal("0.00")                    # limite da regra de negocio

# Caixa-preta parte da ESPECIFICACAO, nao do codigo. Estas quatro regras vem do
# manual do laboratorio (secoes 2 e 3) e sao o "oraculo" dos testes.
ESPECIFICACAO = [
    "A função recebe três parâmetros decimais monetários (val_param1, val_param2, val_param3).",
    "Parâmetro NULL é tratado como 0,00.",
    "Nenhum parâmetro pode ser negativo: se algum for menor que 0,00, a função retorna -1 (erro).",
    "Caso contrário, retorna (val_param1 × val_param2) + val_param3.",
]

# O primeiro e o modelo do manual; os outros entram se ele nao estiver liberado.
MODELOS = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]

REFERENCIAS = [
    ("DELAMARO, M. E.; MALDONADO, J. C.; JINO, M. Introdução ao Teste de Software. "
     "Rio de Janeiro: Elsevier, 2007.",
     "Base da disciplina: teste funcional (PCE e AVL), teste estrutural (GFC e critérios de "
     "cobertura), fluxo de dados e teste de mutação."),
    ("MYERS, G. J.; SANDLER, C.; BADGETT, T. The Art of Software Testing. 3. ed. "
     "Hoboken: John Wiley & Sons, 2011.",
     "Regra de montar um caso por classe inválida, para que uma falha não esconda outra."),
    ("WHITE, L. J.; COHEN, E. I. A domain strategy for computer program testing. "
     "IEEE Transactions on Software Engineering, v. SE-6, n. 3, p. 247-257, 1980.",
     "Origem dos pontos On e Off usados na análise de fronteira."),
    ("ISO/IEC/IEEE 29119-4:2021. Software and systems engineering — Software testing — "
     "Part 4: Test techniques.",
     "Definição normativa das técnicas e das medidas de cobertura de classes e de fronteiras."),
    ("ISTQB. Certified Tester Foundation Level Syllabus, v4.0, 2023.",
     "Vocabulário de caso de teste, resultado esperado e cobertura."),
    ("IBM. Informix 4GL Reference Manual — tipo de dado DECIMAL(p,s).",
     "Precisão e escala do tipo, de onde sai o Épsilon."),
    ("McCABE, T. J. A complexity measure. IEEE Transactions on Software Engineering, "
     "v. SE-2, n. 4, p. 308-320, 1976.",
     "Complexidade ciclomática V(G) e conjunto básico de caminhos independentes."),
    ("RAPPS, S.; WEYUKER, E. J. Selecting software test data using data flow information. "
     "IEEE Transactions on Software Engineering, v. SE-11, n. 4, p. 367-375, 1985.",
     "Critérios de fluxo de dados: todas-definições, todos-c-usos, todos-p-usos e todos-usos."),
    ("DeMILLO, R. A.; LIPTON, R. J.; SAYWARD, F. G. Hints on test data selection: help for the "
     "practicing programmer. Computer, v. 11, n. 4, p. 34-41, 1978.",
     "Teste de mutação: hipótese do programador competente e efeito de acoplamento."),
    ("BOURQUE, P.; FAIRLEY, R. E. (ed.). Guide to the Software Engineering Body of Knowledge "
     "(SWEBOK), version 3.0. IEEE Computer Society, 2014.",
     "Terminologia de verificação, validação e técnicas de teste."),
    ("PIFFER, F. Slides das aulas de Teste de Software I, de 26/08 a 30/09/2026.",
     "Notação do GFC, os três métodos de McCabe, pares DU, operadores de mutação e os "
     "exemplos usados na validação da ferramenta."),
    ("PIFFER, F. Manual de Laboratório — Sprint 1: TestingStudio Web. "
     "Teste de Software I, 2026.2.",
     "Especificação do CAD0001 e os quatro pontos de fronteira (Tabela 1)."),
]


# ==========================================================================
# PASSO 1 - Leitura do arquivo .txt
# ==========================================================================
def decodificar(dados: bytes) -> str:
    """Converte bytes em texto. Fontes Logix/4GL costumam vir em cp1252
    (acentos do Windows), por isso tentamos UTF-8 primeiro e depois cp1252."""
    for codificacao in ("utf-8-sig", "cp1252"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            continue
    return dados.decode("latin-1", errors="replace")


def registrar_fonte(nome: str, dados: bytes, origem: str, ident) -> None:
    """Guarda o arquivo lido na sessao, com dados de rastreabilidade
    (nome, tamanho, hash e horario) para a aba Fontes."""
    texto = decodificar(dados)
    st.session_state.update({
        "fonte_nome": nome,
        "fonte_origem": origem,
        "fonte_ident": ident,
        "fonte_original": texto,
        "fonte_editado": texto,          # conteudo da caixa de texto
        "fonte_bytes": len(dados),
        "fonte_sha": hashlib.sha256(dados).hexdigest(),
        "fonte_quando": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    })
    st.session_state.pop("parecer", None)


def esquecer_fonte() -> None:
    for chave in [c for c in st.session_state if c.startswith("fonte_")]:
        del st.session_state[chave]
    st.session_state.pop("parecer", None)


# ==========================================================================
# PASSO 2 - Oraculo, classes de equivalencia e casos de teste
# ==========================================================================
def oraculo(entradas, epsilon) -> Decimal:
    """Resultado ESPERADO segundo a especificacao (nao olha o codigo)."""
    valores = [Decimal(0) if v is None else v for v in entradas]
    if any(v < 0 for v in valores):
        return Decimal(-1).quantize(epsilon)
    return ((valores[0] * valores[1]) + valores[2]).quantize(epsilon, ROUND_HALF_UP)


def classe_de(valor) -> str:
    """Classe de equivalencia a que um valor de entrada pertence."""
    if valor is None:
        return "Inválida (nulo)"
    return "Inválida (negativo)" if valor < FRONTEIRA else "Válida"


def ponto_de(valor, epsilon) -> str:
    """Ponto de fronteira (AVL) que um valor representa."""
    if valor is None:
        return ""
    if valor == FRONTEIRA:
        return "On-Point"
    if valor == FRONTEIRA - epsilon:
        return "Off-Point"
    return "Interior" if valor > FRONTEIRA else "Exterior"


PONTOS = ["On-Point", "Off-Point", "Interior", "Exterior"]
CLASSES = ["Válida", "Inválida (negativo)", "Inválida (nulo)"]

ACHADOS = {
    "NEGATIVO_ACEITO": ("Valor negativo aceito",
                        "A especificação manda retornar -1 quando algum parâmetro é negativo, "
                        "mas a função fez o cálculo normalmente."),
    "VALIDO_REJEITADO": ("Valor válido rejeitado",
                         "A função retornou -1 para uma entrada permitida. Causa provável: "
                         "comparação com <= no lugar de <."),
    "NULO": ("Nulo não tratado como 0,00",
             "A função devolveu NULL em vez de tratar o parâmetro nulo como 0,00."),
    "CALCULO": ("Resultado diferente da fórmula",
                "O valor devolvido não corresponde a (val_param1 × val_param2) + val_param3."),
    "ERRO": ("Erro na execução", "A função não chegou a devolver um resultado."),
}


def montar_caso(ident, tecnica, alvo, rotulo, entradas, programa, epsilon, maximo, descricao=""):
    """Executa um caso de teste e compara o obtido com o esperado."""
    esperado = oraculo(entradas, epsilon)
    execucao = motor.executar_funcao(programa, entradas, epsilon)
    obtido, erro = execucao["valor"], execucao["erro"]

    achado, observacao = "", descricao
    if abs(esperado) > maximo:
        status = "Sem oráculo"
        observacao = "O resultado passa do maior valor do tipo; a especificação não define esse caso."
    elif erro:
        status, achado, observacao = "Reprovado", "ERRO", erro
    elif obtido == esperado:
        status = "Aprovado"
    else:
        status = "Reprovado"
        if obtido is None:
            achado = "NULO"
        elif esperado == -1:
            achado = "NEGATIVO_ACEITO"
        elif obtido == -1:
            achado = "VALIDO_REJEITADO"
        else:
            achado = "CALCULO"
    return {"id": ident, "tecnica": tecnica, "alvo": alvo, "rotulo": rotulo,
            "entradas": list(entradas), "esperado": esperado, "obtido": obtido,
            "erro": erro, "status": status, "achado": achado, "observacao": observacao}


def gerar_suite_base(programa, epsilon, maximo, nominal, interior, exterior):
    """Suite planejada: para cada parametro, os 4 pontos da AVL e a classe nula.
    Um parametro varia por vez; os outros ficam no valor nominal (valido).
    Assim, se um teste falhar, sabemos qual parametro causou a falha."""
    nomes = programa["parametros"]
    pontos = [("On-Point", FRONTEIRA), ("Off-Point", FRONTEIRA - epsilon),
              ("Interior", interior), ("Exterior", exterior)]
    casos = []
    for i, nome in enumerate(nomes):
        for rotulo, valor in pontos:
            entradas = [nominal] * 3
            entradas[i] = valor
            casos.append(montar_caso(f"CT{len(casos) + 1:02d}", "AVL", nome, rotulo,
                                     entradas, programa, epsilon, maximo))
    for i, nome in enumerate(nomes):
        entradas = [nominal] * 3
        entradas[i] = None
        casos.append(montar_caso(f"CT{len(casos) + 1:02d}", "PCE", nome, "Nulo",
                                 entradas, programa, epsilon, maximo))
    return casos


def gerar_casos_extras(tabela: pd.DataFrame, programa, epsilon, maximo):
    """Converte as linhas digitadas na aba 'Testes extras' em casos de teste."""
    casos = []
    for _, linha in tabela.iterrows():
        entradas = []
        for coluna in ("p1", "p2", "p3"):
            bruto = linha[coluna]
            if bruto is None or pd.isna(bruto):
                entradas.append(None)
            else:
                entradas.append(Decimal(str(bruto)).quantize(epsilon, ROUND_HALF_UP))
        descricao = "" if pd.isna(linha["descricao"]) else str(linha["descricao"]).strip()
        if all(v is None for v in entradas) and not descricao:
            continue                               # linha em branco
        casos.append(montar_caso(f"EX{len(casos) + 1:02d}", "Extra", "—", "Extra",
                                 entradas, programa, epsilon, maximo, descricao))
    return casos


def medir_qualidade(casos, nomes, epsilon):
    """Indicadores de qualidade do conjunto de testes (criterios de adequacao)."""
    classes_cobertas, pontos_cobertos = set(), set()
    for caso in casos:
        for nome, valor in zip(nomes, caso["entradas"]):
            classes_cobertas.add((nome, classe_de(valor)))
            if ponto_de(valor, epsilon):
                pontos_cobertos.add((nome, ponto_de(valor, epsilon)))
    achados = {}
    for caso in casos:
        if caso["achado"]:
            achados.setdefault(caso["achado"], []).append(caso["id"])
    return {
        "total": len(casos),
        "aprovados": sum(c["status"] == "Aprovado" for c in casos),
        "reprovados": sum(c["status"] == "Reprovado" for c in casos),
        "sem_oraculo": sum(c["status"] == "Sem oráculo" for c in casos),
        "classes": (len(classes_cobertas), len(nomes) * len(CLASSES)),
        "pontos": (len(pontos_cobertos), len(nomes) * len(PONTOS)),
        "classes_cobertas": classes_cobertas,
        "achados": achados,
    }


# ==========================================================================
# PASSO 3 - Apresentacao: formatos, tabelas e grafico
# ==========================================================================
def formato_br(valor) -> str:
    """Numero no padrao brasileiro (1.234,56). None vira NULL."""
    if valor is None:
        return "NULL"
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


ICONE = {"Aprovado": "✓", "Reprovado": "✕", "Sem oráculo": "–"}


def tabela_casos(casos, nomes) -> pd.DataFrame:
    linhas = []
    for c in casos:
        linha = {"Caso": c["id"], "Técnica": c["tecnica"], "Parâmetro variado": c["alvo"],
                 "Ponto ou classe": c["rotulo"]}
        for nome, valor in zip(nomes, c["entradas"]):
            linha[nome] = formato_br(valor)
        linha["Esperado"] = formato_br(c["esperado"])
        linha["Obtido"] = "erro" if c["erro"] else formato_br(c["obtido"])
        linha["Resultado"] = f"{ICONE[c['status']]} {c['status']}"
        linha["Observação"] = (ACHADOS[c["achado"]][0] if c["achado"] and not c["erro"]
                               else c["observacao"])
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabela_pce(casos, nomes, maximo) -> pd.DataFrame:
    """Classes de equivalencia de cada parametro e os casos que cobrem cada uma."""
    dominio = {"Válida": f"0,00 ≤ valor ≤ {formato_br(maximo)}",
               "Inválida (negativo)": "valor < 0,00",
               "Inválida (nulo)": "valor IS NULL"}
    esperado = {"Válida": "Cálculo (p1 × p2) + p3",
                "Inválida (negativo)": "Erro: retorna -1",
                "Inválida (nulo)": "Tratado como 0,00"}
    linhas = []
    for i, nome in enumerate(nomes):
        for classe in CLASSES:
            cobrem = [c["id"] for c in casos
                      if classe_de(c["entradas"][i]) == classe and c["alvo"] in (nome, "—")]
            linhas.append({"Parâmetro": nome, "Classe": classe, "Domínio": dominio[classe],
                           "Resultado esperado": esperado[classe],
                           "Casos que cobrem": ", ".join(cobrem) if cobrem else "nenhum"})
    return pd.DataFrame(linhas)


def tabela_pontos(epsilon, interior, exterior) -> pd.DataFrame:
    """Os 4 pontos da AVL em torno da fronteira 0,00 (Tabela 1 do manual)."""
    return pd.DataFrame([
        {"Ponto": "On-Point", "Valor": FRONTEIRA, "Condição da fronteira": "Exatamente na fronteira válida",
         "Resultado esperado": "Sucesso (cálculo)"},
        {"Ponto": "Off-Point", "Valor": FRONTEIRA - epsilon,
         "Condição da fronteira": "Primeiro ponto fora da fronteira (0,00 − ε)",
         "Resultado esperado": "Erro (-1)"},
        {"Ponto": "Interior", "Valor": interior, "Condição da fronteira": "Profundamente na região válida",
         "Resultado esperado": "Sucesso (cálculo)"},
        {"Ponto": "Exterior", "Valor": exterior, "Condição da fronteira": "Profundamente na região inválida",
         "Resultado esperado": "Erro (-1)"},
    ])


COR_VALIDA, COR_INVALIDA = "#2a78d6", "#eb6834"


def grafico_fronteira(pontos: pd.DataFrame, epsilon: Decimal) -> alt.LayerChart:
    """Regua da fronteira: regiao invalida a esquerda do 0,00 e valida a direita.
    A escala e 'symlog' (logaritmica dos dois lados do zero) para que 0,00 e
    -0,01 nao fiquem um em cima do outro, como ficariam numa escala comum."""
    dados = pontos.assign(valor=pontos["Valor"].astype(float),
                          texto=pontos["Valor"].map(formato_br)).drop(columns=["Valor"])
    maior = max(abs(dados["valor"].min()), abs(dados["valor"].max())) * 4
    escala = alt.Scale(type="symlog", constant=float(epsilon) / 5, domain=[-maior, maior], nice=False)

    marcas = [0.0]
    potencia = float(epsilon)
    while potencia <= maior:
        marcas += [potencia, -potencia]
        potencia = round(potencia * 10, 6)
    rotulos = " : ".join(f"abs(datum.value - ({m!r})) < 1e-9 ? '{formato_br(Decimal(str(m)))}'"
                         for m in marcas) + " : ''"

    regioes = pd.DataFrame([
        {"inicio": -maior, "fim": 0.0, "Região": "Inválida: valor < 0,00 (retorna -1)"},
        {"inicio": 0.0, "fim": maior, "Região": "Válida: valor ≥ 0,00 (calcula)"},
    ])
    eixo = alt.Axis(values=sorted(marcas), labelExpr=rotulos, labelOverlap="greedy", grid=False,
                    title="Valor do parâmetro (escala logarítmica dos dois lados do zero)")
    # Eixo vertical escondido, de 0 a 100, so para posicionar: rotulos em cima, faixa embaixo.
    altura = alt.Scale(domain=[0, 100], nice=False)

    def y(posicao):
        return alt.YDatum(posicao, scale=altura, axis=None)

    faixa = alt.Chart(regioes).mark_rect(cornerRadius=4).encode(
        x=alt.X("inicio:Q", scale=escala, axis=eixo), x2="fim:Q",
        y=y(8), y2=alt.Y2Datum(36),
        color=alt.Color("Região:N", legend=alt.Legend(orient="bottom", title=None, symbolType="square",
                                                      labelLimit=400),
                        scale=alt.Scale(domain=list(regioes["Região"]),
                                        range=[COR_INVALIDA, COR_VALIDA])),
        tooltip=["Região:N"])
    limite = alt.Chart(pd.DataFrame({"x": [0.0]})).mark_rule(strokeWidth=2, strokeDash=[4, 3]).encode(
        x=alt.X("x:Q", scale=escala), y=y(0), y2=alt.Y2Datum(48))
    dica = ["Ponto:N", alt.Tooltip("texto:N", title="Valor"), "Condição da fronteira:N", "Resultado esperado:N"]
    marcador = alt.Chart(dados).mark_point(size=190, filled=True, opacity=1, color="#1b2a3d",
                                           stroke="white", strokeWidth=2).encode(
        x=alt.X("valor:Q", scale=escala), y=y(22), tooltip=dica)

    def rotulo(filtro, alinhamento, dx):
        base = alt.Chart(dados).transform_filter(filtro).encode(x=alt.X("valor:Q", scale=escala))
        nome = base.mark_text(dx=dx, align=alinhamento, fontWeight="bold", fontSize=13).encode(
            text="Ponto:N", y=y(86))
        valor = base.mark_text(dx=dx, align=alinhamento, fontSize=13).encode(
            text="texto:N", y=y(68))
        return nome + valor

    camadas = (faixa + limite + marcador
               + rotulo("datum.Ponto == 'Off-Point'", "right", -8)
               + rotulo("datum.Ponto == 'On-Point'", "left", 8)
               + rotulo("datum.Ponto == 'Interior' || datum.Ponto == 'Exterior'", "center", 0))
    # No Streamlit a altura inclui o eixo e a legenda, por isso 215 e nao 120.
    return camadas.properties(height=215).configure_view(stroke=None)


def html_matriz(casos, nomes) -> str:
    """Matriz parametro x ponto: mostra de uma vez o que foi coberto e o resultado."""
    colunas = PONTOS + ["Nulo"]
    partes = ["<table class='ts-matriz'><thead><tr><th>Parâmetro</th>"]
    partes += [f"<th>{c}</th>" for c in colunas]
    partes.append("</tr></thead><tbody>")
    for nome in nomes:
        partes.append(f"<tr><th>{html.escape(nome)}</th>")
        for coluna in colunas:
            caso = next((c for c in casos if c["alvo"] == nome and c["rotulo"] == coluna), None)
            if caso is None:
                partes.append("<td><span class='ts-chip'>não testado</span></td>")
                continue
            classe = {"Aprovado": "ok", "Reprovado": "falha"}.get(caso["status"], "")
            partes.append(f"<td><span class='ts-chip {classe}'><b>{ICONE[caso['status']]}</b> "
                          f"{caso['status']}</span><small>{caso['id']}</small></td>")
        partes.append("</tr>")
    partes.append("</tbody></table>")
    return "".join(partes)


ESTILO = """
<style>
[data-testid="stMain"] h1 {font-size:2.5rem; letter-spacing:-.02em;}
[data-testid="stMain"] h2 {font-size:1.55rem; margin-top:.6rem;}
[data-testid="stMain"] h3 {font-size:1.15rem;}
[data-testid="stMetricValue"] {font-size:1.9rem;}
.ts-sub {font-size:1.05rem; margin:-.6rem 0 .5rem; max-width:62rem; opacity:.82;}
.ts-regua {height:13px; margin:0 0 1.2rem; opacity:.5; border-top:2px solid currentColor;
  background:
    repeating-linear-gradient(90deg, currentColor 0 1px, transparent 1px 60px) top left/100% 12px no-repeat,
    repeating-linear-gradient(90deg, currentColor 0 1px, transparent 1px 12px) top left/100% 6px no-repeat;}
.ts-matriz {width:100%; border-collapse:collapse; font-size:.92rem;}
.ts-matriz th, .ts-matriz td {padding:.55rem .7rem; text-align:left;
  border-bottom:1px solid rgba(128,128,128,.28);}
.ts-matriz thead th {font-weight:600; opacity:.75;}
.ts-matriz small {margin-left:.5rem; opacity:.6;}
.ts-chip {display:inline-block; padding:.12rem .55rem; border-radius:999px;
  border:1px solid rgba(128,128,128,.4); white-space:nowrap;}
.ts-chip.ok {border-color:#0ca30c; background:rgba(12,163,12,.10);}
.ts-chip.ok b {color:#0ca30c;}
.ts-chip.falha {border-color:#d03b3b; background:rgba(208,59,59,.10);}
.ts-chip.falha b {color:#d03b3b;}
.ts-ref {margin:0 0 .9rem; padding-left:1rem; border-left:3px solid rgba(128,128,128,.35);}
.ts-ref p {margin:0;} .ts-ref .uso {opacity:.72; font-size:.92rem;}
</style>
"""


def gerar_relatorio_html(d) -> str:
    """Relatorio completo (Sprints 1 a 4) em uma pagina HTML, pronta para
    apresentar ou imprimir em PDF pelo navegador (Ctrl+P)."""
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    cob, crit = a["cobertura"], a["criterios"]
    ok, total = d["validacao_resumo"]
    achados = "".join(
        f"<li><b>{html.escape(ACHADOS[cod][0])}</b> ({len(ids)} casos: {', '.join(ids)}). "
        f"{html.escape(ACHADOS[cod][1])}</li>" for cod, ids in q["achados"].items()
    ) or "<li>Nenhuma divergência: todos os casos com oráculo foram aprovados.</li>"
    referencias = "".join(f"<li>{html.escape(ref)}<br><small>{html.escape(uso)}</small></li>"
                          for ref, uso in REFERENCIAS)
    especificacao = "".join(f"<li>{html.escape(regra)}</li>" for regra in ESPECIFICACAO)
    parecer = (f"<h2>Parecer do Gemini ({html.escape(d['parecer_modelo'])})</h2>"
               f"<pre class='parecer'>{html.escape(d['parecer'])}</pre>") if d.get("parecer") else ""
    dot = json.dumps(motor.grafo_em_dot(a["grafo"], set(a["nos_cobertos"]), set(a["arestas_cobertas"]))
                     ).replace("</", "<\\/")

    def tabela(df):
        return df.to_html(index=False, border=0, classes="t", escape=True)

    def kpi(valor, rotulo):
        return f"<div class='kpi'><b>{valor}</b><span>{rotulo}</span></div>"

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatório de teste — CAD0001</title>
<style>
 body {{font-family:'Segoe UI',system-ui,sans-serif; color:#1b2a3d; margin:2.2rem auto; max-width:1000px; padding:0 1.2rem; line-height:1.5;}}
 h1,h2 {{font-family:'Cascadia Mono',Consolas,monospace; letter-spacing:-.01em;}}
 h1 {{font-size:1.7rem; margin-bottom:.2rem;}} h2 {{font-size:1.15rem; margin-top:2rem; border-top:2px solid #1b2a3d; padding-top:.6rem;}}
 h3 {{font-size:1rem; margin:1.2rem 0 .3rem;}}
 .meta {{color:#52606f; margin-top:0;}}
 .kpis {{display:flex; flex-wrap:wrap; gap:.8rem; margin:1.2rem 0;}}
 .kpi {{border:1px solid #c9d1da; border-radius:6px; padding:.6rem .9rem; min-width:130px;}}
 .kpi b {{display:block; font-size:1.5rem;}} .kpi span {{color:#52606f; font-size:.85rem;}}
 .destaque {{border-left:4px solid #1f4e79; background:#edf1f5; padding:.8rem 1rem; border-radius:0 6px 6px 0;}}
 table.t {{border-collapse:collapse; width:100%; font-size:.84rem; margin:.6rem 0;}}
 table.t th, table.t td {{border-bottom:1px solid #d5dbe2; padding:.35rem .5rem; text-align:left;}}
 table.t th {{background:#edf1f5;}} table.t td {{white-space:nowrap;}} table.t td:last-child {{white-space:normal;}}
 small, .nota {{color:#52606f;}} li {{margin-bottom:.35rem;}}
 #gfc {{text-align:center; margin:1rem 0;}} #gfc svg {{max-width:100%; height:auto;}}
 pre.parecer {{white-space:pre-wrap; font-family:inherit; background:#f4f6f8; padding:1rem; border-radius:6px;}}
 @media print {{ body {{margin:0; max-width:none;}} h2 {{break-after:avoid;}} tr {{break-inside:avoid;}} }}
</style></head><body>
<h1>Relatório de teste — CAD0001</h1>
<p class="meta">Função {FUNCAO_ALVO}: caixa-preta, caixa-branca, fluxo de dados e mutação. Teste de Software I, Prof. Frank Piffer.<br>
Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")} pelo TestingStudio Web</p>

<p class="destaque">{html.escape(d['achado'])}</p>

<h2>1. Objeto de teste e origem dos dados</h2>
{tabela(d['origem'])}

<h2>2. Sprint 1: caixa-preta (PCE e AVL)</h2>
<div class="kpis">{kpi(q['total'], 'casos executados')}{kpi(q['aprovados'], 'aprovados')}{kpi(q['reprovados'], 'reprovados')}
{kpi(f"{q['classes'][0]} de {q['classes'][1]}", 'classes de equivalência cobertas')}{kpi(f"{q['pontos'][0]} de {q['pontos'][1]}", 'pontos de fronteira cobertos')}{kpi(len(q['achados']), 'tipos de defeito revelados')}</div>
<h3>Achados</h3><ul>{achados}</ul>
<h3>Especificação usada como oráculo</h3><ol>{especificacao}</ol>
<h3>Particionamento em classes de equivalência</h3>
{tabela(d['pce'])}
<h3>Análise do valor limite e Épsilon</h3>
<p>{html.escape(d['justificativa'])}</p>
{tabela(d['pontos'])}
<h3>Casos de teste executados</h3>
{tabela(d['casos'])}

<h2>3. Sprint 2: caixa-branca (GFC e McCabe)</h2>
<div class="kpis">{kpi(m['N'], 'nós (N)')}{kpi(m['E'], 'arestas (E)')}{kpi(m['P'], 'nós predicativos (P)')}{kpi(m['R'], 'regiões (R)')}{kpi(m['V'], 'complexidade V(G)')}</div>
<ul>
 <li>Método 1, topológico: V(G) = E − N + 2 = {m['E']} − {m['N']} + 2 = <b>{m['v_topologico']}</b></li>
 <li>Método 2, lógico: V(G) = P + 1 = {m['P']} + 1 = <b>{m['v_logico']}</b></li>
 <li>Método 3, espacial: V(G) = R = {m['regioes_internas']} internas + 1 externa = <b>{m['v_espacial']}</b></li>
</ul>
<div id="gfc"><p class="nota">O desenho do grafo aparece quando o relatório é aberto com internet. A tabela de nós abaixo descreve o mesmo grafo.</p></div>
{tabela(d['nos'])}
<h3>Cobertura estrutural</h3>
<div class="kpis">{kpi(porcento(cob['Todos-Nós']), f"Todos-Nós ({cob['Todos-Nós'][0]} de {cob['Todos-Nós'][1]})")}{kpi(porcento(cob['Todas-Arestas']), f"Todas-Arestas ({cob['Todas-Arestas'][0]} de {cob['Todas-Arestas'][1]})")}{kpi(porcento(cob['Todos-Caminhos']), f"Todos-Caminhos ({cob['Todos-Caminhos'][0]} de {cob['Todos-Caminhos'][1]})")}</div>
<h3>O que cada caso percorre</h3>
{tabela(d['execucoes'])}
<h3>Caminhos completos</h3>
{tabela(d['caminhos'])}

<h2>4. Sprint 3: fluxo de dados</h2>
<div class="kpis">{''.join(kpi(porcento(par), f"{nome} ({par[0]} de {par[1]})") for nome, par in crit.items())}</div>
{tabela(d['variaveis'])}
<h3>Pares Def-Uso</h3>
{tabela(d['pares'])}

<h2>5. Sprint 3: teste de mutação</h2>
<div class="kpis">{kpi(mut['Mt'], 'mutantes gerados (Mt)')}{kpi(mut['Md'], 'mortos (Md)')}{kpi(mut['vivos'], 'vivos')}{kpi(mut['Me'], 'equivalentes (Me)')}{kpi(texto_ms(mut), 'escore de mutação (MS)')}</div>
<p>MS = Md ÷ (Mt − Me) × 100 = {mut['Md']} ÷ ({mut['Mt']} − {mut['Me']}) × 100 = <b>{texto_ms(mut)}</b></p>
{tabela(d['mutantes'])}

<h2>6. Sprint 4: validação da ferramenta</h2>
<p>{ok} de {total} verificações conferem com os gabaritos dos slides das aulas.</p>
{tabela(d['validacao'])}
{parecer}
<h2>Fontes</h2><ol>{referencias}</ol>
<p><small>Método: o TestingStudio interpreta em Python a lógica da função 4GL carregada
(IF, WHILE, LET, RETURN, comparações e aritmética). Não é o compilador Informix.</small></p>
<script src="https://cdn.jsdelivr.net/npm/@viz-js/viz@3.31.0/dist/viz-global.js"></script>
<script>
 if (window.Viz) {{ Viz.instance().then(function (viz) {{
   var alvo = document.getElementById("gfc"); alvo.innerHTML = ""; alvo.appendChild(viz.renderSVGElement({dot}));
 }}); }}
</script>
</body></html>"""


# ==========================================================================
# PASSO 4 - Gemini: teste da chave e parecer
# ==========================================================================
LIMITE_DE_PARECERES = 10     # por visita, quando a chave e a do servidor (protege a sua cota)


def chave_do_servidor() -> str:
    """Chave guardada fora do codigo: nos Secrets do Streamlit Community Cloud
    ou na variavel de ambiente GEMINI_API_KEY. Quando existe, a pagina usa essa
    chave sem nunca coloca-la em um campo da tela."""
    try:
        if st.secrets.load_if_toml_exists():
            chave = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
            if chave:
                return chave
    except Exception:
        pass
    return os.environ.get("GEMINI_API_KEY", "").strip()


def marca_da(chave: str) -> str:
    """Impressao digital da chave. Serve para lembrar 'esta chave ja foi testada'
    sem guardar a chave em si."""
    return hashlib.sha256(chave.encode()).hexdigest()


def sem_chave(texto: str, chave: str) -> str:
    """Garante que a chave nao aparece em nenhuma mensagem mostrada na tela."""
    return texto.replace(chave, "[chave oculta]") if chave else texto


class FalhaGemini(Exception):
    """Mensagem pronta para mostrar na tela quando o Gemini nao responde."""


def _explicar_erro(erro):
    """Traduz o erro da API. Devolve (mensagem, vale_tentar_outro_modelo)."""
    codigo = getattr(erro, "code", None)
    texto = str(erro).lower()
    if "api key not valid" in texto or "api_key_invalid" in texto:
        return "Chave inválida. Confira se copiou a chave inteira do Google AI Studio.", False
    if codigo == 429:
        return "A chave é válida, mas o limite de uso gratuito acabou por agora. Tente de novo em alguns minutos.", True
    if codigo in (401, 403):
        return "O Google recusou esta chave para o modelo escolhido (sem permissão).", True
    if codigo == 404:
        return "O modelo escolhido não está disponível para esta chave.", True
    if codigo and codigo >= 500:
        return "O serviço do Gemini está fora do ar no momento. Tente de novo em instantes.", True
    return f"Não foi possível falar com o Google. Confira a internet. Detalhe: {str(erro)[:160]}", False


def chamar_gemini(api_key: str, modelo: str, prompt: str):
    """Envia o prompt ao Gemini. Tenta o modelo escolhido e, se ele nao
    estiver disponivel, os outros da lista. Devolve (texto, modelo usado)."""
    from google import genai   # importado aqui para a pagina abrir mesmo sem a biblioteca

    cliente = genai.Client(api_key=api_key)
    mensagens = []
    for nome_modelo in [modelo] + [m for m in MODELOS if m != modelo]:
        try:
            resposta = cliente.models.generate_content(model=nome_modelo, contents=prompt)
            return (resposta.text or "").strip(), nome_modelo
        except Exception as erro:
            mensagem, tentar_outro = _explicar_erro(erro)
            mensagens.append(sem_chave(mensagem, api_key))
            if not tentar_outro:
                break
    raise FalhaGemini(mensagens[0])


def testar_chave(api_key: str, modelo: str) -> dict:
    """Faz uma pergunta minima ao Gemini so para confirmar que a chave funciona."""
    try:
        _, usado = chamar_gemini(api_key, modelo, "Responda apenas com a palavra OK.")
        return {"chave": marca_da(api_key), "ok": True, "modelo": usado,
                "mensagem": f"Chave funcionando. O modelo {usado} respondeu."}
    except FalhaGemini as falha:
        return {"chave": marca_da(api_key), "ok": False, "modelo": None, "mensagem": str(falha)}
    except Exception as erro:    # biblioteca ausente etc.
        return {"chave": marca_da(api_key), "ok": False, "modelo": None,
                "mensagem": sem_chave(f"Não foi possível testar a chave: {erro}", api_key)}


def _dados_para_o_gemini(fonte_funcao, d) -> str:
    """Bloco de dados comum aos dois pedidos (parecer e fala do pitch)."""
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    cob, crit = a["cobertura"], a["criterios"]
    ok, total = d["validacao_resumo"]
    achados = "\n".join(f"- {ACHADOS[c][0]}: casos {', '.join(ids)}" for c, ids in q["achados"].items()) \
        or "- nenhum"
    regras = "\n".join(f"{i}. {r}" for i, r in enumerate(ESPECIFICACAO, 1))
    referencias = "\n".join(f"- {ref}" for ref, _ in REFERENCIAS)
    vivos = d["mutantes"][d["mutantes"]["Estado"] == "Vivo"]
    return f"""<especificacao>
{regras}
</especificacao>

<funcao_sob_teste>
{fonte_funcao}
</funcao_sob_teste>

<epsilon>{d['justificativa']}</epsilon>

<caixa_preta>
casos executados: {q['total']} | aprovados: {q['aprovados']} | reprovados: {q['reprovados']}
classes de equivalência cobertas: {q['classes'][0]} de {q['classes'][1]}
pontos de fronteira cobertos: {q['pontos'][0]} de {q['pontos'][1]}
achados:
{achados}
</caixa_preta>

<caixa_branca>
N = {m['N']} | E = {m['E']} | P = {m['P']} | R = {m['R']}
V(G) = E - N + 2 = {m['v_topologico']} | V(G) = P + 1 = {m['v_logico']} | V(G) = R = {m['v_espacial']}
Todos-Nós: {cob['Todos-Nós'][0]} de {cob['Todos-Nós'][1]} | Todas-Arestas: {cob['Todas-Arestas'][0]} de {cob['Todas-Arestas'][1]} | caminhos completos: {cob['Todos-Caminhos'][0]} de {cob['Todos-Caminhos'][1]}
nos_csv:
{d['nos'].to_csv(index=False)}
caminhos_csv:
{d['caminhos'].to_csv(index=False)}
</caixa_branca>

<fluxo_de_dados>
{' | '.join(f"{nome}: {par[0]} de {par[1]}" for nome, par in crit.items())}
variaveis_csv:
{d['variaveis'].to_csv(index=False)}
</fluxo_de_dados>

<mutacao>
Mt = {mut['Mt']} | Md = {mut['Md']} | Me = {mut['Me']} | MS = {texto_ms(mut)}
mutantes_vivos_csv:
{vivos.to_csv(index=False) if len(vivos) else 'nenhum'}
</mutacao>

<validacao_da_ferramenta>{ok} de {total} verificações conferem com os gabaritos das aulas</validacao_da_ferramenta>

<achado_central>{d['achado']}</achado_central>

<casos_de_teste_csv>
{d['casos'].to_csv(index=False)}
</casos_de_teste_csv>

<referencias>
{referencias}
</referencias>"""


def montar_prompt(fonte_funcao, d) -> str:
    return f"""Você é um auditor de teste de software. Escreva, em português do Brasil, um parecer
de teste da função {FUNCAO_ALVO} do programa CAD0001, com foco na QUALIDADE DO PRODUTO DE TESTE
(adequação e cobertura do conjunto de casos) e nos defeitos revelados.

Estrutura do parecer:
1. Resumo executivo (3 a 5 linhas).
2. Caixa-preta: classes de equivalência, valor limite e justificativa do Épsilon.
3. Caixa-branca: nós, arestas, V(G) pelos três métodos e cobertura de nós, arestas e caminhos.
4. Fluxo de dados e mutação: pares Def-Uso cobertos, escore de mutação e mutantes vivos.
5. O que as três técnicas dizem em conjunto, defeitos revelados e correção sugerida no fonte.
6. Próximos testes recomendados.

Use somente os dados abaixo, que já foram calculados pela ferramenta. Ao citar literatura,
use apenas as referências listadas e não invente citações literais nem números de página.

{_dados_para_o_gemini(fonte_funcao, d)}"""


def montar_prompt_pitch(fonte_funcao, d) -> str:
    return f"""Você vai ajudar um estudante a apresentar um pitch de 5 minutos do TestingStudio Web,
uma ferramenta web que audita o programa CAD0001 (4GL/Logix) com caixa-preta, caixa-branca,
fluxo de dados e teste de mutação. O público é o professor e a turma de Teste de Software.

Escreva, em português do Brasil, a FALA do pitch, em primeira pessoa e tom natural, dividida em:
problema, solução, demonstração (o que mostrar em cada passo), evidências com os números,
o achado principal e próximos passos. Marque o tempo sugerido de cada parte.
Depois, liste 5 perguntas prováveis do professor com uma resposta curta para cada uma.

Use somente os números abaixo. Não invente resultados, citações nem funcionalidades.

{_dados_para_o_gemini(fonte_funcao, d)}"""


# ==========================================================================
# PASSO 5 - Sprints 2, 3 e 4: tabelas e paineis (os calculos estao em motor.py)
# ==========================================================================
@st.cache_data(show_spinner=False, max_entries=64)
def analise_em_cache(parametros, corpo, linha, epsilon, casos, por_bloco, nome):
    """Guarda o resultado da analise: a pagina e reexecutada a cada clique e
    nao precisa refazer grafo, fluxo de dados e mutantes se nada mudou."""
    return motor.analisar(list(parametros), corpo, linha, epsilon, list(casos), por_bloco, nome)


@st.cache_data(show_spinner=False)
def validacao_em_cache():
    return motor.validar_exemplos()


def texto_entrada(entrada) -> str:
    return "(" + "; ".join(formato_br(v) for v in entrada) + ")"


def texto_caminho(nos) -> str:
    return "-".join(str(n) for n in nos) if nos else "sem execução"


def porcento(par) -> str:
    feito, total = par
    return "sem itens" if not total else f"{round(100 * feito / total)}%"


def como_cobrir(sugestao, sondagens: int) -> str:
    if sugestao is None:
        return f"Nenhuma das {sondagens} entradas de sondagem alcança: possivelmente infactível"
    return f"Testar com {texto_entrada(sugestao)}"


def tabela_nos(a) -> pd.DataFrame:
    grafo, linhas = a["grafo"], []
    for no in grafo["nos"].values():
        tipo = {"decisao": "Predicativo", "comando": "Comando", "saida": "Saída"}[no["tipo"]]
        marcas = [m for m, vale in (("entrada", no["id"] == grafo["entrada"]),
                                    ("saída", no["id"] == grafo["saida"] and no["tipo"] != "saida"),
                                    ("inacessível", no["id"] in grafo["inacessiveis"])) if vale]
        destinos = [f"{b} ({r})" if r else str(b) for x, b, r in grafo["arestas"] if x == no["id"]]
        linhas.append({"Nó": no["id"], "Tipo": tipo + (f" ({', '.join(marcas)})" if marcas else ""),
                       "Linhas do fonte": ", ".join(map(str, no["linhas"])) or "fim",
                       "Comandos": "; ".join(no["texto"]), "Vai para": ", ".join(destinos) or "fim"})
    return pd.DataFrame(linhas)


def tabela_execucoes(a) -> pd.DataFrame:
    m, linhas = a["metricas"], []
    for x in a["execucoes"]:
        linha = {"Caso": x["caso"]}
        for nome, valor in zip(a["parametros"], x["entrada"]):
            linha[nome] = formato_br(valor)
        linha["Caminho executado"] = texto_caminho(x["nos"])
        linha["Nós percorridos"] = f"{x['nos_distintos']} de {m['N']}"
        linha["Arestas percorridas"] = f"{x['arestas_distintas']} de {m['E']}"
        linha["Retorno"] = "erro" if x["erro"] else formato_br(x["valor"])
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabela_caminhos(a) -> pd.DataFrame:
    return pd.DataFrame([{
        "Caminho completo": texto_caminho(c["nos"]),
        "Conjunto básico": "Sim" if c["basico"] else "",
        "Coberto por": ", ".join(c["casos"]) if c["casos"] else "nenhum caso",
        "Como cobrir": "" if c["casos"] else como_cobrir(c["sugestao"], a["sondagens"]),
    } for c in a["caminhos"]])


def tabela_variaveis(a) -> pd.DataFrame:
    """Mesmo formato do slide de pares DU: variavel, no de definicao, nos c-uso, arestas p-uso."""
    arestas = a["grafo"]["arestas"]
    return pd.DataFrame([{
        "Variável": variavel,
        "Nó de definição (d)": ", ".join(map(str, linha["defs"])) or "nenhum",
        "Nós c-uso": ", ".join(map(str, linha["c_usos"])) or "nenhum",
        "Arestas p-uso": ", ".join(f"({arestas[i][0]},{arestas[i][1]})" for i in linha["p_usos"]) or "nenhuma",
    } for variavel, linha in a["fluxo_tabela"].items()])


def tabela_pares(a) -> pd.DataFrame:
    linhas = []
    for p in a["pares"]:
        if p["tipo"] == "c":
            uso = f"nó {p['uso']}"
        else:
            uso = f"aresta ({p['uso'][0]},{p['uso'][1]})" + (f" {p['rotulo']}" if p["rotulo"] else "")
        linhas.append({"Variável": p["variavel"], "Definição (nó)": p["no_def"], "Uso": uso,
                       "Tipo": "c-uso" if p["tipo"] == "c" else "p-uso",
                       "Coberto por": ", ".join(p["casos"]) if p["casos"] else "nenhum caso",
                       "Como cobrir": "" if p["casos"] else como_cobrir(p["sugestao"], a["sondagens"])})
    return pd.DataFrame(linhas)


def tabela_mutantes(a) -> pd.DataFrame:
    linhas = []
    for m in a["mutantes"]:
        if m["estado"] == "Morto":
            analise = ""
        elif m["provavel_equivalente"]:
            analise = f"Provável equivalente: nenhuma das {a['sondagens']} entradas de sondagem distingue"
        else:
            analise = f"Mata com {texto_entrada(m['sugestao'])}"
        linhas.append({"Mutante": m["id"], "Operador": m["operador"], "Linha": m["linha"],
                       "Original": m["original"], "Alterado": m["mutado"], "Estado": m["estado"],
                       "Morto por": m["morto_por"], "Análise do mutante vivo": analise})
    return pd.DataFrame(linhas)


def resumo_mutacao(a, equivalentes=()) -> dict:
    """Mt, Md, Me e o escore MS = Md / (Mt - Me). 'equivalentes' sao os ids
    dos mutantes vivos que o analista marcou como equivalentes."""
    total = len(a["mutantes"])
    mortos = sum(1 for m in a["mutantes"] if m["estado"] == "Morto")
    me = sum(1 for m in a["mutantes"] if m["estado"] == "Vivo" and m["id"] in equivalentes)
    return {"Mt": total, "Md": mortos, "Me": me, "vivos": total - mortos,
            "MS": motor.escore_de_mutacao(mortos, total, me)}


def texto_ms(resumo) -> str:
    return "sem mutantes" if resumo["MS"] is None else f"{resumo['MS']:.1f}%".replace(".", ",")


def painel_caixa_branca(a, chave: str) -> None:
    """Sprint 2: grafo, contagens, McCabe pelos tres metodos e cobertura."""
    m, grafo = a["metricas"], a["grafo"]
    k = st.columns(5)
    k[0].metric("Nós (N)", m["N"], border=True, help="Blocos de comandos do grafo.")
    k[1].metric("Arestas (E)", m["E"], border=True, help="Desvios de fluxo entre os nós.")
    k[2].metric("Predicativos (P)", m["P"], border=True, help="Nós de decisão (IF, WHILE), com duas saídas.")
    k[3].metric("Regiões (R)", m["R"], border=True,
                help=f"{m['regioes_internas']} regiões internas mais a região externa.")
    k[4].metric("V(G)", m["V"], border=True, help="Complexidade ciclomática de McCabe.")

    st.markdown(
        f"- **Método 1, topológico:** V(G) = E − N + 2 = {m['E']} − {m['N']} + 2 = **{m['v_topologico']}**\n"
        f"- **Método 2, lógico:** V(G) = P + 1 = {m['P']} + 1 = **{m['v_logico']}**\n"
        f"- **Método 3, espacial:** V(G) = R = {m['regioes_internas']} internas + 1 externa = **{m['v_espacial']}**")
    if m["coincidem"]:
        st.success(f"Os três métodos coincidem: V(G) = {m['V']}. O conjunto básico tem {m['V']} caminhos "
                   f"independentes, então são necessários no mínimo {m['V']} casos de teste.",
                   icon=":material/check_circle:")
    else:
        st.warning("Os três métodos não coincidem. Isso acontece quando o grafo tem nós inacessíveis "
                   "ou mais de um componente. Revise o fluxo do código.", icon=":material/warning:")
    if m["condicoes_simples"] > m["P"]:
        st.caption(f"Há predicado composto (AND/OR): são {m['condicoes_simples']} condições simples em "
                   f"{m['P']} nós predicativos. Contando cada condição, a complexidade seria {m['v_condicoes']}.")
    if grafo["inacessiveis"]:
        st.warning(f"Nó(s) inacessível(is): {', '.join(map(str, grafo['inacessiveis']))}. "
                   "Nenhum caminho chega a eles a partir da entrada (código morto).", icon=":material/block:")

    st.subheader("Grafo de fluxo de controle (GFC)")
    esquerda, direita = st.columns([2, 3])
    with esquerda:
        st.graphviz_chart(motor.grafo_em_dot(grafo, set(a["nos_cobertos"]), set(a["arestas_cobertas"])))
        st.caption("Losango: nó predicativo. Círculo duplo: saída. V e F: desvio verdadeiro e falso. "
                   "Tracejado laranja: não coberto pela suíte.")
    with direita:
        st.dataframe(tabela_nos(a), hide_index=True, width="stretch")
        st.caption("Blocos indivisíveis: comandos em sequência, sem desvio, formam um único nó."
                   if grafo["por_bloco"] else "Um nó para cada comando executável.")

    st.subheader("Cobertura estrutural da suíte")
    c = st.columns(3)
    for coluna, nome, ajuda in zip(c, ("Todos-Nós", "Todas-Arestas", "Todos-Caminhos"), (
            "Cada nó executado pelo menos uma vez.", "Cada desvio (verdadeiro e falso) percorrido.",
            "Caminhos completos, com cada laço percorrido no máximo uma vez.")):
        feito, total = a["cobertura"][nome]
        coluna.metric(f"{nome}: {feito} de {total}", porcento((feito, total)), border=True, help=ajuda)
    if a["tem_laco"]:
        st.caption("Com laço, a quantidade real de caminhos não tem limite; a lista considera cada laço "
                   "percorrido zero ou uma vez.")

    st.markdown("**O que cada caso de teste percorre**")
    st.dataframe(tabela_execucoes(a), hide_index=True, width="stretch")
    st.markdown("**Caminhos completos do grafo**")
    st.dataframe(tabela_caminhos(a), hide_index=True, width="stretch")
    faltam = [x for x in a["arestas"] if not x["coberta"]]
    if faltam:
        st.markdown("**Arestas ainda não cobertas**")
        st.dataframe(pd.DataFrame([{
            "Aresta": f"({x['de']},{x['para']})" + (f" {x['rotulo']}" if x["rotulo"] else ""),
            "Como cobrir": como_cobrir(x["sugestao"], a["sondagens"])} for x in faltam]),
            hide_index=True, width="stretch")


def painel_fluxo(a, chave: str) -> None:
    """Sprint 3, parte 1: definicoes, usos e pares Def-Uso."""
    c = st.columns(4)
    ajudas = {"Todas-Definições": "Cada definição chega a pelo menos um uso.",
              "Todos-c-Usos": "Cada par definição e uso computacional (em um nó).",
              "Todos-p-Usos": "Cada par definição e uso predicativo (em uma aresta).",
              "Todos-Usos": "Todos os pares Def-Uso: c-usos e p-usos."}
    for coluna, (nome, par) in zip(c, a["criterios"].items()):
        coluna.metric(f"{nome}: {par[0]} de {par[1]}", porcento(par), border=True, help=ajudas[nome])
    st.markdown("**Definições e usos de cada variável**")
    st.dataframe(tabela_variaveis(a), hide_index=True, width="stretch")
    st.caption("d: nó onde a variável recebe valor (parâmetros são definidos no nó de entrada). "
               "c-uso: uso em cálculo ou retorno, associado a um nó. "
               "p-uso: uso em decisão, associado às arestas que saem do nó.")
    st.markdown("**Pares Def-Uso (caminho livre de definição entre d e o uso)**")
    st.dataframe(tabela_pares(a), hide_index=True, width="stretch")
    if a["uso_sem_definicao"]:
        st.warning("Uso sem definição que o alcance: " + ", ".join(
            f"{v} (linha {linha})" for v, linha in a["uso_sem_definicao"]) +
            ". A variável chega NULL a esse ponto.", icon=":material/warning:")
    if a["definicao_sem_uso"]:
        st.info("Definição que nenhum uso aproveita: " + ", ".join(
            f"{v} (nó {no})" for v, no in a["definicao_sem_uso"]) + ".", icon=":material/info:")


def painel_mutacao(a, chave: str) -> dict:
    """Sprint 3, parte 2: mutantes, estados e escore de mutacao. Devolve o resumo."""
    topo = st.container()
    tabela = tabela_mutantes(a)
    if tabela.empty:
        st.info("Esta função não tem operador, comparação ou variável para mutar.", icon=":material/info:")
        return resumo_mutacao(a)
    st.markdown("**Mutantes gerados**")
    tabela.insert(6, "Equivalente", False)
    editado = st.data_editor(
        tabela, key=f"{chave}_mutantes", hide_index=True, width="stretch",
        disabled=[c for c in tabela.columns if c != "Equivalente"],
        column_config={"Equivalente": st.column_config.CheckboxColumn(
            "Equivalente", help="Marque o mutante vivo que você analisou e concluiu que se comporta "
                                "igual ao original para qualquer entrada.")})
    st.caption("Morto: algum caso deu resultado diferente do programa original. Vivo: todos os casos deram "
               "o mesmo resultado. Decidir se um mutante vivo é equivalente é tarefa do analista; "
               "a marcação só conta para mutantes vivos.")
    marcados = set(editado.loc[editado["Equivalente"], "Mutante"])
    r = resumo_mutacao(a, marcados)

    with topo:
        k = st.columns(5)
        k[0].metric("Gerados (Mt)", r["Mt"], border=True)
        k[1].metric("Mortos (Md)", r["Md"], border=True)
        k[2].metric("Vivos", r["vivos"], border=True)
        k[3].metric("Equivalentes (Me)", r["Me"], border=True)
        k[4].metric("Escore (MS)", texto_ms(r), border=True)
        st.markdown(f"MS = Md ÷ (Mt − Me) × 100 = {r['Md']} ÷ ({r['Mt']} − {r['Me']}) × 100 = **{texto_ms(r)}**")
        vivos = [m for m in a["mutantes"] if m["estado"] == "Vivo"]
        provaveis = [m for m in vivos if m["provavel_equivalente"]]
        mataveis = [m for m in vivos if not m["provavel_equivalente"]]
        if not vivos:
            st.success("A suíte matou todos os mutantes.", icon=":material/check_circle:")
        if mataveis:
            st.warning(f"{len(mataveis)} mutante(s) vivo(s) podem ser mortos com um caso novo: "
                       f"{', '.join(m['id'] for m in mataveis)}. A tabela indica uma entrada para cada um.",
                       icon=":material/science:")
        if provaveis:
            st.info(f"{len(provaveis)} mutante(s) vivo(s) parecem equivalentes: "
                    f"{', '.join(m['id'] for m in provaveis)}. Se a análise confirmar, marque a coluna "
                    "Equivalente e o escore é recalculado.", icon=":material/balance:")
        por_operador = []
        for operador, descricao in motor.OPERADORES.items():
            do_operador = [m for m in a["mutantes"] if m["operador"] == operador]
            if do_operador:
                mortos = sum(1 for m in do_operador if m["estado"] == "Morto")
                por_operador.append({"Operador": operador, "O que faz": descricao,
                                     "Gerados": len(do_operador), "Mortos": mortos,
                                     "Vivos": len(do_operador) - mortos})
        st.dataframe(pd.DataFrame(por_operador), hide_index=True, width="stretch")
    return r


def tabela_validacao(linhas) -> pd.DataFrame:
    return pd.DataFrame([{"Exemplo": l["exemplo"], "Origem": l["aula"], "Medida": l["medida"],
                          "Gabarito do slide": l["esperado"], "Ferramenta": l["obtido"],
                          "Resultado": "✓ Confere" if l["confere"] else "✕ Diverge"} for l in linhas])


def achado_central(q, a, mut) -> str:
    """Frase que liga as tres tecnicas, calculada a partir dos resultados."""
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    estrutural_total = nos[0] == nos[1] and arestas[0] == arestas[1]
    if q["reprovados"] and estrutural_total:
        return (f"A caixa-branca cobriu 100% dos nós e das arestas e o escore de mutação ficou em "
                f"{texto_ms(mut)}, e mesmo assim a caixa-preta reprovou {q['reprovados']} casos. "
                "O motivo é um requisito que não foi escrito no código: teste estrutural e mutação só "
                "enxergam o código que existe, e requisito omitido só aparece no teste funcional. "
                "É o que a aula de 21/09 chama de ilusão do teste estrutural.")
    if q["reprovados"]:
        return (f"A caixa-preta reprovou {q['reprovados']} casos e a cobertura estrutural ainda não é "
                f"total (nós: {porcento(nos)}, arestas: {porcento(arestas)}). Há defeito a corrigir e "
                "código ainda não exercitado.")
    if estrutural_total:
        return (f"As técnicas concordam: nenhum caso reprovado na caixa-preta, 100% dos nós e das "
                f"arestas cobertos e escore de mutação de {texto_ms(mut)}.")
    return (f"Nenhum caso reprovado na caixa-preta, mas a cobertura estrutural não é total "
            f"(nós: {porcento(nos)}, arestas: {porcento(arestas)}): falta exercitar parte do código.")


def roteiro_do_pitch(d) -> str:
    """Roteiro de apresentacao em Markdown, com os numeros desta auditoria."""
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    ok, total = d["validacao_resumo"]
    cob = a["cobertura"]
    return f"""## Roteiro do pitch (cerca de 5 minutos)

**1. O problema (30 s)**
Testar tudo é impossível, e testar "mais ou menos" deixa o defeito passar na fronteira.
Em sistema legado como o Logix, o teste costuma ser manual e sem medida de quanto foi coberto.

**2. A solução (30 s)**
O TestingStudio Web lê o fonte 4GL, executa a função e aplica as três famílias de técnicas da disciplina:
caixa-preta, caixa-branca e teste baseado em defeitos. Para cada uma, mostra o resultado e a medida de cobertura.

**3. Demonstração (2 min)**
1. Anexar o `{d['arquivo']}` e mostrar o fonte na tela.
2. Sprint 1: classes de equivalência, valor limite com ε = {formato_br(d['epsilon'])} e a matriz de cobertura.
3. Sprint 2: o grafo com N = {m['N']}, E = {m['E']}, P = {m['P']}, R = {m['R']} e V(G) = {m['V']} pelos três métodos.
4. Sprint 3: pares Def-Uso e mutantes, com o escore de mutação.
5. Trocar um valor na aba de testes extras ou editar o fonte e ver tudo recalcular.

**4. Evidências (1 min)**

| Técnica | Resultado desta auditoria |
|---|---|
| Caixa-preta | {q['total']} casos, {q['aprovados']} aprovados, {q['reprovados']} reprovados; classes {q['classes'][0]}/{q['classes'][1]}; fronteiras {q['pontos'][0]}/{q['pontos'][1]} |
| Caixa-branca | Todos-Nós {porcento(cob['Todos-Nós'])}; Todas-Arestas {porcento(cob['Todas-Arestas'])}; caminhos {cob['Todos-Caminhos'][0]} de {cob['Todos-Caminhos'][1]} |
| Fluxo de dados | Todos-Usos: {a['criterios']['Todos-Usos'][0]} de {a['criterios']['Todos-Usos'][1]} pares Def-Uso |
| Mutação | Mt = {mut['Mt']}, Md = {mut['Md']}, Me = {mut['Me']}, MS = {texto_ms(mut)} |
| Validação da ferramenta | {ok} de {total} verificações conferem com os gabaritos dos slides |

**5. O achado (30 s)**
{d['achado']}

**6. Limites e próximos passos (30 s)**
O interpretador entende DEFINE, IF, WHILE, LET e RETURN; não é o compilador Informix e não acessa banco.
Próximos passos: FOR e CASE, chamadas entre funções (teste de integração) e geração automática dos casos que faltam.
"""


GRANULARIDADES = ["Blocos indivisíveis (definição formal)", "Um nó por comando"]
MODELO_DE_EXERCICIO = """FUNCTION minha_funcao(a, b)
    DEFINE a, b, diferenca DECIMAL(12,2)
    IF a > b THEN
        LET diferenca = a - b
    ELSE
        LET diferenca = b - a
    END IF
    RETURN diferenca
END FUNCTION
"""


@st.cache_data(show_spinner=False, max_entries=64)
def analise_do_laboratorio(codigo, casos, por_bloco):
    return motor.analisar_fonte(codigo, list(casos), por_bloco)


def laboratorio() -> None:
    """Sprint 4: o mesmo motor aplicado a exemplos das aulas ou a um codigo colado."""
    opcoes = {f"{e['titulo']} ({e['aula']})": e for e in motor.EXEMPLOS}
    escolha = st.selectbox("Exercício", list(opcoes) + ["Colar o meu código"], key="lab_escolha")
    exemplo = opcoes.get(escolha)
    chave = exemplo["chave"] if exemplo else "proprio"
    codigo = st.text_area("Código em 4GL (DEFINE, IF, WHILE, LET, RETURN)",
                          value=exemplo["fonte"] if exemplo else MODELO_DE_EXERCICIO,
                          height=250, key=f"lab_codigo_{chave}")
    funcao = motor.localizar_funcao(codigo)
    if funcao is None:
        st.error("Não encontrei 'FUNCTION nome(...) ... END FUNCTION' no texto.")
        return
    nomes = funcao["parametros"]
    por_bloco = st.radio("Como contar os nós", GRANULARIDADES, horizontal=True, key=f"lab_nos_{chave}",
                         index=0 if exemplo is None or exemplo["por_bloco"] else 1) == GRANULARIDADES[0]

    base = exemplo["casos"] if exemplo else [("T1", (5, 3)), ("T2", (3, 5))]
    linhas = [{"_caso": rotulo, **{n: (None if v is None else float(v)) for n, v in zip(nomes, entrada)}}
              for rotulo, entrada in base if len(entrada) == len(nomes)]
    inicial = pd.DataFrame(linhas or [{"_caso": "T1", **{n: None for n in nomes}}])
    st.markdown("**Casos de teste** (edite, apague ou acrescente linhas; célula vazia envia NULL)")
    editado = st.data_editor(
        inicial, num_rows="dynamic", hide_index=True, width="stretch",
        key=f"lab_casos_{chave}_{'_'.join(nomes)}",
        column_config={"_caso": st.column_config.TextColumn("Caso"),
                       **{n: st.column_config.NumberColumn(n, format="%.2f") for n in nomes}})
    casos = []
    for _, linha in editado.iterrows():
        rotulo = linha["_caso"] if isinstance(linha["_caso"], str) and linha["_caso"].strip() else f"T{len(casos) + 1}"
        casos.append((rotulo, tuple(None if pd.isna(linha[n]) else float(linha[n]) for n in nomes)))
    if not casos:
        st.info("Inclua pelo menos um caso de teste.", icon=":material/add:")
        return
    try:
        a = analise_do_laboratorio(codigo, tuple(casos), por_bloco)
    except motor.Erro4GL as problema:
        st.error(f"Não consegui interpretar a função: {problema}. "
                 "O interpretador entende DEFINE, IF/THEN/ELSE, WHILE, LET e RETURN.")
        return
    if exemplo and exemplo.get("observacao"):
        st.caption(exemplo["observacao"])
    aba_cb, aba_fd, aba_mu = st.tabs(["Caixa-branca", "Fluxo de dados", "Mutação"])
    with aba_cb:
        painel_caixa_branca(a, f"lab_{chave}")
    with aba_fd:
        painel_fluxo(a, f"lab_{chave}")
    with aba_mu:
        painel_mutacao(a, f"lab_{chave}")


# ==========================================================================
# INTERFACE WEB (Streamlit)
# ==========================================================================
st.set_page_config(page_title="TestingStudio Web", layout="wide")
st.html(ESTILO)

st.title("TestingStudio Web")
st.html("<p class='ts-sub'>Auditoria de teste do programa CAD0001: caixa-preta, caixa-branca, fluxo de "
        "dados e mutação, com os testes executados sobre o fonte que você anexar.</p>"
        "<div class='ts-regua'></div>")

# ---- Barra lateral: chave do Gemini ---------------------------------------
chave_servidor = chave_do_servidor()
with st.sidebar:
    st.header("Gemini")
    if chave_servidor:
        # Pagina publicada: a chave vem do servidor e nao existe campo para ela na tela.
        api_key = chave_servidor
        st.caption("A chave do Gemini está guardada no servidor e não é exibida nesta página.")
    else:
        api_key = st.text_input("Chave da API (aistudio.google.com)", type="password").strip()
    modelo = st.selectbox("Modelo", MODELOS)
    if st.button("Testar chave", width="stretch", disabled=not api_key):
        with st.spinner("Perguntando ao Gemini..."):
            st.session_state["chave_status"] = testar_chave(api_key, modelo)

    situacao = st.session_state.get("chave_status")
    if not api_key:
        st.caption("Sem chave, a auditoria funciona normalmente; só os textos do Gemini ficam desligados.")
    elif not situacao or situacao["chave"] != marca_da(api_key):
        st.info("Chave ainda não testada.", icon=":material/help:")
    elif situacao["ok"]:
        st.success(situacao["mensagem"], icon=":material/check_circle:")
    else:
        st.error(situacao["mensagem"], icon=":material/error:")

    st.divider()
    st.caption("Teste de Software I, Prof. Frank Piffer. Sprints 1 a 4.")

chave_ok = bool(api_key and situacao and situacao["chave"] == marca_da(api_key) and situacao["ok"])

# ---- 1. Leitura do fonte ---------------------------------------------------
st.header("1. Fonte do programa")
enviado = st.file_uploader("Anexe o arquivo .txt do programa", type=["txt"])

if enviado is not None:
    ident = (enviado.name, enviado.size, getattr(enviado, "file_id", None))
    if st.session_state.get("fonte_ident") != ident:
        registrar_fonte(enviado.name, enviado.getvalue(), "upload", ident)
elif st.session_state.get("fonte_origem") == "upload":
    esquecer_fonte()                 # o arquivo foi removido do campo acima

if "fonte_original" not in st.session_state:
    st.info("Nenhum arquivo carregado. A auditoria começa depois que você anexar o .txt do programa.",
            icon=":material/upload_file:")
    exemplo = PASTA / ARQUIVO_EXEMPLO
    if exemplo.exists():
        if st.button(f"Usar o arquivo de exemplo ({ARQUIVO_EXEMPLO})"):
            registrar_fonte(ARQUIVO_EXEMPLO, exemplo.read_bytes(), "exemplo", ("exemplo",))
            st.rerun()
    st.stop()

original = st.session_state["fonte_original"]
st.success(f"Arquivo carregado: {st.session_state['fonte_nome']} — {len(original.splitlines())} linhas, "
           f"lido em {st.session_state['fonte_quando']}", icon=":material/description:")

fonte = st.text_area("Fonte do CAD0001 (você pode editar aqui para testar uma alteração)",
                     key="fonte_editado", height=280)
alterado = fonte != original
col_a, col_b, _ = st.columns([1.4, 1.4, 4])
if alterado:
    col_a.button("Restaurar o original", width="stretch",
                 on_click=lambda: st.session_state.update(fonte_editado=st.session_state["fonte_original"]))
if st.session_state["fonte_origem"] == "exemplo":
    col_b.button("Remover o arquivo", width="stretch", on_click=esquecer_fonte)
if alterado:
    st.warning("O fonte foi alterado nesta página. Os testes abaixo rodam sobre a versão editada, "
               "não sobre o arquivo original.", icon=":material/edit:")

# ---- 2. Unidade sob teste --------------------------------------------------
funcao = motor.localizar_funcao(fonte, FUNCAO_ALVO)
if funcao is None:
    st.error(f"Não encontrei 'FUNCTION {FUNCAO_ALVO}(...) ... END FUNCTION' neste fonte.")
    st.stop()
parametros, corpo, linha_funcao = funcao["parametros"], funcao["corpo"], funcao["linha"]
tipo = motor.tipo_decimal(corpo)
if tipo is None or len(parametros) != 3:
    st.error("A função precisa ter 3 parâmetros e uma declaração DECIMAL(precisão, escala).")
    st.stop()
precisao, escala, epsilon, maximo = tipo
try:
    programa = motor.compilar_funcao(parametros, corpo, linha_funcao, FUNCAO_ALVO)
except motor.Erro4GL as problema:
    st.error(f"Não consegui interpretar a função: {problema}. "
             "O interpretador entende DEFINE, IF/THEN/ELSE, WHILE, LET e RETURN.")
    st.stop()

st.header("2. Unidade sob teste e Épsilon")
texto_funcao = f"FUNCTION {FUNCAO_ALVO}({', '.join(parametros)}){corpo}END FUNCTION"
with st.expander(f"Função {FUNCAO_ALVO} extraída do fonte (com o número da linha no arquivo)"):
    st.code("\n".join(f"{numero:>4}  {linha}" for numero, linha in
                      enumerate(texto_funcao.split("\n"), start=linha_funcao)), language=None)

c1, c2, c3 = st.columns(3)
c1.metric("Tipo dos parâmetros", f"DECIMAL({precisao},{escala})", border=True)
c2.metric("Épsilon (ε) calculado", formato_br(epsilon), border=True,
          help="Menor variação que o tipo representa: 10 elevado a menos a escala.")
c3.metric("Maior valor do tipo", formato_br(maximo), border=True)

justificativa = (
    f"Os parâmetros são DECIMAL({precisao},{escala}), com {escala} casas decimais. A menor variação "
    f"representável é ε = 10^-{escala} = {formato_br(epsilon)} (1 centavo). Por isso o Off-Point da "
    f"fronteira 0,00 é 0,00 − ε = {formato_br(FRONTEIRA - epsilon)}: é o valor inválido mais próximo "
    "possível do limite, o único capaz de distinguir um '<' de um '<=' no código."
)

passo = float(epsilon)
with st.expander("Valores usados na suíte (você pode trocar)"):
    v1, v2, v3 = st.columns(3)
    nominal = v1.number_input("Valor dos parâmetros que não variam", min_value=0.0, value=10.0,
                              step=passo, format=f"%.{escala}f")
    interior = v2.number_input("Ponto Interior (válido)", min_value=passo, value=100.0,
                               step=passo, format=f"%.{escala}f")
    exterior = v3.number_input("Ponto Exterior (inválido)", max_value=-2 * passo, value=-100.0,
                               step=passo, format=f"%.{escala}f")
    st.caption("O On-Point (0,00) e o Off-Point (0,00 − ε) são fixos: vêm da regra de negócio e do tipo de dado.")


def para_decimal(numero: float) -> Decimal:
    return Decimal(str(numero)).quantize(epsilon, ROUND_HALF_UP)


nominal, interior, exterior = para_decimal(nominal), para_decimal(interior), para_decimal(exterior)

# ---- 3. Auditoria ----------------------------------------------------------
st.header("3. Auditoria")
sprint1, sprint2, sprint3, sprint4, aba_ia, aba_fontes = st.tabs(
    ["Sprint 1: caixa-preta", "Sprint 2: caixa-branca", "Sprint 3: fluxo de dados e mutação",
     "Sprint 4: validação e pitch", "Parecer do Gemini", "Fontes"])

# ======================= SPRINT 1: CAIXA-PRETA ==============================
with sprint1:
    aba_resumo, aba_rel, aba_graf, aba_extra = st.tabs(
        ["Resumo da qualidade", "Relatório (PCE & AVL)", "Gráfico de fronteira", "Testes extras"])

# A aba de testes extras e montada primeiro porque todos os indicadores
# (das quatro sprints) usam as linhas digitadas nela.
with aba_extra:
    st.write("Monte seus próprios casos: troque os valores, apague ou acrescente linhas. "
             "Deixe uma célula vazia para enviar NULL. Os resultados de todas as sprints "
             "são recalculados na hora.")
    sugestoes = pd.DataFrame([
        {"descricao": "Primeiro valor válido acima da fronteira (0,00 + ε)", "p1": passo, "p2": 10.0, "p3": 10.0},
        {"descricao": "Todos os parâmetros negativos", "p1": -passo, "p2": -passo, "p3": -passo},
        {"descricao": "Todos os parâmetros nulos", "p1": None, "p2": None, "p3": None},
        {"descricao": "Maior valor do tipo no terceiro parâmetro", "p1": 0.0, "p2": 0.0, "p3": float(maximo)},
    ])
    coluna_numero = {f"p{i + 1}": st.column_config.NumberColumn(nome, step=passo, format=f"%.{escala}f")
                     for i, nome in enumerate(parametros)}
    digitado = st.data_editor(
        sugestoes, key="extras", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={"descricao": st.column_config.TextColumn("O que este caso verifica", width="large"),
                       **coluna_numero})

casos_base = gerar_suite_base(programa, epsilon, maximo, nominal, interior, exterior)
casos_extras = gerar_casos_extras(digitado, programa, epsilon, maximo)
casos = casos_base + casos_extras
qualidade = medir_qualidade(casos, parametros, epsilon)

df_casos = tabela_casos(casos, parametros)
df_pce = tabela_pce(casos, parametros, maximo)
df_pontos = tabela_pontos(epsilon, interior, exterior)
df_pontos_tela = df_pontos.assign(Valor=df_pontos["Valor"].map(formato_br))
df_origem = pd.DataFrame([
    {"Dado": "Arquivo", "Valor": st.session_state["fonte_nome"]},
    {"Dado": "Lido em", "Valor": st.session_state["fonte_quando"]},
    {"Dado": "Tamanho", "Valor": f"{st.session_state['fonte_bytes']} bytes, {len(original.splitlines())} linhas"},
    {"Dado": "SHA-256 do arquivo", "Valor": st.session_state["fonte_sha"]},
    {"Dado": "Fonte editado na página", "Valor": "Sim" if alterado else "Não"},
    {"Dado": "Unidade sob teste", "Valor": f"{FUNCAO_ALVO}({', '.join(parametros)}), a partir da linha {linha_funcao}"},
    {"Dado": "Tipo de dado e Épsilon", "Valor": f"DECIMAL({precisao},{escala}); ε = {formato_br(epsilon)}"},
])

with aba_extra:
    if casos_extras:
        st.dataframe(tabela_casos(casos_extras, parametros).drop(columns=["Técnica", "Parâmetro variado", "Ponto ou classe"]),
                     hide_index=True, width="stretch")
    else:
        st.caption("Nenhum caso extra preenchido.")

with aba_resumo:
    k = st.columns(6)
    k[0].metric("Casos", qualidade["total"], border=True, help="Casos de teste executados: suíte planejada mais os testes extras.")
    k[1].metric("Aprovados", qualidade["aprovados"], border=True)
    k[2].metric("Reprovados", qualidade["reprovados"], border=True)
    k[3].metric("Classes", f"{qualidade['classes'][0]}/{qualidade['classes'][1]}", border=True,
                help="Classes de equivalência cobertas: válida, negativa e nula, com pelo menos um caso por parâmetro.")
    k[4].metric("Fronteiras", f"{qualidade['pontos'][0]}/{qualidade['pontos'][1]}", border=True,
                help="Pontos de fronteira cobertos: On, Off, Interior e Exterior de cada parâmetro.")
    k[5].metric("Defeitos", len(qualidade["achados"]), border=True,
                help="Tipos de defeito revelados: divergências diferentes entre o esperado e o obtido.")

    if qualidade["reprovados"] == 0:
        st.success(f"Nenhuma divergência: os {qualidade['aprovados']} casos com resultado esperado "
                   "definido foram aprovados.", icon=":material/check_circle:")
    for codigo, ids in qualidade["achados"].items():
        titulo, explicacao = ACHADOS[codigo]
        st.error(f"**{titulo}** — {len(ids)} casos ({', '.join(ids)}). {explicacao}", icon=":material/bug_report:")
    if qualidade["sem_oraculo"]:
        st.info(f"{qualidade['sem_oraculo']} caso(s) sem resultado esperado definido pela especificação "
                "(estouro do tipo). Isso é uma lacuna da especificação, não do código.", icon=":material/help:")

    st.subheader("Cobertura da suíte planejada")
    st.html(html_matriz(casos_base, parametros))
    st.caption("Cada célula é um caso: um parâmetro recebe o valor da coluna e os outros dois ficam em "
               f"{formato_br(nominal)}. Os testes extras entram nos indicadores acima.")
    lugar_dos_downloads = st.container()

with aba_rel:
    st.subheader("Especificação usada como oráculo")
    st.markdown("\n".join(f"{i}. {regra}" for i, regra in enumerate(ESPECIFICACAO, 1)))
    st.subheader("Particionamento em classes de equivalência (PCE)")
    st.dataframe(df_pce, hide_index=True, width="stretch")
    st.subheader("Justificativa do Épsilon")
    st.write(justificativa)
    st.subheader("Análise do valor limite (AVL) e demais casos")
    st.dataframe(df_casos, hide_index=True, width="stretch")
    st.caption("Esperado: calculado pela especificação. Obtido: resultado da execução da função carregada.")

with aba_graf:
    st.subheader("Pontos limites em torno da fronteira 0,00")
    st.altair_chart(grafico_fronteira(df_pontos, epsilon), width="stretch")
    st.dataframe(df_pontos_tela, hide_index=True, width="stretch")

# ======================= SPRINT 2: CAIXA-BRANCA =============================
with sprint2:
    st.write("A caixa-branca olha a estrutura do código. A função vira um grafo de fluxo de controle, "
             "e os mesmos casos de teste da Sprint 1 são executados para medir o que cada um percorre.")
    por_bloco = st.radio("Como contar os nós", GRANULARIDADES, horizontal=True, key="cad_granularidade",
                         help="A definição formal junta em um nó os comandos em sequência, sem desvio. "
                              "Alguns slides desenham um nó para cada comando.") == GRANULARIDADES[0]

casos_do_motor = tuple((c["id"], tuple(c["entradas"])) for c in casos)
try:
    analise = analise_em_cache(tuple(parametros), corpo, linha_funcao, epsilon, casos_do_motor,
                               por_bloco, FUNCAO_ALVO)
except motor.Erro4GL as problema:
    st.error(f"Não foi possível fazer a análise estrutural: {problema}.")
    st.stop()

with sprint2:
    painel_caixa_branca(analise, "cad")

# ======================= SPRINT 3: FLUXO DE DADOS E MUTACAO =================
with sprint3:
    aba_fluxo, aba_mutacao = st.tabs(["Fluxo de dados (pares Def-Uso)", "Teste de mutação"])
    with aba_fluxo:
        st.write("O teste de fluxo de dados acompanha cada variável: onde recebe valor e onde esse valor é usado. "
                 "Os números de nó e de aresta são os do grafo da Sprint 2.")
        painel_fluxo(analise, "cad")
    with aba_mutacao:
        st.write("O teste de mutação avalia a suíte, não o código: cada mutante é a função com um defeito "
                 "proposital, e uma boa suíte percebe a diferença.")
        mutacao = painel_mutacao(analise, "cad")

# ======================= SPRINT 4: VALIDACAO E PITCH ========================
linhas_validacao = validacao_em_cache()
validacao_resumo = (sum(1 for l in linhas_validacao if l["confere"]), len(linhas_validacao))
achado = achado_central(qualidade, analise, mutacao)
df_mutantes = tabela_mutantes(analise)
pacote = {
    "qualidade": qualidade, "casos": df_casos, "pce": df_pce, "pontos": df_pontos_tela,
    "origem": df_origem, "justificativa": justificativa,
    "analise": analise, "mutacao": mutacao, "achado": achado,
    "nos": tabela_nos(analise), "execucoes": tabela_execucoes(analise), "caminhos": tabela_caminhos(analise),
    "variaveis": tabela_variaveis(analise), "pares": tabela_pares(analise), "mutantes": df_mutantes,
    "validacao": tabela_validacao(linhas_validacao), "validacao_resumo": validacao_resumo,
    "arquivo": st.session_state["fonte_nome"], "epsilon": epsilon,
}
assinatura = hashlib.sha256((texto_funcao + df_casos.to_csv() + str(por_bloco) + str(mutacao)).encode()).hexdigest()
parecer = st.session_state.get("parecer")
if parecer:
    pacote.update(parecer=parecer["texto"], parecer_modelo=parecer["modelo"])
relatorio_html = gerar_relatorio_html(pacote)
roteiro = roteiro_do_pitch(pacote)

with sprint4:
    aba_validacao, aba_laboratorio, aba_pitch = st.tabs(
        ["Validação com gabaritos das aulas", "Laboratório de exercícios", "Roteiro do pitch"])
    with aba_validacao:
        st.write("Antes de confiar na ferramenta, ela mesma é testada: cada exemplo dos slides das aulas, "
                 "que tem resposta conhecida, é analisado e o resultado é comparado com o gabarito.")
        v1, v2 = st.columns([1, 3])
        v1.metric("Verificações que conferem", f"{validacao_resumo[0]} de {validacao_resumo[1]}", border=True)
        if validacao_resumo[0] == validacao_resumo[1]:
            v2.success("O motor reproduz todos os gabaritos: contagens do grafo, V(G), caminhos, pares "
                       "Def-Uso, estados dos mutantes e escore de mutação.", icon=":material/verified:")
        else:
            v2.error("Há divergência em relação a algum gabarito. Veja as linhas marcadas na tabela.",
                     icon=":material/error:")
        st.dataframe(pacote["validacao"], hide_index=True, width="stretch", height="content")
        for exemplo in motor.EXEMPLOS:
            if exemplo.get("observacao"):
                st.caption(f"{exemplo['titulo']}: {exemplo['observacao']}")
    with aba_laboratorio:
        st.write("Use o mesmo motor para conferir exercícios e gabaritos: escolha um exemplo das aulas "
                 "ou cole a sua função, monte os casos e veja grafo, pares Def-Uso e mutantes.")
        laboratorio()
    with aba_pitch:
        st.info(achado, icon=":material/lightbulb:")
        st.markdown(roteiro)
        p1, p2, _ = st.columns([1.6, 1.6, 3])
        p1.download_button("Baixar relatório completo (HTML)", relatorio_html, key="baixar_relatorio_pitch",
                           file_name="relatorio_cad0001.html", mime="text/html", width="stretch")
        p2.download_button("Baixar roteiro (Markdown)", roteiro, key="baixar_roteiro",
                           file_name="roteiro_pitch.md", mime="text/markdown", width="stretch")

with lugar_dos_downloads:
    b1, b2, _ = st.columns([1.6, 1.6, 3])
    b1.download_button("Baixar relatório completo (HTML)", relatorio_html, key="baixar_relatorio_resumo",
                       file_name="relatorio_cad0001.html", mime="text/html", width="stretch",
                       help="Reúne as quatro sprints. Abra no navegador para apresentar ou use Ctrl+P para salvar em PDF.")
    b2.download_button("Baixar casos de teste (CSV)", df_casos.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name="casos_de_teste_cad0001.csv", mime="text/csv", width="stretch")

# ======================= GEMINI =============================================
with aba_ia:
    st.write("Todos os números são calculados pelo Python. Aqui o Gemini só redige um texto a partir deles.")
    pedido = st.radio("O que o Gemini deve escrever", ["Parecer de auditoria", "Fala para o pitch"],
                      horizontal=True, key="pedido_gemini")
    guarda = "parecer" if pedido == "Parecer de auditoria" else "fala"
    if not api_key:
        st.info("Cole a chave da API na barra lateral para ligar esta parte.", icon=":material/key:")
    elif not chave_ok:
        st.info("Use o botão Testar chave, na barra lateral, para confirmar que a chave funciona.",
                icon=":material/key:")
    usos = st.session_state.get("usos_gemini", 0)
    no_limite = bool(chave_servidor) and usos >= LIMITE_DE_PARECERES
    if no_limite:
        st.info(f"Limite de {LIMITE_DE_PARECERES} textos por visita atingido. "
                "Recarregue a página para continuar.", icon=":material/hourglass:")
    if st.button("Executar auditoria com Gemini" if guarda == "parecer" else "Escrever a fala com Gemini",
                 type="primary", disabled=not api_key or no_limite):
        st.session_state["usos_gemini"] = usos + 1
        try:
            with st.spinner("Gemini escrevendo..."):
                prompt = (montar_prompt if guarda == "parecer" else montar_prompt_pitch)(texto_funcao, pacote)
                texto, usado = chamar_gemini(api_key, situacao["modelo"] if chave_ok else modelo, prompt)
            st.session_state[guarda] = {"texto": texto, "modelo": usado, "assinatura": assinatura}
            st.session_state["chave_status"] = {"chave": marca_da(api_key), "ok": True, "modelo": usado,
                                                "mensagem": f"Chave funcionando. O modelo {usado} respondeu."}
            st.rerun()
        except FalhaGemini as falha:
            st.error(str(falha), icon=":material/error:")
        except Exception as erro:
            st.error(sem_chave(f"Não foi possível gerar o texto: {erro}", api_key), icon=":material/error:")
    escrito = st.session_state.get(guarda)
    if escrito:
        if escrito["assinatura"] != assinatura:
            st.warning("Este texto foi gerado antes das últimas alterações no fonte ou nos casos. "
                       "Execute de novo para atualizar.", icon=":material/history:")
        st.caption(f"Texto gerado pelo modelo {escrito['modelo']}.")
        st.markdown(escrito["texto"])

# ======================= FONTES =============================================
with aba_fontes:
    st.subheader("Referências")
    st.html("".join(f"<div class='ts-ref'><p>{html.escape(ref)}</p><p class='uso'>{html.escape(uso)}</p></div>"
                    for ref, uso in REFERENCIAS))
    st.subheader("Origem dos dados desta auditoria")
    st.dataframe(df_origem, hide_index=True, width="stretch")
    st.subheader("Como os resultados são obtidos")
    st.markdown(
        "- **Esperado (caixa-preta):** vem das quatro regras da especificação, sem olhar o código.\n"
        "- **Obtido:** o TestingStudio interpreta em Python a lógica da função carregada "
        "(IF, WHILE, LET, RETURN, comparações e aritmética) e a executa com as entradas de cada caso. "
        "Não é o compilador Informix.\n"
        "- **Grafo e McCabe:** o grafo é montado a partir dos comandos da função; N, E e P são contados "
        "nele e V(G) é calculado pelos três métodos.\n"
        "- **Cobertura:** cada execução registra os comandos por onde passou; daí saem os nós, as arestas, "
        "os caminhos e os pares Def-Uso exercitados.\n"
        "- **Mutação:** cada mutante é executado com a mesma suíte e comparado com o programa original.\n"
        f"- **Sugestões e itens possivelmente infactíveis:** vêm de {analise['sondagens']} entradas de sondagem "
        "(combinações de valores típicos). São indícios para o analista, não provas.\n"
        "- **Textos do Gemini:** gerados por IA a partir dessas tabelas; os números vêm sempre do Python."
    )
