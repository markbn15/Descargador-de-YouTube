"""
utils/sound.py
====================================================================
Pitidos de confirmacion con winsound. Se aislan y protegen para que un
fallo de audio (tarjeta ocupada, RDP, etc.) jamas rompa la logica.
====================================================================
"""

from __future__ import annotations

import os


def beep(frecuencia: int, duracion_ms: int) -> None:
    """Emite un beep sincrono en Windows; en otros SO no hace nada."""
    if os.name != "nt":
        return
    try:
        import winsound

        winsound.Beep(int(frecuencia), int(duracion_ms))
    except Exception:
        # Sin sonido disponible: no es un error critico.
        pass
