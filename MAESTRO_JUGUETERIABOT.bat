@echo off
setlocal EnableExtensions EnableDelayedExpansion
title JugueteriaBot - Instalador, EXE, Servidor y Ngrok
cd /d "%~dp0"

echo ============================================================
echo   JugueteriaBot - BAT MAESTRO
echo ============================================================
echo.

REM ============================================================
REM  CONFIGURACION PRINCIPAL
REM ============================================================
set "APP_NAME=JugueteriaBot"
set "APP_PORT=8000"
set "APP_HOST=127.0.0.1"
set "PANEL_URL=http://127.0.0.1:8000/panel"
set "NGROK_DIR=%cd%\tools\ngrok"
set "NGROK_EXE=%NGROK_DIR%\ngrok.exe"
set "NGROK_ZIP=%TEMP%\ngrok-v3-windows-amd64.zip"
set "NGROK_URL=https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip"

REM ============================================================
REM  1) VALIDAR PYTHON
REM ============================================================
echo [1/9] Validando Python...
set "PY_CMD="
where py >nul 2>nul
if not errorlevel 1 set "PY_CMD=py -3"

if not defined PY_CMD (
    where python >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    echo ERROR: Python no esta instalado o no esta en PATH.
    echo.
    echo Instala Python 3.11 o superior desde python.org.
    echo Durante la instalacion activa: Add Python to PATH.
    echo.
    pause
    exit /b 1
)

%PY_CMD% --version
if errorlevel 1 (
    echo ERROR: Python fue detectado, pero no responde correctamente.
    pause
    exit /b 1
)

REM ============================================================
REM  2) CREAR ENTORNO VIRTUAL
REM ============================================================
echo.
echo [2/9] Preparando entorno virtual .venv...
if not exist ".venv" (
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo ERROR: No se pudo activar el entorno virtual.
    pause
    exit /b 1
)

REM ============================================================
REM  3) INSTALAR DEPENDENCIAS PYTHON
REM ============================================================
echo.
echo [3/9] Instalando dependencias del proyecto...

REM Algunos equipos tienen antivirus/proxy que intercepta HTTPS y causa:
REM CERTIFICATE_VERIFY_FAILED self-signed certificate in certificate chain.
REM Por eso se usa trusted-host como respaldo. No se obliga actualizar pip
REM si ya existe una version funcional.
set "PIP_FLAGS=--trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org"

python -m pip --version
if errorlevel 1 (
    echo ERROR: pip no responde dentro del entorno virtual.
    pause
    exit /b 1
)

echo Actualizando herramientas base de Python si es posible...
python -m pip install --upgrade pip setuptools wheel %PIP_FLAGS%
if errorlevel 1 (
    echo AVISO: No se pudo actualizar pip/setuptools/wheel por SSL/red.
    echo Se continuara con las versiones ya instaladas.
)

if not exist "requirements.txt" (
    echo ERROR: No se encontro requirements.txt.
    pause
    exit /b 1
)

echo Instalando requirements.txt...
python -m pip install -r requirements.txt %PIP_FLAGS%
if errorlevel 1 (
    echo.
    echo ERROR: Fallo la instalacion de requirements.txt.
    echo Causa probable: certificado SSL interceptado por antivirus/proxy o falta de Internet.
    echo Soluciones:
    echo 1^) Revisa tu conexion.
    echo 2^) Desactiva temporalmente inspeccion HTTPS del antivirus, si aplica.
    echo 3^) Ejecuta manualmente:
    echo    .venv\Scripts\python.exe -m pip install -r requirements.txt %PIP_FLAGS%
    pause
    exit /b 1
)

echo Instalando PyInstaller...
python -m pip install pyinstaller %PIP_FLAGS%
if errorlevel 1 (
    echo.
    echo ERROR: Fallo la instalacion de PyInstaller.
    echo Ejecuta manualmente:
    echo .venv\Scripts\python.exe -m pip install pyinstaller %PIP_FLAGS%
    pause
    exit /b 1
)

REM ============================================================
REM  4) VALIDAR ARCHIVOS BASE
REM ============================================================
echo.
echo [4/9] Validando archivos principales...
if not exist "main.py" (
    echo ERROR: No se encontro main.py.
    pause
    exit /b 1
)

if not exist "iniciar_jugueteriabot.py" (
    echo ERROR: No se encontro iniciar_jugueteriabot.py.
    pause
    exit /b 1
)

if not exist "templates" (
    echo ERROR: No se encontro la carpeta templates.
    pause
    exit /b 1
)

if not exist "static" (
    echo ERROR: No se encontro la carpeta static.
    pause
    exit /b 1
)

if not exist ".env" (
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo.
        echo AVISO: Se creo .env desde .env.example.
        echo Debes configurar tus tokens de Meta/OpenAI, SQL Server y claves del panel.
        echo El sistema NO arrancara hasta que llenes .env correctamente.
        echo.
        start "Editar .env" notepad ".env"
        pause
        exit /b 1
    ) else (
        echo ERROR: No existe .env ni .env.example.
        pause
        exit /b 1
    )
)

REM ============================================================
REM  5) COMPILAR / DETECTAR ERRORES DE SINTAXIS ANTES DE ARRANCAR
REM ============================================================
echo.
echo [5/9] Compilando Python para detectar errores antes de arrancar...
python -m py_compile "main.py" "iniciar_jugueteriabot.py"
if errorlevel 1 (
    echo.
    echo ERROR: Hay errores de sintaxis en main.py o iniciar_jugueteriabot.py.
    echo Corrige esos errores antes de crear el ejecutable o iniciar el servidor.
    pause
    exit /b 1
)

if exist "scripts\validar_pre_zip.py" (
    echo Ejecutando validacion operativa pre-ZIP...
    python "scripts\validar_pre_zip.py"
    if errorlevel 1 (
        echo.
        echo ERROR: La validacion operativa fallo.
        pause
        exit /b 1
    )
)

python -m compileall -q .
if errorlevel 1 (
    echo.
    echo ERROR: Se detectaron errores compilando archivos Python del proyecto.
    pause
    exit /b 1
)

REM ============================================================
REM  6) CREAR EJECUTABLE EXE
REM ============================================================
echo.
echo [6/9] Creando ejecutable %APP_NAME%.exe...
if exist "build" rmdir /s /q "build"
if exist "dist\%APP_NAME%.exe" del /q "dist\%APP_NAME%.exe"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

pyinstaller ^
  --clean ^
  --onefile ^
  --name "%APP_NAME%" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --hidden-import main ^
  --hidden-import pyodbc ^
  --hidden-import dotenv ^
  --hidden-import rapidfuzz ^
  --hidden-import multipart ^
  --hidden-import itsdangerous ^
  --hidden-import openai ^
  "iniciar_jugueteriabot.py"

if errorlevel 1 (
    echo.
    echo ERROR: No se pudo crear el ejecutable.
    pause
    exit /b 1
)

if not exist "dist\%APP_NAME%.exe" (
    echo ERROR: PyInstaller termino, pero no se encontro dist\%APP_NAME%.exe.
    pause
    exit /b 1
)

if exist ".env" copy ".env" "dist\.env" >nul
if exist ".env.example" copy ".env.example" "dist\.env.example" >nul
if exist "ACTUALIZACION_LOGIN_AVISO_PEDIDOS.sql" copy "ACTUALIZACION_LOGIN_AVISO_PEDIDOS.sql" "dist\ACTUALIZACION_LOGIN_AVISO_PEDIDOS.sql" >nul

echo Ejecutable creado correctamente: dist\%APP_NAME%.exe

REM ============================================================
REM  7) INSTALAR / VALIDAR NGROK
REM ============================================================
echo.
echo [7/9] Validando ngrok...
set "NGROK_LOCAL_EXE=%NGROK_DIR%\ngrok.exe"
set "NGROK_RUN_CMD="

REM Primero se intenta tener ngrok local real. No se copia desde WindowsApps porque
REM el alias de Microsoft Store puede marcar "El sistema no tiene acceso al archivo".
if not exist "%NGROK_LOCAL_EXE%" (
    echo Ngrok local no encontrado. Descargando ngrok v3 para Windows x64...
    if not exist "%NGROK_DIR%" mkdir "%NGROK_DIR%"
    if exist "%NGROK_ZIP%" del /q "%NGROK_ZIP%" >nul 2>nul

    powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -Uri '%NGROK_URL%' -OutFile '%NGROK_ZIP%' -UseBasicParsing } catch { exit 1 }"
    if errorlevel 1 (
        echo AVISO: PowerShell no pudo descargar ngrok. Probando con curl -k...
        curl.exe -L -k "%NGROK_URL%" -o "%NGROK_ZIP%"
    )

    if exist "%NGROK_ZIP%" (
        powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Expand-Archive -LiteralPath '%NGROK_ZIP%' -DestinationPath '%NGROK_DIR%' -Force } catch { exit 1 }"
    )
)

if exist "%NGROK_LOCAL_EXE%" (
    set "NGROK_EXE=%NGROK_LOCAL_EXE%"
    set "NGROK_RUN_CMD=%NGROK_LOCAL_EXE%"
) else (
    where ngrok >nul 2>nul
    if not errorlevel 1 (
        set "NGROK_RUN_CMD=ngrok"
        echo AVISO: Se usara ngrok desde PATH. No se copiara el alias de WindowsApps a dist.
    ) else (
        echo ERROR: No se encontro ngrok local ni en PATH.
        echo Descargalo manualmente y coloca ngrok.exe en: tools\ngrok\ngrok.exe
        pause
        exit /b 1
    )
)

"%NGROK_RUN_CMD%" version
if errorlevel 1 (
    echo ERROR: ngrok existe, pero no responde correctamente.
    pause
    exit /b 1
)

REM Si quieres guardar el authtoken automaticamente, define NGROK_AUTHTOKEN en Windows.
if defined NGROK_AUTHTOKEN (
    "%NGROK_RUN_CMD%" config add-authtoken "%NGROK_AUTHTOKEN%"
)

REM Copiar ngrok junto al ejecutable solo cuando existe un archivo local real.
if exist "%NGROK_LOCAL_EXE%" (
    copy /Y "%NGROK_LOCAL_EXE%" "dist\ngrok.exe" >nul
    if errorlevel 1 (
        echo AVISO: No se pudo copiar ngrok.exe a dist. El EXE intentara usar ngrok desde PATH.
    )
) else (
    echo AVISO: No hay ngrok local para copiar. El EXE intentara usar ngrok desde PATH.
)

REM ============================================================
REM  8) ARRANCAR SERVIDOR + NGROK DESDE EL MISMO EXE
REM ============================================================
echo.
echo [8/9] Arrancando JugueteriaBot.exe...
echo El ejecutable abrira FastAPI y tambien ngrok automaticamente.
echo Panel local: %PANEL_URL%
echo Dashboard ngrok: http://127.0.0.1:4040
echo.
set "DIST_DIR=%cd%\dist"
start "%APP_NAME% SERVER + NGROK" /D "%DIST_DIR%" cmd /k "%APP_NAME%.exe"

REM Espera corta para que uvicorn y ngrok levanten.
timeout /t 6 /nobreak >nul

REM ============================================================
REM  9) ABRIR PANEL Y DASHBOARD
REM ============================================================
echo.
echo [9/9] Abriendo panel y dashboard ngrok...
start "Panel JugueteriaBot" "%PANEL_URL%"
start "Ngrok Dashboard" "http://127.0.0.1:4040"

echo.
echo ============================================================
echo   LISTO
echo ============================================================
echo 1) Servidor local: %PANEL_URL%
echo 2) Ngrok dashboard: http://127.0.0.1:4040
echo 3) El EXE tambien abre ngrok automaticamente
echo 4) Ejecutable generado: %cd%\dist\%APP_NAME%.exe
echo.
echo IMPORTANTE:
echo - Para WhatsApp Meta, copia la URL https de ngrok y agrega /webhook.
echo - Ejemplo: https://xxxxx.ngrok-free.app/webhook
echo - Si ngrok pide authtoken, ejecuta:
echo   ngrok config add-authtoken TU_TOKEN
echo.
pause
endlocal
