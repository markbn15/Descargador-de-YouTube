"""
tests/download_test.py
====================================================================
Prueba de integracion del DownloadThread SIN tocar Internet ni el
Escritorio del usuario:

1. Genera un MP4 de 1 segundo con el ffmpeg de /bin.
2. Lo sirve por HTTP en 127.0.0.1.
3. Descarga con bin/yt-dlp.exe usando el hilo real de la app.
4. Verifica archivo, progreso y log.

Uso:
    .venv\\Scripts\\python.exe tests\\download_test.py
====================================================================
"""

from __future__ import annotations

import functools
import http.server
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PySide6.QtCore import QCoreApplication  # noqa: E402

import core.downloader as downloader  # noqa: E402
from core.downloader import DownloadThread, construir_comando  # noqa: E402
from utils.paths import get_ffmpeg_path, get_ytdlp_path  # noqa: E402

_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def _assert(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise AssertionError(mensaje)
    print(f"  [OK] {mensaje}")


def _generar_video(destino: Path) -> None:
    ffmpeg = get_ffmpeg_path()
    if ffmpeg is None:
        raise SystemExit("FFmpeg no disponible para generar el video de prueba")
    comando = [
        str(ffmpeg),
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=320x240:rate=10",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:duration=1",
        "-c:v",
        "mpeg4",
        "-c:a",
        "aac",
        "-shortest",
        str(destino),
    ]
    completado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        errors="replace",
        creationflags=_CREATE_NO_WINDOW,
    )
    if completado.returncode != 0 or not destino.is_file():
        raise SystemExit(f"No se pudo generar el video: {completado.stderr}")


def main() -> int:
    ytdlp = get_ytdlp_path()
    _assert(ytdlp is not None, f"yt-dlp resuelto: {ytdlp}")

    temp = Path(tempfile.mkdtemp(prefix="markos_dl_"));
    servidor_dir = temp / "servidor"
    descargas = temp / "DESCARGAS"
    servidor_dir.mkdir()
    descargas.mkdir()

    print("1) Generando MP4 de prueba")
    _generar_video(servidor_dir / "prueba.mp4")
    _assert((servidor_dir / "prueba.mp4").stat().st_size > 1000, "Video generado")

    print("2) Levantando servidor HTTP local")
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(servidor_dir)
    )
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    puerto = httpd.server_address[1]
    hilo_servidor = threading.Thread(target=httpd.serve_forever, daemon=True)
    hilo_servidor.start()
    url = f"http://127.0.0.1:{puerto}/prueba.mp4"
    _assert(True, f"Servidor en {url}")

    print("3) Ejecutando DownloadThread real")
    app = QCoreApplication([])
    downloader.dir_descargas = lambda: descargas  # aislar del Escritorio

    comando = construir_comando(url, "max")
    _assert(comando[0].lower().endswith("yt-dlp.exe"), "Usa el binario de /bin")

    estados: dict = {"fin": None, "progreso": [], "log": [], "items": []}
    hilo = DownloadThread([url], "max")
    hilo.log.connect(lambda texto: estados["log"].append(texto))
    hilo.progreso.connect(lambda pct: estados["progreso"].append(pct))
    hilo.item_actual.connect(
        lambda i, total, u: estados["items"].append((i, total, u))
    )
    hilo.finalizado.connect(lambda ok, msg: estados.__setitem__("fin", (ok, msg)))
    hilo.start()

    limite = time.time() + 90
    while time.time() < limite and estados["fin"] is None:
        app.processEvents()
        time.sleep(0.05)

    _assert(estados["fin"] is not None, "El hilo terminó en menos de 90 s")
    exito, resumen = estados["fin"]
    _assert(exito is True, f"Descarga correcta: {resumen}")
    archivos = sorted(descargas.glob("*.mp4"))
    _assert(len(archivos) == 1, f"El archivo existe en DESCARGAS: {archivos}")
    _assert(archivos[0].stat().st_size > 1000, "El archivo tiene contenido")
    _assert(estados["items"] == [(1, 1, url)], "Se emitió item_actual(1,1,url)")
    _assert(estados["progreso"] and estados["progreso"][-1] == 100, "Progreso llegó a 100%")
    _assert(
        any("[download]" in linea for linea in estados["log"]),
        "El log contiene líneas de descarga de yt-dlp",
    )

    httpd.shutdown()
    hilo.wait(3000)
    print("\nDOWNLOAD TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
