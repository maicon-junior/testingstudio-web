"""
motor.py - Motor de analise do TestingStudio Web (sem interface).

Tudo o que a pagina mostra nas Sprints 2, 3 e 4 e calculado aqui:

  1. Interpretador de 4GL  - le e EXECUTA a funcao (IF, WHILE, LET, RETURN).
  2. Caixa-branca          - Grafo de Fluxo de Controle (GFC), nos, arestas,
                             complexidade ciclomatica de McCabe e caminhos.
  3. Fluxo de dados        - definicoes, c-usos, p-usos e pares Def-Uso.
  4. Teste de mutacao      - operadores AOR, ROR, COR e LVR e escore de mutacao.
  5. Validacao             - exemplos das aulas com resultado conhecido (gabarito).

Notacao e criterios: Delamaro, Maldonado e Jino (2007) e slides das aulas.
"""

import itertools
import random
import re
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

EPSILON_PADRAO = Decimal("0.01")


class Erro4GL(Exception):
    """Erro ao interpretar ou executar o fonte 4GL."""


# ==========================================================================
# 1. INTERPRETADOR DE 4GL
# ==========================================================================
PALAVRAS = {"if", "then", "else", "end", "let", "return", "define", "while",
            "and", "or", "not", "is", "null", "true", "false"}
# Comandos reconhecidos so para avisar que o interpretador nao os executa.
NAO_EXECUTA = {"for", "foreach", "case", "when", "call", "display", "message", "select",
               "insert", "update", "delete", "whenever", "goto", "exit", "continue", "function"}
PADRAO_TOKEN = re.compile(
    r"\s*(?:(\d+\.\d+|\d+|\.\d+)|([A-Za-z_][\w.]*)|(<=|>=|<>|!=|==|[-+*/()=<>,]))")


def tokenizar(codigo: str, linha_inicial: int = 1):
    """Quebra o texto em tokens (tipo, valor, linha do arquivo)."""
    # Comentarios viram espacos, mas as quebras de linha ficam para manter a numeracao.
    codigo = re.sub(r"\{.*?\}", lambda m: re.sub(r"[^\n]", " ", m.group(0)), codigo, flags=re.DOTALL)
    codigo = re.sub(r"(#|--).*", " ", codigo)
    tokens = []
    for numero, linha in enumerate(codigo.split("\n"), start=linha_inicial):
        pos = 0
        while pos < len(linha):
            achado = PADRAO_TOKEN.match(linha, pos)
            if not achado:
                resto = linha[pos:].strip()
                if not resto:
                    break
                raise Erro4GL(f"linha {numero}: símbolo não reconhecido perto de '{resto[:20]}'")
            numero_txt, nome, operador = achado.groups()
            if numero_txt:
                tokens.append(("num", Decimal(numero_txt), numero))
            elif nome:
                nome = nome.lower()
                tokens.append(("palavra" if nome in PALAVRAS or nome in NAO_EXECUTA else "nome", nome, numero))
            else:
                tokens.append(("op", {"==": "=", "!=": "<>"}.get(operador, operador), numero))
            pos = achado.end()
    return tokens


class Analisador:
    """Transforma a lista de tokens em uma arvore de comandos.

    Cada comando executavel recebe um numero (id) e guarda a linha do fonte:
      {"t": "let",    "id", "linha", "nome", "expr"}
      {"t": "return", "id", "linha", "expr"}
      {"t": "if",     "id", "linha", "cond", "entao": [...], "senao": [...]}
      {"t": "while",  "id", "linha", "cond", "corpo": [...]}
    """

    def __init__(self, tokens):
        self.tokens, self.pos, self.declaradas, self.contador = tokens, 0, [], 0

    def atual(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ("fim", "", 0)

    def e(self, tipo, *valores):
        t, v, _ = self.atual()
        return t == tipo and (not valores or v in valores)

    def avancar(self):
        token = self.atual()
        self.pos += 1
        return token

    def exigir(self, tipo, valor):
        if not self.e(tipo, valor):
            _, achado, linha = self.atual()
            raise Erro4GL(f"linha {linha}: esperava '{str(valor).upper()}' e encontrei '{achado}'")
        return self.avancar()

    def novo(self, tipo, linha, **campos):
        self.contador += 1
        return {"t": tipo, "id": self.contador, "linha": linha, **campos}

    # ---- comandos --------------------------------------------------------
    def bloco(self, *fins):
        comandos = []
        while not self.e("fim") and not (fins and self.e("palavra", *fins)):
            comando = self.comando()
            if comando:
                comandos.append(comando)
        return comandos

    def comando(self):
        _, valor, linha = self.atual()
        if self.e("palavra", "define"):
            self.avancar()
            while not self.e("fim") and not self.e("palavra"):
                tipo, nome, _ = self.avancar()
                if tipo == "nome":
                    self.declaradas.append(nome)
            return None
        if self.e("palavra", "if"):
            self.avancar()
            condicao = self.expressao()
            self.exigir("palavra", "then")
            comando = self.novo("if", linha, cond=condicao, entao=[], senao=[])
            comando["entao"] = self.bloco("else", "end")
            if self.e("palavra", "else"):
                self.avancar()
                comando["senao"] = self.bloco("end")
            self.exigir("palavra", "end")
            self.exigir("palavra", "if")
            return comando
        if self.e("palavra", "while"):
            self.avancar()
            comando = self.novo("while", linha, cond=self.expressao(), corpo=[])
            comando["corpo"] = self.bloco("end")
            self.exigir("palavra", "end")
            self.exigir("palavra", "while")
            return comando
        if self.e("palavra", "let"):
            self.avancar()
            if not self.e("nome"):
                raise Erro4GL(f"linha {linha}: LET sem nome de variável")
            nome = self.avancar()[1]
            self.exigir("op", "=")
            return self.novo("let", linha, nome=nome, expr=self.expressao())
        if self.e("palavra", "return"):
            self.avancar()
            inicia_expressao = (self.e("num") or self.e("nome") or self.e("op", "(", "-", "+")
                                or self.e("palavra", "not", "null", "true", "false"))
            return self.novo("return", linha, expr=self.expressao() if inicia_expressao else None)
        raise Erro4GL(f"linha {linha}: comando não suportado: '{valor}'")

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
        if self.e("op", "<", "<=", ">", ">=", "=", "<>"):
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
        tipo, valor, linha = self.avancar()
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
        raise Erro4GL(f"linha {linha}: expressão inválida perto de '{valor}'")


CAMPO_EXPR = {"let": "expr", "return": "expr", "if": "cond", "while": "cond"}


def todos_os_comandos(comandos):
    """Percorre a arvore e devolve todos os comandos, na ordem do fonte."""
    for c in comandos:
        yield c
        for filhos in ("entao", "senao", "corpo"):
            if filhos in c:
                yield from todos_os_comandos(c[filhos])


def variaveis_da_expressao(no):
    """Nomes de variaveis usados em uma expressao, na ordem em que aparecem."""
    if no is None:
        return []
    if no[0] == "var":
        return [no[1]]
    nomes = []
    for parte in no[1:]:
        if isinstance(parte, tuple):
            for nome in variaveis_da_expressao(parte):
                if nome not in nomes:
                    nomes.append(nome)
    return nomes


def compilar_funcao(parametros, corpo: str, linha_inicial: int = 1, nome: str = ""):
    """Analisa o corpo da funcao uma unica vez. Devolve o 'programa' pronto
    para ser executado varias vezes com entradas diferentes."""
    analisador = Analisador(tokenizar(corpo, linha_inicial))
    comandos = analisador.bloco()
    if not analisador.e("fim"):
        _, valor, linha = analisador.atual()
        raise Erro4GL(f"linha {linha}: trecho não interpretado a partir de '{valor}'")
    parametros = [p.lower() for p in parametros]
    # Variaveis de verdade: parametros, alvos de LET e nomes usados em expressoes.
    nomes = list(parametros)
    for c in todos_os_comandos(comandos):
        candidatos = ([c["nome"]] if c["t"] == "let" else []) + variaveis_da_expressao(c[CAMPO_EXPR[c["t"]]])
        for candidato in candidatos:
            if candidato not in nomes:
                nomes.append(candidato)
    atribuidas = {c["nome"] for c in todos_os_comandos(comandos) if c["t"] == "let"}
    return {"nome": nome, "parametros": parametros, "comandos": comandos,
            "variaveis": nomes,
            "conhecidas": set(parametros) | set(analisador.declaradas) | atribuidas}


# ---- texto de expressoes e comandos (usado em tabelas, grafo e mutantes) ---
_NIVEL = {"logico_or": 1, "logico_and": 2, "nao": 3, "compara": 4, "is_null": 4,
          "conta_+": 5, "conta_-": 5, "conta_*": 6, "conta_/": 6, "negativo": 7}


def texto_expr(no, nivel_pai: int = 0) -> str:
    """Escreve a expressao de volta em 4GL, com parenteses so onde precisa."""
    tipo = no[0]
    if tipo == "num":
        return format(no[1].normalize(), "f") if no[1] == no[1].to_integral() else str(no[1])
    if tipo == "var":
        return no[1]
    if tipo == "nulo":
        return "NULL"
    if tipo == "negativo":
        texto, nivel = "-" + texto_expr(no[1], 7), 7
    elif tipo == "nao":
        texto, nivel = "NOT " + texto_expr(no[1], 3), 3
    elif tipo == "is_null":
        texto, nivel = texto_expr(no[1], 5) + (" IS NOT NULL" if no[2] else " IS NULL"), 4
    else:
        chave = f"{tipo}_{no[1]}" if tipo in ("logico", "conta") else tipo
        nivel = _NIVEL[chave]
        operador = no[1].upper() if tipo == "logico" else no[1]
        texto = f"{texto_expr(no[2], nivel)} {operador} {texto_expr(no[3], nivel + 1)}"
    return f"({texto})" if nivel < nivel_pai else texto


def texto_comando(c) -> str:
    if c["t"] == "let":
        return f"LET {c['nome']} = {texto_expr(c['expr'])}"
    if c["t"] == "return":
        return "RETURN" + (f" {texto_expr(c['expr'])}" if c["expr"] is not None else "")
    return f"{c['t'].upper()} {texto_expr(c['cond'])}"


# ---- execucao --------------------------------------------------------------
def _avaliar(no, ambiente, conhecidas):
    tipo = no[0]
    if tipo == "num":
        return no[1]
    if tipo == "nulo":
        return None
    if tipo == "var":
        if no[1] not in conhecidas:
            raise Erro4GL(f"variável '{no[1]}' não foi declarada")
        return ambiente.get(no[1])
    if tipo == "negativo":
        valor = _avaliar(no[1], ambiente, conhecidas)
        return None if valor is None else -valor
    if tipo == "nao":
        return not bool(_avaliar(no[1], ambiente, conhecidas))
    if tipo == "is_null":
        e_nulo = _avaliar(no[1], ambiente, conhecidas) is None
        return (not e_nulo) if no[2] else e_nulo
    if tipo == "logico":
        esquerda = bool(_avaliar(no[2], ambiente, conhecidas))
        if no[1] == "and":
            return esquerda and bool(_avaliar(no[3], ambiente, conhecidas))
        return esquerda or bool(_avaliar(no[3], ambiente, conhecidas))
    a = _avaliar(no[2], ambiente, conhecidas)
    b = _avaliar(no[3], ambiente, conhecidas)
    if tipo == "compara":
        if a is None or b is None:        # em SQL/4GL, comparar com NULL nunca e verdadeiro
            return False
        return {"<": a < b, "<=": a <= b, ">": a > b, ">=": a >= b, "=": a == b, "<>": a != b}[no[1]]
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


class _Retorno(Exception):
    def __init__(self, valor):
        self.valor = valor


def executar_funcao(programa, entradas, epsilon=EPSILON_PADRAO, limite: int = 3000):
    """Roda a funcao com as entradas dadas.

    Devolve {"valor", "erro", "trilha"}. A trilha e a lista dos comandos
    executados, na ordem: (id do comando, desvio), onde desvio e True/False
    nos IF e WHILE e None nos demais. E dela que saem o caminho no grafo e a
    cobertura de fluxo de dados."""
    ambiente = dict(zip(programa["parametros"], entradas))
    conhecidas, trilha, passos = programa["conhecidas"], [], [0]

    def rodar(comandos):
        for c in comandos:
            passos[0] += 1
            if passos[0] > limite:
                raise Erro4GL(f"laço sem fim (mais de {limite} passos)")
            if c["t"] == "let":
                trilha.append((c["id"], None))
                valor = _avaliar(c["expr"], ambiente, conhecidas)
                if isinstance(valor, Decimal):    # variavel DECIMAL(p,e) arredonda na escala
                    valor = valor.quantize(epsilon, ROUND_HALF_UP)
                ambiente[c["nome"]] = valor
            elif c["t"] == "return":
                trilha.append((c["id"], None))
                raise _Retorno(None if c["expr"] is None else _avaliar(c["expr"], ambiente, conhecidas))
            elif c["t"] == "if":
                desvio = _desvio(c)
                rodar(c["entao"] if desvio else c["senao"])
            else:                                  # while
                while _desvio(c):
                    rodar(c["corpo"])
                    passos[0] += 1
                    if passos[0] > limite:
                        raise Erro4GL(f"laço sem fim (mais de {limite} passos)")

    def _desvio(c):
        try:
            resultado = bool(_avaliar(c["cond"], ambiente, conhecidas))
        except Erro4GL:
            trilha.append((c["id"], None))
            raise
        trilha.append((c["id"], resultado))
        return resultado

    try:
        rodar(programa["comandos"])
        valor = None                               # funcao terminou sem RETURN
    except _Retorno as retorno:
        valor = retorno.valor
    except Erro4GL as problema:
        return {"valor": None, "erro": str(problema), "trilha": trilha}
    except (ArithmeticError, RecursionError) as problema:
        return {"valor": None, "erro": f"erro de cálculo ({type(problema).__name__})", "trilha": trilha}
    if isinstance(valor, bool):
        valor = Decimal(int(valor))
    if isinstance(valor, Decimal):
        try:
            valor = valor.quantize(epsilon, ROUND_HALF_UP)
        except ArithmeticError:
            return {"valor": None, "erro": "resultado grande demais", "trilha": trilha}
    return {"valor": valor, "erro": None, "trilha": trilha}


def assinatura(resultado):
    """Resumo do resultado para comparar duas execucoes (valor ou 'ERRO')."""
    return "ERRO" if resultado["erro"] else resultado["valor"]


# ---- localizar funcoes no arquivo ------------------------------------------
def localizar_funcao(fonte: str, nome: str = None):
    """Acha 'FUNCTION nome(params) ... END FUNCTION' (ou a primeira funcao, se
    nome for None). Devolve {"nome", "parametros", "corpo", "linha"} ou None."""
    alvo = re.escape(nome) if nome else r"[A-Za-z_]\w*"
    achado = re.search(rf"FUNCTION\s+({alvo})\s*\((.*?)\)(.*?)END\s+FUNCTION", fonte,
                       re.IGNORECASE | re.DOTALL)
    if not achado:
        return None
    return {"nome": achado.group(1),
            "parametros": [p.strip().lower() for p in achado.group(2).split(",") if p.strip()],
            "corpo": achado.group(3),
            "linha": fonte.count("\n", 0, achado.start(3)) + 1}


def tipo_decimal(corpo: str):
    """Le o DECIMAL(precisao, escala) da funcao e calcula o Epsilon.

    Epsilon = menor variacao que o tipo consegue representar = 10 ^ -escala.
    DECIMAL(12,2) -> escala 2 -> epsilon = 10^-2 = 0,01 (1 centavo).
    Maior valor  = 10^(precisao - escala) - epsilon = 9.999.999.999,99.
    Devolve (precisao, escala, epsilon, maximo) ou None."""
    achado = re.search(r"DECIMAL\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", corpo, re.IGNORECASE)
    if not achado:
        return None
    precisao, escala = int(achado.group(1)), int(achado.group(2))
    epsilon = Decimal(10) ** -escala
    return precisao, escala, epsilon, Decimal(10) ** (precisao - escala) - epsilon


# ==========================================================================
# 2. CAIXA-BRANCA: GRAFO DE FLUXO DE CONTROLE E McCABE
# ==========================================================================
SAIDA = 0     # id reservado para o ponto de saida da funcao (END FUNCTION)


def construir_grafo(programa, por_bloco: bool = True):
    """Monta o GFC G = (N, E, s).

    por_bloco=True : no = bloco indivisivel de comandos (definicao formal:
                     comandos em sequencia, sem desvio, formam um unico no).
    por_bloco=False: um no por comando (como em alguns slides).

    Primeiro liga comando a comando; depois, se pedido, funde as sequencias."""
    comandos = {c["id"]: c for c in todos_os_comandos(programa["comandos"])}
    sucessores = {}                       # id do comando -> [(destino, rotulo)]

    def ligar(lista, proximo):
        """Liga os comandos da lista de tras para frente. Devolve por onde se entra nela."""
        alvo = proximo
        for c in reversed(lista):
            if c["t"] == "let":
                sucessores[c["id"]] = [(alvo, "")]
            elif c["t"] == "return":
                sucessores[c["id"]] = [(SAIDA, "")]
            elif c["t"] == "if":
                sucessores[c["id"]] = [(ligar(c["entao"], alvo), "V"), (ligar(c["senao"], alvo), "F")]
            else:                         # while: o corpo volta para a condicao
                sucessores[c["id"]] = [(ligar(c["corpo"], c["id"]), "V"), (alvo, "F")]
            alvo = c["id"]
        return alvo

    entrada_cmd = ligar(programa["comandos"], SAIDA)

    # Cada comando comeca como um grupo; no modo por bloco, os grupos em sequencia se fundem.
    grupos = {sid: [sid] for sid in comandos}
    saidas = {sid: list(destinos) for sid, destinos in sucessores.items()}

    def predecessores():
        conta = {sid: 0 for sid in grupos}
        conta[SAIDA] = 0
        for origem, destinos in saidas.items():
            for destino, _ in destinos:
                conta[destino] += 1
        if entrada_cmd != SAIDA:
            conta[entrada_cmd] += 1       # a entrada da funcao conta como uma chegada
        return conta

    if por_bloco:
        mudou = True
        while mudou:
            mudou = False
            chegadas = predecessores()
            for a in sorted(grupos):
                ultimo = comandos[grupos[a][-1]]
                if ultimo["t"] != "let" or len(saidas[a]) != 1:
                    continue
                b = saidas[a][0][0]
                if b in (SAIDA, a) or chegadas[b] != 1:
                    continue
                grupos[a] += grupos.pop(b)        # funde b em a
                saidas[a] = saidas.pop(b)
                mudou = True
                break

    # A saida vira um no proprio so quando mais de um ponto termina a funcao.
    chegam_na_saida = [(a, r) for a, destinos in saidas.items() for d, r in destinos if d == SAIDA]
    saida_virtual = True
    no_final = None
    if len(chegam_na_saida) == 1:
        a = chegam_na_saida[0][0]
        if len(saidas[a]) == 1:
            saida_virtual, no_final = False, a
            saidas[a] = []

    # Numera os nos pela ordem do fonte: 1, 2, 3...
    numero = {lider: i for i, lider in enumerate(sorted(grupos), start=1)}
    if saida_virtual:
        numero[SAIDA] = len(grupos) + 1
    nos = {}
    for lider, membros in grupos.items():
        ultimo = comandos[membros[-1]]
        tipo = "decisao" if ultimo["t"] in ("if", "while") else "comando"
        nos[numero[lider]] = {"id": numero[lider], "comandos": membros, "tipo": tipo,
                              "linhas": sorted({comandos[m]["linha"] for m in membros}),
                              "texto": [texto_comando(comandos[m]) for m in membros]}
    if saida_virtual:
        nos[numero[SAIDA]] = {"id": numero[SAIDA], "comandos": [], "tipo": "saida",
                              "linhas": [], "texto": ["END FUNCTION"]}
    arestas = [(numero[a], numero[d], r) for a in sorted(saidas) for d, r in saidas[a]]
    entrada = numero[entrada_cmd] if entrada_cmd in numero else numero.get(SAIDA, 1)
    saida = numero[SAIDA] if saida_virtual else numero[no_final]

    # Nos que nenhum caminho alcanca a partir da entrada (codigo morto).
    alcancados, fila = {entrada}, [entrada]
    while fila:
        atual = fila.pop()
        for a, d, _ in arestas:
            if a == atual and d not in alcancados:
                alcancados.add(d)
                fila.append(d)
    no_de = {sid: numero[lider] for lider, membros in grupos.items() for sid in membros}
    return {"nos": nos, "arestas": arestas, "entrada": entrada, "saida": saida,
            "saida_virtual": saida_virtual, "por_bloco": por_bloco,
            "no_de": no_de, "lideres": {lider: numero[lider] for lider in grupos},
            "inacessiveis": sorted(set(nos) - alcancados),
            "cmd": comandos, "cmd_suc": sucessores, "cmd_entrada": entrada_cmd}


def _condicoes_simples(no):
    """Conta as condicoes atomicas de um predicado (a < 0 OR b < 0 -> 2)."""
    if no[0] == "logico":
        return _condicoes_simples(no[2]) + _condicoes_simples(no[3])
    if no[0] == "nao":
        return _condicoes_simples(no[1])
    return 1


def metricas_mccabe(grafo):
    """N, E, P, R e V(G) pelos tres metodos de McCabe.

    Metodo 1 (topologico): V(G) = E - N + 2
    Metodo 2 (logico)    : V(G) = P + 1        (P = nos predicativos)
    Metodo 3 (espacial)  : V(G) = R            (regioes, contando a externa)"""
    n, e = len(grafo["nos"]), len(grafo["arestas"])
    p = sum(1 for no in grafo["nos"].values() if no["tipo"] == "decisao")
    # Regioes internas = arestas que fecham ciclo no grafo sem direcao. Conta-se
    # montando uma arvore geradora: cada aresta que liga dois nos ja ligados fecha uma regiao.
    chefe = {no: no for no in grafo["nos"]}

    def raiz(x):
        while chefe[x] != x:
            chefe[x] = chefe[chefe[x]]
            x = chefe[x]
        return x

    internas = 0
    for a, b, _ in grafo["arestas"]:
        ra, rb = raiz(a), raiz(b)
        if ra == rb:
            internas += 1
        else:
            chefe[ra] = rb
    componentes = len({raiz(no) for no in grafo["nos"]})
    condicoes = sum(_condicoes_simples(grafo["cmd"][no["comandos"][-1]]["cond"])
                    for no in grafo["nos"].values() if no["tipo"] == "decisao")
    v1, v2, v3 = e - n + 2, p + 1, internas + 1
    return {"N": n, "E": e, "P": p, "R": internas + 1, "regioes_internas": internas,
            "v_topologico": v1, "v_logico": v2, "v_espacial": v3, "V": v2,
            "coincidem": v1 == v2 == v3, "componentes": componentes,
            "condicoes_simples": condicoes, "v_condicoes": condicoes + 1}


def enumerar_caminhos(grafo, limite: int = 400):
    """Caminhos completos (da entrada a saida), passando no maximo uma vez por
    cada aresta. Com lacos o numero real de caminhos nao tem limite; aqui cada
    laco aparece percorrido zero ou uma vez."""
    saindo = {}
    for indice, (a, _, _) in enumerate(grafo["arestas"]):
        saindo.setdefault(a, []).append(indice)
    caminhos = []

    def andar(no, nos, arestas, usadas):
        if len(caminhos) >= limite:
            return
        if no == grafo["saida"]:
            caminhos.append({"nos": tuple(nos), "arestas": tuple(arestas)})
            return
        for indice in saindo.get(no, []):
            if indice not in usadas:
                destino = grafo["arestas"][indice][1]
                andar(destino, nos + [destino], arestas + [indice], usadas | {indice})

    andar(grafo["entrada"], [grafo["entrada"]], [], frozenset())
    return caminhos


def caminhos_basicos(grafo, caminhos):
    """Escolhe um conjunto de caminhos linearmente independentes (o 'conjunto
    basico' de McCabe). Um caminho entra se nao for combinacao dos ja escolhidos."""
    total = len(grafo["arestas"])
    base, escolhidos = [], []
    for indice, caminho in enumerate(caminhos):
        vetor = [Fraction(0)] * total
        for aresta in caminho["arestas"]:
            vetor[aresta] += 1
        for pivo, linha in base:                   # eliminacao de Gauss
            if vetor[pivo] != 0:
                fator = vetor[pivo] / linha[pivo]
                vetor = [v - fator * l for v, l in zip(vetor, linha)]
        pivo = next((i for i, v in enumerate(vetor) if v != 0), None)
        if pivo is not None:
            base.append((pivo, vetor))
            escolhidos.append(indice)
    return escolhidos


def percurso(grafo, resultado):
    """Converte a trilha de uma execucao no caminho percorrido no grafo:
    {"nos": [1, 3, 5...], "arestas": [indices das arestas usadas]}."""
    indice_da_aresta = {}
    for indice, aresta in enumerate(grafo["arestas"]):
        indice_da_aresta.setdefault(aresta, indice)
    nos, arestas, desvio_anterior = [], [], None

    def entrar(no):
        if nos:
            rotulo = ""
            if grafo["nos"][nos[-1]]["tipo"] == "decisao" and desvio_anterior is not None:
                rotulo = "V" if desvio_anterior else "F"
            chave = (nos[-1], no, rotulo)
            if chave in indice_da_aresta:
                arestas.append(indice_da_aresta[chave])
        nos.append(no)

    for comando, desvio in resultado["trilha"]:
        if comando in grafo["lideres"]:
            entrar(grafo["lideres"][comando])
        desvio_anterior = desvio
    if resultado["erro"] is None and grafo["saida_virtual"]:
        entrar(grafo["saida"])
    return {"nos": tuple(nos), "arestas": tuple(arestas)}


# ==========================================================================
# 3. FLUXO DE DADOS: DEFINICOES, USOS E PARES DEF-USO
# ==========================================================================
def analisar_fluxo(programa, grafo):
    """Calcula, para cada variavel, onde ela e definida (d), onde tem uso
    computacional (c-uso, em um no) e uso predicativo (p-uso, em uma aresta),
    e os pares Def-Uso ligados por um caminho livre de definicao.

    A analise e feita comando a comando e depois projetada nos nos do grafo.
    Par c-uso: (variavel, no_def, "c", no_uso)
    Par p-uso: (variavel, no_def, "p", indice_da_aresta)"""
    comandos, sucessores = grafo["cmd"], grafo["cmd_suc"]
    indice_da_aresta = {}
    for indice, aresta in enumerate(grafo["arestas"]):
        indice_da_aresta.setdefault(aresta, indice)

    def no_do(comando):
        return grafo["saida"] if comando == SAIDA else grafo["no_de"][comando]

    usos = {sid: variaveis_da_expressao(c[CAMPO_EXPR[c["t"]]]) for sid, c in comandos.items()}
    definicoes = [("entrada", p) for p in programa["parametros"]]
    definicoes += [(sid, c["nome"]) for sid, c in sorted(comandos.items()) if c["t"] == "let"]

    projecao = {}            # par no nivel de comando -> par no nivel de no
    pares = {}               # par no nivel de no -> detalhes
    usos_alcancados = set()
    for origem, variavel in definicoes:
        no_def = grafo["entrada"] if origem == "entrada" else no_do(origem)
        inicio = [grafo["cmd_entrada"]] if origem == "entrada" else [d for d, _ in sucessores[origem]]
        fila, vistos = list(inicio), set()
        while fila:
            atual = fila.pop(0)
            if atual == SAIDA or atual in vistos:
                continue
            vistos.add(atual)
            comando = comandos[atual]
            if variavel in usos[atual]:
                usos_alcancados.add((atual, variavel))
                if comando["t"] in ("if", "while"):
                    for destino, rotulo in sucessores[atual]:
                        aresta = indice_da_aresta[(no_do(atual), no_do(destino), rotulo)]
                        par = (variavel, no_def, "p", aresta)
                        projecao[((origem, variavel), atual, rotulo)] = par
                        pares.setdefault(par, {"linha_uso": comando["linha"]})
                else:
                    par = (variavel, no_def, "c", no_do(atual))
                    projecao[((origem, variavel), atual, None)] = par
                    pares.setdefault(par, {"linha_uso": comando["linha"]})
            if comando["t"] == "let" and comando["nome"] == variavel:
                continue                         # redefinida: o caminho deixa de ser livre
            fila += [d for d, _ in sucessores[atual]]

    # Tabela por variavel, no formato do slide: no de definicao, nos c-uso, arestas p-uso.
    tabela = {}
    for origem, variavel in definicoes:
        linha = tabela.setdefault(variavel, {"defs": set(), "c_usos": set(), "p_usos": set()})
        linha["defs"].add(grafo["entrada"] if origem == "entrada" else no_do(origem))
    for variavel, _, tipo, alvo in pares:
        tabela.setdefault(variavel, {"defs": set(), "c_usos": set(), "p_usos": set()})
        (tabela[variavel]["c_usos"] if tipo == "c" else tabela[variavel]["p_usos"]).add(alvo)

    # Anomalias: uso que nenhuma definicao alcanca e definicao que nenhum uso aproveita.
    sem_definicao = sorted({(v, comandos[sid]["linha"]) for sid, lista in usos.items() for v in lista
                            if (sid, v) not in usos_alcancados})
    com_uso = {(par[0], par[1]) for par in pares}
    sem_uso = sorted({(v, grafo["entrada"] if o == "entrada" else no_do(o)) for o, v in definicoes}
                     - com_uso)
    return {"pares": sorted(pares, key=lambda p: (programa["variaveis"].index(p[0]), p[1], p[2], p[3])),
            "projecao": projecao, "tabela": tabela, "usos": usos,
            "uso_sem_definicao": sem_definicao, "definicao_sem_uso": sem_uso}


def pares_exercitados(programa, grafo, fluxo, resultado):
    """Pares Def-Uso que uma execucao exercitou (segue a trilha e lembra, para
    cada variavel, qual foi a ultima definicao)."""
    comandos = grafo["cmd"]
    ultima = {p: ("entrada", p) for p in programa["parametros"]}
    cobertos = set()
    for comando, desvio in resultado["trilha"]:
        c = comandos[comando]
        for variavel in fluxo["usos"][comando]:
            if variavel in ultima:
                if c["t"] in ("if", "while"):
                    chave = (ultima[variavel], comando, None if desvio is None else ("V" if desvio else "F"))
                else:
                    chave = (ultima[variavel], comando, None)
                if chave in fluxo["projecao"]:
                    cobertos.add(fluxo["projecao"][chave])
        if c["t"] == "let":
            ultima[c["nome"]] = (comando, c["nome"])
    return cobertos


# ==========================================================================
# 4. TESTE DE MUTACAO
# ==========================================================================
OPERADORES = {
    "AOR": "Aritmético: troca + - * /",
    "ROR": "Relacional: troca < <= > >= = <> (e IS NULL por IS NOT NULL)",
    "COR": "Condicional: troca AND por OR",
    "LVR": "Variável local: troca uma variável por outra",
}


def _mutacoes_da_expressao(no, variaveis):
    """Gera (operador, expressao mutada) para cada troca possivel na expressao."""
    tipo = no[0]
    if tipo == "var":
        for outra in variaveis:
            if outra != no[1]:
                yield "LVR", ("var", outra)
        return
    if tipo == "conta":
        for novo in "+-*/":
            if novo != no[1]:
                yield "AOR", ("conta", novo, no[2], no[3])
    elif tipo == "compara":
        for novo in ("<", "<=", ">", ">=", "=", "<>"):
            if novo != no[1]:
                yield "ROR", ("compara", novo, no[2], no[3])
    elif tipo == "is_null":
        yield "ROR", ("is_null", no[1], not no[2])
    elif tipo == "logico":
        yield "COR", ("logico", "or" if no[1] == "and" else "and", no[2], no[3])
    # Desce nos pedacos da expressao e remonta com um pedaco trocado.
    for posicao, parte in enumerate(no):
        if isinstance(parte, tuple):
            for operador, mutada in _mutacoes_da_expressao(parte, variaveis):
                yield operador, no[:posicao] + (mutada,) + no[posicao + 1:]


def _trocar_expressao(comandos, alvo, nova):
    """Copia a arvore de comandos trocando a expressao do comando 'alvo'."""
    copia = []
    for c in comandos:
        novo = dict(c)
        if c["id"] == alvo:
            novo[CAMPO_EXPR[c["t"]]] = nova
        for filhos in ("entao", "senao", "corpo"):
            if filhos in c:
                novo[filhos] = _trocar_expressao(c[filhos], alvo, nova)
        copia.append(novo)
    return copia


def gerar_mutantes(programa):
    """Um mutante = o programa com UMA pequena alteracao (defeito proposital)."""
    mutantes = []
    for c in todos_os_comandos(programa["comandos"]):
        expressao = c[CAMPO_EXPR[c["t"]]]
        if expressao is None:
            continue
        for operador, mutada in _mutacoes_da_expressao(expressao, programa["variaveis"]):
            alterado = dict(c)
            alterado[CAMPO_EXPR[c["t"]]] = mutada
            mutantes.append({
                "id": f"M{len(mutantes) + 1:02d}", "operador": operador, "linha": c["linha"],
                "comando": c["id"], "original": texto_comando(c), "mutado": texto_comando(alterado),
                "programa": {**programa, "comandos": _trocar_expressao(programa["comandos"], c["id"], mutada)},
            })
    return mutantes


def executar_mutantes(programa, mutantes, entradas, epsilon=EPSILON_PADRAO, rotulos=None):
    """Roda a suite em cada mutante. O mutante MORRE quando, em pelo menos um
    caso, o seu resultado e diferente do resultado do programa original."""
    rotulos = rotulos or [f"T{i + 1}" for i in range(len(entradas))]
    originais = [assinatura(executar_funcao(programa, e, epsilon)) for e in entradas]
    resultado = []
    for m in mutantes:
        morto_por = None
        for rotulo, entrada, original in zip(rotulos, entradas, originais):
            if assinatura(executar_funcao(m["programa"], entrada, epsilon)) != original:
                morto_por = rotulo
                break
        resultado.append({**{k: v for k, v in m.items() if k != "programa"},
                          "estado": "Morto" if morto_por else "Vivo", "morto_por": morto_por or ""})
    return resultado


def escore_de_mutacao(mortos: int, total: int, equivalentes: int):
    """MS = Md / (Mt - Me), em porcentagem. Devolve None se nao ha o que medir."""
    return None if total - equivalentes <= 0 else 100.0 * mortos / (total - equivalentes)


# ==========================================================================
# SONDAGEM: procura entradas para o que a suite ainda nao cobriu
# ==========================================================================
def entradas_de_sondagem(quantos: int, epsilon=EPSILON_PADRAO, maximo: int = 1500):
    """Combina alguns valores tipicos (fronteira, pequenos, negativos, nulo) para
    cada parametro. Serve para sugerir casos novos e apontar o que parece inalcancavel."""
    valores = [Decimal(1), Decimal(2), Decimal(3), Decimal(0), Decimal(10), Decimal(5),
               epsilon, -epsilon, Decimal(-10), None]
    combinacoes = list(itertools.product(valores, repeat=quantos)) if quantos else [()]
    if len(combinacoes) > maximo:
        combinacoes = random.Random(2026).sample(combinacoes, maximo)
    return combinacoes


def sondar(programa, grafo, fluxo, epsilon=EPSILON_PADRAO):
    """Executa as entradas de sondagem no programa original e guarda o que cada uma alcanca."""
    execucoes = []
    for entrada in entradas_de_sondagem(len(programa["parametros"]), epsilon):
        resultado = executar_funcao(programa, entrada, epsilon)
        caminho = percurso(grafo, resultado)
        execucoes.append({"entrada": entrada, "assinatura": assinatura(resultado),
                          "nos": caminho["nos"], "arestas": set(caminho["arestas"]),
                          "pares": pares_exercitados(programa, grafo, fluxo, resultado)})
    return execucoes


# ==========================================================================
# ANALISE COMPLETA (o que a pagina chama)
# ==========================================================================
def analisar(parametros, corpo, linha_inicial, epsilon, casos, por_bloco=True, nome=""):
    """Faz toda a analise estrutural, de fluxo de dados e de mutacao.

    casos: lista de (rotulo, entradas). Devolve um dicionario so com dados
    simples (listas, numeros, textos), pronto para virar tabela."""
    programa = compilar_funcao(parametros, corpo, linha_inicial, nome)
    grafo = construir_grafo(programa, por_bloco)
    metricas = metricas_mccabe(grafo)
    caminhos = enumerar_caminhos(grafo)
    basicos = set(caminhos_basicos(grafo, caminhos))
    fluxo = analisar_fluxo(programa, grafo)

    # ---- execucao da suite: caminho, nos e arestas de cada caso ------------
    execucoes, nos_cobertos, arestas_cobertas, pares_cobertos = [], set(), set(), {}
    for rotulo, entrada in casos:
        resultado = executar_funcao(programa, entrada, epsilon)
        caminho = percurso(grafo, resultado)
        exercitados = pares_exercitados(programa, grafo, fluxo, resultado)
        nos_cobertos |= set(caminho["nos"])
        arestas_cobertas |= set(caminho["arestas"])
        for par in exercitados:
            pares_cobertos.setdefault(par, []).append(rotulo)
        execucoes.append({"caso": rotulo, "entrada": tuple(entrada), "valor": resultado["valor"],
                          "erro": resultado["erro"], "nos": caminho["nos"],
                          "arestas": caminho["arestas"],
                          "nos_distintos": len(set(caminho["nos"])),
                          "arestas_distintas": len(set(caminho["arestas"]))})

    sondagem = sondar(programa, grafo, fluxo, epsilon)

    def sugerir(alcanca):
        """Primeira entrada de sondagem que alcanca o item pedido (ou None)."""
        return next((s["entrada"] for s in sondagem if alcanca(s)), None)

    # ---- caminhos -----------------------------------------------------------
    lista_caminhos = []
    for indice, caminho in enumerate(caminhos):
        cobrem = [x["caso"] for x in execucoes if x["nos"] == caminho["nos"]]
        lista_caminhos.append({"nos": caminho["nos"], "basico": indice in basicos, "casos": cobrem,
                               "sugestao": None if cobrem else sugerir(lambda s, c=caminho: s["nos"] == c["nos"])})

    # ---- arestas ------------------------------------------------------------
    lista_arestas = []
    for indice, (a, b, rotulo) in enumerate(grafo["arestas"]):
        coberta = indice in arestas_cobertas
        lista_arestas.append({"indice": indice, "de": a, "para": b, "rotulo": rotulo, "coberta": coberta,
                              "sugestao": None if coberta else sugerir(lambda s, i=indice: i in s["arestas"])})

    # ---- pares Def-Uso ------------------------------------------------------
    lista_pares = []
    for par in fluxo["pares"]:
        variavel, no_def, tipo, alvo = par
        cobrem = pares_cobertos.get(par, [])
        aresta = grafo["arestas"][alvo] if tipo == "p" else None
        lista_pares.append({"variavel": variavel, "no_def": no_def, "tipo": tipo,
                            "uso": (aresta[0], aresta[1]) if aresta else alvo,
                            "rotulo": aresta[2] if aresta else "", "casos": cobrem,
                            "sugestao": None if cobrem else sugerir(lambda s, p=par: p in s["pares"])})

    def cobertura(itens):
        return (sum(1 for i in itens if i), len(itens))

    definicoes = {}
    for p in lista_pares:
        definicoes.setdefault((p["variavel"], p["no_def"]), []).append(bool(p["casos"]))
    criterios = {
        "Todas-Definições": cobertura([any(v) for v in definicoes.values()]),
        "Todos-c-Usos": cobertura([bool(p["casos"]) for p in lista_pares if p["tipo"] == "c"]),
        "Todos-p-Usos": cobertura([bool(p["casos"]) for p in lista_pares if p["tipo"] == "p"]),
        "Todos-Usos": cobertura([bool(p["casos"]) for p in lista_pares]),
    }

    # ---- mutantes -----------------------------------------------------------
    mutantes = gerar_mutantes(programa)
    avaliados = executar_mutantes(programa, mutantes, [e for _, e in casos], epsilon,
                                  [r for r, _ in casos])
    for mutante, avaliado in zip(mutantes, avaliados):
        avaliado["sugestao"], avaliado["provavel_equivalente"] = None, False
        if avaliado["estado"] == "Vivo":
            for s in sondagem:
                if assinatura(executar_funcao(mutante["programa"], s["entrada"], epsilon)) != s["assinatura"]:
                    avaliado["sugestao"] = s["entrada"]
                    break
            avaliado["provavel_equivalente"] = avaliado["sugestao"] is None

    return {
        "nome": nome, "parametros": programa["parametros"], "variaveis": programa["variaveis"],
        "grafo": {"nos": grafo["nos"], "arestas": grafo["arestas"], "entrada": grafo["entrada"],
                  "saida": grafo["saida"], "saida_virtual": grafo["saida_virtual"],
                  "inacessiveis": grafo["inacessiveis"], "por_bloco": por_bloco},
        "metricas": metricas, "execucoes": execucoes, "caminhos": lista_caminhos,
        "arestas": lista_arestas,
        "nos_cobertos": sorted(nos_cobertos), "arestas_cobertas": sorted(arestas_cobertas),
        "cobertura": {"Todos-Nós": (len(nos_cobertos), metricas["N"]),
                      "Todas-Arestas": (len(arestas_cobertas), metricas["E"]),
                      "Todos-Caminhos": cobertura([bool(c["casos"]) for c in lista_caminhos])},
        "tem_laco": any(c["t"] == "while" for c in todos_os_comandos(programa["comandos"])),
        "fluxo_tabela": {v: {k: sorted(x) for k, x in linha.items()} for v, linha in fluxo["tabela"].items()},
        "pares": lista_pares, "criterios": criterios,
        "uso_sem_definicao": fluxo["uso_sem_definicao"], "definicao_sem_uso": fluxo["definicao_sem_uso"],
        "mutantes": avaliados, "sondagens": len(sondagem),
    }


def grafo_em_dot(grafo, nos_cobertos=None, arestas_cobertas=None) -> str:
    """Desenho do grafo na linguagem DOT (Graphviz). Losango = no predicativo;
    circulo duplo = saida; tracejado = nao coberto pela suite."""
    cor, cor_falta = "#1f4e79", "#eb6834"
    linhas = ['digraph GFC {', '  rankdir=TB; bgcolor="transparent"; nodesep=0.5; ranksep=0.45;',
              f'  node [fontname="IBM Plex Sans, Segoe UI, Arial, sans-serif", fontsize=12, color="{cor}", fontcolor="#1b2a3d", penwidth=1.6];',
              f'  edge [fontname="IBM Plex Sans, Segoe UI, Arial, sans-serif", fontsize=10, color="{cor}", fontcolor="#1b2a3d", arrowsize=0.8];',
              '  inicio [shape=point, width=0.12, color="#1b2a3d"];',
              f'  inicio -> n{grafo["entrada"]};']
    for no in grafo["nos"].values():
        if no["linhas"]:
            trecho = (f"L{no['linhas'][0]}" if len(no["linhas"]) == 1
                      else f"L{no['linhas'][0]}-{no['linhas'][-1]}")
        else:
            trecho = "fim"
        forma = "diamond" if no["tipo"] == "decisao" else ("doublecircle" if no["id"] == grafo["saida"] else "circle")
        estilos = ["filled"] if no["tipo"] == "decisao" else []
        estilo = ', fillcolor="#e1eafa"' if no["tipo"] == "decisao" else ""
        if nos_cobertos is not None and no["id"] not in nos_cobertos:
            estilos.append("dashed")
            estilo += f', color="{cor_falta}"'
        if estilos:
            estilo += f', style="{",".join(estilos)}"'
        linhas.append(f'  n{no["id"]} [label=<<B>{no["id"]}</B><BR/><FONT POINT-SIZE="9">{trecho}</FONT>>, '
                      f'shape={forma}{estilo}];')
    for indice, (a, b, rotulo) in enumerate(grafo["arestas"]):
        estilo = ""
        if arestas_cobertas is not None and indice not in arestas_cobertas:
            estilo = f', style=dashed, color="{cor_falta}"'
        linhas.append(f'  n{a} -> n{b} [label="{rotulo}"{estilo}];')
    linhas.append("}")
    return "\n".join(linhas)


# ==========================================================================
# 5. VALIDACAO: EXEMPLOS DAS AULAS COM GABARITO
# ==========================================================================
EXEMPLOS = [
    {
        "chave": "if_else", "titulo": "IF-ELSE", "aula": "Aula de 28/09, exemplo 1",
        "por_bloco": True,
        "fonte": """FUNCTION exemplo_if_else(saldo)
    DEFINE saldo, resultado DECIMAL(12,2)
    IF saldo > 0 THEN
        LET resultado = 1          # aprovar_compra()
    ELSE
        LET resultado = 0          # recusar_compra()
    END IF
    RETURN resultado               # finalizar()
END FUNCTION
""",
        "casos": [("T1", (10,)), ("T2", (0,))],
        "gabarito": {"N": 4, "E": 4, "P": 1, "R": 2, "V(G)": 2},
    },
    {
        "chave": "if_while", "titulo": "IF com WHILE", "aula": "Aula de 28/09, exemplo 2",
        "por_bloco": True,
        "fonte": """FUNCTION exemplo_if_while(saldo, dias_atraso)
    DEFINE saldo, dias_atraso, multa DECIMAL(12,2)
    LET multa = 0
    IF saldo > 0 THEN
        WHILE dias_atraso > 0
            LET multa = multa + 2              # cobrar_multa()
            LET dias_atraso = dias_atraso - 1
        END WHILE
    END IF
    RETURN multa
END FUNCTION
""",
        "casos": [("T1", (100, 3)), ("T2", (100, 0)), ("T3", (0, 3))],
        "gabarito": {"P": 2, "R": 3, "V(G)": 3, "E - N": 1},
        "observacao": "O slide desenha N = 5 e E = 6 porque cria um nó para o ramo falso do IF, que "
                      "não tem comando. A ferramenta não cria nó vazio (N = 4, E = 5). A diferença "
                      "E − N é a mesma, por isso V(G), P e R conferem.",
    },
    {
        "chave": "bhaskara", "titulo": "Função Bhaskara", "aula": "Aula de 09/09, laboratório estrutural A",
        "por_bloco": True,
        "fonte": """FUNCTION bhaskara(a, b, c)
    DEFINE a, b, c, delta, raizes DECIMAL(12,2)
    LET delta = (b * b) - (4 * a * c)
    IF delta < 0 THEN
        LET raizes = 0                 # sem raizes
    ELSE
        IF delta = 0 THEN
            LET raizes = 1             # raiz unica
        ELSE
            LET raizes = 2             # duas raizes
        END IF
    END IF
    RETURN raizes
END FUNCTION
""",
        "casos": [("Delta = -4", (1, 0, 1)), ("Delta = 0", (1, 2, 1)), ("Delta = 21", (1, 5, 1))],
        "gabarito": {"N": 6, "Caminhos completos": 3, "Caminho de Delta = -4": "1-2-6",
                     "Caminho de Delta = 0": "1-3-4-6", "Caminho de Delta = 21": "1-3-5-6",
                     "Todos-Nós": "100%", "Todas-Arestas": "100%"},
        "observacao": "A função devolve a quantidade de raízes reais (0, 1 ou 2); a estrutura de "
                      "decisão é a mesma do slide.",
    },
    {
        "chave": "pares_du", "titulo": "Pares Def-Uso", "aula": "Aula de 30/09, prática de pares DU",
        "por_bloco": False,
        "fonte": """FUNCTION exemplo_du(x)
    DEFINE v, x, calc DECIMAL(12,2)
    LET v = 100
    LET x = x                      # read(x)
    IF v > x THEN
        LET calc = v * 0.9
    END IF
    RETURN calc
END FUNCTION
""",
        "casos": [("T1", (50,)), ("T2", (200,))],
        "gabarito": {"N": 5, "Definição de v": "1", "c-uso de v": "4", "p-uso de v": "(3,4), (3,5)"},
        "observacao": "Aqui o grafo usa um nó por comando, como no slide.",
    },
    {
        "chave": "maior", "titulo": "Mutantes de maior(a, b)", "aula": "Aula de 30/09, exercício de mutação",
        "por_bloco": True,
        "fonte": """FUNCTION maior(a, b)
    DEFINE a, b DECIMAL(12,2)
    IF a > b THEN
        RETURN a
    ELSE
        RETURN b
    END IF
END FUNCTION
""",
        "casos": [("T1", (3, 2)), ("T2", (2, 2))],
        "mutantes_do_slide": [("#1", "IF a >= b"), ("#2", "IF a < b"), ("#3", "IF a <= b"),
                              ("#4", "IF a = b"), ("#5", "RETURN a")],
        "gabarito": {"Mutante #1 (a >= b)": "Vivo", "Mutante #2 (a < b)": "Morto",
                     "Mutante #3 (a <= b)": "Morto", "Mutante #4 (a = b)": "Morto",
                     "Mutante #5 (else return a)": "Vivo", "Md": 3, "MS": "60%"},
        "observacao": "O slide lista 5 mutantes e a validação usa exatamente esses 5. No laboratório a "
                      "ferramenta gera todos os mutantes dos quatro operadores, por isso o escore de lá é outro.",
    },
    {
        "chave": "triangulo", "titulo": "Triângulo e valor limite", "aula": "Aula de 26/08, problema do triângulo",
        "por_bloco": True,
        "fonte": """FUNCTION triangulo(a, b, c)
    DEFINE a, b, c DECIMAL(12,2)
    IF a + b > c THEN
        RETURN 1                   # forma triangulo
    ELSE
        RETURN 0
    END IF
END FUNCTION
""",
        "casos": [("(3, 4, 5)", (3, 4, 5)), ("(1, 2, 3)", (1, 2, 3))],
        "mutantes_do_slide": [(">=", "IF a + b >= c")],
        "gabarito": {"Mutante >= com (3, 4, 5)": "Vivo", "Mutante >= com (1, 2, 3)": "Morto"},
    },
]


def _para_decimais(entrada):
    return tuple(None if v is None else Decimal(str(v)) for v in entrada)


def analisar_fonte(fonte, casos, por_bloco=True):
    """Analisa a primeira funcao encontrada em um texto (usado nos exemplos e no laboratorio)."""
    funcao = localizar_funcao(fonte)
    if funcao is None:
        raise Erro4GL("não encontrei 'FUNCTION nome(...) ... END FUNCTION' no texto")
    tipo = tipo_decimal(funcao["corpo"])
    epsilon = tipo[2] if tipo else EPSILON_PADRAO
    casos = [(rotulo, _para_decimais(entrada)) for rotulo, entrada in casos]
    return analisar(funcao["parametros"], funcao["corpo"], funcao["linha"], epsilon, casos,
                    por_bloco, funcao["nome"])


def _estados_dos_mutantes_do_slide(exemplo, casos):
    """Roda so os mutantes citados no slide. Devolve {rotulo: (estado, morto_por)}."""
    funcao = localizar_funcao(exemplo["fonte"])
    programa = compilar_funcao(funcao["parametros"], funcao["corpo"], funcao["linha"])
    gerados = gerar_mutantes(programa)
    escolhidos = []
    for rotulo, texto in exemplo["mutantes_do_slide"]:
        achado = next(m for m in gerados if m["mutado"] == texto and m["original"] != texto
                      and (rotulo != "#5" or m["original"] == "RETURN b"))
        escolhidos.append((rotulo, achado))
    entradas = [_para_decimais(e) for _, e in casos]
    avaliados = executar_mutantes(programa, [m for _, m in escolhidos], entradas, EPSILON_PADRAO,
                                  [r for r, _ in casos])
    return {rotulo: avaliado["estado"] for (rotulo, _), avaliado in zip(escolhidos, avaliados)}


def validar_exemplos():
    """Compara o que o motor calcula com o gabarito dos slides.
    Devolve linhas {exemplo, aula, medida, esperado, obtido, confere}."""
    linhas = []
    for exemplo in EXEMPLOS:
        analise = analisar_fonte(exemplo["fonte"], exemplo["casos"], exemplo["por_bloco"])
        m = analise["metricas"]
        obtido = {"N": m["N"], "E": m["E"], "P": m["P"], "R": m["R"], "V(G)": m["V"],
                  "E - N": m["E"] - m["N"], "Caminhos completos": len(analise["caminhos"])}
        for nome, (feito, total) in analise["cobertura"].items():
            obtido[nome] = f"{round(100 * feito / total)}%" if total else "-"
        for execucao in analise["execucoes"]:
            obtido[f"Caminho de {execucao['caso']}"] = "-".join(map(str, execucao["nos"]))
        if exemplo["chave"] == "pares_du":
            v = analise["fluxo_tabela"]["v"]
            obtido["Definição de v"] = ", ".join(map(str, v["defs"]))
            obtido["c-uso de v"] = ", ".join(map(str, v["c_usos"]))
            arestas = analise["grafo"]["arestas"]
            obtido["p-uso de v"] = ", ".join(f"({arestas[i][0]},{arestas[i][1]})" for i in v["p_usos"])
        if exemplo["chave"] == "maior":
            estados = _estados_dos_mutantes_do_slide(exemplo, exemplo["casos"])
            nomes = {"#1": "Mutante #1 (a >= b)", "#2": "Mutante #2 (a < b)", "#3": "Mutante #3 (a <= b)",
                     "#4": "Mutante #4 (a = b)", "#5": "Mutante #5 (else return a)"}
            for rotulo, estado in estados.items():
                obtido[nomes[rotulo]] = estado
            mortos = sum(1 for e in estados.values() if e == "Morto")
            obtido["Md"] = mortos
            obtido["MS"] = f"{round(escore_de_mutacao(mortos, len(estados), 0))}%"
        if exemplo["chave"] == "triangulo":
            for rotulo, entrada in exemplo["casos"]:
                estado = _estados_dos_mutantes_do_slide(exemplo, [(rotulo, entrada)])[">="]
                obtido[f"Mutante >= com {rotulo}"] = estado
        for medida, esperado in exemplo["gabarito"].items():
            linhas.append({"exemplo": exemplo["titulo"], "aula": exemplo["aula"], "medida": medida,
                           "esperado": str(esperado), "obtido": str(obtido.get(medida, "?")),
                           "confere": str(obtido.get(medida, "?")) == str(esperado)})
    return linhas
