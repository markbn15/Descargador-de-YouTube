"""
core/updates.py
====================================================================
Sistema de actualizacion de la aplicacion vinculado a las releases de
GitHub:

    https://github.com/markbn15/Descargador-de-YouTube

- Consulta /releases/latest y compara etiquetas tipo V1.51.
- ComprobacionThread evita bloquear la interfaz.
- DescargaActualizacionThread descarga el asset .exe con progreso.
- Si la release no trae .exe, la interfaz ofrece abrir la pagina.
- En el EXE, preparar_instalacion() crea un .bat que espera a que la
  app termine, reemplaza el ejecutable y la vuelve a abrir.

Todo falla de forma controlada: sin red, con limite de peticiones de
GitHub o con assets incompletos la app sigue funcionando.
====================================================================
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from utils.logger import obtener_logger
from utils.paths import (
    APP_VERSION,
    archivo_actualizacion,
    dir_actualizaciones,
    esta_congelado,
)

_log = obtener_logger("updates")

REPO = "markbn15/Descargador-de-YouTube"
URL_REPO = f"https://github.com/{REPO}"
URL_RELEASES = f"{URL_REPO}/releases"
URL_API_ULTIMA = f"https://api.github.com/repos/{REPO}/releases/latest"
USER_AGENT = f"MarkOS-Downloader-Suite/{APP_VERSION}"
BLOQUE = 256 * 1024
TAMANO_MINIMO_EXE = 2 * 1024 * 1024


# ----------------------------------------------------------------------
# Versionado
# ----------------------------------------------------------------------
def normalizar_version(texto: str) -> tuple[int, ...]:
    """Extrae la primera secuencia numerica de una etiqueta (V1.51 -> 1.51)."""
    coincidencia = re.search(r"(\d+(?:[._-]\d+)*)", str(texto or ""))
    if not coincidencia:
        return ()
    numeros = re.split(r"[._-]", coincidencia.group(1))
    return tuple(int(n) for n in numeros if n.isdigit())


def _clave_version(texto: str) -> tuple[Decimal, tuple[int, ...]]:
    """
    Clave de comparacion con semantica decimal para etiquetas tipo V1.7.

    El proyecto usa versiones major.minor con un solo decimal visible:
    1.7 se interpreta como 1.70 y por tanto es mayor que 1.51.
    Si hay mas componentes (1.7.1), se comparan despues del major.minor.
    """
    numeros = normalizar_version(texto)
    if not numeros:
        return (Decimal(0), ())
    principal = Decimal(numeros[0])
    resto: tuple[int, ...] = ()
    if len(numeros) >= 2:
        try:
            principal = Decimal(f"{numeros[0]}.{numeros[1]}")
        except InvalidOperation:
            principal = Decimal(numeros[0])
        resto = tuple(numeros[2:])
    while resto and resto[-1] == 0:
        resto = resto[:-1]
    return (principal, resto)


def comparar_versiones(a: str, b: str) -> int:
    """-1 si a<b, 0 si son iguales, 1 si a>b (V1.7 > V1.51)."""
    clave_a = _clave_version(a)
    clave_b = _clave_version(b)
    if clave_a < clave_b:
        return -1
    if clave_a > clave_b:
        return 1
    return 0


def es_mas_nueva(remota: str, actual: str = APP_VERSION) -> bool:
    return comparar_versiones(remota, actual) > 0


def version_legible(etiqueta: str) -> str:
    etiqueta = str(etiqueta or "").strip()
    if not etiqueta:
        return "desconocida"
    return etiqueta


# ----------------------------------------------------------------------
# Modelos
# ----------------------------------------------------------------------
@dataclass
class Activo:
    nombre: str
    url: str
    tamano: int = 0
    tipo: str = ""

    @property
    def es_exe(self) -> bool:
        return self.nombre.lower().endswith(".exe")


@dataclass
class Release:
    tag: str
    nombre: str
    notas: str
    pagina: str
    publicado: str
    prerelease: bool = False
    assets: list[Activo] = field(default_factory=list)

    @property
    def activo_exe(self) -> Activo | None:
        return elegir_activo_exe(self)


@dataclass
class ResultadoActualizacion:
    ok: bool
    error: str = ""
    release: Release | None = None
    hay_nueva: bool = False
    actual: str = APP_VERSION
    comprobado: str = ""

    @property
    def tag(self) -> str:
        return self.release.tag if self.release else ""

    @property
    def activo_exe(self) -> Activo | None:
        return self.release.activo_exe if self.release else None


def elegir_activo_exe(release: Release | None) -> Activo | None:
    """Elige el .exe mas adecuado de una release."""
    if release is None:
        return None
    ejecutables = [a for a in release.assets if a.es_exe]
    if not ejecutables:
        return None
    # Preferimos nombres que mencionen MarkOS/Suite/Downloader.
    preferidos = [
        a
        for a in ejecutables
        if any(
            palabra in a.nombre.lower()
            for palabra in ("markos", "suite", "downloader")
        )
    ]
    candidatos = preferidos or ejecutables
    return max(candidatos, key=lambda a: a.tamano or 0)


# ----------------------------------------------------------------------
# Consulta
# ----------------------------------------------------------------------
def consultar_ultima_release(timeout: int = 15) -> ResultadoActualizacion:
    """Consulta GitHub y devuelve la ultima release publicada."""
    peticion = urllib.request.Request(
        URL_API_ULTIMA,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            mensaje = (
                "GitHub limitó temporalmente las comprobaciones "
                "(límite de peticiones). Inténtalo más tarde."
            )
        elif exc.code == 404:
            mensaje = "El repositorio de releases no está disponible."
        else:
            mensaje = f"GitHub respondió con error HTTP {exc.code}."
        _log.warning("Error consultando releases: %s", exc)
        return ResultadoActualizacion(ok=False, error=mensaje)
    except urllib.error.URLError as exc:
        _log.warning("Sin conexión al consultar releases: %s", exc)
        return ResultadoActualizacion(
            ok=False,
            error=(
                "No se pudo conectar con GitHub. Comprueba tu conexión a "
                "Internet o inténtalo más tarde."
            ),
        )
    except (TimeoutError, ValueError, OSError) as exc:
        _log.warning("Respuesta de releases inválida: %s", exc)
        return ResultadoActualizacion(
            ok=False,
            error=f"No se pudo leer la respuesta de GitHub: {exc}",
        )

    if not isinstance(datos, dict):
        return ResultadoActualizacion(
            ok=False, error="La respuesta de GitHub no tiene el formato esperado."
        )

    tag = str(datos.get("tag_name") or "")
    assets: list[Activo] = []
    for bruto in datos.get("assets") or []:
        if not isinstance(bruto, dict):
            continue
        nombre = str(bruto.get("name") or "")
        url = str(bruto.get("browser_download_url") or "")
        if not nombre or not url:
            continue
        assets.append(
            Activo(
                nombre=nombre,
                url=url,
                tamano=int(bruto.get("size") or 0),
                tipo=str(bruto.get("content_type") or ""),
            )
        )

    release = Release(
        tag=tag,
        nombre=str(datos.get("name") or tag),
        notas=str(datos.get("body") or ""),
        pagina=str(datos.get("html_url") or URL_RELEASES),
        publicado=str(datos.get("published_at") or ""),
        prerelease=bool(datos.get("prerelease")),
        assets=assets,
    )
    hay_nueva = es_mas_nueva(tag, APP_VERSION)
    _log.info(
        "Release consultada: %s (actual %s, nueva=%s)",
        tag or "sin etiqueta",
        APP_VERSION,
        hay_nueva,
    )
    return ResultadoActualizacion(
        ok=True,
        release=release,
        hay_nueva=hay_nueva,
        actual=APP_VERSION,
    )


class ComprobacionThread(QThread):
    """Consulta GitHub sin congelar la interfaz."""

    resultado = Signal(object)

    def run(self) -> None:  # noqa: D401
        try:
            self.resultado.emit(consultar_ultima_release())
        except Exception as exc:  # red de seguridad
            _log.exception("Error inesperado comprobando actualizaciones")
            self.resultado.emit(
                ResultadoActualizacion(
                    ok=False, error=f"Error inesperado: {exc}"
                )
            )


# ----------------------------------------------------------------------
# Descarga del asset .exe
# ----------------------------------------------------------------------
class _Cancelado(Exception):
    pass


class DescargaActualizacionThread(QThread):
    """Descarga el .exe de la release con progreso y cancelacion."""

    progreso = Signal(int, str)
    log = Signal(str)
    finalizado = Signal(bool, str, str)  # (exito, ruta, error)

    def __init__(self, activo: Activo, parent=None) -> None:
        super().__init__(parent)
        self.activo = activo
        self._detener = threading.Event()

    def detener(self) -> None:
        self._detener.set()

    @property
    def cancelado(self) -> bool:
        return self._detener.is_set()

    def run(self) -> None:  # noqa: D401
        destino = dir_actualizaciones() / self.activo.nombre
        temporal = destino.with_name(destino.name + ".part")
        try:
            self.progreso.emit(1, f"Descargando {self.activo.nombre}…")
            self.log.emit(f"[>] {self.activo.url}")
            peticion = urllib.request.Request(
                self.activo.url, headers={"User-Agent": USER_AGENT}
            )
            with urllib.request.urlopen(peticion, timeout=120) as respuesta:
                total = int(respuesta.headers.get("Content-Length") or 0)
                leido = 0
                ultimo = -1
                with temporal.open("wb") as archivo:
                    while not self.cancelado:
                        bloque = respuesta.read(BLOQUE)
                        if not bloque:
                            break
                        archivo.write(bloque)
                        leido += len(bloque)
                        if total:
                            pct = int(leido * 96 / total)
                            if pct != ultimo:
                                ultimo = pct
                                self.progreso.emit(
                                    max(1, pct),
                                    f"{self.activo.nombre}: "
                                    f"{leido / 1048576:.1f} / "
                                    f"{total / 1048576:.1f} MB",
                                )
                        elif leido % (4 * 1024 * 1024) < BLOQUE:
                            self.progreso.emit(
                                min(95, 1 + leido // (2 * 1024 * 1024)),
                                f"{self.activo.nombre}: "
                                f"{leido / 1048576:.1f} MB",
                            )

            if self.cancelado:
                raise _Cancelado()
            if not temporal.is_file() or temporal.stat().st_size < TAMANO_MINIMO_EXE:
                raise RuntimeError(
                    "La descarga quedó incompleta o el archivo no es válido."
                )
            with temporal.open("rb") as archivo:
                if archivo.read(2) != b"MZ":
                    raise RuntimeError(
                        "El archivo descargado no es un ejecutable de Windows."
                    )
            os.replace(temporal, destino)
            self.progreso.emit(100, "Actualización lista para instalar")
            self.finalizado.emit(True, str(destino), "")
            _log.info("Actualización descargada en %s", destino)
        except _Cancelado:
            self.progreso.emit(0, "Descarga cancelada")
            self.log.emit("[x] Descarga de la actualización cancelada.")
            self.finalizado.emit(False, "", "Cancelada por el usuario.")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, RuntimeError) as exc:
            _log.exception("Error descargando la actualización")
            self.log.emit(f"[!] {exc}")
            self.finalizado.emit(False, "", str(exc))
        except Exception as exc:  # red de seguridad
            _log.exception("Error inesperado descargando la actualización")
            self.finalizado.emit(False, "", f"Error inesperado: {exc}")
        finally:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                pass


# ----------------------------------------------------------------------
# Instalacion en el EXE
# ----------------------------------------------------------------------
def puede_autoinstalar() -> bool:
    """La sustitucion del EXE solo tiene sentido en la version compilada."""
    return esta_congelado() and os.name == "nt"


def preparar_instalacion(
    nuevo: Path,
    actual: Path | None = None,
    pid: int | None = None,
) -> Path | None:
    """
    Crea un .bat que espera a que la app cierre, reemplaza el EXE y la
    vuelve a abrir. Devuelve la ruta del .bat o None si no es posible.
    """
    if os.name != "nt":
        return None
    nuevo = Path(nuevo)
    actual = Path(actual or Path(sys.executable))
    pid = int(pid or os.getpid())
    if not nuevo.is_file() or not actual.is_file():
        return None

    bat = archivo_actualizacion()
    contenido = f"""@echo off
setlocal EnableExtensions EnableDelayedExpansion
title MarkOS - instalando actualizacion
set /a intentos=0
:esperar
tasklist /FI "PID eq {pid}" 2>nul | find /I "{pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto esperar
)
:copiar
copy /Y "{nuevo}" "{actual}" >nul 2>&1
if errorlevel 1 (
    set /a intentos+=1
    if !intentos! LSS 30 (
        timeout /t 1 /nobreak >nul
        goto copiar
    )
    start "" "{URL_RELEASES}"
    goto fin
)
start "" "{actual}" --actualizado
:fin
del /F /Q "{nuevo}" >nul 2>&1
del /F /Q "%~f0" >nul 2>&1
exit /b 0
"""
    try:
        bat.parent.mkdir(parents=True, exist_ok=True)
        bat.write_text(contenido, encoding="utf-8", errors="replace")
        return bat
    except OSError as exc:
        _log.warning("No se pudo preparar el instalador: %s", exc)
        return None


def lanzar_instalador(bat: Path) -> bool:
    """Lanza el .bat desacoplado de la app actual."""
    if os.name != "nt" or not bat.is_file():
        return False
    try:
        flags = 0
        for nombre in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP", "CREATE_NO_WINDOW"):
            flags |= int(getattr(subprocess, nombre, 0))
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat)],
            cwd=str(bat.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        _log.info("Instalador de actualización lanzado: %s", bat)
        return True
    except OSError as exc:
        _log.warning("No se pudo lanzar el instalador: %s", exc)
        return False


__all__ = [
    "Activo",
    "ComprobacionThread",
    "DescargaActualizacionThread",
    "Release",
    "ResultadoActualizacion",
    "URL_RELEASES",
    "URL_REPO",
    "comparar_versiones",
    "consultar_ultima_release",
    "elegir_activo_exe",
    "es_mas_nueva",
    "lanzar_instalador",
    "normalizar_version",
    "preparar_instalacion",
    "puede_autoinstalar",
]
