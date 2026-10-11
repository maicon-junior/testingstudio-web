"""
caixa_preta.py - Especificacao (oraculo), classes de equivalencia, valor limite e suite.

Funciona para qualquer funcao 4GL com parametros numericos. A especificacao vem
do enunciado ou do manual do programa (nunca do codigo) e diz:
  - a faixa valida de cada parametro (minimo e/ou maximo, se houver);
  - o que fazer com parametro em branco (NULL);
  - o que a funcao devolve quando algum valor e invalido;
  - a formula do resultado nos demais casos (escrita em 4GL).
Sem interface: tudo aqui pode ser testado sozinho.
"""

VERSAO = 2          # conferida pelo app.py (evita misturar versoes no servidor)

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import motor

NULO_OPCOES = {"zero": "vale 0", "invalido": "é inválido (recusa)", "indefinido": "a especificação não diz"}
DISTANCIA_EXTERIOR = Decimal(100)          # quanto o ponto Exterior fica alem da fronteira


class ErroEspecificacao(Exception):
    """A especificacao escrita na pagina tem algum problema."""


# ==========================================================================
# Formatos
# ==========================================================================
def formato_br(valor) -> str:
    """Numero no padrao brasileiro (1.234,56), com as casas do proprio valor. None vira NULL."""
    if valor is None:
        return "NULL"
    casas = max(0, -valor.as_tuple().exponent) if isinstance(valor, Decimal) else 2
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def decimal_ou_none(texto, epsilon=None):
    """'10,5' -> Decimal('10.50') (na escala do tipo). Vazio -> None."""
    if texto is None:
        return None
    if isinstance(texto, float):
        if texto != texto:                       # NaN do pandas
            return None
        texto = repr(texto)
    texto = str(texto).strip().replace(" ", "")
    if not texto:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise ErroEspecificacao(f"'{texto}' não é um número")
    return valor.quantize(epsilon, ROUND_HALF_UP) if epsilon is not None else valor


def ordinal(i: int) -> str:
    return f"{i + 1}º"


# ==========================================================================
# Especificacao
# ==========================================================================
def _parametro(programa, nome):
    return {"nome": nome, "tipo": motor.tipo_da_variavel(programa, nome),
            "minimo": None, "maximo": None, "comum": None, "interior": None}


def especificacao_inicial(programa) -> dict:
    """Especificacao em branco para uma funcao nova: so os tipos vem do codigo."""
    spec = {"params": [_parametro(programa, p) for p in programa["parametros"]],
            "nulo": "indefinido", "retorno_invalido": None, "formula": "", "enunciado": ""}
    completar_valores(spec)
    return spec


def especificacao_de_exemplo(programa):
    """O CAD0001 do manual do laboratorio, ja preenchido (usado so como exemplo)."""
    if programa["nome"].lower() != "cad0001_calcula_valor" or len(programa["parametros"]) != 3:
        return None
    spec = especificacao_inicial(programa)
    for p in spec["params"]:
        p["minimo"] = Decimal("0").quantize(p["tipo"]["epsilon"])
        p["comum"] = Decimal("10").quantize(p["tipo"]["epsilon"])
        p["interior"] = Decimal("100").quantize(p["tipo"]["epsilon"])
    a, b, c = programa["parametros"]
    spec.update(nulo="zero", retorno_invalido=Decimal("-1"), formula=f"({a} * {b}) + {c}", enunciado=(
        "A função recebe três parâmetros decimais monetários (val_param1, val_param2, val_param3). "
        "Parâmetro NULL é tratado como 0,00. Nenhum parâmetro pode ser negativo: se algum for menor que 0,00, "
        "a função retorna -1 (erro). Caso contrário, retorna (val_param1 × val_param2) + val_param3."))
    return spec


def completar_valores(spec) -> None:
    """Preenche 'valor comum' e 'interior' que ficaram em branco, dentro da faixa valida."""
    for p in spec["params"]:
        eps, lo, hi = p["tipo"]["epsilon"], p["minimo"], p["maximo"]
        if lo is not None and hi is not None:
            largura = hi - lo
            comum, interior = lo + largura / 4, lo + largura / 2
            if lo + 10 <= hi:
                comum = lo + 10
            if lo + 100 < hi:
                interior = lo + 100
        elif lo is not None:
            comum, interior = lo + 10, lo + 100
        elif hi is not None:
            comum, interior = hi - 10, hi - 100
        else:
            comum, interior = Decimal(10), Decimal(100)
        if p["comum"] is None:
            p["comum"] = comum.quantize(eps, ROUND_HALF_UP)
        if p["interior"] is None:
            p["interior"] = interior.quantize(eps, ROUND_HALF_UP)


def problemas_da_especificacao(spec) -> list:
    """Avisos sobre o que esta incoerente (faixa invertida, valor comum fora da faixa...)."""
    avisos = []
    for i, p in enumerate(spec["params"]):
        if p["minimo"] is not None and p["maximo"] is not None and p["minimo"] > p["maximo"]:
            avisos.append(f"{p['nome']}: o mínimo é maior que o máximo.")
        for campo, rotulo in (("comum", "valor comum"), ("interior", "valor interior")):
            if p[campo] is not None and fora_da_faixa(p, p[campo]):
                avisos.append(f"{p['nome']}: o {rotulo} ({formato_br(p[campo])}) está fora da faixa válida.")
        if p["comum"] is not None and p["comum"] == p["interior"]:
            avisos.append(f"{p['nome']}: use um valor interior diferente do valor comum, para que o teste "
                          "Interior mude de fato um valor.")
    tem_faixa = any(p["minimo"] is not None or p["maximo"] is not None for p in spec["params"])
    if tem_faixa and spec["retorno_invalido"] is None:
        avisos.append("Há faixa válida, mas falta dizer o que a função devolve para valor fora dela.")
    return avisos


def compilar_formula(spec):
    """A formula vira um pequeno programa 4GL (RETURN formula), executado pelo mesmo motor."""
    texto = (spec["formula"] or "").strip()
    if not texto:
        return None
    nomes = [p["nome"] for p in spec["params"]]
    try:
        programa = motor.compilar_funcao(nomes, f"RETURN {texto}\n", 1, "formula")
    except motor.Erro4GL as erro:
        raise ErroEspecificacao("fórmula: " + str(erro).replace("linha 1: ", ""))
    comandos = programa["comandos"]
    if len(comandos) != 1 or comandos[0]["t"] != "return":
        raise ErroEspecificacao("a fórmula deve ser uma única expressão, como (a * b) + c")
    desconhecidas = [v for v in motor.variaveis_da_expressao(comandos[0]["expr"]) if v not in nomes]
    if desconhecidas:
        raise ErroEspecificacao(f"a fórmula usa {', '.join(desconhecidas)}, que não é parâmetro da função "
                                f"(parâmetros: {', '.join(nomes)})")
    return programa


def fora_da_faixa(p, valor) -> bool:
    return valor is not None and ((p["minimo"] is not None and valor < p["minimo"]) or
                                  (p["maximo"] is not None and valor > p["maximo"]))


def oraculo(spec, formula, entradas, epsilon_resultado):
    """Resultado ESPERADO pela especificacao (nao olha o codigo).
    Devolve (esperado, motivo). esperado None = a especificacao nao define o caso."""
    valores, invalido = [], False
    for p, v in zip(spec["params"], entradas):
        if v is None:
            if spec["nulo"] == "zero":
                v = Decimal(0)
            elif spec["nulo"] == "invalido":
                invalido = True
            else:
                return None, "A especificação não diz o que fazer com valor em branco."
        elif fora_da_faixa(p, v):
            invalido = True
        valores.append(v)
    if invalido:
        if spec["retorno_invalido"] is None:
            return None, "A especificação não diz o que a função devolve para valor inválido."
        return spec["retorno_invalido"].quantize(epsilon_resultado, ROUND_HALF_UP), ""
    if formula is None:
        return None, "A especificação ainda não tem a fórmula do resultado."
    r = motor.executar_funcao(formula, valores, epsilon_resultado)
    if r["erro"]:
        return None, f"A fórmula da especificação não pôde ser calculada: {r['erro']}."
    return r["valor"], ""


# ==========================================================================
# Classes de equivalencia e pontos de fronteira
# ==========================================================================
def _faixa_txt(p) -> str:
    lo, hi = p["minimo"], p["maximo"]
    if lo is not None and hi is not None:
        return f"{formato_br(lo)} ≤ valor ≤ {formato_br(hi)}"
    if lo is not None:
        return f"valor ≥ {formato_br(lo)}"
    if hi is not None:
        return f"valor ≤ {formato_br(hi)}"
    return "qualquer valor do tipo"


def classes_do_parametro(p):
    """[(classe, dominio)] de um parametro."""
    classes = [("Válida", _faixa_txt(p))]
    if p["minimo"] is not None:
        classes.append((f"Inválida (abaixo de {formato_br(p['minimo'])})", f"valor < {formato_br(p['minimo'])}"))
    if p["maximo"] is not None:
        classes.append((f"Inválida (acima de {formato_br(p['maximo'])})", f"valor > {formato_br(p['maximo'])}"))
    classes.append(("Nula (em branco)", "valor IS NULL"))
    return classes


def classe_de(p, valor) -> str:
    if valor is None:
        return "Nula (em branco)"
    if p["minimo"] is not None and valor < p["minimo"]:
        return f"Inválida (abaixo de {formato_br(p['minimo'])})"
    if p["maximo"] is not None and valor > p["maximo"]:
        return f"Inválida (acima de {formato_br(p['maximo'])})"
    return "Válida"


def pontos_do_parametro(p):
    """Pontos da AVL: [{"rotulo", "valor", "lado", "condicao", "valido"}], na ordem dos testes."""
    eps, tipo = p["tipo"]["epsilon"], p["tipo"]
    dois_lados = p["minimo"] is not None and p["maximo"] is not None
    sufixo = {"min": " (mín.)" if dois_lados else "", "max": " (máx.)" if dois_lados else ""}
    pontos = []
    if p["minimo"] is not None:
        lo = p["minimo"]
        pontos += [
            {"rotulo": "On-Point" + sufixo["min"], "valor": lo, "lado": "min", "valido": True,
             "condicao": f"Exatamente no mínimo válido ({formato_br(lo)})"},
            {"rotulo": "Off-Point" + sufixo["min"], "valor": lo - eps, "lado": "min", "valido": False,
             "condicao": f"Primeiro valor abaixo do mínimo ({formato_br(lo)} − ε)"}]
    if p["maximo"] is not None:
        hi = p["maximo"]
        pontos += [
            {"rotulo": "On-Point" + sufixo["max"], "valor": hi, "lado": "max", "valido": True,
             "condicao": f"Exatamente no máximo válido ({formato_br(hi)})"},
            {"rotulo": "Off-Point" + sufixo["max"], "valor": hi + eps, "lado": "max", "valido": False,
             "condicao": f"Primeiro valor acima do máximo ({formato_br(hi)} + ε)"}]
    pontos.append({"rotulo": "Interior", "valor": p["interior"], "lado": "", "valido": True,
                   "condicao": "Bem dentro da região válida"})
    if p["minimo"] is not None:
        valor = p["minimo"] - DISTANCIA_EXTERIOR
        if tipo["minimo"] is not None and valor < tipo["minimo"]:
            valor = tipo["minimo"]
        if valor < p["minimo"] - eps:
            pontos.append({"rotulo": "Exterior" + sufixo["min"], "valor": valor.quantize(eps), "lado": "min",
                           "valido": False, "condicao": "Bem fora da região válida, abaixo do mínimo"})
    if p["maximo"] is not None:
        valor = p["maximo"] + DISTANCIA_EXTERIOR
        if tipo["maximo"] is not None and valor > tipo["maximo"]:
            valor = tipo["maximo"]
        if valor > p["maximo"] + eps:
            pontos.append({"rotulo": "Exterior" + sufixo["max"], "valor": valor.quantize(eps), "lado": "max",
                           "valido": False, "condicao": "Bem fora da região válida, acima do máximo"})
    return pontos


def ponto_de(p, valor) -> str:
    """Que ponto da AVL um valor representa para este parametro ('' se nenhum)."""
    if valor is None:
        return ""
    pontos = pontos_do_parametro(p)
    for ponto in pontos:
        if ponto["rotulo"].startswith(("On-Point", "Off-Point")) and ponto["valor"] == valor:
            return ponto["rotulo"]
    if not fora_da_faixa(p, valor):
        return "Interior"
    lado = "min" if p["minimo"] is not None and valor < p["minimo"] else "max"
    return next((x["rotulo"] for x in pontos if x["rotulo"].startswith("Exterior") and x["lado"] == lado), "")


def e_fronteira(p, valor) -> bool:
    return ponto_de(p, valor).startswith(("On-Point", "Off-Point"))


# ==========================================================================
# Regras do combinado (para o laudo e a rastreabilidade)
# ==========================================================================
def _faixas_resumo(spec) -> str:
    faixas = {_faixa_txt(p) for p in spec["params"] if p["minimo"] is not None or p["maximo"] is not None}
    if len(faixas) == 1 and all(p["minimo"] is not None or p["maximo"] is not None for p in spec["params"]):
        return f"cada valor deve ser {next(iter(faixas)).replace('valor ', '')}"
    return "; ".join(f"{p['nome']}: {_faixa_txt(p)}" for p in spec["params"]
                     if p["minimo"] is not None or p["maximo"] is not None)


def formula_bonita(texto: str) -> str:
    return texto.replace("*", "×").replace("/", "÷")


def regras(spec):
    """As regras do combinado, na ordem: entrada, nulo, faixa e formula (as que existirem)."""
    params, r = spec["params"], spec["retorno_invalido"]
    n = len(params)
    tipos = sorted({p["tipo"]["rotulo"] for p in params})
    lista = [{"chave": "entrada", "titulo": f"Recebe {n} valor{'es' if n > 1 else ''}",
              "detalhe": f"do tipo {' e '.join(tipos)}",
              "formal": f"A função recebe {n} parâmetro{'s' if n > 1 else ''}: "
                        + ", ".join(f"{p['nome']} ({p['tipo']['rotulo']})" for p in params) + "."}]
    if spec["nulo"] == "zero":
        lista.append({"chave": "nulo", "titulo": "Valor em branco conta como zero",
                      "detalhe": "um campo vazio vale 0", "formal": "Parâmetro NULL é tratado como 0."})
    elif spec["nulo"] == "invalido" and r is not None:
        lista.append({"chave": "nulo", "titulo": "Valor em branco é recusado",
                      "detalhe": f"um campo vazio faz a resposta ser {formato_br(r)}",
                      "formal": f"Parâmetro NULL é inválido: a função retorna {formato_br(r)}."})
    if r is not None and any(p["minimo"] is not None or p["maximo"] is not None for p in params):
        lista.append({"chave": "faixa", "titulo": "Valor fora da faixa é recusado",
                      "detalhe": f"{_faixas_resumo(spec)}; se não for, a resposta é {formato_br(r)}",
                      "formal": f"Faixa válida: {_faixas_resumo(spec)}. Fora dela, a função retorna {formato_br(r)}."})
    if (spec["formula"] or "").strip():
        lista.append({"chave": "formula", "titulo": "Nos demais casos, faz a conta",
                      "detalhe": formula_bonita(spec["formula"].strip()),
                      "formal": f"Caso contrário, retorna {formula_bonita(spec['formula'].strip())}."})
    return lista


def regra_do_caso(spec, entradas) -> str:
    """Chave da regra que o caso verifica em primeiro lugar."""
    chaves = [r["chave"] for r in regras(spec)]
    if "faixa" in chaves and any(fora_da_faixa(p, v) for p, v in zip(spec["params"], entradas)):
        return "faixa"
    if "nulo" in chaves and any(v is None for v in entradas):
        return "nulo"
    if "formula" in chaves:
        return "formula"
    return "entrada"


def situacao_do_caso(spec, entradas) -> str:
    """As tres frentes do teste de unidade: caminho feliz, fronteira e excecao."""
    if any(e_fronteira(p, v) for p, v in zip(spec["params"], entradas)):
        return "Fronteira"
    if any(v is None or fora_da_faixa(p, v) for p, v in zip(spec["params"], entradas)):
        return "Exceção"
    return "Caminho feliz"


def textos_dos_achados(spec):
    """Nome tecnico e explicacao simples de cada tipo de defeito, com os valores da especificacao."""
    r = "o valor de erro" if spec["retorno_invalido"] is None else formato_br(spec["retorno_invalido"])
    formula = formula_bonita(spec["formula"].strip()) if (spec["formula"] or "").strip() else "a fórmula"
    tecnico = {
        "INVALIDO_ACEITO": ("Valor inválido aceito",
                            f"A especificação manda retornar {r} quando um valor está fora da faixa válida "
                            "(ou em branco, se for o caso), mas a função devolveu outro resultado."),
        "VALIDO_REJEITADO": ("Valor válido rejeitado",
                             f"A função retornou {r} para uma entrada permitida. Causa provável: comparação "
                             "com <= no lugar de < (ou o contrário) na fronteira."),
        "NULO": ("Devolveu NULL", "A função devolveu NULL onde a especificação define um resultado."),
        "CALCULO": ("Resultado diferente da fórmula", f"O valor devolvido não corresponde a {formula}."),
        "ERRO": ("Erro na execução", "A função não chegou a devolver um resultado."),
    }
    simples = {
        "INVALIDO_ACEITO": ("Aceita valor fora da faixa", f"deveria recusar com {r} e responde outra coisa"),
        "VALIDO_REJEITADO": ("Recusa um valor permitido", f"responde {r} para um valor que a regra aceita"),
        "NULO": ("Devolve resposta vazia", "responde NULL onde a regra define um resultado"),
        "CALCULO": ("Faz a conta errada", f"o resultado não bate com {formula}"),
        "ERRO": ("Para no meio da execução", "o programa não chega a dar uma resposta"),
    }
    return tecnico, simples


def condicao_que_falta(spec) -> str:
    """Trecho 4GL que implementaria a regra de faixa (para a sugestao de correcao)."""
    partes = []
    for p in spec["params"]:
        if p["minimo"] is not None:
            partes.append(f"{p['nome']} < {p['minimo']}")
        if p["maximo"] is not None:
            partes.append(f"{p['nome']} > {p['maximo']}")
    if spec["nulo"] == "invalido":
        partes += [f"{p['nome']} IS NULL" for p in spec["params"]]
    if not partes or spec["retorno_invalido"] is None:
        return ""
    return f"IF {' OR '.join(partes)} THEN\n    RETURN {spec['retorno_invalido']}\nEND IF"


# ==========================================================================
# Casos de teste
# ==========================================================================
def montar_caso(ident, tecnica, alvo, rotulo, entradas, programa, spec, formula, epsilon, maximo, descricao=""):
    """Executa um caso de teste e compara o obtido com o esperado."""
    esperado, motivo = oraculo(spec, formula, entradas, epsilon)
    execucao = motor.executar_funcao(programa, entradas, epsilon)
    obtido, erro = execucao["valor"], execucao["erro"]
    achado, observacao = "", descricao
    r = spec["retorno_invalido"]
    if esperado is None:
        status, observacao = "Sem oráculo", motivo
    elif abs(esperado) > maximo:
        status, esperado = "Sem oráculo", None
        observacao = "O resultado passa do maior valor do tipo; a especificação não define esse caso."
    elif erro:
        status, achado, observacao = "Reprovado", "ERRO", erro
    elif obtido == esperado:
        status = "Aprovado"
    else:
        status = "Reprovado"
        if obtido is None:
            achado = "NULO"
        elif r is not None and esperado == r.quantize(epsilon):
            achado = "INVALIDO_ACEITO"
        elif r is not None and obtido == r.quantize(epsilon):
            achado = "VALIDO_REJEITADO"
        else:
            achado = "CALCULO"
    return {"id": ident, "tecnica": tecnica, "alvo": alvo, "rotulo": rotulo,
            "entradas": list(entradas), "esperado": esperado, "obtido": obtido,
            "erro": erro, "status": status, "achado": achado, "observacao": observacao}


def gerar_suite_base(programa, spec, formula, epsilon, maximo):
    """Suite planejada: para cada parametro, os pontos da AVL e a classe nula.
    Um parametro varia por vez; os outros ficam no valor comum (valido).
    Assim, se um teste falhar, sabemos qual parametro causou a falha."""
    comuns = [p["comum"] for p in spec["params"]]
    casos = []
    for i, p in enumerate(spec["params"]):
        for ponto in pontos_do_parametro(p):
            entradas = list(comuns)
            entradas[i] = ponto["valor"]
            casos.append(montar_caso(f"CT{len(casos) + 1:02d}", "AVL", p["nome"], ponto["rotulo"],
                                     entradas, programa, spec, formula, epsilon, maximo))
    for i, p in enumerate(spec["params"]):
        entradas = list(comuns)
        entradas[i] = None
        casos.append(montar_caso(f"CT{len(casos) + 1:02d}", "PCE", p["nome"], "Nulo",
                                 entradas, programa, spec, formula, epsilon, maximo))
    return casos


def sugestoes_de_extras(spec):
    """Linhas iniciais da aba de testes extras: [(descricao, [valores])]."""
    params = spec["params"]
    comuns = [p["comum"] for p in params]
    linhas = []
    com_min = next((i for i, p in enumerate(params) if p["minimo"] is not None), None)
    if com_min is not None:
        p = params[com_min]
        valores = list(comuns)
        valores[com_min] = p["minimo"] + p["tipo"]["epsilon"]
        linhas.append(("Primeiro valor válido acima do mínimo (mínimo + ε)", valores))
    fora = []
    for p in params:
        if p["minimo"] is not None:
            fora.append(p["minimo"] - p["tipo"]["epsilon"])
        elif p["maximo"] is not None:
            fora.append(p["maximo"] + p["tipo"]["epsilon"])
        else:
            fora.append(p["comum"])
    if any(p["minimo"] is not None or p["maximo"] is not None for p in params):
        linhas.append(("Todos os parâmetros um passo fora da faixa", fora))
    linhas.append(("Todos os parâmetros em branco (NULL)", [None] * len(params)))
    ultimo = params[-1]
    teto = ultimo["maximo"] if ultimo["maximo"] is not None else ultimo["tipo"]["maximo"]
    if teto is not None:
        valores = [p["minimo"] if p["minimo"] is not None else Decimal(0) for p in params]
        valores = [v.quantize(p["tipo"]["epsilon"]) for v, p in zip(valores, params)]
        valores[-1] = teto
        linhas.append(("Maior valor permitido no último parâmetro", valores))
    return linhas


# ==========================================================================
# Salvar e carregar a especificacao (arquivo .json)
# ==========================================================================
def especificacao_para_json(spec, funcao: str) -> str:
    import json
    texto = lambda v: None if v is None else str(v)   # noqa: E731
    return json.dumps({
        "funcao": funcao,
        "parametros": {p["nome"]: {"minimo": texto(p["minimo"]), "maximo": texto(p["maximo"]),
                                   "comum": texto(p["comum"]), "interior": texto(p["interior"])}
                       for p in spec["params"]},
        "nulo": spec["nulo"], "retorno_invalido": texto(spec["retorno_invalido"]),
        "formula": spec["formula"], "enunciado": spec["enunciado"],
    }, ensure_ascii=False, indent=2)


def especificacao_de_json(texto: str, programa) -> dict:
    """Le uma especificacao salva. Os nomes dos parametros precisam bater com os da funcao."""
    import json
    try:
        dados = json.loads(texto)
    except ValueError:
        raise ErroEspecificacao("o arquivo não é um JSON válido")
    if not isinstance(dados, dict) or "parametros" not in dados:
        raise ErroEspecificacao("o arquivo não parece uma especificação do TestingStudio")
    salvos = dados["parametros"]
    faltam = [p for p in programa["parametros"] if p not in salvos]
    if faltam:
        raise ErroEspecificacao(f"a especificação é de outra função (faltam os parâmetros {', '.join(faltam)})")
    spec = especificacao_inicial(programa)
    for p in spec["params"]:
        for campo in ("minimo", "maximo", "comum", "interior"):
            p[campo] = decimal_ou_none(salvos[p["nome"]].get(campo), p["tipo"]["epsilon"])
    spec["nulo"] = dados.get("nulo") if dados.get("nulo") in NULO_OPCOES else "indefinido"
    spec["retorno_invalido"] = decimal_ou_none(dados.get("retorno_invalido"))
    spec["formula"] = str(dados.get("formula") or "")
    spec["enunciado"] = str(dados.get("enunciado") or "")
    completar_valores(spec)
    return spec
