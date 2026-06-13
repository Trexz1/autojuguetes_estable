"""Diagnóstico operativo básico para JugueteriaBot.
Ejecutar desde la raíz del proyecto:
    python scripts/diagnostico_sistema.py
"""
from pathlib import Path
import os
import sys
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

REQUIRED = [
    "META_VERIFY_TOKEN", "META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID",
    "OPENAI_API_KEY", "DB_SERVER", "DB_NAME", "PANEL_SECRET_KEY"
]

print("== Diagnóstico JugueteriaBot ==")
missing = [k for k in REQUIRED if not os.getenv(k)]
if missing:
    print("[ERROR] Variables faltantes:", ", ".join(missing))
else:
    print("[OK] Variables obligatorias presentes")

for folder in ["templates", "static", "logs", "docs", "scripts"]:
    path = ROOT / folder
    print(f"[{'OK' if path.exists() else 'ERROR'}] Carpeta {folder}")

try:
    import pyodbc  # noqa
    print("[OK] pyodbc instalado")
except Exception as exc:
    print("[ERROR] pyodbc no disponible:", exc)

try:
    import openai  # noqa
    print("[OK] openai instalado")
except Exception as exc:
    print("[ERROR] openai no disponible:", exc)

try:
    import rapidfuzz  # noqa
    print("[OK] rapidfuzz instalado")
except Exception as exc:
    print("[ERROR] rapidfuzz no disponible:", exc)

print("Diagnóstico terminado.")
