@echo off
setlocal
cd /d "%~dp0"
title TestingStudio - gerar executavel

set PY=python
%PY% --version >nul 2>nul
if errorlevel 1 set PY=py -3
%PY% --version >nul 2>nul
if errorlevel 1 goto sempython

echo.
echo  [1/3] Conferindo as bibliotecas. Pode levar alguns minutos...
%PY% -m pip install --quiet --disable-pip-version-check pyinstaller streamlit pandas google-genai
if errorlevel 1 goto erro

echo  [2/3] Montando o executavel. Leva de 3 a 10 minutos, nao feche esta janela...
%PY% -m PyInstaller --noconfirm --clean --log-level WARN TestingStudio.spec
if errorlevel 1 goto erro
if not exist "dist\TestingStudio.exe" goto erro

echo  [3/3] Finalizando...
copy /y "dist\TestingStudio.exe" "TestingStudio.exe" >nul
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo.
echo  Pronto. O arquivo TestingStudio.exe esta nesta pasta.
echo  Para abrir, de dois cliques nele. Para enviar, use um link do Google Drive.
echo.
pause
exit /b 0

:sempython
echo.
echo  Nao encontrei o Python neste computador.
echo  Instale em https://www.python.org/downloads/ e marque a opcao Add python.exe to PATH.
echo.
pause
exit /b 1

:erro
echo.
echo  Nao foi possivel gerar o executavel. Copie as mensagens acima para pedir ajuda.
echo.
pause
exit /b 1
