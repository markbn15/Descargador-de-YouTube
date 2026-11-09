"""
core/updater.py
====================================================================
Actualizador de dependencias en un QThread propio.

Descarga las versiones mas recientes de:
  * yt-dlp.exe                (GitHub oficial)
  * ffmpeg.exe + ffprobe.exe  (gyan.dev, essentials)

Los archivos se guardan en:

    %APPDATA%\\MarkOS_Downloader\\bin

utils.paths da prioridad a esa carpeta sobre los binarios incluidos en
el EXE, de modo que la actualizacion se aplica sin recompilar ni tocar
el ejecutable original. La descarga nunca bloquea la interfaz y se
puede cancelar con detener().
====================================================================
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from utils.logger import obtener_logger
from utils.paths import dir_bin_usuario

_log = obtener_logger("updater")

USER_AGENT = "MarkOS-Downloader-Suite/1.1"
URL_YTDLP_API = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
URL_YTDLP = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
URL_FFMPEG = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

BLOQUE = 256 * 1024
TAMANO_MINIMO = 512 * 1024


class _Cancelado(Exception):
    """Se lanza cuando el usuario pulsa Detener."""


class UpdaterThread(QThread):
    """Descarga e instala binarios actualizados sin congelar la GUI."""

    progreso = Signal(int, str)      # 0..100, texto de estado
    log = Signal(str)                # linea legible para el usuario
    finalizado = Signal(bool, str)   # (exito, resumen)

    def __init__(
        self,
        actualizar_ytdlp: bool = True,
        actualizar_ffmpeg: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.actualizar_ytdlp = bool(actualizar_ytdlp)
        self.actualizar_ffmpeg = bool(actualizar_ffmpeg)
        self._detener = threading.Event()

    # ------------------------------------------------------------------
    def detener(self) -> None:
        self._detener.set()

    @property
    def cancelado(self) -> bool:
        return self._detener.is_set()

    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401
        try:
            if not self.actualizar_ytdlp and not self.actualizar_ffmpeg:
                self.finalizado.emit(False, "No seleccionaste ninguna dependencia.")
                return

            dir_bin_usuario().mkdir(parents=True, exist_ok=True)
            hechos: list[str] = []

            if self.actualizar_ytdlp:
                self._actualizar_ytdlp()
                hechos.append("yt-dlp")

            if self.actualizar_ffmpeg:
                self._actualizar_ffmpeg()
                hechos.append("FFmpeg")

            if self.cancelado:
                raise _Cancelado()

            self.progreso.emit(100, "Actualización completada")
            resumen = "Actualizado correctamente: " + ", ".join(hechos) + "."
            self.log.emit(f"[OK] {resumen}")
            _log.info(resumen)
            self.finalizado.emit(True, resumen)
        except _Cancelado:
            self.progreso.emit(0, "Actualización cancelada")
            self.log.emit("[x] Actualización cancelada por el usuario.")
            _log.info("Actualización cancelada")
            self.finalizado.emit(False, "Actualización cancelada.")
        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            TimeoutError,
            OSError,
            ValueError,
            RuntimeError,
            zipfile.BadZipFile,
        ) as exc:
            self.progreso.emit(0, "Error de actualización")
            self.log.emit(f"[!] {exc}")
            _log.exception("Error actualizando dependencias")
            self.finalizado.emit(False, str(exc))
        except Exception as exc:  # red de seguridad
            self.progreso.emit(0, "Error inesperado")
            self.log.emit(f"[!] Error inesperado: {exc}")
            _log.exception("Error no controlado en UpdaterThread")
            self.finalizado.emit(False, f"Error inesperado: {exc}")

    # ------------------------------------------------------------------
    # yt-dlp
    # ------------------------------------------------------------------
    def _actualizar_ytdlp(self) -> None:
        self.progreso.emit(2, "Consultando la última versión de yt-dlp…")
        self.log.emit("[>] Buscando la última versión de yt-dlp…")

        version = ""
        url = URL_YTDLP
        try:
            peticion = urllib.request.Request(
                URL_YTDLP_API,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "application/vnd.github+json",
                },
            )
            with urllib.request.urlopen(peticion, timeout=30) as respuesta:
                datos = json.loads(respuesta.read().decode("utf-8"))
            version = str(datos.get("tag_name") or "")
            for activo in datos.get("assets", []):
                if activo.get("name") == "yt-dlp.exe":
                    url = str(activo["browser_download_url"])
                    break
            if version:
                self.log.emit(f"    Versión disponible: {version}")
            else:
                self.log.emit("    No se pudo leer la versión; se usa el canal estable.")
        except (urllib.error.URLError, ValueError, KeyError, TypeError) as exc:
            self.log.emit(
                f"    Aviso: no se pudo consultar GitHub ({exc}). "
                "Se descargará el canal estable."
            )

        destino = dir_bin_usuario() / "yt-dlp.exe"
        temporal = destino.with_name("yt-dlp.exe.download")
        try:
            self._descargar(url, temporal, "yt-dlp.exe", 4, 78)
            self._validar_exe(temporal)
            os.replace(temporal, destino)
            self.progreso.emit(80, "yt-dlp actualizado")
            self.log.emit(f"[OK] yt-dlp instalado en {destino}")
        finally:
            try:
                temporal.unlink(missing_ok=True)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # FFmpeg
    # ------------------------------------------------------------------
    def _actualizar_ffmpeg(self) -> None:
        self.progreso.emit(80, "Descargando FFmpeg essentials…")
        self.log.emit("[>] Descargando FFmpeg essentials (puede tardar)…")

        with tempfile.TemporaryDirectory(prefix="markos_updater_") as tmp:
            carpeta = Path(tmp)
            zip_ruta = carpeta / "ffmpeg.zip"
            self._descargar(URL_FFMPEG, zip_ruta, "FFmpeg", 80, 94)

            if self.cancelado:
                raise _Cancelado()

            self.progreso.emit(95, "Extrayendo ffmpeg y ffprobe…")
            self.log.emit("[>] Extrayendo ffmpeg.exe y ffprobe.exe…")
            extraidos: dict[str, Path] = {}
            with zipfile.ZipFile(zip_ruta) as zf:
                for miembro in zf.namelist():
                    nombre = Path(miembro).name.lower()
                    if nombre in ("ffmpeg.exe", "ffprobe.exe") and nombre not in extraidos:
                        salida = carpeta / nombre
                        with zf.open(miembro) as origen, salida.open("wb") as destino_f:
                            shutil.copyfileobj(origen, destino_f)
                        extraidos[nombre] = salida

            faltan = {"ffmpeg.exe", "ffprobe.exe"} - set(extraidos)
            if faltan:
                raise RuntimeError(
                    "El ZIP de FFmpeg no contiene: " + ", ".join(sorted(faltan))
                )

            for nombre, origen in extraidos.items():
                self._validar_exe(origen)
                destino = dir_bin_usuario() / nombre
                temporal = destino.with_name(nombre + ".tmp")
                try:
                    shutil.copy2(origen, temporal)
                    os.replace(temporal, destino)
                finally:
                    try:
                        temporal.unlink(missing_ok=True)
                    except OSError:
                        pass
                self.log.emit(f"[OK] {nombre} instalado en {destino}")

            self.progreso.emit(98, "FFmpeg actualizado")

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _descargar(
        self,
        url: str,
        destino: Path,
        etiqueta: str,
        inicio: int,
        fin: int,
    ) -> None:
        peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(peticion, timeout=120) as respuesta:
            total = int(respuesta.headers.get("Content-Length") or 0)
            leido = 0
            ultimo = -1
            with destino.open("wb") as f:
                while not self.cancelado:
                    bloque = respuesta.read(BLOQUE)
                    if not bloque:
                        break
                    f.write(bloque)
                    leido += len(bloque)
                    if total:
                        pct = inicio + int(leido * (fin - inicio) / total)
                        if pct != ultimo:
                            ultimo = pct
                            mb_leidos = leido / (1024 * 1024)
                            mb_total = total / (1024 * 1024)
                            self.progreso.emit(
                                min(fin, pct),
                                f"{etiqueta}: {mb_leidos:.1f} / {mb_total:.1f} MB",
                            )

        if self.cancelado:
            raise _Cancelado()
        if not destino.is_file() or destino.stat().st_size < TAMANO_MINIMO:
            raise RuntimeError(f"La descarga de {etiqueta} quedó incompleta.")

    @staticmethod
    def _validar_exe(ruta: Path) -> None:
        if not ruta.is_file() or ruta.stat().st_size < TAMANO_MINIMO:
            raise RuntimeError(f"Archivo demasiado pequeño: {ruta.name}")
        with ruta.open("rb") as f:
            if f.read(2) != b"MZ":
                raise RuntimeError(
                    f"{ruta.name} no es un ejecutable de Windows válido (falta MZ)."
                )
