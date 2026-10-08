@echo off
setlocal
cd /d "%~dp0"
title TestingStudio Web

set PY=python
%PY% --version >nul 2>nul
if errorlevel 1 set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 goto sempython

%PY% -c "import streamlit, pandas, altair; from google import genai" >nul 2>nul
if errorlevel 1 (
  echo  Instalando as bibliotecas pela primeira vez. Aguarde...
  %PY% -m pip install --quiet --disable-pip-version-check streamlit pandas google-genai
)

%PY% iniciar.py
if errorlevel 1 pause
exit /b 0

:sempython
echo.
echo  Nao encontrei o Python neste computador.
echo  Instale em https://www.python.org/downloads/ e marque a opcao Add python.exe to PATH.
echo.
pause
exit /b 1
