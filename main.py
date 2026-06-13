from pathlib import Path
import os
import sys
import re
import unicodedata
from typing import Optional, Any, List, Dict
import base64
import json
import logging
import time
import hashlib
import shutil
from datetime import datetime
from urllib.parse import urlparse
from collections import defaultdict, deque

import pyodbc
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Form, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from rapidfuzz import process, fuzz
from openai import OpenAI
try:
    import mercadopago
except Exception:
    mercadopago = None

# =========================================================
# CONFIGURACIÃ“N GENERAL
# =========================================================
# Directorios compatibles con ejecuciÃ³n normal y PyInstaller.
# APP_DIR: recursos empaquetados dentro del .exe (templates/static).
# RUNTIME_DIR: carpeta externa donde vive .env cuando se ejecuta el .exe.
if getattr(sys, "frozen", False):
    APP_DIR = Path(getattr(sys, "_MEIPASS"))
    RUNTIME_DIR = Path(sys.executable).resolve().parent
else:
    APP_DIR = Path(__file__).resolve().parent
    RUNTIME_DIR = APP_DIR

BASE_DIR = RUNTIME_DIR
load_dotenv(RUNTIME_DIR / ".env")

LOG_DIR = RUNTIME_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8"), logging.StreamHandler()]
)
app_logger = logging.getLogger("jugueteriabot.app")
whatsapp_logger = logging.getLogger("jugueteriabot.whatsapp")
error_logger = logging.getLogger("jugueteriabot.errores")
whatsapp_handler = logging.FileHandler(LOG_DIR / "whatsapp.log", encoding="utf-8")
whatsapp_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
whatsapp_logger.addHandler(whatsapp_handler)
error_handler = logging.FileHandler(LOG_DIR / "errores.log", encoding="utf-8")
error_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
error_logger.addHandler(error_handler)

APP_TITLE = "JugueteriaBot API + Panel"
GRAPH_API_VERSION = "v25.0"
DEBUG = True

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN")
META_ACCESS_TOKEN = PEGA_AQUI_TU_META_ACCESS_TOKEN
META_PHONE_NUMBER_ID = PEGA_AQUI_TU_PHONE_NUMBER_ID
NOTIFY_ORDER_PHONE = os.getenv("NOTIFY_ORDER_PHONE", "523411081543")

PANEL_SECRET_KEY = os.getenv("PANEL_SECRET_KEY", "cambia_esta_clave_panel_robles_outlet")
PANEL_ADMIN_USER = os.getenv("PANEL_ADMIN_USER", "admin")
PANEL_ADMIN_PASSWORD = os.getenv("PANEL_ADMIN_PASSWORD", "admin123")
PANEL_PEDIDOS_USER = os.getenv("PANEL_PEDIDOS_USER", "pedidos")
PANEL_PEDIDOS_PASSWORD = os.getenv("PANEL_PEDIDOS_PASSWORD", "pedidos123")
PANEL_READONLY_USER = os.getenv("PANEL_READONLY_USER", "lectura")
PANEL_READONLY_PASSWORD = os.getenv("PANEL_READONLY_PASSWORD", "lectura123")

OPENAI_API_KEY = PEGA_AQUI_TU_OPENAI_API_KEY
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4.1")
CONVERSATION_AGENT_ENABLED = os.getenv("CONVERSATION_AGENT_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}
CONVERSATION_AGENT_MODEL = os.getenv("CONVERSATION_AGENT_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
CONVERSATION_AGENT_MIN_CONFIDENCE = float(os.getenv("CONVERSATION_AGENT_MIN_CONFIDENCE", "0.45"))
AUDIO_TRANSCRIPTION_MODEL = os.getenv("AUDIO_TRANSCRIPTION_MODEL", "whisper-1")
MERCADOPAGO_ACCESS_TOKEN = PEGA_AQUI_TU_ACCESS_TOKEN
MERCADOPAGO_PUBLIC_KEY = os.getenv("MERCADOPAGO_PUBLIC_KEY")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
PAYMENT_LINK_FALLBACK = (
    os.getenv("PAYMENT_LINK_FALLBACK")
    or os.getenv("LINK_PAGO_GENERAL")
    or os.getenv("PAYMENT_LINK")
    or ""
).strip()
STATIC_DIR = RUNTIME_DIR / "static"
PRODUCT_IMAGE_DIR = STATIC_DIR / "productos"
PRODUCT_IMAGE_WEB_PREFIX = "/static/productos"

def preparar_static_runtime() -> None:
    """
    Mantiene /static funcionando tanto en modo cÃ³digo fuente como en .exe.
    En PyInstaller APP_DIR apunta a _MEIPASS, que es de solo lectura; por eso las
    fotos subidas por el panel deben guardarse y servirse desde RUNTIME_DIR/static.
    """
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    fuente_static = APP_DIR / "static"
    if fuente_static.exists() and fuente_static.resolve() != STATIC_DIR.resolve():
        for origen in fuente_static.rglob("*"):
            if origen.is_file():
                relativo = origen.relative_to(fuente_static)
                destino = STATIC_DIR / relativo
                if not destino.exists():
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(origen, destino)

preparar_static_runtime()
STOCK_BAJO_UMBRAL = int(os.getenv("STOCK_BAJO_UMBRAL", "3"))
ENVIO_DOMICILIO = float(os.getenv("ENVIO_DOMICILIO", "30"))

# Canal de WhatsApp. Por defecto se usa Meta WhatsApp Cloud API.
# OpenWA queda como gateway opcional para instalaciones self-hosted.
WHATSAPP_PROVIDER = os.getenv("WHATSAPP_PROVIDER", "meta").strip().lower()
OPENWA_BASE_URL = os.getenv("OPENWA_BASE_URL", "").rstrip("/")
OPENWA_API_KEY = os.getenv("OPENWA_API_KEY", "")
OPENWA_SESSION_ID = os.getenv("OPENWA_SESSION_ID", "my-bot")
OPENWA_CHAT_SUFFIX = os.getenv("OPENWA_CHAT_SUFFIX", "@c.us")

DB_SERVER = os.getenv("DB_SERVER", r"DESKTOP-ABEON0C\SQLEXPRESS")
DB_NAME = os.getenv("DB_NAME", "JugueteriaBot")

if not META_VERIFY_TOKEN:
    print("ADVERTENCIA: META_VERIFY_TOKEN no estÃ¡ configurado")
if not META_ACCESS_TOKEN:
    print("ADVERTENCIA: META_ACCESS_TOKEN no estÃ¡ configurado")
if not META_PHONE_NUMBER_ID:
    print("ADVERTENCIA: META_PHONE_NUMBER_ID no estÃ¡ configurado")
if not OPENAI_API_KEY:
    print("ADVERTENCIA: OPENAI_API_KEY no estÃ¡ configurado")

app = FastAPI(title=APP_TITLE)
class PanelAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/panel") and path not in {"/panel/login"}:
            usuario = request.session.get("usuario_panel")
            rol = request.session.get("rol_panel")
            if not usuario or not rol:
                return RedirectResponse(url="/panel/login", status_code=303)
            if rol == "pedidos":
                puede_ver_pedidos = (
                    path == "/panel/pedidos" or
                    re.fullmatch(r"/panel/pedidos/\d+", path) or
                    path.startswith("/panel/pedidos/entregar") or
                    path.startswith("/panel/pedidos/estado") or
                    path.startswith("/panel/pedidos/ticket") or
                    path.startswith("/panel/pedidos/mercadopago")
                )
                if not (path == "/panel" or path == "/panel/logout" or puede_ver_pedidos):
                    return PlainTextResponse("Acceso no autorizado. Este usuario solo puede gestionar pedidos.", status_code=403)
            if rol == "vendedor":
                rutas_vendedor = (
                    path == "/panel" or path == "/panel/logout" or
                    path.startswith("/panel/ventas") or
                    path.startswith("/panel/pedidos") or
                    path.startswith("/api/productos")
                )
                if not rutas_vendedor:
                    return PlainTextResponse("Acceso no autorizado. Este usuario solo puede vender y consultar pedidos.", status_code=403)
            if rol == "caja":
                rutas_caja = (
                    path == "/panel" or path == "/panel/logout" or
                    path.startswith("/panel/ventas") or
                    path.startswith("/panel/cortes") or
                    path.startswith("/panel/pedidos/ticket") or
                    path.startswith("/api/productos")
                )
                if not rutas_caja:
                    return PlainTextResponse("Acceso no autorizado. Este usuario solo puede operar caja y ventas.", status_code=403)
            if rol == "lectura":
                if request.method != "GET" or any(x in path for x in ["/nuevo", "/editar", "/eliminar", "/entregar", "/estado", "/manual", "/cerrar", "/respaldo/restaurar"]):
                    return PlainTextResponse("Acceso no autorizado. Este usuario es solo lectura.", status_code=403)
        return await call_next(request)

app.add_middleware(PanelAuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=PANEL_SECRET_KEY, same_site="lax", https_only=False)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

def foto_src_panel(ruta: Optional[str]) -> str:
    """Normaliza rutas de foto para el panel web.
    Acepta URLs absolutas, /static/..., static/..., productos/... o solo filename.
    """
    if not ruta:
        return ""
    valor = str(ruta).strip().replace("\\", "/")
    if not valor or valor.lower() in {"none", "null", "-"}:
        return ""
    if valor.startswith("http://") or valor.startswith("https://"):
        return valor
    if valor.startswith("/static/"):
        return valor
    if valor.startswith("static/"):
        return "/" + valor
    if valor.startswith("/productos/"):
        return "/static" + valor
    if valor.startswith("productos/"):
        return "/static/" + valor
    return f"/static/productos/{valor.lstrip('/')}"

templates.env.globals["foto_src"] = foto_src_panel

CONNECTION_STRING = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    f"SERVER={DB_SERVER};"
    f"DATABASE={DB_NAME};"
    "Trusted_Connection=yes;"
)

# =========================================================
# MODELOS
# =========================================================
class MensajeEntrada(BaseModel):
    telefono: str
    mensaje: str
    nombre: Optional[str] = None
    ciudad: Optional[str] = None

# =========================================================
# UTILIDADES GENERALES
# =========================================================
def log_debug(*args: Any) -> None:
    mensaje = " ".join(str(a) for a in args)
    if DEBUG:
        print(mensaje)
    app_logger.info(mensaje)

def get_connection():
    return pyodbc.connect(CONNECTION_STRING)

def get_master_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={DB_SERVER};"
        "DATABASE=master;"
        "Trusted_Connection=yes;"
    )

def render_template(request: Request, template_name: str, **kwargs):
    return templates.TemplateResponse(
        request,
        template_name,
        {"request": request, **kwargs}
    )

def normalizar_texto(texto: str) -> str:
    texto = (texto or "").lower().strip()
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto)
        if unicodedata.category(c) != "Mn"
    )
    texto = texto.replace("Ã±", "n")
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    texto = traducir_modismos_basicos(texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def traducir_modismos_basicos(texto: str) -> str:
    """Normaliza modismos, abreviaturas y errores comunes antes de clasificar.

    Esto no reemplaza a OpenAI; solo limpia casos frecuentes de WhatsApp para que las
    reglas locales y la bÃºsqueda difusa funcionen mejor aun sin internet.
    """
    if not texto:
        return ""

    reemplazos_frases = {
        "q onda": "hola",
        "que onda": "hola",
        "k onda": "hola",
        "buen dia": "buenos dias",
        "bna tarde": "buenas tardes",
        "bnas tardes": "buenas tardes",
        "bnas noches": "buenas noches",
        "me late": "me interesa",
        "jalo con": "quiero comprar",
        "jalo": "confirmo",
        "va que va": "confirmo",
        "va va": "confirmo",
        "arre": "confirmo",
        "simona": "si",
        "sip": "si",
        "simon": "si",
        "nel": "no",
        "nop": "no",
        "pa recoger": "recoger",
        "pa recojer": "recoger",
        "para recojer": "recoger",
        "recojer": "recoger",
        "recojo": "recoger",
        "ocupo": "necesito",
        "apartame": "aparta",
        "apartamelo": "aparta",
        "mandamelo": "a domicilio",
        "mandemelo": "a domicilio",
        "envialo": "a domicilio",
        "con envio": "a domicilio",
        "domi": "domicilio",
        "expo": "expo",
        "expocicion": "exposicion",
        "exposicion": "exposicion",
    }

    texto = f" {texto} "
    for origen, destino in reemplazos_frases.items():
        texto = re.sub(rf"\b{re.escape(origen)}\b", destino, texto)

    reemplazos_tokens = {
        "q": "que", "k": "que", "ke": "que", "xq": "porque", "xk": "porque",
        "pq": "porque", "pa": "para", "pal": "para el", "toy": "estoy",
        "stoy": "estoy", "tas": "estas", "tmb": "tambien", "tambn": "tambien",
        "info": "informacion", "presio": "precio", "presios": "precios",
        "cuanto": "cuanto", "kuanto": "cuanto", "kuesta": "cuesta",
        "jueguete": "juguete", "jueguetes": "juguetes", "peluxe": "peluche",
        "muneca": "muneca", "muneco": "muneco",
    }
    tokens = [reemplazos_tokens.get(t, t) for t in texto.split()]
    return " ".join(tokens).strip()

def contiene_ene(texto: str) -> bool:
    return "Ã±" in (texto or "").lower()

def normalizar_para_busqueda_sql(texto: str) -> str:
    """Normaliza texto para bÃºsquedas simples; Ã± queda como n para evitar fallas con conversaciones variables."""
    return normalizar_texto(texto).replace("Ã±", "n")

def obtener_categorias_texto_publico() -> str:
    categorias_default = ["BebÃ©s", "NiÃ±os", "NiÃ±as", "Peluches", "Juegos de mesa", "Coleccionables"]
    try:
        filas = obtener_categorias()
        categorias = [str(f.nombre) for f in filas if getattr(f, "nombre", None)] or categorias_default
    except Exception:
        categorias = categorias_default
    return "\n".join(f"â€¢ {c}" for c in categorias)

def mensaje_no_encontrado_con_categorias() -> str:
    return (
        "No encontrÃ© un producto exacto con ese nombre ðŸ˜•\n"
        "Puedes elegir una categorÃ­a o escribir el nombre de otro juguete.\n\n"
        "CategorÃ­as disponibles:\n"
        f"{obtener_categorias_texto_publico()}\n\n"
        "Responde con una opciÃ³n como:\n"
        "â€¢ Peluches\n"
        "â€¢ Juegos de mesa\n"
        "â€¢ Quiero un carrito\n"
        "â€¢ Puedes enviar una imagen o nota de voz de referencia"
    )


def es_peticion_mostrar_productos(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    patrones = {
        "productos", "muestrame productos", "mostrar productos", "ver productos",
        "catalogo", "ver catalogo", "muestrame catalogo", "que productos tienen",
        "que juguetes tienen", "muestrame juguetes", "ver juguetes", "lista de productos"
    }
    return texto in patrones or any(p in texto for p in ["muestrame productos", "ver catalogo", "mostrar catalogo", "que productos"])


def obtener_productos_destacados_texto(limite: int = 8) -> str:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP (?)
                j.nombre,
                j.precio,
                ISNULL(j.precio_compra, 0) AS precio_compra,
                j.stock,
                j.foto_url,
                j.foto_local,
                c.nombre AS categoria
            FROM Juguete j
            INNER JOIN Categoria c ON j.id_categoria = c.id_categoria
            WHERE ISNULL(j.stock, 0) > 0
            ORDER BY j.id_juguete DESC
        """, limite)
        filas = cursor.fetchall()
        conn.close()
    except Exception as e:
        error_logger.exception("No se pudo obtener catÃ¡logo destacado")
        filas = []

    if not filas:
        return (
            "Por ahora no pude cargar productos especÃ­ficos. Puedes elegir una categorÃ­a:\n"
            f"{obtener_categorias_texto_publico()}"
        )

    lineas = ["Estos son algunos productos disponibles ðŸ§¸:"]
    for p in filas:
        foto_txt = " | foto disponible" if producto_tiene_foto(p) else ""
        lineas.append(f"â€¢ {p.nombre} â€” ${float(p.precio):.2f} | stock: {int(p.stock or 0)} | {p.categoria}{foto_txt}")
    lineas.append("\nPara agregar uno al carrito, escribe el nombre exacto del producto.")
    return "\n".join(lineas)


def mensaje_confirmar_producto(juguete) -> str:
    extra_foto = ""
    if producto_tiene_foto(juguete):
        extra_foto = "\nTambiÃ©n puedes responder: imagen, para ver una foto antes de agregarlo.\n"
    return (
        "EncontrÃ© este producto en el catÃ¡logo:\n\n"
        f"â€¢ {juguete.nombre}\n"
        f"â€¢ Precio: ${float(juguete.precio):.2f}\n"
        f"â€¢ Stock: {int(juguete.stock or 0)} pieza(s)\n"
        f"â€¢ CategorÃ­a: {getattr(juguete, 'categoria', 'Sin categorÃ­a')}"
        f"{extra_foto}\n"
        "Â¿Confirmas que este es el producto que quieres agregar al carrito?\n"
        "Responde:\n"
        "â€¢ sÃ­\n"
        "â€¢ no, cambiar producto\n"
        "â€¢ muÃ©strame productos"
    )


def respuesta_categoria_para_seleccion(categoria: str) -> str:
    respuesta = construir_respuesta_categoria(categoria=categoria, intencion="Consulta")
    return (
        f"Estos productos estÃ¡n en la categorÃ­a {categoria}:\n\n"
        f"{respuesta['respuesta']}\n\n"
        "Para agregar uno al carrito, escribe el nombre exacto del producto. No lo agregarÃ© sin confirmarlo primero."
    )

def normalizar_numero_whatsapp(numero: str) -> str:
    numero = re.sub(r"\D", "", numero or "")

    if numero.startswith("521") and len(numero) == 13:
        numero = "52" + numero[3:]

    return numero

# =========================================================
# SEGURIDAD OPERATIVA / RATE LIMIT / DIAGNÃ“STICO
# =========================================================
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_MESSAGES = int(os.getenv("RATE_LIMIT_MAX_MESSAGES", "30"))
_rate_limit_store = defaultdict(deque)

def excede_rate_limit(clave: str) -> bool:
    ahora = time.time()
    ventana = _rate_limit_store[clave]
    while ventana and ahora - ventana[0] > RATE_LIMIT_WINDOW_SECONDS:
        ventana.popleft()
    if len(ventana) >= RATE_LIMIT_MAX_MESSAGES:
        return True
    ventana.append(ahora)
    return False

def validar_env_basico() -> dict:
    requeridas = ["META_VERIFY_TOKEN", "META_ACCESS_TOKEN", "META_PHONE_NUMBER_ID", "OPENAI_API_KEY", "DB_SERVER", "DB_NAME", "PANEL_SECRET_KEY"]
    faltantes = [k for k in requeridas if not os.getenv(k)]
    advertencias = []
    if PANEL_SECRET_KEY == "cambia_esta_clave_panel_robles_outlet":
        advertencias.append("PANEL_SECRET_KEY usa el valor por defecto; cÃ¡mbialo antes de vender o desplegar.")
    if PANEL_ADMIN_PASSWORD == "admin123" or PANEL_PEDIDOS_PASSWORD == "pedidos123":
        advertencias.append("Hay contraseÃ±as de panel por defecto; cÃ¡mbialas en .env.")
    return {"ok": not faltantes, "faltantes": faltantes, "advertencias": advertencias}

def diagnostico_sql() -> dict:
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        conn.close()
        return {"ok": True, "detalle": "ConexiÃ³n SQL Server correcta."}
    except Exception as e:
        error_logger.exception("Fallo diagnÃ³stico SQL")
        return {"ok": False, "detalle": str(e)}

def diagnostico_meta() -> dict:
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        return {"ok": False, "detalle": "Faltan META_ACCESS_TOKEN o META_PHONE_NUMBER_ID."}
    try:
        url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{META_PHONE_NUMBER_ID}"
        resp = requests.get(url, headers={"Authorization": f"Bearer {META_ACCESS_TOKEN}"}, timeout=10)
        return {"ok": resp.status_code == 200, "status_code": resp.status_code, "detalle": resp.text[:300]}
    except Exception as e:
        error_logger.exception("Fallo diagnÃ³stico Meta")
        return {"ok": False, "detalle": str(e)}

def diagnostico_openai() -> dict:
    if not OPENAI_API_KEY:
        return {"ok": False, "detalle": "Falta OPENAI_API_KEY."}
    return {"ok": bool(client_openai), "detalle": "Cliente OpenAI inicializado." if client_openai else "Cliente OpenAI no inicializado."}

# =========================================================
# CLIENTES
# =========================================================
def obtener_cliente_por_id(id_cliente: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_cliente, nombre, telefono, ciudad
            FROM Cliente
            WHERE id_cliente = ?
        """, id_cliente)
        return cursor.fetchone()
    finally:
        conn.close()

def obtener_cliente_por_telefono(telefono: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_cliente, nombre, telefono, ciudad
            FROM Cliente
            WHERE telefono = ?
        """, telefono)
        return cursor.fetchone()
    finally:
        conn.close()

def obtener_o_crear_cliente_por_telefono(
    telefono: str,
    nombre: Optional[str] = None,
    ciudad: Optional[str] = None
) -> int:
    telefono = normalizar_numero_whatsapp(telefono)
    cliente = obtener_cliente_por_telefono(telefono)

    if cliente:
        return cliente.id_cliente

    conn = get_connection()
    try:
        cursor = conn.cursor()

        nombre_final = nombre.strip() if nombre and nombre.strip() else "Cliente WhatsApp"
        ciudad_final = ciudad.strip() if ciudad and ciudad.strip() else "Desconocida"

        cursor.execute("""
            INSERT INTO Cliente (nombre, telefono, ciudad)
            OUTPUT INSERTED.id_cliente
            VALUES (?, ?, ?)
        """, nombre_final, telefono, ciudad_final)

        nuevo_id = cursor.fetchone()[0]
        conn.commit()
        return nuevo_id
    finally:
        conn.close()

def obtener_clientes():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_cliente, nombre, telefono, ciudad
            FROM Cliente
            ORDER BY id_cliente DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

# =========================================================
# CONSULTAS
# =========================================================
def obtener_id_intencion(nombre_intencion: str) -> Optional[int]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_intencion
            FROM Intencion
            WHERE nombre = ?
        """, nombre_intencion)
        fila = cursor.fetchone()
        return fila[0] if fila else None
    finally:
        conn.close()

def guardar_consulta(id_cliente: int, mensaje: str, intencion: str):
    id_intencion = obtener_id_intencion(intencion)

    if not id_intencion:
        log_debug(f"No existe la intenciÃ³n en BD: {intencion}")
        return

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ConsultaCliente (id_cliente, mensaje, id_intencion)
            VALUES (?, ?, ?)
        """, id_cliente, mensaje, id_intencion)
        conn.commit()
    finally:
        conn.close()

def obtener_consultas_por_cliente(id_cliente: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                cc.id_consulta,
                cc.mensaje,
                cc.fecha,
                i.nombre AS intencion
            FROM ConsultaCliente cc
            LEFT JOIN Intencion i
                ON cc.id_intencion = i.id_intencion
            WHERE cc.id_cliente = ?
            ORDER BY cc.fecha DESC
        """, id_cliente)
        return cursor.fetchall()
    finally:
        conn.close()

def obtener_consultas():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 100
                cc.id_consulta,
                c.nombre AS cliente,
                cc.mensaje,
                i.nombre AS intencion,
                cc.fecha
            FROM ConsultaCliente cc
            LEFT JOIN Cliente c
                ON cc.id_cliente = c.id_cliente
            LEFT JOIN Intencion i
                ON cc.id_intencion = i.id_intencion
            ORDER BY cc.fecha DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()
        
def guardar_log_clasificacion_ai(
    id_cliente: Optional[int],
    mensaje_original: str,
    analisis_reglas: Optional[dict] = None,
    clasificacion_ai: Optional[dict] = None,
    respuesta_final: Optional[str] = None,
    fuente_clasificacion: str = "OpenAI"
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO LogClasificacionAI
            (
                id_cliente,
                mensaje_original,
                analisis_reglas,
                clasificacion_ai,
                respuesta_final,
                fuente_clasificacion
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            id_cliente,
            mensaje_original,
            json.dumps(analisis_reglas, ensure_ascii=False) if analisis_reglas else None,
            json.dumps(clasificacion_ai, ensure_ascii=False) if clasificacion_ai else None,
            respuesta_final,
            fuente_clasificacion
        )
        conn.commit()
    finally:
        conn.close()

def guardar_log_conversacion_agente(
    id_cliente: Optional[int],
    telefono: Optional[str],
    mensaje_cliente: str,
    json_agente: Optional[dict],
    accion_final: Optional[str],
    respuesta_bot: Optional[str]
):
    """Log operativo para auditar y mejorar el agente con conversaciones reales."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO LogConversacionAgente
            (id_cliente, telefono, mensaje_cliente, json_agente, accion_final, respuesta_bot, proveedor_whatsapp, modelo_openai)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            id_cliente,
            telefono,
            mensaje_cliente,
            json.dumps(json_agente, ensure_ascii=False, default=str) if json_agente else None,
            accion_final,
            respuesta_bot,
            WHATSAPP_PROVIDER,
            CONVERSATION_AGENT_MODEL
        )
        conn.commit()
    except Exception as e:
        # El log no debe romper la venta ni el webhook.
        log_debug("No se pudo guardar LogConversacionAgente:", str(e))
    finally:
        conn.close()

# =========================================================
# CONTEXTO CONVERSACIONAL
# =========================================================
def obtener_contexto_cliente(id_cliente: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id_contexto,
                id_cliente,
                ultima_intencion,
                ultima_categoria,
                ultimo_termino,
                ultimo_producto,
                fecha_actualizacion
            FROM ContextoCliente
            WHERE id_cliente = ?
        """, id_cliente)
        return cursor.fetchone()
    finally:
        conn.close()

def guardar_o_actualizar_contexto_cliente(
    id_cliente: int,
    ultima_intencion: Optional[str] = None,
    ultima_categoria: Optional[str] = None,
    ultimo_termino: Optional[str] = None,
    ultimo_producto: Optional[str] = None
):
    contexto_actual = obtener_contexto_cliente(id_cliente)

    conn = get_connection()
    try:
        cursor = conn.cursor()

        if contexto_actual:
            cursor.execute("""
                UPDATE ContextoCliente
                SET
                    ultima_intencion = ?,
                    ultima_categoria = ?,
                    ultimo_termino = ?,
                    ultimo_producto = ?,
                    fecha_actualizacion = GETDATE()
                WHERE id_cliente = ?
            """,
                ultima_intencion,
                ultima_categoria,
                ultimo_termino,
                ultimo_producto,
                id_cliente
            )
        else:
            cursor.execute("""
                INSERT INTO ContextoCliente
                (
                    id_cliente,
                    ultima_intencion,
                    ultima_categoria,
                    ultimo_termino,
                    ultimo_producto,
                    fecha_actualizacion
                )
                VALUES (?, ?, ?, ?, ?, GETDATE())
            """,
                id_cliente,
                ultima_intencion,
                ultima_categoria,
                ultimo_termino,
                ultimo_producto
            )

        conn.commit()
    finally:
        conn.close()

def mensaje_usa_contexto(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)

    patrones = [
        "y cuanto cuesta",
        "y cuanto vale",
        "cuanto cuesta",
        "cuanto vale",
        "quiero ese",
        "quiero esa",
        "me interesa ese",
        "me interesa esa",
        "tienes otro",
        "tienes otra",
        "muestrame mas",
        "otro parecido",
        "algo parecido",
        "ese",
        "esa"
    ]

    return any(p in texto for p in patrones)

# =========================================================
# MEMORIA OPERATIVA DEL CLIENTE
# =========================================================
def obtener_memoria_cliente(id_cliente: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id_memoria,
                id_cliente,
                estado_proceso,
                id_juguete,
                producto_interes,
                categoria_interes,
                metodo_entrega,
                direccion_entrega,
                referencia_entrega,
                notas_cliente,
                fecha_actualizacion
            FROM MemoriaCliente
            WHERE id_cliente = ?
        """, id_cliente)
        return cursor.fetchone()
    finally:
        conn.close()
        
def guardar_o_actualizar_memoria_cliente(
    id_cliente: int,
    estado_proceso: Optional[str] = None,
    id_juguete: Optional[int] = None,
    producto_interes: Optional[str] = None,
    categoria_interes: Optional[str] = None,
    metodo_entrega: Optional[str] = None,
    direccion_entrega: Optional[str] = None,
    referencia_entrega: Optional[str] = None,
    notas_cliente: Optional[str] = None
):
    memoria_actual = obtener_memoria_cliente(id_cliente)

    conn = get_connection()
    try:
        cursor = conn.cursor()

        if memoria_actual:
            cursor.execute("""
                UPDATE MemoriaCliente
                SET
                    estado_proceso = ?,
                    id_juguete = ?,
                    producto_interes = ?,
                    categoria_interes = ?,
                    metodo_entrega = ?,
                    direccion_entrega = ?,
                    referencia_entrega = ?,
                    notas_cliente = ?,
                    fecha_actualizacion = GETDATE()
                WHERE id_cliente = ?
            """,
                estado_proceso,
                id_juguete,
                producto_interes,
                categoria_interes,
                metodo_entrega,
                direccion_entrega,
                referencia_entrega,
                notas_cliente,
                id_cliente
            )
        else:
            cursor.execute("""
                INSERT INTO MemoriaCliente
                (
                    id_cliente,
                    estado_proceso,
                    id_juguete,
                    producto_interes,
                    categoria_interes,
                    metodo_entrega,
                    direccion_entrega,
                    referencia_entrega,
                    notas_cliente,
                    fecha_actualizacion
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, GETDATE())
            """,
                id_cliente,
                estado_proceso,
                id_juguete,
                producto_interes,
                categoria_interes,
                metodo_entrega,
                direccion_entrega,
                referencia_entrega,
                notas_cliente
            )

        conn.commit()
    finally:
        conn.close()

def limpiar_memoria_cliente(id_cliente: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM MemoriaCliente
            WHERE id_cliente = ?
        """, id_cliente)
        conn.commit()
    finally:
        conn.close()

# =========================================================
# CATÃLOGO / BÃšSQUEDA
# =========================================================
def obtener_catalogo_busqueda():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT j.nombre AS termino
            FROM Juguete j
            UNION
            SELECT DISTINCT e.etiqueta AS termino
            FROM JugueteEtiqueta e
        """)
        filas = cursor.fetchall()
        return [normalizar_texto(f.termino) for f in filas if f.termino]
    finally:
        conn.close()

def corregir_termino_aproximado(texto_busqueda: str):
    catalogo = obtener_catalogo_busqueda()
    if not catalogo:
        return texto_busqueda

    coincidencia = process.extractOne(
        normalizar_texto(texto_busqueda),
        catalogo,
        scorer=fuzz.ratio
    )

    if coincidencia:
        termino, score, _ = coincidencia
        if score >= 75:
            return termino

    return texto_busqueda

def buscar_juguete_por_texto(texto_busqueda: str):
    texto_busqueda = normalizar_texto(texto_busqueda)
    texto_corregido = corregir_termino_aproximado(texto_busqueda)

    conn = get_connection()
    try:
        cursor = conn.cursor()
        patron = f"%{texto_corregido}%"
        cursor.execute("""
            SELECT TOP 5
                j.id_juguete,
                j.nombre,
                j.descripcion,
                j.precio,
                ISNULL(j.precio_compra, 0) AS precio_compra,
                j.stock,
                j.foto_url,
                j.foto_local,
                c.nombre AS categoria
            FROM Juguete j
            INNER JOIN Categoria c
                ON j.id_categoria = c.id_categoria
            LEFT JOIN JugueteEtiqueta e
                ON j.id_juguete = e.id_juguete
            WHERE
                LOWER(j.nombre) LIKE ?
                OR LOWER(j.descripcion) LIKE ?
                OR LOWER(e.etiqueta) LIKE ?
            GROUP BY
                j.id_juguete,
                j.nombre,
                j.descripcion,
                j.precio,
                j.precio_compra,
                j.stock,
                j.foto_url,
                j.foto_local,
                c.nombre
            ORDER BY
                j.nombre
        """, patron, patron, patron)
        return cursor.fetchall()
    finally:
        conn.close()

def buscar_por_categoria(nombre_categoria: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                j.id_juguete,
                j.nombre,
                j.descripcion,
                j.precio,
                j.stock,
                j.foto_url,
                j.foto_local,
                c.nombre AS categoria
            FROM Juguete j
            INNER JOIN Categoria c
                ON j.id_categoria = c.id_categoria
            WHERE c.nombre = ?
            ORDER BY j.nombre
        """, nombre_categoria)
        return cursor.fetchall()
    finally:
        conn.close()

def obtener_expos():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT nombre, ubicacion, fecha_inicio, fecha_fin
            FROM Expo
            WHERE fecha_fin >= CAST(GETDATE() AS DATE)
            ORDER BY fecha_inicio
        """)
        return cursor.fetchall()
    finally:
        conn.close()

# =========================================================
# LÃ“GICA CHATBOT
# =========================================================
def detectar_intencion(mensaje: str) -> str:
    texto = normalizar_texto(mensaje)

    patrones_compra = [
        "quiero comprar", "comprar", "lo quiero", "me interesa",
        "encargar", "apartar", "separar", "quiero uno", "quiero una",
        "quiero el", "quiero la", "si ese", "sÃ­ ese", "ese", "esa",
        "me llevo", "quiero el", "quiero la"
    ]

    patrones_cotizacion = [
        "cuanto cuesta", "cuanto sale", "cuanto vale", "precio",
        "cotizacion", "coste", "costo"
    ]

    patrones_entrega = [
        "a domicilio", "domicilio", "envio", "entrega",
        "mandadito", "mandado", "reparto", "delivery",
        "recoger en expo", "lo recojo", "paso por el"
    ]

    patrones_expos = [
        "que expos", "que expo", "exposicion", "exposiciones",
        "evento", "eventos", "donde estaran", "donde van a estar",
        "proximas expos", "feria", "ferias"
    ]

    if any(p in texto for p in patrones_cotizacion):
        return "Cotizacion"

    if any(p in texto for p in patrones_expos):
        return "Expos"

    if any(p in texto for p in patrones_compra):
        return "Compra"

    if any(p in texto for p in patrones_entrega):
        if any(x in texto for x in [
            "quiero", "oso", "peluche", "carrito", "juguete",
            "producto", "figura", "max steel", "batman"
        ]):
            return "Compra"
        return "Entrega"

    return "Consulta"
def detectar_categoria(mensaje: str):
    texto = normalizar_texto(mensaje)

    categorias = {
        "bebes": "BebÃ©s",
        "bebe": "BebÃ©s",
        "para bebe": "BebÃ©s",
        "ninos": "NiÃ±os",
        "nino": "NiÃ±os",
        "para ninos": "NiÃ±os",
        "ninas": "NiÃ±as",
        "nina": "NiÃ±as",
        "para ninas": "NiÃ±as",
        "peluches": "Peluches",
        "peluche": "Peluches",
        "juegos de mesa": "Juegos de mesa",
        "juego de mesa": "Juegos de mesa",
        "mesa": "Juegos de mesa",
        "coleccion": "Coleccionables",
        "coleccionable": "Coleccionables",
        "coleccionables": "Coleccionables",
    }

    coincidencias = []
    for clave, valor in categorias.items():
        if clave in texto:
            coincidencias.append((len(clave), valor))

    if coincidencias:
        coincidencias.sort(reverse=True)
        return coincidencias[0][1]

    return None

def es_saludo(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    saludos = [
        "hola", "holi", "buenas", "buen dia", "buenos dias",
        "buenas tardes", "buenas noches", "hey", "que tal",
        "hello", "hi"
    ]
    return any(texto == s or texto.startswith(s + " ") for s in saludos)

def es_despedida(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    despedidas = [
        "gracias", "muchas gracias", "ok gracias", "sale gracias",
        "adios", "bye", "hasta luego", "perfecto gracias"
    ]
    return any(texto == d or texto.endswith(" " + d) for d in despedidas)

def detectar_metodo_entrega(mensaje: str) -> Optional[str]:
    texto = normalizar_texto(mensaje)

    patrones_expo = [
        "recoger en expo",
        "recogo en expo",
        "lo recojo en expo",
        "paso por el en expo",
        "para recoger en expo",
        "quiero recoger en expo",
        "entrega local"
    ]

    patrones_domicilio = [
        "a domicilio",
        "domicilio",
        "envio",
        "entrega",
        "delivery"
    ]

    if any(p in texto for p in patrones_expo):
        return "Expo"

    if any(p in texto for p in patrones_domicilio):
        return "Domicilio"

    return None

def es_frase_bloqueada_como_producto(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    frases_bloqueadas = {
        "ya es todo",
        "no",
        "no quiero mas",
        "cerrar pedido",
        "es todo",
        "efectivo",
        "pago en linea",
        "mercado pago",
        "tarjeta",
        "a domicilio",
        "domicilio",
        "entrega local",
        "recoger en expo"
    }
    return texto in frases_bloqueadas

def es_confirmacion_producto_por_contexto(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    confirmaciones = {
        "si", "sí", "si ese", "sí ese", "ese", "esa",
        "si ese quiero", "sí ese quiero", "ese mismo", "esa misma",
        "quiero ese", "quiero esa", "me interesa ese", "me interesa esa"
    }
    return texto in confirmaciones

def parece_direccion(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)

    pistas = [
        "calle", "colonia", "numero", "número", "cp", "c.p", "casa",
        "avenida", "av", "fraccionamiento", "interior", "exterior",
        "domicilio", "fracc"
    ]

    return any(p in texto for p in pistas) or len(texto) >= 25

def parece_referencia_entrega(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)

    pistas = [
        "referencia", "frente a", "cerca de", "junto a", "a un lado de",
        "porton", "portón", "casa", "puerta", "esquina", "color",
        "kiosko", "farmacia", "tienda", "edificio"
    ]

    return any(p in texto for p in pistas) or len(texto) >= 10

def es_confirmacion_pedido(mensaje: str) -> bool:
    """ConfirmaciÃ³n final estricta para crear pedido.

    No acepta solo "sÃ­", "ok", "va" o "efectivo" para evitar pedidos accidentales.
    """
    texto = normalizar_texto(mensaje)
    confirmaciones = {
        "confirmar pedido",
        "confirmo pedido",
        "si confirmo el pedido",
        "confirmo el pedido",
        "confirmar compra",
        "confirmo la compra",
        "finalizar pedido",
        "registrar pedido",
        "crear pedido"
    }
    return texto in confirmaciones


def es_cancelacion_pedido(mensaje: str) -> bool:
    """CancelaciÃ³n explÃ­cita.

    No se toma "no" como cancelaciÃ³n general, porque dentro del carrito puede
    significar "no quiero agregar mÃ¡s productos".
    """
    texto = normalizar_texto(mensaje)
    cancelaciones = {
        "cancelar", "cancela", "cancelar pedido", "cancelar compra",
        "no confirmar", "ya no quiero comprar", "ya no quiero el pedido",
        "mejor cancela", "mejor cancelar", "mejor no comprar",
        "quiero cancelar", "cancela todo", "anular pedido",
        "no quiero ese", "no quiero ese producto", "ese no",
        "cambiar producto", "quita ese", "eliminar ese"
    }
    return texto in cancelaciones

def extraer_cantidad_mensaje(mensaje: str) -> Optional[int]:
    """Extrae cantidades naturales del mensaje del cliente.
    Devuelve None si no hay cantidad clara. Limita cantidades absurdas para evitar pedidos errÃ³neos.
    """
    texto = normalizar_texto(mensaje)

    numeros_texto = {
        "uno": 1, "una": 1, "un": 1,
        "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
        "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
    }

    patrones = [
        r"\b(\d{1,2})\s*(?:piezas|pieza|pz|pzs|unidades|unidad|juguetes|productos)?\b",
        r"\b(?:cantidad|quiero|ocupo|necesito|dame|apartame|aparta|llevo)\s+(\d{1,2})\b",
    ]

    for patron in patrones:
        match = re.search(patron, texto)
        if match:
            try:
                cantidad = int(match.group(1))
                if 1 <= cantidad <= 99:
                    return cantidad
            except Exception:
                pass

    for palabra, cantidad in numeros_texto.items():
        if re.search(rf"\b{re.escape(palabra)}\b", texto):
            return cantidad

    return None


def limpiar_cantidad_de_texto(texto: str) -> str:
    """Quita frases de cantidad para que no contaminen la bÃºsqueda del producto."""
    texto = normalizar_texto(texto)
    patrones = [
        r"\b\d{1,2}\s*(?:piezas|pieza|pz|pzs|unidades|unidad|juguetes|productos)?\b",
        r"\b(?:uno|una|un|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\b",
        r"\b(?:cantidad|ocupo|necesito|dame|apartame|aparta|llevo)\b",
    ]
    for patron in patrones:
        texto = re.sub(patron, " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def actualizar_cantidad_en_notas(notas: Optional[str], cantidad: Optional[int]) -> Optional[str]:
    """Guarda CantidadPedido=N dentro de notas_cliente sin requerir migraciÃ³n de base de datos."""
    if cantidad is None:
        return notas

    base = notas or ""
    base = re.sub(r"\bCantidadPedido\s*=\s*\d+\b", "", base).strip(" ;|\n\t")
    sufijo = f"CantidadPedido={int(cantidad)}"
    if base:
        return f"{base}; {sufijo}"
    return sufijo


def obtener_cantidad_desde_notas(notas: Optional[str]) -> Optional[int]:
    if not notas:
        return None
    match = re.search(r"\bCantidadPedido\s*=\s*(\d+)\b", str(notas))
    if not match:
        return None
    try:
        cantidad = int(match.group(1))
        if 1 <= cantidad <= 99:
            return cantidad
    except Exception:
        pass
    return None


# =========================================================
# CARRITO CONVERSACIONAL EN MEMORIA
# =========================================================
CART_PREFIX = "CARRITO_JSON="

def _extraer_carrito_de_notas(notas: Optional[str]) -> list[dict]:
    """Extrae el carrito aunque notas_cliente tenga otros metadatos despuÃ©s.

    Antes se intentaba decodificar todo lo que venÃ­a despuÃ©s de CARRITO_JSON=.
    Si luego se agregaba '; PAGO_METODO=Efectivo', json.loads fallaba y el bot
    creÃ­a que el carrito estaba vacÃ­o.
    """
    if not notas:
        return []
    texto = str(notas)
    idx = texto.find(CART_PREFIX)
    if idx < 0:
        return []
    raw = texto[idx + len(CART_PREFIX):].strip()
    try:
        data, _end = json.JSONDecoder().raw_decode(raw)
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict) and x.get("id_juguete")]
    except Exception:
        return []
    return []

def _quitar_carrito_de_notas(notas: Optional[str]) -> str:
    texto = str(notas or "")
    idx = texto.find(CART_PREFIX)
    if idx < 0:
        return texto.strip(" ;|\n\t")
    return texto[:idx].strip(" ;|\n\t")

def _guardar_carrito_en_notas(notas: Optional[str], carrito: list[dict]) -> str:
    base = _quitar_carrito_de_notas(notas)
    base = re.sub(r"\bCantidadPedido\s*=\s*\d+\b", "", base).strip(" ;|\n\t")
    payload = json.dumps(carrito, ensure_ascii=False, separators=(",", ":"))
    return f"{base}; {CART_PREFIX}{payload}" if base else f"{CART_PREFIX}{payload}"

def obtener_carrito_memoria(memoria) -> list[dict]:
    carrito = _extraer_carrito_de_notas(getattr(memoria, "notas_cliente", None))
    if carrito:
        return carrito
    if getattr(memoria, "id_juguete", None):
        juguete = obtener_juguete_resumen_por_id(memoria.id_juguete)
        if juguete:
            return [{"id_juguete": int(juguete.id_juguete), "nombre": str(juguete.nombre), "cantidad": int(obtener_cantidad_desde_notas(getattr(memoria, "notas_cliente", None)) or 1), "precio_unitario": float(juguete.precio), "stock": int(juguete.stock or 0)}]
    return []

def agregar_producto_actual_a_carrito(memoria, cantidad: int) -> tuple[bool, str, Optional[str]]:
    if not getattr(memoria, "id_juguete", None):
        return False, "No hay producto seleccionado para agregar al carrito.", None
    juguete = obtener_juguete_resumen_por_id(memoria.id_juguete)
    if not juguete:
        return False, "El producto seleccionado ya no existe en el catÃ¡logo.", None
    cantidad = int(cantidad)
    stock = int(juguete.stock or 0)
    if cantidad < 1:
        return False, "La cantidad debe ser mayor a cero.", None
    if cantidad > stock:
        return False, f"Solo hay {stock} pieza(s) disponibles de {juguete.nombre}.", None
    carrito = _extraer_carrito_de_notas(getattr(memoria, "notas_cliente", None))
    actualizado = False
    for item in carrito:
        if int(item.get("id_juguete")) == int(juguete.id_juguete):
            item.update({"cantidad": cantidad, "nombre": str(juguete.nombre), "precio_unitario": float(juguete.precio), "stock": stock})
            actualizado = True
            break
    if not actualizado:
        carrito.append({"id_juguete": int(juguete.id_juguete), "nombre": str(juguete.nombre), "cantidad": cantidad, "precio_unitario": float(juguete.precio), "stock": stock})
    return True, f"{juguete.nombre} agregado al carrito.", _guardar_carrito_en_notas(getattr(memoria, "notas_cliente", None), carrito)

def texto_carrito_corto(memoria) -> str:
    carrito = obtener_carrito_memoria(memoria)
    if not carrito:
        return "El carrito estÃ¡ vacÃ­o."
    lineas = []
    total = 0.0
    for i, item in enumerate(carrito, start=1):
        cantidad = int(item.get("cantidad", 1))
        precio = float(item.get("precio_unitario", 0))
        subtotal = round(cantidad * precio, 2)
        total += subtotal
        lineas.append(f"{i}. {item.get('nombre')} x{cantidad} = ${subtotal:.2f}")
    lineas.append(f"Total estimado: ${total:.2f}")
    return "\n".join(lineas)

def es_si_agregar_otro(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    return texto in {
        "si", "si agregar", "si agrega", "si agregar otro", "si agrego otro",
        "agrega otro", "agregar otro", "otro", "otra", "quiero otro",
        "quiero agregar otro", "quiero anadir otro", "anadir otro", "sumar otro"
    }

def es_no_agregar_otro(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    return texto in {
        "no", "no gracias", "no cerrar", "no cerrar pedido", "no quiero otro",
        "no quiero mas", "no quiero mÃ¡s",
        "no agregar otro", "no agrega otro", "asi esta bien", "asÃ­ estÃ¡ bien",
        "seria todo", "serÃ­a todo", "ya es todo", "ya seria todo", "ya serÃ­a todo",
        "eso es todo", "es todo", "con eso", "con eso esta bien", "con eso estÃ¡ bien",
        "ya no", "nada mas", "nada mÃ¡s", "solo eso", "solo ese", "solo ese producto",
        "cerrar", "cerrar pedido", "cerrar carrito", "finalizar pedido",
        "finalizar compra", "terminar pedido", "terminar compra"
    }

def es_cerrar_carrito(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    return es_no_agregar_otro(mensaje) or texto in {"cerrar carrito", "cerramos", "terminar compra", "finalizar compra"}

def es_pago_online(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    return texto in {"online", "en linea", "pago en linea", "mercado pago", "mercadopago", "link de pago", "tarjeta", "transferencia", "pagar en linea"}

def es_pago_efectivo(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    return texto in {"efectivo", "pago efectivo", "en efectivo", "contra entrega", "pagar en efectivo", "pago al recibir"}

def es_mensaje_no_producto(mensaje: str, entidades: Optional[Dict[str, Any]] = None) -> bool:
    texto = normalizar_texto(mensaje)
    if es_frase_bloqueada_como_producto(texto):
        return True
    if texto == "entrega local":
        return True
    if es_no_agregar_otro(texto) or es_cerrar_carrito(texto):
        return True
    if es_pago_online(texto) or es_pago_efectivo(texto):
        return True
    if texto in {
        "domicilio", "a domicilio", "recoger", "recoger en expo", "expo", "envio", "envÃ­o",
        "direccion", "direcciÃ³n", "colonia", "calle", "avenida", "av", "carrera"
    }:
        return True
    if entidades and (entidades.get("parece_direccion") or entidades.get("parece_referencia")):
        return True
    return False

def ajustar_entidades_por_estado(memoria, analisis: dict, entidades: dict, mensaje: str) -> None:
    estado = getattr(memoria, "estado_proceso", None) if memoria else None
    if estado == "EsperandoDireccion":
        entidades["cantidad"] = None
    if es_frase_bloqueada_como_producto(mensaje):
        entidades["producto"] = None
        if analisis.get("termino_busqueda") == normalizar_texto(mensaje):
            analisis["termino_busqueda"] = ""

def _quitar_clave_notas(notas: Optional[str], clave: str) -> str:
    texto = str(notas or "")
    patron = rf"(?:^|[;|]\s*){re.escape(clave)}=[^;|\n]*"
    texto = re.sub(patron, "", texto).strip(" ;|\n\t")
    return texto

def guardar_metodo_pago_en_notas(notas: Optional[str], metodo_pago: str) -> str:
    base = _quitar_clave_notas(notas, "PAGO_METODO")
    return f"{base}; PAGO_METODO={metodo_pago}" if base else f"PAGO_METODO={metodo_pago}"

def obtener_metodo_pago_desde_notas(notas: Optional[str]) -> Optional[str]:
    m = re.search(r"PAGO_METODO=([^;|\n]+)", str(notas or ""))
    return m.group(1).strip() if m else None


def guardar_confirmacion_final_en_notas(notas: Optional[str]) -> str:
    """Marca interna que habilita crear el pedido solo despuÃ©s de confirmaciÃ³n explÃ­cita."""
    base = _quitar_clave_notas(notas, "CONFIRMACION_FINAL_OK")
    return f"{base}; CONFIRMACION_FINAL_OK=1" if base else "CONFIRMACION_FINAL_OK=1"


def tiene_confirmacion_final_en_notas(notas: Optional[str]) -> bool:
    return bool(re.search(r"(?:^|[;|]\s*)CONFIRMACION_FINAL_OK=1(?:[;|]|$)", str(notas or "")))


def respuesta_resumen_confirmacion_final(memoria, metodo_pago: Optional[str] = None) -> str:
    """Construye resumen final y obliga a confirmar o cancelar antes de crear pedido."""
    resumen = construir_resumen_pedido_desde_memoria(memoria)
    encabezado = f"Perfecto, elegiste {metodo_pago}.\n\n" if metodo_pago else ""
    return (
        f"{encabezado}{resumen}\n\n"
        "AÃºn no registro el pedido. Elige una opciÃ³n:\n"
        "â€¢ confirmar pedido\n"
        "â€¢ cancelar pedido"
    )

def respuesta_preguntar_metodo_pago(memoria) -> str:
    total_productos = sum(float(i.get("precio_unitario", 0)) * int(i.get("cantidad", 1)) for i in obtener_carrito_memoria(memoria))
    envio = ENVIO_DOMICILIO if getattr(memoria, "metodo_entrega", None) == "Domicilio" else 0.0
    total = total_productos + envio
    lineas = [
        "Perfecto âœ… Ya tengo los datos de entrega.",
        "",
        f"Subtotal productos: ${total_productos:.2f}",
    ]
    if envio > 0:
        lineas.append(f"EnvÃ­o a domicilio: ${envio:.2f}")
    lineas.extend([
        f"Total a pagar: ${total:.2f}",
        "",
        "Ahora elige mÃ©todo de pago:",
        "â€¢ efectivo",
        "â€¢ pago en lÃ­nea",
        "",
        "Responde exactamente: efectivo  o  pago en lÃ­nea"
    ])
    return "\n".join(lineas)

def respuesta_preguntar_otro_producto(memoria) -> str:
    return (
        "Listo âœ… AgreguÃ© el producto al carrito.\n\n"
        f"{texto_carrito_corto(memoria)}\n\n"
        "Antes de cerrar el pedido dime si quieres agregar otro producto.\n"
        "Puedes responder de estas formas:\n"
        "â€¢ sÃ­, agregar otro\n"
        "â€¢ no, cerrar pedido\n\n"
        "Si tienes duda, escribe: Â¿cÃ³mo sigo? y te explico sin borrar tu carrito."
    )

def es_pregunta_ayuda_flujo(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    patrones = {
        "ayuda", "como sigo", "como continuo", "como funciona", "que hago",
        "que sigue", "no entiendo", "explica", "explicame", "opciones",
        "como tengo que responder", "que respondo"
    }
    return texto in patrones or any(p in texto for p in patrones)

def respuesta_ayuda_flujo(memoria) -> str:
    estado = getattr(memoria, "estado_proceso", None)
    if estado == "EsperandoConfirmacionProducto":
        return (
            "Claro ðŸ˜Š Para seguir necesito que confirmes el producto que te mostrÃ©.\n\n"
            "Responde una opciÃ³n:\n"
            "â€¢ sÃ­\n"
            "â€¢ no, cambiar producto\n"
            "â€¢ muÃ©strame productos\n\n"
            "No perderÃ© el contexto de tu pedido."
        )
    if estado == "EsperandoCantidad":
        return (
            "Claro ðŸ˜Š En este paso solo necesito la cantidad del producto seleccionado.\n\n"
            "Ejemplos vÃ¡lidos:\n"
            "â€¢ 1\n"
            "â€¢ 2 piezas\n"
            "â€¢ quiero 3\n\n"
            "Cuando me digas la cantidad, lo agrego al carrito."
        )
    if estado == "EsperandoMasProductos":
        return (
            "Tu carrito sigue guardado âœ…\n\n"
            f"{texto_carrito_corto(memoria)}\n\n"
            "Ahora responde una opciÃ³n:\n"
            "â€¢ sÃ­, agregar otro\n"
            "â€¢ no, cerrar pedido\n"
            "â€¢ escribe el nombre de otro producto\n"
            "â€¢ muÃ©strame productos"
        )
    if estado == "EsperandoDireccion":
        return (
            "Para continuar con la entrega necesito tu direcciÃ³n completa en un solo mensaje.\n\n"
            "Formato recomendado:\n"
            "Calle y nÃºmero, colonia o fraccionamiento, interior o exterior si aplica.\n\n"
            "Ejemplo: Del Ajusco 32, Lomas, interior 7"
        )
    if estado == "EsperandoReferencia":
        return (
            "Ya tengo la direcciÃ³n. Ahora necesito una referencia breve para ubicar la entrega.\n\n"
            "Ejemplos:\n"
            "â€¢ frente al parque\n"
            "â€¢ portÃ³n negro\n"
            "â€¢ casa color crema"
        )
    if estado == "EsperandoMetodoPago":
        return (
            "Ya casi terminamos ðŸ˜Š Solo falta elegir el mÃ©todo de pago.\n\n"
            "Responde una opciÃ³n:\n"
            "â€¢ efectivo\n"
            "â€¢ pago en lÃ­nea"
        )
    return (
        "Puedo ayudarte a comprar por WhatsApp ðŸ˜Š\n\n"
        "1. Me dices quÃ© producto buscas.\n"
        "2. Confirmas el producto.\n"
        "3. Indicas cantidad.\n"
        "4. Te pregunto si quieres agregar mÃ¡s productos.\n"
        "5. Elegimos entrega y pago.\n\n"
        "Escribe el nombre del juguete o una categorÃ­a para empezar."
    )

def respuesta_redireccion_estado(memoria, motivo: Optional[str] = None) -> str:
    estado = getattr(memoria, "estado_proceso", None)
    prefijo = "Te respondo sin perder tu pedido ðŸ˜Š\n" if motivo else ""
    if estado == "EsperandoConfirmacionProducto":
        return (
            prefijo +
            "En este paso necesito confirmar el producto antes de avanzar.\n\n"
            f"Producto pendiente: {getattr(memoria, 'producto_interes', None) or 'producto seleccionado'}\n\n"
            "Responde: sÃ­, no cambiar producto, o muÃ©strame productos."
        )
    if estado == "EsperandoCantidad":
        return (
            prefijo +
            "Ya tengo el producto seleccionado. Para no agregar cantidades incorrectas, responde solo la cantidad.\n\n"
            "Ejemplos: 1, 2 piezas, quiero 3"
        )
    if estado == "EsperandoMasProductos":
        return respuesta_ayuda_flujo(memoria)
    if estado == "EsperandoDireccion":
        return respuesta_ayuda_flujo(memoria)
    if estado == "EsperandoReferencia":
        return respuesta_ayuda_flujo(memoria)
    if estado == "EsperandoMetodoPago":
        return respuesta_ayuda_flujo(memoria)
    return respuesta_ayuda_flujo(memoria)

def guardar_producto_en_carrito_por_juguete(id_cliente: int, memoria, juguete, cantidad: int, metodo_entrega: Optional[str] = None) -> tuple[bool, str, Optional[object]]:
    """Selecciona un juguete, valida stock, lo agrega al carrito y devuelve memoria actualizada."""
    notas_base = getattr(memoria, "notas_cliente", None) if memoria else None
    guardar_o_actualizar_memoria_cliente(
        id_cliente=id_cliente,
        estado_proceso="EsperandoCantidad",
        id_juguete=juguete.id_juguete,
        producto_interes=juguete.nombre,
        categoria_interes=getattr(juguete, "categoria", None),
        metodo_entrega=metodo_entrega,
        direccion_entrega=getattr(memoria, "direccion_entrega", None) if memoria else None,
        referencia_entrega=getattr(memoria, "referencia_entrega", None) if memoria else None,
        notas_cliente=notas_base or "Compra detectada por agente"
    )
    memoria_tmp = obtener_memoria_cliente(id_cliente)
    ok, detalle, notas_carrito = agregar_producto_actual_a_carrito(memoria_tmp, int(cantidad))
    if not ok:
        return False, detalle, memoria_tmp
    guardar_o_actualizar_memoria_cliente(
        id_cliente=id_cliente,
        estado_proceso="EsperandoMasProductos",
        id_juguete=juguete.id_juguete,
        producto_interes=juguete.nombre,
        categoria_interes=getattr(juguete, "categoria", None),
        metodo_entrega=metodo_entrega,
        direccion_entrega=getattr(memoria, "direccion_entrega", None) if memoria else None,
        referencia_entrega=getattr(memoria, "referencia_entrega", None) if memoria else None,
        notas_cliente=notas_carrito
    )
    return True, detalle, obtener_memoria_cliente(id_cliente)

def obtener_cantidad_memoria(memoria) -> int:
    carrito = _extraer_carrito_de_notas(getattr(memoria, "notas_cliente", None))
    if carrito:
        return int(carrito[0].get("cantidad", 1))
    cantidad = obtener_cantidad_desde_notas(getattr(memoria, "notas_cliente", None))
    return cantidad if cantidad is not None else 1


def mensaje_pedir_cantidad(nombre_producto: Optional[str] = None) -> str:
    producto = f" para {nombre_producto}" if nombre_producto else ""
    return (
        f"Perfecto ðŸ˜Š Ya tengo el producto{producto}.\n\n"
        "Ahora dime cuÃ¡ntas piezas quieres.\n"
        "Ejemplos:\n"
        "â€¢ 1\n"
        "â€¢ 2 piezas\n"
        "â€¢ Quiero 3"
    )


def respuesta_despues_de_cantidad(memoria) -> str:
    if getattr(memoria, "metodo_entrega", None) == "Domicilio":
        return (
            "Perfecto ðŸšš Ya guardÃ© la cantidad.\n"
            "Ahora envÃ­ame tu direcciÃ³n completa en un solo mensaje.\n\n"
            "Formato:\n"
            "â€¢ Calle y nÃºmero\n"
            "â€¢ Colonia o fraccionamiento\n"
            "â€¢ Interior o exterior si aplica"
        )

    return (
        "Perfecto ðŸ˜Š Ya guardÃ© la cantidad.\n\n"
        "Ahora responde solo una de estas opciones para continuar:\n"
        "â€¢ a domicilio\n"
        "â€¢ recoger en expo"
    )

def extraer_termino_busqueda(mensaje: str) -> str:
    texto = normalizar_texto(mensaje)

    if es_frase_bloqueada_como_producto(texto):
        return ""

    saludos_y_cortesia = {
        "hola", "holi", "buenas", "buen dia", "buenos dias",
        "buenas tardes", "buenas noches", "hey", "que tal",
        "gracias", "muchas gracias", "ok gracias", "sale gracias",
        "adios", "bye", "hasta luego", "perfecto gracias"
    }

    if texto in saludos_y_cortesia:
        return ""

    frases_basura = [
        "cuanto cuesta", "cuanto sale", "cuanto vale",
        "precio de", "precio del", "precio",
        "quiero comprar", "quiero uno", "quiero una",
        "me interesa", "cotizacion de", "cotizacion",
        "informacion de", "informacion sobre", "info de"
    ]

    for frase in frases_basura:
        texto = re.sub(rf"\b{re.escape(frase)}\b", " ", texto)

    palabras_basura = {
        "comprar", "quiero", "tienen", "busco", "buscas",
        "hola", "holi", "buenas", "gracias", "adios", "bye",
        "del", "de", "la", "el", "los", "las", "un", "una", "unos", "unas",
        "para", "por", "favor", "si", "ese", "esa"
    }

    tokens = [t for t in texto.split() if t not in palabras_basura]
    texto = " ".join(tokens).strip()

    if texto in {"", "juguete", "juguetes", "producto", "productos"} or es_frase_bloqueada_como_producto(texto):
        return ""

    return texto

def limpiar_termino_producto(texto: str) -> str:
    texto = limpiar_cantidad_de_texto(texto)

    frases_a_quitar = [
        "a domicilio",
        "para recoger en expo",
        "recoger en expo",
        "lo recojo en expo",
        "quiero recoger en expo",
        "entrega local",
        "con entrega",
        "con envio",
        "con entrega a domicilio"
    ]

    for frase in frases_a_quitar:
        texto = re.sub(rf"\b{re.escape(frase)}\b", " ", texto)

    texto = re.sub(r"\s+", " ", texto).strip()
    if es_frase_bloqueada_como_producto(texto):
        return ""
    return texto

def extraer_entidades_mensaje(mensaje: str) -> dict:
    texto = normalizar_texto(mensaje)
    metodo_entrega = detectar_metodo_entrega(mensaje)
    cantidad = extraer_cantidad_mensaje(mensaje)
    categoria = detectar_categoria(mensaje)
    termino = extraer_termino_busqueda(mensaje)
    intencion = detectar_intencion(mensaje)

    palabras_compra = [
        "quiero", "comprar", "aparta", "apartar", "encarga", "encargar",
        "me interesa", "lo quiero", "me lo llevo", "separar"
    ]
    palabras_precio = [
        "precio", "cuanto cuesta", "cuanto vale", "cuanto sale", "cotizacion"
    ]

    accion = "consulta"
    if any(p in texto for p in palabras_precio):
        accion = "cotizacion"
    elif any(p in texto for p in palabras_compra) or intencion == "Compra":
        accion = "compra"

    producto = None
    if termino and not categoria:
        producto = limpiar_termino_producto(termino)
        if producto in {"", "domicilio", "expo", "recoger"} or es_frase_bloqueada_como_producto(producto):
            producto = None

    if producto and metodo_entrega and accion == "consulta":
        accion = "compra"

    return {
        "texto_normalizado": texto,
        "accion": accion,
        "producto": producto,
        "categoria": categoria,
        "metodo_entrega": metodo_entrega,
        "cantidad": cantidad,
        "confirmacion_producto": es_confirmacion_producto_por_contexto(mensaje),
        "confirmacion_pedido": es_confirmacion_pedido(mensaje),
        "cancelacion": es_cancelacion_pedido(mensaje),
        "parece_direccion": parece_direccion(mensaje),
        "parece_referencia": parece_referencia_entrega(mensaje),
        "intencion_detectada": intencion
    }
    
def clasificar_mensaje_ambiguo_con_openai(
    mensaje: str,
    contexto: Optional[Any] = None,
    memoria: Optional[Any] = None
) -> Optional[dict]:
    """
    Usa OpenAI Ãºnicamente cuando el mensaje es ambiguo y las reglas no bastan.
    Devuelve un dict con estructura fija o None si no pudo clasificar.
    """
    if not client_openai:
        return None

    texto = normalizar_texto(mensaje)
    if not texto:
        return None

    contexto_dict = {
        "ultima_intencion": getattr(contexto, "ultima_intencion", None) if contexto else None,
        "ultima_categoria": getattr(contexto, "ultima_categoria", None) if contexto else None,
        "ultimo_termino": getattr(contexto, "ultimo_termino", None) if contexto else None,
        "ultimo_producto": getattr(contexto, "ultimo_producto", None) if contexto else None,
    }

    memoria_dict = {
        "estado_proceso": getattr(memoria, "estado_proceso", None) if memoria else None,
        "producto_interes": getattr(memoria, "producto_interes", None) if memoria else None,
        "categoria_interes": getattr(memoria, "categoria_interes", None) if memoria else None,
        "metodo_entrega": getattr(memoria, "metodo_entrega", None) if memoria else None,
        "cantidad": obtener_cantidad_desde_notas(getattr(memoria, "notas_cliente", None)) if memoria else None,
    }

    prompt = f"""
Eres un clasificador de mensajes para una jugueterÃ­a por WhatsApp en MÃ©xico.
Debes interpretar modismos, faltas de ortografÃ­a, abreviaturas y mensajes incompletos sin inventar datos.

Debes analizar el mensaje del usuario y responder ÃšNICAMENTE con JSON vÃ¡lido.
No expliques nada fuera del JSON.

Contexto conversacional actual:
{json.dumps(contexto_dict, ensure_ascii=False)}

Memoria operativa actual:
{json.dumps(memoria_dict, ensure_ascii=False)}

Mensaje del usuario:
"{mensaje}"

Responde con esta estructura exacta:
{{
  "accion": "consulta|compra|cotizacion|entrega|expos|confirmacion|cancelacion|desconocida",
  "producto": "texto o null",
  "categoria": "BebÃ©s|NiÃ±os|NiÃ±as|Peluches|Juegos de mesa|Coleccionables|null",
  "metodo_entrega": "Domicilio|Expo|null",
  "cantidad": 1,
  "confirmacion_producto": true,
  "confirmacion_pedido": false,
  "cancelacion": false,
  "requiere_aclaracion": false,
  "mensaje_aclaracion": "texto o null",
  "texto_interpretado": "texto limpio o null",
  "palabras_desconocidas": []
}}

Reglas:
- Usa "compra" si el usuario quiere apartar, pedir, comprar, llevarse o confirmar un producto.
- Usa "cotizacion" si claramente pide precio.
- Usa "entrega" solo si pregunta por formas de entrega o responde Ãºnicamente el mÃ©todo.
- Usa "expos" solo si pregunta por eventos o expos.
- Usa "confirmacion" si confirma algo del flujo actual.
- Usa "cancelacion" si cancela el pedido o la compra.
- Si el usuario responde algo como "sÃ­ ese", "ese", "esa", activa confirmacion_producto=true.
- Si el usuario responde algo como "confirmar", activa confirmacion_pedido=true.
- Si el usuario responde algo como "cancelar", activa cancelacion=true.
- Si el usuario indica cantidad, devuelve cantidad como nÃºmero entero. Si no hay cantidad clara, usa null.
- Traduce modismos comunes: "ocupo" = necesito, "me late" = me interesa, "jalo" = confirmo, "arre" = confirmo, "mandamelo" = a domicilio, "recojer" = recoger.
- Filtra palabras de relleno o desconocidas que no ayuden a encontrar producto, pero conserva el posible nombre del juguete.
- Si detectas palabras desconocidas, ponlas en palabras_desconocidas.
- Si no puedes identificar bien quÃ© quiso decir, usa requiere_aclaracion=true y escribe un mensaje_aclaracion breve y Ãºtil.
- No inventes productos si no estÃ¡n claros.
- Si hay un producto parcial como "oso", devuÃ©lvelo tal cual.
""".strip()

    try:
        response = client_openai.responses.create(
            model=VISION_MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt}
                    ]
                }
            ]
        )

        texto_respuesta = getattr(response, "output_text", "") or ""
        texto_respuesta = limpiar_json_respuesta(texto_respuesta)
        data = json.loads(texto_respuesta)

        accion = str(data.get("accion") or "desconocida").strip().lower()
        producto = data.get("producto")
        categoria = data.get("categoria")
        metodo_entrega = data.get("metodo_entrega")
        cantidad = data.get("cantidad")
        confirmacion_producto = bool(data.get("confirmacion_producto", False))
        confirmacion_pedido = bool(data.get("confirmacion_pedido", False))
        cancelacion = bool(data.get("cancelacion", False))
        requiere_aclaracion = bool(data.get("requiere_aclaracion", False))
        mensaje_aclaracion = data.get("mensaje_aclaracion")
        texto_interpretado = data.get("texto_interpretado")
        palabras_desconocidas = data.get("palabras_desconocidas") or []

        acciones_validas = {
            "consulta", "compra", "cotizacion", "entrega",
            "expos", "confirmacion", "cancelacion", "desconocida"
        }
        categorias_validas = {
            "BebÃ©s", "NiÃ±os", "NiÃ±as", "Peluches",
            "Juegos de mesa", "Coleccionables", None
        }
        metodos_validos = {"Domicilio", "Expo", None}

        if accion not in acciones_validas:
            accion = "desconocida"

        if categoria not in categorias_validas:
            categoria = None

        if metodo_entrega not in metodos_validos:
            metodo_entrega = None

        if producto is not None:
            producto = str(producto).strip() or None

        if mensaje_aclaracion is not None:
            mensaje_aclaracion = str(mensaje_aclaracion).strip() or None

        if texto_interpretado is not None:
            texto_interpretado = str(texto_interpretado).strip() or None

        if not isinstance(palabras_desconocidas, list):
            palabras_desconocidas = []
        palabras_desconocidas = [str(p).strip() for p in palabras_desconocidas if str(p).strip()][:8]

        try:
            cantidad = int(cantidad) if cantidad is not None else None
            if cantidad is not None and not (1 <= cantidad <= 99):
                cantidad = None
        except Exception:
            cantidad = None

        return {
            "accion": accion,
            "producto": producto,
            "categoria": categoria,
            "metodo_entrega": metodo_entrega,
            "cantidad": cantidad,
            "confirmacion_producto": confirmacion_producto,
            "confirmacion_pedido": confirmacion_pedido,
            "cancelacion": cancelacion,
            "requiere_aclaracion": requiere_aclaracion,
            "mensaje_aclaracion": mensaje_aclaracion,
            "texto_interpretado": texto_interpretado,
            "palabras_desconocidas": palabras_desconocidas
        }

    except Exception as e:
        log_debug("ERROR CLASIFICANDO MENSAJE AMBIGUO CON OPENAI:", str(e))
        return None


# =========================================================
# AGENTE PRINCIPAL DE CONVERSACIÃ“N
# =========================================================
AGENTE_CATEGORIAS_VALIDAS = {"BebÃ©s", "NiÃ±os", "NiÃ±as", "Peluches", "Juegos de mesa", "Coleccionables", None}
AGENTE_METODOS_ENTREGA_VALIDOS = {"Domicilio", "Expo", None}
AGENTE_FORMAS_PAGO_VALIDAS = {"Efectivo", "Pago en lÃ­nea", None}
AGENTE_ACCIONES_VALIDAS = {
    "saludo", "buscar_producto", "recomendacion_producto", "cotizacion", "compra",
    "agregar_producto", "confirmacion", "cancelacion", "entrega", "pago",
    "expos", "direccion", "referencia", "soporte_humano", "desconocida"
}

AGENTE_JSON_SCHEMA = {
    "name": "jugueteriabot_conversation_agent",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "accion": {"type": "string", "enum": sorted([a for a in AGENTE_ACCIONES_VALIDAS])},
            "intencion": {"type": "string", "enum": ["Consulta", "Cotizacion", "Compra", "Entrega", "Expos", "Soporte", "Desconocida"]},
            "producto": {"type": ["string", "null"]},
            "categoria": {"type": ["string", "null"], "enum": ["BebÃ©s", "NiÃ±os", "NiÃ±as", "Peluches", "Juegos de mesa", "Coleccionables", None]},
            "cantidad": {"type": ["integer", "null"], "minimum": 1, "maximum": 99},
            "edad": {"type": ["integer", "null"], "minimum": 0, "maximum": 99},
            "presupuesto": {"type": ["number", "null"], "minimum": 0},
            "metodo_entrega": {"type": ["string", "null"], "enum": ["Domicilio", "Expo", None]},
            "forma_pago": {"type": ["string", "null"], "enum": ["Efectivo", "Pago en lÃ­nea", None]},
            "requiere_envio": {"type": "boolean"},
            "confirmacion_producto": {"type": "boolean"},
            "confirmacion_pedido": {"type": "boolean"},
            "cancelacion": {"type": "boolean"},
            "parece_direccion": {"type": "boolean"},
            "parece_referencia": {"type": "boolean"},
            "quiere_humano": {"type": "boolean"},
            "requiere_aclaracion": {"type": "boolean"},
            "mensaje_aclaracion": {"type": ["string", "null"]},
            "texto_interpretado": {"type": ["string", "null"]},
            "siguiente_paso_sugerido": {"type": ["string", "null"]},
            "palabras_desconocidas": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "confianza": {"type": "number", "minimum": 0, "maximum": 1},
            "razon_corta": {"type": ["string", "null"]}
        },
        "required": [
            "accion", "intencion", "producto", "categoria", "cantidad", "edad", "presupuesto",
            "metodo_entrega", "forma_pago", "requiere_envio", "confirmacion_producto",
            "confirmacion_pedido", "cancelacion", "parece_direccion", "parece_referencia",
            "quiere_humano", "requiere_aclaracion", "mensaje_aclaracion", "texto_interpretado",
            "siguiente_paso_sugerido", "palabras_desconocidas", "confianza", "razon_corta"
        ]
    },
    "strict": True
}

def _json_para_agente(valor: Any) -> str:
    try:
        return json.dumps(valor, ensure_ascii=False, default=str)
    except Exception:
        return "{}"

def agente_principal_conversacion_openai(
    mensaje: str,
    analisis_reglas: Optional[dict] = None,
    contexto: Optional[Any] = None,
    memoria: Optional[Any] = None
) -> Optional[dict]:
    """
    Agente principal: interpreta lenguaje natural de WhatsApp y devuelve JSON estructurado.
    No ejecuta acciones ni confirma datos sensibles; solo alimenta al motor de flujo existente.
    """
    if not CONVERSATION_AGENT_ENABLED or not client_openai:
        return None
    texto = normalizar_texto(mensaje)
    if not texto:
        return None

    contexto_dict = {
        "ultima_intencion": getattr(contexto, "ultima_intencion", None) if contexto else None,
        "ultima_categoria": getattr(contexto, "ultima_categoria", None) if contexto else None,
        "ultimo_termino": getattr(contexto, "ultimo_termino", None) if contexto else None,
        "ultimo_producto": getattr(contexto, "ultimo_producto", None) if contexto else None,
    }
    memoria_dict = {
        "estado_proceso": getattr(memoria, "estado_proceso", None) if memoria else None,
        "id_juguete": getattr(memoria, "id_juguete", None) if memoria else None,
        "producto_interes": getattr(memoria, "producto_interes", None) if memoria else None,
        "categoria_interes": getattr(memoria, "categoria_interes", None) if memoria else None,
        "metodo_entrega": getattr(memoria, "metodo_entrega", None) if memoria else None,
        "direccion_entrega": getattr(memoria, "direccion_entrega", None) if memoria else None,
        "referencia_entrega": getattr(memoria, "referencia_entrega", None) if memoria else None,
        "cantidad": obtener_cantidad_desde_notas(getattr(memoria, "notas_cliente", None)) if memoria else None,
        "metodo_pago": obtener_metodo_pago_desde_notas(getattr(memoria, "notas_cliente", None)) if memoria else None,
    }

    prompt = f"""
Eres el agente principal de conversaciÃ³n de JugueterÃ­aBot para WhatsApp.
Tu trabajo es interpretar el mensaje del cliente y regresar JSON estructurado para que el motor de flujo del bot ejecute acciones seguras.

Reglas obligatorias:
- No inventes productos, precios, stock, pagos ni promesas de entrega.
- Si el cliente pide precio o disponibilidad, identifica intenciÃ³n y producto/categorÃ­a, pero el precio real lo darÃ¡ SQL Server.
- Si el cliente confirma pago, NO marques pago como confirmado; solo identifica forma_pago o intenciÃ³n de pago.
- Si el cliente pide domicilio, marca metodo_entrega="Domicilio" y requiere_envio=true.
- Si el cliente quiere expo/recolecciÃ³n/eventos, usa Expos o metodo_entrega="Expo" segÃºn el caso.
- Interpreta modismos mexicanos y errores de escritura: ocupo=necesito, jalo/arre=sÃ­/confirmo, mandamelo=a domicilio, recojer=recoger.
- Si estÃ¡ en un estado activo de compra, prioriza el dato que falta segÃºn memoria_operativa.
- Si el mensaje es ambiguo pero recuperable, llena texto_interpretado y confianza; si no, requiere_aclaracion=true.

Contexto por reglas locales:
{_json_para_agente(analisis_reglas)}

Contexto conversacional anterior:
{_json_para_agente(contexto_dict)}

Memoria operativa del pedido:
{_json_para_agente(memoria_dict)}

Mensaje del cliente:
{mensaje!r}
""".strip()

    try:
        completion = client_openai.chat.completions.create(
            model=CONVERSATION_AGENT_MODEL,
            messages=[
                {"role": "system", "content": "Responde Ãºnicamente con JSON vÃ¡lido que cumpla el esquema."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_schema", "json_schema": AGENTE_JSON_SCHEMA},
            temperature=0.1,
        )
        raw = completion.choices[0].message.content or "{}"
    except Exception as schema_error:
        log_debug("AGENTE PRINCIPAL: fallo JSON schema, usando fallback JSON simple:", str(schema_error))
        try:
            completion = client_openai.chat.completions.create(
                model=CONVERSATION_AGENT_MODEL,
                messages=[
                    {"role": "system", "content": "Responde Ãºnicamente con JSON vÃ¡lido. No agregues explicaciÃ³n."},
                    {"role": "user", "content": prompt + "\n\nDevuelve todos los campos del esquema solicitado."},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
            )
            raw = completion.choices[0].message.content or "{}"
        except Exception as e:
            log_debug("ERROR AGENTE PRINCIPAL OPENAI:", str(e))
            return None

    try:
        data = json.loads(limpiar_json_respuesta(raw))
    except Exception as e:
        log_debug("ERROR PARSEANDO JSON AGENTE PRINCIPAL:", str(e), raw[:500])
        return None

    accion = str(data.get("accion") or "desconocida").strip().lower()
    if accion not in AGENTE_ACCIONES_VALIDAS:
        accion = "desconocida"

    intencion = str(data.get("intencion") or "Desconocida").strip()
    if intencion not in {"Consulta", "Cotizacion", "Compra", "Entrega", "Expos", "Soporte", "Desconocida"}:
        intencion = "Desconocida"

    categoria = data.get("categoria")
    if categoria not in AGENTE_CATEGORIAS_VALIDAS:
        categoria = None

    metodo_entrega = data.get("metodo_entrega")
    if metodo_entrega not in AGENTE_METODOS_ENTREGA_VALIDOS:
        metodo_entrega = None

    forma_pago = data.get("forma_pago")
    if forma_pago not in AGENTE_FORMAS_PAGO_VALIDAS:
        forma_pago = None

    def _str_or_none(v):
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    def _int_or_none(v, minimo=1, maximo=99):
        try:
            if v is None:
                return None
            n = int(v)
            return n if minimo <= n <= maximo else None
        except Exception:
            return None

    def _float_conf(v):
        try:
            f = float(v)
            return max(0.0, min(1.0, f))
        except Exception:
            return 0.0

    palabras = data.get("palabras_desconocidas") or []
    if not isinstance(palabras, list):
        palabras = []

    return {
        "accion": accion,
        "intencion": intencion,
        "producto": _str_or_none(data.get("producto")),
        "categoria": categoria,
        "cantidad": _int_or_none(data.get("cantidad")),
        "edad": _int_or_none(data.get("edad"), 0, 99),
        "presupuesto": data.get("presupuesto") if isinstance(data.get("presupuesto"), (int, float)) else None,
        "metodo_entrega": metodo_entrega,
        "forma_pago": forma_pago,
        "requiere_envio": bool(data.get("requiere_envio", False)),
        "confirmacion_producto": bool(data.get("confirmacion_producto", False)),
        "confirmacion_pedido": bool(data.get("confirmacion_pedido", False)),
        "cancelacion": bool(data.get("cancelacion", False)),
        "parece_direccion": bool(data.get("parece_direccion", False)),
        "parece_referencia": bool(data.get("parece_referencia", False)),
        "quiere_humano": bool(data.get("quiere_humano", False)),
        "requiere_aclaracion": bool(data.get("requiere_aclaracion", False)),
        "mensaje_aclaracion": _str_or_none(data.get("mensaje_aclaracion")),
        "texto_interpretado": _str_or_none(data.get("texto_interpretado")),
        "siguiente_paso_sugerido": _str_or_none(data.get("siguiente_paso_sugerido")),
        "palabras_desconocidas": [str(x).strip() for x in palabras if str(x).strip()][:8],
        "confianza": _float_conf(data.get("confianza")),
        "razon_corta": _str_or_none(data.get("razon_corta")),
    }

def aplicar_agente_a_analisis(analisis: dict, entidades: dict, salida_agente: dict) -> None:
    """Fusiona el JSON del agente con el anÃ¡lisis local sin sobreescribir datos seguros ya detectados."""
    if not salida_agente:
        return
    if salida_agente.get("confianza", 0) < CONVERSATION_AGENT_MIN_CONFIDENCE:
        return

    if salida_agente.get("confirmacion_producto"):
        entidades["confirmacion_producto"] = True
    if salida_agente.get("confirmacion_pedido"):
        entidades["confirmacion_pedido"] = True
    if salida_agente.get("cancelacion"):
        entidades["cancelacion"] = True
    if salida_agente.get("parece_direccion"):
        entidades["parece_direccion"] = True
    if salida_agente.get("parece_referencia"):
        entidades["parece_referencia"] = True

    if salida_agente.get("producto") and not entidades.get("producto"):
        entidades["producto"] = limpiar_termino_producto(salida_agente["producto"])
        if not analisis.get("termino_busqueda"):
            analisis["termino_busqueda"] = entidades["producto"]

    if salida_agente.get("categoria") and not entidades.get("categoria"):
        entidades["categoria"] = salida_agente["categoria"]
        analisis["categoria"] = salida_agente["categoria"]

    if salida_agente.get("cantidad") and not entidades.get("cantidad"):
        entidades["cantidad"] = salida_agente["cantidad"]

    if salida_agente.get("metodo_entrega") and not entidades.get("metodo_entrega"):
        entidades["metodo_entrega"] = salida_agente["metodo_entrega"]

    if salida_agente.get("forma_pago") and not entidades.get("forma_pago"):
        entidades["forma_pago"] = salida_agente["forma_pago"]

    intencion = salida_agente.get("intencion")
    if intencion in {"Compra", "Cotizacion", "Entrega", "Expos"}:
        analisis["intencion"] = intencion
    elif salida_agente.get("accion") in {"compra", "agregar_producto"} and analisis.get("intencion") == "Consulta":
        analisis["intencion"] = "Compra"

# Tools internas controladas por el backend. El agente no ejecuta SQL directamente; solo el motor de flujo llama estas funciones.
def tool_buscar_productos_sql(termino: Optional[str] = None, categoria: Optional[str] = None, limite: int = 5) -> List[dict]:
    productos = buscar_por_categoria(categoria) if categoria else buscar_juguete_por_texto(termino or "")
    salida = []
    for p in productos[:limite]:
        salida.append({
            "id_juguete": int(p.id_juguete),
            "nombre": str(p.nombre),
            "categoria": str(getattr(p, "categoria", categoria or "")),
            "precio": float(p.precio),
            "stock": int(p.stock or 0),
            "descripcion": str(getattr(p, "descripcion", "") or "")
        })
    return salida

def tool_consultar_stock_sql(id_juguete: int) -> dict:
    juguete = obtener_juguete_resumen_por_id(int(id_juguete))
    if not juguete:
        return {"ok": False, "mensaje": "Producto no encontrado"}
    return {
        "ok": True,
        "id_juguete": int(juguete.id_juguete),
        "nombre": str(juguete.nombre),
        "stock": int(juguete.stock or 0),
        "precio": float(juguete.precio),
    }

def tool_consultar_expos_sql() -> List[dict]:
    return [
        {"nombre": str(e.nombre), "ubicacion": str(e.ubicacion), "fecha_inicio": str(e.fecha_inicio), "fecha_fin": str(e.fecha_fin)}
        for e in obtener_expos()
    ]

def mensaje_es_ambiguo_para_openai(analisis: dict, entidades: dict, memoria=None) -> bool:
    """
    Decide cuÃ¡ndo vale la pena consultar OpenAI.
    No se usa en mensajes simples o ya resueltos por reglas.
    """
    texto = analisis.get("texto_normalizado", "")

    if not texto:
        return False

    if analisis.get("es_saludo") or analisis.get("es_despedida"):
        return False

    if memoria and getattr(memoria, "estado_proceso", None) in {
        "EsperandoDireccion", "EsperandoReferencia", "EsperandoMetodoPago", "CompraListaParaConfirmacion"
    }:
        return False

    if entidades["producto"] and entidades["metodo_entrega"]:
        return False

    if entidades["categoria"]:
        return False

    if analisis.get("intencion") in {"Expos", "Entrega"}:
        return False

    ambiguos_tipicos = {
        "si", "sÃ­", "ese", "esa", "ese mismo", "esa misma",
        "lo quiero", "me interesa", "apartamelo", "apÃ¡rtamelo",
        "quiero ese", "quiero esa", "para maÃ±ana", "mandamelo",
        "mÃ¡ndamelo", "lo recojo", "me lo llevo"
    }

    if texto in ambiguos_tipicos:
        return True

    if entidades["accion"] == "consulta" and analisis.get("termino_busqueda") and len(analisis.get("termino_busqueda", "")) <= 4:
        return True

    palabras = texto.split()
    if entidades["accion"] == "consulta" and analisis.get("termino_busqueda") and any(len(p) <= 2 for p in palabras):
        return True

    if entidades["accion"] == "consulta" and not entidades["producto"] and not entidades["categoria"]:
        return True

    return False
def analizar_mensaje(mensaje: str) -> dict:
    texto = normalizar_texto(mensaje)
    intencion = detectar_intencion(mensaje)
    categoria = detectar_categoria(mensaje)
    termino_busqueda = extraer_termino_busqueda(mensaje)
    entidades = extraer_entidades_mensaje(mensaje)

    palabras_genericas = {
        "hola", "holi", "buenas", "gracias", "adios", "bye", "ok", "sale",
        "quiero", "comprar", "precio", "cotizacion", "cuanto", "cuesta",
        "envio", "entrega", "expo", "evento", "informacion", "info"
    }

    palabras = [p for p in texto.split() if p]
    palabras_utiles = [p for p in palabras if p not in palabras_genericas]

    requiere_catalogo = False
    requiere_humano = False

    if categoria:
        requiere_catalogo = True
    elif (
        not es_saludo(mensaje)
        and not es_despedida(mensaje)
        and intencion in ("Cotizacion", "Compra", "Consulta")
        and termino_busqueda
    ):
        requiere_catalogo = True

    if (
        intencion == "Consulta"
        and not categoria
        and len(palabras_utiles) == 0
        and not es_saludo(mensaje)
        and not es_despedida(mensaje)
    ):
        requiere_humano = True

    return {
        "texto_normalizado": texto,
        "intencion": intencion,
        "categoria": categoria,
        "termino_busqueda": termino_busqueda,
        "es_saludo": es_saludo(mensaje),
        "es_despedida": es_despedida(mensaje),
        "requiere_catalogo": requiere_catalogo,
        "requiere_humano": requiere_humano,
        "entidades": entidades
    }

def buscar_juguete_para_pedido(
    producto_interes: Optional[str] = None,
    categoria_interes: Optional[str] = None
):
    conn = get_connection()
    try:
        cursor = conn.cursor()

        if producto_interes:
            termino = normalizar_texto(producto_interes)
            termino = limpiar_termino_producto(termino)
            termino = corregir_termino_aproximado(termino)
            patron = f"%{termino}%"

            log_debug("BUSCANDO PRODUCTO PARA PEDIDO:", {
                "producto_interes_original": producto_interes,
                "termino_normalizado": termino,
                "categoria_interes": categoria_interes
            })

            cursor.execute("""
                SELECT TOP 1
                    j.id_juguete,
                    j.nombre,
                    j.descripcion,
                    j.precio,
                    ISNULL(j.precio_compra, 0) AS precio_compra,
                    j.stock,
                    j.foto_url,
                    j.foto_local,
                    c.nombre AS categoria
                FROM Juguete j
                INNER JOIN Categoria c
                    ON j.id_categoria = c.id_categoria
                LEFT JOIN JugueteEtiqueta e
                    ON j.id_juguete = e.id_juguete
                WHERE
                    LOWER(j.nombre) LIKE ?
                    OR LOWER(j.descripcion) LIKE ?
                    OR LOWER(e.etiqueta) LIKE ?
                GROUP BY
                    j.id_juguete,
                    j.nombre,
                    j.descripcion,
                    j.precio,
                    j.precio_compra,
                    j.stock,
                    j.foto_url,
                    j.foto_local,
                    c.nombre
                ORDER BY
                    MAX(CASE WHEN LOWER(j.nombre) = ? THEN 0 ELSE 1 END),
                    j.stock DESC,
                    j.nombre
            """, patron, patron, patron, termino)

            fila = cursor.fetchone()
            if fila:
                log_debug("PRODUCTO ENCONTRADO PARA PEDIDO:", fila.nombre)
                return fila

        if categoria_interes:
            log_debug("BUSCANDO POR CATEGORIA PARA PEDIDO:", categoria_interes)

            cursor.execute("""
                SELECT TOP 1
                    j.id_juguete,
                    j.nombre,
                    j.descripcion,
                    j.precio,
                    ISNULL(j.precio_compra, 0) AS precio_compra,
                    j.stock,
                    j.foto_url,
                    j.foto_local,
                    c.nombre AS categoria
                FROM Juguete j
                INNER JOIN Categoria c
                    ON j.id_categoria = c.id_categoria
                WHERE c.nombre = ?
                ORDER BY j.stock DESC, j.nombre
            """, categoria_interes)

            fila = cursor.fetchone()
            if fila:
                log_debug("PRODUCTO ENCONTRADO POR CATEGORIA:", fila.nombre)
                return fila

        log_debug("NO SE ENCONTRO PRODUCTO PARA PEDIDO", {
            "producto_interes": producto_interes,
            "categoria_interes": categoria_interes
        })
        return None
    finally:
        conn.close()
 
def obtener_juguete_resumen_por_id(id_juguete: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                j.id_juguete,
                j.nombre,
                j.descripcion,
                j.precio,
                ISNULL(j.precio_compra, 0) AS precio_compra,
                j.stock,
                j.foto_url,
                j.foto_local,
                c.nombre AS categoria
            FROM Juguete j
            INNER JOIN Categoria c
                ON j.id_categoria = c.id_categoria
            WHERE j.id_juguete = ?
        """, id_juguete)
        return cursor.fetchone()
    finally:
        conn.close()        

def construir_respuesta_expos() -> dict:
    expos = obtener_expos()

    if not expos:
        return {
            "intencion": "Expos",
            "respuesta": "Por el momento no tenemos expos registradas ðŸ˜Š"
        }

    lineas = ["ðŸŽª Estas son nuestras prÃ³ximas expos:"]
    for expo in expos:
        lineas.append(
            f"â€¢ {expo.nombre} en {expo.ubicacion} del {expo.fecha_inicio} al {expo.fecha_fin}"
        )

    return {
        "intencion": "Expos",
        "respuesta": "\n".join(lineas)
    }

def obtener_expos_texto_saludo(limite: int = 2) -> str:
    try:
        expos = obtener_expos()
    except Exception:
        expos = []

    if not expos:
        return ""

    lineas = ["ðŸŽª PrÃ³ximas expos disponibles:"]
    for expo in expos[:limite]:
        lineas.append(f"â€¢ {expo.nombre} en {expo.ubicacion} del {expo.fecha_inicio} al {expo.fecha_fin}")
    lineas.append("Si quieres detalles, escribe: Â¿QuÃ© expos tienen?")
    return "\n".join(lineas)


def construir_respuesta_entrega() -> dict:
    return {
        "intencion": "Entrega",
        "respuesta": (
            "ðŸšš Manejamos entregas dentro de la localidad y tambiÃ©n recolecciÃ³n en expo.\n\n"
            "Para continuar, responde solo una de estas opciones:\n"
            "â€¢ a domicilio\n"
            "â€¢ recoger en expo"
        )
    }

def construir_respuesta_categoria(categoria: str, intencion: str) -> dict:
    productos = buscar_por_categoria(categoria)

    if not productos:
        return {
            "intencion": intencion,
            "respuesta": mensaje_no_encontrado_con_categorias()
        }

    encabezado = f"Estos son algunos productos en la categorÃ­a {categoria}:"
    if intencion == "Cotizacion":
        encabezado = f"Te comparto algunos productos y precios de la categorÃ­a {categoria}:"
    elif intencion == "Compra":
        encabezado = f"Estos son algunos productos disponibles de la categorÃ­a {categoria}:"

    lineas = [encabezado]
    for p in productos[:5]:
        lineas.append(f"- {p.nombre}: ${p.precio:.2f} | stock: {p.stock}")

    return {
        "intencion": intencion,
        "respuesta": "\n".join(lineas)
    }

def construir_respuesta_busqueda(termino: str, intencion: str) -> dict:
    resultados = buscar_juguete_por_texto(termino)

    if not resultados:
        return {
            "intencion": intencion,
            "respuesta": (
                mensaje_no_encontrado_con_categorias()
            )
        }

    if intencion == "Cotizacion":
        encabezado = "EncontrÃ© estos productos con su precio:"
    elif intencion == "Compra":
        encabezado = "EncontrÃ© estos productos disponibles:"
    else:
        encabezado = "EncontrÃ© estos productos:"

    lineas = [encabezado]
    for r in resultados:
        lineas.append(
            f"- {r.nombre}: ${r.precio:.2f}, categorÃ­a {r.categoria}, stock {r.stock}. {r.descripcion}"
        )

    return {
        "intencion": intencion,
        "respuesta": "\n".join(lineas)
    }

def construir_resumen_pedido_desde_memoria(memoria) -> str:
    carrito = obtener_carrito_memoria(memoria)
    if not carrito:
        producto_memoria = getattr(memoria, "producto_interes", None) or "No identificado"
        categoria_memoria = getattr(memoria, "categoria_interes", None) or "No identificada"
        return ("No pude preparar el resumen automÃ¡tico porque no encontrÃ© una coincidencia exacta en el catÃ¡logo ðŸ˜•\n\n" f"Referencia guardada:\n" f"â€¢ Producto: {producto_memoria}\n" f"â€¢ CategorÃ­a: {categoria_memoria}\n\n" + mensaje_no_encontrado_con_categorias())
    lineas = ["ðŸ§¾ Resumen de tu pedido", ""]
    total = 0.0
    errores_stock = []
    for idx, item in enumerate(carrito, start=1):
        juguete = obtener_juguete_resumen_por_id(int(item["id_juguete"]))
        if not juguete:
            errores_stock.append(f"El producto #{item.get('id_juguete')} ya no existe en catÃ¡logo.")
            continue
        cantidad = int(item.get("cantidad", 1))
        stock = int(juguete.stock or 0)
        precio_unitario = float(juguete.precio)
        subtotal = round(precio_unitario * cantidad, 2)
        total += subtotal
        lineas.append(f"{idx}. ðŸŽ {juguete.nombre}")
        lineas.append(f"   ðŸ”¢ Cantidad: {cantidad}")
        lineas.append(f"   ðŸ’²Unitario: ${precio_unitario:.2f}")
        lineas.append(f"   Subtotal: ${subtotal:.2f}")
        if cantidad > stock:
            errores_stock.append(f"Solo hay {stock} pieza(s) disponibles de {juguete.nombre}.")
    metodo_pago = obtener_metodo_pago_desde_notas(getattr(memoria, "notas_cliente", None)) or "No definido"
    envio = ENVIO_DOMICILIO if getattr(memoria, "metodo_entrega", None) == "Domicilio" else 0.0
    total_final = round(total + envio, 2)
    lineas.extend(["", f"ðŸšš MÃ©todo de entrega: {getattr(memoria, 'metodo_entrega', None) or 'No definido'}"])
    if getattr(memoria, "metodo_entrega", None) == "Domicilio":
        lineas.append(f"ðŸ“ DirecciÃ³n: {getattr(memoria, 'direccion_entrega', None) or 'No capturada'}")
        lineas.append(f"ðŸ“ Referencia: {getattr(memoria, 'referencia_entrega', None) or 'No capturada'}")
        lineas.append(f"ðŸ“¦ EnvÃ­o a domicilio: ${envio:.2f}")
    elif getattr(memoria, "metodo_entrega", None) == "Expo":
        lineas.append("ðŸ“ Entrega: recoger en expo")
    lineas.append(f"ðŸ’³ MÃ©todo de pago: {metodo_pago}")
    lineas.extend(["", f"ðŸ’° Subtotal productos: ${total:.2f}", f"ðŸ’° Total estimado: ${total_final:.2f}", ""])
    if errores_stock:
        lineas.append("Antes de confirmar necesito corregir stock:")
        lineas.extend(f"â€¢ {e}" for e in errores_stock)
        lineas.append("Puedes cambiar cantidad o eliminar producto antes de confirmar.")
    else:
        lineas.append("Si todo estÃ¡ correcto, responde: confirmar pedido")
        lineas.append("TambiÃ©n puedes responder: cancelar pedido")
    return "\n".join(lineas)

def notificar_nuevo_pedido_whatsapp(id_pedido: int, id_cliente: int, total: float, producto: str, metodo_entrega: Optional[str]) -> None:
    """EnvÃ­a aviso interno por WhatsApp cuando se registra un pedido. No bloquea el flujo si Meta falla."""
    if not NOTIFY_ORDER_PHONE:
        log_debug("NOTIFY_ORDER_PHONE no configurado; aviso interno omitido")
        return

    try:
        cliente = obtener_cliente_por_id(id_cliente)
        cliente_nombre = getattr(cliente, "nombre", "Cliente") if cliente else "Cliente"
        telefono_cliente = getattr(cliente, "telefono", "Sin telÃ©fono") if cliente else "Sin telÃ©fono"
        texto = (
            "ðŸ”” Nuevo pedido registrado\n\n"
            f"Folio: #{id_pedido}\n"
            f"Cliente: {cliente_nombre}\n"
            f"TelÃ©fono: {telefono_cliente}\n"
            f"Producto: {producto}\n"
            f"MÃ©todo: {metodo_entrega or 'No definido'}\n"
            f"Total: ${total:.2f}\n\n"
            "Revisar en el panel: /panel/pedidos"
        )
        resp = enviar_mensaje_whatsapp(normalizar_numero_whatsapp(NOTIFY_ORDER_PHONE), texto)
        if resp.status_code >= 300:
            log_debug("AVISO PEDIDO WHATSAPP FALLÃ“. Pendiente alternativa Telegram.", resp.status_code, resp.text)
    except Exception as e:
        log_debug("ERROR EN AVISO INTERNO DE PEDIDO. Pendiente alternativa Telegram:", str(e))

def crear_pedido_desde_memoria(id_cliente: int):
    memoria = obtener_memoria_cliente(id_cliente)
    if not memoria:
        return False, "No existe una memoria activa de compra para este cliente.", None
    if memoria.estado_proceso == "PedidoConfirmado":
        return False, "Ese pedido ya fue confirmado anteriormente.", None
    if memoria.estado_proceso != "CompraListaParaConfirmacion":
        return False, "La compra aÃºn no estÃ¡ lista para confirmaciÃ³n.", None
    if not tiene_confirmacion_final_en_notas(getattr(memoria, "notas_cliente", None)):
        return False, "Falta la confirmaciÃ³n final del cliente. Debe responder: confirmar pedido.", None
    carrito = obtener_carrito_memoria(memoria)
    if not carrito:
        return False, "El carrito estÃ¡ vacÃ­o o no tiene productos vÃ¡lidos.", None
    detalles = []
    total = 0.0
    for item in carrito:
        juguete = obtener_juguete_resumen_por_id(int(item["id_juguete"]))
        if not juguete:
            return False, f"No se encontrÃ³ el producto #{item.get('id_juguete')} en el catÃ¡logo.", None
        cantidad = int(item.get("cantidad", 1))
        stock_disponible = int(juguete.stock or 0)
        if stock_disponible <= 0:
            return False, f"El producto {juguete.nombre} no tiene stock disponible en este momento.", None
        if cantidad > stock_disponible:
            return False, f"Solo hay {stock_disponible} pieza(s) disponibles de {juguete.nombre}.", None
        precio_unitario = float(juguete.precio)
        costo_unitario = float(getattr(juguete, "precio_compra", 0) or 0)
        subtotal = round(precio_unitario * cantidad, 2)
        total += subtotal
        detalles.append((int(juguete.id_juguete), cantidad, precio_unitario, costo_unitario, subtotal, str(juguete.nombre)))
    metodo_pago = obtener_metodo_pago_desde_notas(getattr(memoria, "notas_cliente", None)) or "Efectivo"
    envio = ENVIO_DOMICILIO if getattr(memoria, "metodo_entrega", None) == "Domicilio" else 0.0
    total_final = round(total + envio, 2)
    observaciones = memoria.notas_cliente
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Pedido (id_cliente, estado, metodo_entrega, direccion_entrega, referencia_entrega, subtotal, total, observaciones, costo_envio, metodo_pago, estado_pago)
            OUTPUT INSERTED.id_pedido
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, id_cliente, "Pendiente", memoria.metodo_entrega, memoria.direccion_entrega, memoria.referencia_entrega, round(total, 2), total_final, observaciones, envio, metodo_pago, "pendiente_online" if metodo_pago == "Pago en lÃ­nea" else "efectivo_pendiente")
        id_pedido = cursor.fetchone()[0]
        for id_juguete, cantidad, precio_unitario, costo_unitario, subtotal, _nombre in detalles:
            cursor.execute("""
                INSERT INTO DetallePedido (id_pedido, id_juguete, cantidad, precio_unitario, costo_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, id_pedido, id_juguete, cantidad, precio_unitario, costo_unitario, subtotal)
        cursor.execute("""
            UPDATE MemoriaCliente SET estado_proceso = ?, notas_cliente = ?, fecha_actualizacion = GETDATE() WHERE id_cliente = ?
        """, "PedidoConfirmado", f"Pedido #{id_pedido} confirmado automÃ¡ticamente", id_cliente)
        conn.commit()
        producto_resumen = ", ".join(f"{n} x{c}" for _id, c, _p, _cu, _s, n in detalles)
        notificar_nuevo_pedido_whatsapp(id_pedido=id_pedido, id_cliente=id_cliente, total=total_final, producto=producto_resumen, metodo_entrega=memoria.metodo_entrega)
        mensaje = f"Pedido guardado correctamente con folio #{id_pedido}."
        if metodo_pago == "Pago en lÃ­nea":
            if MERCADOPAGO_ACCESS_TOKEN:
                try:
                    pref = crear_preferencia_mercadopago(id_pedido)
                    link_pago = pref.get("init_point") or pref.get("sandbox_init_point")
                    if link_pago:
                        mensaje += f"\n\nðŸ’³ Paga en lÃ­nea con Mercado Pago aquÃ­:\n{link_pago}"
                except Exception as mp_error:
                    error_logger.exception("No se pudo crear link de Mercado Pago")
                    mensaje += "\n\nNo pude generar el link de pago automÃ¡tico. Un asesor puede enviarlo desde el panel."
            else:
                if PAYMENT_LINK_FALLBACK:
                    mensaje += f"\n\nðŸ’³ Paga en lÃ­nea aquÃ­:\n{PAYMENT_LINK_FALLBACK}"
                else:
                    mensaje += "\n\nElegiste pago en lÃ­nea, pero falta configurar MERCADOPAGO_ACCESS_TOKEN o PAYMENT_LINK_FALLBACK. Un asesor te enviarÃ¡ el link."
        else:
            mensaje += "\n\nMÃ©todo de pago: efectivo. Paga al recibir tu pedido."
        return True, mensaje, id_pedido
    except Exception as e:
        conn.rollback()
        error_logger.exception("Error al crear pedido desde memoria")
        return False, f"Error al guardar el pedido: {str(e)}", None
    finally:
        conn.close()
        

def construir_respuesta_saludo_publico() -> str:
    bloque_expos = obtener_expos_texto_saludo()
    respuesta_saludo = (
        "Â¡Hola! ðŸ˜Š Bienvenido a Robles Outlet.\n"
        "Te ayudo a encontrar juguetes, precios, compras, entregas y expos.\n\n"
        "CategorÃ­as disponibles:\n"
        f"{obtener_categorias_texto_publico()}\n\n"
    )
    if bloque_expos:
        respuesta_saludo += f"{bloque_expos}\n\n"
    else:
        respuesta_saludo += "ðŸŽª TambiÃ©n puedes preguntarme por nuestras prÃ³ximas expos.\n\n"
    respuesta_saludo += (
        "Puedes escribirme algo como:\n"
        "â€¢ Quiero 2 peluches a domicilio\n"
        "â€¢ Busco juguetes para niÃ±o\n"
        "â€¢ Â¿QuÃ© expos tienen?\n"
        "â€¢ Quiero recoger en expo\n"
        "â€¢ TambiÃ©n puedes pedir: imagen de Stitch."
    )
    return respuesta_saludo

def flujo_pago_directo_desde_memoria(id_cliente: int, memoria, mensaje: str) -> Optional[dict]:
    """Procesa efectivo/pago en lÃ­nea de forma determinista.
    Sirve aunque el estado se haya quedado desfasado, siempre que exista carrito.
    """
    if not memoria:
        return None
    # Solo se acepta pago directo cuando el flujo estÃ¡ exactamente esperando pago.
    # Si se permite en cualquier estado con carrito, "efectivo" puede cerrar o
    # desfasar el pedido sin confirmaciÃ³n final.
    if getattr(memoria, "estado_proceso", None) != "EsperandoMetodoPago":
        return None
    metodo_seleccionado = None
    if es_pago_online(mensaje):
        metodo_seleccionado = "Pago en lÃ­nea"
    elif es_pago_efectivo(mensaje):
        metodo_seleccionado = "Efectivo"
    if not metodo_seleccionado:
        return None
    carrito = obtener_carrito_memoria(memoria)
    if not carrito:
        return None
    if not getattr(memoria, "metodo_entrega", None):
        return None
    if getattr(memoria, "metodo_entrega", None) == "Domicilio" and (not getattr(memoria, "direccion_entrega", None) or not getattr(memoria, "referencia_entrega", None)):
        return None
    notas_pago = guardar_metodo_pago_en_notas(getattr(memoria, "notas_cliente", None), metodo_seleccionado)
    guardar_o_actualizar_memoria_cliente(
        id_cliente=id_cliente,
        estado_proceso="CompraListaParaConfirmacion",
        id_juguete=getattr(memoria, "id_juguete", None),
        producto_interes=getattr(memoria, "producto_interes", None),
        categoria_interes=getattr(memoria, "categoria_interes", None),
        metodo_entrega=getattr(memoria, "metodo_entrega", None),
        direccion_entrega=getattr(memoria, "direccion_entrega", None),
        referencia_entrega=getattr(memoria, "referencia_entrega", None),
        notas_cliente=notas_pago
    )
    memoria = obtener_memoria_cliente(id_cliente)
    return {
        "intencion": "Compra",
        "respuesta": respuesta_resumen_confirmacion_final(memoria, metodo_seleccionado)
    }

def es_url_absoluta_valida(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(str(url).strip())
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False

def responder_mensaje(mensaje: str, id_cliente: Optional[int] = None) -> dict:
    # Normaliza el texto entrante del cliente a minÃºsculas, sin acentos ni signos raros.
    # Esto evita que el motor de flujo trate distinto "Arizona", "ARIZONA" o "arizona".
    mensaje_original = mensaje or ""
    mensaje = normalizar_texto(mensaje_original)

    analisis = analizar_mensaje(mensaje)
    entidades = analisis["entidades"]

    log_debug("ANALISIS MENSAJE:", analisis)

    memoria = obtener_memoria_cliente(id_cliente) if id_cliente else None
    contexto = obtener_contexto_cliente(id_cliente) if id_cliente else None

    estados_activos = {
        "CompraPendiente", "EsperandoConfirmacionProducto", "EsperandoCantidad",
        "EsperandoMasProductos", "EsperandoEntrega", "EsperandoDireccion",
        "EsperandoReferencia", "EsperandoMetodoPago", "CompraListaParaConfirmacion"
    }

    # Si el cliente saluda y la memoria quedÃ³ en un estado cerrado/atascado, se limpia
    # para evitar que "Hola" se busque como producto.
    if id_cliente and memoria and getattr(memoria, "estado_proceso", None) in {"PedidoConfirmado", "CompraCancelada"} and analisis.get("es_saludo"):
        limpiar_memoria_cliente(id_cliente)
        memoria = None

    if analisis.get("es_saludo") and not analisis.get("requiere_catalogo") and (not memoria or getattr(memoria, "estado_proceso", None) not in estados_activos):
        return {"intencion": "Consulta", "respuesta": construir_respuesta_saludo_publico()}

    # Prioridad absoluta para mÃ©todo de pago: evita que "efectivo" o
    # "pago en lÃ­nea" caigan al buscador de productos si el estado se desfasÃ³.
    if id_cliente and memoria:
        pago_directo = flujo_pago_directo_desde_memoria(id_cliente, memoria, mensaje)
        if pago_directo:
            return pago_directo

        # Interceptores deterministas antes de OpenAI.
        # Evitan que frases de control se conviertan en producto o que pago cree pedido sin resumen.
        if memoria.estado_proceso == "EsperandoMasProductos" and es_no_agregar_otro(mensaje):
            guardar_o_actualizar_memoria_cliente(
                id_cliente=id_cliente,
                estado_proceso="EsperandoEntrega",
                id_juguete=getattr(memoria, "id_juguete", None),
                producto_interes=memoria.producto_interes,
                categoria_interes=memoria.categoria_interes,
                metodo_entrega=None,
                direccion_entrega=None,
                referencia_entrega=None,
                notas_cliente=memoria.notas_cliente
            )
            return {
                "intencion": "Compra",
                "respuesta": (
                    "Perfecto, cerramos el carrito âœ…\n\n"
                    f"{texto_carrito_corto(memoria)}\n\n"
                    "Ahora dime cÃ³mo quieres recibir tu pedido:\n"
                    f"â€¢ a domicilio (envÃ­o ${ENVIO_DOMICILIO:.2f})\n"
                    "â€¢ recoger en expo"
                )
            }

        if memoria.estado_proceso == "EsperandoMetodoPago" and (es_pago_online(mensaje) or es_pago_efectivo(mensaje)):
            metodo_seleccionado = "Pago en lÃ­nea" if es_pago_online(mensaje) else "Efectivo"
            notas_pago = guardar_metodo_pago_en_notas(memoria.notas_cliente, metodo_seleccionado)
            guardar_o_actualizar_memoria_cliente(
                id_cliente=id_cliente,
                estado_proceso="CompraListaParaConfirmacion",
                id_juguete=getattr(memoria, "id_juguete", None),
                producto_interes=memoria.producto_interes,
                categoria_interes=memoria.categoria_interes,
                metodo_entrega=memoria.metodo_entrega,
                direccion_entrega=memoria.direccion_entrega,
                referencia_entrega=memoria.referencia_entrega,
                notas_cliente=notas_pago
            )
            memoria = obtener_memoria_cliente(id_cliente)
            return {
                "intencion": "Compra",
                "respuesta": respuesta_resumen_confirmacion_final(memoria, metodo_seleccionado)
            }

        if memoria.estado_proceso == "CompraListaParaConfirmacion":
            if es_cancelacion_pedido(mensaje):
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraCancelada",
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente="Compra cancelada por el cliente antes de confirmar"
                )
                return {"intencion": "Compra", "respuesta": "Entendido ðŸ˜Š CancelÃ© el pedido antes de registrarlo."}
            if es_confirmacion_pedido(mensaje):
                notas_confirmadas = guardar_confirmacion_final_en_notas(memoria.notas_cliente)
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraListaParaConfirmacion",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=notas_confirmadas
                )
                ok, detalle, id_pedido = crear_pedido_desde_memoria(id_cliente)
                if ok:
                    return {
                        "intencion": "Compra",
                        "respuesta": (
                            f"Â¡Listo! ðŸŽ‰ Tu pedido quedÃ³ registrado correctamente.\n"
                            f"Folio: #{id_pedido}\n\n"
                            f"{detalle.replace('Pedido guardado correctamente con folio #' + str(id_pedido) + '.', '').strip()}\n\n"
                            "En breve daremos seguimiento a tu entrega."
                        )
                    }
                return {"intencion": "Compra", "respuesta": f"No pude confirmar tu pedido en este momento ðŸ˜•\nDetalle: {detalle}"}
    
    if es_peticion_imagen_producto(mensaje):
        producto_img = buscar_producto_para_imagen(mensaje, memoria=memoria)
        if producto_img:
            if id_cliente:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoConfirmacionProducto",
                    id_juguete=producto_img.id_juguete,
                    producto_interes=producto_img.nombre,
                    categoria_interes=getattr(producto_img, "categoria", None),
                    metodo_entrega=getattr(memoria, "metodo_entrega", None) if memoria else None,
                    direccion_entrega=getattr(memoria, "direccion_entrega", None) if memoria else None,
                    referencia_entrega=getattr(memoria, "referencia_entrega", None) if memoria else None,
                    notas_cliente=getattr(memoria, "notas_cliente", None) if memoria else "Producto consultado por imagen"
                )
            return respuesta_producto_con_imagen(producto_img)
        return {"intencion": "Consulta", "respuesta": "Claro ðŸ˜Š Â¿De quÃ© producto quieres ver imÃ¡genes? Escribe por ejemplo: imagen de Stitch."}

    if entidades["cancelacion"] and not memoria:
        return {
            "intencion": "Consulta",
            "respuesta": (
                "No hay un pedido activo para cancelar en este momento ðŸ˜Š\n"
                "Si quieres comprar algo, envÃ­ame el nombre del juguete o la categorÃ­a."
            )
        }

    # Respuestas deterministas dentro del flujo de carrito.
    # Evita que OpenAI o el fuzzy matching conviertan frases como
    # "muÃ©strame productos" o "peluches" en un producto especÃ­fico.
    if memoria and memoria.estado_proceso in {"EsperandoMasProductos", "EsperandoConfirmacionProducto", "CompraPendiente"}:
        if es_peticion_mostrar_productos(mensaje):
            return {"intencion": "Consulta", "respuesta": obtener_productos_destacados_texto()}
        categoria_directa = detectar_categoria(mensaje)
        if categoria_directa:
            return {"intencion": "Consulta", "respuesta": respuesta_categoria_para_seleccion(categoria_directa)}

    # =====================================================
    # AGENTE PRINCIPAL CON OPENAI + JSON ESTRUCTURADO
    # =====================================================
    # El agente interpreta el mensaje completo, pero el motor de flujo conserva
    # la autoridad sobre stock, pagos, pedidos y estados.
    salida_agente = None
    if CONVERSATION_AGENT_ENABLED and not (analisis.get("es_saludo") and not memoria):
        salida_agente = agente_principal_conversacion_openai(
            mensaje=mensaje,
            analisis_reglas=analisis,
            contexto=contexto,
            memoria=memoria
        )
        if salida_agente:
            log_debug("AGENTE PRINCIPAL:", salida_agente)
            guardar_log_clasificacion_ai(
                id_cliente=id_cliente,
                mensaje_original=mensaje,
                analisis_reglas=analisis,
                clasificacion_ai=salida_agente,
                respuesta_final=None,
                fuente_clasificacion="AgentePrincipalOpenAI"
            )
            if salida_agente.get("requiere_aclaracion") and salida_agente.get("mensaje_aclaracion") and not memoria:
                return {"intencion": "Consulta", "respuesta": salida_agente["mensaje_aclaracion"]}
            aplicar_agente_a_analisis(analisis, entidades, salida_agente)

    # =====================================================
    # CLASIFICACIÃ“N AMBIGUA CON OPENAI
    # =====================================================
    if mensaje_es_ambiguo_para_openai(analisis, entidades, memoria=memoria):
        clasificacion_ai = clasificar_mensaje_ambiguo_con_openai(
            mensaje=mensaje,
            contexto=contexto,
            memoria=memoria
        )

        if clasificacion_ai:
            log_debug("CLASIFICACION AI:", clasificacion_ai)

            guardar_log_clasificacion_ai(
                id_cliente=id_cliente,
                mensaje_original=mensaje,
                analisis_reglas=analisis,
                clasificacion_ai=clasificacion_ai,
                respuesta_final=None,
                fuente_clasificacion="OpenAI"
            )

            if clasificacion_ai["requiere_aclaracion"] and clasificacion_ai["mensaje_aclaracion"]:
                return {
                    "intencion": "Consulta",
                    "respuesta": clasificacion_ai["mensaje_aclaracion"]
                }

            if clasificacion_ai["confirmacion_producto"]:
                entidades["confirmacion_producto"] = True

            if clasificacion_ai["confirmacion_pedido"]:
                entidades["confirmacion_pedido"] = True

            if clasificacion_ai["cancelacion"]:
                entidades["cancelacion"] = True

            if clasificacion_ai["producto"] and not entidades["producto"]:
                entidades["producto"] = clasificacion_ai["producto"]

            if not entidades.get("producto") and clasificacion_ai.get("texto_interpretado"):
                termino_ai = extraer_termino_busqueda(clasificacion_ai["texto_interpretado"])
                if termino_ai:
                    entidades["producto"] = limpiar_termino_producto(termino_ai)
                    if not analisis.get("termino_busqueda"):
                        analisis["termino_busqueda"] = entidades["producto"]

            if clasificacion_ai["categoria"] and not entidades["categoria"]:
                entidades["categoria"] = clasificacion_ai["categoria"]
                analisis["categoria"] = clasificacion_ai["categoria"]

            if clasificacion_ai["metodo_entrega"] and not entidades["metodo_entrega"]:
                entidades["metodo_entrega"] = clasificacion_ai["metodo_entrega"]

            if clasificacion_ai.get("cantidad") and not entidades.get("cantidad"):
                entidades["cantidad"] = clasificacion_ai["cantidad"]

            if clasificacion_ai["accion"] == "compra" and analisis["intencion"] == "Consulta":
                analisis["intencion"] = "Compra"
            elif clasificacion_ai["accion"] == "cotizacion":
                analisis["intencion"] = "Cotizacion"
            elif clasificacion_ai["accion"] == "entrega":
                analisis["intencion"] = "Entrega"
            elif clasificacion_ai["accion"] == "expos":
                analisis["intencion"] = "Expos"
                
    ajustar_entidades_por_estado(memoria, analisis, entidades, mensaje)

    # =====================================================
    # PRIORIDAD 1: ESTADOS DE PEDIDO ACTIVOS
    # =====================================================
    if id_cliente and memoria:
        if memoria.estado_proceso == "PedidoConfirmado" and entidades["confirmacion_pedido"]:
            return {
                "intencion": "Compra",
                "respuesta": (
                    "Ese pedido ya habÃ­a sido confirmado ðŸ˜Š\n"
                    "Si quieres hacer otra compra, envÃ­ame el nombre del juguete o la categorÃ­a."
                )
            }

        if entidades["cancelacion"] and memoria.estado_proceso in {
            "CompraPendiente", "EsperandoCantidad", "EsperandoDireccion",
            "EsperandoReferencia", "EsperandoMetodoPago", "CompraListaParaConfirmacion"
        }:
            guardar_o_actualizar_memoria_cliente(
                id_cliente=id_cliente,
                estado_proceso="CompraCancelada",
                producto_interes=memoria.producto_interes,
                categoria_interes=memoria.categoria_interes,
                metodo_entrega=memoria.metodo_entrega,
                direccion_entrega=memoria.direccion_entrega,
                referencia_entrega=memoria.referencia_entrega,
                notas_cliente="Compra cancelada por el cliente"
            )
            return {
                "intencion": "Compra",
                "respuesta": (
                    "Entendido ðŸ˜Š Tu pedido fue cancelado.\n"
                    "Si despuÃ©s quieres hacer otra compra, envÃ­ame el nombre del juguete o la categorÃ­a que buscas."
                )
            }

        if memoria.estado_proceso == "EsperandoMasProductos":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            if es_peticion_mostrar_productos(mensaje):
                return {"intencion": "Consulta", "respuesta": obtener_productos_destacados_texto() + "\n\nTu carrito sigue guardado. Cuando elijas otro producto, escrÃ­beme su nombre."}

            categoria_solicitada = detectar_categoria(mensaje)
            if categoria_solicitada:
                return {"intencion": "Consulta", "respuesta": respuesta_categoria_para_seleccion(categoria_solicitada) + "\n\nTu carrito sigue guardado. Elige un producto de la categorÃ­a o escribe: no, cerrar pedido."}

            if es_si_agregar_otro(mensaje):
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente, estado_proceso="CompraPendiente", id_juguete=None,
                    producto_interes=None, categoria_interes=None, metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega, referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=memoria.notas_cliente
                )
                return {"intencion": "Compra", "respuesta": "Perfecto ðŸ˜Š Tu carrito sigue guardado. Escribe el nombre del siguiente producto o escribe: muÃ©strame productos."}

            if es_no_agregar_otro(mensaje):
                metodo_guardado = getattr(memoria, "metodo_entrega", None)
                if not metodo_guardado:
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente, estado_proceso="EsperandoEntrega", id_juguete=getattr(memoria, "id_juguete", None),
                        producto_interes=memoria.producto_interes, categoria_interes=memoria.categoria_interes,
                        metodo_entrega=None, direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente
                    )
                    return {
                        "intencion": "Compra",
                        "respuesta": (
                            "Perfecto, cerramos el carrito âœ…\n\n"
                            f"{texto_carrito_corto(memoria)}\n\n"
                            "Ahora dime si serÃ¡:\n"
                            f"â€¢ a domicilio (envÃ­o ${ENVIO_DOMICILIO:.2f})\n"
                            "â€¢ entrega local"
                        )
                    }
                if metodo_guardado == "Domicilio":
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente, estado_proceso="EsperandoDireccion", id_juguete=getattr(memoria, "id_juguete", None),
                        producto_interes=memoria.producto_interes, categoria_interes=memoria.categoria_interes,
                        metodo_entrega="Domicilio", direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente
                    )
                    memoria = obtener_memoria_cliente(id_cliente)
                    return {"intencion": "Compra", "respuesta": respuesta_despues_de_cantidad(memoria)}
                if metodo_guardado == "Expo":
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente, estado_proceso="EsperandoMetodoPago", id_juguete=getattr(memoria, "id_juguete", None),
                        producto_interes=memoria.producto_interes, categoria_interes=memoria.categoria_interes,
                        metodo_entrega="Expo", direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente
                    )
                    memoria = obtener_memoria_cliente(id_cliente)
                    return {"intencion": "Compra", "respuesta": respuesta_preguntar_metodo_pago(memoria)}
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente, estado_proceso="EsperandoEntrega", id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes, categoria_interes=memoria.categoria_interes,
                    metodo_entrega=None, direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente
                )
                return {"intencion": "Compra", "respuesta": ("Perfecto, cerramos el carrito âœ…\n\n" f"{texto_carrito_corto(memoria)}\n\n" "Ahora elige mÃ©todo de entrega:\n" f"â€¢ a domicilio (envÃ­o ${ENVIO_DOMICILIO:.2f})\n" "â€¢ recoger en expo")}

            if entidades.get("metodo_entrega"):
                metodo = entidades["metodo_entrega"]
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente, estado_proceso="EsperandoDireccion" if metodo == "Domicilio" else "EsperandoMetodoPago",
                    id_juguete=getattr(memoria, "id_juguete", None), producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes, metodo_entrega=metodo, direccion_entrega=None,
                    referencia_entrega=None, notas_cliente=memoria.notas_cliente
                )
                memoria = obtener_memoria_cliente(id_cliente)
                if metodo == "Domicilio":
                    return {"intencion": "Compra", "respuesta": respuesta_despues_de_cantidad(memoria)}
                return {"intencion": "Compra", "respuesta": respuesta_preguntar_metodo_pago(memoria)}

            if es_pago_online(mensaje) or es_pago_efectivo(mensaje):
                if getattr(memoria, "metodo_entrega", None):
                    metodo_seleccionado = "Pago en lÃ­nea" if es_pago_online(mensaje) else "Efectivo"
                    notas_pago = guardar_metodo_pago_en_notas(memoria.notas_cliente, metodo_seleccionado)
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente,
                        estado_proceso="CompraListaParaConfirmacion",
                        id_juguete=getattr(memoria, "id_juguete", None),
                        producto_interes=memoria.producto_interes,
                        categoria_interes=memoria.categoria_interes,
                        metodo_entrega=memoria.metodo_entrega,
                        direccion_entrega=memoria.direccion_entrega,
                        referencia_entrega=memoria.referencia_entrega,
                        notas_cliente=notas_pago
                    )
                    memoria = obtener_memoria_cliente(id_cliente)
                    return {
                        "intencion": "Compra",
                        "respuesta": respuesta_resumen_confirmacion_final(memoria, metodo_seleccionado)
                    }
                return {
                    "intencion": "Compra",
                    "respuesta": (
                        "Perfecto ðŸ˜Š Tu carrito estÃ¡ listo. Antes de seguir necesito saber cÃ³mo quieres recibirlo:\n"
                        f"â€¢ a domicilio (envÃ­o ${ENVIO_DOMICILIO:.2f})\n"
                        "â€¢ recoger en expo"
                    )
                }

            if es_frase_bloqueada_como_producto(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_redireccion_estado(memoria, "mensaje fuera de opciÃ³n")}


            posible_producto = buscar_juguete_para_pedido(producto_interes=mensaje)
            if posible_producto:
                guardar_o_actualizar_memoria_cliente(id_cliente=id_cliente, estado_proceso="EsperandoConfirmacionProducto", id_juguete=posible_producto.id_juguete, producto_interes=posible_producto.nombre, categoria_interes=getattr(posible_producto, "categoria", None), metodo_entrega=memoria.metodo_entrega, direccion_entrega=memoria.direccion_entrega, referencia_entrega=memoria.referencia_entrega, notas_cliente=memoria.notas_cliente)
                return {"intencion": "Compra", "respuesta": mensaje_confirmar_producto(posible_producto)}

            return {"intencion": "Compra", "respuesta": respuesta_redireccion_estado(memoria, "mensaje fuera de opciÃ³n")}

        if memoria.estado_proceso == "EsperandoEntrega":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            if es_peticion_mostrar_productos(mensaje):
                return {"intencion": "Consulta", "respuesta": obtener_productos_destacados_texto() + "\n\nTu carrito sigue guardado. Elige cÃ³mo quieres recibirlo."}

            if es_si_agregar_otro(mensaje):
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente, estado_proceso="CompraPendiente", id_juguete=None,
                    producto_interes=None, categoria_interes=None, metodo_entrega=None,
                    direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente
                )
                return {"intencion": "Compra", "respuesta": "Perfecto ðŸ˜Š Tu carrito sigue guardado. Escribe el nombre del siguiente producto o escribe: muÃ©strame productos."}

            if entidades.get("metodo_entrega"):
                metodo = entidades["metodo_entrega"]
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente, estado_proceso="EsperandoDireccion" if metodo == "Domicilio" else "EsperandoMetodoPago",
                    id_juguete=getattr(memoria, "id_juguete", None), producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes, metodo_entrega=metodo, direccion_entrega=None,
                    referencia_entrega=None, notas_cliente=memoria.notas_cliente
                )
                memoria = obtener_memoria_cliente(id_cliente)
                if metodo == "Domicilio":
                    return {"intencion": "Compra", "respuesta": respuesta_despues_de_cantidad(memoria)}
                return {"intencion": "Compra", "respuesta": respuesta_preguntar_metodo_pago(memoria)}

            if es_pago_online(mensaje) or es_pago_efectivo(mensaje):
                return {
                    "intencion": "Compra",
                    "respuesta": (
                        "Perfecto ðŸ˜Š Tu carrito estÃ¡ listo, pero primero necesito saber cÃ³mo quieres recibirlo:\n"
                        f"â€¢ a domicilio (envÃ­o ${ENVIO_DOMICILIO:.2f})\n"
                        "â€¢ recoger en expo"
                    )
                }

            return {
                "intencion": "Compra",
                "respuesta": (
                    "Para continuar necesito que elijas tu mÃ©todo de entrega:\n"
                    f"â€¢ a domicilio (envÃ­o ${ENVIO_DOMICILIO:.2f})\n"
                    "â€¢ recoger en expo"
                )
            }

        if memoria.estado_proceso == "EsperandoConfirmacionProducto":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            if es_peticion_imagen_producto(mensaje):
                producto_img = buscar_producto_para_imagen(mensaje, memoria=memoria)
                if producto_img:
                    return respuesta_producto_con_imagen(producto_img)

            if es_peticion_mostrar_productos(mensaje):
                guardar_o_actualizar_memoria_cliente(id_cliente=id_cliente, estado_proceso="CompraPendiente", id_juguete=None, producto_interes=None, categoria_interes=None, metodo_entrega=None, direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente)
                return {"intencion": "Consulta", "respuesta": obtener_productos_destacados_texto()}

            categoria_solicitada = detectar_categoria(mensaje)
            if categoria_solicitada:
                guardar_o_actualizar_memoria_cliente(id_cliente=id_cliente, estado_proceso="CompraPendiente", id_juguete=None, producto_interes=None, categoria_interes=categoria_solicitada, metodo_entrega=None, direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente)
                return {"intencion": "Consulta", "respuesta": respuesta_categoria_para_seleccion(categoria_solicitada)}

            if entidades["confirmacion_pedido"]:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoCantidad",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=memoria.notas_cliente
                )
                return {"intencion": "Compra", "respuesta": mensaje_pedir_cantidad(memoria.producto_interes)}

            if entidades["cancelacion"]:
                nuevo_estado = "EsperandoMasProductos" if obtener_carrito_memoria(memoria) else "CompraPendiente"
                guardar_o_actualizar_memoria_cliente(id_cliente=id_cliente, estado_proceso=nuevo_estado, id_juguete=None, producto_interes=None, categoria_interes=None, metodo_entrega=None, direccion_entrega=None, referencia_entrega=None, notas_cliente=memoria.notas_cliente)
                return {"intencion": "Compra", "respuesta": ("Correcto, no agreguÃ© ese producto.\n" "Escribe otro nombre exacto, una categorÃ­a como Peluches, o: muÃ©strame productos.")}

            if es_frase_bloqueada_como_producto(mensaje):
                return {"intencion": "Compra", "respuesta": ("Necesito que confirmes antes de agregarlo al carrito.\n" "Responde: si, no cambiar producto, o muestrame productos.")}

            posible_producto = buscar_juguete_para_pedido(producto_interes=mensaje)
            if posible_producto:
                guardar_o_actualizar_memoria_cliente(id_cliente=id_cliente, estado_proceso="EsperandoConfirmacionProducto", id_juguete=posible_producto.id_juguete, producto_interes=posible_producto.nombre, categoria_interes=getattr(posible_producto, "categoria", None), metodo_entrega=memoria.metodo_entrega, direccion_entrega=memoria.direccion_entrega, referencia_entrega=memoria.referencia_entrega, notas_cliente=memoria.notas_cliente)
                return {"intencion": "Compra", "respuesta": mensaje_confirmar_producto(posible_producto)}

            return {"intencion": "Compra", "respuesta": ("Necesito que confirmes antes de agregarlo al carrito.\n" "Responde: sÃ­, no cambiar producto, o muÃ©strame productos.")}

        if memoria.estado_proceso == "EsperandoCantidad":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            cantidad = entidades.get("cantidad") or extraer_cantidad_mensaje(mensaje)
            if not cantidad:
                return {
                    "intencion": "Compra",
                    "respuesta": respuesta_redireccion_estado(memoria, "cantidad pendiente")
                }

            cantidad = int(cantidad)
            ok_carrito, detalle_carrito, notas_carrito = agregar_producto_actual_a_carrito(memoria, cantidad)
            if not ok_carrito:
                return {"intencion": "Compra", "respuesta": detalle_carrito}
            # Siempre se pregunta si desea agregar mÃ¡s productos antes de pedir entrega/pago.
            # Esto evita brincar el carrito cuando el cliente manda producto + cantidad + entrega en un solo mensaje.
            nuevo_estado = "EsperandoMasProductos"
            guardar_o_actualizar_memoria_cliente(
                id_cliente=id_cliente, estado_proceso=nuevo_estado, id_juguete=getattr(memoria, "id_juguete", None),
                producto_interes=memoria.producto_interes, categoria_interes=memoria.categoria_interes,
                metodo_entrega=memoria.metodo_entrega, direccion_entrega=memoria.direccion_entrega,
                referencia_entrega=memoria.referencia_entrega, notas_cliente=notas_carrito
            )
            memoria = obtener_memoria_cliente(id_cliente)
            return {"intencion": "Compra", "respuesta": respuesta_preguntar_otro_producto(memoria)}

        if memoria.estado_proceso == "EsperandoDireccion":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            if entidades["parece_direccion"]:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoReferencia",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=mensaje.strip(),
                    referencia_entrega=None,
                    notas_cliente=memoria.notas_cliente
                )
                return {
                    "intencion": "Compra",
                    "respuesta": (
                        "Gracias ðŸ˜Š Ya guardÃ© tu direcciÃ³n.\n"
                        "Ahora responde con una referencia visual corta para ubicar la entrega.\n\n"
                        "Ejemplos:\n"
                        "â€¢ Frente al kiosko\n"
                        "â€¢ PortÃ³n negro\n"
                        "â€¢ Edificio verde turquesa"
                    )
                }

            return {
                "intencion": "Compra",
                "respuesta": (
                    "AÃºn necesito tu direcciÃ³n completa ðŸ˜Š\n"
                    "RespÃ³ndeme en un solo mensaje con este formato:\n"
                    "â€¢ Calle y nÃºmero\n"
                    "â€¢ Colonia o fraccionamiento\n"
                    "â€¢ Interior o exterior si aplica"
                )
            }

        if memoria.estado_proceso == "EsperandoReferencia":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            if entidades["parece_referencia"]:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoMetodoPago",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=mensaje.strip(),
                    notas_cliente=memoria.notas_cliente
                )
                memoria = obtener_memoria_cliente(id_cliente)
                return {"intencion": "Compra", "respuesta": respuesta_preguntar_metodo_pago(memoria)}

            return {
                "intencion": "Compra",
                "respuesta": (
                    "AÃºn me falta una referencia para ubicar la entrega ðŸ˜Š\n"
                    "RespÃ³ndeme solo con una referencia breve.\n\n"
                    "Ejemplos:\n"
                    "â€¢ Casa color crema\n"
                    "â€¢ Frente a la farmacia\n"
                    "â€¢ En la esquina junto al kiosko"
                )
            }

        if memoria.estado_proceso == "EsperandoMetodoPago":
            if es_pregunta_ayuda_flujo(mensaje):
                return {"intencion": "Compra", "respuesta": respuesta_ayuda_flujo(memoria)}

            metodo_seleccionado = None
            if es_pago_online(mensaje):
                metodo_seleccionado = "Pago en lÃ­nea"
            elif es_pago_efectivo(mensaje):
                metodo_seleccionado = "Efectivo"

            if metodo_seleccionado:
                notas_pago = guardar_metodo_pago_en_notas(memoria.notas_cliente, metodo_seleccionado)
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraListaParaConfirmacion",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=notas_pago
                )
                memoria = obtener_memoria_cliente(id_cliente)
                return {
                    "intencion": "Compra",
                    "respuesta": respuesta_resumen_confirmacion_final(memoria, metodo_seleccionado)
                }

            return {
                "intencion": "Compra",
                "respuesta": (
                    "Para continuar necesito el mÃ©todo de pago.\n\n"
                    "Responde exactamente una opciÃ³n:\n"
                    "â€¢ efectivo\n"
                    "â€¢ pago en lÃ­nea"
                )
            }

        if memoria.estado_proceso == "CompraListaParaConfirmacion":
            # Crear pedido solo con confirmaciÃ³n final explÃ­cita.
            # No usar entidades["confirmacion_pedido"] porque OpenAI o reglas genÃ©ricas
            # pueden marcar "sÃ­" como confirmaciÃ³n en pasos anteriores.
            if es_confirmacion_pedido(mensaje):
                notas_confirmadas = guardar_confirmacion_final_en_notas(memoria.notas_cliente)
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraListaParaConfirmacion",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=notas_confirmadas
                )
                ok, detalle, id_pedido = crear_pedido_desde_memoria(id_cliente)
                if ok:
                    return {
                        "intencion": "Compra",
                        "respuesta": (
                            f"Â¡Listo! ðŸŽ‰ Tu pedido quedÃ³ registrado correctamente.\n"
                            f"Folio: #{id_pedido}\n\n"
                            f"{detalle.replace('Pedido guardado correctamente con folio #' + str(id_pedido) + '.', '').strip()}\n\n"
                            "En breve daremos seguimiento a tu entrega."
                        )
                    }

                return {
                    "intencion": "Compra",
                    "respuesta": (
                        "No pude confirmar tu pedido en este momento ðŸ˜•\n"
                        f"Detalle: {detalle}"
                    )
                }

            # Si estando en resumen final cambia el mÃ©todo de pago, solo se actualiza
            # el mÃ©todo y se vuelve a mostrar el resumen. No se crea pedido aquÃ­.
            metodo_cambiado = None
            if es_pago_online(mensaje):
                metodo_cambiado = "Pago en lÃ­nea"
            elif es_pago_efectivo(mensaje):
                metodo_cambiado = "Efectivo"
            if metodo_cambiado:
                notas_pago = guardar_metodo_pago_en_notas(memoria.notas_cliente, metodo_cambiado)
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraListaParaConfirmacion",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=notas_pago
                )
                memoria = obtener_memoria_cliente(id_cliente)
                return {
                    "intencion": "Compra",
                    "respuesta": respuesta_resumen_confirmacion_final(memoria, f"{metodo_cambiado}")
                }

            # Si el usuario saluda o escribe algo fuera del flujo, salimos del estado roto
            if analisis["es_saludo"] or analisis["es_despedida"]:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraPendiente",
                    id_juguete=None,
                    producto_interes=None,
                    categoria_interes=None,
                    metodo_entrega=None,
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente="Se reinicia flujo despuÃ©s de resumen fallido"
                )
                return {
                    "intencion": "Consulta",
                    "respuesta": (
                        "Â¡Hola! ðŸ˜Š ReiniciÃ© el flujo anterior para evitar el bloqueo.\n"
                        "Ahora puedes escribirme el nombre del juguete o una categorÃ­a.\n\n"
                        "Ejemplos:\n"
                        "â€¢ Stitch\n"
                        "â€¢ Batman\n"
                        "â€¢ Peluches"
                    )
                }

            termino_nuevo = limpiar_termino_producto(extraer_termino_busqueda(mensaje))
            if termino_nuevo and not entidades["confirmacion_pedido"] and not entidades["cancelacion"]:
                juguete_nuevo = buscar_juguete_para_pedido(producto_interes=termino_nuevo)

                if juguete_nuevo:
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente,
                        estado_proceso="EsperandoConfirmacionProducto",
                        id_juguete=juguete_nuevo.id_juguete,
                        producto_interes=juguete_nuevo.nombre,
                        categoria_interes=getattr(juguete_nuevo, "categoria", None),
                        metodo_entrega=None,
                        direccion_entrega=None,
                        referencia_entrega=None,
                        notas_cliente="Producto reemplazado desde estado de confirmaciÃ³n"
                    )
                    return {
                        "intencion": "Compra",
                        "respuesta": mensaje_confirmar_producto(juguete_nuevo)
                    }

                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraPendiente",
                    id_juguete=None,
                    producto_interes=termino_nuevo,
                    categoria_interes=None,
                    metodo_entrega=None,
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente="Producto reenviado por el cliente desde confirmaciÃ³n fallida"
                )
                return {
                    "intencion": "Compra",
                    "respuesta": mensaje_no_encontrado_con_categorias()
                }

            resumen = construir_resumen_pedido_desde_memoria(memoria)

            if "No pude preparar el resumen" in resumen:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraPendiente",
                    id_juguete=None,
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=None,
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente="Resumen fallido, se regresa a selecciÃ³n de producto"
                )

            return {
                "intencion": "Compra",
                "respuesta": (
                    f"{resumen}\n\n"
                    "AÃºn no registro el pedido. Para confirmarlo responde exactamente: confirmar pedido"
                )
            }

        if memoria.estado_proceso == "CompraPendiente":
            if es_mensaje_no_producto(mensaje, entidades=entidades):
                return {
                    "intencion": "Compra",
                    "respuesta": (
                        "Para continuar necesito el nombre exacto del juguete o una categorÃ­a. "
                        "Si quieres cerrar el carrito y avanzar con la compra, responde: cerrar pedido."
                    )
                }

            cantidad_actual = obtener_cantidad_desde_notas(memoria.notas_cliente)
            cantidad_mensaje = entidades.get("cantidad") or extraer_cantidad_mensaje(mensaje)

            if cantidad_mensaje and not cantidad_actual:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraPendiente",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=memoria.referencia_entrega,
                    notas_cliente=actualizar_cantidad_en_notas(memoria.notas_cliente, int(cantidad_mensaje))
                )
                memoria = obtener_memoria_cliente(id_cliente)
                cantidad_actual = int(cantidad_mensaje)

            if entidades["metodo_entrega"] == "Expo":
                if not cantidad_actual:
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente,
                        estado_proceso="EsperandoCantidad",
                        id_juguete=getattr(memoria, "id_juguete", None),
                        producto_interes=memoria.producto_interes,
                        categoria_interes=memoria.categoria_interes,
                        metodo_entrega="Expo",
                        direccion_entrega=None,
                        referencia_entrega=None,
                        notas_cliente=memoria.notas_cliente
                    )
                    return {"intencion": "Compra", "respuesta": mensaje_pedir_cantidad(memoria.producto_interes)}

                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoMetodoPago",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega="Expo",
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente=memoria.notas_cliente
                )
                memoria = obtener_memoria_cliente(id_cliente)
                return {
                    "intencion": "Compra",
                    "respuesta": respuesta_preguntar_metodo_pago(memoria)
                }

            if entidades["metodo_entrega"] == "Domicilio":
                if not cantidad_actual:
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente,
                        estado_proceso="EsperandoCantidad",
                        id_juguete=getattr(memoria, "id_juguete", None),
                        producto_interes=memoria.producto_interes,
                        categoria_interes=memoria.categoria_interes,
                        metodo_entrega="Domicilio",
                        direccion_entrega=None,
                        referencia_entrega=None,
                        notas_cliente=memoria.notas_cliente
                    )
                    return {"intencion": "Compra", "respuesta": mensaje_pedir_cantidad(memoria.producto_interes)}

                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoDireccion",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega="Domicilio",
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente=memoria.notas_cliente
                )
                return {
                    "intencion": "Compra",
                    "respuesta": (
                        "Perfecto ðŸšš\n"
                        "Para continuar con tu pedido, responde en un solo mensaje con tu direcciÃ³n completa.\n\n"
                        "EscrÃ­bela asÃ­:\n"
                        "â€¢ Calle y nÃºmero\n"
                        "â€¢ Colonia o fraccionamiento\n"
                        "â€¢ Interior o referencia corta si aplica\n\n"
                        "Ejemplo:\n"
                        "Del Ajusco 34, interior 3, Fracc. Las Lomas"
                    )
                }

            if es_peticion_mostrar_productos(mensaje):
                return {"intencion": "Consulta", "respuesta": obtener_productos_destacados_texto()}

            categoria_solicitada = detectar_categoria(mensaje)
            if categoria_solicitada:
                return {"intencion": "Consulta", "respuesta": respuesta_categoria_para_seleccion(categoria_solicitada)}

            posible_producto = buscar_juguete_para_pedido(producto_interes=mensaje)
            if posible_producto:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoConfirmacionProducto",
                    id_juguete=posible_producto.id_juguete,
                    producto_interes=posible_producto.nombre,
                    categoria_interes=getattr(posible_producto, "categoria", memoria.categoria_interes),
                    metodo_entrega=None,
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente=memoria.notas_cliente or "Producto especÃ­fico identificado para compra"
                )
                return {
                    "intencion": "Compra",
                    "respuesta": mensaje_confirmar_producto(posible_producto)
                }

        if memoria.estado_proceso == "EsperandoReferencia":
            if entidades["parece_referencia"]:
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoMetodoPago",
                    id_juguete=getattr(memoria, "id_juguete", None),
                    producto_interes=memoria.producto_interes,
                    categoria_interes=memoria.categoria_interes,
                    metodo_entrega=memoria.metodo_entrega,
                    direccion_entrega=memoria.direccion_entrega,
                    referencia_entrega=mensaje.strip(),
                    notas_cliente=memoria.notas_cliente
                )
                memoria = obtener_memoria_cliente(id_cliente)
                return {"intencion": "Compra", "respuesta": respuesta_preguntar_metodo_pago(memoria)}
    # =====================================================
    # PRIORIDAD 2: CONFIRMACIÃ“N DE PRODUCTO POR CONTEXTO
    # =====================================================
    if id_cliente and contexto and entidades["confirmacion_producto"]:
        producto_ctx = getattr(contexto, "ultimo_termino", None)
        categoria_ctx = getattr(contexto, "ultima_categoria", None)

        id_juguete_ctx = None
        juguete_ctx = None

        if producto_ctx:
            juguete_ctx = buscar_juguete_para_pedido(producto_interes=producto_ctx)
            if juguete_ctx:
                id_juguete_ctx = juguete_ctx.id_juguete
                producto_ctx = juguete_ctx.nombre
                categoria_ctx = getattr(juguete_ctx, "categoria", categoria_ctx)

        if producto_ctx or categoria_ctx:
            guardar_o_actualizar_memoria_cliente(
                id_cliente=id_cliente,
                estado_proceso="EsperandoCantidad",
                id_juguete=id_juguete_ctx,
                producto_interes=producto_ctx,
                categoria_interes=categoria_ctx,
                metodo_entrega=None,
                direccion_entrega=None,
                referencia_entrega=None,
                notas_cliente="Producto confirmado desde contexto conversacional"
            )
            producto_mostrado = producto_ctx or categoria_ctx
            return {
                "intencion": "Compra",
                "respuesta": (
                    mensaje_pedir_cantidad(producto_mostrado)
                )
            }

    # =====================================================
    # PRIORIDAD 3: MENSAJE COMPUESTO CON PRODUCTO + ENTREGA
    # =====================================================
    if id_cliente and entidades["accion"] == "compra" and (entidades["producto"] or entidades["categoria"]):
        if entidades["producto"] and entidades["metodo_entrega"]:
            juguete = buscar_juguete_para_pedido(producto_interes=entidades["producto"])
            if juguete:
                cantidad_detectada = entidades.get("cantidad") or extraer_cantidad_mensaje(mensaje)
                metodo_detectado = entidades["metodo_entrega"]

                if not cantidad_detectada:
                    guardar_o_actualizar_memoria_cliente(
                        id_cliente=id_cliente,
                        estado_proceso="EsperandoCantidad",
                        id_juguete=juguete.id_juguete,
                        producto_interes=juguete.nombre,
                        categoria_interes=getattr(juguete, "categoria", None),
                        metodo_entrega=metodo_detectado,
                        direccion_entrega=None,
                        referencia_entrega=None,
                        notas_cliente="Compra detectada en un solo mensaje"
                    )
                    return {"intencion": "Compra", "respuesta": mensaje_pedir_cantidad(juguete.nombre)}

                ok, detalle, memoria_tmp = guardar_producto_en_carrito_por_juguete(
                    id_cliente=id_cliente,
                    memoria=memoria,
                    juguete=juguete,
                    cantidad=int(cantidad_detectada),
                    metodo_entrega=metodo_detectado
                )
                if not ok:
                    return {"intencion": "Compra", "respuesta": detalle}
                return {"intencion": "Compra", "respuesta": respuesta_preguntar_otro_producto(memoria_tmp)}

    # =====================================================
    # PRIORIDAD 4: USO DE CONTEXTO DE CONSULTA
    # =====================================================
    if id_cliente and contexto and mensaje_usa_contexto(mensaje):
        ultimo_termino = getattr(contexto, "ultimo_termino", None)
        ultima_categoria = getattr(contexto, "ultima_categoria", None)

        if ultima_categoria:
            return construir_respuesta_categoria(
                categoria=ultima_categoria,
                intencion="Consulta"
            )

        if ultimo_termino:
            return construir_respuesta_busqueda(
                termino=ultimo_termino,
                intencion="Consulta"
            )

    # =====================================================
    # PRIORIDAD 5: FLUJO GENERAL
    # =====================================================
    if analisis["es_despedida"]:
        return {
            "intencion": analisis["intencion"],
            "respuesta": (
                "Â¡Gracias por escribirnos! ðŸ˜Š\n"
                "Cuando quieras, aquÃ­ te ayudamos con juguetes, precios, compras, entregas y expos."
            )
        }

    if analisis["es_saludo"] and not analisis["requiere_catalogo"] and analisis["intencion"] == "Consulta":
        return {"intencion": "Consulta", "respuesta": construir_respuesta_saludo_publico()}

    if analisis["intencion"] == "Expos":
        return construir_respuesta_expos()

    if analisis["intencion"] == "Entrega":
        return construir_respuesta_entrega()

    if analisis["categoria"]:
        if id_cliente:
            guardar_o_actualizar_contexto_cliente(
                id_cliente=id_cliente,
                ultima_intencion=analisis["intencion"],
                ultima_categoria=analisis["categoria"],
                ultimo_termino=None,
                ultimo_producto=None
            )

            if analisis["intencion"] == "Compra" or entidades["accion"] == "compra":
                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="CompraPendiente",
                    producto_interes=None,
                    categoria_interes=analisis["categoria"],
                    metodo_entrega=None,
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente="Cliente mostrÃ³ intenciÃ³n de compra por categorÃ­a"
                )

        respuesta = construir_respuesta_categoria(
            categoria=analisis["categoria"],
            intencion="Compra" if entidades["accion"] == "compra" else analisis["intencion"]
        )

        if analisis["intencion"] == "Compra" or entidades["accion"] == "compra":
            respuesta["respuesta"] += (
                "\n\nSi quieres seguir con tu compra, responde asÃ­:\n"
                "â€¢ nombre exacto del producto\n"
                "â€¢ cantidad\n"
                "â€¢ a domicilio o recoger en expo\n\n"
                "Ejemplo:\n"
                "â€¢ Quiero 2 osos gigantes a domicilio"
            )

        return respuesta

    if analisis["termino_busqueda"]:
        if id_cliente:
            guardar_o_actualizar_contexto_cliente(
                id_cliente=id_cliente,
                ultima_intencion=analisis["intencion"],
                ultima_categoria=None,
                ultimo_termino=analisis["termino_busqueda"],
                ultimo_producto=None
            )

            if analisis["intencion"] == "Compra" or entidades["accion"] == "compra":
                termino_limpio = limpiar_termino_producto(analisis["termino_busqueda"])
                juguete_detectado = buscar_juguete_para_pedido(producto_interes=termino_limpio)

                guardar_o_actualizar_memoria_cliente(
                    id_cliente=id_cliente,
                    estado_proceso="EsperandoConfirmacionProducto" if juguete_detectado else "CompraPendiente",
                    id_juguete=juguete_detectado.id_juguete if juguete_detectado else None,
                    producto_interes=juguete_detectado.nombre if juguete_detectado else termino_limpio,
                    categoria_interes=getattr(juguete_detectado, "categoria", None) if juguete_detectado else None,
                    metodo_entrega=None,
                    direccion_entrega=None,
                    referencia_entrega=None,
                    notas_cliente="Cliente mostrÃ³ intenciÃ³n de compra por tÃ©rmino de bÃºsqueda"
                )
                if juguete_detectado:
                    return {"intencion": "Compra", "respuesta": mensaje_confirmar_producto(juguete_detectado)}

        respuesta = construir_respuesta_busqueda(
            termino=analisis["termino_busqueda"],
            intencion="Compra" if entidades["accion"] == "compra" else analisis["intencion"]
        )

        if analisis["intencion"] == "Compra" or entidades["accion"] == "compra":
            respuesta["respuesta"] += (
                "\n\nSi ya elegiste uno, responde asÃ­:\n"
                "â€¢ nombre exacto del producto\n"
                "â€¢ cantidad\n"
                "â€¢ a domicilio o recoger en expo\n\n"
                "Ejemplo:\n"
                "â€¢ Quiero 2 carritos rojos a domicilio"
            )

        return respuesta

    if analisis["requiere_humano"]:
        return {
            "intencion": "Consulta",
            "respuesta": (
                mensaje_no_encontrado_con_categorias()
            )
        }

    return {
        "intencion": analisis["intencion"],
        "respuesta": (
            mensaje_no_encontrado_con_categorias()
        )
    }

# =========================================================
# META WHATSAPP
# =========================================================
def enviar_mensaje_whatsapp(destino: str, texto: str):
    """
    EnvÃ­a mensajes por el canal configurado.
    - meta: WhatsApp Cloud API oficial.
    - openwa: gateway self-hosted compatible con OpenWA.

    Se mantiene Meta como proveedor predeterminado porque ya es el canal estable del proyecto.
    OpenWA es opcional y se activa con WHATSAPP_PROVIDER=openwa.
    """
    if WHATSAPP_PROVIDER == "openwa":
        if not OPENWA_BASE_URL or not OPENWA_API_KEY:
            raise RuntimeError("Faltan OPENWA_BASE_URL u OPENWA_API_KEY para WHATSAPP_PROVIDER=openwa")

        numero = normalizar_numero_whatsapp(destino)
        chat_id = numero if "@" in numero else f"{numero}{OPENWA_CHAT_SUFFIX}"
        url = f"{OPENWA_BASE_URL}/api/sessions/{OPENWA_SESSION_ID}/messages/send-text"
        headers = {
            "Content-Type": "application/json",
            "X-API-Key": OPENWA_API_KEY
        }
        payload = {"chatId": chat_id, "text": texto}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        log_debug("RESPUESTA OPENWA:", resp.status_code, resp.text)
        return resp

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {
            "body": texto
        }
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    log_debug("RESPUESTA META:", resp.status_code, resp.text)
    return resp


def url_publica_archivo(ruta: str) -> Optional[str]:
    if not ruta:
        return None
    ruta = str(ruta).strip().replace("\\", "/")
    if not ruta or ruta.lower() in {"none", "null", "-"}:
        return None
    if ruta.startswith("http://") or ruta.startswith("https://"):
        return ruta if es_url_absoluta_valida(ruta) else None
    if ruta.startswith("static/"):
        ruta = "/" + ruta
    elif ruta.startswith("productos/"):
        ruta = "/static/" + ruta
    elif not ruta.startswith("/"):
        ruta = f"{PRODUCT_IMAGE_WEB_PREFIX}/{ruta}"
    if not PUBLIC_BASE_URL or not es_url_absoluta_valida(PUBLIC_BASE_URL):
        return None
    return f"{PUBLIC_BASE_URL}{ruta}"


def enviar_imagen_whatsapp(destino: str, imagen_url: str, caption: str = ""):
    if not es_url_absoluta_valida(imagen_url):
        log_debug("IMAGEN NO ENVIADA: URL pÃºblica invÃ¡lida para Meta", imagen_url)
        class RespLocal:
            status_code = 0
            text = "URL pÃºblica invÃ¡lida para WhatsApp"
        return RespLocal()
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{META_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "image",
        "image": {"link": imagen_url}
    }
    if caption:
        payload["image"]["caption"] = caption[:1024]
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    log_debug("RESPUESTA META IMAGEN:", resp.status_code, resp.text)
    return resp


def enviar_imagenes_producto_whatsapp(destino: str, image_urls: list):
    respuestas = []
    for item in image_urls or []:
        if isinstance(item, dict):
            imagen_url = item.get("url")
            caption = item.get("caption", "")
        else:
            imagen_url = str(item)
            caption = ""
        if imagen_url:
            respuestas.append(enviar_imagen_whatsapp(destino, imagen_url, caption))
    return respuestas

# =========================================================
# ANÃLISIS DE IMÃGENES / VISIÃ“N
# =========================================================
client_openai = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

def obtener_url_media_whatsapp(media_id: str) -> str:
    if not media_id:
        raise ValueError("media_id vacÃ­o")

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{media_id}"
    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}"
    }

    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()

    data = resp.json()
    media_url = data.get("url")

    if not media_url:
        raise ValueError("No se recibiÃ³ URL del medio desde Meta")

    return media_url

def descargar_media_whatsapp(media_url: str):
    if not media_url:
        raise ValueError("media_url vacÃ­o")

    headers = {
        "Authorization": f"Bearer {META_ACCESS_TOKEN}"
    }

    resp = requests.get(media_url, headers=headers, timeout=30)
    resp.raise_for_status()

    mime_type = resp.headers.get("Content-Type", "application/octet-stream")
    mime_type = mime_type.split(";")[0].strip().lower()

    return resp.content, mime_type

def limpiar_json_respuesta(texto: str) -> str:
    texto = (texto or "").strip()

    if texto.startswith("```"):
        texto = texto.replace("```json", "").replace("```", "").strip()

    inicio = texto.find("{")
    fin = texto.rfind("}")

    if inicio != -1 and fin != -1 and fin > inicio:
        texto = texto[inicio:fin + 1]

    return texto

def analizar_imagen_juguete_con_openai(
    image_bytes: bytes,
    mime_type: str = "image/jpeg",
    caption: str = ""
) -> dict:
    if not client_openai:
        raise RuntimeError("OPENAI_API_KEY no configurado")

    if not image_bytes:
        raise ValueError("La imagen estÃ¡ vacÃ­a")

    if not VISION_MODEL:
        raise RuntimeError("VISION_MODEL no configurado")

    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
    image_data_url = f"data:{mime_type};base64,{image_base64}"

    prompt = f"""
Analiza esta imagen de un juguete o producto infantil.

Tu tarea es responder ÃšNICAMENTE en JSON vÃ¡lido con esta estructura exacta:
{{
  "categoria_sugerida": "BebÃ©s|NiÃ±os|NiÃ±as|Peluches|Juegos de mesa|Coleccionables|Desconocida",
  "terminos_busqueda": ["termino1", "termino2", "termino3"],
  "descripcion_corta": "texto breve",
  "confianza": 0.0
}}

Reglas:
- Si no puedes identificar bien el juguete, usa "Desconocida".
- "terminos_busqueda" debe traer entre 1 y 5 tÃ©rminos Ãºtiles para buscar en catÃ¡logo.
- "confianza" debe ser un nÃºmero entre 0 y 1.
- No agregues explicaciÃ³n fuera del JSON.
- Toma en cuenta este texto opcional del usuario: "{caption}"
""".strip()

    response = client_openai.responses.create(
        model=VISION_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": prompt
                    },
                    {
                        "type": "input_image",
                        "image_url": image_data_url,
                        "detail": "high"
                    }
                ]
            }
        ]
    )

    texto = getattr(response, "output_text", "") or ""
    texto = limpiar_json_respuesta(texto)

    try:
        data = json.loads(texto)
    except Exception:
        log_debug("Respuesta no JSON de visiÃ³n:", texto)
        data = {
            "categoria_sugerida": "Desconocida",
            "terminos_busqueda": [],
            "descripcion_corta": "No se pudo interpretar la imagen con precisiÃ³n.",
            "confianza": 0.0
        }

    categoria = str(data.get("categoria_sugerida") or "Desconocida").strip()
    terminos = data.get("terminos_busqueda") or []
    descripcion = str(data.get("descripcion_corta") or "Sin descripciÃ³n").strip()
    confianza = data.get("confianza", 0.0)

    if not isinstance(terminos, list):
        terminos = []

    terminos = [normalizar_texto(str(t)) for t in terminos if str(t).strip()]
    terminos = [t for t in terminos if t][:5]

    try:
        confianza = float(confianza)
    except Exception:
        confianza = 0.0

    categorias_validas = {
        "BebÃ©s",
        "NiÃ±os",
        "NiÃ±as",
        "Peluches",
        "Juegos de mesa",
        "Coleccionables",
        "Desconocida"
    }

    if categoria not in categorias_validas:
        categoria = "Desconocida"

    return {
        "categoria_sugerida": categoria,
        "terminos_busqueda": terminos,
        "descripcion_corta": descripcion,
        "confianza": max(0.0, min(1.0, confianza))
    }

def transcribir_audio_whatsapp(media_id: str) -> str:
    if not client_openai:
        raise RuntimeError("OPENAI_API_KEY no configurado")
    media_url = obtener_url_media_whatsapp(media_id)
    audio_bytes, mime_type = descargar_media_whatsapp(media_url)
    if not audio_bytes:
        raise ValueError("El audio recibido estÃ¡ vacÃ­o")

    import tempfile
    sufijos = {
        "audio/ogg": ".ogg",
        "audio/opus": ".ogg",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/aac": ".aac",
        "audio/wav": ".wav",
        "audio/webm": ".webm",
    }
    suffix = sufijos.get(mime_type, ".ogg")
    tmp_name = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(audio_bytes)
            tmp_name = tmp.name
        with open(tmp_name, "rb") as audio_file:
            transcripcion = client_openai.audio.transcriptions.create(
                model=AUDIO_TRANSCRIPTION_MODEL,
                file=audio_file,
                language="es"
            )
        texto = getattr(transcripcion, "text", "") or ""
        return texto.strip()
    finally:
        if tmp_name:
            try:
                os.remove(tmp_name)
            except Exception:
                pass


def responder_audio_whatsapp(media_id: str, id_cliente: int) -> dict:
    try:
        texto = transcribir_audio_whatsapp(media_id)
        if not texto:
            return {
                "intencion": "Consulta",
                "transcripcion": "",
                "respuesta": (
                    "RecibÃ­ tu nota de voz, pero no pude entender el audio con claridad ðŸ˜•\n"
                    "Puedes enviarla de nuevo o escribir el nombre del juguete."
                )
            }
        resultado = responder_mensaje(texto, id_cliente=id_cliente)
        resultado["transcripcion"] = texto
        resultado["respuesta"] = f"EntendÃ­ tu nota de voz como: â€œ{texto}â€\n\n" + resultado["respuesta"]
        return resultado
    except Exception as e:
        error_logger.exception("ERROR ANALIZANDO AUDIO")
        return {
            "intencion": "Consulta",
            "transcripcion": "",
            "respuesta": (
                "RecibÃ­ tu nota de voz, pero ocurriÃ³ un error al procesarla ðŸ˜•\n"
                "Puedes escribir tu pedido o enviar otra nota de voz mÃ¡s clara."
            ),
            "error": str(e)
        }


def responder_imagen_juguete(media_id: str, caption: str = "") -> dict:
    try:
        media_url = obtener_url_media_whatsapp(media_id)
        image_bytes, mime_type = descargar_media_whatsapp(media_url)
        if not mime_type.startswith("image/"):
            raise ValueError(f"El medio recibido no es imagen: {mime_type}")

        analisis = analizar_imagen_juguete_con_openai(
            image_bytes=image_bytes,
            mime_type=mime_type,
            caption=caption
        )

        log_debug("ANALISIS IMAGEN:", analisis)

        categoria = analisis.get("categoria_sugerida", "Desconocida")
        terminos = analisis.get("terminos_busqueda", [])
        descripcion = analisis.get("descripcion_corta", "")
        confianza = analisis.get("confianza", 0.0)

        if categoria != "Desconocida":
            productos_categoria = buscar_por_categoria(categoria)
            if productos_categoria:
                lineas = [
                    f"EncontrÃ© productos parecidos en la categorÃ­a {categoria}:"
                ]
                for p in productos_categoria[:5]:
                    lineas.append(f"- {p.nombre}: ${p.precio:.2f} | stock: {p.stock}")

                image_urls = []
                for p in productos_categoria[:3]:
                    url_img = obtener_url_imagen_publica_producto(p)
                    if url_img:
                        image_urls.append({"url": url_img, "caption": f"{p.nombre} - ${float(p.precio):.2f}"})
                return {
                    "intencion": "Consulta",
                    "respuesta": "\n".join(lineas) + ("\n\nTambiÃ©n te envÃ­o las imÃ¡genes disponibles de productos parecidos." if image_urls else ""),
                    "image_urls": image_urls,
                    "analisis_imagen": analisis
                }

        consulta_texto = " ".join(terminos).strip()
        if consulta_texto:
            resultados = buscar_juguete_por_texto(consulta_texto)
            if resultados:
                lineas = [
                   "EncontrÃ© estos productos parecidos a tu imagen:"
                ]
                for r in resultados:
                    lineas.append(
                        f"- {r.nombre}: ${r.precio:.2f}, categorÃ­a {r.categoria}, stock {r.stock}. {r.descripcion}"
                    )

                image_urls = []
                for r in resultados[:3]:
                    url_img = obtener_url_imagen_publica_producto(r)
                    if url_img:
                        image_urls.append({"url": url_img, "caption": f"{r.nombre} - ${float(r.precio):.2f}"})
                return {
                    "intencion": "Consulta",
                    "respuesta": "\n".join(lineas) + ("\n\nTambiÃ©n te envÃ­o las imÃ¡genes disponibles de productos parecidos." if image_urls else ""),
                    "image_urls": image_urls,
                    "analisis_imagen": analisis
                }

        return {
            "intencion": "Consulta",
            "respuesta": mensaje_no_encontrado_con_categorias(),
            "analisis_imagen": analisis
        }

    except Exception as e:
        log_debug("ERROR ANALIZANDO IMAGEN:", str(e))
        return {
            "intencion": "Consulta",
            "respuesta": (
                "RecibÃ­ la imagen, pero ocurriÃ³ un error al intentar analizarla. "
                "Puedes reenviar la foto o escribir el nombre del juguete.\n\n"
                + mensaje_no_encontrado_con_categorias()
            ),
            "analisis_imagen": {
                "error": str(e)
            }
        }

# =========================================================
# RUTAS BASE
# =========================================================
@app.get("/")
def inicio():
    return {"mensaje": "API de JugueteriaBot activa"}

# =========================================================
# WEBHOOK META
# =========================================================
@app.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == META_VERIFY_TOKEN:
        return PlainTextResponse(challenge)

    raise HTTPException(status_code=403, detail="Token de verificaciÃ³n invÃ¡lido")

@app.post("/webhook")
async def recibir_webhook(request: Request):
    body = await request.json()
    log_debug("Webhook recibido:", body)

    try:
        entry = body.get("entry", [])
        if not entry:
            return JSONResponse(content={"status": "sin entry"})

        changes = entry[0].get("changes", [])
        if not changes:
            return JSONResponse(content={"status": "sin changes"})

        value = changes[0].get("value", {})
        messages = value.get("messages", [])
        contacts = value.get("contacts", [])

        if not messages:
            return JSONResponse(content={"status": "sin mensajes"})

        mensaje_obj = messages[0]
        tipo_mensaje = mensaje_obj.get("type")

        telefono_original = mensaje_obj.get("from", "")
        telefono = normalizar_numero_whatsapp(telefono_original)
        if excede_rate_limit(telefono):
            whatsapp_logger.warning("Rate limit excedido para %s", telefono)
            return JSONResponse(content={"status": "rate_limited"}, status_code=429)

        nombre = None
        if contacts:
            nombre = contacts[0].get("profile", {}).get("name")

        id_cliente = obtener_o_crear_cliente_por_telefono(
            telefono=telefono,
            nombre=nombre,
            ciudad="Desconocida"
        )

        if tipo_mensaje == "text":
            mensaje_original = mensaje_obj["text"]["body"]
            mensaje = normalizar_texto(mensaje_original)

            resultado = responder_mensaje(mensaje, id_cliente=id_cliente)
            guardar_consulta(id_cliente, mensaje, resultado["intencion"])
            guardar_log_conversacion_agente(
                id_cliente=id_cliente,
                telefono=telefono,
                mensaje_cliente=mensaje,
                json_agente=resultado.get("agente_json") if isinstance(resultado, dict) else None,
                accion_final=resultado.get("intencion") if isinstance(resultado, dict) else None,
                respuesta_bot=resultado.get("respuesta") if isinstance(resultado, dict) else None
            )

            resp_meta = enviar_mensaje_whatsapp(telefono, resultado["respuesta"])
            imagenes_meta = enviar_imagenes_producto_whatsapp(telefono, resultado.get("image_urls", []))

            return JSONResponse(content={
                "status": "ok",
                "tipo": "text",
                "meta_status": resp_meta.status_code,
                "imagenes_enviadas": len(imagenes_meta)
            })

        elif tipo_mensaje == "image":
            image_data = mensaje_obj.get("image", {})
            media_id = image_data.get("id")
            caption = image_data.get("caption", "")

            log_debug("IMAGEN RECIBIDA:", media_id, caption)

            resultado = responder_imagen_juguete(
                media_id=media_id,
                caption=caption
            )

            mensaje_guardado = f"[IMAGEN] caption={caption or 'Sin texto'} media_id={media_id}"
            guardar_consulta(id_cliente, mensaje_guardado, resultado["intencion"])

            resp_meta = enviar_mensaje_whatsapp(telefono, resultado["respuesta"])
            imagenes_meta = enviar_imagenes_producto_whatsapp(telefono, resultado.get("image_urls", []))

            return JSONResponse(content={
                "status": "ok",
                "tipo": "image",
                "media_id": media_id,
                "meta_status": resp_meta.status_code,
                "imagenes_enviadas": len(imagenes_meta),
                "analisis_imagen": resultado.get("analisis_imagen", {})
            })

        elif tipo_mensaje == "audio":
            audio_data = mensaje_obj.get("audio", {})
            media_id = audio_data.get("id")
            log_debug("AUDIO RECIBIDO:", media_id)

            resultado = responder_audio_whatsapp(media_id=media_id, id_cliente=id_cliente)
            mensaje_guardado = f"[AUDIO] transcripcion={resultado.get('transcripcion', '')} media_id={media_id}"
            guardar_consulta(id_cliente, mensaje_guardado, resultado["intencion"])

            resp_meta = enviar_mensaje_whatsapp(telefono, resultado["respuesta"])

            return JSONResponse(content={
                "status": "ok",
                "tipo": "audio",
                "media_id": media_id,
                "transcripcion": resultado.get("transcripcion", ""),
                "meta_status": resp_meta.status_code
            })

        else:
            texto_respuesta = "Por ahora puedo procesar mensajes de texto, imÃ¡genes y notas de voz."
            resp_meta = enviar_mensaje_whatsapp(telefono, texto_respuesta)

            return JSONResponse(content={
                "status": "mensaje no soportado",
                "tipo": tipo_mensaje,
                "meta_status": resp_meta.status_code
            })

    except Exception as e:
        error_logger.exception("ERROR EN WEBHOOK")
        log_debug("ERROR EN WEBHOOK:", str(e))
        return JSONResponse(
            content={"status": "error", "detalle": str(e)},
            status_code=500
        )

# =========================================================
# API CHAT
# =========================================================
@app.post("/chat")
def chat(data: MensajeEntrada):
    telefono = normalizar_numero_whatsapp(data.telefono)
    if excede_rate_limit(f"chat:{telefono}"):
        raise HTTPException(status_code=429, detail="Demasiados mensajes en poco tiempo.")

    id_cliente = obtener_o_crear_cliente_por_telefono(
        telefono=telefono,
        nombre=data.nombre,
        ciudad=data.ciudad
    )

    resultado = responder_mensaje(data.mensaje, id_cliente=id_cliente)

    try:
        guardar_consulta(id_cliente, data.mensaje, resultado["intencion"])
    except Exception as e:
        log_debug("Error guardando consulta:", e)

    return {
        "id_cliente": id_cliente,
        "intencion": resultado["intencion"],
        "respuesta": resultado["respuesta"]
    }


# =========================================================
# PRODUCTOS: FOTOS / PROVEEDORES / CÃ“DIGOS
# =========================================================
def normalizar_url_foto_producto(foto_url: Optional[str], foto_local: Optional[str] = None) -> Optional[str]:
    for valor in (foto_url, foto_local):
        if not valor:
            continue
        ruta = str(valor).strip().replace("\\", "/")
        if ruta and ruta.lower() not in {"none", "null", "-"}:
            return ruta
    return None


def producto_tiene_foto(juguete) -> bool:
    return bool(normalizar_url_foto_producto(getattr(juguete, "foto_url", None), getattr(juguete, "foto_local", None)))


def obtener_url_imagen_publica_producto(juguete) -> Optional[str]:
    # Primero intenta URL externa; si no es vÃ¡lida, intenta foto local.
    for ruta in (getattr(juguete, "foto_url", None), getattr(juguete, "foto_local", None)):
        url = url_publica_archivo(ruta)
        if url:
            return url
    return None


def guardar_foto_producto_upload(archivo: Optional[UploadFile], nombre_producto: str = "producto") -> Optional[str]:
    if not archivo or not getattr(archivo, "filename", None):
        return None
    filename = Path(archivo.filename).name
    ext = Path(filename).suffix.lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("La foto del producto debe ser JPG, PNG o WEBP.")
    safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "-", normalizar_texto(nombre_producto or "producto")).strip("-") or "producto"
    destino_nombre = f"{safe_name}-{int(time.time())}{ext}"
    destino = PRODUCT_IMAGE_DIR / destino_nombre
    contenido = archivo.file.read()
    if len(contenido) > 5 * 1024 * 1024:
        raise ValueError("La foto no debe superar 5 MB.")
    destino.write_bytes(contenido)
    return f"{PRODUCT_IMAGE_WEB_PREFIX}/{destino_nombre}"


def es_peticion_imagen_producto(mensaje: str) -> bool:
    texto = normalizar_texto(mensaje)
    claves = ["foto", "fotos", "imagen", "imagenes", "ver imagen", "ver foto", "mandame foto", "muestrame foto", "muestrame imagen"]
    return any(c in texto for c in claves)


def texto_sin_palabras_imagen(mensaje: str) -> str:
    texto = normalizar_texto(mensaje)
    for patron in ["quiero ver", "mandame", "muestrame", "mostrar", "ver", "fotos", "foto", "imagenes", "imagen", "del producto", "producto"]:
        texto = texto.replace(patron, " ")
    return re.sub(r"\s+", " ", texto).strip()


def respuesta_producto_con_imagen(juguete) -> dict:
    imagen_url = obtener_url_imagen_publica_producto(juguete)
    if not imagen_url:
        return {
            "intencion": "Consulta",
            "respuesta": (
                f"SÃ­ encontrÃ© {juguete.nombre}, pero todavÃ­a no tiene foto cargada en el sistema.\n\n"
                f"Precio: ${float(juguete.precio):.2f}\n"
                f"Stock: {int(juguete.stock or 0)} pieza(s)."
            )
        }
    return {
        "intencion": "Consulta",
        "respuesta": (
            f"Claro ðŸ˜Š Te envÃ­o la imagen de {juguete.nombre}.\n"
            f"Precio: ${float(juguete.precio):.2f} | stock: {int(juguete.stock or 0)} pieza(s).\n\n"
            "Si te interesa, responde: sÃ­, lo quiero."
        ),
        "image_urls": [{"url": imagen_url, "caption": f"{juguete.nombre} - ${float(juguete.precio):.2f}"}]
    }


def buscar_producto_para_imagen(mensaje: str, memoria=None):
    termino = texto_sin_palabras_imagen(mensaje)
    if termino:
        encontrado = buscar_juguete_para_pedido(producto_interes=termino)
        if encontrado:
            return encontrado
    if memoria and getattr(memoria, "id_juguete", None):
        try:
            return obtener_juguete_por_id(int(memoria.id_juguete))
        except Exception:
            return None
    if memoria and getattr(memoria, "producto_interes", None):
        return buscar_juguete_para_pedido(producto_interes=memoria.producto_interes)
    return None

# =========================================================
# PANEL ADMIN - HELPERS
# =========================================================
def obtener_categorias():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_categoria, nombre FROM Categoria ORDER BY nombre")
        return cursor.fetchall()
    finally:
        conn.close()

def obtener_juguetes():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                j.id_juguete,
                j.nombre,
                j.descripcion,
                j.precio,
                ISNULL(j.precio_compra, 0) AS precio_compra,
                j.stock,
                j.marca,
                j.sku,
                j.codigo_barras,
                j.id_proveedor,
                j.foto_url,
                j.foto_local,
                c.nombre AS categoria,
                p.nombre AS proveedor
            FROM Juguete j
            INNER JOIN Categoria c ON j.id_categoria = c.id_categoria
            LEFT JOIN Proveedor p ON j.id_proveedor = p.id_proveedor
            ORDER BY j.id_juguete DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

def obtener_juguete_por_id(id_juguete: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id_juguete,
                nombre,
                descripcion,
                ISNULL(precio_compra, 0) AS precio_compra,
                precio,
                stock,
                edad_minima,
                edad_maxima,
                marca,
                sku,
                codigo_barras,
                id_proveedor,
                foto_url,
                foto_local,
                id_categoria
            FROM Juguete
            WHERE id_juguete = ?
        """, id_juguete)
        return cursor.fetchone()
    finally:
        conn.close()

def obtener_expos_admin():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id_expo,
                nombre,
                ubicacion,
                fecha_inicio,
                fecha_fin
            FROM Expo
            ORDER BY id_expo DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

def obtener_expo_por_id(id_expo: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                id_expo,
                nombre,
                ubicacion,
                fecha_inicio,
                fecha_fin
            FROM Expo
            WHERE id_expo = ?
        """, id_expo)
        return cursor.fetchone()
    finally:
        conn.close()

def obtener_metricas_dashboard() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        datos = {}
        cursor.execute("SELECT COUNT(*) FROM Pedido WHERE CAST(fecha_pedido AS DATE) = CAST(GETDATE() AS DATE)")
        datos["pedidos_hoy"] = cursor.fetchone()[0]
        cursor.execute("""
            SELECT ISNULL(SUM(total),0)
            FROM Pedido
            WHERE estado = 'Entregado'
              AND CAST(ISNULL(fecha_entregado, fecha_pedido) AS DATE) = CAST(GETDATE() AS DATE)
        """)
        datos["ventas_entregadas_hoy"] = float(cursor.fetchone()[0] or 0)
        cursor.execute("""
            SELECT ISNULL(SUM((ISNULL(d.precio_unitario,0) - ISNULL(d.costo_unitario,0)) * ISNULL(d.cantidad,0)),0)
            FROM Pedido p
            INNER JOIN DetallePedido d ON p.id_pedido = d.id_pedido
            WHERE p.estado = 'Entregado'
              AND CAST(ISNULL(p.fecha_entregado, p.fecha_pedido) AS DATE) = CAST(GETDATE() AS DATE)
        """)
        datos["ganancia_entregada_hoy"] = float(cursor.fetchone()[0] or 0)
        datos["ventas_estimadas_hoy"] = datos["ventas_entregadas_hoy"]
        cursor.execute("SELECT COUNT(*) FROM Juguete WHERE ISNULL(stock,0) <= ?", STOCK_BAJO_UMBRAL)
        datos["productos_bajo_stock"] = cursor.fetchone()[0]
        datos["productos_bajo_stock_lista"] = obtener_productos_bajo_stock(STOCK_BAJO_UMBRAL)
        datos["ventas_grafica"] = obtener_ventas_grafica(14)
        cursor.execute("SELECT COUNT(*) FROM ConsultaCliente WHERE fecha >= DATEADD(day,-1,GETDATE())")
        datos["consultas_24h"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(DISTINCT id_cliente) FROM ConsultaCliente WHERE fecha >= DATEADD(day,-7,GETDATE())")
        datos["clientes_recientes"] = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM Expo WHERE fecha_inicio >= CAST(GETDATE() AS DATE)")
        datos["expos_proximas"] = cursor.fetchone()[0]
        return datos
    except Exception as e:
        error_logger.exception("Error obteniendo mÃ©tricas dashboard")
        return {"error": str(e)}
    finally:
        conn.close()

def obtener_pedidos(estado: Optional[str] = None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id_pedido,
                c.nombre AS cliente,
                c.telefono,
                p.fecha_pedido,
                p.estado,
                p.metodo_entrega,
                p.direccion_entrega,
                p.referencia_entrega,
                p.subtotal,
                p.total,
                ISNULL(p.costo_envio, 0) AS costo_envio,
                p.metodo_pago,
                p.stock_descontado,
                p.fecha_entregado,
                p.estado_pago,
                p.mercadopago_init_point
            FROM Pedido p
            INNER JOIN Cliente c
                ON p.id_cliente = c.id_cliente
            WHERE (? IS NULL OR p.estado = ?)
            ORDER BY p.id_pedido DESC
        """, estado, estado)
        return cursor.fetchall()
    finally:
        conn.close()

def marcar_pedido_entregado(id_pedido: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT stock_descontado
            FROM Pedido
            WHERE id_pedido = ?
        """, id_pedido)
        pedido = cursor.fetchone()

        if not pedido:
            raise ValueError("Pedido no encontrado")

        if not bool(pedido.stock_descontado):
            cursor.execute("""
                SELECT id_juguete, cantidad
                FROM DetallePedido
                WHERE id_pedido = ?
            """, id_pedido)
            detalles = cursor.fetchall()

            for d in detalles:
                cursor.execute("""
                    UPDATE Juguete
                    SET stock = stock - ?
                    WHERE id_juguete = ? AND stock >= ?
                """, d.cantidad, d.id_juguete, d.cantidad)
                if cursor.rowcount == 0:
                    raise ValueError("Stock insuficiente para marcar el pedido como entregado.")

            cursor.execute("""
                UPDATE Pedido
                SET stock_descontado = 1
                WHERE id_pedido = ?
            """, id_pedido)

        cursor.execute("""
            UPDATE Pedido
            SET estado = 'Entregado',
                fecha_entregado = ISNULL(fecha_entregado, GETDATE())
            WHERE id_pedido = ?
        """, id_pedido)

        conn.commit()
        registrar_notificacion("venta", "Venta entregada", f"El pedido #{id_pedido} fue marcado como entregado y ya cuenta como venta.")
    finally:
        conn.close()

def obtener_pedido_por_id(id_pedido: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id_pedido,
                p.id_cliente,
                c.nombre AS cliente,
                c.telefono,
                p.fecha_pedido,
                p.estado,
                p.metodo_entrega,
                p.direccion_entrega,
                p.referencia_entrega,
                p.subtotal,
                p.total,
                ISNULL(p.costo_envio, 0) AS costo_envio,
                p.metodo_pago,
                p.observaciones,
                p.stock_descontado,
                p.fecha_entregado,
                p.estado_pago,
                p.mercadopago_preference_id,
                p.mercadopago_init_point
            FROM Pedido p
            INNER JOIN Cliente c
                ON p.id_cliente = c.id_cliente
            WHERE p.id_pedido = ?
        """, id_pedido)
        return cursor.fetchone()
    finally:
        conn.close()

def obtener_detalles_pedido(id_pedido: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                d.id_juguete,
                j.nombre AS juguete,
                d.cantidad,
                d.precio_unitario,
                ISNULL(d.costo_unitario, 0) AS costo_unitario,
                d.subtotal,
                (ISNULL(d.precio_unitario,0) - ISNULL(d.costo_unitario,0)) * ISNULL(d.cantidad,0) AS ganancia
            FROM DetallePedido d
            INNER JOIN Juguete j
                ON d.id_juguete = j.id_juguete
            WHERE d.id_pedido = ?
            ORDER BY d.id_juguete
        """, id_pedido)
        return cursor.fetchall()
    finally:
        conn.close()
        

def eliminar_pedido(id_pedido: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT stock_descontado
            FROM Pedido
            WHERE id_pedido = ?
        """, id_pedido)
        pedido = cursor.fetchone()

        if not pedido:
            raise ValueError("Pedido no encontrado")

        if bool(pedido.stock_descontado):
            cursor.execute("""
                SELECT id_juguete, cantidad
                FROM DetallePedido
                WHERE id_pedido = ?
            """, id_pedido)
            detalles = cursor.fetchall()

            for d in detalles:
                cursor.execute("""
                    UPDATE Juguete
                    SET stock = stock + ?
                    WHERE id_juguete = ?
                """, d.cantidad, d.id_juguete)

        cursor.execute("DELETE FROM DetallePedido WHERE id_pedido = ?", id_pedido)
        cursor.execute("DELETE FROM Pedido WHERE id_pedido = ?", id_pedido)

        conn.commit()
    finally:
        conn.close()

def actualizar_estado_pedido(id_pedido: int, nuevo_estado: str):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Pedido
            SET estado = ?
            WHERE id_pedido = ?
        """, nuevo_estado, id_pedido)
        conn.commit()
    finally:
        conn.close()        

# =========================================================
# ESQUEMA OPERATIVO EXTENDIDO
# =========================================================
def _columna_existe(cursor, tabla: str, columna: str) -> bool:
    cursor.execute("""
        SELECT COUNT(*)
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ? AND COLUMN_NAME = ?
    """, tabla, columna)
    return int(cursor.fetchone()[0] or 0) > 0


def inicializar_esquema_operativo() -> None:
    """Crea tablas ligeras necesarias para proveedores, entradas, ventas y Mercado Pago.

    Es idempotente. Si SQL Server no estÃ¡ disponible, el sistema sigue arrancando y
    el diagnÃ³stico mostrarÃ¡ el error.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
        IF OBJECT_ID('Proveedor', 'U') IS NULL
        BEGIN
            CREATE TABLE Proveedor (
                id_proveedor INT IDENTITY(1,1) PRIMARY KEY,
                nombre NVARCHAR(150) NOT NULL,
                telefono NVARCHAR(20) NULL,
                correo NVARCHAR(150) NULL,
                empresa NVARCHAR(150) NULL,
                notas NVARCHAR(MAX) NULL,
                activo BIT NOT NULL DEFAULT 1,
                fecha_registro DATETIME NOT NULL DEFAULT GETDATE()
            );
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('EntradaInventario', 'U') IS NULL
        BEGIN
            CREATE TABLE EntradaInventario (
                id_entrada INT IDENTITY(1,1) PRIMARY KEY,
                id_proveedor INT NULL,
                fecha_entrada DATETIME NOT NULL DEFAULT GETDATE(),
                total_costo DECIMAL(18,2) NOT NULL DEFAULT 0,
                observaciones NVARCHAR(MAX) NULL,
                usuario_registro NVARCHAR(100) NULL,
                CONSTRAINT FK_EntradaInventario_Proveedor FOREIGN KEY (id_proveedor)
                    REFERENCES Proveedor(id_proveedor)
            );
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('DetalleEntradaInventario', 'U') IS NULL
        BEGIN
            CREATE TABLE DetalleEntradaInventario (
                id_detalle_entrada INT IDENTITY(1,1) PRIMARY KEY,
                id_entrada INT NOT NULL,
                id_juguete INT NOT NULL,
                cantidad INT NOT NULL,
                costo_unitario DECIMAL(18,2) NOT NULL DEFAULT 0,
                subtotal DECIMAL(18,2) NOT NULL DEFAULT 0,
                CONSTRAINT FK_DetalleEntrada_Entrada FOREIGN KEY (id_entrada)
                    REFERENCES EntradaInventario(id_entrada),
                CONSTRAINT FK_DetalleEntrada_Juguete FOREIGN KEY (id_juguete)
                    REFERENCES Juguete(id_juguete),
                CONSTRAINT CK_DetalleEntrada_Cantidad CHECK (cantidad > 0),
                CONSTRAINT CK_DetalleEntrada_Costo CHECK (costo_unitario >= 0)
            );
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('NotificacionSistema', 'U') IS NULL
        BEGIN
            CREATE TABLE NotificacionSistema (
                id_notificacion INT IDENTITY(1,1) PRIMARY KEY,
                tipo NVARCHAR(50) NOT NULL,
                titulo NVARCHAR(150) NOT NULL,
                mensaje NVARCHAR(MAX) NOT NULL,
                leida BIT NOT NULL DEFAULT 0,
                fecha_creacion DATETIME NOT NULL DEFAULT GETDATE()
            );
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('PagoMercadoPago', 'U') IS NULL
        BEGIN
            CREATE TABLE PagoMercadoPago (
                id_pago_mp INT IDENTITY(1,1) PRIMARY KEY,
                id_pedido INT NOT NULL,
                preference_id NVARCHAR(120) NULL,
                payment_id NVARCHAR(120) NULL,
                status NVARCHAR(50) NULL,
                status_detail NVARCHAR(120) NULL,
                init_point NVARCHAR(MAX) NULL,
                sandbox_init_point NVARCHAR(MAX) NULL,
                raw_json NVARCHAR(MAX) NULL,
                fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
                fecha_actualizacion DATETIME NULL,
                CONSTRAINT FK_PagoMP_Pedido FOREIGN KEY (id_pedido)
                    REFERENCES Pedido(id_pedido)
            );
        END
        """)

        for columna, ddl in [
            ('precio_compra', "ALTER TABLE Juguete ADD precio_compra DECIMAL(18,2) NOT NULL CONSTRAINT DF_Juguete_precio_compra DEFAULT 0"),
        ]:
            if not _columna_existe(cursor, 'Juguete', columna):
                cursor.execute(ddl)

        for columna, ddl in [
            ('costo_unitario', "ALTER TABLE DetallePedido ADD costo_unitario DECIMAL(18,2) NOT NULL CONSTRAINT DF_DetallePedido_costo_unitario DEFAULT 0"),
        ]:
            if not _columna_existe(cursor, 'DetallePedido', columna):
                cursor.execute(ddl)

        for columna, ddl in [
            ('stock_descontado', "ALTER TABLE Pedido ADD stock_descontado BIT NOT NULL CONSTRAINT DF_Pedido_stock_descontado DEFAULT 0"),
            ('fecha_entregado', "ALTER TABLE Pedido ADD fecha_entregado DATETIME NULL"),
            ('observaciones', "ALTER TABLE Pedido ADD observaciones NVARCHAR(MAX) NULL"),
            ('estado_pago', "ALTER TABLE Pedido ADD estado_pago NVARCHAR(50) NULL"),
            ('mercadopago_preference_id', "ALTER TABLE Pedido ADD mercadopago_preference_id NVARCHAR(120) NULL"),
            ('mercadopago_init_point', "ALTER TABLE Pedido ADD mercadopago_init_point NVARCHAR(MAX) NULL"),
            ('costo_envio', "ALTER TABLE Pedido ADD costo_envio DECIMAL(18,2) NOT NULL CONSTRAINT DF_Pedido_costo_envio DEFAULT 0"),
            ('metodo_pago', "ALTER TABLE Pedido ADD metodo_pago NVARCHAR(50) NULL"),
            ('canal_venta', "ALTER TABLE Pedido ADD canal_venta NVARCHAR(50) NULL"),
            ('id_expo', "ALTER TABLE Pedido ADD id_expo INT NULL"),
            ('id_corte', "ALTER TABLE Pedido ADD id_corte INT NULL"),
        ]:
            if not _columna_existe(cursor, 'Pedido', columna):
                cursor.execute(ddl)

        cursor.execute("""
        IF EXISTS (
            SELECT 1
            FROM sys.columns
            WHERE object_id = OBJECT_ID('MemoriaCliente')
              AND name = 'notas_cliente'
              AND max_length <> -1
        )
        BEGIN
            ALTER TABLE MemoriaCliente ALTER COLUMN notas_cliente NVARCHAR(MAX) NULL;
        END
        """)

        if not _columna_existe(cursor, 'Juguete', 'id_proveedor'):
            cursor.execute("ALTER TABLE Juguete ADD id_proveedor INT NULL")
        if not _columna_existe(cursor, 'Juguete', 'foto_url'):
            cursor.execute("ALTER TABLE Juguete ADD foto_url NVARCHAR(MAX) NULL")
        if not _columna_existe(cursor, 'Juguete', 'foto_local'):
            cursor.execute("ALTER TABLE Juguete ADD foto_local NVARCHAR(MAX) NULL")
        cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.foreign_keys WHERE name = 'FK_Juguete_Proveedor'
        )
        BEGIN
            ALTER TABLE Juguete
            ADD CONSTRAINT FK_Juguete_Proveedor FOREIGN KEY (id_proveedor)
            REFERENCES Proveedor(id_proveedor);
        END
        """)

        if not _columna_existe(cursor, 'Juguete', 'codigo_barras'):
            cursor.execute("ALTER TABLE Juguete ADD codigo_barras NVARCHAR(80) NULL")
        cursor.execute("""
        IF NOT EXISTS (
            SELECT 1 FROM sys.indexes
            WHERE name = 'UX_Juguete_codigo_barras'
              AND object_id = OBJECT_ID('Juguete')
        )
        BEGIN
            CREATE UNIQUE INDEX UX_Juguete_codigo_barras
            ON Juguete(codigo_barras)
            WHERE codigo_barras IS NOT NULL AND codigo_barras <> '';
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('UsuarioPanel', 'U') IS NULL
        BEGIN
            CREATE TABLE UsuarioPanel (
                id_usuario INT IDENTITY(1,1) PRIMARY KEY,
                usuario NVARCHAR(80) NOT NULL UNIQUE,
                password_hash NVARCHAR(128) NOT NULL,
                nombre NVARCHAR(150) NULL,
                rol NVARCHAR(30) NOT NULL,
                activo BIT NOT NULL DEFAULT 1,
                fecha_creacion DATETIME NOT NULL DEFAULT GETDATE(),
                ultimo_acceso DATETIME NULL
            );
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('CorteCaja', 'U') IS NULL
        BEGIN
            CREATE TABLE CorteCaja (
                id_corte INT IDENTITY(1,1) PRIMARY KEY,
                fecha_apertura DATETIME NOT NULL DEFAULT GETDATE(),
                fecha_cierre DATETIME NULL,
                usuario_apertura NVARCHAR(100) NULL,
                usuario_cierre NVARCHAR(100) NULL,
                monto_inicial DECIMAL(18,2) NOT NULL DEFAULT 0,
                ventas_efectivo DECIMAL(18,2) NOT NULL DEFAULT 0,
                ventas_online DECIMAL(18,2) NOT NULL DEFAULT 0,
                ventas_total DECIMAL(18,2) NOT NULL DEFAULT 0,
                efectivo_esperado DECIMAL(18,2) NOT NULL DEFAULT 0,
                efectivo_contado DECIMAL(18,2) NULL,
                diferencia DECIMAL(18,2) NULL,
                observaciones NVARCHAR(MAX) NULL,
                estado NVARCHAR(20) NOT NULL DEFAULT 'Abierto'
            );
        END
        """)

        cursor.execute("""
        IF OBJECT_ID('FacturaCFDI', 'U') IS NULL
        BEGIN
            CREATE TABLE FacturaCFDI (
                id_factura INT IDENTITY(1,1) PRIMARY KEY,
                id_pedido INT NOT NULL,
                rfc NVARCHAR(13) NOT NULL,
                razon_social NVARCHAR(250) NOT NULL,
                regimen_fiscal NVARCHAR(10) NULL,
                uso_cfdi NVARCHAR(10) NULL,
                codigo_postal NVARCHAR(10) NULL,
                correo NVARCHAR(150) NULL,
                estado NVARCHAR(30) NOT NULL DEFAULT 'Solicitada',
                uuid NVARCHAR(80) NULL,
                notas NVARCHAR(MAX) NULL,
                fecha_solicitud DATETIME NOT NULL DEFAULT GETDATE(),
                fecha_timbrado DATETIME NULL,
                CONSTRAINT FK_FacturaCFDI_Pedido FOREIGN KEY (id_pedido) REFERENCES Pedido(id_pedido)
            );
        END
        """)

        conn.commit()
        conn.close()
        app_logger.info("Esquema operativo validado correctamente")
    except Exception as e:
        error_logger.exception("No se pudo inicializar esquema operativo extendido")


@app.on_event("startup")
def startup_inicializar_esquema():
    inicializar_esquema_operativo()


def registrar_notificacion(tipo: str, titulo: str, mensaje: str) -> None:
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO NotificacionSistema (tipo, titulo, mensaje)
            VALUES (?, ?, ?)
        """, tipo, titulo, mensaje)
        conn.commit()
        conn.close()
    except Exception:
        error_logger.exception("No se pudo registrar notificaciÃ³n interna")


def obtener_productos_bajo_stock(limite: Optional[int] = None):
    limite = STOCK_BAJO_UMBRAL if limite is None else int(limite)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 30
                j.id_juguete,
                j.nombre,
                j.stock,
                j.precio,
                c.nombre AS categoria
            FROM Juguete j
            LEFT JOIN Categoria c ON j.id_categoria = c.id_categoria
            WHERE ISNULL(j.stock, 0) <= ?
            ORDER BY j.stock ASC, j.nombre ASC
        """, limite)
        return cursor.fetchall()
    finally:
        conn.close()


def obtener_ventas_grafica(dias: int = 14):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            ;WITH Dias AS (
                SELECT CAST(DATEADD(day, -?, CAST(GETDATE() AS DATE)) AS DATE) AS fecha
                UNION ALL
                SELECT DATEADD(day, 1, fecha)
                FROM Dias
                WHERE fecha < CAST(GETDATE() AS DATE)
            )
            SELECT
                CONVERT(VARCHAR(10), d.fecha, 120) AS fecha,
                ISNULL(SUM(CASE WHEN p.estado = 'Entregado' THEN p.total ELSE 0 END), 0) AS total,
                ISNULL(SUM(CASE WHEN p.estado = 'Entregado' THEN (ISNULL(dp.precio_unitario,0) - ISNULL(dp.costo_unitario,0)) * ISNULL(dp.cantidad,0) ELSE 0 END), 0) AS ganancia,
                COUNT(DISTINCT CASE WHEN p.estado = 'Entregado' THEN p.id_pedido END) AS pedidos
            FROM Dias d
            LEFT JOIN Pedido p ON CAST(p.fecha_entregado AS DATE) = d.fecha
            LEFT JOIN DetallePedido dp ON p.id_pedido = dp.id_pedido
            GROUP BY d.fecha
            ORDER BY d.fecha
            OPTION (MAXRECURSION 100)
        """, max(1, dias - 1))
        return [{"fecha": r.fecha, "total": float(r.total or 0), "ganancia": float(r.ganancia or 0), "pedidos": int(r.pedidos or 0)} for r in cursor.fetchall()]
    finally:
        conn.close()


def obtener_proveedores():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_proveedor, nombre, telefono, correo, empresa, activo, fecha_registro
            FROM Proveedor
            ORDER BY activo DESC, nombre ASC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def obtener_proveedor_por_id(id_proveedor: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_proveedor, nombre, telefono, correo, empresa, notas, activo
            FROM Proveedor
            WHERE id_proveedor = ?
        """, id_proveedor)
        return cursor.fetchone()
    finally:
        conn.close()


def validar_telefono_mexicano_panel(telefono: str) -> bool:
    t = re.sub(r"\s+", "", telefono or "")
    return bool(re.fullmatch(r"(\+52)?\d{10}", t))


def validar_correo_simple(correo: str) -> bool:
    if not correo:
        return True
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", correo.strip()))


def obtener_entradas_inventario():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                e.id_entrada,
                e.fecha_entrada,
                e.total_costo,
                e.observaciones,
                p.nombre AS proveedor,
                COUNT(d.id_detalle_entrada) AS productos,
                ISNULL(SUM(d.cantidad), 0) AS piezas
            FROM EntradaInventario e
            LEFT JOIN Proveedor p ON e.id_proveedor = p.id_proveedor
            LEFT JOIN DetalleEntradaInventario d ON e.id_entrada = d.id_entrada
            GROUP BY e.id_entrada, e.fecha_entrada, e.total_costo, e.observaciones, p.nombre
            ORDER BY e.id_entrada DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def obtener_entrada_por_id(id_entrada: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT e.id_entrada, e.fecha_entrada, e.total_costo, e.observaciones, p.nombre AS proveedor
            FROM EntradaInventario e
            LEFT JOIN Proveedor p ON e.id_proveedor = p.id_proveedor
            WHERE e.id_entrada = ?
        """, id_entrada)
        entrada = cursor.fetchone()
        cursor.execute("""
            SELECT d.id_juguete, j.nombre AS juguete, d.cantidad, d.costo_unitario, d.subtotal
            FROM DetalleEntradaInventario d
            INNER JOIN Juguete j ON d.id_juguete = j.id_juguete
            WHERE d.id_entrada = ?
            ORDER BY j.nombre
        """, id_entrada)
        detalles = cursor.fetchall()
        return entrada, detalles
    finally:
        conn.close()


def crear_entrada_inventario(id_proveedor: Optional[int], observaciones: str, items_json: str, usuario: str = "panel"):
    try:
        items = json.loads(items_json or "[]")
    except Exception:
        raise ValueError("Formato invÃ¡lido de productos de entrada.")
    items_validos = []
    total = 0.0
    for item in items:
        id_juguete = int(item.get("id_juguete") or 0)
        cantidad = int(item.get("cantidad") or 0)
        costo = float(item.get("costo_unitario") or 0)
        if id_juguete <= 0 or cantidad <= 0 or costo < 0:
            continue
        subtotal = round(cantidad * costo, 2)
        total += subtotal
        items_validos.append((id_juguete, cantidad, costo, subtotal))
    if not items_validos:
        raise ValueError("Debes agregar al menos un producto vÃ¡lido con cantidad mayor a cero.")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        for id_juguete, cantidad, costo, subtotal in items_validos:
            cursor.execute("SELECT nombre, precio FROM Juguete WHERE id_juguete = ?", id_juguete)
            juguete_validacion = cursor.fetchone()
            if not juguete_validacion:
                raise ValueError(f"El producto #{id_juguete} no existe.")
            if float(costo) > float(juguete_validacion.precio or 0):
                raise ValueError(f"El costo de compra de {juguete_validacion.nombre} no puede ser mayor que su precio de venta (${float(juguete_validacion.precio or 0):.2f}).")

        cursor.execute("""
            INSERT INTO EntradaInventario (id_proveedor, total_costo, observaciones, usuario_registro)
            OUTPUT INSERTED.id_entrada
            VALUES (?, ?, ?, ?)
        """, id_proveedor, round(total, 2), observaciones or None, usuario)
        id_entrada = int(cursor.fetchone()[0])
        for id_juguete, cantidad, costo, subtotal in items_validos:
            cursor.execute("""
                INSERT INTO DetalleEntradaInventario (id_entrada, id_juguete, cantidad, costo_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?)
            """, id_entrada, id_juguete, cantidad, costo, subtotal)
            cursor.execute("""
                UPDATE Juguete
                SET stock = ISNULL(stock, 0) + ?,
                    precio_compra = ?
                WHERE id_juguete = ?
            """, cantidad, costo, id_juguete)
        conn.commit()
        registrar_notificacion("inventario", "Entrada de inventario", f"Se registrÃ³ la entrada #{id_entrada} por ${total:.2f}.")
        return id_entrada
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_ventas_entregadas(estado: Optional[str] = None):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id_pedido,
                c.nombre AS cliente,
                c.telefono,
                p.fecha_pedido,
                p.fecha_entregado,
                p.estado,
                p.metodo_entrega,
                ISNULL(p.costo_envio,0) AS costo_envio,
                p.total,
                p.estado_pago,
                ISNULL(SUM((ISNULL(d.precio_unitario,0) - ISNULL(d.costo_unitario,0)) * ISNULL(d.cantidad,0)),0) AS ganancia
            FROM Pedido p
            INNER JOIN Cliente c ON p.id_cliente = c.id_cliente
            LEFT JOIN DetallePedido d ON p.id_pedido = d.id_pedido
            WHERE p.estado = 'Entregado'
            GROUP BY p.id_pedido, c.nombre, c.telefono, p.fecha_pedido, p.fecha_entregado, p.estado, p.metodo_entrega, p.costo_envio, p.total, p.estado_pago
            ORDER BY p.fecha_entregado DESC, p.id_pedido DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()



def obtener_pagos_panel():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                p.id_pedido,
                c.nombre AS cliente,
                p.total,
                p.metodo_pago,
                p.estado_pago,
                p.mercadopago_init_point,
                mp.preference_id,
                mp.payment_id,
                mp.status,
                mp.status_detail,
                mp.fecha_creacion,
                mp.fecha_actualizacion
            FROM Pedido p
            INNER JOIN Cliente c ON p.id_cliente = c.id_cliente
            OUTER APPLY (
                SELECT TOP 1 *
                FROM PagoMercadoPago x
                WHERE x.id_pedido = p.id_pedido
                ORDER BY ISNULL(x.fecha_actualizacion, x.fecha_creacion) DESC, x.id_pago_mp DESC
            ) mp
            WHERE p.metodo_pago = 'Pago en lÃ­nea'
               OR p.estado_pago IN ('pendiente_online','link_generado','pagado','approved','pending','in_process','rejected')
               OR p.mercadopago_preference_id IS NOT NULL
            ORDER BY p.id_pedido DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()

def generar_texto_ticket(id_pedido: int) -> str:
    pedido = obtener_pedido_por_id(id_pedido)
    detalles = obtener_detalles_pedido(id_pedido)
    if not pedido:
        raise ValueError("Pedido no encontrado")
    if pedido.estado != "Entregado":
        raise ValueError("Solo se pueden imprimir tickets de ventas entregadas")
    lineas = [
        "ROBLES OUTLET",
        "Ticket de venta",
        f"Folio: #{pedido.id_pedido}",
        f"Fecha: {pedido.fecha_entregado or pedido.fecha_pedido}",
        f"Cliente: {pedido.cliente}",
        f"TelÃ©fono: {pedido.telefono}",
        "-" * 32,
    ]
    for d in detalles:
        lineas.append(f"{d.juguete}")
        lineas.append(f"  {int(d.cantidad)} x ${float(d.precio_unitario):.2f} = ${float(d.subtotal):.2f}")
    if float(getattr(pedido, "costo_envio", 0) or 0) > 0:
        lineas.append(f"EnvÃ­o a domicilio: ${float(pedido.costo_envio):.2f}")
    lineas.extend(["-" * 32, f"TOTAL: ${float(pedido.total or 0):.2f}", "Gracias por tu compra."])
    return "\n".join(lineas)


def crear_preferencia_mercadopago(id_pedido: int):
    if mercadopago is None:
        raise RuntimeError("La dependencia mercadopago no estÃ¡ instalada. Ejecuta: pip install mercadopago")
    if not MERCADOPAGO_ACCESS_TOKEN:
        raise RuntimeError("Falta MERCADOPAGO_ACCESS_TOKEN en .env")
    pedido = obtener_pedido_por_id(id_pedido)
    detalles = obtener_detalles_pedido(id_pedido)
    if not pedido or not detalles:
        raise RuntimeError("Pedido no encontrado o sin detalle")
    sdk = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)
    items = []
    for d in detalles:
        items.append({
            "title": str(d.juguete),
            "quantity": int(d.cantidad),
            "unit_price": float(d.precio_unitario),
            "currency_id": "MXN",
        })
    if float(getattr(pedido, "costo_envio", 0) or 0) > 0:
        items.append({
            "title": "EnvÃ­o a domicilio",
            "quantity": 1,
            "unit_price": float(pedido.costo_envio),
            "currency_id": "MXN",
        })
    base = PUBLIC_BASE_URL or "http://127.0.0.1:8000"
    preference_data = {
        "items": items,
        "external_reference": str(id_pedido),
        "notification_url": f"{base}/mercadopago/webhook",
        "back_urls": {
            "success": f"{base}/pago/success/{id_pedido}",
            "failure": f"{base}/pago/failure/{id_pedido}",
            "pending": f"{base}/pago/pending/{id_pedido}",
        },
        "metadata": {"id_pedido": id_pedido},
        "payer": {"name": str(pedido.cliente), "phone": {"number": str(pedido.telefono)}},
    }
    result = sdk.preference().create(preference_data)
    if result.get("status", 500) >= 300:
        raise RuntimeError(f"Mercado Pago rechazÃ³ la preferencia: {result}")
    pref = result["response"]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Pedido
            SET mercadopago_preference_id = ?, mercadopago_init_point = ?, estado_pago = ISNULL(estado_pago, 'link_generado')
            WHERE id_pedido = ?
        """, pref.get("id"), pref.get("init_point"), id_pedido)
        cursor.execute("""
            INSERT INTO PagoMercadoPago (id_pedido, preference_id, status, init_point, sandbox_init_point, raw_json)
            VALUES (?, ?, ?, ?, ?, ?)
        """, id_pedido, pref.get("id"), "preference_created", pref.get("init_point"), pref.get("sandbox_init_point"), json.dumps(pref, ensure_ascii=False))
        conn.commit()
    finally:
        conn.close()
    return pref


def actualizar_pago_mercadopago_desde_webhook(payload: dict, query_params: dict):
    if mercadopago is None or not MERCADOPAGO_ACCESS_TOKEN:
        return
    payment_id = None
    if isinstance(payload, dict):
        data = payload.get("data") or {}
        payment_id = data.get("id") or payload.get("id")
    payment_id = payment_id or query_params.get("data.id") or query_params.get("id")
    if not payment_id:
        return
    sdk = mercadopago.SDK(MERCADOPAGO_ACCESS_TOKEN)
    result = sdk.payment().get(str(payment_id))
    if result.get("status", 500) >= 300:
        error_logger.error("Mercado Pago payment get fallÃ³: %s", result)
        return
    pago = result.get("response", {})
    external_reference = pago.get("external_reference") or (pago.get("metadata") or {}).get("id_pedido")
    if not external_reference:
        return
    id_pedido = int(external_reference)
    status = pago.get("status")
    status_detail = pago.get("status_detail")
    estado_pago = "pagado" if status == "approved" else status
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Pedido SET estado_pago = ? WHERE id_pedido = ?", estado_pago, id_pedido)
        cursor.execute("""
            INSERT INTO PagoMercadoPago (id_pedido, payment_id, status, status_detail, raw_json, fecha_actualizacion)
            VALUES (?, ?, ?, ?, ?, GETDATE())
        """, id_pedido, str(payment_id), status, status_detail, json.dumps(pago, ensure_ascii=False))
        conn.commit()
        if estado_pago == "pagado":
            registrar_notificacion("pago", "Pago confirmado", f"Mercado Pago confirmÃ³ el pago del pedido #{id_pedido}.")
    finally:
        conn.close()

# =========================================================
# OPERACIÃ“N COMERCIAL: USUARIOS, VENTAS MANUALES, CORTES,
# RESPALDOS, CFDI Y CÃ“DIGOS DE BARRAS
# =========================================================
ROLES_PANEL = {
    "admin": "Administrador general",
    "vendedor": "Ventas manuales y pedidos",
    "caja": "Caja, cortes y ventas",
    "pedidos": "Pedidos del bot",
    "lectura": "Solo lectura",
}


def hash_password_panel(password: str) -> str:
    return hashlib.sha256((password or "").encode("utf-8")).hexdigest()


def validar_codigo_barras_unico(codigo_barras: str, id_juguete: Optional[int] = None) -> None:
    codigo = (codigo_barras or "").strip()
    if not codigo:
        return
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if id_juguete:
            cursor.execute("SELECT COUNT(*) FROM Juguete WHERE codigo_barras = ? AND id_juguete <> ?", codigo, id_juguete)
        else:
            cursor.execute("SELECT COUNT(*) FROM Juguete WHERE codigo_barras = ?", codigo)
        if int(cursor.fetchone()[0] or 0) > 0:
            raise ValueError(f"El cÃ³digo de barras {codigo} ya estÃ¡ asignado a otro producto.")
    finally:
        conn.close()


def producto_to_dict(p) -> dict:
    if not p:
        return {}
    return {
        "id_juguete": int(p.id_juguete),
        "nombre": str(p.nombre),
        "descripcion": str(getattr(p, "descripcion", "") or ""),
        "precio": float(getattr(p, "precio", 0) or 0),
        "precio_compra": float(getattr(p, "precio_compra", 0) or 0),
        "stock": int(getattr(p, "stock", 0) or 0),
        "categoria": str(getattr(p, "categoria", "") or ""),
        "codigo_barras": str(getattr(p, "codigo_barras", "") or ""),
        "foto_url": str(getattr(p, "foto_url", "") or getattr(p, "foto_local", "") or ""),
        "imagen_publica": url_publica_archivo(str(getattr(p, "foto_url", "") or getattr(p, "foto_local", "") or "")) or "",
        "sku": str(getattr(p, "sku", "") or ""),
    }


def buscar_producto_por_codigo(codigo: str):
    codigo = (codigo or "").strip()
    if not codigo:
        return None
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1
                j.id_juguete, j.nombre, j.descripcion, j.precio,
                ISNULL(j.precio_compra, 0) AS precio_compra,
                j.stock, j.sku, j.codigo_barras, j.foto_url, j.foto_local, c.nombre AS categoria
            FROM Juguete j
            INNER JOIN Categoria c ON j.id_categoria = c.id_categoria
            WHERE j.codigo_barras = ?
        """, codigo)
        return cursor.fetchone()
    finally:
        conn.close()


def buscar_productos_panel(q: str, limite: int = 12) -> list:
    q = (q or "").strip()
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if q:
            patron = f"%{q}%"
            cursor.execute("""
                SELECT TOP (?)
                    j.id_juguete, j.nombre, j.descripcion, j.precio,
                    ISNULL(j.precio_compra,0) AS precio_compra,
                    j.stock, j.sku, j.codigo_barras, j.foto_url, j.foto_local, c.nombre AS categoria
                FROM Juguete j
                INNER JOIN Categoria c ON j.id_categoria = c.id_categoria
                WHERE j.nombre LIKE ? OR j.sku LIKE ? OR j.codigo_barras LIKE ?
                ORDER BY j.nombre
            """, limite, patron, patron, patron)
        else:
            cursor.execute("""
                SELECT TOP (?)
                    j.id_juguete, j.nombre, j.descripcion, j.precio,
                    ISNULL(j.precio_compra,0) AS precio_compra,
                    j.stock, j.sku, j.codigo_barras, j.foto_url, j.foto_local, c.nombre AS categoria
                FROM Juguete j
                INNER JOIN Categoria c ON j.id_categoria = c.id_categoria
                WHERE ISNULL(j.stock,0) > 0
                ORDER BY j.nombre
            """, limite)
        return [producto_to_dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def obtener_o_crear_cliente_mostrador(nombre: str = "Venta mostrador") -> int:
    telefono = "MOSTRADOR"
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id_cliente FROM Cliente WHERE telefono = ?", telefono)
        row = cursor.fetchone()
        if row:
            return int(row.id_cliente)
        cursor.execute("""
            INSERT INTO Cliente (nombre, telefono, ciudad)
            OUTPUT INSERTED.id_cliente
            VALUES (?, ?, ?)
        """, nombre or "Venta mostrador", telefono, "Mostrador")
        id_cliente = int(cursor.fetchone()[0])
        conn.commit()
        return id_cliente
    finally:
        conn.close()


def crear_venta_manual(items_json: str, metodo_pago: str, canal_venta: str, usuario: str, id_expo: Optional[int] = None, cliente_nombre: str = "Venta mostrador") -> int:
    try:
        items = json.loads(items_json or "[]")
    except Exception:
        raise ValueError("Formato invÃ¡lido de productos para venta.")
    if not isinstance(items, list) or not items:
        raise ValueError("Debes agregar al menos un producto a la venta.")

    acumulados = {}
    for item in items:
        id_juguete = int(item.get("id_juguete") or 0)
        cantidad = int(item.get("cantidad") or 0)
        if id_juguete <= 0 or cantidad <= 0:
            continue
        acumulados[id_juguete] = acumulados.get(id_juguete, 0) + cantidad
    if not acumulados:
        raise ValueError("No hay cantidades vÃ¡lidas para vender.")

    id_cliente = obtener_o_crear_cliente_mostrador(cliente_nombre)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        detalles = []
        total = 0.0
        for id_juguete, cantidad in acumulados.items():
            cursor.execute("""
                SELECT id_juguete, nombre, precio, ISNULL(precio_compra,0) AS precio_compra, ISNULL(stock,0) AS stock
                FROM Juguete
                WHERE id_juguete = ?
            """, id_juguete)
            prod = cursor.fetchone()
            if not prod:
                raise ValueError(f"El producto #{id_juguete} no existe.")
            if int(prod.stock or 0) < cantidad:
                raise ValueError(f"Stock insuficiente de {prod.nombre}. Disponible: {int(prod.stock or 0)}.")
            precio = float(prod.precio or 0)
            costo = float(prod.precio_compra or 0)
            subtotal = round(precio * cantidad, 2)
            total += subtotal
            detalles.append((id_juguete, cantidad, precio, costo, subtotal))

        estado_pago = "pagado_efectivo" if metodo_pago == "Efectivo" else "pendiente_online"
        cursor.execute("""
            INSERT INTO Pedido (
                id_cliente, estado, metodo_entrega, subtotal, total,
                observaciones, costo_envio, metodo_pago, estado_pago,
                stock_descontado, fecha_entregado, canal_venta, id_expo
            )
            OUTPUT INSERTED.id_pedido
            VALUES (?, 'Entregado', ?, ?, ?, ?, 0, ?, ?, 1, GETDATE(), ?, ?)
        """, id_cliente, canal_venta, round(total, 2), round(total, 2), f"Venta manual registrada por {usuario}", metodo_pago, estado_pago, canal_venta, id_expo)
        id_pedido = int(cursor.fetchone()[0])
        for id_juguete, cantidad, precio, costo, subtotal in detalles:
            cursor.execute("""
                INSERT INTO DetallePedido (id_pedido, id_juguete, cantidad, precio_unitario, costo_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, id_pedido, id_juguete, cantidad, precio, costo, subtotal)
            cursor.execute("UPDATE Juguete SET stock = ISNULL(stock,0) - ? WHERE id_juguete = ?", cantidad, id_juguete)
        conn.commit()
        registrar_notificacion("venta", "Venta manual", f"Se registrÃ³ venta manual #{id_pedido} por ${total:.2f}.")
        return id_pedido
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def obtener_usuarios_panel():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_usuario, usuario, nombre, rol, activo, fecha_creacion, ultimo_acceso
            FROM UsuarioPanel
            ORDER BY activo DESC, usuario ASC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def crear_usuario_panel_db(usuario: str, password: str, nombre: str, rol: str) -> None:
    usuario = (usuario or "").strip()
    if rol not in ROLES_PANEL:
        raise ValueError("Rol no vÃ¡lido.")
    if not usuario or not password:
        raise ValueError("Usuario y contraseÃ±a son obligatorios.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO UsuarioPanel (usuario, password_hash, nombre, rol, activo)
            VALUES (?, ?, ?, ?, 1)
        """, usuario, hash_password_panel(password), nombre or usuario, rol)
        conn.commit()
    finally:
        conn.close()


def cambiar_estado_usuario_panel(id_usuario: int, activo: bool) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE UsuarioPanel SET activo = ? WHERE id_usuario = ?", 1 if activo else 0, id_usuario)
        conn.commit()
    finally:
        conn.close()


def obtener_cortes_caja():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 100 *
            FROM CorteCaja
            ORDER BY id_corte DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def calcular_totales_corte_desde(fecha_inicio: Optional[str] = None) -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        filtro = "p.estado = 'Entregado'"
        params = []
        if fecha_inicio:
            filtro += " AND p.fecha_entregado >= ?"
            params.append(fecha_inicio)
        cursor.execute(f"""
            SELECT
                ISNULL(SUM(CASE WHEN p.metodo_pago = 'Efectivo' THEN p.total ELSE 0 END),0) AS efectivo,
                ISNULL(SUM(CASE WHEN p.metodo_pago <> 'Efectivo' OR p.metodo_pago IS NULL THEN p.total ELSE 0 END),0) AS online,
                ISNULL(SUM(p.total),0) AS total,
                COUNT(*) AS ventas
            FROM Pedido p
            WHERE {filtro}
        """, *params)
        r = cursor.fetchone()
        return {"efectivo": float(r.efectivo or 0), "online": float(r.online or 0), "total": float(r.total or 0), "ventas": int(r.ventas or 0)}
    finally:
        conn.close()


def cerrar_corte_caja(usuario: str, monto_inicial: float, efectivo_contado: float, observaciones: str) -> int:
    totales = calcular_totales_corte_desde(datetime.now().strftime("%Y-%m-%d 00:00:00"))
    efectivo_esperado = round(float(monto_inicial or 0) + totales["efectivo"], 2)
    diferencia = round(float(efectivo_contado or 0) - efectivo_esperado, 2)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO CorteCaja (
                fecha_cierre, usuario_apertura, usuario_cierre, monto_inicial,
                ventas_efectivo, ventas_online, ventas_total, efectivo_esperado,
                efectivo_contado, diferencia, observaciones, estado
            )
            OUTPUT INSERTED.id_corte
            VALUES (GETDATE(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Cerrado')
        """, usuario, usuario, monto_inicial, totales["efectivo"], totales["online"], totales["total"], efectivo_esperado, efectivo_contado, diferencia, observaciones or None)
        id_corte = int(cursor.fetchone()[0])
        conn.commit()
        return id_corte
    finally:
        conn.close()


def carpeta_backups() -> Path:
    path = RUNTIME_DIR / "backups"
    path.mkdir(exist_ok=True)
    return path


def listar_respaldos():
    bdir = carpeta_backups()
    return sorted([p for p in bdir.glob("*.bak")], key=lambda x: x.stat().st_mtime, reverse=True)


def crear_respaldo_sql() -> Path:
    bdir = carpeta_backups()
    nombre = f"{DB_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"
    destino = bdir / nombre
    conn = get_master_connection()
    try:
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"BACKUP DATABASE [{DB_NAME}] TO DISK = ? WITH INIT, FORMAT", str(destino))
        return destino
    finally:
        conn.close()


def restaurar_respaldo_sql(nombre_archivo: str) -> None:
    backup = (carpeta_backups() / Path(nombre_archivo).name).resolve()
    if not backup.exists() or backup.suffix.lower() != ".bak":
        raise ValueError("Respaldo no encontrado.")
    conn = get_master_connection()
    try:
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"ALTER DATABASE [{DB_NAME}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        cursor.execute(f"RESTORE DATABASE [{DB_NAME}] FROM DISK = ? WITH REPLACE", str(backup))
        cursor.execute(f"ALTER DATABASE [{DB_NAME}] SET MULTI_USER")
    finally:
        conn.close()


def obtener_facturas_cfdi():
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.*, p.total, c.nombre AS cliente
            FROM FacturaCFDI f
            INNER JOIN Pedido p ON f.id_pedido = p.id_pedido
            INNER JOIN Cliente c ON p.id_cliente = c.id_cliente
            ORDER BY f.id_factura DESC
        """)
        return cursor.fetchall()
    finally:
        conn.close()


def crear_solicitud_cfdi(id_pedido: int, rfc: str, razon_social: str, regimen_fiscal: str, uso_cfdi: str, codigo_postal: str, correo: str, notas: str) -> None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM Pedido WHERE id_pedido = ?", id_pedido)
        if int(cursor.fetchone()[0] or 0) == 0:
            raise ValueError("El pedido no existe.")
        cursor.execute("""
            INSERT INTO FacturaCFDI (id_pedido, rfc, razon_social, regimen_fiscal, uso_cfdi, codigo_postal, correo, notas)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, id_pedido, rfc.strip().upper(), razon_social.strip(), regimen_fiscal.strip() or None, uso_cfdi.strip() or None, codigo_postal.strip() or None, correo.strip() or None, notas.strip() or None)
        conn.commit()
    finally:
        conn.close()


# =========================================================
# PANEL ADMIN - AUTENTICACIÃ“N
# =========================================================
def validar_usuario_panel(usuario: str, password: str) -> Optional[str]:
    usuario = (usuario or "").strip()
    password = (password or "").strip()

    # Primero valida usuarios comerciales guardados en base de datos.
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id_usuario, rol, password_hash, activo
            FROM UsuarioPanel
            WHERE usuario = ?
        """, usuario)
        row = cursor.fetchone()
        if row and int(row.activo or 0) == 1 and row.password_hash == hash_password_panel(password):
            cursor.execute("UPDATE UsuarioPanel SET ultimo_acceso = GETDATE() WHERE id_usuario = ?", row.id_usuario)
            conn.commit()
            conn.close()
            return str(row.rol)
        conn.close()
    except Exception:
        # Si la tabla aÃºn no existe o SQL falla, conserva compatibilidad con usuarios .env.
        pass

    if usuario == PANEL_ADMIN_USER and password == PANEL_ADMIN_PASSWORD:
        return "admin"
    if usuario == PANEL_PEDIDOS_USER and password == PANEL_PEDIDOS_PASSWORD:
        return "pedidos"
    if usuario == PANEL_READONLY_USER and password == PANEL_READONLY_PASSWORD:
        return "lectura"
    return None

@app.get("/panel/login", response_class=HTMLResponse)
def panel_login_form(request: Request):
    return render_template(request, "login.html", error=None)

@app.post("/panel/login")
def panel_login(request: Request, usuario: str = Form(...), password: str = Form(...)):
    rol = validar_usuario_panel(usuario, password)
    if not rol:
        return render_template(request, "login.html", error="Usuario o contraseÃ±a incorrectos.")

    request.session["usuario_panel"] = usuario.strip()
    request.session["rol_panel"] = rol
    destino = "/panel/pedidos" if rol == "pedidos" else "/panel"
    return RedirectResponse(url=destino, status_code=303)

@app.get("/panel/logout")
def panel_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/panel/login", status_code=303)


@app.get("/diagnostico")
def diagnostico_publico():
    return {"env": validar_env_basico(), "sql": diagnostico_sql(), "openai": diagnostico_openai(), "nota": "Meta se valida en /panel/diagnostico para evitar exponer detalles en ruta pÃºblica."}

@app.get("/panel/diagnostico", response_class=HTMLResponse)
def panel_diagnostico(request: Request):
    return render_template(request, "diagnostico.html", env=validar_env_basico(), sql=diagnostico_sql(), meta=diagnostico_meta(), openai=diagnostico_openai())

# =========================================================
# PANEL ADMIN - VISTAS
# =========================================================
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "Error de validaciÃ³n en formulario",
            "detalle": exc.errors()
        }
    )

@app.get("/panel", response_class=HTMLResponse)
def panel_dashboard(request: Request):
    return render_template(request, "dashboard.html", metricas=obtener_metricas_dashboard())

# -------------------------
# JUGUETES
# -------------------------
@app.get("/panel/juguetes", response_class=HTMLResponse)
def panel_juguetes(request: Request):
    return render_template(
        request,
        "juguetes.html",
        juguetes=obtener_juguetes()
    )

@app.get("/panel/juguetes/nuevo", response_class=HTMLResponse)
def panel_nuevo_juguete(request: Request):
    return render_template(
        request,
        "juguete_form.html",
        categorias=obtener_categorias(),
        proveedores=obtener_proveedores(),
        juguete=None,
        accion="Crear",
        error=None
    )

@app.post("/panel/juguetes/nuevo")
def panel_guardar_juguete(
    request: Request,
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio_compra: float = Form(0),
    precio: float = Form(...),
    stock: int = Form(...),
    edad_minima: int = Form(...),
    edad_maxima: int = Form(...),
    marca: str = Form(...),
    sku: str = Form(...),
    codigo_barras: str = Form(""),
    id_proveedor: Optional[int] = Form(None),
    foto_url: str = Form(""),
    foto_producto: UploadFile = File(None),
    id_categoria: int = Form(...)
):
    if precio_compra < 0 or precio < 0 or stock < 0:
        raise HTTPException(status_code=400, detail="Precio de compra, precio de venta y stock no pueden ser negativos.")
    if precio_compra > precio:
        raise HTTPException(status_code=400, detail="El precio de compra no puede ser mayor que el precio de venta.")
    try:
        validar_codigo_barras_unico(codigo_barras)
    except ValueError as e:
        return render_template(request, "juguete_form.html", categorias=obtener_categorias(), proveedores=obtener_proveedores(), juguete=None, accion="Crear", error=str(e))
    try:
        foto_local = guardar_foto_producto_upload(foto_producto, nombre)
    except ValueError as e:
        return render_template(request, "juguete_form.html", categorias=obtener_categorias(), proveedores=obtener_proveedores(), juguete=None, accion="Crear", error=str(e))
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Juguete
            (nombre, descripcion, precio_compra, precio, stock, edad_minima, edad_maxima, marca, sku, codigo_barras, id_proveedor, foto_url, foto_local, id_categoria)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, nombre, descripcion, precio_compra, precio, stock, edad_minima, edad_maxima, marca, sku, codigo_barras.strip() or None, id_proveedor or None, foto_url.strip() or None, foto_local, id_categoria)
        conn.commit()
        return RedirectResponse(url="/panel/juguetes", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL guardar juguete: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/juguetes/editar/{id_juguete}", response_class=HTMLResponse)
def panel_editar_juguete(request: Request, id_juguete: int):
    return render_template(
        request,
        "juguete_form.html",
        categorias=obtener_categorias(),
        proveedores=obtener_proveedores(),
        juguete=obtener_juguete_por_id(id_juguete),
        accion="Editar",
        error=None
    )

@app.post("/panel/juguetes/editar/{id_juguete}")
def panel_actualizar_juguete(
    request: Request,
    id_juguete: int,
    nombre: str = Form(...),
    descripcion: str = Form(...),
    precio_compra: float = Form(0),
    precio: float = Form(...),
    stock: int = Form(...),
    edad_minima: int = Form(...),
    edad_maxima: int = Form(...),
    marca: str = Form(...),
    sku: str = Form(...),
    codigo_barras: str = Form(""),
    id_proveedor: Optional[int] = Form(None),
    foto_url: str = Form(""),
    foto_producto: UploadFile = File(None),
    id_categoria: int = Form(...)
):
    if precio_compra < 0 or precio < 0 or stock < 0:
        raise HTTPException(status_code=400, detail="Precio de compra, precio de venta y stock no pueden ser negativos.")
    if precio_compra > precio:
        raise HTTPException(status_code=400, detail="El precio de compra no puede ser mayor que el precio de venta.")
    try:
        validar_codigo_barras_unico(codigo_barras, id_juguete)
    except ValueError as e:
        return render_template(request, "juguete_form.html", categorias=obtener_categorias(), proveedores=obtener_proveedores(), juguete=obtener_juguete_por_id(id_juguete), accion="Editar", error=str(e))
    juguete_actual = obtener_juguete_por_id(id_juguete)
    try:
        foto_local_nueva = guardar_foto_producto_upload(foto_producto, nombre)
    except ValueError as e:
        return render_template(request, "juguete_form.html", categorias=obtener_categorias(), proveedores=obtener_proveedores(), juguete=juguete_actual, accion="Editar", error=str(e))
    foto_local_final = foto_local_nueva or getattr(juguete_actual, "foto_local", None)
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Juguete
            SET nombre = ?,
                descripcion = ?,
                precio_compra = ?,
                precio = ?,
                stock = ?,
                edad_minima = ?,
                edad_maxima = ?,
                marca = ?,
                sku = ?,
                codigo_barras = ?,
                id_proveedor = ?,
                foto_url = ?,
                foto_local = ?,
                id_categoria = ?
            WHERE id_juguete = ?
        """, nombre, descripcion, precio_compra, precio, stock, edad_minima, edad_maxima, marca, sku, codigo_barras.strip() or None, id_proveedor or None, foto_url.strip() or None, foto_local_final, id_categoria, id_juguete)
        conn.commit()
        return RedirectResponse(url="/panel/juguetes", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL actualizar juguete: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/juguetes/eliminar/{id_juguete}")
def panel_eliminar_juguete(id_juguete: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM JugueteEtiqueta WHERE id_juguete = ?", id_juguete)
        cursor.execute("DELETE FROM Juguete WHERE id_juguete = ?", id_juguete)
        conn.commit()
        return RedirectResponse(url="/panel/juguetes", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL eliminar juguete: {str(e)}")

    finally:
        conn.close()

# -------------------------
# EXPOS
# -------------------------
@app.get("/panel/expos", response_class=HTMLResponse)
def panel_expos(request: Request):
    return render_template(
        request,
        "expos.html",
        expos=obtener_expos_admin()
    )

@app.get("/panel/expos/nuevo", response_class=HTMLResponse)
def panel_nueva_expo(request: Request):
    return render_template(
        request,
        "expo_form.html",
        expo=None,
        accion="Crear"
    )

@app.post("/panel/expos/nuevo")
def panel_guardar_expo(
    nombre: str = Form(...),
    ubicacion: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...)
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Expo (nombre, ubicacion, fecha_inicio, fecha_fin)
            VALUES (?, ?, ?, ?)
        """, nombre, ubicacion, fecha_inicio, fecha_fin)
        conn.commit()
        return RedirectResponse(url="/panel/expos", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL guardar expo: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/expos/editar/{id_expo}", response_class=HTMLResponse)
def panel_editar_expo(request: Request, id_expo: int):
    return render_template(
        request,
        "expo_form.html",
        expo=obtener_expo_por_id(id_expo),
        accion="Editar"
    )

@app.post("/panel/expos/editar/{id_expo}")
def panel_actualizar_expo(
    id_expo: int,
    nombre: str = Form(...),
    ubicacion: str = Form(...),
    fecha_inicio: str = Form(...),
    fecha_fin: str = Form(...)
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Expo
            SET nombre = ?, ubicacion = ?, fecha_inicio = ?, fecha_fin = ?
            WHERE id_expo = ?
        """, nombre, ubicacion, fecha_inicio, fecha_fin, id_expo)
        conn.commit()
        return RedirectResponse(url="/panel/expos", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL actualizar expo: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/expos/eliminar/{id_expo}")
def panel_eliminar_expo(id_expo: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Expo WHERE id_expo = ?", id_expo)
        conn.commit()
        return RedirectResponse(url="/panel/expos", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL eliminar expo: {str(e)}")

    finally:
        conn.close()

# -------------------------
# CLIENTES
# -------------------------
@app.get("/panel/clientes", response_class=HTMLResponse)
def panel_clientes(request: Request):
    return render_template(
        request,
        "clientes.html",
        clientes=obtener_clientes()
    )

@app.get("/panel/clientes/nuevo", response_class=HTMLResponse)
def panel_nuevo_cliente(request: Request):
    return render_template(
        request,
        "cliente_form.html",
        cliente=None,
        accion="Crear"
    )

@app.post("/panel/clientes/nuevo")
def panel_guardar_cliente(
    nombre: str = Form(...),
    telefono: str = Form(...),
    ciudad: str = Form(...)
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Cliente (nombre, telefono, ciudad)
            VALUES (?, ?, ?)
        """, nombre, telefono, ciudad)
        conn.commit()
        return RedirectResponse(url="/panel/clientes", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL guardar cliente: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/clientes/editar/{id_cliente}", response_class=HTMLResponse)
def panel_editar_cliente(request: Request, id_cliente: int):
    return render_template(
        request,
        "cliente_form.html",
        cliente=obtener_cliente_por_id(id_cliente),
        accion="Editar"
    )

@app.post("/panel/clientes/editar/{id_cliente}")
def panel_actualizar_cliente(
    id_cliente: int,
    nombre: str = Form(...),
    telefono: str = Form(...),
    ciudad: str = Form(...)
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Cliente
            SET nombre = ?, telefono = ?, ciudad = ?
            WHERE id_cliente = ?
        """, nombre, telefono, ciudad, id_cliente)
        conn.commit()
        return RedirectResponse(url="/panel/clientes", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL actualizar cliente: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/clientes/eliminar/{id_cliente}")
def panel_eliminar_cliente(id_cliente: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM ConsultaCliente WHERE id_cliente = ?", id_cliente)
        cursor.execute("DELETE FROM Cliente WHERE id_cliente = ?", id_cliente)
        conn.commit()
        return RedirectResponse(url="/panel/clientes", status_code=303)

    except pyodbc.Error as e:
        raise HTTPException(status_code=500, detail=f"SQL eliminar cliente: {str(e)}")

    finally:
        conn.close()

@app.get("/panel/clientes/{id_cliente}/consultas", response_class=HTMLResponse)
def panel_historial_cliente(request: Request, id_cliente: int):
    return render_template(
        request,
        "cliente_consultas.html",
        cliente=obtener_cliente_por_id(id_cliente),
        consultas=obtener_consultas_por_cliente(id_cliente)
    )


# -------------------------
# PROVEEDORES
# -------------------------
@app.get("/panel/proveedores", response_class=HTMLResponse)
def panel_proveedores(request: Request):
    return render_template(request, "proveedores.html", proveedores=obtener_proveedores())

@app.get("/panel/proveedores/nuevo", response_class=HTMLResponse)
def panel_nuevo_proveedor(request: Request):
    return render_template(request, "proveedor_form.html", proveedor=None, accion="Crear", error=None)

@app.post("/panel/proveedores/nuevo")
def panel_guardar_proveedor(
    request: Request,
    nombre: str = Form(...),
    telefono: str = Form(""),
    correo: str = Form(""),
    empresa: str = Form(""),
    notas: str = Form("")
):
    if telefono and not validar_telefono_mexicano_panel(telefono):
        return render_template(request, "proveedor_form.html", proveedor=None, accion="Crear", error="TelÃ©fono invÃ¡lido. Usa 10 dÃ­gitos o +52 seguido de 10 dÃ­gitos.")
    if not validar_correo_simple(correo):
        return render_template(request, "proveedor_form.html", proveedor=None, accion="Crear", error="Correo invÃ¡lido.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Proveedor (nombre, telefono, correo, empresa, notas)
            VALUES (?, ?, ?, ?, ?)
        """, nombre.strip(), telefono.strip() or None, correo.strip() or None, empresa.strip() or None, notas.strip() or None)
        conn.commit()
        return RedirectResponse(url="/panel/proveedores", status_code=303)
    finally:
        conn.close()

@app.get("/panel/proveedores/editar/{id_proveedor}", response_class=HTMLResponse)
def panel_editar_proveedor(request: Request, id_proveedor: int):
    proveedor = obtener_proveedor_por_id(id_proveedor)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    return render_template(request, "proveedor_form.html", proveedor=proveedor, accion="Editar", error=None)

@app.post("/panel/proveedores/editar/{id_proveedor}")
def panel_actualizar_proveedor(
    request: Request,
    id_proveedor: int,
    nombre: str = Form(...),
    telefono: str = Form(""),
    correo: str = Form(""),
    empresa: str = Form(""),
    notas: str = Form(""),
    activo: Optional[str] = Form(None)
):
    proveedor = obtener_proveedor_por_id(id_proveedor)
    if not proveedor:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado")
    if telefono and not validar_telefono_mexicano_panel(telefono):
        return render_template(request, "proveedor_form.html", proveedor=proveedor, accion="Editar", error="TelÃ©fono invÃ¡lido. Usa 10 dÃ­gitos o +52 seguido de 10 dÃ­gitos.")
    if not validar_correo_simple(correo):
        return render_template(request, "proveedor_form.html", proveedor=proveedor, accion="Editar", error="Correo invÃ¡lido.")
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Proveedor
            SET nombre = ?, telefono = ?, correo = ?, empresa = ?, notas = ?, activo = ?
            WHERE id_proveedor = ?
        """, nombre.strip(), telefono.strip() or None, correo.strip() or None, empresa.strip() or None, notas.strip() or None, 1 if activo else 0, id_proveedor)
        conn.commit()
        return RedirectResponse(url="/panel/proveedores", status_code=303)
    finally:
        conn.close()

@app.get("/panel/proveedores/eliminar/{id_proveedor}")
def panel_eliminar_proveedor(id_proveedor: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE Proveedor SET activo = 0 WHERE id_proveedor = ?", id_proveedor)
        conn.commit()
        return RedirectResponse(url="/panel/proveedores", status_code=303)
    finally:
        conn.close()

# -------------------------
# ENTRADAS DE INVENTARIO
# -------------------------
@app.get("/panel/entradas", response_class=HTMLResponse)
def panel_entradas(request: Request):
    return render_template(request, "entradas.html", entradas=obtener_entradas_inventario())

@app.get("/panel/entradas/nueva", response_class=HTMLResponse)
def panel_nueva_entrada(request: Request):
    return render_template(request, "entrada_form.html", proveedores=obtener_proveedores(), juguetes=obtener_juguetes(), error=None)

@app.post("/panel/entradas/nueva")
def panel_guardar_entrada(
    request: Request,
    id_proveedor: Optional[int] = Form(None),
    observaciones: str = Form(""),
    items_json: str = Form("[]")
):
    try:
        usuario = request.session.get("usuario_panel", "panel")
        crear_entrada_inventario(id_proveedor, observaciones, items_json, usuario)
        return RedirectResponse(url="/panel/entradas", status_code=303)
    except Exception as e:
        return render_template(request, "entrada_form.html", proveedores=obtener_proveedores(), juguetes=obtener_juguetes(), error=str(e))

@app.get("/panel/entradas/{id_entrada}", response_class=HTMLResponse)
def panel_detalle_entrada(request: Request, id_entrada: int):
    entrada, detalles = obtener_entrada_por_id(id_entrada)
    if not entrada:
        raise HTTPException(status_code=404, detail="Entrada no encontrada")
    return render_template(request, "entrada_detalle.html", entrada=entrada, detalles=detalles)

# -------------------------
# VENTAS
# -------------------------
@app.get("/panel/ventas", response_class=HTMLResponse)
def panel_ventas(request: Request):
    return render_template(request, "ventas.html", ventas=obtener_ventas_entregadas(), grafica=obtener_ventas_grafica(30))

@app.get("/panel/pagos", response_class=HTMLResponse)
def panel_pagos(request: Request):
    return render_template(request, "pagos.html", pagos=obtener_pagos_panel())

@app.get("/api/productos/codigo/{codigo}")
def api_producto_por_codigo(codigo: str):
    producto = buscar_producto_por_codigo(codigo)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado con ese cÃ³digo de barras.")
    return producto_to_dict(producto)

@app.get("/api/productos/buscar")
def api_productos_buscar(q: str = ""):
    return {"productos": buscar_productos_panel(q)}

@app.get("/panel/ventas/manual", response_class=HTMLResponse)
def panel_venta_manual(request: Request):
    return render_template(request, "venta_manual.html", juguetes=obtener_juguetes(), expos=obtener_expos_admin(), error=None)

@app.post("/panel/ventas/manual")
def panel_guardar_venta_manual(
    request: Request,
    items_json: str = Form("[]"),
    metodo_pago: str = Form("Efectivo"),
    canal_venta: str = Form("Mostrador"),
    id_expo: Optional[int] = Form(None),
    cliente_nombre: str = Form("Venta mostrador")
):
    try:
        usuario = request.session.get("usuario_panel", "panel")
        id_pedido = crear_venta_manual(items_json, metodo_pago, canal_venta, usuario, id_expo, cliente_nombre)
        return RedirectResponse(url=f"/panel/pedidos/ticket/{id_pedido}", status_code=303)
    except Exception as e:
        return render_template(request, "venta_manual.html", juguetes=obtener_juguetes(), expos=obtener_expos_admin(), error=str(e))

@app.get("/panel/cortes", response_class=HTMLResponse)
def panel_cortes(request: Request):
    return render_template(request, "cortes.html", cortes=obtener_cortes_caja(), totales=calcular_totales_corte_desde(datetime.now().strftime("%Y-%m-%d 00:00:00")), error=None)

@app.post("/panel/cortes/cerrar")
def panel_cerrar_corte(request: Request, monto_inicial: float = Form(0), efectivo_contado: float = Form(0), observaciones: str = Form("")):
    try:
        usuario = request.session.get("usuario_panel", "panel")
        cerrar_corte_caja(usuario, monto_inicial, efectivo_contado, observaciones)
        return RedirectResponse(url="/panel/cortes", status_code=303)
    except Exception as e:
        return render_template(request, "cortes.html", cortes=obtener_cortes_caja(), totales=calcular_totales_corte_desde(datetime.now().strftime("%Y-%m-%d 00:00:00")), error=str(e))

@app.get("/panel/usuarios", response_class=HTMLResponse)
def panel_usuarios(request: Request):
    return render_template(request, "usuarios.html", usuarios=obtener_usuarios_panel(), roles=ROLES_PANEL, error=None)

@app.post("/panel/usuarios/nuevo")
def panel_usuario_nuevo(request: Request, usuario: str = Form(...), password: str = Form(...), nombre: str = Form(""), rol: str = Form("vendedor")):
    try:
        crear_usuario_panel_db(usuario, password, nombre, rol)
        return RedirectResponse(url="/panel/usuarios", status_code=303)
    except Exception as e:
        return render_template(request, "usuarios.html", usuarios=obtener_usuarios_panel(), roles=ROLES_PANEL, error=str(e))

@app.get("/panel/usuarios/desactivar/{id_usuario}")
def panel_usuario_desactivar(id_usuario: int):
    cambiar_estado_usuario_panel(id_usuario, False)
    return RedirectResponse(url="/panel/usuarios", status_code=303)

@app.get("/panel/usuarios/activar/{id_usuario}")
def panel_usuario_activar(id_usuario: int):
    cambiar_estado_usuario_panel(id_usuario, True)
    return RedirectResponse(url="/panel/usuarios", status_code=303)

@app.get("/panel/respaldo", response_class=HTMLResponse)
def panel_respaldo(request: Request):
    return render_template(request, "respaldo.html", respaldos=listar_respaldos(), mensaje=None, error=None)

@app.post("/panel/respaldo/crear")
def panel_respaldo_crear(request: Request):
    try:
        archivo = crear_respaldo_sql()
        return render_template(request, "respaldo.html", respaldos=listar_respaldos(), mensaje=f"Respaldo creado: {archivo.name}", error=None)
    except Exception as e:
        return render_template(request, "respaldo.html", respaldos=listar_respaldos(), mensaje=None, error=str(e))

@app.post("/panel/respaldo/restaurar")
def panel_respaldo_restaurar(request: Request, archivo: str = Form(...)):
    try:
        restaurar_respaldo_sql(archivo)
        return render_template(request, "respaldo.html", respaldos=listar_respaldos(), mensaje=f"Base restaurada desde: {archivo}", error=None)
    except Exception as e:
        return render_template(request, "respaldo.html", respaldos=listar_respaldos(), mensaje=None, error=str(e))

@app.get("/panel/cfdi", response_class=HTMLResponse)
def panel_cfdi(request: Request):
    return render_template(request, "cfdi.html", facturas=obtener_facturas_cfdi(), ventas=obtener_ventas_entregadas(), error=None)

@app.post("/panel/cfdi/nuevo")
def panel_cfdi_nuevo(
    request: Request,
    id_pedido: int = Form(...),
    rfc: str = Form(...),
    razon_social: str = Form(...),
    regimen_fiscal: str = Form(""),
    uso_cfdi: str = Form(""),
    codigo_postal: str = Form(""),
    correo: str = Form(""),
    notas: str = Form("")
):
    try:
        crear_solicitud_cfdi(id_pedido, rfc, razon_social, regimen_fiscal, uso_cfdi, codigo_postal, correo, notas)
        return RedirectResponse(url="/panel/cfdi", status_code=303)
    except Exception as e:
        return render_template(request, "cfdi.html", facturas=obtener_facturas_cfdi(), ventas=obtener_ventas_entregadas(), error=str(e))

# -------------------------
# CONSULTAS
# -------------------------
@app.get("/panel/consultas", response_class=HTMLResponse)
def panel_consultas(request: Request):
    return render_template(
        request,
        "consultas.html",
        consultas=obtener_consultas()
    )
    


@app.get("/panel/pedidos", response_class=HTMLResponse)
def panel_pedidos(request: Request, estado: Optional[str] = None):
    estados = ["Pendiente", "Confirmado", "En preparaciÃ³n", "Entregado", "Cancelado"]
    estado_filtrado = estado if estado in estados else None
    return render_template(request, "pedidos.html", pedidos=obtener_pedidos(estado_filtrado), estados=estados, estado_actual=estado_filtrado)

@app.get("/panel/pedidos/entregar/{id_pedido}")
def panel_entregar_pedido(id_pedido: int):
    try:
        marcar_pedido_entregado(id_pedido)
        return RedirectResponse(url="/panel/pedidos", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al entregar pedido: {str(e)}")

@app.get("/panel/pedidos/estado/{id_pedido}/{nuevo_estado}")
def panel_cambiar_estado_pedido(id_pedido: int, nuevo_estado: str):
    permitidos = {"Pendiente", "Confirmado", "En preparaciÃ³n", "Cancelado"}
    nuevo_estado = nuevo_estado.replace("_", " ")
    if nuevo_estado not in permitidos:
        raise HTTPException(status_code=400, detail="Estado no permitido")
    actualizar_estado_pedido(id_pedido, nuevo_estado)
    return RedirectResponse(url="/panel/pedidos", status_code=303)


@app.get("/panel/pedidos/ticket/{id_pedido}", response_class=HTMLResponse)
def panel_ticket_pedido(request: Request, id_pedido: int):
    pedido = obtener_pedido_por_id(id_pedido)
    detalles = obtener_detalles_pedido(id_pedido)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    if pedido.estado != "Entregado":
        raise HTTPException(status_code=400, detail="Solo se imprimen tickets de ventas entregadas")
    return render_template(request, "ticket.html", pedido=pedido, detalles=detalles, ticket_texto=generar_texto_ticket(id_pedido))

@app.get("/panel/pedidos/mercadopago/{id_pedido}")
def panel_generar_pago_mp(id_pedido: int):
    try:
        pref = crear_preferencia_mercadopago(id_pedido)
        return RedirectResponse(url=pref.get("init_point") or pref.get("sandbox_init_point") or "/panel/pedidos", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo generar link de Mercado Pago: {str(e)}")

@app.post("/mercadopago/webhook")
async def mercadopago_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    actualizar_pago_mercadopago_desde_webhook(payload, dict(request.query_params))
    return {"ok": True}

@app.get("/pago/{resultado}/{id_pedido}", response_class=HTMLResponse)
def pago_resultado(request: Request, resultado: str, id_pedido: int):
    return render_template(request, "pago_resultado.html", resultado=resultado, id_pedido=id_pedido)

@app.get("/panel/pedidos/{id_pedido}", response_class=HTMLResponse)
def panel_detalle_pedido(request: Request, id_pedido: int):
    pedido = obtener_pedido_por_id(id_pedido)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    detalles = obtener_detalles_pedido(id_pedido)

    return render_template(
        request,
        "pedido_detalle.html",
        pedido=pedido,
        detalles=detalles
    )

@app.get("/panel/pedidos/editar/{id_pedido}", response_class=HTMLResponse)
def panel_editar_pedido(request: Request, id_pedido: int):
    pedido = obtener_pedido_por_id(id_pedido)
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    return render_template(
        request,
        "pedido_form.html",
        pedido=pedido
    )

@app.post("/panel/pedidos/editar/{id_pedido}")
def panel_actualizar_pedido(
    id_pedido: int,
    estado: str = Form(...),
    metodo_entrega: str = Form(...),
    direccion_entrega: str = Form(""),
    referencia_entrega: str = Form(""),
    observaciones: str = Form("")
):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE Pedido
            SET
                estado = ?,
                metodo_entrega = ?,
                direccion_entrega = ?,
                referencia_entrega = ?,
                observaciones = ?
            WHERE id_pedido = ?
        """,
            estado,
            metodo_entrega,
            direccion_entrega if direccion_entrega.strip() else None,
            referencia_entrega if referencia_entrega.strip() else None,
            observaciones if observaciones.strip() else None,
            id_pedido
        )
        conn.commit()
        return RedirectResponse(url="/panel/pedidos", status_code=303)
    finally:
        conn.close()

@app.get("/panel/pedidos/eliminar/{id_pedido}")
def panel_eliminar_pedido(id_pedido: int):
    try:
        eliminar_pedido(id_pedido)
        return RedirectResponse(url="/panel/pedidos", status_code=303)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar pedido: {str(e)}")    

