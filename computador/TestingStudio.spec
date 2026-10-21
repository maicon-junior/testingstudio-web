# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller: como transformar o TestingStudio em um executavel.
# Usada pelo Gerar_Executavel.bat  (python -m PyInstaller TestingStudio.spec)
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# O Streamlit precisa levar junto os arquivos da pagina (HTML/JS) e seus metadados.
datas, binaries, hiddenimports = collect_all("streamlit")
datas += copy_metadata("streamlit")

# Arquivos do projeto que vao dentro do executavel. Este arquivo fica na pasta
# computador/; os arquivos do app ficam na pasta principal, um nivel acima.
RAIZ = os.path.abspath(os.path.join(SPECPATH, ".."))


def da_raiz(*partes):
    return os.path.join(RAIZ, *partes)


def pasta_inteira(pasta):
    """Todos os arquivos de uma pasta (e subpastas), no mesmo lugar dentro do executavel."""
    itens = []
    for raiz, pastas, nomes in os.walk(da_raiz(pasta)):
        pastas[:] = [p for p in pastas if p != "__pycache__"]
        destino = os.path.relpath(raiz, RAIZ)
        itens += [(os.path.join(raiz, nome), destino) for nome in nomes]
    return itens


datas += [(da_raiz("app.py"), "."), (da_raiz(".streamlit", "config.toml"), ".streamlit")]
datas += pasta_inteira("nucleo") + pasta_inteira("static") + pasta_inteira("exemplos")
datas += collect_all("reportlab")[0]

a = Analysis(
    [os.path.join(SPECPATH, "iniciar.py")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["altair", "pandas", "google.genai", "reportlab"] + collect_all("reportlab")[2],
    # Bibliotecas grandes que o app nao usa: ficam de fora para o arquivo nao inchar.
    excludes=["matplotlib", "scipy", "tkinter", "IPython", "notebook", "pytest",
              "torch", "tensorflow", "sklearn", "PyQt5", "PyQt6", "PySide2", "PySide6"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="TestingStudio",
    console=True,      # a janela preta mostra o endereco e serve para encerrar o programa
    upx=False,
)
