"""
utils/integration.py
====================================================================
Integracion con Windows: protocolo markos:// y arranque automatico.

Todo se escribe en HKEY_CURRENT_USER, por lo que no hacen falta
permisos de administrador y se puede deshacer desde Preferencias.

    markos://add?url=https%3A%2F%2F...   anade un enlace a la cola
    markos://download?url=...            anade y descarga
    markos://capture                     inicia la captura

El comando registrado apunta al EXE actual (o a pythonw + main.py en
modo desarrollo).
====================================================================
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from utils.logger import obtener_logger
from utils.paths import APP_NAME, dir_ejecutable, esta_congelado

_log = obtener_logger("integration")

RAIZ_PROTOCOLO = r"Software\Classes\markos"
RUTA_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALOR_RUN = "MarkOS_Downloader"


def _winreg():
    try:
        import winreg  # type: ignore

        return winreg
    except Exception:  # pragma: no cover - solo Windows
        return None


def _comando_protocolo() -> str:
    if esta_congelado():
        return f'"{Path(sys.executable).resolve()}" "%1"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    ejecutable = pythonw if pythonw.is_file() else Path(sys.executable)
    main_py = dir_ejecutable() / "main.py"
    return f'"{ejecutable}" "{main_py}" "%1"'


def _comando_inicio() -> str:
    if esta_congelado():
        return f'"{Path(sys.executable).resolve()}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    ejecutable = pythonw if pythonw.is_file() else Path(sys.executable)
    main_py = dir_ejecutable() / "main.py"
    return f'"{ejecutable}" "{main_py}" --minimized'


# ----------------------------------------------------------------------
# Protocolo markos://
# ----------------------------------------------------------------------
def protocolo_registrado() -> bool:
    """True si HKCU tiene un comando para markos://."""
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RAIZ_PROTOCOLO + r"\shell\open\command",
        ) as clave:
            comando, _tipo = winreg.QueryValueEx(clave, "")
        return bool(str(comando).strip())
    except OSError:
        return False


def registrar_protocolo() -> bool:
    """Registra markos:// en HKCU. Devuelve True si quedo operativo."""
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RAIZ_PROTOCOLO, 0, winreg.KEY_WRITE
        ) as clave:
            winreg.SetValueEx(clave, "", 0, winreg.REG_SZ, "URL:MarkOS Downloader")
            winreg.SetValueEx(clave, "URL Protocol", 0, winreg.REG_SZ, "")
            winreg.SetValueEx(
                clave, "FriendlyTypeName", 0, winreg.REG_SZ, APP_NAME
            )

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RAIZ_PROTOCOLO + r"\DefaultIcon",
            0,
            winreg.KEY_WRITE,
        ) as clave:
            icono = (
                Path(sys.executable).resolve()
                if esta_congelado()
                else dir_ejecutable() / "assets" / "icon.ico"
            )
            winreg.SetValueEx(clave, "", 0, winreg.REG_SZ, str(icono))

        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            RAIZ_PROTOCOLO + r"\shell\open\command",
            0,
            winreg.KEY_WRITE,
        ) as clave:
            winreg.SetValueEx(
                clave, "", 0, winreg.REG_SZ, _comando_protocolo()
            )
        _log.info("Protocolo markos:// registrado")
        return True
    except OSError as exc:
        _log.warning("No se pudo registrar markos://: %s", exc)
        return False


def quitar_protocolo() -> bool:
    """Elimina las claves de markos:// de HKCU."""
    winreg = _winreg()
    if winreg is None:
        return False
    subclaves = [
        RAIZ_PROTOCOLO + r"\shell\open\command",
        RAIZ_PROTOCOLO + r"\shell\open",
        RAIZ_PROTOCOLO + r"\shell",
        RAIZ_PROTOCOLO + r"\DefaultIcon",
        RAIZ_PROTOCOLO,
    ]
    for ruta in subclaves:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, ruta)
        except OSError:
            pass
    _log.info("Protocolo markos:// eliminado")
    return not protocolo_registrado()


# ----------------------------------------------------------------------
# Inicio con Windows
# ----------------------------------------------------------------------
def inicio_windows_activo() -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUTA_RUN) as clave:
            valor, _tipo = winreg.QueryValueEx(clave, VALOR_RUN)
        return bool(str(valor).strip())
    except OSError:
        return False


def activar_inicio_windows() -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUTA_RUN, 0, winreg.KEY_SET_VALUE
        ) as clave:
            winreg.SetValueEx(
                clave, VALOR_RUN, 0, winreg.REG_SZ, _comando_inicio()
            )
        _log.info("Inicio con Windows activado")
        return True
    except OSError as exc:
        _log.warning("No se pudo activar el inicio con Windows: %s", exc)
        return False


def desactivar_inicio_windows() -> bool:
    winreg = _winreg()
    if winreg is None:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUTA_RUN, 0, winreg.KEY_SET_VALUE
        ) as clave:
            winreg.DeleteValue(clave, VALOR_RUN)
    except OSError:
        pass
    return not inicio_windows_activo()


def sincronizar_inicio_windows(activo: bool) -> bool:
    """Aplica el estado deseado y refresca la ruta del EXE si esta activo."""
    if os.name != "nt":
        return False
    if activo:
        return activar_inicio_windows()
    return desactivar_inicio_windows()


def sincronizar_protocolo(activo: bool) -> bool:
    """Aplica el estado deseado y refresca la ruta del EXE si esta activo."""
    if os.name != "nt":
        return False
    if activo:
        return registrar_protocolo()
    return quitar_protocolo()


__all__ = [
    "activar_inicio_windows",
    "desactivar_inicio_windows",
    "inicio_windows_activo",
    "protocolo_registrado",
    "quitar_protocolo",
    "registrar_protocolo",
    "sincronizar_inicio_windows",
    "sincronizar_protocolo",
]
