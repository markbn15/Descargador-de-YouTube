"""
utils/paths.py
====================================================================
Rutas centralizadas de MarkOS Downloader Suite.

Regla de oro: cuando la app corre como EXE (PyInstaller) los recursos
se resuelven dentro de sys._MEIPASS (o en la carpeta de actualizaciones
del usuario) y NUNCA desde el PATH del sistema. En modo desarrollo se
permite el fallback al PATH para poder probar sin empaquetar.

Orden de busqueda de binarios:
    1. %APPDATA%\\MarkOS_Downloader\\bin  (actualizador integrado)
    2. sys._MEIPASS\\bin                  (incluido en el EXE)
    3. PATH                               (SOLO en desarrollo)

Las rutas de trabajo son identicas a los scripts originales:
    ~/Desktop/Descargador casero/enlaces.txt
    ~/Desktop/Descargador casero/DESCARGAS
====================================================================
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

_log = logging.getLogger("markos.paths")

# ------------------------------------------------------------------
# Metadatos de la aplicacion
# ------------------------------------------------------------------
APP_NAME = "MarkOS Downloader Suite"
APP_SLUG = "MarkOS_Downloader"
# Version de la aplicacion. Se muestra como V1.7 y se compara con las
# etiquetas de GitHub tratando 1.7 como 1.70 (mayor que V1.51). Asi la
# build local queda por delante de la ultima release publicada.
APP_VERSION = "1.7"
APP_ID = "MarkOS.DownloaderSuite.1.7"

# Nombres de los ejecutables que se empaquetan en /bin
YTDLP_EXE = "yt-dlp.exe"
FFMPEG_EXE = "ffmpeg.exe"
FFPROBE_EXE = "ffprobe.exe"


# ------------------------------------------------------------------
# Deteccion de ejecucion congelada (PyInstaller)
# ------------------------------------------------------------------
def esta_congelado() -> bool:
    """True cuando corremos dentro de un EXE de PyInstaller."""
    return bool(getattr(sys, "frozen", False)) and hasattr(sys, "_MEIPASS")


def dir_base() -> Path:
    """
    Carpeta raiz de recursos.

    - Congelado: sys._MEIPASS (carpeta temporal donde PyInstaller extrae
      binarios y datos del onefile).
    - Desarrollo: la carpeta del proyecto (un nivel arriba de /utils).
    """
    if esta_congelado():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def dir_ejecutable() -> Path:
    """Carpeta donde vive el .exe (o la raiz del proyecto en desarrollo)."""
    if esta_congelado():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _primer_archivo(candidatos: list[Path]) -> Path | None:
    """Devuelve el primer archivo existente o None."""
    for candidato in candidatos:
        try:
            if candidato.is_file():
                return candidato
        except OSError:
            continue
    return None


def _buscar_en_path(nombre: str) -> Path | None:
    """
    Fallback SOLO para desarrollo: busca en el PATH del sistema.
    En el EXE congelado esto jamas se usa.
    """
    if esta_congelado():
        return None
    encontrado = shutil.which(nombre)
    return Path(encontrado) if encontrado else None


def dir_bin_usuario() -> Path:
    """
    Binarios actualizados por el usuario (actualizador integrado).

    Se guardan en %APPDATA%\\MarkOS_Downloader\\bin y tienen prioridad
    sobre los que viajan dentro del EXE. Si no existen, la app usa los
    binarios incluidos (sys._MEIPASS\\bin) sin tocar el PATH.
    """
    return dir_appdata() / "bin"


def get_ytdlp_path() -> Path | None:
    """Ruta absoluta de yt-dlp.exe (actualizado > incluido > PATH en dev)."""
    base = dir_base()
    return _primer_archivo(
        [
            dir_bin_usuario() / YTDLP_EXE,
            base / "bin" / YTDLP_EXE,
            base / YTDLP_EXE,
        ]
    ) or _buscar_en_path("yt-dlp")


def get_ffmpeg_path() -> Path | None:
    """Ruta absoluta de ffmpeg.exe (opcional, recomendado)."""
    base = dir_base()
    return _primer_archivo(
        [
            dir_bin_usuario() / FFMPEG_EXE,
            base / "bin" / FFMPEG_EXE,
            base / FFMPEG_EXE,
        ]
    ) or _buscar_en_path("ffmpeg")


def get_ffprobe_path() -> Path | None:
    """Ruta absoluta de ffprobe.exe (opcional)."""
    base = dir_base()
    return _primer_archivo(
        [
            dir_bin_usuario() / FFPROBE_EXE,
            base / "bin" / FFPROBE_EXE,
            base / FFPROBE_EXE,
        ]
    ) or _buscar_en_path("ffprobe")


def carpeta_bin() -> Path:
    """Carpeta /bin resuelta (util para --ffmpeg-location)."""
    return dir_base() / "bin"


# ------------------------------------------------------------------
# Rutas de trabajo (identicas a los scripts originales)
# ------------------------------------------------------------------
def dir_escritorio() -> Path:
    """
    Escritorio del usuario. Se mantiene la ruta original (~/Desktop);
    si no existe se intenta el Escritorio de OneDrive, habitual en
    equipos con Windows 11 + cuenta Microsoft.
    """
    home = Path(os.path.expanduser("~"))
    clasico = home / "Desktop"
    if clasico.is_dir():
        return clasico
    onedrive = os.environ.get("OneDrive")
    if onedrive:
        alterno = Path(onedrive) / "Desktop"
        if alterno.is_dir():
            return alterno
    return clasico


def dir_trabajo() -> Path:
    """Desktop/Descargador casero (misma ruta que los scripts originales)."""
    return dir_escritorio() / "Descargador casero"


def archivo_enlaces() -> Path:
    """Desktop/Descargador casero/enlaces.txt."""
    return dir_trabajo() / "enlaces.txt"


def dir_descargas() -> Path:
    """Desktop/Descargador casero/DESCARGAS."""
    return dir_trabajo() / "DESCARGAS"


def asegurar_entorno(limpiar_enlaces: bool = False) -> None:
    """
    Crea las carpetas necesarias.

    Si limpiar_enlaces=True se vacia enlaces.txt, que es exactamente lo
    que hacia setup_environment() en el interceptor original al arrancar.
    """
    dir_trabajo().mkdir(parents=True, exist_ok=True)
    dir_descargas().mkdir(parents=True, exist_ok=True)
    if limpiar_enlaces:
        archivo_enlaces().write_text("", encoding="utf-8")


def leer_enlaces() -> list[str]:
    """
    Lee enlaces.txt tal como el Descargador original: una URL por linea,
    sin recortes adicionales ni deduplicacion (se respeta el archivo).
    """
    ruta = archivo_enlaces()
    if not ruta.is_file():
        return []
    try:
        with ruta.open("r", encoding="utf-8", errors="replace") as f:
            return [linea.strip() for linea in f if linea.strip()]
    except OSError:
        return []


def contar_enlaces() -> int:
    """Numero de lineas utiles de enlaces.txt (para la barra de estado)."""
    return len(leer_enlaces())


def agregar_enlaces(urls: list[str], origen: str = "externo") -> int:
    """
    Anade URLs a enlaces.txt conservando el comportamiento original:
    solo se evita el duplicado CONSECUTIVO (la ultima linea escrita).

    Devuelve cuantas URLs nuevas se escribieron.
    """
    from utils.urls import limpiar_url

    candidatas: list[str] = []
    ultima = ""
    if archivo_enlaces().is_file():
        try:
            lineas = archivo_enlaces().read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            for linea in reversed(lineas):
                if linea.strip():
                    ultima = linea.strip()
                    break
        except OSError:
            pass

    for cruda in urls:
        url = limpiar_url(cruda)
        if not url.lower().startswith(("http://", "https://")):
            continue
        if url == ultima:
            continue
        candidatas.append(url)
        ultima = url

    if not candidatas:
        return 0

    try:
        asegurar_entorno()
        with archivo_enlaces().open("a", encoding="utf-8") as f:
            for url in candidatas:
                f.write(url + "\n")
        _log.info("Anadidos %d enlace(s) desde %s", len(candidatas), origen)
        return len(candidatas)
    except OSError as exc:
        _log.error("No se pudieron anadir enlaces: %s", exc)
        return 0


# ------------------------------------------------------------------
# Datos de aplicacion (%APPDATA%/MarkOS_Downloader)
# ------------------------------------------------------------------
def dir_appdata() -> Path:
    """Carpeta persistente de configuracion, log e instrucciones."""
    raiz = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    destino = Path(raiz) / APP_SLUG
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        # Ultimo recurso: junto al ejecutable.
        destino = dir_ejecutable() / ".markos"
        destino.mkdir(parents=True, exist_ok=True)
    return destino


def archivo_config() -> Path:
    return dir_appdata() / "config.json"


def archivo_log() -> Path:
    return dir_appdata() / "app.log"


def archivo_instrucciones() -> Path:
    """Copia persistente de las instrucciones (se abre con el Bloc de notas)."""
    return dir_appdata() / "Instrucciones.txt"


def archivo_historial() -> Path:
    """Base de datos SQLite del historial de descargas."""
    return dir_appdata() / "historial.db"


def dir_actualizaciones() -> Path:
    """Carpeta temporal de actualizaciones de la aplicacion."""
    destino = dir_appdata() / "updates"
    try:
        destino.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return destino


def archivo_actualizacion() -> Path:
    """Script .bat que reemplaza el EXE cuando la app se cierra."""
    return dir_actualizaciones() / "instalar_actualizacion.bat"
