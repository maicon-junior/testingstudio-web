"""
TestingStudio Web - Sprint 1: Auditoria de Caixa-Preta (PCE & AVL) do CAD0001
Disciplina: Teste de Software I | Prof. Frank Piffer

O que a pagina faz, na ordem:
  1. Le o arquivo .txt do programa (so depois que voce anexa).
  2. Extrai a funcao cad0001_calcula_valor e calcula o Epsilon pelo tipo DECIMAL.
  3. EXECUTA a logica da funcao (mini-interpretador de 4GL) para cada caso de teste.
  4. Compara o resultado obtido com o esperado pela especificacao (oraculo).
  5. Mostra indicadores de qualidade, tabelas, grafico de fronteira e fontes.
  6. Opcional: pede ao Gemini um parecer escrito sobre os resultados.

Abrir no computador:  dois cliques em Abrir_TestingStudio.bat   (ou: python iniciar.py)
Publicar online:      veja o LEIA-ME.txt. A chave do Gemini fica no servidor, em "Secrets".
"""

import hashlib
import html
import os
import re
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

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
     "Base da disciplina: teste funcional, particionamento em classes de equivalência "
     "e análise do valor limite."),
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
# PASSO 2 - Unidade sob teste e Epsilon
# ==========================================================================
def extrair_funcao(fonte: str, nome: str):
    """Localiza 'FUNCTION nome(params) ... END FUNCTION' e devolve
    (lista de parametros, corpo da funcao). Retorna None se nao achar."""
    padrao = rf"FUNCTION\s+{nome}\s*\((.*?)\)(.*?)END\s+FUNCTION"
    achado = re.search(padrao, fonte, re.IGNORECASE | re.DOTALL)
    if not achado:
        return None
    parametros = [p.strip().lower() for p in achado.group(1).split(",") if p.strip()]
    return parametros, achado.group(2)


def calcular_epsilon(corpo: str):
    """Le o DECIMAL(precisao, escala) da funcao e calcula o Epsilon.

    Epsilon = menor variacao que o tipo consegue representar = 10 ^ -escala.
    DECIMAL(12,2) -> escala 2 -> epsilon = 10^-2 = 0,01 (1 centavo).
    Maior valor  = 10^(precisao - escala) - epsilon = 9.999.999.999,99.
    """
    achado = re.search(r"DECIMAL\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", corpo, re.IGNORECASE)
    if not achado:
        return None
    precisao, escala = int(achado.group(1)), int(achado.group(2))
    epsilon = Decimal(10) ** -escala
    maximo = Decimal(10) ** (precisao - escala) - epsilon
    return precisao, escala, epsilon, maximo


# ==========================================================================
# PASSO 3 - Mini-interpretador de 4GL
# Executa de verdade a logica da funcao carregada. Entende o subconjunto usado
# no CAD0001: DEFINE, IF/THEN/ELSE/END IF, LET, RETURN, IS [NOT] NULL,
# comparacoes, AND/OR/NOT e aritmetica. Se o fonte mudar (por exemplo, trocar
# '<' por '<='), o resultado dos testes muda junto.
# ==========================================================================
class Erro4GL(Exception):
    """Erro ao interpretar ou executar o fonte 4GL."""


PALAVRAS = {"if", "then", "else", "end", "let", "return", "define",
            "and", "or", "not", "is", "null", "true", "false",
            # comandos que o interpretador reconhece so para avisar que nao executa
            "while", "for", "foreach", "case", "when", "call", "display", "message",
            "select", "insert", "update", "delete", "whenever", "goto", "exit", "continue"}
PADRAO_TOKEN = re.compile(
    r"\s*(?:(\d+\.\d+|\d+|\.\d+)|([A-Za-z_][\w.]*)|(<=|>=|<>|!=|==|[-+*/()=<>,]))")


def tokenizar(codigo: str):
    """Quebra o texto em tokens: ('num', Decimal), ('palavra', 'if'),
    ('nome', 'p_val1') ou ('op', '<=')."""
    codigo = re.sub(r"\{.*?\}", " ", codigo, flags=re.DOTALL)   # comentario { }
    codigo = re.sub(r"(#|--).*", " ", codigo)                    # comentario # e --
    tokens, pos = [], 0
    while pos < len(codigo):
        achado = PADRAO_TOKEN.match(codigo, pos)
        if not achado:
            resto = codigo[pos:].strip()
            if not resto:
                break
            raise Erro4GL(f"símbolo não reconhecido perto de '{resto[:20]}'")
        numero, nome, operador = achado.groups()
        if numero:
            tokens.append(("num", Decimal(numero)))
        elif nome:
            nome = nome.lower()
            tokens.append(("palavra" if nome in PALAVRAS else "nome", nome))
        else:
            tokens.append(("op", operador))
        pos = achado.end()
    return tokens


class Analisador:
    """Transforma a lista de tokens em uma arvore de comandos."""

    def __init__(self, tokens):
        self.tokens, self.pos, self.declaradas = tokens, 0, set()

    def atual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("fim", "")

    def e(self, tipo, *valores):
        t, v = self.atual()
        return t == tipo and (not valores or v in valores)

    def avancar(self):
        token = self.atual()
        self.pos += 1
        return token

    def exigir(self, tipo, valor):
        if not self.e(tipo, valor):
            raise Erro4GL(f"esperava '{str(valor).upper()}' e encontrei '{self.atual()[1]}'")
        return self.avancar()

    # ---- comandos --------------------------------------------------------
    def bloco(self, *fins):
        comandos = []
        while not self.e("fim") and not (fins and self.e("palavra", *fins)):
            comando = self.comando()
            if comando:
                comandos.append(comando)
        return comandos

    def comando(self):
        if self.e("palavra", "define"):
            self.avancar()
            while not self.e("fim") and not self.e("palavra"):
                tipo, valor = self.avancar()
                if tipo == "nome":
                    self.declaradas.add(valor)
            return None
        if self.e("palavra", "if"):
            self.avancar()
            condicao = self.expressao()
            self.exigir("palavra", "then")
            entao = self.bloco("else", "end")
            senao = []
            if self.e("palavra", "else"):
                self.avancar()
                senao = self.bloco("end")
            self.exigir("palavra", "end")
            self.exigir("palavra", "if")
            return ("if", condicao, entao, senao)
        if self.e("palavra", "let"):
            self.avancar()
            if not self.e("nome"):
                raise Erro4GL("LET sem nome de variável")
            nome = self.avancar()[1]
            self.exigir("op", "=")
            return ("let", nome, self.expressao())
        if self.e("palavra", "return"):
            self.avancar()
            inicia_expressao = (self.e("num") or self.e("nome") or self.e("op", "(", "-", "+")
                                or self.e("palavra", "not", "null", "true", "false"))
            return ("return", self.expressao() if inicia_expressao else None)
        raise Erro4GL(f"comando não suportado: '{self.atual()[1]}'")

    # ---- expressoes (da menor para a maior precedencia) ------------------
    def expressao(self):
        no = self.conjuncao()
        while self.e("palavra", "or"):
            self.avancar()
            no = ("logico", "or", no, self.conjuncao())
        return no

    def conjuncao(self):
        no = self.negacao()
        while self.e("palavra", "and"):
            self.avancar()
            no = ("logico", "and", no, self.negacao())
        return no

    def negacao(self):
        if self.e("palavra", "not"):
            self.avancar()
            return ("nao", self.negacao())
        return self.comparacao()

    def comparacao(self):
        no = self.soma()
        if self.e("palavra", "is"):
            self.avancar()
            negado = self.e("palavra", "not")
            if negado:
                self.avancar()
            self.exigir("palavra", "null")
            return ("is_null", no, negado)
        if self.e("op", "<", "<=", ">", ">=", "=", "==", "<>", "!="):
            operador = self.avancar()[1]
            return ("compara", operador, no, self.soma())
        return no

    def soma(self):
        no = self.produto()
        while self.e("op", "+", "-"):
            operador = self.avancar()[1]
            no = ("conta", operador, no, self.produto())
        return no

    def produto(self):
        no = self.unario()
        while self.e("op", "*", "/"):
            operador = self.avancar()[1]
            no = ("conta", operador, no, self.unario())
        return no

    def unario(self):
        if self.e("op", "-"):
            self.avancar()
            return ("negativo", self.unario())
        if self.e("op", "+"):
            self.avancar()
            return self.unario()
        return self.primario()

    def primario(self):
        tipo, valor = self.avancar()
        if tipo == "num":
            return ("num", valor)
        if tipo == "nome":
            return ("var", valor)
        if tipo == "palavra" and valor == "null":
            return ("nulo",)
        if tipo == "palavra" and valor in ("true", "false"):
            return ("num", Decimal(1 if valor == "true" else 0))
        if tipo == "op" and valor == "(":
            no = self.expressao()
            self.exigir("op", ")")
            return no
        raise Erro4GL(f"expressão inválida perto de '{valor}'")


class _Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


def compilar_funcao(parametros, corpo: str):
    """Analisa o corpo da funcao uma unica vez. Devolve o 'programa' pronto
    para ser executado varias vezes com entradas diferentes."""
    analisador = Analisador(tokenizar(corpo))
    comandos = analisador.bloco()
    if not analisador.e("fim"):
        raise Erro4GL(f"trecho não interpretado a partir de '{analisador.atual()[1]}'")
    return {"comandos": comandos, "parametros": list(parametros),
            "variaveis": set(parametros) | analisador.declaradas}


def _avaliar(no, ambiente, variaveis):
    tipo = no[0]
    if tipo == "num":
        return no[1]
    if tipo == "nulo":
        return None
    if tipo == "var":
        if no[1] not in variaveis:
            raise Erro4GL(f"variável '{no[1]}' não foi declarada")
        return ambiente.get(no[1])
    if tipo == "negativo":
        valor = _avaliar(no[1], ambiente, variaveis)
        return None if valor is None else -valor
    if tipo == "nao":
        return not bool(_avaliar(no[1], ambiente, variaveis))
    if tipo == "is_null":
        e_nulo = _avaliar(no[1], ambiente, variaveis) is None
        return (not e_nulo) if no[2] else e_nulo
    if tipo == "logico":
        esquerda = bool(_avaliar(no[2], ambiente, variaveis))
        if no[1] == "and":
            return esquerda and bool(_avaliar(no[3], ambiente, variaveis))
        return esquerda or bool(_avaliar(no[3], ambiente, variaveis))
    a = _avaliar(no[2], ambiente, variaveis)
    b = _avaliar(no[3], ambiente, variaveis)
    if tipo == "compara":
        if a is None or b is None:        # em SQL/4GL, comparar com NULL nunca e verdadeiro
            return False
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b,
                "=": a == b, "==": a == b, "<>": a != b, "!=": a != b}[no[1]]
    if a is None or b is None:            # conta com NULL resulta em NULL
        return None
    if no[1] == "+":
        return a + b
    if no[1] == "-":
        return a - b
    if no[1] == "*":
        return a * b
    if b == 0:
        raise Erro4GL("divisão por zero")
    return a / b


def _executar(comandos, ambiente, variaveis, epsilon):
    for comando in comandos:
        if comando[0] == "let":
            valor = _avaliar(comando[2], ambiente, variaveis)
            if isinstance(valor, Decimal):    # variavel DECIMAL(p,e) arredonda na escala
                valor = valor.quantize(epsilon, ROUND_HALF_UP)
            ambiente[comando[1]] = valor
        elif comando[0] == "if":
            ramo = comando[2] if bool(_avaliar(comando[1], ambiente, variaveis)) else comando[3]
            _executar(ramo, ambiente, variaveis, epsilon)
        elif comando[0] == "return":
            raise _Retorno(None if comando[1] is None else _avaliar(comando[1], ambiente, variaveis))


def executar_funcao(programa, entradas, epsilon):
    """Roda a funcao com as entradas dadas e devolve o valor do RETURN."""
    ambiente = dict(zip(programa["parametros"], entradas))
    try:
        _executar(programa["comandos"], ambiente, programa["variaveis"], epsilon)
        resultado = None                       # funcao terminou sem RETURN
    except _Retorno as retorno:
        resultado = retorno.valor
    if isinstance(resultado, bool):
        resultado = Decimal(int(resultado))
    if isinstance(resultado, Decimal):
        resultado = resultado.quantize(epsilon, ROUND_HALF_UP)
    return resultado


# ==========================================================================
# PASSO 4 - Oraculo, classes de equivalencia e casos de teste
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
    obtido, erro = None, None
    try:
        obtido = executar_funcao(programa, entradas, epsilon)
    except Erro4GL as problema:
        erro = str(problema)

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
# PASSO 5 - Apresentacao: formatos, tabelas e grafico
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


def gerar_relatorio_html(dados) -> str:
    """Relatorio completo em uma pagina HTML, pronta para apresentar ou
    imprimir em PDF pelo navegador (Ctrl+P)."""
    q = dados["qualidade"]
    achados = "".join(
        f"<li><b>{html.escape(ACHADOS[cod][0])}</b> ({len(ids)} casos: {', '.join(ids)}). "
        f"{html.escape(ACHADOS[cod][1])}</li>" for cod, ids in q["achados"].items()
    ) or "<li>Nenhuma divergência: todos os casos com oráculo foram aprovados.</li>"
    referencias = "".join(f"<li>{html.escape(ref)}<br><small>{html.escape(uso)}</small></li>"
                          for ref, uso in REFERENCIAS)
    especificacao = "".join(f"<li>{html.escape(regra)}</li>" for regra in ESPECIFICACAO)
    parecer = (f"<h2>Parecer do Gemini ({html.escape(dados['parecer_modelo'])})</h2>"
               f"<pre class='parecer'>{html.escape(dados['parecer'])}</pre>") if dados.get("parecer") else ""

    def tabela(df):
        return df.to_html(index=False, border=0, classes="t", escape=True)

    return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatório de teste — CAD0001</title>
<style>
 body {{font-family:'Segoe UI',system-ui,sans-serif; color:#1b2a3d; margin:2.2rem auto; max-width:1000px; padding:0 1.2rem; line-height:1.5;}}
 h1,h2 {{font-family:'Cascadia Mono',Consolas,monospace; letter-spacing:-.01em;}}
 h1 {{font-size:1.7rem; margin-bottom:.2rem;}} h2 {{font-size:1.15rem; margin-top:2rem; border-top:2px solid #1b2a3d; padding-top:.6rem;}}
 .meta {{color:#52606f; margin-top:0;}}
 .kpis {{display:flex; flex-wrap:wrap; gap:.8rem; margin:1.2rem 0;}}
 .kpi {{border:1px solid #c9d1da; border-radius:6px; padding:.6rem .9rem; min-width:150px;}}
 .kpi b {{display:block; font-size:1.5rem;}} .kpi span {{color:#52606f; font-size:.85rem;}}
 table.t {{border-collapse:collapse; width:100%; font-size:.86rem; margin:.6rem 0;}}
 table.t th, table.t td {{border-bottom:1px solid #d5dbe2; padding:.35rem .5rem; text-align:left;}}
 table.t th {{background:#edf1f5;}} table.t td {{white-space:nowrap;}} table.t td:last-child {{white-space:normal;}}
 small {{color:#52606f;}} li {{margin-bottom:.35rem;}}
 pre.parecer {{white-space:pre-wrap; font-family:inherit; background:#f4f6f8; padding:1rem; border-radius:6px;}}
 @media print {{ body {{margin:0; max-width:none;}} h2 {{break-after:avoid;}} tr {{break-inside:avoid;}} }}
</style></head><body>
<h1>Relatório de teste funcional — CAD0001</h1>
<p class="meta">Função {FUNCAO_ALVO}, teste de caixa-preta (PCE e AVL). Teste de Software I, Prof. Frank Piffer, Sprint 1.<br>
Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")} pelo TestingStudio Web</p>

<h2>1. Qualidade do conjunto de testes</h2>
<div class="kpis">
 <div class="kpi"><b>{q['total']}</b><span>casos executados</span></div>
 <div class="kpi"><b>{q['aprovados']}</b><span>aprovados</span></div>
 <div class="kpi"><b>{q['reprovados']}</b><span>reprovados</span></div>
 <div class="kpi"><b>{q['classes'][0]} de {q['classes'][1]}</b><span>classes de equivalência cobertas</span></div>
 <div class="kpi"><b>{q['pontos'][0]} de {q['pontos'][1]}</b><span>pontos de fronteira cobertos</span></div>
 <div class="kpi"><b>{len(q['achados'])}</b><span>tipos de defeito revelados</span></div>
</div>
<h2>2. Achados</h2><ul>{achados}</ul>

<h2>3. Objeto de teste e origem dos dados</h2>
{tabela(dados['origem'])}
<h2>4. Especificação usada como oráculo</h2><ol>{especificacao}</ol>

<h2>5. Particionamento em classes de equivalência (PCE)</h2>
{tabela(dados['pce'])}

<h2>6. Análise do valor limite (AVL) e Épsilon</h2>
<p>{html.escape(dados['justificativa'])}</p>
{tabela(dados['pontos'])}

<h2>7. Casos de teste executados</h2>
{tabela(dados['casos'])}
{parecer}
<h2>Fontes</h2><ol>{referencias}</ol>
<p><small>Método: o TestingStudio interpreta em Python a lógica da função 4GL carregada
(IF, LET, RETURN, comparações e aritmética). Não é o compilador Informix.</small></p>
</body></html>"""


# ==========================================================================
# PASSO 6 - Gemini: teste da chave e parecer
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


def montar_prompt(fonte_funcao, dados) -> str:
    q = dados["qualidade"]
    achados = "\n".join(f"- {ACHADOS[c][0]}: casos {', '.join(ids)}" for c, ids in q["achados"].items()) \
        or "- nenhum"
    referencias = "\n".join(f"- {ref}" for ref, _ in REFERENCIAS)
    regras = "\n".join(f"{i}. {r}" for i, r in enumerate(ESPECIFICACAO, 1))
    return f"""Você é um auditor de teste de software. Escreva, em português do Brasil, um parecer
de teste funcional (caixa-preta) da função {FUNCAO_ALVO} do programa CAD0001, com foco na
QUALIDADE DO PRODUTO DE TESTE (adequação e cobertura do conjunto de casos) e nos defeitos revelados.

Estrutura do parecer:
1. Resumo executivo (3 a 5 linhas).
2. Classes de equivalência: tabela com classes válidas e inválidas de cada parâmetro.
3. Análise do valor limite: justifique o Épsilon e comente os pontos On, Off, Interior e Exterior.
4. Qualidade do conjunto de testes: cobertura de classes e de fronteiras, pontos fortes e lacunas.
5. Defeitos revelados e correção sugerida no fonte.
6. Próximos testes recomendados.

Use somente os dados abaixo, que já foram calculados pela ferramenta. Ao citar literatura,
use apenas as referências listadas e não invente citações literais nem números de página.

<especificacao>
{regras}
</especificacao>

<funcao_sob_teste>
{fonte_funcao}
</funcao_sob_teste>

<epsilon>{dados['justificativa']}</epsilon>

<indicadores>
casos executados: {q['total']} | aprovados: {q['aprovados']} | reprovados: {q['reprovados']}
classes de equivalência cobertas: {q['classes'][0]} de {q['classes'][1]}
pontos de fronteira cobertos: {q['pontos'][0]} de {q['pontos'][1]}
achados:
{achados}
</indicadores>

<classes_de_equivalencia_csv>
{dados['pce'].to_csv(index=False)}
</classes_de_equivalencia_csv>

<casos_de_teste_csv>
{dados['casos'].to_csv(index=False)}
</casos_de_teste_csv>

<referencias>
{referencias}
</referencias>"""


# ==========================================================================
# INTERFACE WEB (Streamlit)
# ==========================================================================
st.set_page_config(page_title="TestingStudio Web - Sprint 1", layout="wide")
st.html(ESTILO)

st.title("TestingStudio Web")
st.html("<p class='ts-sub'>Auditoria de caixa-preta do programa CAD0001: classes de equivalência "
        "e análise do valor limite, com os testes executados sobre o fonte que você anexar.</p>"
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
        st.caption("Sem chave, a auditoria funciona normalmente; só o parecer do Gemini fica desligado.")
    elif not situacao or situacao["chave"] != marca_da(api_key):
        st.info("Chave ainda não testada.", icon=":material/help:")
    elif situacao["ok"]:
        st.success(situacao["mensagem"], icon=":material/check_circle:")
    else:
        st.error(situacao["mensagem"], icon=":material/error:")

    st.divider()
    st.caption("Teste de Software I, Prof. Frank Piffer. Sprint 1: caixa-preta (PCE e AVL).")

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
funcao = extrair_funcao(fonte, FUNCAO_ALVO)
if funcao is None:
    st.error(f"Não encontrei 'FUNCTION {FUNCAO_ALVO}(...) ... END FUNCTION' neste fonte.")
    st.stop()
parametros, corpo = funcao
tipo = calcular_epsilon(corpo)
if tipo is None or len(parametros) != 3:
    st.error("A função precisa ter 3 parâmetros e uma declaração DECIMAL(precisão, escala).")
    st.stop()
precisao, escala, epsilon, maximo = tipo
try:
    programa = compilar_funcao(parametros, corpo)
except Erro4GL as problema:
    st.error(f"Não consegui interpretar a função: {problema}. "
             "O interpretador entende DEFINE, IF/THEN/ELSE, LET e RETURN.")
    st.stop()

st.header("2. Unidade sob teste e Épsilon")
texto_funcao = f"FUNCTION {FUNCAO_ALVO}({', '.join(parametros)}){corpo}END FUNCTION"
with st.expander(f"Função {FUNCAO_ALVO} extraída do fonte"):
    st.code(texto_funcao, language="sql", line_numbers=True)

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
st.header("3. Auditoria de caixa-preta")
aba_resumo, aba_rel, aba_graf, aba_extra, aba_ia, aba_fontes = st.tabs(
    ["Resumo da qualidade", "Relatório (PCE & AVL)", "Gráfico de fronteira",
     "Testes extras", "Parecer do Gemini", "Fontes"])

# A aba de testes extras e montada primeiro porque os indicadores do resumo
# precisam das linhas digitadas nela.
with aba_extra:
    st.write("Monte seus próprios casos: troque os valores, apague ou acrescente linhas. "
             "Deixe uma célula vazia para enviar NULL. Os resultados e os indicadores "
             "das outras abas são recalculados na hora.")
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
    {"Dado": "Unidade sob teste", "Valor": f"{FUNCAO_ALVO}({', '.join(parametros)})"},
    {"Dado": "Tipo de dado e Épsilon", "Valor": f"DECIMAL({precisao},{escala}); ε = {formato_br(epsilon)}"},
])
pacote = {"qualidade": qualidade, "casos": df_casos, "pce": df_pce, "pontos": df_pontos_tela,
          "origem": df_origem, "justificativa": justificativa}
assinatura = hashlib.sha256((texto_funcao + df_casos.to_csv()).encode()).hexdigest()
parecer = st.session_state.get("parecer")
if parecer:
    pacote.update(parecer=parecer["texto"], parecer_modelo=parecer["modelo"])

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

    b1, b2, _ = st.columns([1.6, 1.6, 3])
    b1.download_button("Baixar relatório (HTML)", gerar_relatorio_html(pacote),
                       file_name="relatorio_cad0001.html", mime="text/html", width="stretch",
                       help="Abra no navegador para apresentar ou use Ctrl+P para salvar em PDF.")
    b2.download_button("Baixar casos de teste (CSV)", df_casos.to_csv(index=False, sep=";").encode("utf-8-sig"),
                       file_name="casos_de_teste_cad0001.csv", mime="text/csv", width="stretch")

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

with aba_ia:
    st.write("As tabelas e os indicadores são calculados pelo Python. Aqui o Gemini redige um parecer a partir deles.")
    if not api_key:
        st.info("Cole a chave da API na barra lateral para ligar esta parte.", icon=":material/key:")
    elif not chave_ok:
        st.info("Use o botão Testar chave, na barra lateral, para confirmar que a chave funciona.",
                icon=":material/key:")
    usos = st.session_state.get("usos_gemini", 0)
    no_limite = bool(chave_servidor) and usos >= LIMITE_DE_PARECERES
    if no_limite:
        st.info(f"Limite de {LIMITE_DE_PARECERES} pareceres por visita atingido. "
                "Recarregue a página para continuar.", icon=":material/hourglass:")
    if st.button("Executar auditoria com Gemini", type="primary", disabled=not api_key or no_limite):
        st.session_state["usos_gemini"] = usos + 1
        try:
            with st.spinner("Gemini analisando classes e limites..."):
                texto, usado = chamar_gemini(api_key, situacao["modelo"] if chave_ok else modelo,
                                             montar_prompt(texto_funcao, pacote))
            st.session_state["parecer"] = {"texto": texto, "modelo": usado, "assinatura": assinatura}
            st.session_state["chave_status"] = {"chave": marca_da(api_key), "ok": True, "modelo": usado,
                                                "mensagem": f"Chave funcionando. O modelo {usado} respondeu."}
            st.rerun()
        except FalhaGemini as falha:
            st.error(str(falha), icon=":material/error:")
        except Exception as erro:
            st.error(sem_chave(f"Não foi possível gerar o parecer: {erro}", api_key), icon=":material/error:")
    if parecer:
        if parecer["assinatura"] != assinatura:
            st.warning("Este parecer foi gerado antes das últimas alterações no fonte ou nos casos. "
                       "Execute de novo para atualizar.", icon=":material/history:")
        st.caption(f"Parecer gerado pelo modelo {parecer['modelo']}.")
        st.markdown(parecer["texto"])

with aba_fontes:
    st.subheader("Referências")
    st.html("".join(f"<div class='ts-ref'><p>{html.escape(ref)}</p><p class='uso'>{html.escape(uso)}</p></div>"
                    for ref, uso in REFERENCIAS))
    st.subheader("Origem dos dados desta auditoria")
    st.dataframe(df_origem, hide_index=True, width="stretch")
    st.subheader("Como os resultados são obtidos")
    st.markdown(
        "- **Esperado:** vem das quatro regras da especificação, sem olhar o código (caixa-preta).\n"
        "- **Obtido:** o TestingStudio interpreta em Python a lógica da função carregada "
        "(IF, LET, RETURN, comparações e aritmética) e a executa com as entradas de cada caso. "
        "Não é o compilador Informix.\n"
        "- **Parecer do Gemini:** texto gerado por IA a partir dessas tabelas; os números vêm sempre do Python."
    )
