# Empaquetado instalable en Windows

## Objetivo

Tener un paquete que pueda instalar dependencias, validar el proyecto, crear ejecutable y arrancar el panel sin tocar manualmente cada paso.

## Flujo con agentes

1. DevOps Automator
   - Mantiene `MAESTRO_JUGUETERIABOT.bat`.
   - Crea `.venv`.
   - Instala `requirements.txt`.
   - Compila con PyInstaller.
   - Valida ngrok.

2. Infrastructure Maintainer
   - Revisa puertos, rutas, archivos requeridos, arranque de Uvicorn y ngrok.
   - Documenta fallos comunes de Windows, Python y SQL Server.

3. Security Engineer
   - Revisa `.env`.
   - Evita secretos dentro del ZIP.
   - Valida que tokens no vayan al frontend.
   - Revisa login y roles del panel.

4. Backend Architect
   - Garantiza que el ejecutable cargue `main.py`, `templates/` y `static/`.
   - Revisa rutas y dependencias.

5. Technical Writer
   - Mantiene instrucciones para usuario final.

6. Reality Checker
   - Confirma que el paquete final sí puede instalarse y no solo está documentado.

## Comando principal

En Windows:

```bat
MAESTRO_JUGUETERIABOT.bat
```

## Recomendación de entrega

Para entregar a un cliente, copiar `.env.example` como `.env` en el equipo final y configurar ahí los tokens reales. No distribuir tokens reales en ZIP compartidos.
