@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title MarkOS Downloader Suite - Build
cd /d "%~dp0"

echo ============================================================
echo   MarkOS Downloader Suite - compilacion (onefile)
echo   Python 3.11/3.12 + PySide6 + PyInstaller
echo ============================================================
echo.

REM ------------------------------------------------------------
REM 1) Localizar Python 3.11 o 3.12 (nunca 3.13)
REM ------------------------------------------------------------
set "PYTHON_CMD="
for %%V in (3.12 3.11) do (
    py -%%V -c "import sys" >nul 2>&1
    if not errorlevel 1 (
        if not defined PYTHON_CMD set "PYTHON_CMD=py -%%V"
    )
)
if not defined PYTHON_CMD (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in [(3,11),(3,12)] else 1)" >nul 2>&1
    if not errorlevel 1 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
    echo [ERROR] No se encontro Python 3.11 o 3.12.
    echo         Descargalo en https://www.python.org/downloads/
    echo         Marca "Add python.exe to PATH" durante la instalacion.
    goto :error
)
echo [OK] Interprete: %PYTHON_CMD%

REM ------------------------------------------------------------
REM 2) Entorno virtual aislado
REM ------------------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo [..] Creando entorno virtual .venv ...
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 goto :error
) else (
    echo [=] Reutilizando .venv
)
set "PY=.venv\Scripts\python.exe"

REM ------------------------------------------------------------
REM 3) Dependencias
REM ------------------------------------------------------------
echo [..] Actualizando pip ...
"%PY%" -m pip install --upgrade pip --disable-pip-version-check
if errorlevel 1 goto :error

echo [..] Instalando requirements.txt ...
"%PY%" -m pip install -r requirements.txt --disable-pip-version-check
if errorlevel 1 goto :error

REM ------------------------------------------------------------
REM 4) Binarios embebidos (yt-dlp + ffmpeg/ffprobe)
REM ------------------------------------------------------------
if /I "%~1"=="noffmpeg" (
    set "MARKOS_SIN_FFMPEG=1"
    echo [..] Modo sin FFmpeg: EXE mas pequeno ^(sin MP3/fusion^)
    "%PY%" tools\descargar_binarios.py --sin-ffmpeg
) else (
    echo [..] Descargando yt-dlp.exe y FFmpeg essentials ...
    "%PY%" tools\descargar_binarios.py
)
if errorlevel 1 goto :error

REM ------------------------------------------------------------
REM 5) Icono y assets incrustados
REM ------------------------------------------------------------
echo [..] Generando icono .ico/.png ...
"%PY%" tools\make_icon.py
if errorlevel 1 goto :error

echo [..] Incrustando banner, instrucciones e icono ...
"%PY%" tools\build_assets.py
if errorlevel 1 goto :error

REM ------------------------------------------------------------
REM 6) PyInstaller (onefile + windowed)
REM ------------------------------------------------------------
echo [..] Compilando. Esto puede tardar varios minutos ...
"%PY%" -m PyInstaller --noconfirm --clean MarkOS_Downloader.spec
if errorlevel 1 goto :error

REM ------------------------------------------------------------
REM 7) Resultado
REM ------------------------------------------------------------
echo.
echo ============================================================
echo   BUILD COMPLETADO
echo   dist\MarkOS Downloader Suite.exe
echo ============================================================
if exist "dist\MarkOS Downloader Suite.exe" (
    for %%F in ("dist\MarkOS Downloader Suite.exe") do (
        set /a "MB=%%~zF/1048576"
        echo   Tamano: %%~zF bytes  ^(^~!MB! MB^)
    )
) else (
    echo [ERROR] No se genero el ejecutable esperado.
    goto :error
)
echo.
echo   Prueba el EXE en un equipo limpio y revisa:
echo     %%APPDATA%%\MarkOS_Downloader\app.log
echo.
pause
exit /b 0

:error
echo.
echo [ERROR] La compilacion fallo. Revisa el mensaje anterior.
echo.
pause
exit /b 1
