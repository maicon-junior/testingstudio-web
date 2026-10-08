"""
TestingStudio - Laudo de qualidade de testes para programas Logix/4GL (CAD0001)
Teste de Software I, Univille, Prof. Frank Piffer

  Laudo de qualidade : visao para apresentar, em linguagem simples.
  Sprint 1           : caixa-preta, classes de equivalencia (PCE) e valor limite (AVL) com Epsilon.
  Sprint 2           : caixa-branca, grafo de fluxo de controle, nos, arestas e V(G) de McCabe.
  Sprint 3           : fluxo de dados (pares Def-Uso) e teste de mutacao (escore MS).
  Sprint 4           : validacao com gabaritos das aulas, laboratorio e roteiro de apresentacao.

Este arquivo cuida da PAGINA (leitura do .txt, laudo, tabelas, Gemini).
Os calculos das Sprints 2 a 4 e o interpretador de 4GL ficam em motor.py.
Cores, fontes e modo claro/escuro ficam em .streamlit/config.toml e na pasta static/.

Abrir no computador:  dois cliques em Abrir_TestingStudio.bat   (ou: python iniciar.py)
Publicar online:      veja o LEIA-ME.txt. A chave do Gemini fica no servidor, em "Secrets".
"""

import base64
import hashlib
import html
import json
import os
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

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
# As mesmas regras, em linguagem simples, para o laudo.
REGRAS_SIMPLES = [
    ("Recebe três valores em dinheiro", "com duas casas decimais, como R$ 10,00"),
    ("Valor em branco conta como zero", "um campo vazio vale 0,00"),
    ("Valor negativo é recusado", "se algum valor for menor que zero, a resposta é -1, que significa erro"),
    ("Nos demais casos, faz a conta", "primeiro valor × segundo valor + terceiro valor"),
]

# O primeiro e o modelo do manual; os outros entram se ele nao estiver liberado.
MODELOS = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]

# --------------------------------------------------------------------------
# Fontes. Dados conferidos em: Repositorio da USP (livro e capitulo de teste
# estrutural), dblp e IEEE (artigos). Os capitulos 2 e 4 do livro-base seguem
# a numeracao citada nos slides da disciplina.
# --------------------------------------------------------------------------
REFERENCIAS = [
    {"n": 1, "grupo": "Livro-base da disciplina", "curto": "Delamaro, Maldonado e Jino (2007)",
     "texto": "DELAMARO, M. E.; MALDONADO, J. C.; JINO, M. (org.). Introdução ao teste de software. "
              "Rio de Janeiro: Elsevier, 2007. 408 p. ISBN 978-85-352-2634-8.",
     "uso": "Fundamentos e vocabulário de todo o laudo: teste funcional (cap. 2), oráculo e teste de mutação.",
     "link": "https://repositorio.usp.br/item/001726007"},
    {"n": 2, "grupo": "Livro-base da disciplina", "curto": "Barbosa et al. (2007)",
     "texto": "BARBOSA, E. F.; CHAIM, M. L.; VINCENZI, A. M. R.; DELAMARO, M. E.; JINO, M.; MALDONADO, J. C. "
              "Teste estrutural. In: DELAMARO, M. E.; MALDONADO, J. C.; JINO, M. (org.). Introdução ao teste "
              "de software. Rio de Janeiro: Elsevier, 2007. cap. 4.",
     "uso": "Grafo de fluxo de controle, critérios Todos-Nós e Todas-Arestas, caminhos e critérios de fluxo "
            "de dados (Sprints 2 e 3).",
     "link": "https://repositorio.usp.br/item/001820393"},
    {"n": 3, "grupo": "Teste funcional (caixa-preta)", "curto": "Myers, Sandler e Badgett (2011)",
     "texto": "MYERS, G. J.; SANDLER, C.; BADGETT, T. The art of software testing. 3. ed. Hoboken: "
              "John Wiley & Sons, 2011. (1. ed.: 1979).",
     "uso": "Classes de equivalência, análise do valor limite e a regra de um caso por classe inválida.",
     "link": ""},
    {"n": 4, "grupo": "Teste funcional (caixa-preta)", "curto": "White e Cohen (1980)",
     "texto": "WHITE, L. J.; COHEN, E. I. A domain strategy for computer program testing. IEEE Transactions "
              "on Software Engineering, v. SE-6, n. 3, p. 247-257, 1980. DOI: 10.1109/TSE.1980.234486.",
     "uso": "Pontos On e Off da análise de fronteira (o 0,00 e o 0,00 − ε).",
     "link": "https://doi.org/10.1109/TSE.1980.234486"},
    {"n": 5, "grupo": "Teste estrutural (caixa-branca)", "curto": "McCabe (1976)",
     "texto": "McCABE, T. J. A complexity measure. IEEE Transactions on Software Engineering, v. SE-2, n. 4, "
              "p. 308-320, dez. 1976. DOI: 10.1109/TSE.1976.233837.",
     "uso": "Complexidade ciclomática V(G), as três fórmulas equivalentes e o conjunto básico de caminhos.",
     "link": "https://doi.org/10.1109/TSE.1976.233837"},
    {"n": 6, "grupo": "Fluxo de dados", "curto": "Rapps e Weyuker (1985)",
     "texto": "RAPPS, S.; WEYUKER, E. J. Selecting software test data using data flow information. IEEE "
              "Transactions on Software Engineering, v. SE-11, n. 4, p. 367-375, abr. 1985. "
              "DOI: 10.1109/TSE.1985.232226.",
     "uso": "Definição, c-uso, p-uso, pares Def-Uso e a hierarquia de critérios (Todos-Usos e abaixo).",
     "link": "https://doi.org/10.1109/TSE.1985.232226"},
    {"n": 7, "grupo": "Teste de mutação", "curto": "DeMillo, Lipton e Sayward (1978)",
     "texto": "DeMILLO, R. A.; LIPTON, R. J.; SAYWARD, F. G. Hints on test data selection: help for the "
              "practicing programmer. Computer, v. 11, n. 4, p. 34-41, 1978. DOI: 10.1109/C-M.1978.218136.",
     "uso": "Hipótese do programador competente e efeito de acoplamento, que justificam os mutantes.",
     "link": "https://doi.org/10.1109/C-M.1978.218136"},
    {"n": 8, "grupo": "Normas e guias", "curto": "ISTQB CTFL v4.0 (2023)",
     "texto": "ISTQB. Certified Tester Foundation Level Syllabus, versão 4.0. International Software Testing "
              "Qualifications Board, 2023. Seções 4.2.1, 4.2.2, 4.3.1 e 4.3.2.",
     "uso": "Definições de partição de equivalência, valor limite, cobertura de comandos e de desvios.",
     "link": "https://www.istqb.org/"},
    {"n": 9, "grupo": "Normas e guias", "curto": "ISO/IEC/IEEE 29119-4 (2021)",
     "texto": "ISO/IEC/IEEE 29119-4:2021. Software and systems engineering: software testing. "
              "Part 4: Test techniques. Genebra: ISO, 2021.",
     "uso": "Descrição normativa das técnicas de teste e das medidas de cobertura usadas no laudo.",
     "link": ""},
    {"n": 10, "grupo": "Normas e guias", "curto": "SWEBOK v3.0 (2014)",
     "texto": "BOURQUE, P.; FAIRLEY, R. E. (ed.). Guide to the Software Engineering Body of Knowledge "
              "(SWEBOK), version 3.0. IEEE Computer Society, 2014. cap. 4: Software Testing.",
     "uso": "Verificação e validação, oráculo de teste e terminologia geral.",
     "link": ""},
    {"n": 11, "grupo": "Objeto de teste", "curto": "IBM Informix 4GL",
     "texto": "IBM. IBM Informix 4GL Reference Manual. Tipo de dado DECIMAL(p,s).",
     "uso": "Precisão e escala do tipo DECIMAL(12,2), de onde sai o Épsilon (ε = 0,01).",
     "link": ""},
    {"n": 12, "grupo": "Material da disciplina", "curto": "Manual do laboratório (2026)",
     "texto": "PIFFER, F. Manual de laboratório, Sprint 1: TestingStudio Web, auditoria de caixa-preta "
              "(PCE e AVL) do CAD0001. Teste de Software I (ementa 62371). Joinville: Univille, 2026.",
     "uso": "Especificação do CAD0001, usada como oráculo, e a tabela dos quatro pontos de fronteira.",
     "link": ""},
    {"n": 13, "grupo": "Material da disciplina", "curto": "Slides da disciplina (2026)",
     "texto": "PIFFER, F. Teste de Software I: slides das aulas de 19/08, 26/08, 09/09, 16/09, 21/09, 28/09, "
              "30/09 e 05/10/2026. Joinville: Univille, 2026.",
     "uso": "19/08 e 05/10: oráculo. 26/08: PCE, AVL e o problema do triângulo. 09/09 e 21/09: grafo, "
            "caminhos e Bhaskara. 28/09: McCabe. 30/09: pares DU e mutação. São os seis exercícios da validação.",
     "link": ""},
]
REF = {r["n"]: r for r in REFERENCIAS}

# Em que cada parte do laudo se apoia: (numero da referencia, detalhe).
BASES = {
    "caixa_preta": [(1, "cap. 2"), (3, ""), (4, ""), (8, "seções 4.2.1 e 4.2.2"), (12, ""), (13, "aula de 26/08")],
    "epsilon": [(11, ""), (12, "Tabela 1")],
    "caixa_branca": [(2, "cap. 4"), (5, ""), (8, "seções 4.3.1 e 4.3.2"), (13, "aulas de 09/09, 21/09 e 28/09")],
    "fluxo": [(2, "cap. 4"), (6, ""), (13, "aula de 30/09")],
    "mutacao": [(1, "teste de mutação"), (7, ""), (13, "aula de 30/09")],
    "validacao": [(10, "cap. 4"), (1, "oráculo"), (13, "aulas de 19/08 e 05/10")],
}

GLOSSARIO = [
    ("Caixa-preta", "Testar pelo que o programa promete, sem olhar o código: entra um valor, confere-se a resposta."),
    ("Classe de equivalência", "Grupo de valores que o programa deve tratar do mesmo jeito. Basta testar um de cada grupo."),
    ("Valor limite", "O valor exatamente na fronteira entre dois grupos, onde os erros mais acontecem."),
    ("Épsilon (ε)", "O menor passo que o tipo de dado aceita. Em dinheiro com duas casas, 0,01: um centavo."),
    ("Oráculo", "A fonte do resultado esperado. Aqui, a regra escrita no manual, nunca o próprio código."),
    ("Caixa-branca", "Testar olhando por dentro: garantir que cada trecho e cada desvio do código foi executado."),
    ("Grafo de fluxo de controle", "O mapa do programa: cada trecho é um nó (círculo) e cada passagem é uma aresta (seta)."),
    ("Complexidade ciclomática V(G)", "Quantos caminhos independentes o programa tem. É o mínimo de testes para passar por todos os desvios."),
    ("Cobertura", "Quanto do programa os testes de fato percorreram, em porcentagem."),
    ("Par Def-Uso", "O percurso de um dado: do ponto em que recebe valor até o ponto em que esse valor é usado."),
    ("Mutante", "Uma cópia do programa com um defeito plantado de propósito, para ver se os testes percebem."),
    ("Escore de mutação", "A porcentagem de defeitos plantados que os testes perceberam. Mede a qualidade dos próprios testes."),
    ("Mutante equivalente", "Uma alteração que não muda o comportamento; nenhum teste consegue percebê-la."),
    ("Caminho infactível", "Um caminho que existe no mapa, mas que nenhum dado real consegue percorrer."),
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
# PASSO 3 - Apresentacao: formatos e tabelas
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


# ==========================================================================
# PASSO 3B - Visual: estilo (claro e escuro), componentes do laudo e relatorio
# ==========================================================================
# As cores usam light-dark(): o navegador escolhe o tom certo conforme o modo
# claro ou escuro que o Streamlit aplica na pagina (color-scheme da .stApp).
ESTILO_CSS = """
.stApp, .ts-relatorio {
  --ts-tinta: light-dark(#131c28, #e6edf5);
  --ts-suave: light-dark(#536175, #9badc1);
  --ts-linha: light-dark(#d5dde8, #283748);
  --ts-cartao: light-dark(#ffffff, #111a25);
  --ts-relevo: light-dark(#eef3f9, #172332);
  --ts-destaque: light-dark(#1a56b8, #78b0f5);
  --ts-destaque-suave: light-dark(#e1eafa, #15283f);
  --ts-ok: light-dark(#12803a, #55cc80);
  --ts-ok-suave: light-dark(#e2f3e7, #10301d);
  --ts-ruim: light-dark(#bf322e, #f3857e);
  --ts-ruim-suave: light-dark(#fbe6e5, #3b1918);
  --ts-alerta: light-dark(#8a5a00, #f1bb52);
  --ts-alerta-suave: light-dark(#fbf0d6, #33270e);
  --ts-valido: #2a78d6;
  --ts-invalido: #eb6834;
}
.block-container { max-width: 1200px; padding-top: 3.6rem; }
[data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 { letter-spacing: -0.01em; }
.ts-num { font-variant-numeric: tabular-nums; }

/* ---- topo e identificacao ---- */
.ts-topo { display:flex; align-items:center; justify-content:space-between; gap:1rem; flex-wrap:wrap;
  padding: .2rem 0 1.1rem; border-bottom: 1px solid var(--ts-linha); margin-bottom: 1.2rem; }
.ts-marca { display:flex; align-items:center; gap:.85rem; }
.ts-marca .ts-logo { width:46px; height:46px; flex: none; }
.ts-nome { font-size: 1.9rem; font-weight: 700; letter-spacing: -0.025em; line-height: 1.05; margin: 0; color: var(--ts-tinta); }
.ts-slogan { margin: .15rem 0 0; color: var(--ts-suave); font-size: 1rem; }
.ts-credito { color: var(--ts-suave); font-size: .85rem; text-align: right; line-height: 1.4; }

.ts-boas-vindas { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 1rem; margin: .4rem 0 1rem; }
.ts-boas-vindas article { background: var(--ts-cartao); border:1px solid var(--ts-linha); border-radius: 12px; padding: 1rem 1.1rem; }
.ts-boas-vindas h3 { margin: .35rem 0 .3rem; font-size: 1.05rem; font-weight: 600; color: var(--ts-tinta); }
.ts-boas-vindas p { margin: 0; color: var(--ts-suave); font-size: .95rem; line-height: 1.5; }

.ts-faixa { display:grid; grid-template-columns: 1.35fr 1.45fr .75fr 1.05fr 1.1fr; gap: 0; margin: .2rem 0 1.2rem;
  border: 1px solid var(--ts-linha); border-radius: 12px; background: var(--ts-cartao); overflow: hidden; }
.ts-faixa div { padding: .7rem .95rem; border-right: 1px solid var(--ts-linha); min-width: 0; }
.ts-faixa div:last-child { border-right: 0; }
.ts-faixa dt { color: var(--ts-suave); font-size: .78rem; margin: 0 0 .15rem; }
.ts-faixa dd { margin: 0; font-weight: 600; color: var(--ts-tinta); font-size: .95rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ts-faixa code { font-size: .85rem; background: none; padding: 0; color: inherit; }

/* ---- chips de estado (sempre icone + texto) ---- */
.ts-chip { display:inline-flex; align-items:center; gap:.35rem; padding:.18rem .6rem; border-radius:999px;
  font-size:.82rem; font-weight:600; white-space:nowrap; border:1px solid transparent; }
.ts-chip i { font-style: normal; font-weight: 700; font-size: .9em; line-height: 1; }
.ts-chip-ok { color: var(--ts-ok); background: var(--ts-ok-suave); border-color: color-mix(in srgb, var(--ts-ok) 35%, transparent); }
.ts-chip-ruim { color: var(--ts-ruim); background: var(--ts-ruim-suave); border-color: color-mix(in srgb, var(--ts-ruim) 35%, transparent); }
.ts-chip-alerta { color: var(--ts-alerta); background: var(--ts-alerta-suave); border-color: color-mix(in srgb, var(--ts-alerta) 35%, transparent); }
.ts-chip-neutro { color: var(--ts-suave); background: var(--ts-relevo); border-color: var(--ts-linha); }

/* ---- veredito ---- */
.ts-veredito { position: relative; display:grid; grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr); gap: 1.6rem;
  background: var(--ts-cartao); border:1px solid var(--ts-linha); border-radius: 16px; padding: 1.6rem 1.7rem 1.5rem 2rem; overflow: hidden; }
.ts-veredito::before { content:""; position:absolute; left:0; top:0; bottom:0; width:7px; background: var(--ts-cor); }
.ts-veredito.ts-ok { --ts-cor: var(--ts-ok); } .ts-veredito.ts-ruim { --ts-cor: var(--ts-ruim); } .ts-veredito.ts-alerta { --ts-cor: var(--ts-alerta); }
.ts-veredito h2 { font-size: 1.85rem; line-height: 1.18; margin: .7rem 0 .55rem; font-weight: 700; letter-spacing: -0.02em; color: var(--ts-tinta); }
.ts-veredito p { margin: 0; color: var(--ts-suave); font-size: 1.05rem; line-height: 1.55; max-width: 60ch; }
.ts-fatos { display:grid; grid-template-columns: 1fr 1fr; gap: .75rem; margin: 0; align-content: center; }
.ts-fatos div { background: var(--ts-relevo); border-radius: 12px; padding: .75rem .9rem; }
.ts-fatos dt { color: var(--ts-suave); font-size: .82rem; margin-bottom: .2rem; min-height: 2.4em; }
.ts-fatos dd { margin: 0; font-size: 1.6rem; font-weight: 700; color: var(--ts-tinta); font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }

/* ---- blocos e titulos de secao do laudo ---- */
.ts-secao { margin: 2.2rem 0 .9rem; }
.ts-secao h2 { font-size: 1.4rem; margin: 0 0 .25rem; font-weight: 650; color: var(--ts-tinta); }
.ts-secao p { margin: 0; color: var(--ts-suave); max-width: 75ch; }

/* ---- regras (o combinado) ---- */
.ts-regras { border:1px solid var(--ts-linha); border-radius: 14px; background: var(--ts-cartao); overflow:hidden; }
.ts-regra { display:grid; grid-template-columns: 2.2rem minmax(0,1fr) auto; gap: .9rem; align-items:center;
  padding: .85rem 1.1rem; border-bottom: 1px solid var(--ts-linha); }
.ts-regra:last-child { border-bottom: 0; }
.ts-regra .ts-n { width: 2rem; height: 2rem; border-radius: 50%; display:grid; place-items:center; font-weight:700;
  background: var(--ts-destaque-suave); color: var(--ts-destaque); font-size: .95rem; }
.ts-regra b { display:block; color: var(--ts-tinta); font-weight: 600; }
.ts-regra small { color: var(--ts-suave); font-size: .9rem; }
.ts-regra .ts-direita { text-align:right; display:flex; flex-direction:column; align-items:flex-end; gap:.25rem; }
.ts-regra .ts-direita small { font-size: .8rem; }

/* ---- as quatro conferencias ---- */
.ts-estacoes { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 1rem; }
.ts-estacao { display:flex; flex-direction:column; background: var(--ts-cartao); border:1px solid var(--ts-linha);
  border-radius: 14px; padding: 1.05rem 1.1rem 1.1rem; }
.ts-estacao-topo { display:flex; flex-direction: column; align-items:flex-start; gap:.45rem; }
.ts-passo { font-size: .8rem; font-weight: 700; color: var(--ts-destaque); }
.ts-estacao h3 { margin: .65rem 0 .1rem; font-size: 1.12rem; font-weight: 650; line-height: 1.25; color: var(--ts-tinta); }
.ts-tecnico { margin: 0 0 .6rem; color: var(--ts-destaque); font-size: .82rem; font-weight: 500; }
.ts-estacao > p.ts-texto { margin: 0 0 .9rem; color: var(--ts-suave); font-size: .92rem; line-height: 1.5; flex: 1; }
.ts-medida { display:flex; align-items:baseline; gap:.45rem; flex-wrap: wrap; }
.ts-medida b { font-size: 1.65rem; font-weight: 700; letter-spacing: -0.02em; color: var(--ts-tinta); font-variant-numeric: tabular-nums; }
.ts-medida span { color: var(--ts-suave); font-size: .88rem; line-height: 1.3; }
.ts-medidor { height: 8px; border-radius: 999px; background: var(--ts-destaque-suave); margin: .55rem 0 .6rem; overflow:hidden; }
.ts-medidor span { display:block; height:100%; border-radius: 999px; background: var(--ts-destaque); }
.ts-detalhe { margin: 0; color: var(--ts-suave); font-size: .84rem; line-height: 1.45; }

/* ---- exemplo do defeito ---- */
.ts-exemplo { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 0; border:1px solid var(--ts-linha);
  border-radius: 14px; overflow:hidden; background: var(--ts-cartao); }
.ts-exemplo > div { padding: 1rem 1.15rem; border-right:1px solid var(--ts-linha); }
.ts-exemplo > div:last-child { border-right: 0; }
.ts-exemplo .ts-rot { display:block; color: var(--ts-suave); font-size: .82rem; margin-bottom: .3rem; }
.ts-exemplo b { display:block; font-size: 1.45rem; font-weight: 700; color: var(--ts-tinta); font-variant-numeric: tabular-nums; }
.ts-exemplo small { display:block; color: var(--ts-suave); font-size: .88rem; margin-top: .2rem; line-height: 1.4; }
.ts-exemplo .ts-errado { background: var(--ts-ruim-suave); }
.ts-exemplo .ts-errado b { color: var(--ts-ruim); }
.ts-exemplo .ts-certo { background: var(--ts-ok-suave); }
.ts-exemplo .ts-certo b { color: var(--ts-ok); }
.ts-duas { display:grid; grid-template-columns: minmax(0,1.25fr) minmax(0,1fr); gap: 1rem; margin-top: 1rem; }
.ts-cartao { background: var(--ts-cartao); border:1px solid var(--ts-linha); border-radius: 14px; padding: 1.05rem 1.2rem; }
.ts-cartao h3 { margin: 0 0 .45rem; font-size: 1.05rem; font-weight: 650; color: var(--ts-tinta); }
.ts-cartao p { margin: 0 0 .5rem; color: var(--ts-suave); line-height: 1.55; }
.ts-cartao p:last-child { margin-bottom: 0; }
.ts-cartao pre { margin: .4rem 0 .5rem; padding: .7rem .85rem; border-radius: 10px; background: var(--ts-relevo);
  color: var(--ts-tinta); font-family: 'IBM Plex Mono', Consolas, monospace; font-size: .85rem; white-space: pre; overflow-x: auto; }

/* ---- confianca e limites ---- */
.ts-confianca { display:grid; grid-template-columns: 210px minmax(0,1fr); gap: 1.4rem; align-items: start; }
.ts-placar { background: var(--ts-ok-suave); border-radius: 14px; padding: 1.1rem 1.2rem; text-align:center; }
.ts-placar b { display:block; font-size: 3rem; line-height: 1; font-weight: 700; color: var(--ts-ok); letter-spacing: -0.03em; }
.ts-placar span { display:block; color: var(--ts-tinta); font-size: .9rem; margin-top: .45rem; line-height: 1.35; }
.ts-placar.ts-placar-ruim { background: var(--ts-ruim-suave); } .ts-placar.ts-placar-ruim b { color: var(--ts-ruim); }
.ts-cartao ul.ts-lista { list-style: none; padding: 0; margin: .3rem 0 .2rem; display:grid; grid-template-columns: 1fr 1fr; gap: .35rem 1.2rem; }
.ts-cartao ul.ts-lista li { display:flex; justify-content: space-between; gap: .6rem; padding: .4rem 0; border-bottom: 1px dashed var(--ts-linha); color: var(--ts-tinta); font-size: .92rem; }
.ts-cartao ul.ts-lista li span { color: var(--ts-suave); white-space: nowrap; }
.ts-marcadores { margin: .2rem 0 0; padding-left: 1.1rem; color: var(--ts-suave); line-height: 1.6; }
.ts-marcadores b { color: var(--ts-tinta); font-weight: 600; }

/* ---- base teorica e fontes ---- */
.ts-base { display:flex; flex-wrap: wrap; align-items:center; gap: .4rem .5rem; margin: .2rem 0 1rem; }
.ts-base > span:first-child { color: var(--ts-suave); font-size: .82rem; margin-right: .2rem; }
.ts-cita { display:inline-flex; align-items:center; gap:.4rem; padding:.2rem .6rem .2rem .25rem; border-radius: 999px;
  background: var(--ts-relevo); border: 1px solid var(--ts-linha); color: var(--ts-tinta); font-size: .82rem; }
.ts-cita b { display:inline-grid; place-items:center; min-width: 1.45rem; height: 1.45rem; padding: 0 .3rem; border-radius: 999px;
  background: var(--ts-destaque); color: var(--ts-cartao); font-size: .74rem; font-weight: 700; }
.ts-explica { border-left: 4px solid var(--ts-destaque); background: var(--ts-destaque-suave); border-radius: 0 12px 12px 0;
  padding: .9rem 1.1rem; margin: .3rem 0 .7rem; }
.ts-explica h3 { margin: 0 0 .3rem; font-size: 1.05rem; font-weight: 650; color: var(--ts-tinta); }
.ts-explica p { margin: 0; color: var(--ts-tinta); line-height: 1.55; max-width: 85ch; }
.ts-fontes-grupo { margin: 1.4rem 0 .5rem; font-size: 1rem; font-weight: 650; color: var(--ts-destaque); }
.ts-fonte { display:grid; grid-template-columns: 2.4rem minmax(0,1fr); gap: .8rem; padding: .85rem 0; border-bottom: 1px solid var(--ts-linha); }
.ts-fonte .ts-fn { width: 2.1rem; height: 2.1rem; border-radius: 10px; display:grid; place-items:center; font-weight: 700;
  background: var(--ts-destaque-suave); color: var(--ts-destaque); }
.ts-fonte p { margin: 0; color: var(--ts-tinta); line-height: 1.5; }
.ts-fonte .ts-uso { color: var(--ts-suave); font-size: .9rem; margin-top: .3rem; }
.ts-fonte a { color: var(--ts-destaque); }
.ts-glossario { display:grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: .2rem 1.6rem; margin: 0; }
.ts-glossario div { padding: .6rem 0; border-bottom: 1px solid var(--ts-linha); }
.ts-glossario dt { font-weight: 600; color: var(--ts-tinta); }
.ts-glossario dd { margin: .15rem 0 0; color: var(--ts-suave); line-height: 1.45; font-size: .93rem; }

/* ---- matriz de cobertura ---- */
.ts-matriz { width:100%; border-collapse:collapse; font-size:.92rem; }
.ts-matriz th, .ts-matriz td { padding:.6rem .7rem; text-align:left; border-bottom:1px solid var(--ts-linha); color: var(--ts-tinta); }
.ts-matriz thead th { font-weight:600; color: var(--ts-suave); font-size: .85rem; }
.ts-matriz small { margin-left:.45rem; color: var(--ts-suave); }

/* ---- regua da fronteira (SVG) ---- */
.ts-regua { width: 100%; height: auto; display:block; font-family: inherit; }
.ts-regua .ts-tinta { fill: var(--ts-tinta); } .ts-regua .ts-suave { fill: var(--ts-suave); }
.ts-regua .ts-zero { stroke: var(--ts-tinta); }
.ts-regua .ts-ponto { fill: #ffffff; stroke: #131c28; }

/* ---- grafo (Graphviz): cores trocadas conforme o modo claro ou escuro ---- */
[data-testid="stGraphVizChart"] svg text, .ts-gfc svg text { fill: var(--ts-tinta); }
[data-testid="stGraphVizChart"] svg [stroke="#1f4e79"], .ts-gfc svg [stroke="#1f4e79"] { stroke: var(--ts-destaque); }
[data-testid="stGraphVizChart"] svg [fill="#1f4e79"], .ts-gfc svg [fill="#1f4e79"] { fill: var(--ts-destaque); }
[data-testid="stGraphVizChart"] svg [fill="#e1eafa"], .ts-gfc svg [fill="#e1eafa"] { fill: var(--ts-destaque-suave); }
[data-testid="stGraphVizChart"] svg [stroke="#1b2a3d"], .ts-gfc svg [stroke="#1b2a3d"] { stroke: var(--ts-tinta); }
[data-testid="stGraphVizChart"] svg [fill="#1b2a3d"], .ts-gfc svg [fill="#1b2a3d"] { fill: var(--ts-tinta); }

@media (max-width: 1100px) {
  .ts-estacoes { grid-template-columns: repeat(2, minmax(0,1fr)); }
  .ts-faixa { grid-template-columns: 1fr 1fr; } .ts-faixa div { border-bottom: 1px solid var(--ts-linha); }
}
@media (max-width: 760px) {
  .ts-veredito, .ts-confianca, .ts-duas, .ts-exemplo, .ts-boas-vindas, .ts-cartao ul.ts-lista, .ts-glossario { grid-template-columns: 1fr; }
  .ts-estacoes, .ts-faixa { grid-template-columns: 1fr; }
  .ts-exemplo > div { border-right: 0; border-bottom: 1px solid var(--ts-linha); }
}
"""

ICONES = {"ok": "✓", "ruim": "✕", "alerta": "!", "neutro": "–"}
# Marca do produto: uma lupa sobre a linha de fronteira (o centro do teste de valor limite).
_MARCA_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" stroke="#4a86e8">'
              '<rect x="1.5" y="1.5" width="45" height="45" rx="12" stroke-width="3"/>'
              '<path d="M9 31h30" stroke-width="3" stroke-linecap="round" opacity=".4"/>'
              '<path d="M24 26v10" stroke-width="3" stroke-linecap="round"/>'
              '<circle cx="21" cy="19" r="7.5" stroke-width="3"/>'
              '<path d="M26.5 24.5l5 5" stroke-width="3.4" stroke-linecap="round"/></svg>')
MARCA = ('<img class="ts-logo" alt="" src="data:image/svg+xml;base64,'
         + base64.b64encode(_MARCA_SVG.encode()).decode() + '">')

ACHADOS_SIMPLES = {
    "NEGATIVO_ACEITO": ("Aceita valor negativo", "deveria recusar com -1 e faz a conta"),
    "VALIDO_REJEITADO": ("Recusa um valor permitido", "responde -1 para um valor que a regra aceita"),
    "NULO": ("Não trata campo em branco como zero", "devolve vazio em vez de fazer a conta com 0,00"),
    "CALCULO": ("Faz a conta errada", "o resultado não bate com 1º × 2º + 3º"),
    "ERRO": ("Para no meio da execução", "o programa não chega a dar uma resposta"),
}
ORDINAL = ["primeiro", "segundo", "terceiro"]


def esc(texto) -> str:
    return html.escape(str(texto))


def chip(texto: str, tipo: str) -> str:
    return f'<span class="ts-chip ts-chip-{tipo}"><i aria-hidden="true">{ICONES[tipo]}</i>{esc(texto)}</span>'


def html_topo() -> str:
    return (f'<header class="ts-topo"><div class="ts-marca">{MARCA}<div>'
            '<p class="ts-nome">TestingStudio</p>'
            '<p class="ts-slogan">Laudo de qualidade de testes para programas Logix/4GL</p></div></div>'
            '<div class="ts-credito">Teste de Software I, Univille<br>Prof. Frank Piffer</div></header>')


def html_boas_vindas() -> str:
    passos = [
        ("1", "Anexe o programa", "Envie o arquivo .txt com o código 4GL. Nada é analisado antes disso."),
        ("2", "A ferramenta testa de quatro formas", "Ela executa o programa com valores escolhidos a dedo e "
                                                    "mede o quanto desse programa os testes alcançaram."),
        ("3", "Você recebe um laudo", "Um resumo em linguagem simples, com as provas técnicas e as fontes logo abaixo."),
    ]
    return '<div class="ts-boas-vindas">' + "".join(
        f'<article><span class="ts-passo">Passo {n}</span><h3>{esc(t)}</h3><p>{esc(x)}</p></article>'
        for n, t, x in passos) + "</div>"


def html_faixa(d) -> str:
    itens = [("Programa", d["arquivo"]), ("Função testada", f"{FUNCAO_ALVO}"),
             ("Tamanho", f"{d['linhas']} linhas"), ("Analisado em", d["quando"][:16]),
             ("Impressão digital", d["sha"][:16] + "…")]
    return '<dl class="ts-faixa">' + "".join(
        f'<div><dt>{esc(r)}</dt><dd title="{esc(v)}">{esc(v) if r != "Função testada" else f"<code>{esc(v)}</code>"}</dd></div>'
        for r, v in itens) + "</dl>"


def html_base(chave: str) -> str:
    """Faixa 'Base teorica' com as fontes numeradas que sustentam uma parte do laudo."""
    citas = "".join(f'<span class="ts-cita"><b>{n}</b>{esc(REF[n]["curto"])}{", " + esc(det) if det else ""}</span>'
                    for n, det in BASES[chave])
    return f'<div class="ts-base"><span>Base teórica</span>{citas}</div>'


def html_explica(titulo: str, texto: str, chave: str = "") -> str:
    return (f'<div class="ts-explica"><h3>{esc(titulo)}</h3><p>{texto}</p></div>'
            + (html_base(chave) if chave else ""))


def html_secao(titulo: str, texto: str = "") -> str:
    return f'<div class="ts-secao"><h2>{esc(titulo)}</h2>{f"<p>{texto}</p>" if texto else ""}</div>'


def estado_geral(d) -> str:
    q, a, mut = d["qualidade"], d["analise"], d["mutacao"]
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    if q["reprovados"]:
        return "ruim"
    if nos[0] < nos[1] or arestas[0] < arestas[1] or (mut["MS"] is not None and mut["MS"] < 100):
        return "alerta"
    return "ok"


def html_veredito(d) -> str:
    q, mut = d["qualidade"], d["mutacao"]
    estado = estado_geral(d)
    ok, total = d["validacao_resumo"]
    causas = [ACHADOS_SIMPLES[c][0].lower() for c in q["achados"]]
    if estado == "ruim":
        selo = chip("Reprovado na conferência", "ruim")
        titulo = "O programa ainda não cumpre tudo o que foi combinado."
        texto = (f"{q['reprovados']} de {q['total']} testes receberam uma resposta diferente da regra. "
                 f"{'O motivo é um só' if len(causas) == 1 else 'Os motivos'}: {', '.join(causas)}.")
    elif estado == "alerta":
        selo = chip("Aprovado, com ressalvas", "alerta")
        titulo = "O programa respondeu como combinado, mas os testes ainda não alcançam tudo."
        texto = (f"Os {q['aprovados']} testes com resposta definida foram aprovados. Parte do código ou dos defeitos "
                 "plantados ainda escapa aos testes; veja as conferências abaixo.")
    else:
        selo = chip("Aprovado na conferência", "ok")
        titulo = "O programa respondeu como combinado em todos os testes."
        texto = (f"Os {q['aprovados']} testes foram aprovados, passaram por todo o código e perceberam todos os "
                 "defeitos plantados de propósito.")
    fatos = [("Testes executados", q["total"]), ("Formas de teste aplicadas", 4),
             ("Defeitos plantados percebidos", f"{mut['Md']}/{mut['Mt'] - mut['Me']}"),
             ("Conferências da própria ferramenta", f"{ok}/{total}")]
    return (f'<section class="ts-veredito ts-{estado}"><div>{selo}<h2>{esc(titulo)}</h2><p>{esc(texto)}</p></div>'
            '<dl class="ts-fatos">' + "".join(f"<div><dt>{esc(r)}</dt><dd>{esc(v)}</dd></div>" for r, v in fatos)
            + "</dl></section>")


def situacao_das_regras(d):
    """Para cada regra do combinado: quantos testes a verificam e se foi cumprida."""
    casos, achados = d["casos_lista"], d["qualidade"]["achados"]
    com_nulo = [c for c in casos if any(v is None for v in c["entradas"])]
    com_negativo = [c for c in casos if any(v is not None and v < 0 for v in c["entradas"])]
    so_validos = [c for c in casos if c not in com_nulo and c not in com_negativo]
    regras = [
        (len(casos), []),
        (len(com_nulo), achados.get("NULO", [])),
        (len(com_negativo), achados.get("NEGATIVO_ACEITO", []) + achados.get("VALIDO_REJEITADO", [])),
        (len(so_validos), achados.get("CALCULO", [])),
    ]
    return regras


def html_regras(d) -> str:
    linhas = []
    for i, ((titulo, detalhe), (verificada, falhas)) in enumerate(zip(REGRAS_SIMPLES, situacao_das_regras(d)), 1):
        estado = chip(f"Não cumprida em {len(falhas)} testes", "ruim") if falhas else chip("Cumprida", "ok")
        linhas.append(f'<div class="ts-regra"><span class="ts-n">{i}</span><div><b>{esc(titulo)}</b>'
                      f'<small>{esc(detalhe)}</small></div><div class="ts-direita">{estado}'
                      f'<small>verificada em {verificada} testes</small></div></div>')
    return '<div class="ts-regras">' + "".join(linhas) + "</div>"


def _medidor(fracao: float) -> str:
    return f'<div class="ts-medidor" aria-hidden="true"><span style="width:{max(0, min(100, fracao * 100)):.0f}%"></span></div>'


def html_estacoes(d) -> str:
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    usos = a["criterios"]["Todos-Usos"]
    com_oraculo = q["aprovados"] + q["reprovados"]
    estrutura_total = nos[0] == nos[1] and arestas[0] == arestas[1]
    ms = mut["MS"]
    cartoes = [
        ("Conferência 1", "Conferimos as respostas", "Caixa-preta: classes de equivalência e valor limite",
         "Como conferir uma calculadora sem abri-la: digitamos valores e comparamos cada resposta com a regra "
         "combinada. Os valores foram escolhidos onde o erro costuma se esconder: o zero, um centavo abaixo "
         "dele e campos em branco.",
         f"{q['aprovados']} de {com_oraculo}", "respostas iguais ao combinado",
         q["aprovados"] / com_oraculo if com_oraculo else 0,
         f"Grupos de valores testados: {q['classes'][0]} de {q['classes'][1]}. "
         f"Fronteiras testadas: {q['pontos'][0]} de {q['pontos'][1]}.",
         chip("Encontrou defeito", "ruim") if q["reprovados"] else chip("Tudo conforme", "ok")),
        ("Conferência 2", "Percorremos o programa por dentro", "Caixa-branca: grafo de fluxo e McCabe",
         "Como percorrer todas as ruas de um bairro: desenhamos o mapa do código e conferimos se os testes "
         "passaram por cada trecho e por cada desvio.",
         porcento(arestas), "dos desvios percorridos",
         min(nos[0] / nos[1] if nos[1] else 0, arestas[0] / arestas[1] if arestas[1] else 0),
         f"Trechos percorridos: {porcento(nos)}. O mapa tem {m['N']} trechos, {m['E']} ligações e "
         f"{m['V']} caminhos independentes.",
         chip("Cobertura total", "ok") if estrutura_total else chip("Cobertura parcial", "alerta")),
        ("Conferência 3", "Seguimos cada dado", "Fluxo de dados: pares Def-Uso",
         "Como rastrear uma encomenda: cada valor foi acompanhado do ponto em que é definido até cada ponto "
         "em que é usado.",
         f"{usos[0]} de {usos[1]}", "percursos de dados exercitados",
         usos[0] / usos[1] if usos[1] else 0,
         f"{len(a['fluxo_tabela'])} variáveis acompanhadas, em cálculos e em decisões.",
         chip("Todos exercitados", "ok") if usos[0] == usos[1] else chip("Faltam percursos", "alerta")),
        ("Conferência 4", "Testamos os próprios testes", "Teste de mutação: escore MS",
         "Como um simulado de incêndio: plantamos defeitos de propósito, um de cada vez, para ver se os "
         "testes dão o alarme.",
         f"{mut['Md']} de {mut['Mt'] - mut['Me']}", "defeitos plantados foram percebidos",
         (ms or 0) / 100,
         f"Escore de mutação: {texto_ms(mut)}." + (f" {mut['Me']} equivalentes descontados." if mut["Me"] else ""),
         chip("Testes atentos", "ok") if ms is not None and ms >= 100 else
         (chip("Bons, com lacunas", "alerta") if ms is not None and ms >= 80 else chip("Testes fracos", "ruim"))),
    ]
    blocos = []
    for passo, titulo, tecnico, texto, numero, rotulo, fracao, detalhe, selo in cartoes:
        blocos.append(f'<article class="ts-estacao"><div class="ts-estacao-topo"><span class="ts-passo">{esc(passo)}'
                      f'</span>{selo}</div><h3>{esc(titulo)}</h3><p class="ts-tecnico">{esc(tecnico)}</p>'
                      f'<p class="ts-texto">{esc(texto)}</p><div class="ts-medida"><b>{esc(numero)}</b>'
                      f'<span>{esc(rotulo)}</span></div>{_medidor(fracao)}<p class="ts-detalhe">{esc(detalhe)}</p></article>')
    return '<div class="ts-estacoes">' + "".join(blocos) + "</div>"


def _descreve_entrada(caso, nomes) -> str:
    if caso["tecnica"] == "Extra":
        return caso["observacao"] or "caso extra"
    i = nomes.index(caso["alvo"]) if caso["alvo"] in nomes else 0
    onde = f"no {ORDINAL[i]} valor"
    return {"On-Point": f"zero exato {onde}", "Off-Point": f"um centavo abaixo de zero {onde}",
            "Interior": f"um valor comum {onde}", "Exterior": f"um valor bem negativo {onde}",
            "Nulo": f"campo em branco {onde}"}.get(caso["rotulo"], "")


def caso_exemplar(d):
    """O caso que melhor mostra o defeito principal (de preferencia o Off-Point)."""
    reprovados = [c for c in d["casos_lista"] if c["status"] == "Reprovado"]
    if not reprovados:
        return None
    principal = next(iter(d["qualidade"]["achados"]))
    candidatos = [c for c in reprovados if c["achado"] == principal]
    return next((c for c in candidatos if c["rotulo"] == "Off-Point"), candidatos[0])


def html_exemplo(d) -> str:
    caso = caso_exemplar(d)
    q, a = d["qualidade"], d["analise"]
    if caso is None:
        bom = next((c for c in d["casos_lista"] if c["rotulo"] == "Off-Point"), d["casos_lista"][0])
        return (f'<div class="ts-exemplo"><div><span class="ts-rot">O teste mais difícil enviou</span>'
                f'<b class="ts-num">{esc(texto_entrada(bom["entradas"]))}</b><small>{esc(_descreve_entrada(bom, d["parametros"]))}</small></div>'
                f'<div><span class="ts-rot">O combinado manda</span><b class="ts-num">{esc(formato_br(bom["esperado"]))}</b>'
                f'<small>{"recusar, porque há valor negativo" if bom["esperado"] == -1 else "o resultado da conta"}</small></div>'
                f'<div class="ts-certo"><span class="ts-rot">O programa respondeu</span><b class="ts-num">{esc(formato_br(bom["obtido"]))}</b>'
                '<small>exatamente o combinado</small></div></div>')
    explica_obtido = {"NEGATIVO_ACEITO": "fez a conta como se o valor fosse válido",
                      "VALIDO_REJEITADO": "recusou um valor que a regra aceita",
                      "NULO": "devolveu vazio", "CALCULO": "fez uma conta diferente da regra",
                      "ERRO": "parou com erro"}[caso["achado"]]
    obtido = "erro" if caso["erro"] else formato_br(caso["obtido"])
    exemplo = (f'<div class="ts-exemplo"><div><span class="ts-rot">O teste enviou</span>'
               f'<b class="ts-num">{esc(texto_entrada(caso["entradas"]))}</b><small>{esc(_descreve_entrada(caso, d["parametros"]))}</small></div>'
               f'<div><span class="ts-rot">O combinado manda</span><b class="ts-num">{esc(formato_br(caso["esperado"]))}</b>'
               f'<small>{"recusar, porque há valor negativo" if caso["esperado"] == -1 else "o resultado da conta"}</small></div>'
               f'<div class="ts-errado"><span class="ts-rot">O programa respondeu</span><b class="ts-num">{esc(obtido)}</b>'
               f'<small>{esc(explica_obtido)}</small></div></div>')
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    total = nos[0] == nos[1] and arestas[0] == arestas[1]
    ids = q["achados"][caso["achado"]]
    porque = (f'<div class="ts-cartao"><h3>Por que só a conferência 1 percebeu</h3>'
              f'<p>O mesmo problema apareceu em {len(ids)} testes ({esc(", ".join(ids))}).</p>'
              + ('<p>As conferências 2, 3 e 4 examinam o código que foi escrito, e nele tudo foi percorrido e vigiado. '
                 'Mas a regra dos negativos nunca foi escrita: não há trecho para percorrer nem defeito para plantar. '
                 'Só quem compara a resposta com o combinado percebe o que falta. É por isso que o laudo usa mais de '
                 'uma forma de teste.</p>' if total and caso["achado"] == "NEGATIVO_ACEITO" else
                 '<p>Cada forma de teste enxerga um tipo de problema; comparar a resposta com o combinado é a que '
                 'mostra se o programa faz o que foi pedido.</p>') + "</div>")
    if caso["achado"] == "NEGATIVO_ACEITO":
        p = d["parametros"]
        conserto = (f"IF {p[0]} &lt; 0 OR {p[1]} &lt; 0 OR {p[2]} &lt; 0 THEN\n    RETURN -1\nEND IF")
        corrige = (f'<div class="ts-cartao"><h3>Como corrigir</h3><p>Antes da conta, incluir a verificação que falta:</p>'
                   f'<pre>{conserto}</pre><p>Cole essas linhas no fonte, na aba Programa, e veja o laudo mudar na hora.</p></div>')
    else:
        corrige = ('<div class="ts-cartao"><h3>Como corrigir</h3><p>Compare o trecho do código responsável por essa '
                   'regra com o combinado; a aba da Sprint 1 lista todos os testes que falharam.</p></div>')
    return exemplo + f'<div class="ts-duas">{porque}{corrige}</div>'


def html_confianca(d) -> str:
    ok, total = d["validacao_resumo"]
    por_exemplo = {}
    for linha in d["validacao_linhas"]:
        chave = f"{linha['exemplo']} ({linha['aula'].split(',')[0].replace('Aula de', 'aula de')})"
        feito, n = por_exemplo.get(chave, (0, 0))
        por_exemplo[chave] = (feito + int(linha["confere"]), n + 1)
    itens = "".join(f"<li>{esc(nome)}<span>{feito} de {n}</span></li>" for nome, (feito, n) in por_exemplo.items())
    classe = "" if ok == total else " ts-placar-ruim"
    return (f'<div class="ts-confianca"><div class="ts-placar{classe}"><b>{ok}/{total}</b><span>conferências iguais '
            f'ao gabarito das aulas</span></div><div class="ts-cartao"><h3>A ferramenta também foi testada</h3>'
            f'<p>Antes de examinar o CAD0001, a própria ferramenta passou por {len(por_exemplo)} exercícios resolvidos em '
            f'aula, cujas respostas já eram conhecidas. Em {ok} de {total} conferências ela chegou ao mesmo resultado '
            'do gabarito.</p><ul class="ts-lista">' + itens + '</ul>'
            '<p style="margin-top:.8rem"><b>Quem decide o que é certo.</b> A resposta esperada de cada teste vem da '
            'regra escrita no manual, e não do próprio código. Assim o programa nunca é comparado com ele mesmo.</p>'
            "</div></div>")


def html_limites() -> str:
    itens = [
        ("Uma função por vez.", "O laudo examina a função de cálculo do CAD0001; telas, banco de dados e a "
                                "comunicação entre módulos ficam fora."),
        ("Interpretação do código.", "A ferramenta lê e executa o 4GL por conta própria (IF, WHILE, LET, RETURN); "
                                     "ela não é o compilador Informix."),
        ("Sugestões são indícios.", "Quando a ferramenta sugere um teste novo ou aponta um caminho impossível, ela "
                                    "se baseia em mil combinações de valores, não em uma prova matemática."),
        ("Textos de IA são opcionais.", "O Gemini só redige textos; todos os números vêm dos cálculos da ferramenta."),
    ]
    return '<div class="ts-cartao"><ul class="ts-marcadores">' + "".join(
        f"<li><b>{esc(t)}</b> {esc(x)}</li>" for t, x in itens) + "</ul></div>"


def html_apoio() -> str:
    principais = [1, 2, 5, 6, 7, 12]
    return "".join(f'<div class="ts-fonte"><span class="ts-fn">{n}</span><div><p>{esc(REF[n]["curto"])}</p>'
                   f'<p class="ts-uso">{esc(REF[n]["uso"])}</p></div></div>' for n in principais)


def html_fontes() -> str:
    partes, grupo_atual = [], None
    for r in REFERENCIAS:
        if r["grupo"] != grupo_atual:
            grupo_atual = r["grupo"]
            partes.append(f'<p class="ts-fontes-grupo">{esc(grupo_atual)}</p>')
        link = (f' <a href="{esc(r["link"])}" target="_blank" rel="noopener">{esc(r["link"].replace("https://", ""))}</a>'
                if r["link"] else "")
        partes.append(f'<div class="ts-fonte"><span class="ts-fn">{r["n"]}</span><div><p>{esc(r["texto"])}{link}</p>'
                      f'<p class="ts-uso">Onde aparece no laudo: {esc(r["uso"])}</p></div></div>')
    return "".join(partes)


def html_glossario() -> str:
    return '<dl class="ts-glossario">' + "".join(
        f"<div><dt>{esc(t)}</dt><dd>{esc(x)}</dd></div>" for t, x in GLOSSARIO) + "</dl>"


def html_matriz(casos, nomes) -> str:
    """Matriz parametro x ponto: mostra de uma vez o que foi coberto e o resultado."""
    colunas = PONTOS + ["Nulo"]
    partes = ["<table class='ts-matriz'><thead><tr><th>Parâmetro</th>"]
    partes += [f"<th>{c}</th>" for c in colunas]
    partes.append("</tr></thead><tbody>")
    for nome in nomes:
        partes.append(f"<tr><th>{esc(nome)}</th>")
        for coluna in colunas:
            caso = next((c for c in casos if c["alvo"] == nome and c["rotulo"] == coluna), None)
            if caso is None:
                partes.append(f"<td>{chip('não testado', 'neutro')}</td>")
                continue
            tipo = {"Aprovado": "ok", "Reprovado": "ruim"}.get(caso["status"], "neutro")
            partes.append(f"<td>{chip(caso['status'], tipo)}<small>{caso['id']}</small></td>")
        partes.append("</tr>")
    partes.append("</tbody></table>")
    return "".join(partes)


def svg_regua(pontos: pd.DataFrame, epsilon: Decimal) -> str:
    """Regua da fronteira: regiao invalida a esquerda do 0,00 e valida a direita.
    Escala logaritmica dos dois lados do zero, para que 0,00 e -0,01 nao
    fiquem um em cima do outro."""
    import math
    largura, esquerda, direita = 960, 46, 46
    c = float(epsilon) / 5
    valores = [float(v) for v in pontos["Valor"]]
    maior = max(abs(v) for v in valores) * 4

    def f(x):
        return math.copysign(math.log10(1 + abs(x) / c), x)

    def X(x):
        return esquerda + (f(x) - f(-maior)) / (f(maior) - f(-maior)) * (largura - esquerda - direita)

    zero = X(0)
    partes = [f'<svg viewBox="0 0 {largura} 176" class="ts-regua" role="img" '
              'aria-label="Régua da fronteira com os quatro pontos testados">',
              f'<rect x="{X(-maior):.1f}" y="78" width="{zero - X(-maior):.1f}" height="28" rx="6" fill="var(--ts-invalido)"/>',
              f'<rect x="{zero:.1f}" y="78" width="{X(maior) - zero:.1f}" height="28" rx="6" fill="var(--ts-valido)"/>',
              f'<line class="ts-zero" x1="{zero:.1f}" x2="{zero:.1f}" y1="66" y2="118" stroke-width="2" stroke-dasharray="4 3"/>']
    marcas, potencia = [0.0], float(epsilon)
    while potencia <= maior:
        marcas += [potencia, -potencia]
        potencia = round(potencia * 10, 6)
    ultimo = -999.0
    for marca in sorted(marcas):
        x = X(marca)
        if x - ultimo < 40:
            continue
        ultimo = x
        partes.append(f'<text class="ts-suave" x="{x:.1f}" y="130" font-size="12" text-anchor="middle">'
                      f'{esc(formato_br(Decimal(str(marca))))}</text>')
    for _, linha in pontos.iterrows():
        x = X(float(linha["Valor"]))
        ancora, dx = {"Off-Point": ("end", -9), "On-Point": ("start", 9)}.get(linha["Ponto"], ("middle", 0))
        partes.append(f'<g><title>{esc(linha["Ponto"])}: {esc(formato_br(linha["Valor"]))}. '
                      f'{esc(linha["Condição da fronteira"])}. Esperado: {esc(linha["Resultado esperado"])}.</title>'
                      f'<text class="ts-tinta" x="{x + dx:.1f}" y="40" font-size="14" font-weight="700" text-anchor="{ancora}">{esc(linha["Ponto"])}</text>'
                      f'<text class="ts-suave" x="{x + dx:.1f}" y="58" font-size="13" text-anchor="{ancora}">{esc(formato_br(linha["Valor"]))}</text>'
                      f'<circle class="ts-ponto" cx="{x:.1f}" cy="92" r="7.5" stroke-width="2.4"/></g>')
    partes.append(f'<text class="ts-suave" x="{esquerda}" y="160" font-size="12.5">Região inválida: valor menor que '
                  f'0,00, a resposta deve ser -1</text>')
    partes.append(f'<text class="ts-suave" x="{largura - direita}" y="160" font-size="12.5" text-anchor="end">'
                  'Região válida: valor de 0,00 para cima, faz a conta</text>')
    partes.append(f'<rect x="{esquerda - 16}" y="151" width="11" height="11" rx="2" fill="var(--ts-invalido)"/>')
    partes.append(f'<rect x="{largura - direita + 5}" y="151" width="11" height="11" rx="2" fill="var(--ts-valido)"/>')
    partes.append("</svg>")
    return "".join(partes)


def _fontes_embutidas() -> str:
    """As fontes tipograficas vao dentro do relatorio, para ele ficar igual mesmo sem internet."""
    regras = []
    for familia, arquivo, peso in (("IBM Plex Sans", "ibm-plex-sans-latin-400-normal.woff2", 400),
                                   ("IBM Plex Sans", "ibm-plex-sans-latin-600-normal.woff2", 600),
                                   ("IBM Plex Sans", "ibm-plex-sans-latin-700-normal.woff2", 700),
                                   ("IBM Plex Mono", "ibm-plex-mono-latin-400-normal.woff2", 400)):
        caminho = PASTA / "static" / arquivo
        if caminho.exists():
            dados = base64.b64encode(caminho.read_bytes()).decode()
            regras.append(f"@font-face {{ font-family: '{familia}'; font-weight: {peso}; font-display: swap; "
                          f"src: url(data:font/woff2;base64,{dados}) format('woff2'); }}")
    return "\n".join(regras)


def gerar_relatorio_html(d) -> str:
    """O laudo completo em uma pagina HTML: primeiro a parte para apresentar,
    depois os anexos tecnicos e as fontes. Abre no navegador (claro ou escuro)
    e imprime em PDF com Ctrl+P."""
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    cob, crit = a["cobertura"], a["criterios"]
    ok, total = d["validacao_resumo"]
    parecer = (f"<h2>Parecer do Gemini ({esc(d['parecer_modelo'])})</h2>"
               f"<pre class='parecer'>{esc(d['parecer'])}</pre>") if d.get("parecer") else ""
    dot = json.dumps(motor.grafo_em_dot(a["grafo"], set(a["nos_cobertos"]), set(a["arestas_cobertas"]))
                     ).replace("</", "<\\/")

    def tabela(df):
        return '<div class="rolagem">' + df.to_html(index=False, border=0, classes="t", escape=True) + "</div>"

    def base(chave):
        return "<p class='nota'>Base teórica: " + "; ".join(
            f"[{n}] {esc(REF[n]['curto'])}{', ' + esc(det) if det else ''}" for n, det in BASES[chave]) + ".</p>"

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Laudo de qualidade — CAD0001</title>
<style>
{_fontes_embutidas()}
{ESTILO_CSS}
.ts-relatorio {{ color-scheme: light dark; }}
html, body {{ margin:0; }}
body.ts-relatorio {{ background: light-dark(#f6f8fb, #0c131b); color: var(--ts-tinta);
  font-family: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif; line-height: 1.5; }}
.pagina {{ max-width: 1120px; margin: 0 auto; padding: 2rem 1.4rem 3rem; }}
h2.anexo {{ font-size: 1.35rem; margin: 2.6rem 0 .3rem; padding-top: 1rem; border-top: 2px solid var(--ts-linha); }}
h3 {{ font-size: 1.05rem; margin: 1.4rem 0 .4rem; }}
p.nota {{ color: var(--ts-suave); font-size: .9rem; margin: .2rem 0 .8rem; }}
.kpis {{ display:flex; flex-wrap:wrap; gap:.7rem; margin:.8rem 0; }}
.kpi {{ border:1px solid var(--ts-linha); background: var(--ts-cartao); border-radius:12px; padding:.6rem .9rem; min-width:140px; }}
.kpi b {{ display:block; font-size:1.45rem; }} .kpi span {{ color: var(--ts-suave); font-size:.85rem; }}
.ts-cartao {{ min-width:0; }} .ts-cartao pre {{ overflow-x:auto; white-space:pre; }}
.rolagem {{ overflow-x:auto; max-width:100%; }} @media print {{ .rolagem {{ overflow:visible; }} }}
table.t {{ border-collapse:collapse; width:100%; font-size:.84rem; margin:.5rem 0 1rem; background: var(--ts-cartao); }}
table.t th, table.t td {{ border-bottom:1px solid var(--ts-linha); padding:.4rem .55rem; text-align:left; vertical-align: top; }}
table.t th {{ background: var(--ts-relevo); font-weight:600; }}
table.t td {{ white-space:nowrap; }} table.t td:last-child {{ white-space:normal; }}
.ts-gfc {{ text-align:center; margin:1rem 0; }} .ts-gfc svg {{ max-width:100%; height:auto; }}
pre.parecer {{ white-space:pre-wrap; font-family:inherit; background: var(--ts-relevo); padding:1rem; border-radius:10px; }}
.rodape {{ margin-top: 2.5rem; color: var(--ts-suave); font-size: .85rem; }}
@media print {{
  .ts-relatorio {{ color-scheme: light; }}
  .pagina {{ max-width:none; padding:0; }}
  h2.anexo {{ break-before: page; }}
  .ts-estacao, .ts-regra, tr, .ts-cartao {{ break-inside: avoid; }}
}}
</style></head><body class="ts-relatorio"><div class="pagina">
{html_topo()}
{html_faixa(d)}
{html_veredito(d)}
{html_secao("O combinado, regra por regra", "O que o manual diz que a função deve fazer, e se ela cumpriu cada regra nos testes.")}
{html_regras(d)}
{html_secao("Como o programa foi testado", "Quatro conferências independentes. Cada uma responde a uma pergunta diferente sobre a qualidade.")}
{html_estacoes(d)}
{html_secao("O defeito, em um exemplo" if caso_exemplar(d) else "Um exemplo de teste", "Um dos testes, do começo ao fim.")}
{html_exemplo(d)}
{html_secao("Por que confiar neste laudo")}
{html_confianca(d)}
{html_secao("O que este laudo não cobre")}
{html_limites()}
{html_secao("Glossário", "Os termos técnicos usados nos anexos, em linguagem simples.")}
{html_glossario()}

<h2 class="anexo">Anexo A. Caixa-preta: classes de equivalência e valor limite</h2>
{base("caixa_preta")}
<div class="kpis"><div class="kpi"><b>{q['total']}</b><span>casos executados</span></div><div class="kpi"><b>{q['aprovados']}</b><span>aprovados</span></div>
<div class="kpi"><b>{q['reprovados']}</b><span>reprovados</span></div><div class="kpi"><b>{q['classes'][0]}/{q['classes'][1]}</b><span>classes cobertas</span></div>
<div class="kpi"><b>{q['pontos'][0]}/{q['pontos'][1]}</b><span>pontos de fronteira cobertos</span></div></div>
<h3>Especificação usada como oráculo</h3><ol>{''.join(f'<li>{esc(r)}</li>' for r in ESPECIFICACAO)}</ol>
<h3>Épsilon e régua da fronteira</h3><p>{esc(d['justificativa'])}</p>{base("epsilon")}
{svg_regua(d['pontos_brutos'], d['epsilon'])}
<h3>Classes de equivalência</h3>{tabela(d['pce'])}
<h3>Casos de teste</h3>{tabela(d['casos'])}

<h2 class="anexo">Anexo B. Caixa-branca: grafo de fluxo de controle e McCabe</h2>
{base("caixa_branca")}
<div class="kpis"><div class="kpi"><b>{m['N']}</b><span>nós (N)</span></div><div class="kpi"><b>{m['E']}</b><span>arestas (E)</span></div>
<div class="kpi"><b>{m['P']}</b><span>predicativos (P)</span></div><div class="kpi"><b>{m['R']}</b><span>regiões (R)</span></div><div class="kpi"><b>{m['V']}</b><span>V(G)</span></div></div>
<ul><li>Método 1, topológico: V(G) = E − N + 2 = {m['E']} − {m['N']} + 2 = <b>{m['v_topologico']}</b></li>
<li>Método 2, lógico: V(G) = P + 1 = {m['P']} + 1 = <b>{m['v_logico']}</b></li>
<li>Método 3, espacial: V(G) = R = {m['regioes_internas']} internas + 1 externa = <b>{m['v_espacial']}</b></li></ul>
<div class="ts-gfc" id="gfc"><p class="nota">O desenho do grafo aparece quando o laudo é aberto com internet. A tabela de nós abaixo descreve o mesmo grafo.</p></div>
{tabela(d['nos'])}
<div class="kpis"><div class="kpi"><b>{porcento(cob['Todos-Nós'])}</b><span>Todos-Nós ({cob['Todos-Nós'][0]} de {cob['Todos-Nós'][1]})</span></div>
<div class="kpi"><b>{porcento(cob['Todas-Arestas'])}</b><span>Todas-Arestas ({cob['Todas-Arestas'][0]} de {cob['Todas-Arestas'][1]})</span></div>
<div class="kpi"><b>{porcento(cob['Todos-Caminhos'])}</b><span>caminhos ({cob['Todos-Caminhos'][0]} de {cob['Todos-Caminhos'][1]})</span></div></div>
<h3>O que cada caso percorre</h3>{tabela(d['execucoes'])}
<h3>Caminhos completos</h3>{tabela(d['caminhos'])}

<h2 class="anexo">Anexo C. Fluxo de dados: pares Def-Uso</h2>
{base("fluxo")}
<div class="kpis">{''.join(f"<div class='kpi'><b>{porcento(par)}</b><span>{esc(nome)} ({par[0]} de {par[1]})</span></div>" for nome, par in crit.items())}</div>
{tabela(d['variaveis'])}
<h3>Pares Def-Uso</h3>{tabela(d['pares'])}

<h2 class="anexo">Anexo D. Teste de mutação</h2>
{base("mutacao")}
<div class="kpis"><div class="kpi"><b>{mut['Mt']}</b><span>gerados (Mt)</span></div><div class="kpi"><b>{mut['Md']}</b><span>mortos (Md)</span></div>
<div class="kpi"><b>{mut['vivos']}</b><span>vivos</span></div><div class="kpi"><b>{mut['Me']}</b><span>equivalentes (Me)</span></div><div class="kpi"><b>{texto_ms(mut)}</b><span>escore (MS)</span></div></div>
<p>MS = Md ÷ (Mt − Me) × 100 = {mut['Md']} ÷ ({mut['Mt']} − {mut['Me']}) × 100 = <b>{texto_ms(mut)}</b></p>
{tabela(d['mutantes'])}

<h2 class="anexo">Anexo E. Validação da ferramenta com os gabaritos das aulas</h2>
{base("validacao")}
<p>{ok} de {total} verificações conferem com os gabaritos dos slides das aulas.</p>
{tabela(d['validacao'])}
{parecer}
<h2 class="anexo">Fontes</h2>
{html_fontes()}
<p class="rodape">Laudo gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")} pelo TestingStudio. Método: a ferramenta interpreta
em Python a lógica da função 4GL carregada (IF, WHILE, LET, RETURN, comparações e aritmética); não é o compilador Informix.</p>
</div>
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
    referencias = "\n".join(f"- [{r['n']}] {r['texto']}" for r in REFERENCIAS)
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
st.set_page_config(page_title="TestingStudio, laudo de qualidade", layout="wide",
                   initial_sidebar_state="collapsed")
st.html(f"<style>{ESTILO_CSS}</style>")
st.html(html_topo())

# ---- Barra lateral: chave do Gemini (so para os textos opcionais) ----------
chave_servidor = chave_do_servidor()
with st.sidebar:
    st.header("Textos com IA")
    st.caption("O Gemini só redige textos a partir dos resultados. O laudo funciona sem ele.")
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
        st.caption("Sem chave, só os textos do Gemini ficam desligados.")
    elif not situacao or situacao["chave"] != marca_da(api_key):
        st.info("Chave ainda não testada.", icon=":material/help:")
    elif situacao["ok"]:
        st.success(situacao["mensagem"], icon=":material/check_circle:")
    else:
        st.error(situacao["mensagem"], icon=":material/error:")
    st.divider()
    st.caption("Modo claro ou escuro: menu de três pontos, no canto superior direito: System, Light ou Dark.")

chave_ok = bool(api_key and situacao and situacao["chave"] == marca_da(api_key) and situacao["ok"])

# ---- Leitura do programa -----------------------------------------------------
enviado = st.file_uploader("Programa em 4GL (arquivo .txt)", type=["txt"])
if enviado is not None:
    ident = (enviado.name, enviado.size, getattr(enviado, "file_id", None))
    if st.session_state.get("fonte_ident") != ident:
        registrar_fonte(enviado.name, enviado.getvalue(), "upload", ident)
elif st.session_state.get("fonte_origem") == "upload":
    esquecer_fonte()                 # o arquivo foi removido do campo acima

if "fonte_original" not in st.session_state:
    st.html(html_boas_vindas())
    exemplo = PASTA / ARQUIVO_EXEMPLO
    if exemplo.exists():
        if st.button(f"Usar o arquivo de exemplo ({ARQUIVO_EXEMPLO})", icon=":material/description:"):
            registrar_fonte(ARQUIVO_EXEMPLO, exemplo.read_bytes(), "exemplo", ("exemplo",))
            st.rerun()
    st.stop()

original = st.session_state["fonte_original"]
identificacao = {"arquivo": st.session_state["fonte_nome"], "linhas": len(original.splitlines()),
                 "quando": st.session_state["fonte_quando"], "sha": st.session_state["fonte_sha"]}
st.html(html_faixa(identificacao))

aba_laudo, aba_programa, aba_s1, aba_s2, aba_s3, aba_s4, aba_apresentar, aba_fontes = st.tabs(
    ["Laudo de qualidade", "Programa", "Sprint 1: caixa-preta", "Sprint 2: caixa-branca",
     "Sprint 3: dados e mutação", "Sprint 4: validação", "Apresentar", "Fontes"])

# ======================= PROGRAMA ===========================================
with aba_programa:
    st.html(html_explica("O programa analisado",
                         "Este é o código que a ferramenta lê e executa. Você pode editar o texto aqui mesmo para "
                         "testar uma correção: todas as abas são recalculadas na hora, sem mexer no arquivo original."))
    fonte = st.text_area("Código-fonte do CAD0001", key="fonte_editado", height=320)
    alterado = fonte != original
    col_a, col_b, _ = st.columns([1.4, 1.4, 4])
    if alterado:
        col_a.button("Restaurar o original", width="stretch", icon=":material/undo:",
                     on_click=lambda: st.session_state.update(fonte_editado=st.session_state["fonte_original"]))
    if st.session_state["fonte_origem"] == "exemplo":
        col_b.button("Remover o arquivo", width="stretch", icon=":material/close:", on_click=esquecer_fonte)
    if alterado:
        st.warning("O fonte foi alterado nesta página. Os testes rodam sobre a versão editada, "
                   "não sobre o arquivo original.", icon=":material/edit:")

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

texto_funcao = f"FUNCTION {FUNCAO_ALVO}({', '.join(parametros)}){corpo}END FUNCTION"
justificativa = (
    f"Os parâmetros são DECIMAL({precisao},{escala}), com {escala} casas decimais. A menor variação "
    f"representável é ε = 10^-{escala} = {formato_br(epsilon)} (1 centavo). Por isso o Off-Point da "
    f"fronteira 0,00 é 0,00 − ε = {formato_br(FRONTEIRA - epsilon)}: é o valor inválido mais próximo "
    "possível do limite, o único capaz de distinguir um '<' de um '<=' no código."
)
passo = float(epsilon)

with aba_programa:
    st.subheader("Unidade sob teste")
    st.code("\n".join(f"{numero:>4}  {linha}" for numero, linha in
                      enumerate(texto_funcao.split("\n"), start=linha_funcao)), language=None)
    st.caption("O número à esquerda é a linha no arquivo; é o mesmo usado nos nós do grafo.")
    c1, c2, c3 = st.columns(3)
    c1.metric("Tipo dos parâmetros", f"DECIMAL({precisao},{escala})", border=True)
    c2.metric("Épsilon (ε)", formato_br(epsilon), border=True,
              help="Menor variação que o tipo representa: 10 elevado a menos a escala.")
    c3.metric("Maior valor do tipo", formato_br(maximo), border=True)
    st.write(justificativa)
    st.html(html_base("epsilon"))
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

# ======================= SPRINT 1: CAIXA-PRETA ==============================
with aba_s1:
    st.html(html_explica(
        "Em palavras simples",
        "A caixa-preta testa o programa pelo que ele promete, sem olhar o código. Os valores possíveis são "
        "divididos em grupos que o programa deve tratar igual (classes de equivalência) e o teste se concentra "
        "nas fronteiras entre os grupos (valor limite), onde os erros mais aparecem.", "caixa_preta"))
    aba_resumo, aba_rel, aba_graf, aba_extra = st.tabs(
        ["Resumo", "Classes e casos de teste", "Régua da fronteira", "Testes extras"])

# A aba de testes extras e montada primeiro porque todos os indicadores usam as linhas digitadas nela.
with aba_extra:
    st.write("Monte seus próprios casos: troque os valores, apague ou acrescente linhas. "
             "Deixe uma célula vazia para enviar NULL. Todas as abas são recalculadas na hora.")
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

with aba_rel:
    st.subheader("Especificação usada como oráculo")
    st.markdown("\n".join(f"{i}. {regra}" for i, regra in enumerate(ESPECIFICACAO, 1)))
    st.subheader("Particionamento em classes de equivalência (PCE)")
    st.dataframe(df_pce, hide_index=True, width="stretch")
    st.subheader("Análise do valor limite (AVL) e demais casos")
    st.dataframe(df_casos, hide_index=True, width="stretch")
    st.caption("Esperado: calculado pela especificação. Obtido: resultado da execução da função carregada.")

with aba_graf:
    st.subheader("Os quatro pontos testados em torno da fronteira 0,00")
    st.markdown(svg_regua(df_pontos, epsilon), unsafe_allow_html=True)
    st.caption("A escala é logarítmica dos dois lados do zero, para que 0,00 e −0,01 não fiquem um sobre o outro. "
               "Passe o mouse sobre um ponto para ver a condição e o resultado esperado.")
    st.dataframe(df_pontos_tela, hide_index=True, width="stretch")

# ======================= SPRINT 2: CAIXA-BRANCA =============================
with aba_s2:
    st.html(html_explica(
        "Em palavras simples",
        "A caixa-branca testa olhando por dentro. O código vira um mapa: cada trecho é um nó (círculo) e cada "
        "passagem é uma aresta (seta). Os mesmos testes da Sprint 1 são executados e a ferramenta mede por quais "
        "trechos e desvios cada um passou.", "caixa_branca"))
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

with aba_s2:
    painel_caixa_branca(analise, "cad")

# ======================= SPRINT 3: FLUXO DE DADOS E MUTACAO =================
with aba_s3:
    aba_fluxo, aba_mutacao = st.tabs(["Fluxo de dados (pares Def-Uso)", "Teste de mutação"])
    with aba_fluxo:
        st.html(html_explica(
            "Em palavras simples",
            "O teste de fluxo de dados acompanha cada variável: onde ela recebe um valor e onde esse valor é "
            "usado, em contas (c-uso) ou em decisões (p-uso). Os números de nó e de aresta são os do grafo da "
            "Sprint 2.", "fluxo"))
        painel_fluxo(analise, "cad")
    with aba_mutacao:
        st.html(html_explica(
            "Em palavras simples",
            "O teste de mutação avalia os testes, não o código. Cada mutante é uma cópia da função com um "
            "pequeno defeito plantado de propósito; uma boa suíte percebe a diferença e mata o mutante.",
            "mutacao"))
        mutacao = painel_mutacao(analise, "cad")

# ======================= DADOS CONSOLIDADOS =================================
linhas_validacao = validacao_em_cache()
validacao_resumo = (sum(1 for l in linhas_validacao if l["confere"]), len(linhas_validacao))
achado = achado_central(qualidade, analise, mutacao)
pacote = {
    "qualidade": qualidade, "casos": df_casos, "casos_lista": casos, "pce": df_pce, "pontos": df_pontos_tela,
    "pontos_brutos": df_pontos, "origem": df_origem, "justificativa": justificativa,
    "analise": analise, "mutacao": mutacao, "achado": achado, "parametros": parametros,
    "nos": tabela_nos(analise), "execucoes": tabela_execucoes(analise), "caminhos": tabela_caminhos(analise),
    "variaveis": tabela_variaveis(analise), "pares": tabela_pares(analise), "mutantes": tabela_mutantes(analise),
    "validacao": tabela_validacao(linhas_validacao), "validacao_resumo": validacao_resumo,
    "validacao_linhas": linhas_validacao, "epsilon": epsilon, **identificacao,
}
assinatura = hashlib.sha256((texto_funcao + df_casos.to_csv() + str(por_bloco) + str(mutacao)).encode()).hexdigest()
parecer = st.session_state.get("parecer")
if parecer:
    pacote.update(parecer=parecer["texto"], parecer_modelo=parecer["modelo"])
relatorio_html = gerar_relatorio_html(pacote)
roteiro = roteiro_do_pitch(pacote)


def botoes_de_download(chave: str) -> None:
    b1, b2, _ = st.columns([1.7, 1.5, 3])
    b1.download_button("Baixar o laudo completo (HTML)", relatorio_html, key=f"laudo_{chave}",
                       file_name="laudo_cad0001.html", mime="text/html", width="stretch",
                       icon=":material/download:", type="primary",
                       help="Abre em qualquer navegador, no modo claro ou escuro. Para PDF, use Ctrl+P.")
    b2.download_button("Baixar casos de teste (CSV)", df_casos.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       key=f"csv_{chave}", file_name="casos_de_teste_cad0001.csv", mime="text/csv",
                       width="stretch", icon=":material/table:")


# ======================= SPRINT 4: VALIDACAO ================================
with aba_s4:
    st.html(html_explica(
        "Em palavras simples",
        "Antes de confiar na ferramenta, ela mesma é testada. Cada exercício resolvido em aula, com resposta "
        "conhecida, passa pelo mesmo motor, e o resultado é comparado com o gabarito do slide.", "validacao"))
    aba_validacao, aba_laboratorio = st.tabs(["Validação com gabaritos das aulas", "Laboratório de exercícios"])
    with aba_validacao:
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

# ======================= APRESENTAR =========================================
with aba_apresentar:
    st.html(html_explica(
        "Para apresentar",
        "Comece pela aba Laudo de qualidade: ela foi escrita para quem não é da área. O roteiro abaixo "
        "organiza a fala em cerca de cinco minutos, com os números desta análise."))
    botoes_de_download("apresentar")
    aba_roteiro, aba_ia = st.tabs(["Roteiro da apresentação", "Textos com IA (Gemini)"])
    with aba_roteiro:
        st.markdown(roteiro)
        st.download_button("Baixar o roteiro (Markdown)", roteiro, key="baixar_roteiro",
                           file_name="roteiro_apresentacao.md", mime="text/markdown", icon=":material/notes:")
    with aba_ia:
        st.write("Todos os números são calculados pela ferramenta. Aqui o Gemini só redige um texto a partir deles.")
        pedido = st.radio("O que o Gemini deve escrever", ["Parecer de auditoria", "Fala para a apresentação"],
                          horizontal=True, key="pedido_gemini")
        guarda = "parecer" if pedido == "Parecer de auditoria" else "fala"
        if not api_key:
            st.info("Abra a barra lateral (seta no canto superior esquerdo) e cole a chave da API.",
                    icon=":material/key:")
        elif not chave_ok:
            st.info("Use o botão Testar chave, na barra lateral, para confirmar que a chave funciona.",
                    icon=":material/key:")
        usos = st.session_state.get("usos_gemini", 0)
        no_limite = bool(chave_servidor) and usos >= LIMITE_DE_PARECERES
        if no_limite:
            st.info(f"Limite de {LIMITE_DE_PARECERES} textos por visita atingido. "
                    "Recarregue a página para continuar.", icon=":material/hourglass:")
        if st.button("Escrever o parecer com Gemini" if guarda == "parecer" else "Escrever a fala com Gemini",
                     type="primary", disabled=not api_key or no_limite, icon=":material/edit_note:"):
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
                           "Gere de novo para atualizar.", icon=":material/history:")
            st.caption(f"Texto gerado pelo modelo {escrito['modelo']}.")
            st.markdown(escrito["texto"])

# ======================= FONTES =============================================
with aba_fontes:
    st.html(html_explica(
        "De onde vem cada coisa",
        "Cada técnica do laudo segue uma fonte publicada ou o material da disciplina. O número de cada fonte "
        "é o mesmo que aparece nas faixas de base teórica das outras abas."))
    st.html(html_fontes())
    st.subheader("Origem dos dados desta análise")
    st.dataframe(df_origem, hide_index=True, width="stretch")
    st.subheader("Como os resultados são obtidos")
    st.markdown(
        "- **Esperado (caixa-preta):** vem das quatro regras da especificação, sem olhar o código.\n"
        "- **Obtido:** a ferramenta interpreta em Python a lógica da função carregada "
        "(IF, WHILE, LET, RETURN, comparações e aritmética) e a executa com as entradas de cada caso. "
        "Não é o compilador Informix.\n"
        "- **Grafo e McCabe:** o grafo é montado a partir dos comandos da função; N, E e P são contados "
        "nele e V(G) é calculado pelos três métodos.\n"
        "- **Cobertura:** cada execução registra os comandos por onde passou; daí saem os nós, as arestas, "
        "os caminhos e os pares Def-Uso exercitados.\n"
        "- **Mutação:** cada mutante é executado com a mesma suíte e comparado com o programa original.\n"
        f"- **Sugestões e itens possivelmente infactíveis:** vêm de {analise['sondagens']} entradas de sondagem "
        "(combinações de valores típicos). São indícios para o analista, não provas.\n"
        "- **Textos do Gemini:** gerados por IA a partir dessas tabelas; os números vêm sempre da ferramenta."
    )

# ======================= LAUDO (primeira aba, montada por ultimo) ===========
with aba_laudo:
    st.html(html_veredito(pacote))
    botoes_de_download("laudo")
    st.html(html_secao("O combinado, regra por regra",
                       "O que o manual diz que a função deve fazer, e se ela cumpriu cada regra nos testes."))
    st.html(html_regras(pacote))
    st.html(html_secao("Como o programa foi testado",
                       "Quatro conferências independentes. Cada uma responde a uma pergunta diferente sobre a "
                       "qualidade, e as abas das sprints mostram as provas de cada uma."))
    st.html(html_estacoes(pacote))
    st.html(html_secao("O defeito, em um exemplo" if caso_exemplar(pacote) else "Um exemplo de teste",
                       "Um dos testes, do começo ao fim."))
    st.html(html_exemplo(pacote))
    st.html(html_secao("Por que confiar neste laudo"))
    st.html(html_confianca(pacote))
    st.html(html_secao("O que este laudo não cobre"))
    st.html(html_limites())
    st.html(html_secao("Em que este laudo se apoia",
                       "As seis fontes principais. A lista completa, com os dados de publicação e os links, "
                       "está na aba Fontes."))
    st.html(html_apoio())
    with st.expander("Glossário: os termos técnicos em linguagem simples", icon=":material/menu_book:"):
        st.html(html_glossario())
