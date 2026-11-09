"""
tests/smoke_test.py
====================================================================
Prueba de humo segura (no descarga, no mata procesos):
  * arranca la GUI en modo offscreen,
  * verifica las 3 paginas y la persistencia de calidad,
  * arranca/detiene el interceptor usando una carpeta temporal
    (NUNCA toca el enlaces.txt real del usuario),
  * comprueba argumentos de yt-dlp y el icono generado.

Uso:
    .venv\\Scripts\\python.exe tests\\smoke_test.py
====================================================================
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

# Aisla config/log en una carpeta temporal ANTES de importar la app.
_TEMP = Path(tempfile.mkdtemp(prefix="markos_smoke_"))
os.environ["APPDATA"] = str(_TEMP / "appdata")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pyperclip  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

import core.interceptor as interceptor_mod  # noqa: E402
from core.downloader import args_calidad, construir_comando  # noqa: E402
from ui.main_window import VentanaPrincipal  # noqa: E402
from ui.theme import aplicar_tema  # noqa: E402
from utils.paths import (  # noqa: E402
    APP_VERSION,
    archivo_config,
    dir_appdata,
    get_ffmpeg_path,
    get_ytdlp_path,
)
from utils.settings import Configuracion  # noqa: E402


def _assert(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise AssertionError(mensaje)
    print(f"  [OK] {mensaje}")


def main() -> int:
    print("1) Argumentos de yt-dlp")
    _assert(
        args_calidad("mp3")
        == ["-x", "--audio-format", "mp3", "--audio-quality", "0"],
        "MP3 conserva los argumentos originales",
    )
    _assert(
        args_calidad("720p")
        == [
            "-f",
            "bestvideo[height<=720]+bestaudio/best[height<=720]",
            "--merge-output-format",
            "mp4",
        ],
        "720p conserva los argumentos originales",
    )
    _assert(args_calidad("max") == [], "Máxima no fuerza formato")
    comando = construir_comando("https://example.com/video", "1080p")
    _assert(comando[-1] == "https://example.com/video", "La URL va al final")
    _assert("--newline" in comando, "Se añade --newline para el log en vivo")

    print("2) Rutas de binarios")
    print(f"  yt-dlp: {get_ytdlp_path()}")
    print(f"  ffmpeg: {get_ffmpeg_path()}")
    _assert(get_ytdlp_path() is not None, "yt-dlp localizable")

    print("3) Interfaz Qt (offscreen)")
    app = QApplication([])
    aplicar_tema(app)
    ventana = VentanaPrincipal()
    ventana.show()
    app.processEvents()
    _assert(ventana._stack.count() == 3, "La ventana tiene 3 páginas")
    ventana.cambiar_pagina(1)
    _assert(ventana._stack.currentIndex() == 1, "Navegación por pasos funciona")
    _assert(
        len(ventana._botones_paso) == 3 and ventana._botones_paso[1].isChecked(),
        "El stepper superior marca el paso activo",
    )
    _assert(
        ventana.lbl_paso.text().startswith("Paso 2 de 3"),
        "La barra inferior muestra el paso actual",
    )
    _assert(ventana._anim_pagina is not None, "La transición de página se anima")

    ventana.ir_paso_siguiente()
    _assert(
        ventana._stack.currentIndex() == 2
        and not ventana.boton_siguiente.isEnabled(),
        "Siguiente avanza al último paso y se deshabilita",
    )
    ventana.ir_paso_siguiente()
    _assert(ventana._stack.currentIndex() == 2, "Siguiente no se sale del rango")
    ventana.ir_paso_anterior()
    _assert(
        ventana._stack.currentIndex() == 1 and ventana.boton_atras.isEnabled(),
        "Atrás regresa al paso anterior",
    )

    ventana.page_descargador.set_calidad("1080p")
    app.processEvents()
    _assert(
        ventana.page_descargador.calidad_actual() == "1080p",
        "Selector de calidad funciona",
    )
    _assert(
        Configuracion().get("calidad") == "1080p",
        "La calidad se persiste en config.json",
    )
    _assert(archivo_config().is_file(), f"config.json creado en {dir_appdata()}")
    _assert(APP_VERSION in ventana.lbl_version.text(), "Versión en la barra de estado")
    _assert(
        APP_VERSION in ventana.lbl_marca_version.text(),
        "Versión visible en la barra superior",
    )

    # Regresión de maquetación: en una pantalla de 720p (cliente ~640 px)
    # ninguna página debe comprimirse ni solaparse.
    ventana.resize(1280, 640)
    app.processEvents()
    _assert(
        ventana.minimumSize().height() <= 640,
        "La ventana cabe en pantallas de 720p",
    )
    for indice, pagina in enumerate(
        (ventana.page_interceptor, ventana.page_descargador, ventana.page_historial)
    ):
        ventana.cambiar_pagina(indice, animar=False)
        app.processEvents()
        _assert(
            pagina.height() >= pagina.minimumSizeHint().height(),
            f"La página {indice + 1} conserva su altura mínima",
        )
    ventana.cambiar_pagina(1, animar=False)
    app.processEvents()

    print("3b) Prioridad de binarios actualizados")
    import utils.paths as paths_mod

    original_appdata = paths_mod.dir_appdata
    try:
        appdata_fake = _TEMP / "appdata_actualizado"
        (appdata_fake / "bin").mkdir(parents=True, exist_ok=True)
        falso_ytdlp = appdata_fake / "bin" / "yt-dlp.exe"
        falso_ytdlp.write_bytes(b"MZ" + b"\x00" * 2048)
        paths_mod.dir_appdata = lambda: appdata_fake
        _assert(
            paths_mod.get_ytdlp_path() == falso_ytdlp,
            "El binario actualizado tiene prioridad sobre el incluido",
        )
        _assert(
            paths_mod.dir_bin_usuario() == appdata_fake / "bin",
            "Carpeta de actualizaciones correcta",
        )
    finally:
        paths_mod.dir_appdata = original_appdata
    _assert(
        paths_mod.get_ytdlp_path() is not None,
        "Al restaurar, vuelve a usarse el binario incluido",
    )

    print("3c) Botón Limpiar enlaces")
    import ui.main_window as mw_limpio

    originales_limpio = (
        mw_limpio.archivo_enlaces,
        mw_limpio.asegurar_entorno,
        mw_limpio.contar_enlaces,
        mw_limpio.DialogoConfirmacion,
    )

    class _ConfirmarSi:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    carpeta_limpia = _TEMP / "limpia"
    carpeta_limpia.mkdir(parents=True, exist_ok=True)
    archivo_fake = carpeta_limpia / "enlaces.txt"
    archivo_fake.write_text(
        "https://example.com/a\nhttps://example.com/b\n", encoding="utf-8"
    )
    try:
        mw_limpio.archivo_enlaces = lambda: archivo_fake
        mw_limpio.asegurar_entorno = lambda *a, **k: None
        mw_limpio.contar_enlaces = lambda: 2
        mw_limpio.DialogoConfirmacion = _ConfirmarSi
        ventana.page_interceptor.agregar_enlace("https://example.com/a")
        ventana.limpiar_enlaces()
        _assert(archivo_fake.read_text(encoding="utf-8") == "", "enlaces.txt queda vacío")
        _assert(
            ventana.page_interceptor.lista.count() == 0,
            "La lista visible se limpia",
        )
        _assert(
            ventana.lbl_cola.text() == "Enlaces en cola: 0",
            "El contador de cola vuelve a cero",
        )
        _assert(
            "0 capturados" in ventana.page_interceptor.lbl_contador_lista.text(),
            "El contador de capturados se reinicia",
        )
    finally:
        (
            mw_limpio.archivo_enlaces,
            mw_limpio.asegurar_entorno,
            mw_limpio.contar_enlaces,
            mw_limpio.DialogoConfirmacion,
        ) = originales_limpio

    print("3d) Diálogo del actualizador")
    import ui.updater_dialog as upd_dialog

    dialogo_upd = upd_dialog.DialogoActualizador(ventana)
    _assert(
        dialogo_upd.chk_ytdlp.isChecked() and not dialogo_upd.chk_ffmpeg.isChecked(),
        "yt-dlp viene marcado por defecto",
    )
    _assert(
        str(paths_mod.dir_bin_usuario()) in dialogo_upd.lbl_actual.text(),
        "El diálogo muestra la carpeta de destino",
    )

    avisos: list[str] = []
    original_info = upd_dialog.QMessageBox.information
    try:
        upd_dialog.QMessageBox.information = (
            lambda *a, **k: avisos.append(a[2] if len(a) > 2 else "")
        )
        dialogo_upd.chk_ytdlp.setChecked(False)
        dialogo_upd._iniciar()
        _assert(
            bool(avisos) and dialogo_upd._hilo is None,
            "Sin dependencias seleccionadas no se lanza la descarga",
        )
    finally:
        upd_dialog.QMessageBox.information = original_info
        dialogo_upd.chk_ytdlp.setChecked(True)
        dialogo_upd.deleteLater()

    print("3e) Historial, perfiles y versiones")
    from core.history import Historial
    from core.updates import comparar_versiones
    from utils.urls import calidad_para_url, extraer_urls, parsear_markos

    historial_prueba = Historial(_TEMP / "historial_test.db")
    id_ok = historial_prueba.anadir_pendiente(
        "https://youtube.com/watch?v=1", "max", origen="prueba"
    )
    historial_prueba.marcar_completada(
        id_ok,
        archivo=str(_TEMP / "video.mp4"),
        tamano=2048,
        titulo="Demo",
        calidad="1080p",
    )
    id_error = historial_prueba.anadir_pendiente(
        "https://example.com/fallo", "720p"
    )
    historial_prueba.marcar_error(id_error, "fallo de prueba")
    stats = historial_prueba.estadisticas()
    _assert(
        stats["completadas"] == 1 and stats["errores"] == 1,
        "El historial registra completadas y errores",
    )
    _assert(
        historial_prueba.obtener(id_ok)["archivo"].endswith("video.mp4"),
        "El historial guarda el archivo descargado",
    )
    _assert(
        calidad_para_url(
            "https://music.youtube.com/watch?v=2",
            {"youtube.com": "720p"},
            "max",
        )
        == "720p",
        "El perfil del dominio se aplica a los subdominios",
    )
    _assert(
        calidad_para_url(
            "https://example.com/v", {"example.com": "480p"}, "max",
            {"https://example.com/v": "mp3"},
        )
        == "mp3",
        "El reintento conserva su calidad original",
    )
    _assert(
        extraer_urls("mira https://example.com/a y https://example.com/b")
        == ["https://example.com/a", "https://example.com/b"],
        "Se extraen varias URLs de un texto",
    )
    arranque = parsear_markos(
        ["markos://add?url=https%3A%2F%2Fexample.com%2Fa", "--minimized"]
    )
    _assert(
        arranque["urls"] == ["https://example.com/a"] and arranque["minimizado"],
        "El protocolo markos:// y --minimized se interpretan",
    )
    _assert(
        comparar_versiones("V1.51", "1.51.0") == 0
        and comparar_versiones("V1.52", "1.51.0") > 0
        and comparar_versiones("V1.7", "V1.51") > 0,
        "La comparación de versiones de GitHub es correcta",
    )
    _assert(
        ventana.page_historial is not None
        and ventana._stack.count() == 3,
        "El Historial sustituye a la antigua página de pánico",
    )
    historial_prueba.cerrar()

    print("4) Interceptor con carpeta temporal")
    carpeta = _TEMP / "Descargador casero"
    carpeta.mkdir(parents=True, exist_ok=True)

    # Monkeypatch: evita tocar el Escritorio real.
    interceptor_mod.dir_trabajo = lambda: carpeta
    interceptor_mod.archivo_enlaces = lambda: carpeta / "enlaces.txt"

    portapapeles_original = ""
    try:
        portapapeles_original = pyperclip.paste()
    except Exception:
        pass

    hilo = None
    try:
        pyperclip.copy("https://example.com/uno")
        hilo = interceptor_mod.InterceptorThread()
        capturados: list[str] = []
        hilo.enlace_capturado.connect(lambda url, _n: capturados.append(url))
        hilo.start()

        archivo = carpeta / "enlaces.txt"
        limite = time.time() + 6
        while time.time() < limite and not capturados:
            app.processEvents()
            time.sleep(0.05)

        _assert(capturados == ["https://example.com/uno"], "Captura la primera URL")
        _assert(
            archivo.read_text(encoding="utf-8").strip() == "https://example.com/uno",
            "Escribe la URL en enlaces.txt",
        )

        # Duplicado consecutivo: NO debe volver a capturarse.
        pyperclip.copy("https://example.com/uno")
        limite = time.time() + 1.2
        while time.time() < limite:
            app.processEvents()
            time.sleep(0.05)
        _assert(len(capturados) == 1, "Ignora el duplicado consecutivo")

        pyperclip.copy("https://example.com/dos")
        limite = time.time() + 3
        while time.time() < limite and len(capturados) < 2:
            app.processEvents()
            time.sleep(0.05)
        _assert(len(capturados) == 2, "Captura una URL nueva")
        _assert(
            "https://example.com/dos" in archivo.read_text(encoding="utf-8"),
            "La segunda URL queda en el archivo",
        )
    finally:
        if hilo is not None:
            hilo.detener()
            _assert(hilo.wait(4000), "El interceptor se detiene sin colgarse")
        try:
            pyperclip.copy(portapapeles_original)
        except Exception:
            pass

    print("5) Icono e instrucciones incrustadas")
    ico = RAIZ / "assets" / "icon.ico"
    _assert(ico.is_file() and ico.stat().st_size > 10_000, "icon.ico generado")
    with ico.open("rb") as f:
        cabecera = f.read(6)
    _assert(cabecera[:2] == b"\x00\x00" and cabecera[2:4] == b"\x01\x00", "ICO válido")
    from utils.resources import asegurar_instrucciones, banner

    _assert("MarkOS" in banner(), "Banner ASCII disponible")
    _assert(asegurar_instrucciones().is_file(), "Instrucciones disponibles")

    print("6) Diálogos del flujo rápido")
    from ui.dialogs import DialogoDescargaFinalizada, DialogoPostCaptura

    post = DialogoPostCaptura(ventana, 2, "1080p")
    _assert(post.calidad() == "1080p", "El selector recuerda la última calidad")
    post.set_calidad("mp3")
    _assert(post.calidad() == "mp3", "Se puede cambiar la calidad al detener")
    post.deleteLater()

    sin_enlaces = DialogoPostCaptura(ventana, 0, "max")
    _assert(
        not sin_enlaces.boton_descargar.isEnabled(),
        "Sin enlaces, el botón Descargar queda deshabilitado",
    )
    sin_enlaces.deleteLater()

    resultado = DialogoDescargaFinalizada(
        ventana, True, "Descargas completadas: 1/1."
    )
    _assert(
        resultado.windowTitle() == "Descargas completadas",
        "El resultado invita a abrir la carpeta",
    )
    resultado.deleteLater()

    print("7) Flujo guiado (sin descargar de verdad)")
    import ui.main_window as mw

    class _FakeSignal:
        def connect(self, _slot):
            pass

    class _FakePostCaptura:
        def __init__(self, *_args, **_kwargs):
            self.abrir_carpeta_solicitado = _FakeSignal()

        def exec(self):
            return QDialog.DialogCode.Accepted

        def calidad(self):
            return "720p"

    calidad_iniciada: list[str] = []
    original_post = mw.DialogoPostCaptura
    original_leer = mw.leer_enlaces
    original_contar = mw.contar_enlaces
    original_iniciar = ventana.iniciar_descarga
    try:
        mw.DialogoPostCaptura = _FakePostCaptura
        mw.leer_enlaces = lambda: ["https://example.com/flujo"]
        mw.contar_enlaces = lambda: 0
        ventana.iniciar_descarga = (
            lambda calidad=None: calidad_iniciada.append(calidad or "")
        )

        pyperclip.copy("https://example.com/flujo")
        ventana.alternar_interceptor()
        limite = time.time() + 6
        while time.time() < limite and ventana.page_interceptor.lista.count() == 0:
            app.processEvents()
            time.sleep(0.05)
        _assert(
            ventana.page_interceptor.lista.count() == 1,
            "La ventana captura el enlace para el flujo guiado",
        )

        ventana._detener_interceptor()
        limite = time.time() + 6
        while time.time() < limite and not calidad_iniciada:
            app.processEvents()
            time.sleep(0.05)

        _assert(
            calidad_iniciada == ["720p"],
            "Al detener se elige la calidad y se inicia la descarga",
        )
        _assert(
            ventana._stack.currentIndex() == 1,
            "El flujo guiado salta a la pestaña Descargador",
        )
        _assert(
            Configuracion().get("calidad") == "720p",
            "La calidad elegida se guarda en config.json",
        )
    finally:
        mw.DialogoPostCaptura = original_post
        mw.leer_enlaces = original_leer
        mw.contar_enlaces = original_contar
        ventana.iniciar_descarga = original_iniciar
        if ventana._interceptor is not None:
            ventana._interceptor.detener()
            ventana._interceptor.wait(3000)

    print("8) Aviso final para abrir la carpeta")
    abierta: list[bool] = []

    class _FakeResultado:
        def __init__(self, *_args, **_kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    original_resultado = mw.DialogoDescargaFinalizada
    original_abrir = ventana.abrir_carpeta_trabajo
    try:
        mw.DialogoDescargaFinalizada = _FakeResultado
        ventana.abrir_carpeta_trabajo = lambda: abierta.append(True)
        ventana._al_finalizar_descarga(
            True, "Descargas completadas: 1/1."
        )
        _assert(
            abierta == [True],
            "Al terminar se pregunta y se abre la carpeta DESCARGAS",
        )
    finally:
        mw.DialogoDescargaFinalizada = original_resultado
        ventana.abrir_carpeta_trabajo = original_abrir

    print("9) Cierre limpio de la ventana")
    ventana.close()
    app.processEvents()
    _assert(True, "closeEvent completado sin bloqueos")

    print("\nSMOKE TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
