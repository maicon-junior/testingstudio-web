"""
Abre o TestingStudio Web no navegador.

Serve para duas coisas:
  - rodar direto:            python iniciar.py   (ou Abrir_TestingStudio.bat)
  - virar o executavel:      Gerar_Executavel.bat empacota este arquivo com o PyInstaller
"""

import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Aparencia da pagina (tema do Streamlit).
TEMA = {
    "base": "light",
    "primaryColor": "#1f4e79",
    "backgroundColor": "#fafbfc",
    "secondaryBackgroundColor": "#edf1f5",
    "textColor": "#1b2a3d",
    "font": "'Segoe UI', system-ui, sans-serif",
    "headingFont": "'Cascadia Mono', Consolas, 'Courier New', monospace",
    "baseRadius": "6px",
}


def pasta_do_app() -> Path:
    """No executavel, os arquivos ficam na pasta temporaria do PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def porta_livre() -> int:
    """Pede ao sistema uma porta desocupada, para nao brigar com outro programa."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def abrir_navegador(porta: int) -> None:
    """Espera o servidor responder e so entao abre a pagina."""
    for _ in range(240):
        try:
            with socket.create_connection(("127.0.0.1", porta), timeout=0.5):
                webbrowser.open(f"http://localhost:{porta}")
                return
        except OSError:
            time.sleep(0.5)


def _dependencias_do_app():
    """Nunca e chamada. Existe para o PyInstaller enxergar o que o app.py usa."""
    import altair  # noqa: F401
    import pandas  # noqa: F401
    from google import genai  # noqa: F401


def main() -> None:
    porta = porta_livre()
    print("=" * 62)
    print(" TestingStudio Web - Auditoria do CAD0001")
    print(f" A pagina vai abrir no navegador: http://localhost:{porta}")
    print(" Para encerrar, feche esta janela.")
    print("=" * 62, flush=True)
    threading.Thread(target=abrir_navegador, args=(porta,), daemon=True).start()

    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit", "run", str(pasta_do_app() / "app.py"),
        "--global.developmentMode=false",
        "--server.headless=true",              # nao pergunta e-mail; quem abre o navegador e este script
        f"--server.port={porta}",
        "--server.address=localhost",          # so este computador acessa; evita aviso do firewall
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
        "--client.toolbarMode=minimal",        # esconde o menu de desenvolvedor
    ] + [f"--theme.{opcao}={valor}" for opcao, valor in TEMA.items()]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
