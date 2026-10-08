# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller: como transformar o TestingStudio em um executavel.
# Usada pelo Gerar_Executavel.bat  (python -m PyInstaller TestingStudio.spec)
import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# O Streamlit precisa levar junto os arquivos da pagina (HTML/JS) e seus metadados.
datas, binaries, hiddenimports = collect_all("streamlit")
datas += copy_metadata("streamlit")

# Arquivos do projeto que vao dentro do executavel.
datas += [("app.py", "."), ("motor.py", ".")]
if os.path.exists("cad0001_item_calculo.txt"):
    datas += [("cad0001_item_calculo.txt", ".")]

a = Analysis(
    ["iniciar.py"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["altair", "pandas", "google.genai"],
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
