# JugueteriaBot - Instalacion y ejecutable Windows

## Opcion recomendada para instalar en una PC

1. Instala Python 3.11 o superior.
2. Instala Microsoft ODBC Driver 17 for SQL Server.
3. Instala SQL Server Express o conecta el sistema a un SQL Server existente.
4. Ejecuta `instalar.bat`.
5. Copia `.env.example` como `.env` si no se creó automáticamente.
6. Edita `.env` con:
   - Token de Meta WhatsApp Cloud API.
   - Phone Number ID.
   - Servidor SQL Server.
   - Nombre de base de datos.
   - API key de OpenAI.
   - Usuarios y contraseñas del panel.
7. Ejecuta `iniciar.bat`.

El panel abre en:

```text
http://127.0.0.1:8000/panel
```

La documentación de la API abre en:

```text
http://127.0.0.1:8000/docs
```

## Crear ejecutable .exe

Ejecuta:

```bat
crear_ejecutable.bat
```

El archivo se generará en:

```text
dist\JugueteriaBot.exe
```

Dentro de `dist`, copia `.env.example` como `.env` y configura tus variables.

## Importante

El `.exe` no incluye SQL Server ni el driver ODBC. Eso debe estar instalado o disponible en la PC donde se usará el sistema.

## Requisitos externos

- Windows 10/11.
- SQL Server Express o SQL Server accesible.
- Microsoft ODBC Driver 17 for SQL Server.
- Acceso a internet si usarás WhatsApp Cloud API y OpenAI.
- Base de datos creada/actualizada con el script SQL incluido.

## Seguridad

No subas tu archivo `.env` a internet ni lo compartas. Ahí van tokens de Meta, OpenAI y claves del panel.
