"""
utils/logger.py
====================================================================
Log rotativo en %APPDATA%/MarkOS_Downloader/app.log
(1 MB por archivo, 3 respaldos). Nunca se muestra un traceback crudo
al usuario: los errores tecnicos van al archivo y a la UI se envia un
mensaje legible.
====================================================================
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from utils.paths import APP_NAME, archivo_log

_FORMATO = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_logger_raiz = logging.getLogger("markos")


def configurar_logging() -> logging.Logger:
    """Configura (una sola vez) el log de archivo y, en dev, de consola."""
    if _logger_raiz.handlers:
        return _logger_raiz

    _logger_raiz.setLevel(logging.INFO)
    _logger_raiz.propagate = False
    formateador = logging.Formatter(_FORMATO, datefmt="%Y-%m-%d %H:%M:%S")

    try:
        manejador_archivo = RotatingFileHandler(
            archivo_log(),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        manejador_archivo.setFormatter(formateador)
        manejador_archivo.setLevel(logging.INFO)
        _logger_raiz.addHandler(manejador_archivo)
    except OSError as exc:
        # Si no se puede escribir el log no impedimos que arranque la app.
        print(f"[MarkOS] No se pudo abrir app.log: {exc}", file=sys.stderr)

    # En el EXE --windowed sys.stderr puede ser None.
    if sys.stderr is not None:
        consola = logging.StreamHandler(sys.stderr)
        consola.setFormatter(formateador)
        consola.setLevel(logging.INFO)
        _logger_raiz.addHandler(consola)

    _logger_raiz.info("===== %s iniciado =====", APP_NAME)
    return _logger_raiz


def obtener_logger(nombre: str) -> logging.Logger:
    """Logger hijo con nombre corto (markos.core, markos.ui...)."""
    return logging.getLogger(f"markos.{nombre}")
