"""
core/interceptor.py
====================================================================
Interceptor de portapapeles en un QThread independiente.

Comportamiento heredado de interceptor_links.py:
  * Crea "Desktop/Descargador casero" y VACIA enlaces.txt al iniciar.
  * Sondea el portapapeles cada 0.4 s.
  * Captura cualquier texto que empiece por http:// o https://.
  * Solo evita duplicados CONSECUTIVOS (last_url), igual que el original.
  * Beep(1000, 150) al capturar.
  * ESC global -> detiene la captura y abre la carpeta. En la GUI no
    cierra la aplicacion: solo detiene el interceptor (requisito B).

Se usa threading.Event para poder detener el hilo sin cerrar la app y
keyboard.unhook_all() para liberar el atajo global.
====================================================================
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pyperclip
from PySide6.QtCore import QThread, Signal

from utils.logger import obtener_logger
from utils.paths import archivo_enlaces, dir_trabajo
from utils.sound import beep

_log = obtener_logger("interceptor")

INTERVALO_SONDEO = 0.4  # segundos, identico al time.sleep(0.4) original


class InterceptorThread(QThread):
    """Hilo que monitorea el portapapeles y escribe en enlaces.txt."""

    enlace_capturado = Signal(str, int)   # (url, total de la sesion)
    estado_cambiado = Signal(bool, str)   # (activo, texto de estado)
    aviso = Signal(str)                   # problema no fatal
    error = Signal(str)                   # problema fatal (hilo termina)
    solicitud_abrir_carpeta = Signal()    # ESC pulsado
    finalizado = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._detener = threading.Event()
        self._ultimo_enlace = ""
        self._total = 0
        self._ultimo_error_portapapeles = 0.0
        self._hotkey_registrado = False

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def detener(self) -> None:
        """Solicita el fin del sondeo (seguro desde el hilo de la GUI)."""
        self._detener.set()

    @property
    def activo(self) -> bool:
        return self.isRunning() and not self._detener.is_set()

    # ------------------------------------------------------------------
    # Ciclo del hilo
    # ------------------------------------------------------------------
    def run(self) -> None:  # noqa: D401 (metodo de Qt)
        self._detener.clear()
        self._ultimo_enlace = ""
        self._total = 0

        # 1) Preparar rutas y vaciar enlaces.txt (setup_environment original).
        try:
            dir_trabajo().mkdir(parents=True, exist_ok=True)
            archivo_enlaces().write_text("", encoding="utf-8")
        except OSError as exc:
            _log.error("No se pudo preparar enlaces.txt: %s", exc)
            self.error.emit(
                "No se pudo crear la carpeta de trabajo o enlaces.txt.\n"
                f"Detalle: {exc}"
            )
            self.estado_cambiado.emit(False, "Interceptor detenido por error")
            self.finalizado.emit()
            return

        # 2) Registrar ESC global (puede fallar por permisos).
        self._registrar_hotkey()

        self.estado_cambiado.emit(True, "Interceptor activo: copia un enlace")
        _log.info("Interceptor iniciado (enlaces.txt vaciado)")

        # 3) Bucle de sondeo.
        try:
            while not self._detener.is_set():
                try:
                    actual = pyperclip.paste().strip()

                    # Misma condicion exacta que el script original.
                    if (
                        actual
                        and actual != self._ultimo_enlace
                        and actual.startswith(("http://", "https://"))
                    ):
                        self._agregar_enlace(actual)

                except Exception as exc:  # portapapeles bloqueado, etc.
                    self._reportar_error_portapapeles(exc)
                    self._detener.wait(1.0)
                    continue

                self._detener.wait(INTERVALO_SONDEO)
        finally:
            # Libera el hook global y evita que ESC siga secuestrado.
            self._liberar_hotkey()
            self.estado_cambiado.emit(False, "Interceptor detenido")
            self.finalizado.emit()
            _log.info("Interceptor detenido (%d enlaces en la sesion)", self._total)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------
    def _agregar_enlace(self, url: str) -> None:
        """Escribe la URL, actualiza el estado y emite la senal a la UI."""
        try:
            with archivo_enlaces().open("a", encoding="utf-8") as f:
                f.write(url + "\n")
        except OSError as exc:
            _log.error("No se pudo escribir en enlaces.txt: %s", exc)
            self.error.emit(f"No se pudo guardar el enlace en enlaces.txt:\n{exc}")
            self._detener.set()
            return

        self._ultimo_enlace = url
        self._total += 1
        beep(1000, 150)  # identico al original
        self.enlace_capturado.emit(url, self._total)

    def _reportar_error_portapapeles(self, exc: Exception) -> None:
        """Evita inundar la UI: como maximo un aviso cada 15 segundos."""
        ahora = time.monotonic()
        if ahora - self._ultimo_error_portapapeles >= 15:
            self._ultimo_error_portapapeles = ahora
            _log.warning("Portapapeles no disponible: %s", exc)
            self.aviso.emit(
                "No se pudo leer el portapapeles (puede estar bloqueado por "
                "otra aplicacion). Se reintentara automaticamente."
            )

    def _al_pulsar_esc(self) -> None:
        """Callback del hotkey global ESC (hilo interno de keyboard)."""
        self._detener.set()
        self.solicitud_abrir_carpeta.emit()

    def _registrar_hotkey(self) -> None:
        try:
            import keyboard

            keyboard.add_hotkey("esc", self._al_pulsar_esc, suppress=False)
            self._hotkey_registrado = True
        except Exception as exc:
            self._hotkey_registrado = False
            _log.warning("No se pudo registrar ESC global: %s", exc)
            self.aviso.emit(
                "No se pudo activar la tecla ESC global (permisos insuficientes). "
                "Usa el boton Detener de la interfaz."
            )

    def _liberar_hotkey(self) -> None:
        if not self._hotkey_registrado:
            return
        try:
            import keyboard

            keyboard.unhook_all()
        except Exception as exc:
            _log.warning("No se pudieron liberar los hooks de teclado: %s", exc)
        finally:
            self._hotkey_registrado = False

    # Compatibilidad con codigo que espere la ruta del archivo.
    @staticmethod
    def ruta_enlaces() -> Path:
        return archivo_enlaces()
