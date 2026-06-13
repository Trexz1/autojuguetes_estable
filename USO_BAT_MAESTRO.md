# JugueteriaBot - BAT maestro y ejecutable

## Uso principal

Ejecuta:

```bat
MAESTRO_JUGUETERIABOT.bat
```

El BAT realiza:

1. Valida Python.
2. Crea/activa `.venv`.
3. Instala dependencias.
4. Compila `main.py` e `iniciar_jugueteriabot.py` para detectar errores antes de arrancar.
5. Genera `dist\JugueteriaBot.exe`.
6. Descarga o localiza `ngrok.exe`.
7. Copia `.env`, `.env.example` y `ngrok.exe` dentro de `dist`.
8. Arranca `JugueteriaBot.exe`.
9. El propio `JugueteriaBot.exe` abre FastAPI y ngrok.

## Ejecutar solo el EXE

Después de generado, puedes abrir directamente:

```bat
dist\JugueteriaBot.exe
```

El EXE abrirá:

- Servidor local: `http://127.0.0.1:8000/panel`
- API docs: `http://127.0.0.1:8000/docs`
- Ngrok: `http://127.0.0.1:4040`

## Requisitos externos

El EXE no instala SQL Server ni el ODBC Driver. La PC debe tener:

- SQL Server activo o conexión a un servidor SQL Server existente.
- ODBC Driver 17 o 18 para SQL Server.
- `.env` configurado correctamente.

## Error Meta 401

Si el webhook recibe mensajes pero aparece:

```text
RESPUESTA META: 401 {"error":{"message":"Authentication Error","code":190}}
```

El problema no es ngrok ni FastAPI. El error indica que `META_ACCESS_TOKEN` es inválido, vencido o no corresponde al `META_PHONE_NUMBER_ID` configurado.

Revisa en `.env`:

```env
META_ACCESS_TOKEN=PEGA_AQUI_TU_META_ACCESS_TOKEN
META_PHONE_NUMBER_ID=PEGA_AQUI_TU_PHONE_NUMBER_ID
```

Después reinicia el EXE.

## Desactivar ngrok desde el EXE

Si necesitas iniciar el EXE sin ngrok:

```bat
set JUGUETERIABOT_NGROK=0
JugueteriaBot.exe
```
