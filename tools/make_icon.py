"""
tools/make_icon.py
====================================================================
Genera assets/icon.ico y assets/icon.png SIN dependencias externas
(ni Pillow ni ImageMagick), usando solo la libreria estandar.

Diseno: cuadrado redondeado negro (#0D0D0D), borde rojo (#E50914),
circulo rojo (#C1121F) y flecha de descarga blanca (#F5F5F5).

El ICO contiene entradas BMP de 32 bits (16..256 px), el formato mas
compatible con PyInstaller y con el Explorador de Windows. El PNG se
usa en tiempo de ejecucion para QIcon/QSystemTrayIcon.
====================================================================
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
TAMANOS_ICO = (16, 24, 32, 48, 64, 128, 256)
SUPERMUESTREO = 4

NEGRO = (13, 13, 13, 255)
ROJO = (229, 9, 20, 255)
ROJO_OSCURO = (193, 18, 31, 255)
BLANCO = (245, 245, 245, 255)
TRANSPARENTE = (0, 0, 0, 0)


# ----------------------------------------------------------------------
# Utilidades de dibujo (coordenadas normalizadas 0..1)
# ----------------------------------------------------------------------
def _dentro_rect_redondeado(x: float, y: float, r: float) -> bool:
    """Punto dentro de un rectangulo [0,1] con esquinas de radio r."""
    cx = min(max(x, r), 1.0 - r)
    cy = min(max(y, r), 1.0 - r)
    dx = x - cx
    dy = y - cy
    return dx * dx + dy * dy <= r * r


def _dentro_circulo(x: float, y: float, cx: float, cy: float, r: float) -> bool:
    dx = x - cx
    dy = y - cy
    return dx * dx + dy * dy <= r * r


def _dentro_triangulo(x: float, y: float, a, b, c) -> bool:
    """Test de punto en triangulo mediante signos barycentricos."""
    (x1, y1), (x2, y2), (x3, y3) = a, b, c

    def signo(px, py, qx, qy, rx, ry):
        return (px - rx) * (qy - ry) - (qx - rx) * (py - ry)

    d1 = signo(x, y, x1, y1, x2, y2)
    d2 = signo(x, y, x2, y2, x3, y3)
    d3 = signo(x, y, x3, y3, x1, y1)
    tiene_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    tiene_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (tiene_neg and tiene_pos)


def _pintar(pixeles: bytearray, ancho: int, x: int, y: int, color) -> None:
    i = (y * ancho + x) * 4
    pixeles[i : i + 4] = bytes(color)


def renderizar(tamano: int) -> bytes:
    """Devuelve RGBA (top-down) de tamano x tamano con supersampling."""
    escala = SUPERMUESTREO
    lado = tamano * escala
    pixeles = bytearray(lado * lado * 4)  # transparente

    # Formas del icono en coordenadas normalizadas.
    radio_fondo = 0.20
    grosor_borde = max(0.035, 1.2 / tamano)
    radio_interno = max(0.01, radio_fondo - grosor_borde)

    for py in range(lado):
        y = (py + 0.5) / lado
        for px in range(lado):
            x = (px + 0.5) / lado

            # 1) Cuadrado redondeado negro.
            if not _dentro_rect_redondeado(x, y, radio_fondo):
                continue
            color = NEGRO

            # 2) Borde rojo (anillo).
            if not _dentro_rect_redondeado(x, y, radio_interno):
                color = ROJO

            # 3) Circulo rojo oscuro.
            if _dentro_circulo(x, y, 0.5, 0.5, 0.315):
                color = ROJO_OSCURO

            # 4) Flecha de descarga blanca.
            #    Mango.
            if 0.443 <= x <= 0.557 and 0.255 <= y <= 0.565:
                color = BLANCO
            #    Cabeza triangular.
            if _dentro_triangulo(
                x, y, (0.315, 0.535), (0.685, 0.535), (0.5, 0.745)
            ):
                color = BLANCO
            #    Bandeja inferior.
            if 0.30 <= x <= 0.70 and 0.795 <= y <= 0.865:
                color = BLANCO

            _pintar(pixeles, lado, px, py, color)

    return _reducir(pixeles, lado, tamano, escala)


def _reducir(pixeles: bytearray, lado: int, tamano: int, escala: int) -> bytes:
    """Downsample por caja con alfa premultiplicado (bordes limpios)."""
    salida = bytearray(tamano * tamano * 4)
    n = escala * escala
    for y in range(tamano):
        for x in range(tamano):
            a_total = 0
            r_total = g_total = b_total = 0
            for sy in range(escala):
                base = ((y * escala + sy) * lado + x * escala) * 4
                for sx in range(escala):
                    i = base + sx * 4
                    a = pixeles[i + 3]
                    a_total += a
                    r_total += pixeles[i] * a
                    g_total += pixeles[i + 1] * a
                    b_total += pixeles[i + 2] * a
            o = (y * tamano + x) * 4
            if a_total == 0:
                salida[o : o + 4] = b"\x00\x00\x00\x00"
                continue
            salida[o] = r_total // a_total
            salida[o + 1] = g_total // a_total
            salida[o + 2] = b_total // a_total
            salida[o + 3] = a_total // n
    return bytes(salida)


# ----------------------------------------------------------------------
# Codificacion PNG / ICO
# ----------------------------------------------------------------------
def _chunk_png(tipo: bytes, datos: bytes) -> bytes:
    return (
        struct.pack(">I", len(datos))
        + tipo
        + datos
        + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    )


def png_bytes(tamano: int, rgba: bytes) -> bytes:
    """PNG RGBA de 8 bits por canal."""
    filas = bytearray()
    for y in range(tamano):
        filas.append(0)  # filtro None
        inicio = y * tamano * 4
        filas.extend(rgba[inicio : inicio + tamano * 4])

    ihdr = struct.pack(">IIBBBBB", tamano, tamano, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk_png(b"IHDR", ihdr)
        + _chunk_png(b"IDAT", zlib.compress(bytes(filas), 9))
        + _chunk_png(b"IEND", b"")
    )


def entrada_bmp(tamano: int, rgba: bytes) -> bytes:
    """Entrada ICO en formato BMP (BGRA bottom-up + mascara AND)."""
    cabecera = struct.pack(
        "<IiiHHIIiiII",
        40,               # tamano BITMAPINFOHEADER
        tamano,           # ancho
        tamano * 2,       # alto (XOR + AND)
        1,                # planos
        32,               # bits por pixel
        0,                # sin compresion
        tamano * tamano * 4,
        0,
        0,
        0,
        0,
    )

    xor = bytearray()
    for y in range(tamano - 1, -1, -1):
        inicio = y * tamano * 4
        for x in range(tamano):
            i = inicio + x * 4
            r, g, b, a = rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]
            xor += bytes((b, g, r, a))

    fila_and = ((tamano + 31) // 32) * 4
    and_mask = bytes(fila_and * tamano)
    return cabecera + bytes(xor) + and_mask


def escribir_ico(ruta: Path) -> None:
    """Escribe un .ico con entradas BMP para todos los tamanos."""
    entradas = []
    for tamano in TAMANOS_ICO:
        rgba = renderizar(tamano)
        entradas.append((tamano, entrada_bmp(tamano, rgba)))

    offset = 6 + 16 * len(entradas)
    cabecera = struct.pack("<HHH", 0, 1, len(entradas))
    directorio = bytearray()
    datos = bytearray()

    for tamano, imagen in entradas:
        directorio += struct.pack(
            "<BBBBHHII",
            0 if tamano >= 256 else tamano,
            0 if tamano >= 256 else tamano,
            0,
            0,
            1,
            32,
            len(imagen),
            offset,
        )
        datos += imagen
        offset += len(imagen)

    ruta.write_bytes(cabecera + bytes(directorio) + bytes(datos))


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)

    # PNG de 256 px para QIcon (Qt tiene soporte PNG integrado).
    png = png_bytes(256, renderizar(256))
    (ASSETS / "icon.png").write_bytes(png)

    escribir_ico(ASSETS / "icon.ico")

    print(f"[OK] {ASSETS / 'icon.ico'}")
    print(f"[OK] {ASSETS / 'icon.png'} ({len(png)} bytes)")


if __name__ == "__main__":
    main()
