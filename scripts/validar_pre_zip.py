from __future__ import annotations

import compileall
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = [
    "main.py",
    "iniciar_jugueteriabot.py",
    "requirements.txt",
    "MAESTRO_JUGUETERIABOT.bat",
    ".env.example",
    "templates/base.html",
    "templates/dashboard.html",
    "static/panel.css",
    "static/panel-react.js",
    "static/panel-gsap.js",
    "agents/README_AGENTES_JUGUETERIABOT.md",
    "docs/GSAP_EN_PROYECTO.md",
    "docs/VENTA_AUTOMATIZACIONES.md",
    "docs/REVISION_PRE_ZIP.md",
    "docs/EMPAQUETADO_WINDOWS.md",
]
DISALLOWED_DIRS = {".venv", "__pycache__", ".pytest_cache", "node_modules"}
SECRET_PATTERNS = [
    re.compile(r"META_ACCESS_TOKEN\s*=\s*(?!PEGA_AQUI|$).+", re.I),
    re.compile(r"OPENAI_API_KEY\s*=\s*(?!PEGA_AQUI|$).+", re.I),
    re.compile(r"NGROK_AUTHTOKEN\s*=\s*(?!PEGA_AQUI|$).+", re.I),
]


def fail(message: str) -> None:
    print(f"[ERROR] {message}")
    raise SystemExit(1)


def warn(message: str) -> None:
    print(f"[AVISO] {message}")


def ok(message: str) -> None:
    print(f"[OK] {message}")


def validate_required_files() -> None:
    missing = [file for file in REQUIRED_FILES if not (ROOT / file).exists()]
    if missing:
        fail("Faltan archivos requeridos: " + ", ".join(missing))
    ok("Archivos base presentes")


def validate_python_compile() -> None:
    files = [ROOT / "main.py", ROOT / "iniciar_jugueteriabot.py", ROOT / "scripts" / "validar_pre_zip.py"]
    for file in files:
        result = compileall.compile_file(str(file), quiet=1)
        if not result:
            fail(f"Error compilando {file.relative_to(ROOT)}")
    ok("Python compila correctamente")


def validate_templates_static() -> None:
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8", errors="ignore")
    if "/static/panel-react.js" not in base:
        fail("base.html no carga panel-react.js")
    if "/static/panel-gsap.js" not in base:
        fail("base.html no carga panel-gsap.js")
    if "gsap" not in base.lower():
        fail("base.html no carga GSAP")
    ok("Templates y assets frontend enlazados")


def validate_requirements() -> None:
    req = (ROOT / "requirements.txt").read_text(encoding="utf-8", errors="ignore").lower()
    required = ["fastapi", "uvicorn", "pyodbc", "requests", "python-dotenv", "jinja2", "rapidfuzz", "openai", "python-multipart", "itsdangerous"]
    missing = [name for name in required if name not in req]
    if missing:
        fail("requirements.txt no contiene: " + ", ".join(missing))
    ok("requirements.txt contiene dependencias esperadas")


def validate_sensitive_files() -> None:
    env = ROOT / ".env"
    if env.exists():
        warn("Existe .env real. No debe incluirse en ZIP público; usa .env.example para entregas.")
        content = env.read_text(encoding="utf-8", errors="ignore")
        for pattern in SECRET_PATTERNS:
            if pattern.search(content):
                warn(".env parece contener credenciales reales. Excluir del ZIP limpio.")
                break

    env_example = ROOT / ".env.example"
    if env_example.exists():
        example = env_example.read_text(encoding="utf-8", errors="ignore")
        forbidden = ["sk-proj-", "EAAN", "EAA", "xoxb-"]
        leaked = [token for token in forbidden if token in example]
        if leaked:
            fail(".env.example contiene posibles credenciales reales: " + ", ".join(leaked))
    ok("Revisión de secretos finalizada")


def validate_unwanted_dirs() -> None:
    found = []
    for path in ROOT.rglob("*"):
        if path.is_dir() and path.name in DISALLOWED_DIRS:
            found.append(str(path.relative_to(ROOT)))
    if found:
        warn("Directorios que deben excluirse del ZIP limpio: " + ", ".join(found[:12]))
    ok("Revisión de carpetas temporales finalizada")


def main() -> None:
    os.chdir(ROOT)
    print("Validación pre-ZIP de JugueteríaBot")
    print("Raíz:", ROOT)
    validate_required_files()
    validate_python_compile()
    validate_templates_static()
    validate_requirements()
    validate_sensitive_files()
    validate_unwanted_dirs()
    print("\nResultado: validación operativa completada. Revisar avisos antes de entregar a cliente.")


if __name__ == "__main__":
    main()
