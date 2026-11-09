"""
tools/descargar_binarios.py
====================================================================
Descarga los binarios que viajan dentro del EXE:

    bin/yt-dlp.exe
    bin/ffmpeg.exe   (opcional, recomendado)
    bin/ffprobe.exe  (opcional, recomendado)

Fuentes oficiales:
    https://github.com/yt-dlp/yt-dlp/releases/latest
    https://www.gyan.dev/ffmpeg/builds/  (essentials)
    https://www.gyan.dev/ffmpeg/builds/  (essentials) -> ffprobe incluido

Uso:
    python tools/descargar_binarios.py
    python tools/descargar_binarios.py --sin-ffmpeg
    python tools/descargar_binarios.py --forzar
====================================================================
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BIN = RAIZ / "bin"

URL_YTDLP = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
URL_FFMPEG = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

USER_AGENT = "MarkOS-Downloader-Suite-Build/1.1"


def _mb(bytes_: int) -> str:
    return f"{bytes_ / (1024 * 1024):.1f} MB"


def _descargar(url: str, destino: Path, verificar_exe: bool = True) -> None:
    """Descarga con progreso simple y, si aplica, verificacion de cabecera PE."""
    print(f"[>] Descargando {url}")
    peticion = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(peticion, timeout=120) as respuesta:
        total = int(respuesta.headers.get("Content-Length") or 0)
        leido = 0
        ultimo_pct = -10
        with destino.open("wb") as f:
            while True:
                bloque = respuesta.read(1024 * 256)
                if not bloque:
                    break
                f.write(bloque)
                leido += len(bloque)
                if total:
                    pct = int(leido * 100 / total)
                    if pct >= ultimo_pct + 10:
                        ultimo_pct = pct
                        print(f"    {pct:3d}%  ({_mb(leido)} / {_mb(total)})")

    if destino.stat().st_size < 1024 * 1024:
        raise RuntimeError(f"Archivo demasiado pequeno: {destino}")

    # Un .exe de Windows debe empezar por "MZ".
    if verificar_exe:
        with destino.open("rb") as f:
            if f.read(2) != b"MZ":
                raise RuntimeError(f"El archivo descargado no es un EXE valido: {destino}")

    print(f"[OK] {destino.name} ({_mb(destino.stat().st_size)})")


def descargar_ytdlp(forzar: bool) -> None:
    destino = BIN / "yt-dlp.exe"
    if destino.is_file() and not forzar:
        print(f"[=] {destino} ya existe (usa --forzar para actualizarlo)")
        return
    _descargar(URL_YTDLP, destino)


def descargar_ffmpeg(forzar: bool) -> None:
    ffmpeg = BIN / "ffmpeg.exe"
    ffprobe = BIN / "ffprobe.exe"
    if ffmpeg.is_file() and ffprobe.is_file() and not forzar:
        print(f"[=] {ffmpeg.name} y {ffprobe.name} ya existen (usa --forzar)")
        return

    print(f"[>] Descargando FFmpeg essentials desde {URL_FFMPEG}")
    with tempfile.TemporaryDirectory(prefix="markos_ffmpeg_") as tmp:
        zip_ruta = Path(tmp) / "ffmpeg.zip"
        _descargar(URL_FFMPEG, zip_ruta, verificar_exe=False)

        print("[>] Extrayendo ffmpeg.exe y ffprobe.exe...")
        extraidos: dict[str, Path] = {}
        with zipfile.ZipFile(zip_ruta) as zf:
            for miembro in zf.namelist():
                nombre = Path(miembro).name.lower()
                if nombre in ("ffmpeg.exe", "ffprobe.exe") and nombre not in extraidos:
                    salida = Path(tmp) / nombre
                    with zf.open(miembro) as origen, salida.open("wb") as destino_f:
                        shutil.copyfileobj(origen, destino_f)
                    extraidos[nombre] = salida

        faltan = {"ffmpeg.exe", "ffprobe.exe"} - set(extraidos)
        if faltan:
            raise RuntimeError(f"No se encontraron en el ZIP: {', '.join(sorted(faltan))}")

        for nombre, origen in extraidos.items():
            destino = BIN / nombre
            shutil.copy2(origen, destino)
            print(f"[OK] {destino.name} ({_mb(destino.stat().st_size)})")


def main() -> int:
    parser = argparse.ArgumentParser(description="Descarga yt-dlp y FFmpeg para /bin")
    parser.add_argument(
        "--sin-ffmpeg",
        action="store_true",
        help="No descargar FFmpeg (EXE mas pequeno, sin fusion MP3/MP4)",
    )
    parser.add_argument(
        "--forzar",
        action="store_true",
        help="Volver a descargar aunque los archivos ya existan",
    )
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    BIN.mkdir(parents=True, exist_ok=True)

    try:
        descargar_ytdlp(args.forzar)
        if not args.sin_ffmpeg:
            descargar_ffmpeg(args.forzar)
        else:
            print("[=] FFmpeg omitido por --sin-ffmpeg")
    except (urllib.error.URLError, TimeoutError, OSError, RuntimeError, zipfile.BadZipFile) as exc:
        print(f"\n[!] Error descargando binarios: {exc}", file=sys.stderr)
        print("    Comprueba tu conexion o descarga los archivos manualmente en /bin.", file=sys.stderr)
        return 1

    print("\n[OK] Binarios listos en:", BIN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
