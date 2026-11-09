"""
core/downloader.py
====================================================================
Motor de descargas en un QThread propio.

Los argumentos de calidad son EXACTAMENTE los de Descargador_yt.py:
    MP3   -> -x --audio-format mp3 --audio-quality 0
    480p  -> -f bestvideo[height<=480]+bestaudio/best[height<=480]
             --merge-output-format mp4
    720p  -> igual con 720
    1080p -> igual con 1080
    Maxima-> sin argumentos de formato (comportamiento por defecto)

Se anaden solo flags TECNICOS para que la salida sea legible en la GUI
(--newline --no-colors --encoding utf-8) y --ffmpeg-location cuando
ffmpeg/ffprobe viajan dentro del EXE. La descarga se ejecuta con
cwd=DESCARGAS, igual que el script original.

Novedades:
  * perfil de calidad por dominio (utils.urls.calidad_para_url),
  * pausa/reanudacion de la cola entre enlaces,
  * una fila del historial SQLite por cada enlace, con el archivo y
    el tamano reales.

El binario se resuelve con utils.paths.get_ytdlp_path(), que en el EXE
prefiere %APPDATA%\\MarkOS_Downloader\\bin, luego sys._MEIPASS/bin y NUNCA
el PATH del sistema.
====================================================================
"""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from utils.logger import obtener_logger
from utils.paths import (
    dir_descargas,
    get_ffmpeg_path,
    get_ffprobe_path,
    get_ytdlp_path,
)
from utils.urls import calidad_para_url

_log = obtener_logger("downloader")

# En Windows evita que se abra una consola al lanzar yt-dlp/ffmpeg.
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# Regex de progreso de yt-dlp: "[download]  42.3% of 120.00MiB at ..."
_RE_PROGRESO = re.compile(r"\[download\]\s+(\d{1,3}(?:\.\d+)?)%")

# Rutas que yt-dlp anuncia al terminar cada archivo.
_RE_DESTINOS = (
    re.compile(r"^\[download\]\s+Destination:\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\[ExtractAudio\]\s+Destination:\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\[Merger\]\s+Merging formats into\s+\"(.+)\"$", re.IGNORECASE),
    re.compile(r"^\[MoveFiles\]\s+Moving file .+ to\s+\"(.+)\"$", re.IGNORECASE),
    re.compile(r"^\[FixupM3u8\]\s+Destination:\s+(.+)$", re.IGNORECASE),
    re.compile(r"^\[VideoConvertor\]\s+Converting video .+ to\s+\"(.+)\"$", re.IGNORECASE),
    re.compile(r"^\[Metadata\]\s+Writing metadata to\s+\"(.+)\"$", re.IGNORECASE),
    re.compile(r"^\[download\]\s+(.+)\s+has already been downloaded$", re.IGNORECASE),
)
_RE_YA_DESCARGADO = re.compile(
    r"^\[download\]\s+(.+)\s+has already been downloaded$", re.IGNORECASE
)

# Extensiones que producimos (para el respaldo por archivo mas reciente).
_EXTENSIONES = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mp3",
    ".m4a",
    ".opus",
    ".ogg",
    ".flac",
    ".wav",
    ".avi",
    ".mov",
}


# ----------------------------------------------------------------------
# Calidades (mismas cadenas que el script original)
# ----------------------------------------------------------------------
CALIDADES: dict[str, dict] = {
    "mp3": {
        "etiqueta": "MP3 · Solo audio",
        "descripcion": "Extrae el audio y lo convierte a MP3 320 kbps aprox.",
        "args": ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
    },
    "480p": {
        "etiqueta": "480p · SD",
        "descripcion": "Video SD con audio fusionado en MP4.",
        "args": [
            "-f",
            "bestvideo[height<=480]+bestaudio/best[height<=480]",
            "--merge-output-format",
            "mp4",
        ],
    },
    "720p": {
        "etiqueta": "720p · HD",
        "descripcion": "Video HD con audio fusionado en MP4.",
        "args": [
            "-f",
            "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "--merge-output-format",
            "mp4",
        ],
    },
    "1080p": {
        "etiqueta": "1080p · Full HD",
        "descripcion": "Video Full HD con audio fusionado en MP4.",
        "args": [
            "-f",
            "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
            "--merge-output-format",
            "mp4",
        ],
    },
    "max": {
        "etiqueta": "Máxima · Mejor disponible",
        "descripcion": "Sin límite de formato: lo mejor que ofrezca el sitio.",
        "args": [],
    },
}

# Flags tecnicos de la GUI (no alteran la calidad elegida).
ARGS_TECNICOS = ["--newline", "--no-colors", "--encoding", "utf-8"]


def args_calidad(clave: str) -> list[str]:
    """Devuelve una copia de los argumentos de la calidad indicada."""
    return list(CALIDADES.get(clave, CALIDADES["max"])["args"])


def construir_comando(url: str, clave: str, ytdlp: str | None = None) -> list[str]:
    """
    Construye la lista de argumentos para subprocess. Nunca usa shell=True,
    por lo que las URLs con caracteres especiales son seguras.
    """
    binario = str(ytdlp or get_ytdlp_path() or "yt-dlp.exe")
    comando = [binario, *ARGS_TECNICOS]

    # Ruta explicita a ffmpeg/ffprobe (obligatorio cuando van embebidos).
    ffmpeg = get_ffmpeg_path()
    if ffmpeg is not None:
        comando += ["--ffmpeg-location", str(ffmpeg.parent)]

    comando += args_calidad(clave)
    comando.append(url)
    return comando


def ffmpeg_disponible() -> bool:
    """True si se puede fusionar audio+video y convertir a MP3."""
    return get_ffmpeg_path() is not None


def ffmpeg_completo() -> bool:
    """ffprobe es necesario para algunas post-operaciones de yt-dlp."""
    return get_ffmpeg_path() is not None and get_ffprobe_path() is not None


class DownloadThread(QThread):
    """Descarga secuencial de enlaces sin bloquear la interfaz."""

    log = Signal(str)                    # linea de salida de yt-dlp
    progreso = Signal(int)               # 0..100 global
    item_actual = Signal(int, int, str)  # (indice, total, url)
    item_resultado = Signal(object)      # dict con el resultado de un enlace
    pausado = Signal(bool)               # True al entrar/salir de pausa real
    finalizado = Signal(bool, str)       # (exito, resumen legible)

    def __init__(
        self,
        urls: list[str],
        calidad: str,
        parent=None,
        *,
        perfiles: dict[str, str] | None = None,
        calidades_override: dict[str, str] | None = None,
        historial=None,
        historial_ids: list[int | None] | None = None,
        origen: str = "enlaces",
    ) -> None:
        super().__init__(parent)
        self.urls = list(urls)
        self.calidad = calidad if calidad in CALIDADES else "max"
        self.perfiles = dict(perfiles or {})
        self.calidades_override = dict(calidades_override or {})
        self.historial = historial
        self.historial_ids = list(historial_ids or [])
        self.origen = origen
        self._detener = threading.Event()
        self._pausado = threading.Event()
        self._cancelado = False
        self._proceso: subprocess.Popen | None = None
        self._cerrojo = threading.Lock()
        self._errores_recientes: deque[str] = deque(maxlen=6)
        self._finalizado_emitido = False
        self._destino_actual = ""
        self._inicio_item = 0.0
        self._pausa_anunciada = False
        self._procesados: set[int] = set()

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def detener(self) -> None:
        """Cancela la descarga y mata yt-dlp + hijos (ffmpeg)."""
        self._detener.set()
        self._cancelado = True
        self._pausado.clear()
        with self._cerrojo:
            proceso = self._proceso
        self._matar_proceso(proceso)

    def pausar(self) -> None:
        """Solicita pausar la cola. Se aplica al terminar el enlace actual."""
        if not self._detener.is_set():
            self._pausado.set()

    def reanudar(self) -> None:
        self._pausado.clear()

    @property
    def pausado_actual(self) -> bool:
        return self._pausado.is_set()

    @property
    def cancelado(self) -> bool:
        return self._cancelado or self._detener.is_set()

    def _matar_proceso(self, proceso: subprocess.Popen | None) -> None:
        """Mata un proceso y sus hijos con taskkill /T (o kill como respaldo)."""
        if proceso is None or proceso.poll() is not None:
            return
        try:
            # /T mata tambien los ffmpeg hijos del proceso.
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proceso.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                creationflags=_CREATE_NO_WINDOW,
            )
        except Exception:
            try:
                proceso.kill()
            except Exception:
                pass

    def _finalizar(self, exito: bool, resumen: str) -> None:
        """Emite finalizado una sola vez, aunque haya errores encadenados."""
        if self._finalizado_emitido:
            return
        self._finalizado_emitido = True
        self.finalizado.emit(exito, resumen)

    # ------------------------------------------------------------------
    # Ciclo del hilo
    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401
        try:
            self._ejecutar_descargas()
        except Exception as exc:  # red de seguridad: nunca dejar la UI colgada
            _log.exception("Error interno no controlado en DownloadThread")
            self.log.emit(f"[!] Error interno del descargador: {exc}")
            self._finalizar(False, f"Error interno del descargador: {exc}")

    def _esperar_si_pausado(self) -> None:
        """Bloquea la cola (entre enlaces) hasta que se reanude o se cancele."""
        if not self._pausado.is_set():
            return

        if not self._pausa_anunciada:
            self._pausa_anunciada = True
            self.pausado.emit(True)
            self.log.emit("[⏸] Cola en pausa. Pulsa Reanudar para continuar.")

        while self._pausado.is_set() and not self._detener.is_set():
            time.sleep(0.15)

        if self._pausa_anunciada:
            self._pausa_anunciada = False
            self.pausado.emit(False)
            if not self._detener.is_set():
                self.log.emit("[▶] Cola reanudada.")

    def _ejecutar_descargas(self) -> None:
        total = len(self.urls)
        if total == 0:
            self._finalizar(False, "No hay enlaces para descargar.")
            return

        ytdlp = get_ytdlp_path()
        if ytdlp is None:
            self._finalizar(
                False,
                "No se encontró yt-dlp.exe.\n"
                "Abre el archivo de instrucciones o vuelve a compilar con build.bat.",
            )
            return

        try:
            dir_descargas().mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._finalizar(False, f"No se pudo crear la carpeta DESCARGAS:\n{exc}")
            return

        _log.info(
            "Descarga iniciada: %d enlaces | calidad=%s | yt-dlp=%s",
            total,
            self.calidad,
            ytdlp,
        )
        self.log.emit(f"yt-dlp: {ytdlp}")
        self.log.emit(f"Destino: {dir_descargas()}")
        self.log.emit(f"Calidad global: {CALIDADES[self.calidad]['etiqueta']}")
        if self.perfiles:
            self.log.emit(
                "Perfiles por sitio activos: "
                + ", ".join(f"{k} → {v}" for k, v in self.perfiles.items())
            )
        self.log.emit("")

        completados = 0
        fallos = 0

        for indice, url in enumerate(self.urls, start=1):
            if self._detener.is_set():
                break

            self._esperar_si_pausado()
            if self._detener.is_set():
                break

            calidad = calidad_para_url(
                url,
                self.perfiles,
                self.calidad,
                self.calidades_override,
            )
            if calidad not in CALIDADES:
                calidad = self.calidad

            id_historial = self._id_historial(indice)
            if self.historial is not None:
                self.historial.marcar_descargando(id_historial)

            self.item_actual.emit(indice, total, url)
            self.log.emit("─" * 58)
            self.log.emit(f"[{indice}/{total}] {url}")
            self.log.emit(f"    Calidad aplicada: {CALIDADES[calidad]['etiqueta']}")
            self.log.emit("─" * 58)
            self._errores_recientes.clear()
            self._destino_actual = ""
            self._inicio_item = time.time()

            comando = construir_comando(url, calidad, str(ytdlp))
            codigo, archivo, tamano = self._ejecutar(comando, indice, total)

            if self._detener.is_set():
                if self.historial is not None:
                    self.historial.marcar_cancelada(
                        id_historial, "Cancelada durante la descarga"
                    )
                self._procesados.add(indice)
                break

            if codigo == 0:
                completados += 1
                if not archivo:
                    archivo = self._buscar_archivo_reciente(self._inicio_item)
                tamano = tamano or self._tamano_archivo(archivo)
                titulo = Path(archivo).stem if archivo else ""
                if self.historial is not None:
                    self.historial.marcar_completada(
                        id_historial,
                        archivo=archivo,
                        tamano=tamano,
                        titulo=titulo,
                        calidad=calidad,
                    )
                self.item_resultado.emit(
                    {
                        "id": id_historial,
                        "indice": indice,
                        "total": total,
                        "url": url,
                        "exito": True,
                        "calidad": calidad,
                        "archivo": archivo,
                        "tamano": tamano,
                        "titulo": titulo,
                        "error": "",
                        "origen": self.origen,
                    }
                )
                self.progreso.emit(int(indice * 100 / total))
            else:
                fallos += 1
                error = "\n".join(self._errores_recientes).strip()
                if not error:
                    error = f"yt-dlp terminó con código {codigo}."
                if self.historial is not None:
                    self.historial.marcar_error(id_historial, error, calidad)
                self.item_resultado.emit(
                    {
                        "id": id_historial,
                        "indice": indice,
                        "total": total,
                        "url": url,
                        "exito": False,
                        "calidad": calidad,
                        "archivo": "",
                        "tamano": 0,
                        "titulo": "",
                        "error": error,
                        "origen": self.origen,
                    }
                )
                self.log.emit(f"[!] yt-dlp terminó con código {codigo}.")
                for linea in self._errores_recientes:
                    self.log.emit(f"    {linea}")
                self.log.emit(
                    "    Sugerencia: verifica el enlace, actualiza yt-dlp o "
                    "usa cookies si el sitio pide inicio de sesión."
                )
                _log.warning("Fallo yt-dlp (%s): %s", codigo, url)

            self._procesados.add(indice)

        # ------------------------------------------------------------------
        # Resumen final
        # ------------------------------------------------------------------
        if self._cancelado:
            self._cerrar_restantes("Cancelada al detener la cola")
            self.log.emit("")
            self.log.emit("[x] Descarga cancelada por el usuario.")
            self._finalizar(
                False,
                f"Descarga cancelada. Completados: {completados}/{total}.",
            )
            _log.info("Descarga cancelada (%d/%d)", completados, total)
            return

        exito = fallos == 0 and completados == total
        if exito:
            resumen = f"Descargas completadas: {completados}/{total}."
        else:
            resumen = (
                f"Descargas completadas: {completados}/{total} · "
                f"errores: {fallos}."
            )
        self.log.emit("")
        self.log.emit("=" * 58)
        self.log.emit(
            "  "
            + (
                "¡DESCARGAS PROCESADAS CORRECTAMENTE!"
                if exito
                else "FIN CON ERRORES"
            )
        )
        self.log.emit("=" * 58)
        self._finalizar(exito, resumen)
        _log.info("Descarga finalizada: %s", resumen)

    # ------------------------------------------------------------------
    # Historial
    # ------------------------------------------------------------------
    def _id_historial(self, indice: int) -> int | None:
        posicion = indice - 1
        if 0 <= posicion < len(self.historial_ids):
            return self.historial_ids[posicion]
        return None

    def _cerrar_restantes(self, motivo: str) -> None:
        """Marca como canceladas las filas que no llegaron a procesarse."""
        if self.historial is None:
            return
        for indice in range(1, len(self.urls) + 1):
            if indice in self._procesados:
                continue
            self.historial.marcar_cancelada(self._id_historial(indice), motivo)

    # ------------------------------------------------------------------
    # Ejecucion de un enlace
    # ------------------------------------------------------------------
    def _ejecutar(
        self, comando: list[str], indice: int, total: int
    ) -> tuple[int, str, int]:
        """Lanza yt-dlp, transmite su salida y devuelve (codigo, archivo, tamano)."""
        entorno = os.environ.copy()
        entorno["PYTHONIOENCODING"] = "utf-8"
        entorno["PYTHONUTF8"] = "1"
        entorno["NO_COLOR"] = "1"

        try:
            proceso = subprocess.Popen(
                comando,
                cwd=str(dir_descargas()),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                env=entorno,
                creationflags=_CREATE_NO_WINDOW,
            )
        except FileNotFoundError:
            self.log.emit("[!] No se encontró el ejecutable de yt-dlp.")
            return 1, "", 0
        except OSError as exc:
            self.log.emit(f"[!] No se pudo iniciar yt-dlp: {exc}")
            _log.error("Popen falló: %s", exc)
            return 1, "", 0

        with self._cerrojo:
            self._proceso = proceso

        # Si el usuario pulso Detener entre Popen y esta asignacion, el
        # proceso aun no estaba registrado: lo matamos aqui.
        if self._detener.is_set():
            self._matar_proceso(proceso)

        try:
            assert proceso.stdout is not None
            for cruda in proceso.stdout:
                if self._detener.is_set():
                    break

                # yt-dlp puede usar \r; lo normalizamos por si acaso.
                for linea in cruda.replace("\r", "\n").splitlines():
                    linea = linea.rstrip()
                    if not linea:
                        continue

                    self.log.emit(linea)
                    self._capturar_error(linea)
                    self._capturar_destino(linea)

                    coincidencia = _RE_PROGRESO.search(linea)
                    if coincidencia:
                        try:
                            parcial = min(100.0, float(coincidencia.group(1)))
                            global_pct = (
                                ((indice - 1) + parcial / 100.0)
                                * 100.0
                                / total
                            )
                            self.progreso.emit(int(global_pct))
                        except ValueError:
                            pass

            codigo = proceso.wait()
            archivo = self._resolver_destino(self._destino_actual)
            tamano = self._tamano_archivo(archivo)
            return codigo, archivo, tamano
        except Exception as exc:
            _log.exception("Error leyendo la salida de yt-dlp")
            self.log.emit(f"[!] Error inesperado al leer la salida: {exc}")
            try:
                proceso.kill()
            except Exception:
                pass
            return 1, "", 0
        finally:
            with self._cerrojo:
                self._proceso = None
            try:
                if proceso.stdout is not None:
                    proceso.stdout.close()
            except Exception:
                pass

    def _capturar_destino(self, linea: str) -> None:
        """Guarda la ruta del archivo final anunciada por yt-dlp."""
        for patron in _RE_DESTINOS:
            coincidencia = patron.search(linea)
            if coincidencia:
                posible = coincidencia.group(1).strip().strip('"')
                if posible:
                    self._destino_actual = posible
                return

    def _resolver_destino(self, anunciado: str) -> str:
        if not anunciado:
            return ""
        ruta = Path(anunciado)
        if not ruta.is_absolute():
            ruta = dir_descargas() / ruta
        try:
            return str(ruta.resolve())
        except OSError:
            return str(ruta)

    def _tamano_archivo(self, ruta: str) -> int:
        if not ruta:
            return 0
        try:
            archivo = Path(ruta)
            if archivo.is_file():
                return int(archivo.stat().st_size)
        except OSError:
            pass
        return 0

    def _buscar_archivo_reciente(self, desde: float) -> str:
        """Respaldo: archivo de video/audio mas reciente en DESCARGAS."""
        candidato = ""
        ultimo = 0.0
        try:
            for ruta in dir_descargas().iterdir():
                if not ruta.is_file() or ruta.suffix.lower() not in _EXTENSIONES:
                    continue
                try:
                    modificado = ruta.stat().st_mtime
                except OSError:
                    continue
                if modificado >= desde - 2 and modificado >= ultimo:
                    ultimo = modificado
                    candidato = str(ruta.resolve())
        except OSError:
            pass
        return candidato

    def _capturar_error(self, linea: str) -> None:
        """Guarda las ultimas lineas de error para el resumen de la UI."""
        if "ERROR" in linea.upper() or "WARNING" in linea.upper():
            self._errores_recientes.append(linea)
