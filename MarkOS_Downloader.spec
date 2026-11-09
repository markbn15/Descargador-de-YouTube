# -*- mode: python ; coding: utf-8 -*-
"""
MarkOS_Downloader.spec
====================================================================
PyInstaller 6.x - UN SOLO EXE (onefile) + modo ventana (sin consola).

Genera:
    dist/MarkOS Downloader Suite.exe

Incluye dentro del ejecutable:
    bin/yt-dlp.exe      -> obligatorio (lo exige build.bat)
    bin/ffmpeg.exe      -> opcional
    bin/ffprobe.exe     -> opcional

Los assets (banner, instrucciones e icono PNG) NO viajan como datas:
estan incrustados en utils/assets_embedded.py por tools/build_assets.py.
Por eso datas=[] por defecto y el EXE no depende de ninguna carpeta externa.

Compilar:
    pyinstaller --noconfirm --clean MarkOS_Downloader.spec
"""

from __future__ import annotations

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

# ----------------------------------------------------------------------
# Configuracion del build
# ----------------------------------------------------------------------
# El EXE ya trae bin/yt-dlp.exe, que es el motor real. Incluir ademas el
# paquete Python yt_dlp duplica ~15 MB y no aporta nada en produccion.
# Ponlo en True solo si quieres invocar yt_dlp como modulo Python.
INCLUIR_MODULO_YT_DLP = False

# build.bat noffmpeg define esta variable para que el spec NO empaquete
# ffmpeg/ffprobe aunque ya existan en bin/ de una compilacion anterior.
SIN_FFMPEG = os.environ.get("MARKOS_SIN_FFMPEG") == "1"

# Excluir FFmpeg para un EXE minimo (build.bat noffmpeg). Se detecta solo.
PROYECTO = Path(SPECPATH).resolve()
BIN = PROYECTO / "bin"
ASSETS = PROYECTO / "assets"
ICONO = ASSETS / "icon.ico"

# ----------------------------------------------------------------------
# Binarios embebidos (destino dentro de sys._MEIPASS: "bin")
# ----------------------------------------------------------------------
binaries = []
for nombre in ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe"):
    if SIN_FFMPEG and nombre != "yt-dlp.exe":
        continue
    origen = BIN / nombre
    if origen.is_file():
        binaries.append((str(origen), "bin"))
    elif nombre == "yt-dlp.exe":
        raise SystemExit(
            "[spec] Falta bin/yt-dlp.exe. Ejecuta build.bat o "
            "python tools/descargar_binarios.py antes de compilar."
        )

if not ICONO.is_file():
    raise SystemExit(
        "[spec] Falta assets/icon.ico. Ejecuta python tools/make_icon.py."
    )

# ----------------------------------------------------------------------
# hiddenimports
# ----------------------------------------------------------------------
hiddenimports = [
    # Modulos Qt realmente usados (el hook de PySide6 solo arrastra estos).
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
]

# Datos que viajan como datas (vacio por defecto: todo va incrustado).
datas = []

if INCLUIR_MODULO_YT_DLP:
    # Equivalente a --collect-all yt_dlp. OPCIONAL: solo si se usara el
    # paquete Python en lugar del binario.
    yt_datos, yt_binarios, yt_ocultos = collect_all("yt_dlp")
    binaries += yt_binarios
    hiddenimports += yt_ocultos
    datas += yt_datos

# ----------------------------------------------------------------------
# Exclusiones: todo lo que no usa la suite y engorda el onefile
# ----------------------------------------------------------------------
excludes = [
    # GUI alternativa que jamas se usa
    "tkinter",
    "_tkinter",
    # Pruebas y utilidades de desarrollo
    "tests",
    "test",
    "unittest",
    "pytest",
    "pydoc_data",
    "lib2to3",
    # Ciencia de datos / imagenes (no se usan)
    "numpy",
    "scipy",
    "pandas",
    "matplotlib",
    "PIL",
    "IPython",
    "jupyter",
    "notebook",
    # Empaquetado / instaladores que no deben viajar al EXE
    "setuptools",
    "pkg_resources",
    "pip",
    "wheel",
    # Modulos Qt que no se importan en ningun sitio
    "PySide6.QtNetwork",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuickWidgets",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
]

# ----------------------------------------------------------------------
# Analisis
# ----------------------------------------------------------------------
a = Analysis(
    ["main.py"],
    pathex=[str(PROYECTO)],
    binaries=binaries,
    datas=datas,           # assets incrustados en Python (ver cabecera)
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=1,            # elimina asserts/docstrings y reduce un poco
)

pyz = PYZ(a.pure)

# ----------------------------------------------------------------------
# Filtro de DLLs/plugins de Qt que el hook de PySide6 arrastra aunque no
# se importen. Sin esto el EXE pesa ~20 MB mas de lo necesario.
# Comprobado con pefile: qwindows.dll solo depende de Qt6Core/Qt6Gui.
# ----------------------------------------------------------------------
_DLL_EXACTAS = {
    "pyside6\\qt6network.dll",
    "pyside6\\qt6opengl.dll",
    "pyside6\\qt6pdf.dll",
    "pyside6\\qt6qml.dll",
    "pyside6\\qt6qmlmeta.dll",
    "pyside6\\qt6qmlmodels.dll",
    "pyside6\\qt6qmlworkerscript.dll",
    "pyside6\\qt6quick.dll",
    "pyside6\\qt6quickwidgets.dll",
    "pyside6\\qt6svg.dll",
    "pyside6\\qt6virtualkeyboard.dll",
    "pyside6\\opengl32sw.dll",
}


def _conservar_binario(destino: str) -> bool:
    ruta = destino.replace("/", "\\").lower()
    if ruta in _DLL_EXACTAS:
        return False
    if ruta.startswith("pyside6\\translations\\"):
        return False
    if ruta.startswith("pyside6\\plugins\\imageformats\\"):
        return False
    if ruta.startswith("pyside6\\plugins\\iconengines\\"):
        return False
    if ruta.startswith("pyside6\\plugins\\platforminputcontexts\\"):
        return False
    if ruta.startswith("pyside6\\plugins\\generic\\"):
        return False
    if ruta.startswith("pyside6\\plugins\\platforms\\") and not ruta.endswith(
        "qwindows.dll"
    ):
        return False
    return True


a.binaries = [entrada for entrada in a.binaries if _conservar_binario(entrada[0])]

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="MarkOS Downloader Suite",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,           # en Windows no aporta y puede romper DLLs
    upx=False,             # UPX dispara falsos positivos de antivirus
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,         # --windowed: sin consola
    disable_windowed_traceback=True,  # la app muestra sus propios errores
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICONO),
)
