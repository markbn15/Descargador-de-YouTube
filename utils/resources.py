"""
utils/resources.py
====================================================================
Acceso al banner, las instrucciones y el icono. Los assets van
incrustados en utils/assets_embedded.py (generado por build_assets.py),
por eso el .spec puede usar datas=[] y el EXE no necesita archivos
externos. En desarrollo hay fallback a la carpeta assets/.
====================================================================
"""

from __future__ import annotations

import base64
import os
from functools import lru_cache
from pathlib import Path

from utils.paths import archivo_instrucciones, dir_base

try:  # Generado por tools/build_assets.py
    from utils.assets_embedded import BANNER, ICONO_PNG_B64, INSTRUCCIONES
except Exception:  # pragma: no cover - solo si falta el archivo generado
    BANNER = ""
    INSTRUCCIONES = ""
    ICONO_PNG_B64 = ""


def _leer_asset(nombre: str) -> str:
    ruta = dir_base() / "assets" / nombre
    try:
        return ruta.read_text(encoding="utf-8")
    except OSError:
        return ""


@lru_cache(maxsize=1)
def banner() -> str:
    """Banner ASCII de MarkOS."""
    return BANNER or _leer_asset("banner.txt")


@lru_cache(maxsize=1)
def texto_instrucciones() -> str:
    """Texto completo de Instrucciones.txt."""
    return INSTRUCCIONES or _leer_asset("instrucciones.txt")


@lru_cache(maxsize=1)
def icono_png_bytes() -> bytes:
    """Bytes PNG del icono de la app (para QPixmap)."""
    if ICONO_PNG_B64:
        try:
            return base64.b64decode(ICONO_PNG_B64)
        except (ValueError, TypeError):
            pass
    ruta = dir_base() / "assets" / "icon.png"
    try:
        return ruta.read_bytes()
    except OSError:
        return b""


def asegurar_instrucciones() -> Path:
    """
    Copia Instrucciones.txt a %APPDATA% y devuelve su ruta.
    Se reescribe si el contenido cambio (nueva version de la app).
    """
    destino = archivo_instrucciones()
    texto = texto_instrucciones() or "No se pudieron cargar las instrucciones."
    try:
        if not destino.is_file() or destino.read_text(encoding="utf-8") != texto:
            destino.write_text(texto, encoding="utf-8")
    except OSError:
        # Si no se puede escribir, al menos devolvemos la ruta esperada.
        pass
    return destino


def abrir_instrucciones() -> tuple[bool, str]:
    """
    Abre Instrucciones.txt con la aplicacion asociada del sistema.
    Devuelve (exito, mensaje_de_error).
    """
    ruta = asegurar_instrucciones()
    try:
        os.startfile(str(ruta))  # type: ignore[attr-defined]
        return True, ""
    except OSError as exc:
        return False, str(exc)
    except Exception as exc:  # pragma: no cover
        return False, str(exc)
