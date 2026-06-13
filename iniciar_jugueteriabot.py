from __future__ import annotations

import os
import subprocess
import shutil
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn


APP_HOST = "127.0.0.1"
APP_PORT = 8000
PANEL_URL = f"http://{APP_HOST}:{APP_PORT}/panel"
API_URL = f"http://{APP_HOST}:{APP_PORT}/docs"
NGROK_DASHBOARD_URL = "http://127.0.0.1:4040"


def runtime_dir() -> Path:
    """Devuelve la carpeta real desde donde se ejecuta el sistema."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def project_dir() -> Path:
    """Devuelve la carpeta del proyecto cuando se ejecuta como .py o como .exe."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def find_ngrok(base_dir: Path) -> str | None:
    """Busca ngrok.exe junto al ejecutable, en tools/ngrok o en PATH.

    En Windows, ngrok instalado desde Microsoft Store puede aparecer como alias
    en WindowsApps y no siempre se puede copiar. Por eso el EXE también intenta
    ejecutarlo desde PATH si no existe junto a JugueteriaBot.exe.
    """
    candidates = [
        base_dir / "ngrok.exe",
        base_dir / "tools" / "ngrok" / "ngrok.exe",
        base_dir.parent / "tools" / "ngrok" / "ngrok.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)

    path_ngrok = shutil.which("ngrok")
    if path_ngrok:
        return path_ngrok

    return None


def open_browser_later() -> None:
    time.sleep(4)
    webbrowser.open(PANEL_URL)
    time.sleep(1)
    webbrowser.open(NGROK_DASHBOARD_URL)


def start_ngrok(base_dir: Path) -> subprocess.Popen | None:
    """Arranca ngrok desde el mismo ejecutable si está disponible."""
    disabled = os.getenv("JUGUETERIABOT_NGROK", "1").strip().lower() in {"0", "false", "no"}
    if disabled:
        print("Ngrok desactivado por JUGUETERIABOT_NGROK=0.")
        return None

    ngrok_exe = find_ngrok(base_dir)
    if not ngrok_exe:
        print("AVISO: No se encontró ngrok.exe junto al ejecutable ni en PATH.")
        print("Coloca ngrok.exe junto a JugueteriaBot.exe, en tools/ngrok, o instala ngrok en Windows.")
        return None

    authtoken = os.getenv("NGROK_AUTHTOKEN", "").strip()
    if authtoken:
        try:
            subprocess.run([ngrok_exe, "config", "add-authtoken", authtoken], check=False)
        except Exception as exc:
            print(f"AVISO: No se pudo configurar NGROK_AUTHTOKEN automaticamente: {exc}")

    print(f"Abriendo ngrok: http {APP_PORT}")
    print(f"Dashboard ngrok: {NGROK_DASHBOARD_URL}")

    try:
        return subprocess.Popen(
            [ngrok_exe, "http", str(APP_PORT)],
            cwd=str(base_dir),
            creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0,
        )
    except Exception as exc:
        print(f"AVISO: No se pudo iniciar ngrok desde el ejecutable: {exc}")
        return None


def validate_env(base_dir: Path) -> None:
    env_path = base_dir / ".env"
    if not env_path.exists():
        print("ERROR: No se encontro el archivo .env junto al ejecutable.")
        print("Copia .env.example como .env y configura tus tokens, servidor SQL y claves del panel.")
        input("Presiona ENTER para cerrar...")
        raise SystemExit(1)

    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
    except Exception:
        pass

    required = [
        "META_VERIFY_TOKEN",
        "META_ACCESS_TOKEN",
        "META_PHONE_NUMBER_ID",
        "DB_SERVER",
        "DB_NAME",
    ]
    missing = []
    placeholder_tokens = {"", "PEGA_AQUI_TU_TOKEN_DE_META", "PEGA_AQUI_TU_PHONE_NUMBER_ID", "CAMBIA_ESTE_TOKEN_DE_VERIFICACION"}
    for key in required:
        value = os.getenv(key, "").strip()
        if value in placeholder_tokens:
            missing.append(key)

    if missing:
        print("ERROR: .env existe, pero contiene valores vacios o de ejemplo:")
        for key in missing:
            print(f"- {key}")
        print("Corrige .env antes de iniciar el bot.")
        input("Presiona ENTER para cerrar...")
        raise SystemExit(1)


def main() -> None:
    base_dir = runtime_dir()
    os.chdir(base_dir)

    validate_env(base_dir)

    print("Iniciando JugueteriaBot...")
    print(f"Panel: {PANEL_URL}")
    print(f"API:   {API_URL}")
    print("Webhook Meta: usa la URL HTTPS de ngrok + /webhook")
    print("Para detener el servidor, cierra esta ventana o presiona CTRL + C.")

    ngrok_process = start_ngrok(base_dir)

    try:
        from main import app as fastapi_app
    except Exception as exc:
        print("ERROR: No se pudo cargar main.py / FastAPI app.")
        print(f"Detalle: {exc}")
        if ngrok_process:
            ngrok_process.terminate()
        input("Presiona ENTER para cerrar...")
        raise

    threading.Thread(target=open_browser_later, daemon=True).start()

    try:
        uvicorn.run(
            fastapi_app,
            host=APP_HOST,
            port=APP_PORT,
            reload=False,
            log_level="info",
        )
    finally:
        if ngrok_process:
            try:
                ngrok_process.terminate()
            except Exception:
                pass


if __name__ == "__main__":
    main()
