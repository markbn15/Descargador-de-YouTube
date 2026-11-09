"""
tools/build_assets.py
====================================================================
Incrusta banner, instrucciones y el icono PNG dentro de un modulo
Python (utils/assets_embedded.py). Asi el .spec puede usar datas=[]
y el EXE sigue siendo un unico archivo autocontenido, sin depender de
rutas externas ni de sys._MEIPASS para los assets.

Uso:  python tools/build_assets.py
====================================================================
"""

from __future__ import annotations

import base64
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
DESTINO = RAIZ / "utils" / "assets_embedded.py"

CABECERA = '''"""
utils/assets_embedded.py
====================================================================
ARCHIVO GENERADO AUTOMATICAMENTE por tools/build_assets.py.
No lo edites a mano: modifica assets/ y vuelve a ejecutar:
    python tools/build_assets.py
====================================================================
"""

# Banner ASCII de MarkOS (assets/banner.txt)
BANNER = {banner}

# Instrucciones que se copian a %APPDATA% (assets/instrucciones.txt)
INSTRUCCIONES = {instrucciones}

# Icono 256x256 en PNG codificado en base64 (assets/icon.png)
ICONO_PNG_B64 = (
{icono}
)
'''


def _leer_texto(nombre: str) -> str:
    ruta = ASSETS / nombre
    if not ruta.is_file():
        raise SystemExit(f"[!] Falta el archivo: {ruta}")
    return ruta.read_text(encoding="utf-8")


def main() -> None:
    banner = _leer_texto("banner.txt")
    instrucciones = _leer_texto("instrucciones.txt")

    png = ASSETS / "icon.png"
    if not png.is_file():
        raise SystemExit(
            f"[!] Falta {png}. Ejecuta primero: python tools/make_icon.py"
        )
    icono_b64 = base64.b64encode(png.read_bytes()).decode("ascii")
    lineas_icono = "\n".join(
        f'    "{icono_b64[i:i + 88]}"' for i in range(0, len(icono_b64), 88)
    )

    contenido = CABECERA.format(
        banner=repr(banner),
        instrucciones=repr(instrucciones),
        icono=lineas_icono,
    )
    DESTINO.write_text(contenido, encoding="utf-8")

    print(f"[OK] {DESTINO}")
    print(f"     banner: {len(banner)} caracteres")
    print(f"     instrucciones: {len(instrucciones)} caracteres")
    print(f"     icono PNG: {len(icono_b64)} caracteres base64")


if __name__ == "__main__":
    main()
