"""
main.py
====================================================================
Punto de entrada de MarkOS Downloader Suite.

    python main.py

En produccion este archivo es el script que PyInstaller convierte en
"MarkOS Downloader Suite.exe" (--onefile --windowed).
====================================================================
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QMessageBox

from ui.main_window import VentanaPrincipal
from ui.theme import aplicar_tema, icono_app
from utils.integration import (
    activar_inicio_windows,
    desactivar_inicio_windows,
    registrar_protocolo,
    quitar_protocolo,
)
from utils.logger import configurar_logging
from utils.paths import APP_ID, APP_NAME, APP_VERSION
from utils.urls import parsear_markos

_log = None


def _configurar_windows() -> None:
    """
    AppUserModelID propio para que Windows agrupe la app y muestre bien
    el icono en la barra de tareas. Qt ya gestiona el DPI en Qt6.
    """
    if os.name != "nt":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _instalar_manejo_errores() -> None:
    """
    Evita que el usuario vea tracebacks crudos: el detalle va al log y
    en pantalla se muestra un mensaje legible. Tambien cubre excepciones
    de hilos secundarios (keyboard, etc.).
    """
    global _log

    def _hook_excepciones(tipo, valor, traza):
        try:
            _log.exception(
                "Excepción no controlada",
                exc_info=(tipo, valor, traza),
            )
        except Exception:
            pass

        try:
            if QApplication.instance() is not None:
                QMessageBox.critical(
                    None,
                    "Error inesperado",
                    "Se produjo un error inesperado en MarkOS Downloader "
                    "Suite.\n\n"
                    f"{tipo.__name__}: {valor}\n\n"
                    "El detalle técnico se guardó en app.log "
                    "(%APPDATA%\\MarkOS_Downloader).",
                )
        except Exception:
            pass

    def _hook_hilos(args):
        try:
            nombre = args.thread.name if args.thread else "desconocido"
            _log.error(
                "Error no controlado en el hilo '%s': %s",
                nombre,
                args.exc_value,
            )
        except Exception:
            pass

    sys.excepthook = _hook_excepciones
    threading.excepthook = _hook_hilos


def main() -> int:
    _configurar_windows()
    logger = configurar_logging()
    global _log
    _log = logger
    _instalar_manejo_errores()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName("MarkOS")
    app.setWindowIcon(icono_app())

    fuente = QFont("Segoe UI")
    fuente.setPointSize(10)
    app.setFont(fuente)

    aplicar_tema(app)

    arranque = parsear_markos(sys.argv[1:])
    ventana = VentanaPrincipal(
        urls_iniciales=list(arranque["urls"]),  # type: ignore[arg-type]
        capturar=bool(arranque["capturar"]),
        descargar=bool(arranque["descargar"]),
        minimizado=bool(arranque["minimizado"]),
    )

    # Sincroniza la integracion con Windows (siempre actualiza la ruta del
    # EXE por si el usuario movio o renombro el archivo).
    if os.name == "nt":
        try:
            if ventana.config.get("protocolo_registrado", True):
                registrar_protocolo()
            else:
                quitar_protocolo()
            if ventana.config.get("iniciar_con_windows", False):
                activar_inicio_windows()
            else:
                desactivar_inicio_windows()
        except Exception as exc:
            logger.warning("No se pudo sincronizar la integración: %s", exc)

    ventana.show()
    if bool(arranque["minimizado"]):
        QTimer.singleShot(0, ventana.ocultar_a_bandeja)
    else:
        # Verificacion de dependencias tras mostrar la ventana: el dialogo
        # necesita un padre ya visible para centrarse correctamente.
        QTimer.singleShot(500, ventana.verificar_dependencias)

    logger.info("%s v%s arrancada", APP_NAME, APP_VERSION)
    return app.exec()


if __name__ == "__main__":
    try:
        codigo = main()
    except Exception as exc:  # ultimo cortafuegos antes de morir
        try:
            if _log is not None:
                _log.exception("Fallo fatal al iniciar la aplicación")
        except Exception:
            pass
        print(f"[MarkOS] Fallo fatal: {exc}", file=sys.stderr)
        codigo = 1
    sys.exit(codigo)
