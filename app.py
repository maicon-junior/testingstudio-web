"""
TestingStudio - Laudo de qualidade de testes para programas Logix/4GL
Teste de Software I, Univille, Prof. Frank Piffer

  Laudo de qualidade : visao para apresentar, em linguagem simples.
  Sprint 1           : caixa-preta, classes de equivalencia (PCE) e valor limite (AVL) com Epsilon.
  Sprint 2           : caixa-branca, grafo de fluxo de controle, nos, arestas e V(G) de McCabe.
  Sprint 3           : fluxo de dados (pares Def-Uso) e teste de mutacao (escore MS).
  Sprint 4           : validacao da propria suite (oraculo, rastreabilidade, assercoes) e pitch.

Este arquivo cuida da PAGINA (leitura do .txt, laudo, tabelas, Gemini).
A caixa-preta (especificacao, oraculo, classes, fronteiras) fica em nucleo/caixa_preta.py.
O interpretador de 4GL e os calculos das Sprints 2 a 4 ficam em nucleo/motor.py.
O PDF do laudo e montado por nucleo/relatorio_pdf.py.
O CAD0001 vem junto so como exemplo: qualquer arquivo 4GL pode ser analisado.
Cores, fontes e modo claro/escuro ficam em .streamlit/config.toml e na pasta static/.

Abrir no computador:  dois cliques em Abrir_TestingStudio.bat   (ou: python iniciar.py)
Publicar online:      veja o LEIA-ME.txt. A chave do Gemini fica no servidor, em "Secrets".
"""

import base64
import hashlib
import html
import json
import os
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import pandas as pd
import streamlit as st

import importlib

from nucleo import motor

# O Streamlit Cloud guarda os modulos importados na memoria. Quando o app.py e
# atualizado e o motor.py nao (ou o servidor nao o recarrega), as versoes ficam
# misturadas. Por isso o app confere a versao e, se preciso, recarrega o motor.
VERSAO_DO_MOTOR = 3
if getattr(motor, "VERSAO", 0) < VERSAO_DO_MOTOR:
    motor = importlib.reload(motor)
try:
    from nucleo import caixa_preta as cp
    if getattr(cp, "VERSAO", 0) < VERSAO_DO_MOTOR:
        cp = importlib.reload(cp)
    ARQUIVOS_DESATUALIZADOS = [nome for nome, modulo in (("nucleo/motor.py", motor), ("nucleo/caixa_preta.py", cp))
                               if getattr(modulo, "VERSAO", 0) < VERSAO_DO_MOTOR]
except ImportError:
    cp = None
    ARQUIVOS_DESATUALIZADOS = ["nucleo/caixa_preta.py"]

PASTA = Path(__file__).resolve().parent
ARQUIVO_EXEMPLO = "cad0001_item_calculo.txt"
PASTA_EXEMPLOS = PASTA / "exemplos"
# Preenchidos depois que o arquivo e lido e a funcao escolhida (valem para a execucao atual).
FUNCAO_ALVO = ""                 # unidade sob teste
SPEC = {}                        # especificacao (oraculo) escrita na pagina
REGRAS = []                      # as regras do combinado, geradas a partir de SPEC
ACHADOS, ACHADOS_SIMPLES = {}, {}
formato_br = cp.formato_br if cp else str

# O primeiro e o modelo do manual; os outros entram se ele nao estiver liberado.
MODELOS = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]

# --------------------------------------------------------------------------
# Fontes. Dados conferidos em: Repositorio da USP (livro e capitulo de teste
# estrutural), dblp e IEEE (artigos).
# --------------------------------------------------------------------------
REFERENCIAS = [
    {"n": 1, "grupo": "Livro-base da disciplina", "curto": "Delamaro, Maldonado e Jino (2007)",
     "texto": "DELAMARO, M. E.; MALDONADO, J. C.; JINO, M. (org.). Introdução ao teste de software. "
              "Rio de Janeiro: Elsevier, 2007. 408 p. ISBN 978-85-352-2634-8.",
     "uso": "Fundamentos e vocabulário de todo o laudo: teste funcional (cap. 2), oráculo, teste de mutação "
            "e teste de unidade com asserções e driver (cap. 1 e 4).",
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
     "uso": "Pontos On e Off da análise de fronteira (o próprio limite e o limite ± ε).",
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
     "uso": "Verificação e validação, rastreabilidade de requisitos, oráculo de teste e terminologia geral.",
     "link": ""},
    {"n": 11, "grupo": "Objeto de teste", "curto": "IBM Informix 4GL",
     "texto": "IBM. IBM Informix 4GL Reference Manual. Tipo de dado DECIMAL(p,s).",
     "uso": "Precisão e escala do tipo DECIMAL(12,2), de onde sai o Épsilon (ε = 0,01).",
     "link": ""},
    {"n": 12, "grupo": "Material da disciplina", "curto": "Manual do laboratório (2026)",
     "texto": "PIFFER, F. Manual de laboratório, Sprint 1: TestingStudio Web, auditoria de caixa-preta "
              "(PCE e AVL) do CAD0001. Teste de Software I (ementa 62371). Joinville: Univille, 2026.",
     "uso": "Modelo de especificação usado como oráculo (o CAD0001 de exemplo) e a tabela dos pontos de fronteira.",
     "link": ""},
    {"n": 13, "grupo": "Requisitos e rastreabilidade", "curto": "Molinari (2008)",
     "texto": "MOLINARI, L. Testes funcionais de software. Florianópolis: Visual Books, 2008. 214 p. "
              "ISBN 978-85-7502-234-4.",
     "uso": "Derivação de casos de teste a partir de requisitos, fluxos principal, alternativo e de exceção, "
            "e matriz de rastreabilidade (Sprint 4).",
     "link": ""},
]
REF = {r["n"]: r for r in REFERENCIAS}

# Em que cada parte do laudo se apoia: (numero da referencia, detalhe).
BASES = {
    "caixa_preta": [(1, "cap. 2"), (3, ""), (4, ""), (8, "seções 4.2.1 e 4.2.2"), (12, "")],
    "epsilon": [(11, ""), (12, "Tabela 1")],
    "caixa_branca": [(2, "cap. 4"), (5, ""), (8, "seções 4.3.1 e 4.3.2")],
    "fluxo": [(2, "cap. 4"), (6, "")],
    "mutacao": [(1, "teste de mutação"), (7, "")],
    "validacao": [(1, "cap. 2 e 4"), (13, ""), (10, "cap. 1 e 4"), (12, "")],
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
    ("Teste de unidade", "Testar uma peça do programa sozinha, aqui a função de cálculo, antes de juntá-la ao resto."),
    ("Asserção", "Uma afirmação que o teste confere: \"com estes valores, a resposta tem de ser esta\". Se não for, o teste falha."),
    ("Driver", "O programa que chama a peça em teste com os dados de cada caso e recolhe a resposta. Aqui, a própria ferramenta."),
    ("Rastreabilidade", "Poder apontar, para cada regra do combinado, quais testes a verificam, e para cada teste, qual regra ele verifica."),
    ("Requisito (REQ)", "Uma regra do que o programa deve fazer, escrita a partir da especificação. Cada uma recebe um número: REQ01, REQ02..."),
    ("Matriz de rastreabilidade (RTM)", "Tabela que cruza requisitos e casos de teste. Prova que tudo o que foi pedido foi testado e que tudo o que foi testado foi pedido."),
    ("Fluxo principal, alternativo e de exceção", "O caminho feliz; os desvios aceitáveis, como um valor no limite; e os bloqueios, quando o programa deve recusar."),
]


# ==========================================================================
# PASSO 1 - Leitura do arquivo .txt
# ==========================================================================
BRASILIA = timezone(timedelta(hours=-3), "horário de Brasília")   # sem horário de verão desde 2019


def _fuso():
    """Fuso de quem esta vendo a pagina (informado pelo navegador). O servidor publicado
    roda em UTC, por isso nao se usa o relogio dele. Se nao der, usa o horario de Brasilia."""
    try:
        from zoneinfo import ZoneInfo
        nome = st.context.timezone
        if nome:
            return ZoneInfo(nome)
    except Exception:
        pass
    return BRASILIA


def agora() -> datetime:
    return datetime.now(_fuso())


def fuso_horario() -> str:
    fuso = _fuso()
    return "horário de Brasília" if fuso is BRASILIA else str(getattr(fuso, "key", fuso)).replace("_", " ")


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
        "fonte_quando": agora().strftime("%d/%m/%Y %H:%M:%S"),
    })
    esquecer_pareceres()


def esquecer_pareceres() -> None:
    for chave in [c for c in st.session_state if c.startswith(("parecer::", "prof::"))]:
        del st.session_state[chave]


VEREDITOS = ["Sem conclusão", "Aprovado", "Aprovado com ressalvas", "Reprovado"]
TIPO_DO_VEREDITO = {"Aprovado": "ok", "Aprovado com ressalvas": "alerta", "Reprovado": "ruim", "Sem conclusão": "neutro"}


def pareceres_profissionais() -> dict:
    """Pareceres escritos pelo profissional tecnico, por etapa ('s1'...'s4') e 'geral'."""
    nome = str(st.session_state.get("prof_nome", "")).strip()
    funcao = str(st.session_state.get("prof_funcao", "")).strip()
    saida = {}
    for chave in ["s1", "s2", "s3", "s4", "geral"]:
        texto = str(st.session_state.get(f"prof::{chave}::texto", "")).strip()
        if texto:
            saida[chave] = {"texto": texto, "veredito": st.session_state.get(f"prof::{chave}::veredito", VEREDITOS[0]),
                            "nome": nome, "funcao": funcao,
                            "quando": st.session_state.get(f"prof::{chave}::quando", "")}
    return saida


def esquecer_fonte() -> None:
    for chave in [c for c in st.session_state if c.startswith("fonte_")]:
        del st.session_state[chave]
    esquecer_pareceres()


# ==========================================================================
# PASSO 2 - Oraculo, classes de equivalencia e casos de teste
# ==========================================================================
def gerar_casos_extras(tabela: pd.DataFrame, programa, spec, formula, epsilon, maximo):
    """Converte as linhas digitadas na aba 'Testes extras' em casos de teste."""
    casos = []
    for _, linha in tabela.iterrows():
        entradas = []
        for i, p in enumerate(spec["params"]):
            bruto = linha.get(f"p{i + 1}")
            if bruto is None or pd.isna(bruto):
                entradas.append(None)
            else:
                entradas.append(Decimal(str(bruto)).quantize(p["tipo"]["epsilon"], ROUND_HALF_UP))
        descricao = "" if pd.isna(linha["descricao"]) else str(linha["descricao"]).strip()
        if all(v is None for v in entradas) and not descricao:
            continue                               # linha em branco
        casos.append(cp.montar_caso(f"EX{len(casos) + 1:02d}", "Extra", "—", "Extra", entradas,
                                    programa, spec, formula, epsilon, maximo, descricao))
    return casos


def medir_qualidade(casos, spec):
    """Indicadores de qualidade do conjunto de testes (criterios de adequacao)."""
    classes_cobertas, pontos_cobertos = set(), set()
    for caso in casos:
        for p, valor in zip(spec["params"], caso["entradas"]):
            classes_cobertas.add((p["nome"], cp.classe_de(p, valor)))
            ponto = cp.ponto_de(p, valor)
            if ponto:
                pontos_cobertos.add((p["nome"], ponto))
    achados = {}
    for caso in casos:
        if caso["achado"]:
            achados.setdefault(caso["achado"], []).append(caso["id"])
    return {
        "total": len(casos),
        "aprovados": sum(c["status"] == "Aprovado" for c in casos),
        "reprovados": sum(c["status"] == "Reprovado" for c in casos),
        "sem_oraculo": sum(c["status"] == "Sem oráculo" for c in casos),
        "classes": (len(classes_cobertas), sum(len(cp.classes_do_parametro(p)) for p in spec["params"])),
        "pontos": (len(pontos_cobertos), sum(len(cp.pontos_do_parametro(p)) for p in spec["params"])),
        "classes_cobertas": classes_cobertas,
        "achados": achados,
    }


# ==========================================================================
# PASSO 3 - Apresentacao: formatos e tabelas
# ==========================================================================
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


def esperado_da_classe(spec, classe: str) -> str:
    r = spec["retorno_invalido"]
    erro = f"Erro: retorna {formato_br(r)}" if r is not None else "Não definido na especificação"
    if classe == "Válida":
        return f"Cálculo: {cp.formula_bonita(spec['formula'])}" if spec["formula"].strip() else \
            "Não definido na especificação"
    if classe.startswith("Nula"):
        return {"zero": "Tratado como 0", "invalido": erro}.get(spec["nulo"], "Não definido na especificação")
    return erro


def tabela_pce(casos, spec) -> pd.DataFrame:
    """Classes de equivalencia de cada parametro e os casos que cobrem cada uma."""
    linhas = []
    for i, p in enumerate(spec["params"]):
        for classe, dominio in cp.classes_do_parametro(p):
            cobrem = [c["id"] for c in casos
                      if cp.classe_de(p, c["entradas"][i]) == classe and c["alvo"] in (p["nome"], "—")]
            linhas.append({"Parâmetro": p["nome"], "Classe": classe, "Domínio": dominio,
                           "Resultado esperado": esperado_da_classe(spec, classe),
                           "Casos que cobrem": ", ".join(cobrem) if cobrem else "nenhum"})
    return pd.DataFrame(linhas)


def esperado_do_ponto(spec, ponto) -> str:
    if ponto["valido"]:
        return "Sucesso (cálculo)" if spec["formula"].strip() else "Não definido"
    r = spec["retorno_invalido"]
    return f"Erro ({formato_br(r)})" if r is not None else "Não definido"


def grupos_de_fronteira(spec):
    """Parametros com a mesma faixa e os mesmos pontos sao mostrados juntos."""
    grupos = {}
    for p in spec["params"]:
        chave = tuple((x["rotulo"], x["valor"]) for x in cp.pontos_do_parametro(p))
        grupos.setdefault(chave, []).append(p)
    return list(grupos.values())


def tabela_pontos(spec) -> pd.DataFrame:
    """Os pontos da AVL de cada parametro (ou grupo de parametros com a mesma faixa)."""
    linhas = []
    for grupo in grupos_de_fronteira(spec):
        for ponto in cp.pontos_do_parametro(grupo[0]):
            linhas.append({"Parâmetros": ", ".join(p["nome"] for p in grupo), "Ponto": ponto["rotulo"],
                           "Valor": formato_br(ponto["valor"]), "Condição": ponto["condicao"],
                           "Resultado esperado": esperado_do_ponto(spec, ponto)})
    return pd.DataFrame(linhas)


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

.ts-parecer-prof p { margin: .45rem 0 0; color: var(--ts-tinta); line-height:1.55; }
.ts-parecer-topo { display:flex; align-items:center; justify-content:space-between; gap:.6rem; flex-wrap:wrap; }
.ts-assina { margin-top: .8rem !important; padding-top:.55rem; border-top: 1px dashed var(--ts-linha);
  color: var(--ts-suave) !important; font-size:.85rem; }
.ts-pareceres { display:grid; gap: .9rem; }
.ts-regra small.ts-req { font-size:.72rem; letter-spacing:.04em; color: var(--ts-destaque); font-weight:600; margin:0 0 .1rem; }

/* ---- componentes do Streamlit seguem a cor de destaque escolhida ---- */
.stApp { --ts-sobre-destaque: light-dark(#ffffff, #0c131b); }
[data-testid="stBaseButton-primary"] { background-color: var(--ts-destaque) !important; border-color: var(--ts-destaque) !important;
  color: var(--ts-sobre-destaque) !important; }
[data-testid="stBaseButton-primary"]:hover { filter: brightness(1.08); }
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] button:hover {
  border-color: var(--ts-destaque) !important; color: var(--ts-destaque) !important; }
[data-testid="stTab"][aria-selected="true"] p { color: var(--ts-destaque) !important; }
[data-testid="stTab"] .react-aria-SelectionIndicator { background-color: var(--ts-destaque) !important; }
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-checked="true"] * {
  color: var(--ts-destaque) !important; border-color: var(--ts-destaque) !important; }
[data-testid="stMultiSelect"] [data-baseweb="tag"], [data-testid="stMultiSelectTagsContainer"] span[data-baseweb="tag"] {
  background-color: var(--ts-destaque) !important; color: var(--ts-sobre-destaque) !important; }
[data-testid="stMultiSelect"] [data-baseweb="tag"] * { color: var(--ts-sobre-destaque) !important; }

/* ---- impressao da pagina (Imprimir do navegador): centralizada, sem menus ---- */
@media print {
  @page { size: A4; margin: 12mm; }
  [data-testid="stSidebar"], [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stFileUploader"],
  [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"],
  [data-testid="stDecoration"], [data-testid="stSidebarCollapsedControl"], iframe { display: none !important; }
  html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stMainBlockContainer"],
  section.main { position: static !important; overflow: visible !important; height: auto !important; margin: 0 !important;
    left: 0 !important; width: auto !important; min-width: 0 !important; max-width: 100% !important;
    background: #ffffff !important; color-scheme: light !important; }
  [data-testid="stTabs"] [role="tablist"] { flex-wrap: wrap !important; overflow: visible !important; }
  .block-container { max-width: 100% !important; width: 100% !important; padding: 0 !important; margin: 0 auto !important; }
  .ts-estacoes, .ts-operadores { grid-template-columns: repeat(2, minmax(0,1fr)) !important; }
  .ts-veredito, .ts-confianca { grid-template-columns: 1fr !important; }
  .ts-estacao, .ts-regra, .ts-cartao, .ts-operador, .ts-fluxo, .ts-suite { break-inside: avoid; }
}

/* ---- abas: as principais cabem numa linha so ---- */
[data-testid="stTabs"] [role="tablist"] { gap: .9rem !important; }
[data-testid="stTab"] p { font-size: .86rem !important; }

/* ---- tabelas da pagina ---- */
.ts-tab-caixa { overflow:auto; border:1px solid var(--ts-linha); border-radius:12px; background: var(--ts-cartao);
  margin: .35rem 0 1rem; }
.ts-tab-caixa.ts-tab-alta { max-height: 560px; }
table.ts-tab { border-collapse: separate; border-spacing: 0; width: 100%; font-size: .86rem; color: var(--ts-tinta); }
.ts-tab-larga table.ts-tab { font-size: .79rem; }
.ts-tab-larga table.ts-tab td, .ts-tab-larga table.ts-tab thead th { padding-left: .5rem; padding-right: .5rem; }
table.ts-tab thead th { position: sticky; top: 0; z-index: 1; background: var(--ts-relevo); color: var(--ts-suave);
  font-weight: 600; text-align: left; padding: .55rem .7rem; border-bottom: 1px solid var(--ts-linha);
  white-space: nowrap; font-size: .78rem; letter-spacing: .02em; }
table.ts-tab td { padding: .5rem .7rem; border-bottom: 1px solid var(--ts-linha); vertical-align: top; line-height: 1.45;
  overflow-wrap: break-word; word-break: normal; hyphens: none; }
table.ts-tab td:first-child { white-space: nowrap; font-weight: 600; }
table.ts-tab td.ts-st-ok, table.ts-tab td.ts-st-ruim, table.ts-tab td.ts-st-alerta { white-space: nowrap; }
table.ts-tab tbody tr:nth-child(even) td { background: color-mix(in srgb, var(--ts-relevo) 55%, transparent); }
table.ts-tab tbody tr:hover td { background: var(--ts-destaque-suave); }
table.ts-tab tbody tr:last-child td { border-bottom: 0; }
table.ts-tab th.ts-num, table.ts-tab td.ts-num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.ts-tab th.ts-centro, table.ts-tab td.ts-centro { text-align: center; min-width: 2.6rem; }
table.ts-tab td.ts-cod { font-family: 'IBM Plex Mono', ui-monospace, monospace; font-size: .8em; min-width: 12rem; }
table.ts-tab td.ts-st-ok { color: var(--ts-ok); font-weight: 600; }
table.ts-tab td.ts-st-ruim { color: var(--ts-ruim); font-weight: 600; }
table.ts-tab td.ts-st-alerta { color: var(--ts-alerta); font-weight: 600; }
@media print { .ts-tab-caixa.ts-tab-alta { max-height: none; overflow: visible; } }

/* ---- operadores e suites de mutacao ---- */
.ts-operadores { display:grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: .9rem; margin: .4rem 0 .8rem; }
.ts-operador { background: var(--ts-cartao); border:1px solid var(--ts-linha); border-radius: 14px; padding: .95rem 1.05rem;
  display:flex; flex-direction:column; gap:.4rem; min-width:0; }
.ts-operador .ts-sigla { margin:0; font-weight:700; font-size:1.5rem; letter-spacing:.02em; color: var(--ts-destaque); line-height:1; }
.ts-operador h3 { margin:0; font-size:1rem; font-weight:600; color: var(--ts-tinta); }
.ts-operador .ts-tecnico { margin:0; }
.ts-operador .ts-texto { margin:0; color: var(--ts-suave); font-size:.88rem; line-height:1.45; }
.ts-exemplo-mut { background: var(--ts-relevo); border-radius:10px; padding:.55rem .65rem; display:flex; flex-direction:column; gap:.25rem; }
.ts-exemplo-mut small { color: var(--ts-suave); font-size:.76rem; }
.ts-exemplo-mut code { font-size:.8rem; background:none; padding:0; color: var(--ts-tinta); overflow-wrap:anywhere; }
.ts-seta { color: var(--ts-destaque); font-weight:700; font-size:.85rem; }
.ts-suites { display:flex; flex-direction:column; gap:.5rem; margin:.4rem 0 .6rem; }
.ts-suite { display:grid; grid-template-columns: minmax(0,1.3fr) minmax(0,2fr) 8.5rem; gap:1rem; align-items:center;
  background: var(--ts-cartao); border:1px solid var(--ts-linha); border-radius:12px; padding:.6rem .9rem; }
.ts-suite-escolhida { border-color: var(--ts-destaque); box-shadow: inset 4px 0 0 var(--ts-destaque); }
.ts-suite-nome, .ts-suite-num { display:flex; flex-direction:column; gap:.1rem; min-width:0; }
.ts-suite-nome b, .ts-suite-num b { color: var(--ts-tinta); font-size:.95rem; }
.ts-suite small { color: var(--ts-suave); font-size:.8rem; }
.ts-suite-num { text-align:right; align-items:flex-end; }
.ts-barra { height:12px; border-radius:999px; background: var(--ts-relevo); overflow:hidden; }
.ts-barra span { display:block; height:100%; border-radius:999px; }
.ts-barra-ok span { background: var(--ts-ok); } .ts-barra-alerta span { background: var(--ts-alerta); }
.ts-barra-ruim span { background: var(--ts-ruim); }
@media (max-width: 1100px) { .ts-operadores { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 760px) { .ts-operadores { grid-template-columns: 1fr; }
  .ts-suite { grid-template-columns: 1fr; gap:.4rem; } .ts-suite-num { text-align:left; align-items:flex-start; } }

/* ---- fluxos do caso de uso ---- */
.ts-fluxos { display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: .9rem; margin: .4rem 0 1rem; }
.ts-fluxo { background: var(--ts-cartao); border:1px solid var(--ts-linha); border-top-width: 4px; border-radius: 14px;
  padding: .95rem 1.1rem; display:flex; flex-direction:column; gap:.45rem; min-width:0; }
.ts-fluxo-ok { border-top-color: var(--ts-ok); } .ts-fluxo-alerta { border-top-color: var(--ts-alerta); }
.ts-fluxo-ruim { border-top-color: var(--ts-ruim); }
.ts-fluxo .ts-texto { margin:0; color: var(--ts-suave); font-size:.9rem; line-height:1.45; }
.ts-fluxo .ts-detalhe { margin:0; color: var(--ts-suave); font-size:.82rem; overflow-wrap:anywhere; }
@media (max-width: 760px) { .ts-fluxos { grid-template-columns: 1fr; } }

/* ---- calculo do Epsilon ---- */
.ts-contas { display:grid; gap: .9rem; margin: .4rem 0 1rem; }
.ts-conta .ts-tecnico { margin: 0 0 .6rem; }
.ts-passos { list-style:none; margin:0 !important; padding:0 !important; display:grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: .8rem; }
.ts-passos li { margin:0 !important; display:flex; gap:.7rem; align-items:flex-start; background: var(--ts-relevo); border-radius: 12px; padding: .8rem .9rem; }
.ts-passos li div { display:flex; flex-direction:column; gap:.2rem; min-width:0; }
.ts-passos small { color: var(--ts-suave); font-size:.82rem; }
.ts-passos b { font-size: 1.12rem; color: var(--ts-tinta); line-height:1.35; overflow-wrap:anywhere; }
.ts-passos b b { font-size: inherit; color: var(--ts-destaque, var(--ts-tinta)); }
.ts-passos em { font-style: normal; color: var(--ts-suave); font-size: .84rem; line-height:1.4; }
@media (max-width: 760px) { .ts-passos { grid-template-columns: 1fr; } }

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

# Cor de destaque escolhida na barra lateral: (modo claro, modo escuro, fundo suave claro, fundo suave escuro).
CORES = {
    "Azul (padrão)": ("#1a56b8", "#78b0f5", "#e1eafa", "#15283f"),
    "Verde-petróleo": ("#0f766e", "#4fd1c5", "#dcf2ef", "#0e2e2b"),
    "Roxo": ("#6d28d9", "#b39dfa", "#ede6fc", "#241a3d"),
    "Laranja": ("#c2410c", "#fb9a5c", "#fdeadf", "#3a1d0e"),
    "Vinho": ("#9f1239", "#f58aa6", "#fbe4ea", "#3a1220"),
    "Grafite": ("#334155", "#cbd5e1", "#e6eaf0", "#1f2833"),
}
COR_PERSONALIZADA = "Personalizada"


def _mistura(cor_a: str, cor_b: str, t: float) -> str:
    """Mistura duas cores hex: t=0 devolve a primeira, t=1 a segunda."""
    a = [int(cor_a[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(cor_b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _luminancia(cor: str) -> float:
    r, g, b = (int(cor[i:i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def paleta(nome: str, personalizada: str = "#1a56b8"):
    """As quatro cores de destaque. A personalizada e ajustada para ter contraste nos dois modos."""
    if nome in CORES:
        return CORES[nome]
    base = personalizada if len(personalizada) == 7 else "#1a56b8"
    claro = base
    while _luminancia(claro) > 0.42:                 # texto colorido precisa ler bem sobre fundo branco
        claro = _mistura(claro, "#000000", 0.15)
    escuro = base
    while _luminancia(escuro) < 0.5:                 # e sobre o fundo escuro
        escuro = _mistura(escuro, "#ffffff", 0.15)
    return claro, escuro, _mistura(claro, "#ffffff", 0.88), _mistura(claro, "#0c131b", 0.8)


def css_da_cor(cores) -> str:
    claro, escuro, suave_claro, suave_escuro = cores
    return (f".stApp, .ts-relatorio {{ --ts-destaque: light-dark({claro}, {escuro}); "
            f"--ts-destaque-suave: light-dark({suave_claro}, {suave_escuro}); }}")


def marca(cor: str) -> str:
    svg = _MARCA_SVG.replace('stroke="#4a86e8"', f'stroke="{cor}"')
    return '<img class="ts-logo" alt="" src="data:image/svg+xml;base64,' + base64.b64encode(svg.encode()).decode() + '">'


CSS_COR_ATUAL = css_da_cor(CORES["Azul (padrão)"])
# Marca do produto: uma lupa sobre a linha de fronteira (o centro do teste de valor limite).
_MARCA_SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" fill="none" stroke="#4a86e8">'
              '<rect x="1.5" y="1.5" width="45" height="45" rx="12" stroke-width="3"/>'
              '<path d="M9 31h30" stroke-width="3" stroke-linecap="round" opacity=".4"/>'
              '<path d="M24 26v10" stroke-width="3" stroke-linecap="round"/>'
              '<circle cx="21" cy="19" r="7.5" stroke-width="3"/>'
              '<path d="M26.5 24.5l5 5" stroke-width="3.4" stroke-linecap="round"/></svg>')
MARCA = ('<img class="ts-logo" alt="" src="data:image/svg+xml;base64,'
         + base64.b64encode(_MARCA_SVG.encode()).decode() + '">')

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
        ("1", "Anexe o programa", "Envie qualquer arquivo .txt com código 4GL. Nada é analisado antes disso; "
                                  "o CAD0001 está disponível como exemplo."),
        ("2", "Diga o que ele deve fazer", "Escolha a função e escreva a especificação do enunciado: faixa válida, "
                                           "valor em branco e fórmula. É dela que vem a resposta certa."),
        ("3", "Receba o laudo", "A ferramenta testa de quatro formas, valida os próprios testes e entrega um resumo "
                                "em linguagem simples, com as provas técnicas e as fontes."),
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
    if q["aprovados"] == 0 or q["sem_oraculo"]:
        return "alerta"
    if nos[0] < nos[1] or arestas[0] < arestas[1] or (mut["MS"] is not None and mut["MS"] < 100):
        return "alerta"
    return "ok"


def veredito_dados(d) -> dict:
    """Selo, titulo, texto e numeros do veredito (usados no site e no PDF)."""
    q, mut = d["qualidade"], d["mutacao"]
    estado = estado_geral(d)
    v = d["suite"]
    causas = [ACHADOS_SIMPLES[c][0].lower() for c in q["achados"]]
    com_oraculo = q["aprovados"] + q["reprovados"]
    if com_oraculo == 0:
        selo = ("Falta a especificação", "alerta")
        titulo = "Os testes rodaram, mas ainda não há como julgar as respostas."
        texto = ("A resposta certa de cada teste vem da especificação do programa. Preencha-a na aba "
                 "Programa e especificação e o laudo é refeito na hora.")
    elif estado == "ruim":
        selo = ("Reprovado na conferência", "ruim")
        titulo = "O programa ainda não cumpre tudo o que foi combinado."
        texto = (f"{q['reprovados']} de {q['total']} testes receberam uma resposta diferente da regra. "
                 f"{'O motivo é um só' if len(causas) == 1 else 'Os motivos'}: {', '.join(causas)}.")
    elif estado == "alerta" and q["sem_oraculo"]:
        selo = ("Aprovado, com ressalvas", "alerta")
        titulo = "O programa respondeu como combinado onde a especificação define a resposta."
        texto = (f"{q['aprovados']} testes aprovados. Em {q['sem_oraculo']} testes a especificação não diz qual "
                 "é a resposta certa; complete-a na aba Programa e especificação.")
    elif estado == "alerta":
        selo = ("Aprovado, com ressalvas", "alerta")
        titulo = "O programa respondeu como combinado, mas os testes ainda não alcançam tudo."
        texto = (f"Os {q['aprovados']} testes com resposta definida foram aprovados. Parte do código ou dos defeitos "
                 "plantados ainda escapa aos testes; veja as conferências abaixo.")
    else:
        selo = ("Aprovado na conferência", "ok")
        titulo = "O programa respondeu como combinado em todos os testes."
        texto = (f"Os {q['aprovados']} testes foram aprovados, passaram por todo o código e perceberam todos os "
                 "defeitos plantados de propósito.")
    fatos = [("Testes executados", q["total"]), ("Formas de teste aplicadas", 4),
             ("Defeitos plantados percebidos", f"{mut['Md']}/{mut['Mt'] - mut['Me']}"),
             ("Conferências dos próprios testes", f"{v['ok']}/{v['total']}")]
    return {"estado": estado, "selo": selo, "titulo": titulo, "texto": texto, "fatos": fatos}


def html_veredito(d) -> str:
    v = veredito_dados(d)
    return (f'<section class="ts-veredito ts-{v["estado"]}"><div>{chip(*v["selo"])}<h2>{esc(v["titulo"])}</h2>'
            f'<p>{esc(v["texto"])}</p></div><dl class="ts-fatos">'
            + "".join(f"<div><dt>{esc(r)}</dt><dd>{esc(x)}</dd></div>" for r, x in v["fatos"]) + "</dl></section>")


def casos_da_regra(chave, casos, spec):
    """Casos que verificam uma regra do combinado."""
    params = spec["params"]
    if chave == "entrada":
        return list(casos)
    if chave == "nulo":
        return [c for c in casos if any(v is None for v in c["entradas"])]
    if chave == "faixa":                        # valores fora da faixa e valores exatamente no limite
        return [c for c in casos if any(cp.fora_da_faixa(p, v) or cp.ponto_de(p, v).startswith("On-Point")
                                        for p, v in zip(params, c["entradas"]))]
    return [c for c in casos if all((v is None and spec["nulo"] == "zero") or
                                    (v is not None and not cp.fora_da_faixa(p, v))
                                    for p, v in zip(params, c["entradas"]))]


def falhas_da_regra(chave, cobrem):
    """Casos que verificam a regra e falharam por causa dela."""
    return [c["id"] for c in cobrem if c["status"] == "Reprovado" and (
        (chave == "entrada" and c["achado"] == "ERRO") or
        (chave == "faixa" and c["achado"] in ("INVALIDO_ACEITO", "VALIDO_REJEITADO")) or
        (chave == "formula" and c["achado"] not in ("INVALIDO_ACEITO", "VALIDO_REJEITADO")) or
        chave == "nulo")]


def situacao_das_regras(d):
    """Para cada regra do combinado: quantos testes a verificam e quais falharam."""
    situacao = []
    for regra in REGRAS:
        cobrem = casos_da_regra(regra["chave"], d["casos_lista"], SPEC)
        situacao.append((len(cobrem), falhas_da_regra(regra["chave"], cobrem)))
    return situacao


def html_regras(d) -> str:
    linhas = []
    for i, (regra, (verificada, falhas)) in enumerate(zip(REGRAS, situacao_das_regras(d)), 1):
        estado = chip(f"Não cumprida em {len(falhas)} teste{'s' if len(falhas) > 1 else ''}", "ruim") if falhas else (
            chip("Cumprida", "ok") if verificada else chip("Sem teste", "neutro"))
        linhas.append(f'<div class="ts-regra"><span class="ts-n">{i}</span><div><small class="ts-req">REQ{i:02d}</small><b>{esc(regra["titulo"])}</b>'
                      f'<small>{esc(regra["detalhe"])}</small></div><div class="ts-direita">{estado}'
                      f'<small>verificada em {verificada} testes</small></div></div>')
    if len(REGRAS) == 1:
        linhas.append('<div class="ts-regra"><span class="ts-n">!</span><div><b>Faltam as regras do resultado</b>'
                      '<small>preencha a especificação na aba Programa e especificação</small></div></div>')
    return '<div class="ts-regras">' + "".join(linhas) + "</div>"


def _medidor(fracao: float) -> str:
    return f'<div class="ts-medidor" aria-hidden="true"><span style="width:{max(0, min(100, fracao * 100)):.0f}%"></span></div>'


def estacoes_dados(d):
    """As quatro conferencias do laudo (site e PDF)."""
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    usos = a["criterios"]["Todos-Usos"]
    com_oraculo = q["aprovados"] + q["reprovados"]
    estrutura_total = nos[0] == nos[1] and arestas[0] == arestas[1]
    ms = mut["MS"]
    cartoes = [
        ("Conferência 1", "Conferimos as respostas", "Caixa-preta: classes de equivalência e valor limite",
         "Como conferir uma calculadora sem abri-la: digitamos valores e comparamos cada resposta com a regra "
         "combinada. Os valores foram escolhidos onde o erro costuma se esconder: nos limites de cada valor, "
         "um passo além deles e em campos em branco.",
         f"{q['aprovados']} de {com_oraculo}", "respostas iguais ao combinado",
         q["aprovados"] / com_oraculo if com_oraculo else 0,
         f"Grupos de valores testados: {q['classes'][0]} de {q['classes'][1]}. "
         f"Fronteiras testadas: {q['pontos'][0]} de {q['pontos'][1]}.",
         ("Encontrou defeito", "ruim") if q["reprovados"] else ("Tudo conforme", "ok")),
        ("Conferência 2", "Percorremos o programa por dentro", "Caixa-branca: grafo de fluxo e McCabe",
         "Como percorrer todas as ruas de um bairro: desenhamos o mapa do código e conferimos se os testes "
         "passaram por cada trecho e por cada desvio.",
         porcento(arestas), "dos desvios percorridos",
         min(nos[0] / nos[1] if nos[1] else 0, arestas[0] / arestas[1] if arestas[1] else 0),
         f"Trechos percorridos: {porcento(nos)}. O mapa tem {m['N']} trechos, {m['E']} ligações e "
         f"{m['V']} caminhos independentes.",
         ("Cobertura total", "ok") if estrutura_total else ("Cobertura parcial", "alerta")),
        ("Conferência 3", "Seguimos cada dado", "Fluxo de dados: pares Def-Uso",
         "Como rastrear uma encomenda: cada valor foi acompanhado do ponto em que é definido até cada ponto "
         "em que é usado.",
         f"{usos[0]} de {usos[1]}", "percursos de dados exercitados",
         usos[0] / usos[1] if usos[1] else 0,
         f"{len(a['fluxo_tabela'])} variáveis acompanhadas, em cálculos e em decisões.",
         ("Todos exercitados", "ok") if usos[0] == usos[1] else ("Faltam percursos", "alerta")),
        ("Conferência 4", "Testamos os próprios testes", "Teste de mutação: escore MS",
         "Como um simulado de incêndio: plantamos defeitos de propósito, um de cada vez, para ver se os "
         "testes dão o alarme.",
         f"{mut['Md']} de {mut['Mt'] - mut['Me']}", "defeitos plantados foram percebidos",
         (ms or 0) / 100,
         f"Escore de mutação: {texto_ms(mut)}." + (f" {mut['Me']} equivalentes descontados." if mut["Me"] else "")
         + "".join(f" Só com o caminho feliz, {l['Md']} de {l['Mt'] - l['Me']} seriam percebidos."
                   for l in d.get("comparacao_suites", []) if l["nome"] == "Somente caminho feliz" and l["casos"]),
         ("Testes atentos", "ok") if ms is not None and ms >= 100 else
         (("Bons, com lacunas", "alerta") if ms is not None and ms >= 80 else ("Testes fracos", "ruim"))),
    ]
    return cartoes


def html_estacoes(d) -> str:
    cartoes = estacoes_dados(d)
    blocos = []
    for passo, titulo, tecnico, texto, numero, rotulo, fracao, detalhe, selo in cartoes:
        blocos.append(f'<article class="ts-estacao"><div class="ts-estacao-topo"><span class="ts-passo">{esc(passo)}'
                      f'</span>{chip(*selo)}</div><h3>{esc(titulo)}</h3><p class="ts-tecnico">{esc(tecnico)}</p>'
                      f'<p class="ts-texto">{esc(texto)}</p><div class="ts-medida"><b>{esc(numero)}</b>'
                      f'<span>{esc(rotulo)}</span></div>{_medidor(fracao)}<p class="ts-detalhe">{esc(detalhe)}</p></article>')
    return '<div class="ts-estacoes">' + "".join(blocos) + "</div>"


def _descreve_entrada(caso, nomes) -> str:
    if caso["tecnica"] == "Extra":
        return caso["observacao"] or "caso extra"
    i = nomes.index(caso["alvo"]) if caso["alvo"] in nomes else 0
    p, rotulo = SPEC["params"][i], caso["rotulo"]
    onde = f"no {cp.ordinal(i)} valor"
    lado = "máximo" if "(máx.)" in rotulo or p["minimo"] is None else "mínimo"
    if rotulo.startswith("On-Point"):
        return f"exatamente no {lado} permitido, {onde}"
    if rotulo.startswith("Off-Point"):
        return f"um passo (ε) além do {lado}, {onde}"
    if rotulo.startswith("Exterior"):
        return f"um valor bem fora da faixa, {onde}"
    return {"Interior": f"um valor comum {onde}", "Nulo": f"campo em branco {onde}"}.get(rotulo, "")


def _o_que_manda(caso) -> str:
    r = SPEC["retorno_invalido"]
    if r is not None and caso["esperado"] == r.quantize(caso["esperado"]):
        return "recusar, porque há valor fora da faixa"
    return "o resultado da conta"


def caso_exemplar(d):
    """O caso que melhor mostra o defeito principal (de preferencia o Off-Point)."""
    reprovados = [c for c in d["casos_lista"] if c["status"] == "Reprovado"]
    if not reprovados:
        return None
    principal = next(iter(d["qualidade"]["achados"]))
    candidatos = [c for c in reprovados if c["achado"] == principal]
    return next((c for c in candidatos if c["rotulo"].startswith("Off-Point")), candidatos[0])


def html_exemplo(d) -> str:
    caso = caso_exemplar(d)
    q, a = d["qualidade"], d["analise"]
    if caso is None and q["aprovados"] == 0:
        return ('<div class="ts-cartao"><h3>Sem resposta certa definida</h3><p>Os testes foram executados, mas a '
                'especificação ainda não diz qual deveria ser a resposta. Preencha-a na aba Programa e '
                'especificação para ver aqui um teste do começo ao fim.</p></div>')
    if caso is None:
        julgados = [c for c in d["casos_lista"] if c["status"] == "Aprovado"]
        bom = next((c for c in julgados if c["rotulo"].startswith("Off-Point")), julgados[0])
        return (f'<div class="ts-exemplo"><div><span class="ts-rot">O teste mais difícil enviou</span>'
                f'<b class="ts-num">{esc(texto_entrada(bom["entradas"]))}</b><small>{esc(_descreve_entrada(bom, d["parametros"]))}</small></div>'
                f'<div><span class="ts-rot">O combinado manda</span><b class="ts-num">{esc(formato_br(bom["esperado"]))}</b>'
                f'<small>{_o_que_manda(bom)}</small></div>'
                f'<div class="ts-certo"><span class="ts-rot">O programa respondeu</span><b class="ts-num">{esc(formato_br(bom["obtido"]))}</b>'
                '<small>exatamente o combinado</small></div></div>')
    explica_obtido = {"INVALIDO_ACEITO": "fez a conta como se o valor fosse válido",
                      "VALIDO_REJEITADO": "recusou um valor que a regra aceita",
                      "NULO": "devolveu vazio", "CALCULO": "fez uma conta diferente da regra",
                      "ERRO": "parou com erro"}[caso["achado"]]
    obtido = "erro" if caso["erro"] else formato_br(caso["obtido"])
    exemplo = (f'<div class="ts-exemplo"><div><span class="ts-rot">O teste enviou</span>'
               f'<b class="ts-num">{esc(texto_entrada(caso["entradas"]))}</b><small>{esc(_descreve_entrada(caso, d["parametros"]))}</small></div>'
               f'<div><span class="ts-rot">O combinado manda</span><b class="ts-num">{esc(formato_br(caso["esperado"]))}</b>'
               f'<small>{_o_que_manda(caso)}</small></div>'
               f'<div class="ts-errado"><span class="ts-rot">O programa respondeu</span><b class="ts-num">{esc(obtido)}</b>'
               f'<small>{esc(explica_obtido)}</small></div></div>')
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    total = nos[0] == nos[1] and arestas[0] == arestas[1]
    ids = q["achados"][caso["achado"]]
    porque = ('<div class="ts-cartao"><h3>Por que só a conferência 1 percebeu</h3>'
              + (f'<p>O mesmo problema apareceu em {len(ids)} testes ({esc(", ".join(ids))}).</p>' if len(ids) > 1 else
               f'<p>O problema apareceu no teste {esc(ids[0])}.</p>')
              + ('<p>As conferências 2, 3 e 4 examinam o código que foi escrito, e nele tudo foi percorrido e vigiado. '
                 'Mas a verificação da faixa válida não está no código: não há trecho para percorrer nem defeito para plantar. '
                 'Só quem compara a resposta com o combinado percebe o que falta. É por isso que o laudo usa mais de '
                 'uma forma de teste.</p>' if total and caso["achado"] == "INVALIDO_ACEITO" else
                 '<p>Cada forma de teste enxerga um tipo de problema; comparar a resposta com o combinado é a que '
                 'mostra se o programa faz o que foi pedido.</p>') + "</div>")
    conserto = esc(cp.condicao_que_falta(SPEC))
    if caso["achado"] == "INVALIDO_ACEITO" and conserto:
        corrige = (f'<div class="ts-cartao"><h3>Como corrigir</h3><p>Antes da conta, incluir a verificação que falta:</p>'
                   f'<pre>{conserto}</pre><p>Cole essas linhas no fonte, na aba Programa e especificação, e veja o laudo mudar na hora.</p></div>')
    elif caso["achado"] == "VALIDO_REJEITADO":
        p = SPEC["params"][d["parametros"].index(caso["alvo"])] if caso["alvo"] in d["parametros"] else None
        limite = ""
        if p is not None:
            limite = formato_br(p["maximo"] if "(máx.)" in caso["rotulo"] or p["minimo"] is None else p["minimo"])
        corrige = ('<div class="ts-cartao"><h3>Como corrigir</h3><p>O valor do limite faz parte da faixa válida e '
                   f'foi recusado. Procure no código a comparação com {esc(limite) or "o limite"} e confira o sinal: '
                   'para aceitar o próprio limite, use &gt; no lugar de &gt;= (ou &lt; no lugar de &lt;=).</p>'
                   '<p>Corrija o fonte na aba Programa e especificação e veja o laudo mudar na hora.</p></div>')
    else:
        corrige = ('<div class="ts-cartao"><h3>Como corrigir</h3><p>Compare o trecho do código responsável por essa '
                   'regra com o combinado; a aba da Sprint 1 lista todos os testes que falharam.</p></div>')
    return exemplo + f'<div class="ts-duas">{porque}{corrige}</div>'


def html_confianca(d) -> str:
    """A suite tambem foi validada (Sprint 4): o resumo para leigos."""
    v, q = d["suite"], d["qualidade"]
    tudo = v["ok"] == v["total"]
    itens = "".join(f'<li>{"✓" if c["ok"] else "!"}&nbsp; {esc(c["pergunta"])}<span>{esc(c["curto"])}</span></li>'
                    for c in v["criterios"])
    if tudo and q["reprovados"]:
        conclusao = "Como os testes passaram em todas as conferências, o defeito apontado é do programa, e não do teste."
    elif tudo:
        conclusao = "Como os testes passaram em todas as conferências, a aprovação do programa é confiável."
    else:
        conclusao = "Os itens marcados com ! mostram onde os testes ainda podem melhorar; a Sprint 4 detalha cada um."
    return (f'<div class="ts-confianca"><div class="ts-placar{"" if tudo else " ts-placar-ruim"}"><b>{v["ok"]}/{v["total"]}</b>'
            '<span>conferências dos próprios testes atendidas</span></div><div class="ts-cartao">'
            '<h3>Antes do veredito, os testes foram testados</h3>'
            f'<p>Um laudo só vale tanto quanto os testes que o sustentam. Por isso a suíte de {esc(FUNCAO_ALVO)} passou por '
            f'{v["total"]} conferências antes de qualquer conclusão sobre o programa:</p>'
            f'<ul class="ts-lista">{itens}</ul>'
            f'<p style="margin-top:.8rem"><b>{esc(conclusao)}</b></p>'
            '<p style="margin-top:.5rem"><b>Quem decide o que é certo.</b> A resposta esperada de cada teste vem da '
            'regra escrita no manual, e não do próprio código. Assim o programa nunca é comparado com ele mesmo.</p>'
            "</div></div>")


def itens_dos_limites():
    return [
        ("Uma função por vez.", f"O laudo examina a função {FUNCAO_ALVO}; telas, banco de dados e a "
                                "comunicação entre módulos ficam fora."),
        ("Interpretação do código.", "A ferramenta lê e executa o 4GL por conta própria (IF, CASE, WHILE, FOR, "
                                     "LET, RETURN); ela não é o compilador Informix. Comandos de tela, como "
                                     "DISPLAY e ERROR, são ignorados."),
        ("A resposta certa vem da especificação.", "Se a especificação escrita na página estiver errada, o "
                                                   "laudo também estará. Ela deve ser copiada do enunciado, "
                                                   "nunca do código."),
        ("Sugestões são indícios.", "Quando a ferramenta sugere um teste novo ou aponta um caminho impossível, ela "
                                    "se baseia em mil combinações de valores, não em uma prova matemática."),
        ("Textos de IA são opcionais.", "O Gemini só redige textos; todos os números vêm dos cálculos da ferramenta."),
    ]


def html_limites() -> str:
    itens = itens_dos_limites()
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


def _potencia(expoente) -> str:
    return f"10<sup>{'−' if expoente > 0 else ''}{expoente}</sup>" if expoente else "10<sup>0</sup>"


def _o_que_e_o_passo(tipo) -> str:
    if tipo["escala"] == 0:
        return "uma unidade inteira (o tipo não tem casas decimais)"
    if tipo["escala"] == 2:
        return "um centavo"
    return f"a {tipo['escala']}ª casa depois da vírgula"


def _offpoints(p):
    """Contas dos Off-Points de um parametro: [(texto_html, texto_simples)]."""
    eps, contas = p["tipo"]["epsilon"], []
    if p["minimo"] is not None:
        contas.append((f"{esc(formato_br(p['minimo']))} − {esc(formato_br(eps))} = <b>{esc(formato_br(p['minimo'] - eps))}</b>",
                       f"{formato_br(p['minimo'])} − {formato_br(eps)} = {formato_br(p['minimo'] - eps)}"))
    if p["maximo"] is not None:
        contas.append((f"{esc(formato_br(p['maximo']))} + {esc(formato_br(eps))} = <b>{esc(formato_br(p['maximo'] + eps))}</b>",
                       f"{formato_br(p['maximo'])} + {formato_br(eps)} = {formato_br(p['maximo'] + eps)}"))
    return contas


def tabela_epsilon(spec) -> pd.DataFrame:
    """O calculo do Epsilon de cada parametro, com as contas escritas."""
    linhas = []
    for p in spec["params"]:
        t = p["tipo"]
        s_ = t["escala"]
        maior = (f"10^({t['precisao']} − {s_}) − ε = {formato_br(t['maximo'])}" if t.get("precisao") is not None
                 else f"{formato_br(t['maximo'])} (limite do tipo)")
        offs = [simples for _, simples in _offpoints(p)]
        linhas.append({"Parâmetro": p["nome"], "Tipo": t["rotulo"], "Casas decimais (s)": s_,
                       "ε = 10^−s": f"10^−{s_} = {formato_br(t['epsilon'])}" if s_ else "10^0 = 1",
                       "Maior valor do tipo": maior,
                       "Off-Point = fronteira ∓ ε": "; ".join(offs) if offs else "sem fronteira na especificação",
                       "Observação": t["nota"]})
    return pd.DataFrame(linhas)


def html_epsilon(spec) -> str:
    """O calculo do Epsilon em tres passos, um quadro por grupo de parametros iguais."""
    grupos = {}
    for p in spec["params"]:
        chave = (p["tipo"]["rotulo"], p["minimo"], p["maximo"])
        grupos.setdefault(chave, []).append(p)
    quadros = []
    for grupo in grupos.values():
        p, t = grupo[0], grupo[0]["tipo"]
        offs = _offpoints(p)
        terceiro = ("<br>".join(f"Off-Point = {html_}" for html_, _ in offs) if offs else
                    "Sem faixa válida na especificação, não há fronteira")
        passos = [
            ("Tipo declarado no código", esc(t["rotulo"]),
             ("nenhuma casa depois da vírgula" if t["escala"] == 0 else
              f"{t['escala']} casa{'s' if t['escala'] != 1 else ''} depois da vírgula")
             + (f" ({t['nota']})" if t["nota"] else "")),
            ("Menor passo que o tipo representa", f"ε = {_potencia(t['escala'])} = {esc(formato_br(t['epsilon']))}",
             esc(_o_que_e_o_passo(t))),
            ("Primeiro valor fora da fronteira", terceiro,
             "o valor inválido mais próximo do limite: só ele distingue um &lt; de um &lt;= no código"),
        ]
        itens = "".join(f'<li><span class="ts-n">{i}</span><div><small>{titulo}</small><b>{valor}</b>'
                        f'<em>{nota}</em></div></li>' for i, (titulo, valor, nota) in enumerate(passos, 1))
        quadros.append(f'<article class="ts-cartao ts-conta"><p class="ts-tecnico">'
                       f'{esc(", ".join(x["nome"] for x in grupo))}</p><ol class="ts-passos">{itens}</ol></article>')
    return '<div class="ts-contas">' + "".join(quadros) + "</div>"


def html_parecer_profissional(dados, titulo: str = "") -> str:
    assinatura_txt = " · ".join(x for x in (dados["nome"] or "Profissional não identificado", dados["funcao"],
                                            dados["quando"]) if x)
    paragrafos = "".join(f"<p>{esc(par)}</p>" for par in dados["texto"].split("\n") if par.strip())
    return (f'<article class="ts-cartao ts-parecer-prof"><div class="ts-parecer-topo">'
            f'<span class="ts-passo">{esc(titulo or "Parecer do profissional técnico")}</span>'
            f'{chip(dados["veredito"], TIPO_DO_VEREDITO.get(dados["veredito"], "neutro"))}</div>'
            f'{paragrafos}<p class="ts-assina">{esc(assinatura_txt)}</p></article>')


def html_pareceres_do_laudo(d) -> str:
    """Na parte do laudo para leigos: o parecer geral do profissional e o da IA, se existirem."""
    partes = []
    prof = d.get("pareceres_prof", {}).get("geral")
    if prof:
        partes.append(html_parecer_profissional(prof, "Parecer do profissional técnico"))
    ia = d.get("pareceres", {}).get("geral")
    if ia:
        partes.append(f'<article class="ts-cartao"><span class="ts-passo">Parecer escrito com IA (Gemini)</span>'
                      f'<pre class="parecer">{esc(ia["texto"])}</pre><p class="ts-assina">Modelo {esc(ia["modelo"])} · '
                      f'{esc(ia["quando"])}</p></article>')
    return "".join(partes)


COLUNAS_DE_CODIGO = {"Asserção", "Original", "Mutante (alterado)", "Comandos", "Comando", "Trecho", "Caminho",
                     "Nós percorridos", "Arestas percorridas"}
_NUMERO = __import__("re").compile(r"^-?[\d.]+(,\d+)?%?$|^NULL$|^—$")


def _classe_da_celula(coluna: str, texto: str, numerica: bool, marcas: bool) -> str:
    classes = []
    if numerica:
        classes.append("ts-num")
    if marcas:
        classes.append("ts-centro")
    if coluna in COLUNAS_DE_CODIGO:
        classes.append("ts-cod")
    if texto.startswith("✓") or texto in ("Morto", "Atendido"):
        classes.append("ts-st-ok")
    elif texto.startswith("✕") or texto == "Reprovado":
        classes.append("ts-st-ruim")
    elif texto.startswith("!") or texto == "Vivo":
        classes.append("ts-st-alerta")
    return " ".join(classes)


def html_tabela(df: pd.DataFrame) -> str:
    """Tabela da pagina: cabecalho fixo, linhas alternadas, texto que quebra linha,
    numeros a direita, codigo em fonte monoespacada e estados coloridos."""
    if df is None or df.empty:
        return '<p class="ts-detalhe">Nada a mostrar.</p>'
    textos = df.astype(str).replace({"nan": "", "None": ""})
    colunas = list(df.columns)
    numericas = {c for c in colunas if all(_NUMERO.match(v.strip()) or v.strip() == "" for v in textos[c])
                 and any(v.strip() for v in textos[c])}
    marcas = {c for c in colunas if all(v in ("✓", "✕", "") or v.isdigit() for v in textos[c].str.strip())
              and any(v in ("✓", "✕") for v in textos[c].str.strip())}
    cab = "".join(f'<th class="{"ts-num" if c in numericas else ("ts-centro" if c in marcas else "")}">{esc(c)}</th>'
                  for c in colunas)
    linhas = []
    for _, linha in textos.iterrows():
        celulas = "".join(f'<td class="{_classe_da_celula(c, linha[c].strip(), c in numericas, c in marcas)}">'
                          f'{esc(linha[c])}</td>' for c in colunas)
        linhas.append(f"<tr>{celulas}</tr>")
    alta = " ts-tab-alta" if len(df) > 14 else ""
    larga = " ts-tab-larga" if len(colunas) > 9 else ""
    return (f'<div class="ts-tab-caixa{alta}{larga}"><table class="ts-tab"><thead><tr>{cab}</tr></thead>'
            f'<tbody>{"".join(linhas)}</tbody></table></div>')


def mostrar_tabela(df: pd.DataFrame) -> None:
    st.html(html_tabela(df))


def html_matriz(casos, spec) -> str:
    """Matriz parametro x ponto: mostra de uma vez o que foi coberto e o resultado."""
    colunas = []
    for p in spec["params"]:
        for ponto in cp.pontos_do_parametro(p):
            if ponto["rotulo"] not in colunas:
                colunas.append(ponto["rotulo"])
    colunas.append("Nulo")
    partes = ["<div class='rolagem'><table class='ts-matriz'><thead><tr><th>Parâmetro</th>"]
    partes += [f"<th>{esc(c)}</th>" for c in colunas]
    partes.append("</tr></thead><tbody>")
    for p in spec["params"]:
        existentes = {x["rotulo"] for x in cp.pontos_do_parametro(p)} | {"Nulo"}
        partes.append(f"<tr><th>{esc(p['nome'])}</th>")
        for coluna in colunas:
            if coluna not in existentes:
                partes.append("<td><small>não se aplica</small></td>")
                continue
            caso = next((c for c in casos if c["alvo"] == p["nome"] and c["rotulo"] == coluna), None)
            if caso is None:
                partes.append(f"<td>{chip('não testado', 'neutro')}</td>")
                continue
            tipo = {"Aprovado": "ok", "Reprovado": "ruim"}.get(caso["status"], "neutro")
            partes.append(f"<td>{chip(caso['status'], tipo)}<small>{caso['id']}</small></td>")
        partes.append("</tr>")
    partes.append("</tbody></table></div>")
    return "".join(partes)


def svg_regua(fronteira, lado: str, pontos, epsilon, texto_invalido: str, texto_valido: str) -> str:
    """Regua de uma fronteira: regiao invalida de um lado, valida do outro.
    Escala logaritmica dos dois lados da fronteira, para que o On-Point e o
    Off-Point (separados por um Epsilon) nao fiquem um em cima do outro."""
    import math
    largura, esquerda, direita = 960, 46, 46
    c = float(epsilon) / 5
    deslocamentos = [float(p["valor"] - fronteira) for p in pontos]
    maior = max([abs(v) for v in deslocamentos] + [float(epsilon)]) * 4

    def f(x):
        return math.copysign(math.log10(1 + abs(x) / c), x)

    def X(x):
        return esquerda + (f(x) - f(-maior)) / (f(maior) - f(-maior)) * (largura - esquerda - direita)

    zero = X(0)
    cor_esq, cor_dir = ("var(--ts-invalido)", "var(--ts-valido)") if lado == "min" else \
        ("var(--ts-valido)", "var(--ts-invalido)")
    texto_esq, texto_dir = (texto_invalido, texto_valido) if lado == "min" else (texto_valido, texto_invalido)
    partes = [f'<svg viewBox="0 0 {largura} 176" class="ts-regua" role="img" '
              f'aria-label="Régua da fronteira {esc(formato_br(fronteira))} com os pontos testados">',
              f'<rect x="{X(-maior):.1f}" y="78" width="{zero - X(-maior):.1f}" height="28" rx="6" fill="{cor_esq}"/>',
              f'<rect x="{zero:.1f}" y="78" width="{X(maior) - zero:.1f}" height="28" rx="6" fill="{cor_dir}"/>',
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
        valor = (fronteira + Decimal(str(marca))).quantize(epsilon)
        partes.append(f'<text class="ts-suave" x="{x:.1f}" y="130" font-size="12" text-anchor="middle">'
                      f'{esc(formato_br(valor))}</text>')
    lados = {"min": {"Off-Point": ("end", -9), "On-Point": ("start", 9)},
             "max": {"On-Point": ("end", -9), "Off-Point": ("start", 9)}}[lado]
    anterior, alto = None, False
    for ponto, d in sorted(zip(pontos, deslocamentos), key=lambda par: par[1]):
        x = X(d)
        nome = ponto["rotulo"].split(" (")[0]
        ancora, dx = lados.get(nome, ("middle", 0))
        alto = (not alto) if anterior is not None and x - anterior < 150 else False
        anterior = x
        y = 14 if alto else 40
        guia = (f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y + 22}" y2="84" stroke="var(--ts-linha)" stroke-width="1"/>'
                if alto else "")
        partes.append(f'<g><title>{esc(ponto["rotulo"])}: {esc(formato_br(ponto["valor"]))}. '
                      f'{esc(ponto["condicao"])}. Esperado: {esc(ponto["esperado"])}.</title>{guia}'
                      f'<text class="ts-tinta" x="{x + dx:.1f}" y="{y}" font-size="14" font-weight="700" text-anchor="{ancora}">{esc(nome)}</text>'
                      f'<text class="ts-suave" x="{x + dx:.1f}" y="{y + 18}" font-size="13" text-anchor="{ancora}">{esc(formato_br(ponto["valor"]))}</text>'
                      f'<circle class="ts-ponto" cx="{x:.1f}" cy="92" r="7.5" stroke-width="2.4"/></g>')
    partes.append(f'<text class="ts-suave" x="{esquerda}" y="160" font-size="12.5">{esc(texto_esq)}</text>')
    partes.append(f'<text class="ts-suave" x="{largura - direita}" y="160" font-size="12.5" text-anchor="end">'
                  f'{esc(texto_dir)}</text>')
    partes.append(f'<rect x="{esquerda - 16}" y="151" width="11" height="11" rx="2" fill="{cor_esq}"/>')
    partes.append(f'<rect x="{largura - direita + 5}" y="151" width="11" height="11" rx="2" fill="{cor_dir}"/>')
    partes.append("</svg>")
    return "".join(partes)


def dados_das_reguas(spec):
    """Uma regua por fronteira: [(titulo, dados)] (o site desenha em SVG; o PDF, com reportlab)."""
    r = spec["retorno_invalido"]
    resposta = f", a resposta deve ser {formato_br(r)}" if r is not None else ""
    lista = []
    for grupo in grupos_de_fronteira(spec):
        p = grupo[0]
        nomes = ", ".join(x["nome"] for x in grupo)
        for lado, limite in (("min", p["minimo"]), ("max", p["maximo"])):
            if limite is None:
                continue
            pontos = [{**x, "esperado": esperado_do_ponto(spec, x)} for x in cp.pontos_do_parametro(p)
                      if x["lado"] == lado or x["rotulo"] == "Interior"]
            b = formato_br(limite)
            if lado == "min":
                invalido = f"Região inválida: valor menor que {b}{resposta}"
                valido = f"Região válida: valor de {b} para cima"
                titulo = f"{nomes}: limite mínimo {b}"
            else:
                invalido = f"Região inválida: valor maior que {b}{resposta}"
                valido = f"Região válida: valor até {b}"
                titulo = f"{nomes}: limite máximo {b}"
            lista.append((titulo, {"fronteira": limite, "lado": lado, "epsilon": p["tipo"]["epsilon"],
                                   "pontos_completos": pontos, "invalido": invalido, "valido": valido,
                                   "pontos": [(x["rotulo"], x["valor"], x["valido"]) for x in pontos]}))
    return lista


def reguas(spec):
    """Uma regua por fronteira: [(titulo, svg)]."""
    return [(titulo, svg_regua(r["fronteira"], r["lado"], r["pontos_completos"], r["epsilon"], r["invalido"],
                               r["valido"])) for titulo, r in dados_das_reguas(spec)]


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
    v = d["suite"]
    pareceres = d.get("pareceres", {})
    profissionais = d.get("pareceres_prof", {})
    parecer = ""
    if profissionais:
        nomes_p = {**{k: e["titulo"] for k, e in ETAPAS.items()}, "geral": "Parecer geral"}
        parecer += ("<h2 class='anexo'>Pareceres do profissional técnico</h2>" + "".join(
            html_parecer_profissional(profissionais[k], nomes_p[k]) for k in ["geral"] + list(ETAPAS) if k in profissionais))
    if pareceres:
        nomes = {**{k: e["titulo"] for k, e in ETAPAS.items()}, "geral": "Parecer geral"}
        parecer += "<h2 class='anexo'>Pareceres escritos com o Gemini</h2><p class='nota'>Textos redigidos por IA a partir dos números deste laudo.</p>" + "".join(
            f"<h3>{esc(nomes[k])}</h3><pre class='parecer'>{esc(pareceres[k]['texto'])}</pre>"
            f"<p class='nota'>Modelo {esc(pareceres[k]['modelo'])}, {esc(pareceres[k]['quando'])}.</p>"
            for k in ["geral"] + list(ETAPAS) if k in pareceres)
    dot = json.dumps(motor.grafo_em_dot(a["grafo"], set(a["nos_cobertos"]), set(a["arestas_cobertas"]))
                     ).replace("</", "<\\/")

    def tabela(df):
        return '<div class="rolagem">' + df.to_html(index=False, border=0, classes="t", escape=True) + "</div>"

    def base(chave):
        return "<p class='nota'>Base teórica: " + "; ".join(
            f"[{n}] {esc(REF[n]['curto'])}{', ' + esc(det) if det else ''}" for n, det in BASES[chave]) + ".</p>"

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Laudo de qualidade — {esc(FUNCAO_ALVO)}</title>
<style>
{_fontes_embutidas()}
{ESTILO_CSS}
{CSS_COR_ATUAL}
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
.ts-acoes {{ position: sticky; top: 0; z-index: 5; display:flex; justify-content:flex-end; gap:.6rem;
  padding:.6rem 0; background: light-dark(#f6f8fbee, #0c131bee); }}
.ts-acoes button {{ font: inherit; font-weight:600; cursor:pointer; border-radius:10px; padding:.5rem 1rem;
  border:1px solid var(--ts-destaque); background: var(--ts-destaque); color: light-dark(#fff, #0c131b); }}
@page {{ size: A4; margin: 14mm 12mm 16mm; }}
@media print {{
  html, body {{ background:#ffffff !important; }}
  .ts-relatorio {{ color-scheme: light; font-size: 10pt; }}
  .ts-acoes {{ display:none !important; }}
  .pagina {{ max-width: 100%; width: 100%; margin: 0 auto; padding: 0; box-sizing: border-box; }}
  h2.anexo {{ break-before: page; }}
  h2, h3 {{ break-after: avoid; }}
  .ts-estacao, .ts-regra, tr, .ts-cartao, .ts-operador, .ts-fluxo, .ts-suite, .kpi, svg {{ break-inside: avoid; }}
  table.t {{ font-size: 7.6pt; }} table.t th, table.t td {{ white-space: normal !important; padding: .25rem .35rem; }}
  .rolagem {{ overflow: visible !important; }}
  .ts-estacoes, .ts-operadores {{ grid-template-columns: repeat(2, minmax(0,1fr)); }}
  .ts-veredito {{ grid-template-columns: 1fr; }}
  .ts-faixa {{ grid-template-columns: repeat(3, minmax(0,1fr)); }}
  svg {{ max-width: 100% !important; height: auto; }}
}}
</style></head><body class="ts-relatorio"><div class="pagina">
<div class="ts-acoes"><button type="button" onclick="window.print()">Salvar em PDF ou imprimir</button></div>
{html_topo()}
{html_faixa(d)}
{html_veredito(d)}
{html_secao("O combinado, regra por regra", "O que o manual diz que a função deve fazer, e se ela cumpriu cada regra nos testes.")}
{html_regras(d)}
{html_secao("Como o programa foi testado", "Quatro conferências independentes. Cada uma responde a uma pergunta diferente sobre a qualidade.")}
{html_estacoes(d)}
{html_secao("O defeito, em um exemplo" if caso_exemplar(d) else "Um exemplo de teste", "Um dos testes, do começo ao fim.")}
{html_exemplo(d)}
{html_secao("Por que confiar nestes testes")}
{html_confianca(d)}
{(html_secao("Pareceres") + '<div class="ts-pareceres">' + html_pareceres_do_laudo(d) + "</div>") if html_pareceres_do_laudo(d) else ""}
{html_secao("O que este laudo não cobre")}
{html_limites()}
{html_secao("Glossário", "Os termos técnicos usados nos anexos, em linguagem simples.")}
{html_glossario()}

<h2 class="anexo">Anexo A. Caixa-preta: classes de equivalência e valor limite</h2>
{base("caixa_preta")}
<div class="kpis"><div class="kpi"><b>{q['total']}</b><span>casos executados</span></div><div class="kpi"><b>{q['aprovados']}</b><span>aprovados</span></div>
<div class="kpi"><b>{q['reprovados']}</b><span>reprovados</span></div><div class="kpi"><b>{q['classes'][0]}/{q['classes'][1]}</b><span>classes cobertas</span></div>
<div class="kpi"><b>{q['pontos'][0]}/{q['pontos'][1]}</b><span>pontos de fronteira cobertos</span></div></div>
<h3>Especificação usada como oráculo</h3>{f"<p>{esc(SPEC['enunciado'])}</p>" if SPEC['enunciado'].strip() else ""}
<ol>{''.join(f'<li>{esc(r["formal"])}</li>' for r in REGRAS)}</ol>
<h3>Cálculo do Épsilon (ε)</h3><p>{esc(d['justificativa'])}</p>{base("epsilon")}
{html_epsilon(SPEC)}{tabela(tabela_epsilon(SPEC))}
<h3>Réguas da fronteira</h3>
{''.join(f"<p class='nota'>{esc(t)}</p>{svg}" for t, svg in d['reguas']) or "<p>A especificação não define faixa válida; não há fronteira.</p>"}
<h3>Pontos de fronteira</h3>{tabela(d['pontos'])}
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
<h3>Os operadores de mutação</h3>{html_operadores(a)}
<h3>Comparação entre suítes de teste</h3>{html_comparacao_suites(d['comparacao_suites'], COMPLETA) if d['comparacao_suites'] else ""}
<p>{esc(conclusao_das_suites(d['comparacao_suites'])) if d['comparacao_suites'] else ""}</p>
<h3>Mutantes, por operador (suíte completa)</h3>
{tabela(d['mutantes'])}

<h2 class="anexo">Anexo E. Validação: requisitos, rastreabilidade e suíte de testes</h2>
{base("validacao")}
<div class="kpis"><div class="kpi"><b>{d['rtm']['ida'][0]}/{d['rtm']['ida'][1]}</b><span>requisitos cobertos (ida)</span></div>
<div class="kpi"><b>{d['rtm']['volta'][0]}/{d['rtm']['volta'][1]}</b><span>testes rastreados (volta)</span></div></div>
<h3>Requisitos derivados da especificação</h3>{tabela(d['requisitos'])}
<h3>Casos de teste por fluxo</h3>{html_fluxos(d['casos_lista'])}{tabela(d['derivados'])}
<h3>Matriz de rastreabilidade (RTM)</h3>{html_bidirecional(d['rtm'])}{tabela(d['matriz_rtm'])}
<div class="kpis"><div class="kpi"><b>{v['ok']}/{v['total']}</b><span>conferências atendidas</span></div>
<div class="kpi"><b>{v['asercoes']}</b><span>asserções executadas</span></div><div class="kpi"><b>{v['passaram']}</b><span>passaram</span></div>
<div class="kpi"><b>{v['falharam']}</b><span>falharam (acusaram defeito)</span></div></div>
<p>{esc(TEXTO_UNIDADE)}</p>
<h3>Conferências da suíte</h3>{tabela(d['criterios_suite'])}
<h3>Asserções executadas pelo driver</h3>{tabela(d['asercoes'])}
{parecer}
<h2 class="anexo">Fontes</h2>
{html_fontes()}
<p class="rodape">Laudo gerado em {agora().strftime("%d/%m/%Y %H:%M")} ({fuso_horario()}) pelo TestingStudio. Método: a ferramenta interpreta
em Python a lógica da função 4GL carregada (IF, WHILE, LET, RETURN, comparações e aritmética); não é o compilador Informix.</p>
</div>
<script src="https://cdn.jsdelivr.net/npm/@viz-js/viz@3.31.0/dist/viz-global.js"></script>
<script>
 function imprimirSePedido() {{
   if (document.body.dataset.imprimir) {{ setTimeout(function () {{ window.print(); }}, 500); }}
 }}
 if (window.Viz) {{ Viz.instance().then(function (viz) {{
   var alvo = document.getElementById("gfc"); alvo.innerHTML = ""; alvo.appendChild(viz.renderSVGElement({dot}));
   imprimirSePedido();
 }}).catch(imprimirSePedido); }} else {{ imprimirSePedido(); }}
</script>
</body></html>"""


# ==========================================================================
# PASSO 4 - Gemini: teste da chave e parecer
# ==========================================================================
LIMITE_DE_PARECERES = 15     # por visita, quando a chave e a do servidor (protege a sua cota)


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


def secoes_para_o_gemini(fonte_funcao, d) -> dict:
    """Os dados de cada etapa, ja calculados pela ferramenta, em blocos que o Gemini le."""
    q, a, mut, m = d["qualidade"], d["analise"], d["mutacao"], d["analise"]["metricas"]
    cob, crit = a["cobertura"], a["criterios"]
    v, rtm = d["suite"], d["rtm"]
    conferencias = "\n".join(f"- {c['pergunta']} ({c['tecnico']}): {c['curto']}, "
                             f"{'atendido' if c['ok'] else 'pendente'}. {c['evidencia']}" for c in v["criterios"])
    achados = "\n".join(f"- {ACHADOS[c][0]}: casos {', '.join(ids)}. {ACHADOS[c][1]}"
                        for c, ids in q["achados"].items()) or "- nenhum"
    regras = "\n".join(f"REQ{i:02d}. {r['formal']}" for i, r in enumerate(REGRAS, 1))
    if SPEC.get("enunciado", "").strip():
        regras = f"Enunciado: {SPEC['enunciado'].strip()}\n" + regras
    vivos = d["mutantes"][d["mutantes"]["Estado"] == "Vivo"]
    suites_txt = "\n".join(f"- {l['nome']}: {l['casos']} casos, {l['Md']} de {l['Mt'] - l['Me']} mortos, MS = {texto_ms(l)}"
                           for l in d.get("comparacao_suites", [])) or "- (não calculado)"
    por_operador = "\n".join(
        f"- {o} ({motor.NOMES_DOS_OPERADORES[o][1]}): {sum(1 for m in d['analise']['mutantes'] if m['operador'] == o)} gerados, "
        f"{sum(1 for m in d['analise']['mutantes'] if m['operador'] == o and m['matam'])} mortos"
        for o in ORDEM_OPERADORES)
    por_fluxo = "\n".join(f"- {f}: {', '.join(c['id'] for c in d['casos_lista'] if fluxo_do_caso(c) == f) or 'nenhum'}"
                          for f in FLUXOS)
    return {
        "especificacao": f"<especificacao>\n{regras}\n</especificacao>",
        "funcao": f"<funcao_sob_teste>\n{fonte_funcao}\n</funcao_sob_teste>",
        "caixa_preta": f"""<caixa_preta>
{d['justificativa']}
calculo_do_epsilon_csv:
{tabela_epsilon(SPEC).to_csv(index=False)}
casos executados: {q['total']} | aprovados: {q['aprovados']} | reprovados: {q['reprovados']} | sem resposta definida: {q['sem_oraculo']}
classes de equivalência cobertas: {q['classes'][0]} de {q['classes'][1]}
pontos de fronteira cobertos: {q['pontos'][0]} de {q['pontos'][1]}
classes_csv:
{d['pce'].to_csv(index=False)}
pontos_de_fronteira_csv:
{d['pontos'].to_csv(index=False)}
achados:
{achados}
</caixa_preta>""",
        "caixa_branca": f"""<caixa_branca>
N = {m['N']} | E = {m['E']} | P = {m['P']} | R = {m['R']}
V(G) = E - N + 2 = {m['v_topologico']} | V(G) = P + 1 = {m['v_logico']} | V(G) = R = {m['v_espacial']}
Todos-Nós: {cob['Todos-Nós'][0]} de {cob['Todos-Nós'][1]} | Todas-Arestas: {cob['Todas-Arestas'][0]} de {cob['Todas-Arestas'][1]} | caminhos completos: {cob['Todos-Caminhos'][0]} de {cob['Todos-Caminhos'][1]}
nos_csv:
{d['nos'].to_csv(index=False)}
o_que_cada_caso_percorre_csv:
{d['execucoes'].to_csv(index=False)}
caminhos_csv:
{d['caminhos'].to_csv(index=False)}
</caixa_branca>""",
        "fluxo_mutacao": f"""<fluxo_de_dados>
{' | '.join(f"{nome}: {par[0]} de {par[1]}" for nome, par in crit.items())}
variaveis_csv:
{d['variaveis'].to_csv(index=False)}
pares_def_uso_csv:
{d['pares'].to_csv(index=False)}
</fluxo_de_dados>

<mutacao>
Mt = {mut['Mt']} | Md = {mut['Md']} | Me = {mut['Me']} | MS = {texto_ms(mut)}
por operador:
{por_operador}
mesmos mutantes contra suítes diferentes:
{suites_txt}
{conclusao_das_suites(d['comparacao_suites']) if d.get('comparacao_suites') else ''}
mutantes_vivos_csv:
{vivos.to_csv(index=False) if len(vivos) else 'nenhum'}
</mutacao>""",
        "validacao": f"""<validacao>
requisitos_csv:
{d['requisitos'].to_csv(index=False)}
rastreabilidade: ida (requisito -> teste) {rtm['ida'][0]} de {rtm['ida'][1]}; volta (teste -> requisito) {rtm['volta'][0]} de {rtm['volta'][1]}
casos por fluxo do caso de uso:
{por_fluxo}
casos_derivados_csv:
{d['derivados'].to_csv(index=False)}
conferências da suíte ({v['ok']} de {v['total']} atendidas):
{conferencias}
asserções: {v['asercoes']} executadas, {v['passaram']} passaram, {v['falharam']} falharam
</validacao>""",
        "achado": f"<achado_central>{d['achado']}</achado_central>",
        "casos": f"<casos_de_teste_csv>\n{d['casos'].to_csv(index=False)}\n</casos_de_teste_csv>",
        "referencias": "<referencias>\n" + "\n".join(f"- [{r['n']}] {r['texto']}" for r in REFERENCIAS)
                       + "\n</referencias>",
    }


ETAPAS = {
    "s1": {"titulo": "Sprint 1: caixa-preta", "curto": "caixa-preta",
           "secoes": ["especificacao", "funcao", "caixa_preta", "casos"],
           "pede": "1. As classes de equivalência e os pontos de fronteira cobrem bem a especificação?\n"
                   "2. O cálculo do Épsilon e a escolha do Off-Point estão justificados?\n"
                   "3. Que defeitos os testes revelaram e qual a correção no fonte?\n"
                   "4. Que casos de teste ainda valeria acrescentar?"},
    "s2": {"titulo": "Sprint 2: caixa-branca", "curto": "caixa-branca",
           "secoes": ["funcao", "caixa_branca"],
           "pede": "1. Leitura do grafo: nós, arestas, nós predicativos e regiões.\n"
                   "2. V(G) pelos três métodos e o que ele diz sobre o mínimo de testes.\n"
                   "3. Cobertura de nós, arestas e caminhos; caminhos não percorridos e possíveis infactíveis.\n"
                   "4. Recomendações."},
    "s3": {"titulo": "Sprint 3: fluxo de dados e mutação", "curto": "fluxo de dados e mutação",
           "secoes": ["funcao", "fluxo_mutacao"],
           "pede": "1. Critérios de fluxo de dados atendidos e pares Def-Uso não exercitados.\n"
                   "2. Escore de mutação por operador (AOR, ROR, COR, LVR), mutantes vivos e quais parecem equivalentes.\n"
                   "3. A comparação entre suítes (completa, só PCE, só AVL, só caminho feliz): o que cada técnica "
                   "acrescenta e o que diz sobre a força da suíte.\n"
                   "4. Recomendações."},
    "s4": {"titulo": "Sprint 4: validação", "curto": "validação",
           "secoes": ["especificacao", "validacao", "casos"],
           "pede": "1. Os requisitos derivados da especificação estão completos e claros?\n"
                   "2. Os casos de teste cobrem o fluxo principal, os alternativos e os de exceção?\n"
                   "3. A matriz de rastreabilidade fecha nos dois sentidos? O que falta?\n"
                   "4. As conferências da suíte e as asserções permitem confiar no veredito?\n"
                   "5. Conclusão sobre a validação."},
}

REGRAS_DO_TEXTO = """Regras:
- Escreva em português do Brasil, em Markdown, com títulos curtos (###) e frases diretas.
- Use somente os dados abaixo, que já foram calculados pela ferramenta. Não invente números,
  casos, defeitos nem funcionalidades. Se um dado não estiver abaixo, diga que não foi medido.
- Cite números exatos (por exemplo, "7 de 19 testes").
- Ao citar literatura, use apenas as referências listadas, pelo número entre colchetes,
  sem inventar citações literais nem páginas."""


def montar_prompt_etapa(chave: str, fonte_funcao, d) -> str:
    etapa, secoes = ETAPAS[chave], secoes_para_o_gemini(fonte_funcao, d)
    dados = "\n\n".join(secoes[s] for s in etapa["secoes"] + ["referencias"])
    return f"""Você é um auditor de teste de software. Escreva o parecer da etapa "{etapa['titulo']}"
da análise da função {FUNCAO_ALVO} (arquivo {d['arquivo']}), com foco na QUALIDADE DO PRODUTO DE TESTE.
Tamanho: entre 200 e 350 palavras.

Responda, nesta ordem:
{etapa['pede']}

{REGRAS_DO_TEXTO}

{dados}"""


def montar_prompt_geral(fonte_funcao, d, pareceres: dict) -> str:
    secoes = secoes_para_o_gemini(fonte_funcao, d)
    anteriores = "\n\n".join(f"<parecer_da_etapa nome=\"{ETAPAS[k]['titulo']}\">\n{t}\n</parecer_da_etapa>"
                             for k, t in pareceres.items()) or "(nenhum parecer de etapa foi gerado ainda)"
    humanos = "\n\n".join(f"<parecer_do_profissional etapa=\"{k}\" veredito=\"{v['veredito']}\">\n{v['texto']}\n"
                           "</parecer_do_profissional>" for k, v in d.get("pareceres_prof", {}).items())
    if humanos:
        anteriores += "\n\n" + humanos
    return f"""Você é um auditor de teste de software. Escreva o PARECER GERAL da análise da função
{FUNCAO_ALVO} (arquivo {d['arquivo']}), juntando as quatro etapas: caixa-preta, caixa-branca,
fluxo de dados e mutação, e validação. Tamanho: entre 400 e 650 palavras.

Estrutura:
### Resumo para quem não é da área
4 a 6 linhas, sem termos técnicos: o programa faz o que promete? os testes são confiáveis?
### Veredito técnico
### O que cada etapa mostrou
Um parágrafo curto por etapa.
### Defeitos encontrados e correção
### Limites desta análise
### Recomendações

{REGRAS_DO_TEXTO}
- Os pareceres de etapa abaixo (se houver) foram escritos antes; use-os como apoio, mas confira
  sempre com os números. Se houver parecer do profissional técnico, diga se você concorda e por quê.

{chr(10).join(secoes[s] for s in ["especificacao", "funcao", "caixa_preta", "caixa_branca", "fluxo_mutacao", "validacao", "achado", "referencias"])}

{anteriores}"""


# ==========================================================================
# PASSO 5 - Sprints 2, 3 e 4: tabelas e paineis (os calculos estao em motor.py)
# ==========================================================================
@st.cache_data(show_spinner=False, max_entries=64)
def analise_em_cache(parametros, corpo, linha, epsilon, casos, por_bloco, nome, versao_do_motor):
    """Guarda o resultado da analise: a pagina e reexecutada a cada clique e
    nao precisa refazer grafo, fluxo de dados e mutantes se nada mudou.
    A versao do motor faz parte da chave: resultado de um motor antigo nunca e reaproveitado."""
    return motor.analisar(list(parametros), corpo, linha, epsilon, list(casos), por_bloco, nome)


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


def _sem_coluna_vazia(df: pd.DataFrame, coluna: str = "Como cobrir") -> pd.DataFrame:
    """"Como cobrir" so tem texto quando algo ficou sem teste. Se tudo foi coberto, a coluna sai."""
    if coluna in df.columns and not df[coluna].astype(str).str.strip().any():
        return df.drop(columns=[coluna])
    return df


def tabela_caminhos(a) -> pd.DataFrame:
    return _sem_coluna_vazia(pd.DataFrame([{
        "Caminho completo": texto_caminho(c["nos"]),
        "Conjunto básico": "Sim" if c["basico"] else "",
        "Coberto por": ", ".join(c["casos"]) if c["casos"] else "nenhum caso",
        "Como cobrir": "" if c["casos"] else como_cobrir(c["sugestao"], a["sondagens"]),
    } for c in a["caminhos"]]))


def tabela_variaveis(a) -> pd.DataFrame:
    """Formato usual da tabela de pares DU: variavel, no de definicao, nos c-uso, arestas p-uso."""
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
    return _sem_coluna_vazia(pd.DataFrame(linhas))


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
        mostrar_tabela(tabela_nos(a))
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
    mostrar_tabela(tabela_execucoes(a))
    st.markdown("**Caminhos completos do grafo**")
    mostrar_tabela(tabela_caminhos(a))
    faltam = [x for x in a["arestas"] if not x["coberta"]]
    if faltam:
        st.markdown("**Arestas ainda não cobertas**")
        mostrar_tabela(pd.DataFrame([{
            "Aresta": f"({x['de']},{x['para']})" + (f" {x['rotulo']}" if x["rotulo"] else ""),
            "Como cobrir": como_cobrir(x["sugestao"], a["sondagens"])} for x in faltam]))


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
    mostrar_tabela(tabela_variaveis(a))
    st.caption("d: nó onde a variável recebe valor (parâmetros são definidos no nó de entrada). "
               "c-uso: uso em cálculo ou retorno, associado a um nó. "
               "p-uso: uso em decisão, associado às arestas que saem do nó.")
    st.markdown("**Pares Def-Uso (caminho livre de definição entre d e o uso)**")
    mostrar_tabela(tabela_pares(a))
    if a["uso_sem_definicao"]:
        st.warning("Uso sem definição que o alcance: " + ", ".join(
            f"{v} (linha {linha})" for v, linha in a["uso_sem_definicao"]) +
            ". A variável chega NULL a esse ponto.", icon=":material/warning:")
    if a["definicao_sem_uso"]:
        st.info("Definição que nenhum uso aproveita: " + ", ".join(
            f"{v} (nó {no})" for v, no in a["definicao_sem_uso"]) + ".", icon=":material/info:")


ORDEM_OPERADORES = ["AOR", "ROR", "COR", "LVR"]
COMPLETA = "Completa (PCE + AVL + extras)"
DESCRICAO_DAS_SUITES = {
    COMPLETA: "Todos os casos: as classes de equivalência, os pontos de fronteira e os testes extras.",
    "Somente PCE": "Um caso por classe de equivalência: um valor comum válido (Interior), um bem fora da "
                   "faixa (Exterior) e o campo em branco. Sem os pontos exatos da fronteira.",
    "Somente AVL": "Só os pontos exatos da fronteira: On-Point (no limite) e Off-Point (um ε além).",
    "Somente caminho feliz": "Só os casos do fluxo principal: valores comuns, em que tudo dá certo.",
    "Somente testes extras": "Só os casos digitados na aba Testes extras da Sprint 1.",
    "Personalizada": "Você escolhe os casos.",
}


def suites_de_teste(casos) -> dict:
    """Sub-suites prontas, como listas de ids de casos."""
    base = [c for c in casos if c["tecnica"] != "Extra"]
    suites = {
        COMPLETA: [c["id"] for c in casos],
        "Somente PCE": [c["id"] for c in base if c["rotulo"] in ("Interior", "Nulo") or c["rotulo"].startswith("Exterior")],
        "Somente AVL": [c["id"] for c in base if c["rotulo"].startswith(("On-Point", "Off-Point"))],
        "Somente caminho feliz": [c["id"] for c in casos if fluxo_do_caso(c) == "Fluxo principal"],
    }
    extras = [c["id"] for c in casos if c["tecnica"] == "Extra"]
    if extras:
        suites["Somente testes extras"] = extras
    return suites


def _numero_do_mutante(m) -> int:
    return int(m["id"][1:]) if m["id"][1:].isdigit() else 0


def mutantes_em_ordem(a):
    return sorted(a["mutantes"], key=lambda m: (ORDEM_OPERADORES.index(m["operador"])
                                                if m["operador"] in ORDEM_OPERADORES else 9,
                                                m["linha"], _numero_do_mutante(m)))


def resumo_mutacao(a, equivalentes=(), suite=None) -> dict:
    """Mt, Md, Me e o escore MS = Md / (Mt - Me) para uma suite (todos os casos, se None).
    'equivalentes' sao os ids dos mutantes vivos que o analista marcou como equivalentes."""
    escolhidos = None if suite is None else set(suite)
    mortos = sorted((m["id"] for m in a["mutantes"]
                     if (m["matam"] if escolhidos is None else set(m["matam"]) & escolhidos)),
                    key=lambda i: int(i[1:]) if i[1:].isdigit() else 0)
    total = len(a["mutantes"])
    me = sum(1 for m in a["mutantes"] if m["id"] not in mortos and m["id"] in equivalentes)
    return {"Mt": total, "Md": len(mortos), "Me": me, "vivos": total - len(mortos),
            "MS": motor.escore_de_mutacao(len(mortos), total, me), "mortos_ids": mortos,
            "equivalentes": sorted(e for e in equivalentes if e not in mortos)}


def texto_ms(resumo) -> str:
    return "sem mutantes" if resumo["MS"] is None else f"{resumo['MS']:.1f}%".replace(".", ",")


def tabela_mutantes(a, suite=None, equivalentes=()) -> pd.DataFrame:
    """Um mutante por linha, em ordem de operador, linha do fonte e numero."""
    escolhidos = None if suite is None else list(suite)
    linhas = []
    for m in mutantes_em_ordem(a):
        matam = m["matam"] if escolhidos is None else [c for c in escolhidos if c in m["matam"]]
        if matam:
            estado, analise = "Morto", ""
        elif m["id"] in equivalentes:
            estado, analise = "Equivalente", "Marcado pelo analista: se comporta igual ao original"
        else:
            estado = "Vivo"
            if m["matam"]:
                analise = f"A suíte completa mata com {', '.join(m['matam'][:3])}{'…' if len(m['matam']) > 3 else ''}"
            elif m["provavel_equivalente"]:
                analise = f"Provável equivalente: nenhuma das {a['sondagens']} entradas de sondagem distingue"
            else:
                analise = f"Mataria com a entrada {texto_entrada(m['sugestao'])}"
        sigla = m["operador"]
        linhas.append({"Mutante": m["id"], "Operador": f"{sigla} · {motor.NOMES_DOS_OPERADORES[sigla][1].lower()}",
                       "Linha": m["linha"], "Original": m["original"], "Mutante (alterado)": m["mutado"],
                       "Estado": estado, "Morto pelo caso": matam[0] if matam else "—",
                       "Casos que matam": f"{len(matam)} de {len(escolhidos) if escolhidos is not None else len(m['matam']) or 0}"
                       if escolhidos is not None else len(m["matam"]),
                       "Análise": analise})
    return pd.DataFrame(linhas)


def html_operadores(a) -> str:
    """Um quadro por operador: o que ele troca, um exemplo nesta funcao e quantos foram mortos."""
    quadros = []
    for sigla in ORDEM_OPERADORES:
        do_op = [m for m in mutantes_em_ordem(a) if m["operador"] == sigla]
        ingles, nome = motor.NOMES_DOS_OPERADORES[sigla]
        if do_op:
            mortos = sum(1 for m in do_op if m["matam"])
            ex = do_op[0]
            exemplo = (f'<code>{esc(ex["original"])}</code><span class="ts-seta">→</span>'
                       f'<code>{esc(ex["mutado"])}</code>')
            medida = (f'<div class="ts-medida"><b>{mortos} de {len(do_op)}</b><span>mortos pela suíte completa</span></div>'
                      f'{_medidor(mortos / len(do_op))}')
        else:
            exemplo = '<span class="ts-detalhe">Nada nesta função para este operador trocar.</span>'
            medida = '<div class="ts-medida"><b>0</b><span>mutantes</span></div>'
        quadros.append(f'<article class="ts-operador"><p class="ts-sigla">{sigla}</p><h3>{esc(nome)}</h3>'
                       f'<p class="ts-tecnico">{esc(ingles)}</p><p class="ts-texto">{esc(motor.OPERADORES[sigla].split(": ", 1)[1])}</p>'
                       f'<div class="ts-exemplo-mut"><small>Exemplo nesta função</small>{exemplo}</div>{medida}</article>')
    return '<div class="ts-operadores">' + "".join(quadros) + "</div>"


def comparar_suites(a, suites, equivalentes=()):
    """Escore de cada suite contra os mesmos mutantes: [{nome, casos, Md, Mt, Me, MS}]."""
    linhas = []
    for nome, ids in suites.items():
        r = resumo_mutacao(a, equivalentes, ids)
        linhas.append({"nome": nome, "casos": len(ids), **{k: r[k] for k in ("Mt", "Md", "Me", "MS", "vivos")},
                       "mortos_ids": r["mortos_ids"]})
    return linhas


def html_comparacao_suites(linhas, escolhida: str) -> str:
    partes = []
    for l in linhas:
        ms = l["MS"] or 0
        classe = "ok" if ms >= 100 else ("alerta" if ms >= 80 else "ruim")
        partes.append(f'<div class="ts-suite{" ts-suite-escolhida" if l["nome"] == escolhida else ""}">'
                      f'<div class="ts-suite-nome"><b>{esc(l["nome"])}</b><small>{l["casos"]} caso{"s" if l["casos"] != 1 else ""}</small></div>'
                      f'<div class="ts-barra ts-barra-{classe}"><span style="width:{max(0, min(100, ms)):.0f}%"></span></div>'
                      f'<div class="ts-suite-num"><b>{texto_ms(l) if l["casos"] else "—"}</b>'
                      f'<small>{l["Md"]} de {l["Mt"] - l["Me"]} mortos</small></div></div>')
    return '<div class="ts-suites">' + "".join(partes) + "</div>"


def conclusao_das_suites(linhas) -> str:
    """Uma frase simples: o que se perde testando so uma parte."""
    completa = next(l for l in linhas if l["nome"] == COMPLETA)
    frases = []
    for l in linhas:
        if l["nome"] == COMPLETA or not l["casos"]:
            continue
        perdidos = completa["Md"] - l["Md"]
        if perdidos > 0:
            frases.append(f"a suíte “{l['nome']}” ({l['casos']} casos) deixaria passar {perdidos} dos "
                          f"{completa['Md']} defeitos que a completa percebe")
    if not frases:
        return "Qualquer uma das suítes percebe os mesmos defeitos plantados que a suíte completa."
    return "Comparando com a suíte completa: " + "; ".join(frases) + "."


def painel_mutacao(a, chave: str, casos):
    """Sprint 3, parte 2: operadores, suites contra os mutantes e a tabela de mutantes.
    Devolve (resumo da suite completa, comparacao entre suites)."""
    if not a["mutantes"]:
        st.info("Esta função não tem operador, comparação ou variável para mutar.", icon=":material/info:")
        r = resumo_mutacao(a)
        return r, []
    suites = suites_de_teste(casos)
    vivos_na_completa = [m for m in mutantes_em_ordem(a) if not m["matam"]]

    st.subheader("Os operadores de mutação")
    st.html(html_operadores(a))
    st.caption("Cada mutante é uma cópia da função com uma única troca. Os estados possíveis: morto (algum teste "
               "deu resultado diferente do original), vivo (todos os testes passaram) e equivalente (a troca não "
               "muda o comportamento; nenhum teste consegue matá-lo).")

    st.subheader("Qual suíte enfrenta os mutantes")
    opcoes = list(suites) + ["Personalizada"]
    escolha = st.segmented_control("Suíte de testes", opcoes, default=COMPLETA, key=f"{chave}_suite",
                                   label_visibility="collapsed") or COMPLETA
    if escolha == "Personalizada":
        por_id = {c["id"]: c for c in casos}
        ids = st.multiselect("Casos da suíte personalizada", list(por_id), default=suites["Somente AVL"],
                             key=f"{chave}_personalizada",
                             format_func=lambda i: f"{i} · {por_id[i]['rotulo']} · {por_id[i]['alvo']}")
    else:
        ids = suites[escolha]
    st.caption(DESCRICAO_DAS_SUITES.get(escolha, "") + (f" Casos: {', '.join(ids)}." if ids else " Nenhum caso."))
    equivalentes = st.multiselect(
        "Mutantes vivos que você analisou e concluiu que são equivalentes", [m["id"] for m in vivos_na_completa],
        key=f"{chave}_equivalentes",
        format_func=lambda i: f"{i} · {next(m['mutado'] for m in a['mutantes'] if m['id'] == i)}",
        help="Um mutante equivalente se comporta igual ao original para qualquer entrada. Ele sai da conta do "
             "escore: MS = Md ÷ (Mt − Me).") if vivos_na_completa else []
    r = resumo_mutacao(a, equivalentes, ids)
    k = st.columns(6)
    k[0].metric("Casos na suíte", len(ids), border=True)
    k[1].metric("Gerados (Mt)", r["Mt"], border=True)
    k[2].metric("Mortos (Md)", r["Md"], border=True)
    k[3].metric("Vivos", r["vivos"] - r["Me"], border=True)
    k[4].metric("Equivalentes (Me)", r["Me"], border=True)
    k[5].metric("Escore (MS)", texto_ms(r), border=True)
    st.markdown(f"MS = Md ÷ (Mt − Me) × 100 = {r['Md']} ÷ ({r['Mt']} − {r['Me']}) × 100 = **{texto_ms(r)}**")
    vivos = [m for m in a["mutantes"] if m["id"] not in r["mortos_ids"] and m["id"] not in equivalentes]
    if not ids:
        st.warning("A suíte escolhida não tem casos.", icon=":material/rule:")
    elif not vivos:
        st.success("Esta suíte matou todos os mutantes (descontados os equivalentes).", icon=":material/check_circle:")
    else:
        mataveis = [m for m in vivos if m["matam"] or not m["provavel_equivalente"]]
        provaveis = [m for m in vivos if not m["matam"] and m["provavel_equivalente"]]
        if mataveis:
            st.warning(f"{len(mataveis)} mutante(s) sobrevivem a esta suíte, mas poderiam ser mortos: "
                       f"{', '.join(m['id'] for m in mataveis)}. A coluna Análise da tabela diz como.",
                       icon=":material/science:")
        if provaveis:
            st.info(f"{len(provaveis)} mutante(s) vivo(s) parecem equivalentes: {', '.join(m['id'] for m in provaveis)}. "
                    "Se a sua análise confirmar, marque-os no campo acima e o escore é recalculado.",
                    icon=":material/balance:")

    st.subheader("Comparação entre suítes")
    comparacao = comparar_suites(a, {**suites, **({"Personalizada": ids} if escolha == "Personalizada" else {})},
                                 equivalentes)
    st.html(html_comparacao_suites(comparacao, escolha))
    st.caption(conclusao_das_suites(comparacao))

    st.subheader("Mutantes, por operador")
    tabela = tabela_mutantes(a, ids, equivalentes)
    f1, f2 = st.columns([2, 1.3])
    presentes = [o for o in ORDEM_OPERADORES if any(m["operador"] == o for m in a["mutantes"])]
    filtro_op = f1.multiselect("Operadores", presentes, default=presentes, key=f"{chave}_filtro_op",
                               format_func=lambda o: f"{o} · {motor.NOMES_DOS_OPERADORES[o][1]}")
    filtro_estado = f2.segmented_control("Estado", ["Todos", "Mortos", "Vivos"], default="Todos",
                                         key=f"{chave}_filtro_estado") or "Todos"
    visivel = tabela[tabela["Operador"].str[:3].isin(filtro_op)]
    if filtro_estado == "Mortos":
        visivel = visivel[visivel["Estado"] == "Morto"]
    elif filtro_estado == "Vivos":
        visivel = visivel[visivel["Estado"] != "Morto"]
    mostrar_tabela(visivel)
    st.caption(f"{len(visivel)} de {len(tabela)} mutantes. Ordem: operador (AOR, ROR, COR, LVR), linha do fonte e "
               "número. 'Morto pelo caso' é o primeiro caso da suíte que deu resultado diferente do original.")
    return resumo_mutacao(a, equivalentes), comparacao


def achado_central(q, a, mut) -> str:
    """Frase que liga as tres tecnicas, calculada a partir dos resultados."""
    nos, arestas = a["cobertura"]["Todos-Nós"], a["cobertura"]["Todas-Arestas"]
    estrutural_total = nos[0] == nos[1] and arestas[0] == arestas[1]
    if q["reprovados"] and estrutural_total:
        return (f"A caixa-branca cobriu 100% dos nós e das arestas e o escore de mutação ficou em "
                f"{texto_ms(mut)}, e mesmo assim a caixa-preta reprovou {q['reprovados']} casos. "
                "O motivo é um requisito que não foi escrito no código: teste estrutural e mutação só "
                "enxergam o código que existe, e requisito omitido só aparece no teste funcional. "
                "É a ilusão do teste estrutural: cobertura total não prova que o requisito foi implementado.")
    if q["reprovados"]:
        return (f"A caixa-preta reprovou {q['reprovados']} casos e a cobertura estrutural ainda não é "
                f"total (nós: {porcento(nos)}, arestas: {porcento(arestas)}). Há defeito a corrigir e "
                "código ainda não exercitado.")
    if estrutural_total:
        return (f"As técnicas concordam: nenhum caso reprovado na caixa-preta, 100% dos nós e das "
                f"arestas cobertos e escore de mutação de {texto_ms(mut)}.")
    return (f"Nenhum caso reprovado na caixa-preta, mas a cobertura estrutural não é total "
            f"(nós: {porcento(nos)}, arestas: {porcento(arestas)}): falta exercitar parte do código.")


# ---- Sprint 4: requisitos, casos de teste por fluxo e rastreabilidade ---------
FLUXOS = ["Fluxo principal", "Fluxo alternativo", "Fluxo de exceção"]
EXPLICA_FLUXO = {
    "Fluxo principal": "O caminho feliz: valores comuns, tudo dá certo e a conta é feita.",
    "Fluxo alternativo": "Desvios aceitáveis: valor exatamente no limite ou campo em branco que a regra aceita. "
                         "O programa se adapta sem quebrar.",
    "Fluxo de exceção": "Bloqueios: valor fora da faixa (ou em branco, se a regra recusar). O programa deve "
                        "interromper e devolver o erro combinado.",
}
TEXTO_UNIDADE = (
    "Nível de teste: unidade. A função de cálculo é testada isolada do resto do sistema. A ferramenta faz o "
    "papel de driver: chama a função com os dados de cada teste e confere a resposta com uma asserção, cujo "
    "valor esperado vem da especificação. Não são necessários stubs, porque a função não chama outros módulos.")


def requisitos():
    """Os requisitos (REQ01, REQ02...) saem das regras da especificação, na mesma ordem."""
    return [{"id": f"REQ{i:02d}", **r} for i, r in enumerate(REGRAS, 1)]


def rastreio_do_caso(caso):
    """Requisitos que um caso de teste verifica. Sem resposta definida, o caso não verifica nenhum."""
    if caso["status"] == "Sem oráculo":
        return []
    return [r["id"] for r in requisitos() if casos_da_regra(r["chave"], [caso], SPEC)]


def fluxo_do_caso(caso) -> str:
    """Principal (caminho feliz), alternativo (limite aceito, branco aceito) ou exceção (bloqueio)."""
    params, valores = SPEC["params"], caso["entradas"]
    if any(cp.fora_da_faixa(p, v) for p, v in zip(params, valores)) or \
            (SPEC["nulo"] == "invalido" and any(v is None for v in valores)):
        return "Fluxo de exceção"
    if any(v is None for v in valores) or any(cp.ponto_de(p, v).startswith("On-Point") for p, v in zip(params, valores)):
        return "Fluxo alternativo"
    return "Fluxo principal"


def foco_do_caso(caso) -> str:
    texto = _descreve_entrada(caso, [p["nome"] for p in SPEC["params"]])
    return texto[:1].upper() + texto[1:] if texto else ""


def regra_do_caso(caso):
    """(numero, regra) do combinado que o caso verifica em primeiro lugar."""
    chave = cp.regra_do_caso(SPEC, caso["entradas"])
    return next((i, r) for i, r in enumerate(REGRAS, 1) if r["chave"] == chave)


def texto_asercao(caso) -> str:
    argumentos = ", ".join("None" if v is None else str(v) for v in caso["entradas"])
    return f"assert {FUNCAO_ALVO}({argumentos}) == {caso['esperado']}"


def _resultado(c) -> str:
    if c["status"] == "Aprovado":
        return "✓ Passou"
    if c["status"] == "Reprovado":
        return f"✕ Falhou: obteve {'erro' if c['erro'] else c['obtido']}"
    return "— sem resposta definida"


def tabela_asercoes(casos) -> pd.DataFrame:
    linhas = []
    for c in casos:
        numero, regra = regra_do_caso(c)
        linhas.append({"Teste": c["id"], "Fluxo": fluxo_do_caso(c),
                       "Regra verificada": f"REQ{numero:02d}. {regra['titulo']}",
                       "Asserção": texto_asercao(c) if c["status"] != "Sem oráculo" else "—",
                       "Resultado": _resultado(c)})
    return pd.DataFrame(linhas)


def rastreabilidade(casos) -> dict:
    """A matriz de rastreabilidade (RTM) e a cobertura nos dois sentidos."""
    reqs = requisitos()
    traco = {c["id"]: rastreio_do_caso(c) for c in casos}
    por_req = {r["id"]: [c for c in casos if r["id"] in traco[c["id"]]] for r in reqs}
    cobertos = [r for r in reqs if por_req[r["id"]]]
    rastreados = [c for c in casos if traco[c["id"]]]
    return {"requisitos": reqs, "traco": traco, "por_req": por_req,
            "ida": (len(cobertos), len(reqs)), "volta": (len(rastreados), len(casos)),
            "sem_teste": [r["id"] for r in reqs if not por_req[r["id"]]],
            "orfaos": [c["id"] for c in casos if not traco[c["id"]]]}


def tabela_requisitos(rtm) -> pd.DataFrame:
    linhas = []
    for r in rtm["requisitos"]:
        casos_r = rtm["por_req"][r["id"]]
        falhas = falhas_da_regra(r["chave"], casos_r)
        situacao = ("✕ Coberto, com falha" if falhas else "✓ Coberto e cumprido") if casos_r else "! Sem teste"
        linhas.append({"Requisito": r["id"], "O que pede": r["formal"], "Testes que o verificam": len(casos_r),
                       "Testes que falharam": ", ".join(falhas) or "—", "Situação": situacao})
    return pd.DataFrame(linhas)


def tabela_casos_derivados(casos, rtm) -> pd.DataFrame:
    return pd.DataFrame([{"Caso": c["id"], "Fluxo": fluxo_do_caso(c), "Foco": foco_do_caso(c),
                          "Rastreio": " → ".join(rtm["traco"][c["id"]]) or "nenhum requisito",
                          "Esperado": formato_br(c["esperado"]),
                          "Obtido": "erro" if c["erro"] else formato_br(c["obtido"]),
                          "Resultado": _resultado(c)} for c in casos])


def tabela_rtm(casos, rtm) -> pd.DataFrame:
    """Linhas = casos, colunas = requisitos (cabe na tela e no papel).
    ✓ verifica e passou; ✕ verifica e falhou; vazio = nao verifica. A ultima linha soma cada requisito."""
    linhas = []
    for c in casos:
        linha = {"Caso": c["id"]}
        for r in rtm["requisitos"]:
            linha[r["id"]] = ("✓" if c["status"] == "Aprovado" else "✕") if r["id"] in rtm["traco"][c["id"]] else ""
        linha["Fluxo"] = fluxo_do_caso(c)
        linhas.append(linha)
    linhas.append({"Caso": "Total", **{r["id"]: str(len(rtm["por_req"][r["id"]])) for r in rtm["requisitos"]},
                   "Fluxo": ""})
    return pd.DataFrame(linhas)


def html_fluxos(casos) -> str:
    """Tres quadros: quantos testes em cada fluxo do caso de uso e quantos passaram."""
    tipos = {"Fluxo principal": "ok", "Fluxo alternativo": "alerta", "Fluxo de exceção": "ruim"}
    quadros = []
    for fluxo in FLUXOS:
        doFluxo = [c for c in casos if fluxo_do_caso(c) == fluxo]
        julgados = [c for c in doFluxo if c["status"] != "Sem oráculo"]
        passaram = sum(c["status"] == "Aprovado" for c in julgados)
        if not doFluxo:
            selo = chip("Sem teste", "neutro")
        elif passaram == len(julgados) and julgados:
            selo = chip("Todos passaram", "ok")
        else:
            selo = chip(f"{len(julgados) - passaram} falharam" if julgados else "Sem resposta definida", "ruim"
                        if julgados else "neutro")
        quadros.append(f'<article class="ts-fluxo ts-fluxo-{tipos[fluxo]}"><div class="ts-estacao-topo">'
                       f'<span class="ts-passo">{esc(fluxo)}</span>{selo}</div>'
                       f'<p class="ts-texto">{esc(EXPLICA_FLUXO[fluxo])}</p><div class="ts-medida">'
                       f'<b>{len(doFluxo)}</b><span>testes; {passaram} passaram</span></div>'
                       f'<p class="ts-detalhe">{esc(", ".join(c["id"] for c in doFluxo)) or "nenhum"}</p></article>')
    return '<div class="ts-fluxos">' + "".join(quadros) + "</div>"


def html_bidirecional(rtm) -> str:
    """As duas perguntas da rastreabilidade bidirecional, com a resposta desta analise."""
    (ci, ti), (cv, tv) = rtm["ida"], rtm["volta"]
    ida_ok, volta_ok = ci == ti, cv == tv
    ida = (f"Sim: os {ti} requisitos têm pelo menos um teste." if ida_ok else
           f"Não: {', '.join(rtm['sem_teste'])} ainda não tem teste.")
    volta = (f"Sim: os {tv} testes verificam algum requisito." if volta_ok else
             f"Não: {len(rtm['orfaos'])} teste(s) sem resposta definida na especificação "
             f"({', '.join(rtm['orfaos'][:8])}{'…' if len(rtm['orfaos']) > 8 else ''}).")
    blocos = []
    for titulo, sentido, (a, b), ok, texto in (
            ("Tudo o que foi pedido foi testado?", "Ida: requisito → teste", (ci, ti), ida_ok, ida),
            ("Tudo o que foi testado foi pedido?", "Volta: teste → requisito", (cv, tv), volta_ok, volta)):
        blocos.append(f'<article class="ts-cartao"><span class="ts-passo">{esc(sentido)}</span><h3>{esc(titulo)}</h3>'
                      f'<div class="ts-medida"><b>{a} de {b}</b><span>{"requisitos cobertos" if "Ida" in sentido else "testes rastreados"}</span></div>'
                      f'{_medidor(a / b if b else 0)}<p class="ts-detalhe">{chip("Atendido", "ok") if ok else chip("Pendente", "alerta")} {esc(texto)}</p></article>')
    return f'<div class="ts-duas">{"".join(blocos)}</div>'


def validar_suite(casos, casos_base, programa, epsilon, qualidade, analise, mutacao, rtm) -> dict:
    """Sprint 4: antes do veredito, confere se a propria suite e confiavel."""
    q, cob = qualidade, analise["cobertura"]
    nos, arestas, usos = cob["Todos-Nós"], cob["Todas-Arestas"], analise["criterios"]["Todos-Usos"]
    por_fluxo = {f: sum(fluxo_do_caso(c) == f for c in casos) for f in FLUXOS}
    comuns = [p["comum"] for p in SPEC["params"]]
    isolados = sum(sum(v != comum for v, comum in zip(c["entradas"], comuns)) <= 1 for c in casos_base)
    repetidos = 0
    for c in casos:                                   # segunda execucao de toda a suite
        r = motor.executar_funcao(programa, c["entradas"], epsilon)
        repetidos += r["valor"] == c["obtido"] and r["erro"] == c["erro"]
    com_oraculo = q["total"] - q["sem_oraculo"]
    ms = mutacao["MS"]
    (ci, ti), (cv, tv) = rtm["ida"], rtm["volta"]
    criterios = [
        {"pergunta": "As respostas certas vêm da regra, e não do código?",
         "tecnico": "Oráculo independente da implementação", "ok": q["sem_oraculo"] == 0,
         "curto": f"{com_oraculo} de {q['total']}",
         "evidencia": f"O esperado é calculado só pela especificação. {com_oraculo} de {q['total']} "
                      "testes têm resposta esperada definida."},
        {"pergunta": "Tudo o que foi pedido foi testado?",
         "tecnico": "Rastreabilidade de ida (requisito → teste)", "ok": ci == ti and ti > 1,
         "curto": f"{ci} de {ti} requisitos",
         "evidencia": "Testes por requisito: " + "; ".join(
             f"{r['id']}: {len(rtm['por_req'][r['id']])}" for r in rtm["requisitos"]) + "."
             + ("" if ti > 1 else " A especificação ainda não tem as regras do resultado.")},
        {"pergunta": "Tudo o que foi testado foi pedido?",
         "tecnico": "Rastreabilidade de volta (teste → requisito)", "ok": cv == tv,
         "curto": f"{cv} de {tv} testes",
         "evidencia": "Todo teste verifica algum requisito." if cv == tv else
                      f"Testes sem requisito correspondente: {', '.join(rtm['orfaos'])}."},
        {"pergunta": "Entraram o fluxo principal, os alternativos e os de exceção?",
         "tecnico": "Fluxos do caso de uso", "ok": all(por_fluxo.values()),
         "curto": f"{sum(1 for n in por_fluxo.values() if n)} de {len(FLUXOS)} fluxos",
         "evidencia": "; ".join(f"{f}: {n} testes" for f, n in por_fluxo.items()) + "."},
        {"pergunta": "Todo grupo de valores e toda fronteira tiveram teste?",
         "tecnico": "Critérios da PCE e da AVL",
         "ok": q["classes"][0] == q["classes"][1] and q["pontos"][0] == q["pontos"][1],
         "curto": f"{q['classes'][0] + q['pontos'][0]} de {q['classes'][1] + q['pontos'][1]}",
         "evidencia": f"Classes de equivalência: {q['classes'][0]} de {q['classes'][1]}. Pontos de fronteira: "
                      f"{q['pontos'][0]} de {q['pontos'][1]}."},
        {"pergunta": "Cada teste muda um valor só?",
         "tecnico": "Isolamento da causa", "ok": isolados == len(casos_base),
         "curto": f"{isolados} de {len(casos_base)}",
         "evidencia": "Na suíte planejada, cada teste altera um único parâmetro e mantém os outros no valor "
                      "comum. Se falhar, já se sabe qual valor causou a falha."},
        {"pergunta": "Os testes passaram por todo o código?",
         "tecnico": "Todos-Nós e Todas-Arestas", "ok": nos[0] == nos[1] and arestas[0] == arestas[1],
         "curto": porcento(nos) if porcento(nos) == porcento(arestas) else f"{porcento(nos)} e {porcento(arestas)}",
         "evidencia": f"Nós: {nos[0]} de {nos[1]}. Arestas: {arestas[0]} de {arestas[1]}."},
        {"pergunta": "Os testes acompanharam todos os dados?",
         "tecnico": "Todos-Usos (pares Def-Uso)", "ok": usos[0] == usos[1],
         "curto": f"{usos[0]} de {usos[1]}", "evidencia": f"{usos[0]} de {usos[1]} pares Def-Uso exercitados."},
        {"pergunta": "Os testes percebem defeitos plantados?",
         "tecnico": "Escore de mutação (MS)", "ok": ms is not None and ms >= 100,
         "curto": texto_ms(mutacao),
         "evidencia": f"{mutacao['Md']} de {mutacao['Mt'] - mutacao['Me']} mutantes mortos."},
        {"pergunta": "Repetindo os testes, o resultado é o mesmo?",
         "tecnico": "Repetibilidade", "ok": repetidos == len(casos),
         "curto": f"{repetidos} de {len(casos)}",
         "evidencia": f"A suíte foi executada duas vezes; {repetidos} de {len(casos)} testes deram exatamente "
                      "o mesmo resultado."},
    ]
    return {"criterios": criterios, "ok": sum(c["ok"] for c in criterios), "total": len(criterios),
            "asercoes": com_oraculo, "passaram": q["aprovados"], "falharam": q["reprovados"]}


def tabela_criterios_suite(suite) -> pd.DataFrame:
    return pd.DataFrame([{"Pergunta": c["pergunta"], "Critério técnico": c["tecnico"], "Medida": c["curto"],
                          "Situação": "✓ Atendido" if c["ok"] else "! Pendente", "Evidência": c["evidencia"]}
                         for c in suite["criterios"]])


def script_de_testes(casos, arquivo: str) -> str:
    """Os mesmos testes como arquivo Python: roda com pytest ou com python puro."""
    linhas = []
    for c in casos:
        if c["status"] == "Sem oráculo":
            continue
        entradas = ", ".join("None" if v is None else f'D("{v}")' for v in c["entradas"])
        numero, regra = regra_do_caso(c)
        linhas.append(f'    ("{c["id"]}", "Regra {numero}: {regra["titulo"]}", ({entradas}), '
                      f'D("{c["esperado"]}")),')
    casos_txt = "\n".join(linhas)
    return f'''"""
Testes de unidade de {FUNCAO_ALVO}, gerados pelo TestingStudio.

O resultado esperado de cada teste vem da especificacao (oraculo), nunca do codigo.
Este arquivo e o driver: le o fonte 4GL, chama a funcao e confere cada assercao.

Como rodar: deixe este arquivo na pasta principal do TestingStudio (onde fica o
app.py), junto do {arquivo}, e use um dos comandos:
    python test_{FUNCAO_ALVO}.py
    python -m pytest -v test_{FUNCAO_ALVO}.py
"""
from decimal import Decimal as D
from pathlib import Path

try:
    from nucleo import motor      # na pasta principal do TestingStudio
except ImportError:
    import motor                  # ao lado do motor.py

ARQUIVO = Path(__file__).with_name({arquivo!r})
FUNCAO = {FUNCAO_ALVO!r}

# (teste, regra verificada, entradas, esperado pela especificacao)
CASOS = [
{casos_txt}
]


def _ler_fonte():
    dados = ARQUIVO.read_bytes()
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return dados.decode(codificacao)
        except UnicodeDecodeError:
            pass


def _unidade():
    funcao = motor.localizar_funcao(_ler_fonte(), FUNCAO)
    assert funcao is not None, f"FUNCTION {{FUNCAO}} nao encontrada em {{ARQUIVO.name}}"
    programa = motor.compilar_funcao(funcao["parametros"], funcao["corpo"], funcao["linha"], FUNCAO)
    return programa, motor.epsilon_do_resultado(programa)


UNIDADE = _unidade()

try:
    import pytest
    _parametrizar = pytest.mark.parametrize("teste, regra, entradas, esperado", CASOS,
                                            ids=[c[0] for c in CASOS])
except ImportError:
    def _parametrizar(funcao):
        return funcao


@_parametrizar
def test_{FUNCAO_ALVO}(teste, regra, entradas, esperado):
    programa, epsilon = UNIDADE
    r = motor.executar_funcao(programa, list(entradas), epsilon)
    assert r["erro"] is None, f"{{teste}} | {{regra}} | a funcao parou com erro: {{r['erro']}}"
    assert r["valor"] == esperado, f"{{teste}} | {{regra}} | esperado {{esperado}}, obtido {{r['valor']}}"


if __name__ == "__main__":
    falhas = 0
    for caso in CASOS:
        try:
            test_{FUNCAO_ALVO}(*caso)
            print(f"OK      {{caso[0]}}")
        except AssertionError as erro:
            falhas += 1
            print(f"FALHOU  {{erro}}")
    print(f"\\n{{len(CASOS) - falhas}} de {{len(CASOS)}} testes passaram.")
    raise SystemExit(1 if falhas else 0)
'''


GRANULARIDADES = ["Blocos indivisíveis (definição formal)", "Um nó por comando"]
# ==========================================================================
# PDF: o conteudo de cada aba, em blocos (desenhados por relatorio_pdf.py)
# ==========================================================================
ABAS = ["Laudo", "Programa e especificação", "Sprint 1: caixa-preta", "Sprint 2: caixa-branca",
        "Sprint 3: dados e mutação", "Sprint 4: validação", "Parecer geral", "Fontes"]
CHAVE_DA_ABA = {"Sprint 1: caixa-preta": "s1", "Sprint 2: caixa-branca": "s2",
                "Sprint 3: dados e mutação": "s3", "Sprint 4: validação": "s4", "Parecer geral": "geral"}


def _assinatura_prof(dados) -> str:
    return " · ".join(x for x in (dados["nome"] or "Profissional não identificado", dados["funcao"], dados["quando"]) if x)


def blocos_de_parecer(d, chave: str, titulo: str = "Pareceres"):
    prof, ia = d["pareceres_prof"].get(chave), d["pareceres"].get(chave)
    if not (prof or ia):
        return []
    blocos = [("h2", titulo)]
    if prof:
        blocos.append(("parecer", "Parecer do profissional técnico", prof["veredito"], prof["texto"], _assinatura_prof(prof)))
    if ia:
        blocos.append(("ia", "Parecer escrito com IA (Gemini)", ia["texto"], f"Modelo {ia['modelo']} · {ia['quando']}"))
    return blocos


def tabela_matriz(casos, spec) -> pd.DataFrame:
    """A matriz parametro x ponto da Sprint 1, como tabela."""
    colunas = []
    for p in spec["params"]:
        for ponto in cp.pontos_do_parametro(p):
            if ponto["rotulo"] not in colunas:
                colunas.append(ponto["rotulo"])
    colunas.append("Nulo")
    linhas = []
    for p in spec["params"]:
        existentes = {x["rotulo"] for x in cp.pontos_do_parametro(p)} | {"Nulo"}
        linha = {"Parâmetro": p["nome"]}
        for coluna in colunas:
            caso = next((c for c in casos if c["alvo"] == p["nome"] and c["rotulo"] == coluna), None)
            if coluna not in existentes:
                linha[coluna] = "não se aplica"
            elif caso is None:
                linha[coluna] = "não testado"
            else:
                linha[coluna] = f"{'✓' if caso['status'] == 'Aprovado' else ('✕' if caso['status'] == 'Reprovado' else '–')} {caso['id']}"
        linhas.append(linha)
    return pd.DataFrame(linhas)


def _codigo_numerado(texto: str, primeira: int) -> str:
    return "\n".join(f"{n:>4}  {l}" for n, l in enumerate(texto.split("\n"), start=primeira))


def blocos_laudo(d):
    v = veredito_dados(d)
    marca = {"ok": "✓", "ruim": "✕", "alerta": "!", "neutro": "–"}
    blocos = [("h2", "Veredito"), ("p", f"{marca[v['selo'][1]]} {v['selo'][0]}. {v['titulo']}"), ("p", v["texto"]),
              ("metricas", [(r, str(x)) for r, x in v["fatos"]])]
    regras = []
    for i, (regra, (verificada, falhas)) in enumerate(zip(REGRAS, situacao_das_regras(d)), 1):
        situacao = (f"✕ Não cumprida em {len(falhas)} teste{'s' if len(falhas) > 1 else ''}" if falhas
                    else ("✓ Cumprida" if verificada else "! Sem teste"))
        regras.append({"Requisito": f"REQ{i:02d}", "Regra": regra["titulo"], "Detalhe": regra["detalhe"],
                       "Testes": verificada, "Situação": situacao})
    blocos += [("h2", "O combinado, regra por regra"),
               ("nota", "O que a especificação diz que a função deve fazer, e se ela cumpriu cada regra nos testes."),
               ("tabela", pd.DataFrame(regras)), ("h2", "Como o programa foi testado"),
               ("nota", "Quatro conferências independentes; cada uma responde a uma pergunta diferente sobre a qualidade.")]
    for passo, titulo, tecnico, texto, numero, rotulo, _, detalhe, selo in estacoes_dados(d):
        blocos += [("h3", f"{passo}: {titulo}"), ("nota", tecnico), ("p", texto),
                   ("p", f"Resultado: {numero} {rotulo}. {marca[selo[1]]} {selo[0]}. {detalhe}")]
    caso = caso_exemplar(d)
    if caso is not None:
        obtido = "erro" if caso["erro"] else formato_br(caso["obtido"])
        blocos += [("h2", "O defeito, em um exemplo"),
                   ("metricas", [("O teste enviou", texto_entrada(caso["entradas"])),
                                 ("O combinado manda", formato_br(caso["esperado"])), ("O programa respondeu", obtido)]),
                   ("p", f"Entrada: {_descreve_entrada(caso, d['parametros'])}. Esperado: {_o_que_manda(caso)}. "
                         f"{ACHADOS[caso['achado']][1]}")]
        conserto = cp.condicao_que_falta(SPEC)
        if caso["achado"] == "INVALIDO_ACEITO" and conserto:
            blocos += [("p", "Como corrigir: antes da conta, incluir a verificação que falta:"), ("codigo", conserto)]
    s = d["suite"]
    blocos += [("h2", "Por que confiar nestes testes"),
               ("metricas", [("Conferências dos próprios testes atendidas", f"{s['ok']}/{s['total']}")]),
               ("tabela", pd.DataFrame([{"Pergunta": c["pergunta"], "Medida": c["curto"],
                                         "Situação": "✓ Atendido" if c["ok"] else "! Pendente"} for c in s["criterios"]])),
               ("p", "Quem decide o que é certo: a resposta esperada de cada teste vem da especificação, e não do "
                     "próprio código. Assim o programa nunca é comparado com ele mesmo.")]
    blocos += blocos_de_parecer(d, "geral", "Pareceres")
    blocos += [("h2", "O que este laudo não cobre")] + [("p", f"{t} {x}") for t, x in itens_dos_limites()]
    blocos += [("h2", "Glossário"), ("tabela", pd.DataFrame([{"Termo": t, "Significado": x} for t, x in GLOSSARIO]))]
    return blocos


def blocos_programa(d):
    blocos = [("h2", "Origem dos dados"), ("tabela", d["origem"]), ("h2", "Unidade sob teste"),
              ("codigo", _codigo_numerado(d["texto_funcao"], d["linha_funcao"])),
              ("nota", "O número à esquerda é a linha no arquivo; é o mesmo usado nos nós do grafo.")]
    if len(d["descartadas"]):
        blocos += [("h3", "Funções do arquivo que ficam de fora"), ("tabela", d["descartadas"])]
    blocos += [("h2", "Especificação (de onde vem a resposta certa)")]
    if SPEC["enunciado"]:
        blocos.append(("p", SPEC["enunciado"]))
    blocos += [("tabela", pd.DataFrame([{"Requisito": f"REQ{i:02d}", "Regra": r["formal"]} for i, r in enumerate(REGRAS, 1)])),
               ("h3", "Faixa válida e valores usados nos testes"),
               ("tabela", pd.DataFrame([{"Parâmetro": p["nome"], "Tipo": p["tipo"]["rotulo"],
                                         "Mínimo válido": formato_br(p["minimo"]) if p["minimo"] is not None else "—",
                                         "Máximo válido": formato_br(p["maximo"]) if p["maximo"] is not None else "—",
                                         "Valor comum": formato_br(p["comum"]), "Valor interior": formato_br(p["interior"])}
                                        for p in SPEC["params"]])),
               ("p", f"Valor em branco (NULL): {cp.NULO_OPCOES[SPEC['nulo']]}. Resposta para valor inválido: "
                     f"{formato_br(SPEC['retorno_invalido']) if SPEC['retorno_invalido'] is not None else 'não definida'}."),
               ("h2", "Tipos de dado e Épsilon"), ("tabela", tabela_epsilon(SPEC)), ("p", d["justificativa"])]
    return blocos


def blocos_sprint1(d):
    q = d["qualidade"]
    blocos = [("metricas", [("Casos", str(q["total"])), ("Aprovados", str(q["aprovados"])),
                            ("Reprovados", str(q["reprovados"])), ("Classes", f"{q['classes'][0]}/{q['classes'][1]}"),
                            ("Fronteiras", f"{q['pontos'][0]}/{q['pontos'][1]}"), ("Defeitos", str(len(q["achados"])))])]
    for codigo, ids in q["achados"].items():
        blocos.append(("p", f"✕ {ACHADOS[codigo][0]}: {len(ids)} casos ({', '.join(ids)}). {ACHADOS[codigo][1]}"))
    blocos += [("h2", "Cálculo do Épsilon (ε)"), ("p", d["justificativa"]), ("tabela", tabela_epsilon(SPEC)),
               ("h2", "Especificação usada como oráculo")]
    blocos += [("p", f"REQ{i:02d}. {r['formal']}") for i, r in enumerate(REGRAS, 1)]
    blocos += [("h2", "Classes de equivalência (PCE)"), ("tabela", d["pce"]),
               ("h2", "Pontos de fronteira (AVL)"), ("tabela", d["pontos"])]
    for titulo, dados in dados_das_reguas(SPEC):
        blocos += [("h3", f"Régua: {titulo}"), ("regua", dados)]
    blocos += [("h2", "Cobertura da suíte planejada"), ("tabela", tabela_matriz(d["casos_base"], SPEC)),
               ("nota", "Cada célula é um caso: um parâmetro recebe o valor da coluna e os outros ficam no valor comum."),
               ("h2", "Casos de teste"), ("tabela", d["casos"].drop(columns=["Técnica"], errors="ignore")),
               ("nota", "Esperado: calculado pela especificação. Obtido: resultado da execução da função.")]
    return blocos + blocos_de_parecer(d, "s1")


def blocos_sprint2(d):
    a, m = d["analise"], d["analise"]["metricas"]
    cob = a["cobertura"]
    blocos = [("metricas", [("Nós (N)", str(m["N"])), ("Arestas (E)", str(m["E"])), ("Predicativos (P)", str(m["P"])),
                            ("Regiões (R)", str(m["R"])), ("V(G)", str(m["V"]))]),
              ("p", f"Método 1, topológico: V(G) = E − N + 2 = {m['E']} − {m['N']} + 2 = {m['v_topologico']}"),
              ("p", f"Método 2, lógico: V(G) = P + 1 = {m['P']} + 1 = {m['v_logico']}"),
              ("p", f"Método 3, espacial: V(G) = R = {m['regioes_internas']} internas + 1 externa = {m['v_espacial']}"),
              ("h2", "Grafo de fluxo de controle"),
              ("grafo", a["grafo"], set(a["nos_cobertos"]), set(a["arestas_cobertas"])),
              ("nota", "Círculo = trecho de comandos; losango = decisão; círculo duplo = fim; seta para a direita e "
                       "para cima = volta de laço. Tracejado laranja = não percorrido pelos testes."),
              ("tabela", d["nos"]), ("h2", "Cobertura"),
              ("metricas", [("Todos-Nós", f"{porcento(cob['Todos-Nós'])} ({cob['Todos-Nós'][0]} de {cob['Todos-Nós'][1]})"),
                            ("Todas-Arestas", f"{porcento(cob['Todas-Arestas'])} ({cob['Todas-Arestas'][0]} de {cob['Todas-Arestas'][1]})"),
                            ("Caminhos", f"{cob['Todos-Caminhos'][0]} de {cob['Todos-Caminhos'][1]}")]),
              ("h3", "O que cada caso percorre"), ("tabela", d["execucoes"]),
              ("h3", "Caminhos completos"), ("tabela", d["caminhos"])]
    return blocos + blocos_de_parecer(d, "s2")


def blocos_sprint3(d):
    a, mut = d["analise"], d["mutacao"]
    blocos = [("h2", "Fluxo de dados (pares Def-Uso)"),
              ("metricas", [(nome, f"{porcento(par)} ({par[0]} de {par[1]})") for nome, par in a["criterios"].items()]),
              ("tabela", d["variaveis"]), ("h3", "Pares Def-Uso"), ("tabela", d["pares"]),
              ("h2", "Teste de mutação"),
              ("metricas", [("Gerados (Mt)", str(mut["Mt"])), ("Mortos (Md)", str(mut["Md"])),
                            ("Equivalentes (Me)", str(mut["Me"])), ("Escore (MS)", texto_ms(mut))]),
              ("p", f"MS = Md ÷ (Mt − Me) × 100 = {mut['Md']} ÷ ({mut['Mt']} − {mut['Me']}) × 100 = {texto_ms(mut)}"),
              ("h3", "Os operadores de mutação")]
    operadores = []
    for sigla in ORDEM_OPERADORES:
        do_op = [m for m in mutantes_em_ordem(a) if m["operador"] == sigla]
        operadores.append({"Operador": sigla, "Nome": motor.NOMES_DOS_OPERADORES[sigla][1],
                           "O que troca": motor.OPERADORES[sigla].split(": ", 1)[1],
                           "Exemplo nesta função": f"{do_op[0]['original']}  →  {do_op[0]['mutado']}" if do_op else "—",
                           "Gerados": len(do_op), "Mortos": sum(1 for m in do_op if m["matam"])})
    blocos.append(("tabela", pd.DataFrame(operadores)))
    if d["comparacao_suites"]:
        blocos += [("h3", "Comparação entre suítes de teste"),
                   ("barras", [(l["nome"], l["casos"], l["MS"], l["Md"], l["Mt"] - l["Me"]) for l in d["comparacao_suites"]]),
                   ("nota", conclusao_das_suites(d["comparacao_suites"]))]
    blocos += [("h3", "Mutantes, por operador (suíte completa)"), ("tabela", d["mutantes"])]
    return blocos + blocos_de_parecer(d, "s3")


def blocos_sprint4(d):
    s, rtm = d["suite"], d["rtm"]
    casos = d["casos_lista"]
    blocos = [("metricas", [("Requisitos cobertos", f"{rtm['ida'][0]} de {rtm['ida'][1]}"),
                            ("Testes rastreados", f"{rtm['volta'][0]} de {rtm['volta'][1]}"),
                            ("Conferências da suíte", f"{s['ok']} de {s['total']}"),
                            ("Asserções que falharam", f"{s['falharam']} de {s['asercoes']}")]),
              ("h2", "Requisitos derivados da especificação"), ("tabela", d["requisitos"]),
              ("h2", "Casos de teste por fluxo")]
    fluxos = []
    for fluxo in FLUXOS:
        do_fluxo = [c for c in casos if fluxo_do_caso(c) == fluxo]
        fluxos.append({"Fluxo": fluxo, "O que é": EXPLICA_FLUXO[fluxo], "Testes": len(do_fluxo),
                       "Passaram": sum(c["status"] == "Aprovado" for c in do_fluxo),
                       "Casos": ", ".join(c["id"] for c in do_fluxo) or "nenhum"})
    blocos += [("tabela", pd.DataFrame(fluxos)), ("tabela", d["derivados"]),
               ("h2", "Matriz de rastreabilidade (RTM)"),
               ("p", f"Tudo o que foi pedido foi testado? {rtm['ida'][0]} de {rtm['ida'][1]} requisitos têm teste."
                     + (f" Sem teste: {', '.join(rtm['sem_teste'])}." if rtm["sem_teste"] else "")),
               ("p", f"Tudo o que foi testado foi pedido? {rtm['volta'][0]} de {rtm['volta'][1]} testes verificam "
                     "algum requisito." + (f" Sem requisito: {', '.join(rtm['orfaos'])}." if rtm["orfaos"] else ""))]
    blocos += [("tabela", d["matriz_rtm"]),
               ("nota", "Linhas: casos de teste. Colunas: requisitos. ✓ = verifica e passou; ✕ = verifica e falhou."),
               ("h2", "Conferências da suíte"), ("tabela", d["criterios_suite"]),
               ("h2", "Asserções (teste de unidade)"), ("p", TEXTO_UNIDADE), ("tabela", d["asercoes"])]
    return blocos + blocos_de_parecer(d, "s4")


def blocos_parecer_geral(d):
    blocos = blocos_de_parecer(d, "geral", "Parecer geral")
    for chave, etapa in ETAPAS.items():
        blocos += blocos_de_parecer(d, chave, etapa["titulo"])
    return blocos or [("p", "Nenhum parecer foi escrito ou gerado ainda.")]


def blocos_fontes(d):
    return [("h2", "Referências"),
            ("tabela", pd.DataFrame([{"Nº": r["n"], "Referência": r["texto"], "Onde aparece": r["uso"],
                                      "Link": r["link"] or "—"} for r in REFERENCIAS])),
            ("h2", "Origem dos dados desta análise"), ("tabela", d["origem"])]


CONSTRUTORES = dict(zip(ABAS, [blocos_laudo, blocos_programa, blocos_sprint1, blocos_sprint2, blocos_sprint3,
                               blocos_sprint4, blocos_parecer_geral, blocos_fontes]))


def pdf_das_abas(d, abas, cor: str) -> bytes:
    from nucleo import relatorio_pdf
    ident = {"arquivo": d["arquivo"], "funcao": FUNCAO_ALVO, "tamanho": f"{d['linhas']} linhas",
             "quando": d["quando"][:16]}
    return relatorio_pdf.gerar_pdf([(nome, CONSTRUTORES[nome](d)) for nome in abas], ident, cor)


# ==========================================================================
# INTERFACE WEB (Streamlit)
# ==========================================================================
st.set_page_config(page_title="TestingStudio, laudo de qualidade", layout="wide",
                   initial_sidebar_state="collapsed")
def guardar_cor() -> None:
    """Lembra a cor no endereco da pagina, para ela continuar depois de recarregar."""
    st.query_params["cor"] = st.session_state.get("cor_destaque", "")
    if st.session_state.get("cor_destaque") == COR_PERSONALIZADA:
        st.query_params["hex"] = st.session_state.get("cor_personalizada", "#1a56b8").lstrip("#")
    else:
        st.query_params.pop("hex", None)


if "cor_destaque" not in st.session_state:
    pedida = st.query_params.get("cor", "")
    st.session_state["cor_destaque"] = pedida if pedida in CORES or pedida == COR_PERSONALIZADA else "Azul (padrão)"
if "cor_personalizada" not in st.session_state:
    st.session_state["cor_personalizada"] = "#" + st.query_params.get("hex", "1a56b8")[:6]
CORES_ATUAIS = paleta(st.session_state["cor_destaque"], st.session_state["cor_personalizada"])
CSS_COR_ATUAL = css_da_cor(CORES_ATUAIS)
MARCA = marca(_mistura(CORES_ATUAIS[0], CORES_ATUAIS[1], 0.45))
st.html(f"<style>{ESTILO_CSS}\n{CSS_COR_ATUAL}</style>")
st.html(html_topo())
if ARQUIVOS_DESATUALIZADOS:
    st.error("O servidor está sem a versão atual de " + " e ".join(ARQUIVOS_DESATUALIZADOS) + ". Envie de novo "
             "esses arquivos ao GitHub (junto do app.py) e, em share.streamlit.io, abra o menu do app e use "
             "Reboot app.", icon=":material/sync_problem:")
    st.stop()

def aplicar_pareceres_pendentes() -> None:
    """Pareceres carregados de um arquivo: entram antes de qualquer campo ser desenhado."""
    dados = st.session_state.pop("pareceres_pendentes", None)
    if not dados:
        return
    for k, v in dados.get("pareceres", {}).items():
        if k in ("s1", "s2", "s3", "s4", "geral") and isinstance(v, dict):
            st.session_state[f"prof::{k}::texto"] = str(v.get("texto", ""))
            st.session_state[f"prof::{k}::veredito"] = v.get("veredito") if v.get("veredito") in VEREDITOS else VEREDITOS[0]
            st.session_state[f"prof::{k}::quando"] = str(v.get("quando", ""))
    if dados.get("nome"):
        st.session_state["prof_nome"] = str(dados["nome"])
    if dados.get("funcao_do_profissional"):
        st.session_state["prof_funcao"] = str(dados["funcao_do_profissional"])


aplicar_pareceres_pendentes()

# ---- Barra lateral: chave do Gemini (so para os textos opcionais) ----------
chave_servidor = chave_do_servidor()
with st.sidebar:
    st.header("Aparência")
    st.selectbox("Cor de destaque", list(CORES) + [COR_PERSONALIZADA], key="cor_destaque", on_change=guardar_cor)
    if st.session_state["cor_destaque"] == COR_PERSONALIZADA:
        st.color_picker("Escolha a cor", key="cor_personalizada", on_change=guardar_cor)
    st.caption("Modo claro ou escuro: menu de três pontos, no canto superior direito: System, Light ou Dark.")
    st.divider()
    st.header("Profissional técnico")
    st.caption("Quem assina os pareceres técnicos (no fim de cada Sprint e na aba Parecer geral).")
    st.text_input("Nome", key="prof_nome", placeholder="ex.: Maria Souza")
    st.text_input("Função", key="prof_funcao", placeholder="ex.: Analista de testes")
    st.divider()
    st.header("Textos com IA")
    st.caption("O Gemini escreve os pareceres do fim de cada Sprint e da aba Parecer geral, a partir dos resultados. O laudo funciona sem ele.")
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
    exemplo = PASTA_EXEMPLOS / ARQUIVO_EXEMPLO
    if exemplo.exists():
        if st.button(f"Usar o arquivo de exemplo ({ARQUIVO_EXEMPLO})", icon=":material/description:"):
            registrar_fonte(ARQUIVO_EXEMPLO, exemplo.read_bytes(), "exemplo", ("exemplo",))
            st.rerun()
    st.stop()

original = st.session_state["fonte_original"]
identificacao = {"arquivo": st.session_state["fonte_nome"], "linhas": len(original.splitlines()),
                 "quando": st.session_state["fonte_quando"], "sha": st.session_state["fonte_sha"]}
lugar_da_faixa = st.empty()       # preenchida depois que a funcao e escolhida

aba_laudo, aba_programa, aba_s1, aba_s2, aba_s3, aba_s4, aba_parecer, aba_fontes = st.tabs(
    ["Laudo", "Programa e especificação", "Sprint 1: caixa-preta", "Sprint 2: caixa-branca",
     "Sprint 3: dados e mutação", "Sprint 4: validação", "Parecer geral", "Fontes"])
COR_DO_PDF = CORES_ATUAIS[0]
TOPO_DA_ABA = {}
for _nome, _aba in zip(ABAS[1:], [aba_programa, aba_s1, aba_s2, aba_s3, aba_s4, aba_parecer, aba_fontes]):
    with _aba:
        TOPO_DA_ABA[_nome] = st.container()

# ======================= PROGRAMA E ESPECIFICACAO ============================
with aba_programa:
    st.html(html_explica("O programa analisado",
                         "Este é o código que a ferramenta lê e executa. Você pode editar o texto aqui mesmo para "
                         "testar uma correção: todas as abas são recalculadas na hora, sem mexer no arquivo original."))
    fonte = st.text_area("Código-fonte", key="fonte_editado", height=320)
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

# Quais funcoes do arquivo podem ser testadas (recebem parametros numericos e o interpretador entende).
testaveis, descartadas = [], []
for candidata in motor.listar_funcoes(fonte):
    if not candidata["parametros"]:
        descartadas.append((candidata, "não recebe parâmetros: não há entrada para variar"))
        continue
    try:
        compilada = motor.compilar_funcao(candidata["parametros"], candidata["corpo"], candidata["linha"],
                                          candidata["nome"])
    except motor.Erro4GL as problema:
        descartadas.append((candidata, str(problema)))
        continue
    texto_nao_numerico = [p for p in compilada["parametros"] if not motor.tipo_da_variavel(compilada, p)["numerico"]]
    if texto_nao_numerico:
        descartadas.append((candidata, "parâmetro não numérico: " + ", ".join(texto_nao_numerico)))
        continue
    testaveis.append((candidata, compilada))


def tabela_descartadas() -> pd.DataFrame:
    return pd.DataFrame([{"Função": f["nome"], "Linha": f["linha"], "Por que fica de fora": motivo}
                         for f, motivo in descartadas])


if not testaveis:
    with aba_programa:
        st.error("Nenhuma função deste arquivo pode ser testada. A ferramenta testa uma função por vez, que "
                 "receba parâmetros numéricos e use IF, CASE, WHILE, FOR, LET e RETURN.", icon=":material/error:")
        if descartadas:
            mostrar_tabela(tabela_descartadas())
    st.stop()

nomes_testaveis = [f["nome"] for f, _ in testaveis]
with aba_programa:
    st.subheader("Função a testar")
    padrao = next((i for i, n in enumerate(nomes_testaveis) if n.lower() == "cad0001_calcula_valor"), 0)
    escolhida = st.selectbox(
        "Função a testar", nomes_testaveis, index=padrao, label_visibility="collapsed",
        key=f"funcao::{st.session_state['fonte_sha']}",
        help="O arquivo pode ter várias funções; o laudo examina uma por vez.")
    if descartadas:
        with st.expander(f"{len(descartadas)} função(ões) do arquivo ficam de fora dos testes",
                         icon=":material/info:"):
            mostrar_tabela(tabela_descartadas())
funcao, programa = testaveis[nomes_testaveis.index(escolhida)]
FUNCAO_ALVO = funcao["nome"]
with lugar_da_faixa:
    st.html(html_faixa(identificacao))
parametros, corpo, linha_funcao = programa["parametros"], funcao["corpo"], funcao["linha"]
epsilon = motor.epsilon_do_resultado(programa)
texto_funcao = f"FUNCTION {FUNCAO_ALVO}({', '.join(parametros)}){corpo}END FUNCTION"

# ---- especificacao (oraculo) ------------------------------------------------------
chave_spec = f"spec::{st.session_state['fonte_sha']}::{FUNCAO_ALVO}::{','.join(parametros)}"
exemplo_spec = cp.especificacao_de_exemplo(programa)
if chave_spec not in st.session_state:
    st.session_state[chave_spec] = exemplo_spec or cp.especificacao_inicial(programa)
    st.session_state[chave_spec + "::v"] = 0
base_spec, versao = st.session_state[chave_spec], st.session_state[chave_spec + "::v"]
for p in base_spec["params"]:                 # o tipo pode mudar se o DEFINE for editado
    p["tipo"] = motor.tipo_da_variavel(programa, p["nome"])


def trocar_especificacao(nova) -> None:
    st.session_state[chave_spec] = nova
    st.session_state[chave_spec + "::v"] += 1


def numero_para_tela(valor):
    return None if valor is None else float(valor)


with aba_programa:
    st.subheader("Unidade sob teste")
    st.code("\n".join(f"{numero:>4}  {linha}" for numero, linha in
                      enumerate(texto_funcao.split("\n"), start=linha_funcao)), language=None)
    st.caption("O número à esquerda é a linha no arquivo; é o mesmo usado nos nós do grafo.")
    if programa["ignorados"]:
        st.caption("Linhas ignoradas, porque não mudam o resultado da função: " + ", ".join(
            f"{comando} (linha {linha})" for linha, comando in programa["ignorados"]) + ".")

    st.subheader("Especificação: de onde vem a resposta certa")
    st.html(html_explica(
        "Copie do enunciado, nunca do código",
        "A caixa-preta compara a resposta do programa com o que o enunciado (ou o manual) promete. Preencha "
        "com o que está escrito lá: se a regra for copiada do código, um defeito vira regra e nenhum teste "
        "o encontra." + (" Para o CAD0001 de exemplo, a especificação do manual já vem preenchida."
                         if exemplo_spec else ""), "caixa_preta"))
    maior_escala = max(p["tipo"]["escala"] for p in base_spec["params"])
    menor_passo = float(min(p["tipo"]["epsilon"] for p in base_spec["params"]))
    formato_num = "%d" if maior_escala == 0 else f"%.{maior_escala}f"
    editado_params = st.data_editor(
        pd.DataFrame([{"Parâmetro": p["nome"], "Tipo": p["tipo"]["rotulo"],
                       "Mínimo válido": numero_para_tela(p["minimo"]), "Máximo válido": numero_para_tela(p["maximo"]),
                       "Valor comum": numero_para_tela(p["comum"]), "Valor interior": numero_para_tela(p["interior"])}
                      for p in base_spec["params"]]),
        key=f"{chave_spec}::params::{versao}", hide_index=True, width="stretch", num_rows="fixed",
        disabled=["Parâmetro", "Tipo"],
        column_config={
            "Mínimo válido": st.column_config.NumberColumn(
                step=menor_passo, format=formato_num,
                help="Menor valor aceito pela regra de negócio (o próprio valor é válido). Vazio = sem limite."),
            "Máximo válido": st.column_config.NumberColumn(
                step=menor_passo, format=formato_num,
                help="Maior valor aceito pela regra de negócio (o próprio valor é válido). Vazio = sem limite."),
            "Valor comum": st.column_config.NumberColumn(
                step=menor_passo, format=formato_num,
                help="Valor válido usado nos parâmetros que não estão sendo variados no teste."),
            "Valor interior": st.column_config.NumberColumn(
                step=menor_passo, format=formato_num,
                help="Valor bem dentro da faixa válida (ponto Interior da AVL)."),
        })
    e1, e2 = st.columns(2)
    nulo_escolhido = e1.selectbox(
        "Parâmetro em branco (NULL)", list(cp.NULO_OPCOES), format_func=cp.NULO_OPCOES.get,
        index=list(cp.NULO_OPCOES).index(base_spec["nulo"]), key=f"{chave_spec}::nulo::{versao}")
    retorno_txt = e2.text_input(
        "Resposta quando algum valor é inválido", key=f"{chave_spec}::retorno::{versao}",
        value="" if base_spec["retorno_invalido"] is None else str(base_spec["retorno_invalido"]),
        placeholder="ex.: -1", help="O que a função deve devolver para valor fora da faixa. Vazio = não definido.")
    nomes_exemplo = ", ".join(parametros)
    formula_txt = st.text_input(
        "Resultado esperado nos demais casos (fórmula com os nomes dos parâmetros)",
        value=base_spec["formula"], key=f"{chave_spec}::formula::{versao}",
        placeholder=f"ex.: ({parametros[0]} * {parametros[-1]}) + 1", help=f"Parâmetros disponíveis: {nomes_exemplo}. "
        "Use + - * / e parênteses, como em 4GL.")
    enunciado_txt = st.text_area("Texto do enunciado (opcional; aparece no laudo)", value=base_spec["enunciado"],
                                 key=f"{chave_spec}::enunciado::{versao}", height=90)
    b1, b2, _ = st.columns([1.6, 1.6, 3])
    if exemplo_spec:
        b1.button("Usar a especificação do exemplo", width="stretch", icon=":material/restart_alt:",
                  on_click=trocar_especificacao, args=(cp.especificacao_de_exemplo(programa),))
    b2.button("Limpar a especificação", width="stretch", icon=":material/backspace:",
              on_click=trocar_especificacao, args=(cp.especificacao_inicial(programa),))
    carregada = st.file_uploader(
        "Carregar uma especificação salva (.json)", type=["json"], key=f"{chave_spec}::arquivo",
        help="Prepare a especificação antes, salve com o botão 'Salvar a especificação' e carregue aqui.")
    if carregada is not None and st.session_state.get(chave_spec + "::carregada") != carregada.file_id:
        try:
            nova = cp.especificacao_de_json(decodificar(carregada.getvalue()), programa)
        except cp.ErroEspecificacao as problema:
            st.error(f"Não foi possível carregar a especificação: {problema}.", icon=":material/error:")
        else:
            st.session_state[chave_spec + "::carregada"] = carregada.file_id
            trocar_especificacao(nova)
            st.rerun()

# Monta a especificacao a partir do que foi digitado.
erros_spec = []
spec = {"params": [], "nulo": nulo_escolhido, "retorno_invalido": None, "formula": formula_txt.strip(),
        "enunciado": enunciado_txt.strip()}
for p_base, (_, linha) in zip(base_spec["params"], editado_params.iterrows()):
    p = {"nome": p_base["nome"], "tipo": p_base["tipo"]}
    for campo, coluna in (("minimo", "Mínimo válido"), ("maximo", "Máximo válido"),
                          ("comum", "Valor comum"), ("interior", "Valor interior")):
        try:
            p[campo] = cp.decimal_ou_none(linha[coluna], p["tipo"]["epsilon"])
        except cp.ErroEspecificacao as problema:
            erros_spec.append(f"{p['nome']}, {coluna.lower()}: {problema}")
            p[campo] = None
    spec["params"].append(p)
cp.completar_valores(spec)
try:
    spec["retorno_invalido"] = cp.decimal_ou_none(retorno_txt)
except cp.ErroEspecificacao as problema:
    erros_spec.append(f"Resposta para valor inválido: {problema}")
try:
    formula = cp.compilar_formula(spec)
except cp.ErroEspecificacao as problema:
    erros_spec.append(f"Fórmula: {problema}")
    formula, spec["formula"] = None, ""
SPEC = spec
REGRAS = cp.regras(spec)
ACHADOS, ACHADOS_SIMPLES = cp.textos_dos_achados(spec)
maximo = max(p["tipo"]["maximo"] for p in spec["params"])

with aba_programa:
    for erro in erros_spec:
        st.error(erro, icon=":material/error:")
    for aviso in cp.problemas_da_especificacao(spec):
        st.warning(aviso, icon=":material/rule:")
    if len(REGRAS) > 1:
        st.markdown("**Como a ferramenta entendeu a especificação:**\n" +
                    "\n".join(f"{i}. {r['formal']}" for i, r in enumerate(REGRAS, 1)))

    st.download_button("Salvar a especificação (.json)", cp.especificacao_para_json(spec, FUNCAO_ALVO),
                       file_name=f"especificacao_{FUNCAO_ALVO}.json", mime="application/json",
                       icon=":material/save:", key="salvar_spec")

    st.subheader("Tipos de dado e Épsilon")
    mostrar_tabela(pd.DataFrame([{"Parâmetro": p["nome"], "Tipo": p["tipo"]["rotulo"],
                                "Épsilon (ε)": formato_br(p["tipo"]["epsilon"]),
                                "Menor valor do tipo": formato_br(p["tipo"]["minimo"]),
                                "Maior valor do tipo": formato_br(p["tipo"]["maximo"]),
                                "Observação": p["tipo"]["nota"]} for p in spec["params"]]))

epsilons = sorted({p["tipo"]["epsilon"] for p in spec["params"]})
justificativa = (
    "O Épsilon (ε) é a menor variação que o tipo de dado consegue representar: 10 elevado a menos o número de "
    "casas decimais. " + ("Aqui, " + "; ".join(
        f"{', '.join(p['nome'] for p in spec['params'] if p['tipo']['epsilon'] == e)}: ε = {formato_br(e)}"
        for e in epsilons) + ". ") +
    "Por isso o Off-Point fica exatamente um ε além da fronteira: é o valor inválido mais próximo possível do "
    "limite, o único capaz de distinguir um '<' de um '<=' no código.")

with aba_programa:
    st.caption("O cálculo do Épsilon, passo a passo, está na aba Sprint 1: caixa-preta → Cálculo do Épsilon (ε).")

# ======================= SPRINT 1: CAIXA-PRETA ==============================
with aba_s1:
    st.html(html_explica(
        "Em palavras simples",
        "A caixa-preta testa o programa pelo que ele promete, sem olhar o código. Os valores possíveis são "
        "divididos em grupos que o programa deve tratar igual (classes de equivalência) e o teste se concentra "
        "nas fronteiras entre os grupos (valor limite), onde os erros mais aparecem.", "caixa_preta"))
    aba_resumo, aba_eps, aba_rel, aba_graf, aba_extra = st.tabs(
        ["Resumo", "Cálculo do Épsilon (ε)", "Classes e casos de teste", "Régua da fronteira", "Testes extras"])

# A aba de testes extras e montada primeiro porque todos os indicadores usam as linhas digitadas nela.
with aba_extra:
    st.write("Monte seus próprios casos: troque os valores, apague ou acrescente linhas. "
             "Deixe uma célula vazia para enviar NULL. Todas as abas são recalculadas na hora.")
    sugestoes = pd.DataFrame([{"descricao": descricao,
                               **{f"p{i + 1}": numero_para_tela(v) for i, v in enumerate(valores)}}
                              for descricao, valores in cp.sugestoes_de_extras(spec)])
    coluna_numero = {f"p{i + 1}": st.column_config.NumberColumn(
        p["nome"], step=float(p["tipo"]["epsilon"]), format=f"%.{p['tipo']['escala']}f")
        for i, p in enumerate(spec["params"])}
    digitado = st.data_editor(
        sugestoes, key=f"extras::{chave_spec}::{versao}", num_rows="dynamic", hide_index=True, width="stretch",
        column_config={"descricao": st.column_config.TextColumn("O que este caso verifica", width="large"),
                       **coluna_numero})

casos_base = cp.gerar_suite_base(programa, spec, formula, epsilon, maximo)
casos_extras = gerar_casos_extras(digitado, programa, spec, formula, epsilon, maximo)
casos = casos_base + casos_extras
qualidade = medir_qualidade(casos, spec)

df_casos = tabela_casos(casos, parametros)
df_pce = tabela_pce(casos, spec)
df_pontos = tabela_pontos(spec)
lista_reguas = reguas(spec)
df_origem = pd.DataFrame([
    {"Dado": "Arquivo", "Valor": st.session_state["fonte_nome"]},
    {"Dado": "Lido em", "Valor": st.session_state["fonte_quando"]},
    {"Dado": "Tamanho", "Valor": f"{st.session_state['fonte_bytes']} bytes, {len(original.splitlines())} linhas"},
    {"Dado": "SHA-256 do arquivo", "Valor": st.session_state["fonte_sha"]},
    {"Dado": "Fonte editado na página", "Valor": "Sim" if alterado else "Não"},
    {"Dado": "Unidade sob teste", "Valor": f"{FUNCAO_ALVO}({', '.join(parametros)}), a partir da linha {linha_funcao}"},
    {"Dado": "Tipos e Épsilon", "Valor": "; ".join(f"{p['nome']}: {p['tipo']['rotulo']}, ε = "
                                                   f"{formato_br(p['tipo']['epsilon'])}" for p in spec["params"])},
    {"Dado": "Especificação", "Valor": "escrita na página (exemplo do manual)" if exemplo_spec and
     spec["formula"] == exemplo_spec["formula"] else "escrita na página"},
])

with aba_extra:
    if casos_extras:
        mostrar_tabela(tabela_casos(casos_extras, parametros).drop(columns=["Técnica", "Parâmetro variado", "Ponto ou classe"]))
    else:
        st.caption("Nenhum caso extra preenchido.")

with aba_resumo:
    k = st.columns(6)
    k[0].metric("Casos", qualidade["total"], border=True, help="Casos de teste executados: suíte planejada mais os testes extras.")
    k[1].metric("Aprovados", qualidade["aprovados"], border=True)
    k[2].metric("Reprovados", qualidade["reprovados"], border=True)
    k[3].metric("Classes", f"{qualidade['classes'][0]}/{qualidade['classes'][1]}", border=True,
                help="Classes de equivalência cobertas: válida, inválidas e nula de cada parâmetro.")
    k[4].metric("Fronteiras", f"{qualidade['pontos'][0]}/{qualidade['pontos'][1]}", border=True,
                help="Pontos de fronteira cobertos: On, Off, Interior e Exterior de cada limite de cada parâmetro.")
    k[5].metric("Defeitos", len(qualidade["achados"]), border=True,
                help="Tipos de defeito revelados: divergências diferentes entre o esperado e o obtido.")
    st.caption("Épsilon (ε) usado nas fronteiras: " + "; ".join(
        f"{', '.join(p['nome'] for p in spec['params'] if p['tipo']['epsilon'] == e)}: ε = {formato_br(e)}"
        for e in epsilons) + ". A conta está na aba Cálculo do Épsilon (ε).")
    if qualidade["reprovados"] == 0 and qualidade["aprovados"]:
        st.success(f"Nenhuma divergência: os {qualidade['aprovados']} casos com resultado esperado "
                   "definido foram aprovados.", icon=":material/check_circle:")
    for codigo, ids in qualidade["achados"].items():
        titulo, explicacao = ACHADOS[codigo]
        st.error(f"**{titulo}** — {len(ids)} casos ({', '.join(ids)}). {explicacao}", icon=":material/bug_report:")
    if qualidade["sem_oraculo"]:
        st.info(f"{qualidade['sem_oraculo']} caso(s) sem resultado esperado: a especificação não define a resposta "
                "(veja a coluna Observação). Complete-a na aba Programa e especificação.", icon=":material/help:")
    st.subheader("Cobertura da suíte planejada")
    st.html(html_matriz(casos_base, spec))
    st.caption("Cada célula é um caso: um parâmetro recebe o valor da coluna e os outros ficam no valor comum "
               f"({', '.join(formato_br(p['comum']) for p in spec['params'])}). Os testes extras entram nos "
               "indicadores acima.")

with aba_eps:
    st.html(html_explica(
        "Por que o Épsilon importa",
        "O erro mais comum em regra de limite é trocar um &lt; por um &lt;=. Para pegar esse erro, o teste precisa "
        "usar o valor inválido mais próximo possível da fronteira. Esse valor fica a exatamente um Épsilon (ε) "
        "dela, e o ε é calculado a partir do tipo de dado declarado no código.", "epsilon"))
    st.html(html_epsilon(spec))
    st.markdown("**A conta de cada parâmetro**")
    mostrar_tabela(tabela_epsilon(spec))
    st.caption("Fórmula: ε = 10 elevado a menos o número de casas decimais do tipo. DECIMAL(p,s) tem s casas; "
               "INTEGER e SMALLINT não têm casas, então ε = 1. O Off-Point fica um ε abaixo do mínimo válido "
               "ou um ε acima do máximo válido.")

with aba_rel:
    st.subheader("Especificação usada como oráculo")
    if spec["enunciado"]:
        st.write(spec["enunciado"])
    st.markdown("\n".join(f"{i}. {r['formal']}" for i, r in enumerate(REGRAS, 1)))
    st.subheader("Particionamento em classes de equivalência (PCE)")
    mostrar_tabela(df_pce)
    st.subheader("Análise do valor limite (AVL) e demais casos")
    mostrar_tabela(df_casos)
    st.caption("Esperado: calculado pela especificação. Obtido: resultado da execução da função carregada.")

with aba_graf:
    if not lista_reguas:
        st.info("A especificação não define faixa válida (mínimo ou máximo), então não há fronteira para testar. "
                "Preencha-a na aba Programa e especificação.", icon=":material/straighten:")
    for titulo_regua, svg in lista_reguas:
        st.markdown(f"**{titulo_regua}**")
        st.markdown(svg, unsafe_allow_html=True)
    if lista_reguas:
        st.caption("A escala é logarítmica dos dois lados da fronteira, para que o On-Point e o Off-Point, "
                   "separados por um ε, não fiquem um sobre o outro. Passe o mouse sobre um ponto para ver a "
                   "condição e o resultado esperado.")
    mostrar_tabela(df_pontos)

# ======================= SPRINT 2: CAIXA-BRANCA =============================
with aba_s2:
    st.html(html_explica(
        "Em palavras simples",
        "A caixa-branca testa olhando por dentro. O código vira um mapa: cada trecho é um nó (círculo) e cada "
        "passagem é uma aresta (seta). Os mesmos testes da Sprint 1 são executados e a ferramenta mede por quais "
        "trechos e desvios cada um passou.", "caixa_branca"))
    por_bloco = st.radio("Como contar os nós", GRANULARIDADES, horizontal=True, key="cad_granularidade",
                         help="A definição formal junta em um nó os comandos em sequência, sem desvio. "
                              "Também é comum desenhar um nó para cada comando.") == GRANULARIDADES[0]

casos_do_motor = tuple((c["id"], tuple(c["entradas"])) for c in casos)
try:
    analise = analise_em_cache(tuple(parametros), corpo, linha_funcao, epsilon, casos_do_motor,
                               por_bloco, FUNCAO_ALVO, motor.VERSAO)
except motor.Erro4GL as problema:
    st.error(f"Não foi possível fazer a análise estrutural: {problema}.")
    st.stop()
if any("matam" not in m for m in analise["mutantes"]):          # resultado de uma versao antiga do motor
    analise_em_cache.clear()
    analise = analise_em_cache(tuple(parametros), corpo, linha_funcao, epsilon, casos_do_motor,
                               por_bloco, FUNCAO_ALVO, motor.VERSAO)

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
        mutacao, comparacao_suites = painel_mutacao(analise, "cad", casos)

# ======================= DADOS CONSOLIDADOS =================================
rtm = rastreabilidade(casos)
suite = validar_suite(casos, casos_base, programa, epsilon, qualidade, analise, mutacao, rtm)
achado = achado_central(qualidade, analise, mutacao)
pacote = {
    "qualidade": qualidade, "casos": df_casos, "casos_lista": casos, "pce": df_pce, "pontos": df_pontos,
    "origem": df_origem, "justificativa": justificativa,
    "analise": analise, "mutacao": mutacao, "achado": achado, "parametros": parametros,
    "nos": tabela_nos(analise), "execucoes": tabela_execucoes(analise), "caminhos": tabela_caminhos(analise),
    "variaveis": tabela_variaveis(analise), "pares": tabela_pares(analise), "mutantes": tabela_mutantes(analise, None, mutacao["equivalentes"]),
    "comparacao_suites": comparacao_suites,
    "suite": suite, "criterios_suite": tabela_criterios_suite(suite), "asercoes": tabela_asercoes(casos),
    "reguas": lista_reguas, "rtm": rtm, "requisitos": tabela_requisitos(rtm),
    "derivados": tabela_casos_derivados(casos, rtm), "matriz_rtm": tabela_rtm(casos, rtm),
    "epsilon": epsilon, **identificacao,
}
assinatura = hashlib.sha256((texto_funcao + df_casos.to_csv() + str(por_bloco) + str(mutacao) +
                             cp.especificacao_para_json(SPEC, FUNCAO_ALVO)).encode()).hexdigest()
pacote["pareceres"] = {k: st.session_state[f"parecer::{k}"] for k in list(ETAPAS) + ["geral"]
                       if f"parecer::{k}" in st.session_state}
pacote["pareceres_prof"] = pareceres_profissionais()
pacote.update(texto_funcao=texto_funcao, linha_funcao=linha_funcao, casos_base=casos_base,
              descartadas=tabela_descartadas() if descartadas else pd.DataFrame())
relatorio_html = gerar_relatorio_html(pacote)


def botao_pdf_da_aba(nome: str, chave: str) -> None:
    """PDF so desta aba, gerado no clique (nao pesa a pagina)."""
    st.download_button("Baixar esta aba em PDF", data=lambda: pdf_das_abas(pacote, [nome], COR_DO_PDF),
                       file_name=f"{FUNCAO_ALVO}_{chave}.pdf", mime="application/pdf", key=f"pdf_{chave}",
                       icon=":material/picture_as_pdf:", on_click="ignore")


def botoes_de_download(chave: str) -> None:
    b1, b2, b3, b4 = st.columns(4)
    b3.download_button("Laudo completo em PDF", data=lambda: pdf_das_abas(pacote, ABAS, COR_DO_PDF),
                       file_name=f"laudo_completo_{FUNCAO_ALVO}.pdf", mime="application/pdf", key="pdf_completo",
                       icon=":material/picture_as_pdf:", type="primary", on_click="ignore", width="stretch",
                       help="Todas as abas num só PDF, cada uma começando numa página nova.")
    b4.download_button("Só esta aba em PDF", data=lambda: pdf_das_abas(pacote, ["Laudo"], COR_DO_PDF),
                       file_name=f"{FUNCAO_ALVO}_laudo.pdf", mime="application/pdf", key="pdf_laudo",
                       icon=":material/description:", on_click="ignore", width="stretch")
    b1.download_button("Laudo completo (HTML)", relatorio_html, key=f"laudo_{chave}",
                       file_name=f"laudo_{FUNCAO_ALVO}.html", mime="text/html", width="stretch",
                       icon=":material/download:",
                       help="Abre em qualquer navegador, no modo claro ou escuro. Tem um botão para salvar em PDF.")
    b2.download_button("Casos de teste (CSV)", df_casos.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       key=f"csv_{chave}", file_name=f"casos_de_teste_{FUNCAO_ALVO}.csv", mime="text/csv",
                       width="stretch", icon=":material/table:")


def titulos_menores(texto: str) -> str:
    """Os titulos do texto da IA (#, ##, ###) viram titulos pequenos, para nao competir com os da pagina."""
    linhas = []
    for linha in texto.splitlines():
        nivel = len(linha) - len(linha.lstrip("#"))
        if 0 < nivel <= 6 and linha[nivel:nivel + 1] == " ":
            linha = "#" * min(6, max(nivel, 3) + 2) + linha[nivel:]
        linhas.append(linha)
    return "\n".join(linhas)


def painel_gemini(chave: str, titulo: str, explicacao: str) -> None:
    """Parecer escrito pelo Gemini para uma etapa (ou o geral), a partir dos numeros desta analise."""
    guarda = f"parecer::{chave}"
    escrito = st.session_state.get(guarda)
    usos = st.session_state.get("usos_gemini", 0)
    no_limite = bool(chave_servidor) and usos >= LIMITE_DE_PARECERES
    st.html(html_explica(titulo, explicacao))
    if not api_key:
        st.info("Para gerar o parecer, abra a barra lateral (seta no canto superior esquerdo) e cole a chave "
                "da API do Gemini.", icon=":material/key:")
    elif no_limite:
        st.info(f"Limite de {LIMITE_DE_PARECERES} pareceres por visita atingido. Recarregue a página para "
                "continuar.", icon=":material/hourglass:")
    rotulo = "Gerar de novo" if escrito else "Gerar o parecer com Gemini"
    if st.button(rotulo, key=f"botao_{guarda}", type="secondary" if escrito else "primary",
                 disabled=not api_key or no_limite, icon=":material/edit_note:"):
        st.session_state["usos_gemini"] = usos + 1
        try:
            with st.spinner("Gemini escrevendo o parecer..."):
                if chave == "geral":
                    anteriores = {k: v["texto"] for k, v in pacote["pareceres"].items() if k in ETAPAS}
                    prompt = montar_prompt_geral(texto_funcao, pacote, anteriores)
                else:
                    prompt = montar_prompt_etapa(chave, texto_funcao, pacote)
                texto, usado = chamar_gemini(api_key, situacao["modelo"] if chave_ok else modelo, prompt)
            st.session_state[guarda] = {"texto": texto, "modelo": usado, "assinatura": assinatura,
                                        "quando": agora().strftime("%d/%m/%Y %H:%M")}
            st.session_state["chave_status"] = {"chave": marca_da(api_key), "ok": True, "modelo": usado,
                                                "mensagem": f"Chave funcionando. O modelo {usado} respondeu."}
            st.rerun()
        except FalhaGemini as falha:
            st.error(str(falha), icon=":material/error:")
        except Exception as erro:
            st.error(sem_chave(f"Não foi possível gerar o parecer: {erro}", api_key), icon=":material/error:")
    if escrito:
        if escrito["assinatura"] != assinatura:
            st.warning("Este parecer foi gerado antes das últimas mudanças no fonte, na especificação ou nos "
                       "casos. Gere de novo para atualizar.", icon=":material/history:")
        with st.container(border=True):
            st.markdown(titulos_menores(escrito["texto"]))
            st.caption(f"Escrito pelo modelo {escrito['modelo']} em {escrito['quando']}, a partir dos números "
                       "calculados pela ferramenta.")


def marcar_horario(chave: str) -> None:
    st.session_state[f"prof::{chave}::quando"] = agora().strftime("%d/%m/%Y %H:%M")


def painel_profissional(chave: str, titulo: str) -> None:
    """Parecer escrito por uma pessoa: veredito, texto e assinatura (nome e funcao da barra lateral)."""
    st.html(html_explica(titulo, "Espaço para o profissional técnico registrar a sua análise: o veredito e as "
                                 "observações. A assinatura usa o nome e a função informados na barra lateral."))
    st.selectbox("Veredito", VEREDITOS, key=f"prof::{chave}::veredito", on_change=marcar_horario, args=(chave,))
    st.text_area("Parecer", key=f"prof::{chave}::texto", height=170, on_change=marcar_horario, args=(chave,),
                 placeholder="Escreva aqui o que você concluiu, os riscos que vê e o que recomenda.")
    dados = pareceres_profissionais().get(chave)
    if dados:
        st.html(html_parecer_profissional(dados, "Como vai aparecer no laudo"))
        if not dados["nome"]:
            st.caption("Informe nome e função na barra lateral para assinar o parecer.")


def parecer_da_etapa(chave: str) -> None:
    st.divider()
    st.subheader(f"Pareceres sobre a {ETAPAS[chave]['titulo']}")
    aba_humano, aba_ia = st.tabs(["Parecer do profissional técnico", "Parecer da IA (Gemini)"])
    with aba_humano:
        painel_profissional(chave, "Parecer do profissional técnico")
    with aba_ia:
        painel_gemini(chave, f"Parecer da IA sobre a {ETAPAS[chave]['titulo']}",
                      f"O Gemini lê os resultados desta etapa ({ETAPAS[chave]['curto']}) e escreve um parecer. "
                      "Os números vêm sempre da ferramenta; a IA só redige.")


# ======================= SPRINT 4: VALIDACAO ================================
with aba_s4:
    st.html(html_explica(
        "Em palavras simples",
        "A validação confere se o programa faz o que foi pedido, olhando de fora, como o usuário. Cada regra da "
        "especificação vira um requisito (REQ). De cada requisito saem casos de teste para o fluxo principal "
        "(caminho feliz), para os fluxos alternativos (limites aceitos) e para os fluxos de exceção (bloqueios). "
        "A matriz de rastreabilidade prova a cobertura nos dois sentidos: tudo o que foi pedido foi testado, e "
        "tudo o que foi testado foi pedido.", "validacao"))
    k = st.columns(4)
    k[0].metric("Requisitos cobertos", f"{rtm['ida'][0]} de {rtm['ida'][1]}", border=True,
                help="Ida da rastreabilidade: requisitos com pelo menos um caso de teste.")
    k[1].metric("Testes rastreados", f"{rtm['volta'][0]} de {rtm['volta'][1]}", border=True,
                help="Volta da rastreabilidade: casos de teste que verificam algum requisito.")
    k[2].metric("Conferências da suíte", f"{suite['ok']} de {suite['total']}", border=True)
    k[3].metric("Asserções que falharam", f"{suite['falharam']} de {suite['asercoes']}", border=True,
                help="Asserções que acusaram defeito no programa.")
    if suite["ok"] == suite["total"]:
        st.success("A suíte passou em todas as conferências." + (
            " Por isso as asserções que falharam apontam defeito do programa, e não do teste."
            if suite["falharam"] else ""), icon=":material/verified:")
    else:
        st.warning("Há conferência pendente. As linhas marcadas com ! na aba Conferências mostram onde a suíte "
                   "pode melhorar.", icon=":material/rule:")
    aba_req, aba_rtm, aba_conferencias, aba_asercoes = st.tabs(
        ["Requisitos e casos de teste", "Matriz de rastreabilidade (RTM)", "Conferências da suíte",
         "Asserções (teste de unidade)"])
    with aba_req:
        st.subheader("Requisitos derivados da especificação")
        mostrar_tabela(pacote["requisitos"])
        st.subheader("Casos de teste por fluxo")
        st.html(html_fluxos(casos))
        mostrar_tabela(pacote["derivados"])
        st.caption("Rastreio: os requisitos que cada caso verifica. Um caso sem resposta definida na especificação "
                   "não verifica nenhum requisito.")
    with aba_rtm:
        st.html(html_bidirecional(rtm))
        st.subheader("A matriz")
        mostrar_tabela(pacote["matriz_rtm"])
        st.caption("Linhas: casos de teste. Colunas: requisitos. ✓ = o caso verifica o requisito e passou; "
                   "✕ = verifica e falhou; vazio = não verifica. A linha Total conta os casos de cada requisito.")
    with aba_conferencias:
        mostrar_tabela(pacote["criterios_suite"])
    with aba_asercoes:
        st.write(TEXTO_UNIDADE)
        mostrar_tabela(pacote["asercoes"])
        st.download_button("Baixar estes testes em Python", script_de_testes(casos, pacote["arquivo"]),
                           key="baixar_testes", file_name=f"test_{FUNCAO_ALVO}.py", mime="text/x-python",
                           icon=":material/code:")
        st.caption(f"Para rodar fora da página: deixe o arquivo na pasta principal do TestingStudio (onde fica o app.py), junto do "
                   f"{pacote['arquivo']}, e use python test_{FUNCAO_ALVO}.py (ou python -m pytest -v test_{FUNCAO_ALVO}.py).")
    parecer_da_etapa("s4")

# Pareceres das outras etapas: no fim de cada aba (as abas ja existem; aqui so se acrescenta).
with aba_s1:
    parecer_da_etapa("s1")
with aba_s2:
    parecer_da_etapa("s2")
with aba_s3:
    parecer_da_etapa("s3")

# ======================= PARECER GERAL =======================================
with aba_parecer:
    feitos = [ETAPAS[k]["titulo"] for k in ETAPAS if k in pacote["pareceres"]]
    aba_humano_geral, aba_ia_geral, aba_etapas = st.tabs(
        ["Parecer do profissional técnico", "Parecer da IA (Gemini)", "Pareceres das etapas"])
    with aba_humano_geral:
        painel_profissional("geral", "Parecer geral do profissional técnico")
    with aba_ia_geral:
        painel_gemini("geral", "Parecer geral da análise",
                      "O Gemini junta as quatro etapas (caixa-preta, caixa-branca, fluxo de dados e mutação, validação) "
                      "num parecer só, que começa com um resumo para quem não é da área. Os pareceres das etapas e o "
                      "do profissional técnico, se existirem, entram como apoio"
                      + (f" (IA, prontos: {', '.join(feitos)})." if feitos else "."))
    with aba_etapas:
        for k, etapa in ETAPAS.items():
            ia, humano = pacote["pareceres"].get(k), pacote["pareceres_prof"].get(k)
            estado = " · ".join(x for x in ("profissional" if humano else "", "IA" if ia else "") if x) or "nenhum ainda"
            with st.expander(f"{etapa['titulo']} ({estado})", expanded=False,
                             icon=":material/check_circle:" if (ia or humano) else ":material/radio_button_unchecked:"):
                if humano:
                    st.html(html_parecer_profissional(humano))
                if ia:
                    st.markdown(titulos_menores(ia["texto"]))
                    st.caption(f"IA: modelo {ia['modelo']}, {ia['quando']}.")
                if not (ia or humano):
                    st.caption(f"Escreva ou gere os pareceres no fim da aba {etapa['titulo']}.")
        st.divider()
        st.markdown("**Guardar os pareceres do profissional**")
        st.caption("Os pareceres ficam só nesta visita. Salve-os num arquivo para continuar depois.")
        st.download_button("Salvar os pareceres (.json)", json.dumps(
            {"funcao": FUNCAO_ALVO, "nome": st.session_state.get("prof_nome", ""),
             "funcao_do_profissional": st.session_state.get("prof_funcao", ""),
             "pareceres": {k: {"veredito": v["veredito"], "texto": v["texto"], "quando": v["quando"]}
                           for k, v in pacote["pareceres_prof"].items()}}, ensure_ascii=False, indent=2),
            file_name=f"pareceres_{FUNCAO_ALVO}.json", mime="application/json", icon=":material/save:",
            disabled=not pacote["pareceres_prof"])
        salvo = st.file_uploader("Carregar pareceres salvos (.json)", type=["json"], key="carregar_pareceres")
        if salvo is not None and st.session_state.get("pareceres_carregados") != salvo.file_id:
            try:
                dados = json.loads(decodificar(salvo.getvalue()))
                if not isinstance(dados.get("pareceres"), dict):
                    raise ValueError
                # Os campos ja estao na tela; os valores entram no inicio da proxima execucao.
                st.session_state["pareceres_pendentes"] = dados
                st.session_state["pareceres_carregados"] = salvo.file_id
                st.rerun()
            except (ValueError, AttributeError):
                st.error("O arquivo não parece um arquivo de pareceres do TestingStudio.", icon=":material/error:")

# ======================= FONTES =============================================
with aba_fontes:
    st.html(html_explica(
        "De onde vem cada coisa",
        "Cada técnica do laudo segue uma fonte publicada ou o material da disciplina. O número de cada fonte "
        "é o mesmo que aparece nas faixas de base teórica das outras abas."))
    st.html(html_fontes())
    st.subheader("Origem dos dados desta análise")
    mostrar_tabela(df_origem)
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
    st.html(html_secao("Por que confiar nestes testes",
                       "A própria suíte foi conferida antes do veredito. Os detalhes estão na aba Sprint 4."))
    st.html(html_confianca(pacote))
    if html_pareceres_do_laudo(pacote):
        st.html(html_secao("Pareceres", "O que concluíram o profissional técnico e a IA. Detalhes na aba Parecer geral."))
        st.html('<div class="ts-pareceres">' + html_pareceres_do_laudo(pacote) + "</div>")
    st.html(html_secao("O que este laudo não cobre"))
    st.html(html_limites())
    st.html(html_secao("Em que este laudo se apoia",
                       "As seis fontes principais. A lista completa, com os dados de publicação e os links, "
                       "está na aba Fontes."))
    st.html(html_apoio())
    with st.expander("Glossário: os termos técnicos em linguagem simples", icon=":material/menu_book:"):
        st.html(html_glossario())

# Botao de PDF no topo de cada aba (os conteineres foram criados junto com as abas).
for _nome, _lugar in TOPO_DA_ABA.items():
    with _lugar:
        botao_pdf_da_aba(_nome, {"Programa e especificação": "programa", "Fontes": "fontes"}.get(_nome, CHAVE_DA_ABA.get(_nome, "aba")))
