# Revisión antes de entregar ZIP

## Checklist operativo

1. Ejecutar validación sintáctica:

```bash
python -m py_compile main.py iniciar_jugueteriabot.py scripts/validar_pre_zip.py
```

2. Ejecutar revisión del proyecto:

```bash
python scripts/validar_pre_zip.py
```

3. Revisar archivos sensibles:

- No subir `.env` real a entregas públicas.
- No incluir tokens de Meta, OpenAI, ngrok ni claves del panel en documentación.
- Usar `.env.example` para plantilla.

4. Revisar carpetas innecesarias:

- `.venv/`
- `build/`
- `__pycache__/`
- `.pytest_cache/`
- logs temporales

5. Confirmar archivos base:

- `main.py`
- `iniciar_jugueteriabot.py`
- `requirements.txt`
- `templates/`
- `static/`
- `MAESTRO_JUGUETERIABOT.bat`
- `.env.example`
- documentación en `docs/`
- agentes en `agents/`

## Criterio de entrega

El ZIP debe contener el sistema estable, documentación y scripts de validación; no debe contener entornos virtuales, cachés ni secretos reales.
