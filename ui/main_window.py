"""
ui/main_window.py
====================================================================
Ventana principal de MarkOS Downloader Suite.

Orquesta:
  * InterceptorThread  (QThread)  -> portapapeles
  * DownloadThread     (QThread)  -> yt-dlp + historial SQLite
  * ComprobacionThread (QThread)  -> releases de GitHub

Incluye tres pasos (Interceptor, Descargador e Historial),
bandeja del sistema, arrastrar y soltar, protocolo markos:// y
comprobacion diaria de actualizaciones.

Toda la comunicacion con la UI se hace por senales Qt, por lo que la
interfaz nunca se congela.
====================================================================
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtCore import (
    QByteArray,
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    Qt,
)
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.downloader import (
    CALIDADES,
    DownloadThread,
    ffmpeg_completo,
    ffmpeg_disponible,
)
from core.history import Historial
from core.interceptor import InterceptorThread
from core.updates import (
    ComprobacionThread,
    lanzar_instalador,
    preparar_instalacion,
    puede_autoinstalar,
)
from ui.dialogs import (
    DialogoAcercaDe,
    DialogoConfirmacion,
    DialogoDependencias,
    DialogoDescargaFinalizada,
    DialogoPostCaptura,
)
from ui.history_page import PaginaHistorial
from ui.pages import PaginaDescargador, PaginaInterceptor
from ui.preferences_dialog import DialogoPreferencias
from ui.profiles_dialog import DialogoPerfiles
from ui.theme import VERDE, TEXTO_DIM, icono_app, pixmap_icono
from ui.update_dialog import DialogoActualizacion
from ui.updater_dialog import DialogoActualizador
from utils.integration import (
    sincronizar_inicio_windows,
    sincronizar_protocolo,
)
from utils.logger import obtener_logger
from utils.paths import (
    APP_NAME,
    APP_VERSION,
    agregar_enlaces,
    archivo_enlaces,
    asegurar_entorno,
    contar_enlaces,
    dir_appdata,
    dir_trabajo,
    get_ffmpeg_path,
    get_ffprobe_path,
    get_ytdlp_path,
    leer_enlaces,
)
from utils.resources import abrir_instrucciones, banner
from utils.settings import Configuracion
from utils.urls import (
    calidad_para_url,
    extraer_urls,
    leer_urls_de_archivo,
    limpiar_url,
)

_log = obtener_logger("ui")

_NOMBRES_PAGINA = ("Interceptor", "Descargador", "Historial")


class AreaPagina(QScrollArea):
    """
    Contenedor con desplazamiento que nunca comprime su contenido.

    QScrollArea con widgetResizable usa heightForWidth y puede reservar mas
    alto del necesario (mostrando una barra aunque el contenido quepa) o
    comprimir las tarjetas en pantallas bajas. Aqui el tamano se calcula a
    mano: la pagina ocupa todo el alto disponible si su minimo cabe y, si
    no, se activa una barra vertical sin deformar ningun widget.
    """

    def __init__(self, contenido: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._contenido = contenido
        self.setObjectName("PageScroll")
        self.setWidget(contenido)
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.viewport().setAutoFillBackground(False)

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._ajustar()

    def _ajustar(self) -> None:
        viewport = self.viewport().size()
        minimo = self._contenido.minimumSizeHint().height()
        alto = max(viewport.height(), minimo)
        self._contenido.setGeometry(
            0, 0, viewport.width(), alto
        )
        barra = self.verticalScrollBar()
        barra.setRange(0, max(0, alto - viewport.height()))
        barra.setPageStep(viewport.height())
        barra.setSingleStep(24)


class VentanaPrincipal(QMainWindow):
    """Ventana unica con asistente de tres pasos y barra de estado."""

    def __init__(
        self,
        urls_iniciales: list[str] | None = None,
        capturar: bool = False,
        descargar: bool = False,
        minimizado: bool = False,
    ) -> None:
        super().__init__()
        self.config = Configuracion()
        self.historial = Historial()
        self._interceptor: InterceptorThread | None = None
        self._descarga: DownloadThread | None = None
        self._hilo_update: ComprobacionThread | None = None
        self._update_manual = False
        self._cerrando = False
        self._salir_de_verdad = False
        self._aviso_bandeja_mostrado = False
        self._dependencias_verificadas = False
        self._tray: QSystemTrayIcon | None = None
        self._accion_captura: QAction | None = None
        # True cuando la captura se detuvo por accion del usuario y toca
        # ofrecer la descarga inmediata al terminar el hilo.
        self._post_captura_pendiente = False
        # Animaciones de transicion y de la barra de pasos.
        self._anim_pagina: QPropertyAnimation | None = None
        self._widget_animado: QWidget | None = None
        self._anim_paso: QPropertyAnimation | None = None

        self._urls_iniciales = list(urls_iniciales or [])
        self._capturar_al_iniciar = bool(capturar)
        self._descargar_al_iniciar = bool(descargar)
        self._minimizado_al_iniciar = bool(minimizado)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(icono_app())
        self.setMinimumSize(900, 640)
        self.setAcceptDrops(True)

        self._construir_ui()
        self._configurar_atajos()
        self._configurar_bandeja()
        self._restaurar_estado()

        self._actualizar_cola()
        self._actualizar_estado_interceptor(False, "Interceptor detenido")
        self._actualizar_version()
        self.page_descargador.append_log(
            f"{APP_NAME} v{APP_VERSION} — listo."
        )
        self.page_descargador.append_log(
            f"Carpeta de trabajo: {dir_trabajo()}"
        )
        _log.info("Ventana principal creada")

        QTimer.singleShot(0, self._aplicar_arranque)

    # ==================================================================
    # CONSTRUCCION DE LA UI
    # ==================================================================
    def _construir_ui(self) -> None:
        central = QWidget()
        raiz = QVBoxLayout(central)
        raiz.setContentsMargins(0, 0, 0, 0)
        raiz.setSpacing(0)

        self._stack = QStackedWidget()
        self.page_interceptor = PaginaInterceptor()
        self.page_descargador = PaginaDescargador()
        self.page_historial = PaginaHistorial(self.historial)
        self._stack.addWidget(AreaPagina(self.page_interceptor))
        self._stack.addWidget(AreaPagina(self.page_descargador))
        self._stack.addWidget(AreaPagina(self.page_historial))

        raiz.addWidget(self._crear_topbar())

        # Linea de progreso del asistente (1 de 3 ... 3 de 3).
        self._barra_paso = QProgressBar()
        self._barra_paso.setObjectName("StepProgress")
        self._barra_paso.setRange(0, 3)
        self._barra_paso.setValue(1)
        self._barra_paso.setTextVisible(False)
        self._barra_paso.setFixedHeight(3)
        raiz.addWidget(self._barra_paso)

        raiz.addWidget(self._stack, 1)
        raiz.addWidget(self._crear_bottom_nav())
        self.setCentralWidget(central)

        # ----- conexiones de pagina -> ventana -----
        self.page_interceptor.toggle_solicitado.connect(self.alternar_interceptor)
        self.page_interceptor.abrir_carpeta_solicitado.connect(
            self.abrir_carpeta_trabajo
        )
        self.page_interceptor.limpiar_enlaces_solicitado.connect(
            self.limpiar_enlaces
        )
        self.page_descargador.descargar_solicitado.connect(self.iniciar_descarga)
        self.page_descargador.detener_solicitado.connect(self.detener_descarga)
        self.page_descargador.pausar_solicitado.connect(
            self.alternar_pausa_descarga
        )
        self.page_descargador.abrir_carpeta_solicitado.connect(
            self.abrir_carpeta_trabajo
        )
        self.page_descargador.perfiles_solicitado.connect(self.abrir_perfiles)
        self.page_descargador.calidad_cambiada.connect(self._guardar_calidad)
        self.page_historial.reintentar_solicitado.connect(
            self.reintentar_desde_historial
        )
        self.page_historial.eliminar_solicitado.connect(
            self.eliminar_del_historial
        )

        # ----- barra de estado -----
        barra = QStatusBar()
        barra.setSizeGripEnabled(False)
        self.setStatusBar(barra)

        self.lbl_estado_barra = QLabel("● Interceptor detenido")
        self.lbl_cola = QLabel("Enlaces en cola: 0")
        self.lbl_version = QLabel(f"v{APP_VERSION} · MarkOS")

        barra.addWidget(self.lbl_estado_barra)
        barra.addPermanentWidget(self.lbl_cola)
        barra.addPermanentWidget(self.lbl_version)

    # ------------------------------------------------------------------
    def _crear_topbar(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("TopBar")
        barra.setFixedHeight(68)
        barra.setFrameShape(QFrame.Shape.NoFrame)

        h = QHBoxLayout(barra)
        h.setContentsMargins(20, 0, 16, 0)
        h.setSpacing(16)

        # ----- Marca -----
        marca = QWidget()
        hm = QHBoxLayout(marca)
        hm.setContentsMargins(0, 0, 0, 0)
        hm.setSpacing(10)

        logo = QLabel()
        logo.setPixmap(pixmap_icono(34))
        logo.setFixedSize(34, 34)

        textos = QVBoxLayout()
        textos.setSpacing(0)
        nombre = QLabel("MarkOS")
        nombre.setObjectName("BrandName")
        self.lbl_marca_version = QLabel(
            f"DOWNLOADER SUITE · v{APP_VERSION}"
        )
        self.lbl_marca_version.setObjectName("BrandTag")
        textos.addWidget(nombre)
        textos.addWidget(self.lbl_marca_version)

        hm.addWidget(logo)
        hm.addLayout(textos)
        h.addWidget(marca)

        separador = QFrame()
        separador.setFixedSize(1, 30)
        separador.setStyleSheet("background-color: #2B2B2B;")
        h.addWidget(separador)

        # ----- Pasos -----
        self._botones_paso: list[QPushButton] = []
        self._grupo_paso = QButtonGroup(self)
        self._grupo_paso.setExclusive(True)

        pasos = QHBoxLayout()
        pasos.setSpacing(6)
        entradas = (
            ("01", "Interceptor", "Captura enlaces del portapapeles"),
            ("02", "Descargador", "yt-dlp · MP3 y video"),
            ("03", "Historial", "Consultas, reintentos y archivos"),
        )
        for indice, (numero, texto, tooltip) in enumerate(entradas):
            boton = QPushButton(f"{numero}  {texto}")
            boton.setObjectName("StepButton")
            boton.setCheckable(True)
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setToolTip(tooltip)
            boton.setMinimumHeight(36)
            boton.clicked.connect(
                lambda _=False, i=indice: self.cambiar_pagina(i)
            )
            self._grupo_paso.addButton(boton, indice)
            self._botones_paso.append(boton)
            pasos.addWidget(boton)
        h.addLayout(pasos)
        h.addStretch(1)

        # ----- Acciones de utilidad -----
        self.boton_actualizar = QPushButton("↻  Actualizar")
        self.boton_actualizar.setObjectName("Ghost")
        self.boton_actualizar.setFixedHeight(36)
        self.boton_actualizar.setMinimumWidth(128)
        self.boton_actualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_actualizar.setToolTip(
            "Actualizar yt-dlp y FFmpeg sin recompilar el EXE."
        )
        self.boton_actualizar.clicked.connect(self.abrir_actualizador)
        h.addWidget(self.boton_actualizar)

        self.boton_menu = QToolButton()
        self.boton_menu.setObjectName("MenuButton")
        self.boton_menu.setText("⋯")
        self.boton_menu.setFixedSize(40, 36)
        self.boton_menu.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_menu.setToolTip("Más opciones")
        self.boton_menu.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )

        menu = QMenu(self.boton_menu)
        accion_perfiles = menu.addAction("Perfiles por sitio")
        accion_perfiles.triggered.connect(self.abrir_perfiles)
        accion_preferencias = menu.addAction("Preferencias")
        accion_preferencias.triggered.connect(self.abrir_preferencias)
        accion_buscar = menu.addAction("Buscar actualizaciones")
        accion_buscar.triggered.connect(
            lambda: self.buscar_actualizaciones(manual=True)
        )
        menu.addSeparator()
        accion_instrucciones = menu.addAction("Instrucciones")
        accion_instrucciones.triggered.connect(self.abrir_instrucciones)
        accion_acerca = menu.addAction("Acerca de MarkOS")
        accion_acerca.triggered.connect(self.mostrar_acerca_de)
        menu.addSeparator()
        accion_datos = menu.addAction("Abrir carpeta de datos")
        accion_datos.triggered.connect(self.abrir_carpeta_datos)
        menu.addSeparator()
        accion_salir = menu.addAction("Salir")
        accion_salir.triggered.connect(self._salir)
        self.boton_menu.setMenu(menu)
        h.addWidget(self.boton_menu)

        return barra

    # ------------------------------------------------------------------
    def _crear_bottom_nav(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("BottomBar")
        barra.setFixedHeight(56)
        barra.setFrameShape(QFrame.Shape.NoFrame)

        h = QHBoxLayout(barra)
        h.setContentsMargins(22, 0, 18, 0)
        h.setSpacing(10)

        self.lbl_paso = QLabel("Paso 1 de 3 · Interceptor")
        self.lbl_paso.setObjectName("StepCounter")

        atajo = QLabel("Ctrl+← / Ctrl+→")
        atajo.setObjectName("Hint")

        self.boton_atras = QPushButton("←  Atrás")
        self.boton_atras.setObjectName("Ghost")
        self.boton_atras.setFixedSize(118, 36)
        self.boton_atras.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_atras.clicked.connect(self.ir_paso_anterior)

        self.boton_siguiente = QPushButton("Siguiente paso  →")
        self.boton_siguiente.setObjectName("Primary")
        self.boton_siguiente.setFixedSize(190, 36)
        self.boton_siguiente.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_siguiente.clicked.connect(self.ir_paso_siguiente)

        h.addWidget(self.lbl_paso)
        h.addStretch(1)
        h.addWidget(atajo)
        h.addWidget(self.boton_atras)
        h.addWidget(self.boton_siguiente)
        return barra

    # ------------------------------------------------------------------
    def _configurar_atajos(self) -> None:
        atajos = (
            ("Ctrl+I", self.alternar_interceptor),
            ("Ctrl+D", self._atajo_descargar),
            ("Ctrl+Space", self.alternar_pausa_descarga),
            ("Ctrl+H", lambda: self.cambiar_pagina(2)),
            ("Ctrl+,", self.abrir_preferencias),            ("Ctrl+U", lambda: self.buscar_actualizaciones(manual=True)),
            ("Ctrl+Q", self._salir),
            ("Ctrl+Left", self.ir_paso_anterior),
            ("Ctrl+Right", self.ir_paso_siguiente),
        )
        for secuencia, funcion in atajos:
            atajo = QShortcut(QKeySequence(secuencia), self)
            atajo.setContext(Qt.ShortcutContext.ApplicationShortcut)
            atajo.activated.connect(funcion)

    def _atajo_descargar(self) -> None:
        self.cambiar_pagina(1)
        if self.page_descargador.boton_descargar.isEnabled():
            self.iniciar_descarga(self.page_descargador.calidad_actual())

    # ------------------------------------------------------------------
    def _configurar_bandeja(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            _log.info("Bandeja del sistema no disponible")
            return

        self._tray = QSystemTrayIcon(self.windowIcon(), self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu(self)
        accion_mostrar = QAction("Mostrar ventana", self)
        accion_mostrar.triggered.connect(self._mostrar_ventana)
        menu.addAction(accion_mostrar)
        menu.addSeparator()

        self._accion_captura = QAction("Iniciar captura", self)
        self._accion_captura.setCheckable(True)
        self._accion_captura.triggered.connect(self.alternar_interceptor)
        menu.addAction(self._accion_captura)

        accion_descargar = QAction("Descargar enlaces en cola", self)
        accion_descargar.triggered.connect(self.iniciar_descarga)
        menu.addAction(accion_descargar)

        accion_historial = QAction("Abrir historial", self)
        accion_historial.triggered.connect(
            lambda: self._mostrar_pagina(2)
        )
        menu.addAction(accion_historial)
        menu.addSeparator()

        accion_preferencias = QAction("Preferencias…", self)
        accion_preferencias.triggered.connect(self.abrir_preferencias)
        menu.addAction(accion_preferencias)

        accion_actualizaciones = QAction("Buscar actualizaciones…", self)
        accion_actualizaciones.triggered.connect(
            lambda: self.buscar_actualizaciones(manual=True)
        )
        menu.addAction(accion_actualizaciones)
        menu.addSeparator()

        accion_salir = QAction("Salir", self)
        accion_salir.triggered.connect(self._salir)
        menu.addAction(accion_salir)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._al_activar_bandeja)
        self._tray.show()

    def _al_activar_bandeja(self, motivo: QSystemTrayIcon.ActivationReason) -> None:
        if motivo in (
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        ):
            self._mostrar_ventana()

    def _mostrar_ventana(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _mostrar_pagina(self, indice: int) -> None:
        self._mostrar_ventana()
        self.cambiar_pagina(indice)

    def ocultar_a_bandeja(self, notificar: bool = True) -> None:
        """Oculta la ventana manteniendo el interceptor y la cola activos."""
        if self._tray is None:
            return
        self.hide()
        if notificar and not self._aviso_bandeja_mostrado:
            self._aviso_bandeja_mostrado = True
            self._notificar(
                "MarkOS sigue activo",
                "La ventana se ocultó a la bandeja. El interceptor y las "
                "descargas continúan en segundo plano.",
            )

    def _salir(self) -> None:
        """Salida real (ignora 'cerrar a la bandeja')."""
        self._salir_de_verdad = True
        self.close()

    # ------------------------------------------------------------------
    def _restaurar_estado(self) -> None:
        geometria = self.config.get("geometria", "") or ""
        restaurada = False
        if geometria:
            try:
                restaurada = self.restoreGeometry(
                    QByteArray.fromBase64(geometria.encode("ascii"))
                )
            except Exception:
                restaurada = False

        if not restaurada or self.width() < 900 or self.height() < 600:
            ancho, alto = 1260, 820
            pantalla = self.screen()
            if pantalla is not None:
                disponible = pantalla.availableGeometry()
                ancho = min(ancho, max(900, disponible.width() - 60))
                alto = min(alto, max(640, disponible.height() - 40))
            self.resize(ancho, alto)

        indice = int(self.config.get("pestana", 0) or 0)
        indice = max(0, min(2, indice))
        self.cambiar_pagina(indice, animar=False)

        self.page_descargador.set_calidad(str(self.config.get("calidad", "max")))

    def _actualizar_version(self) -> None:
        self.lbl_version.setText(f"v{APP_VERSION} · MarkOS")
        self.lbl_marca_version.setText(
            f"DOWNLOADER SUITE · v{APP_VERSION}"
        )

    # ==================================================================
    # ARRANQUE (protocolo markos:// y cola pendiente)
    # ==================================================================
    def _aplicar_arranque(self) -> None:
        self._restaurar_cola_pendiente()

        if self._urls_iniciales:
            self.agregar_urls_externas(
                self._urls_iniciales,
                origen="markos",
                descargar=self._descargar_al_iniciar,
            )
        elif self._descargar_al_iniciar:
            self.cambiar_pagina(1)
            QTimer.singleShot(60, self.iniciar_descarga)

        if self._capturar_al_iniciar:
            self.cambiar_pagina(0)
            QTimer.singleShot(120, self._iniciar_interceptor)

        self._programar_comprobacion_automatica()

    def _restaurar_cola_pendiente(self) -> None:
        """
        Reanuda la cola que quedo pendiente tras un cierre inesperado.

        Las filas se vuelcan en enlaces.txt sin preguntar nada; las filas
        antiguas se cierran para no duplicar el historial cuando se
        vuelvan a descargar.
        """
        try:
            pendientes = self.historial.pendientes()
        except Exception as exc:  # pragma: no cover - SQLite defensivo
            _log.warning("No se pudo leer la cola pendiente: %s", exc)
            return
        if not pendientes:
            return

        existentes = set(leer_enlaces())
        nuevas: list[str] = []
        for fila in pendientes:
            url = str(fila.get("url") or "").strip()
            if not url or url in existentes:
                continue
            existentes.add(url)
            nuevas.append(url)

        if nuevas:
            agregar_enlaces(nuevas, origen="pendientes")
            self.page_descargador.append_log(
                f"[↻] {len(nuevas)} enlace(s) pendiente(s) restaurados en "
                "la cola."
            )
        for fila in pendientes:
            self.historial.marcar_cancelada(
                int(fila.get("id") or 0),
                "Restaurada en enlaces.txt al iniciar la aplicación",
            )
        self._actualizar_cola()
        self.page_historial.refrescar()

    # ==================================================================
    # ARRASTRAR Y SOLTAR / URLS EXTERNAS
    # ==================================================================
    def dragEnterEvent(self, evento) -> None:  # noqa: N802
        datos = evento.mimeData()
        if datos.hasUrls() or "http" in (datos.text() or "").lower():
            evento.acceptProposedAction()
            return
        super().dragEnterEvent(evento)

    def dropEvent(self, evento) -> None:  # noqa: N802
        datos = evento.mimeData()
        urls: list[str] = []

        if datos.hasText():
            urls.extend(extraer_urls(datos.text()))

        if datos.hasUrls():
            for url in datos.urls():
                if url.isLocalFile():
                    ruta = Path(url.toLocalFile())
                    if ruta.suffix.lower() in (".txt", ".csv", ".list"):
                        urls.extend(leer_urls_de_archivo(ruta))
                else:
                    urls.extend(extraer_urls(url.toString()))

        if not urls:
            self.statusBar().showMessage(
                "No se encontraron enlaces http(s) en lo que arrastraste.",
                6000,
            )
            evento.ignore()
            return

        evento.acceptProposedAction()
        self.agregar_urls_externas(urls, origen="arrastrar")

    def agregar_urls_externas(
        self,
        urls: list[str],
        origen: str = "externo",
        descargar: bool = False,
    ) -> int:
        """Anade URLs a enlaces.txt (arrastrar, soltar o markos://)."""
        depuradas: list[str] = []
        for cruda in urls:
            encontradas = extraer_urls(str(cruda))
            if encontradas:
                depuradas.extend(encontradas)
                continue
            limpia = limpiar_url(str(cruda))
            if limpia.lower().startswith(("http://", "https://")):
                depuradas.append(limpia)

        if not depuradas:
            return 0

        anadidas = agregar_enlaces(depuradas, origen=origen)
        self._actualizar_cola()
        if anadidas:
            self.page_descargador.append_log(
                f"[+] {anadidas} enlace(s) añadidos desde {origen}."
            )
            self.statusBar().showMessage(
                f"{anadidas} enlace(s) añadidos a enlaces.txt.", 6000
            )
        self.cambiar_pagina(1)

        if descargar and not (
            self._descarga is not None and self._descarga.isRunning()
        ):
            QTimer.singleShot(120, self.iniciar_descarga)
        return anadidas

    # ==================================================================
    # NAVEGACION DEL ASISTENTE
    # ==================================================================
    def ir_paso_anterior(self) -> None:
        self.cambiar_pagina(self._stack.currentIndex() - 1)

    def ir_paso_siguiente(self) -> None:
        self.cambiar_pagina(self._stack.currentIndex() + 1)

    def _actualizar_navegacion(self, indice: int) -> None:
        nombres = _NOMBRES_PAGINA
        self.lbl_paso.setText(
            f"Paso {indice + 1} de 3 · {nombres[indice]}"
        )
        self.boton_atras.setEnabled(indice > 0)
        self.boton_siguiente.setEnabled(indice < 2)
        self.boton_siguiente.setText(
            "Siguiente paso  →" if indice < 2 else "Último paso"
        )

    def _animar_entrada_pagina(self, widget: QWidget) -> None:
        """Fundido suave al entrar en una pagina."""
        if self._anim_pagina is not None:
            self._anim_pagina.stop()
            if self._widget_animado is not None:
                self._widget_animado.setGraphicsEffect(None)

        efecto = QGraphicsOpacityEffect(widget)
        efecto.setOpacity(0.0)
        widget.setGraphicsEffect(efecto)

        animacion = QPropertyAnimation(efecto, b"opacity", self)
        animacion.setDuration(230)
        animacion.setStartValue(0.0)
        animacion.setEndValue(1.0)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.finished.connect(
            lambda w=widget: w.setGraphicsEffect(None)
        )
        animacion.start()

        self._anim_pagina = animacion
        self._widget_animado = widget

    def _animar_barra_paso(self, indice: int) -> None:
        if self._anim_paso is not None:
            self._anim_paso.stop()
        animacion = QPropertyAnimation(self._barra_paso, b"value", self)
        animacion.setDuration(320)
        animacion.setStartValue(self._barra_paso.value())
        animacion.setEndValue(indice + 1)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.start()
        self._anim_paso = animacion

    # ==================================================================
    # INTERCEPTOR
    # ==================================================================
    def alternar_interceptor(self) -> None:
        if self._interceptor is not None and self._interceptor.isRunning():
            self._detener_interceptor()
            return

        if self._interceptor is not None:
            # Hilo terminando; evita arrancar dos a la vez.
            return

        n = contar_enlaces()
        if n > 0:
            dialogo = DialogoConfirmacion(
                self,
                "Vaciar enlaces.txt",
                f"El interceptor vacía enlaces.txt al iniciar, igual que el "
                f"script original. Ahora hay {n} enlace(s) en cola y se "
                f"perderán.",
                texto_confirmar="Iniciar y vaciar",
                peligro=True,
                detalle=(
                    "Si todavía no los has descargado, cancela y usa primero "
                    "la pestaña Descargador."
                ),
            )
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return

        self._iniciar_interceptor()

    def _iniciar_interceptor(self) -> None:
        self._post_captura_pendiente = False
        self.page_interceptor.limpiar_aviso()
        self.page_interceptor.limpiar_lista()
        self.page_interceptor.set_capturados(0)
        self.page_interceptor.set_estado(False, "Iniciando interceptor…")
        self.page_interceptor.set_ocupado(True)

        hilo = InterceptorThread(self)
        hilo.enlace_capturado.connect(self._al_capturar_enlace)
        hilo.estado_cambiado.connect(self._actualizar_estado_interceptor)
        hilo.aviso.connect(self._al_aviso_interceptor)
        hilo.error.connect(self._al_error_interceptor)
        hilo.solicitud_abrir_carpeta.connect(self._al_pulsar_escape)
        hilo.finalizado.connect(self._al_finalizar_interceptor)

        self._interceptor = hilo
        hilo.start()

    def _detener_interceptor(self) -> None:
        hilo = self._interceptor
        if hilo is None or not hilo.isRunning():
            return
        self._post_captura_pendiente = True
        self.page_interceptor.set_ocupado(True)
        hilo.detener()

    def _al_capturar_enlace(self, url: str, total: int) -> None:
        self.page_interceptor.agregar_enlace(url)
        self.page_interceptor.set_capturados(total)
        # El interceptor vacia enlaces.txt al arrancar, por lo que el
        # contador de la sesion es exacto y evitamos releer el archivo
        # en cada captura (mas fluido en sesiones largas).
        self.page_interceptor.set_cola(total)
        self.lbl_cola.setText(f"Enlaces en cola: {total}")

    def _al_pulsar_escape(self) -> None:
        """ESC global: detiene la captura, abre la carpeta y ofrece descargar."""
        self._post_captura_pendiente = True
        self.abrir_carpeta_trabajo()
        self.statusBar().showMessage(
            "ESC detectado: interceptor detenido; elige la calidad para descargar.",
            7000,
        )

    def _al_aviso_interceptor(self, texto: str) -> None:
        self.page_interceptor.mostrar_aviso(texto, error=False)
        self.page_descargador.append_log(f"[!] {texto}")

    def _al_error_interceptor(self, texto: str) -> None:
        self.page_interceptor.mostrar_aviso(texto, error=True)
        self.page_descargador.append_log(f"[ERROR] {texto}")
        _log.error("Interceptor: %s", texto)

    def _actualizar_estado_interceptor(self, activo: bool, texto: str) -> None:
        self.page_interceptor.set_estado(activo, texto)
        color = VERDE if activo else TEXTO_DIM
        self.lbl_estado_barra.setText(
            f"● Interceptor {'activo' if activo else 'detenido'}"
        )
        self.lbl_estado_barra.setStyleSheet(
            f"color: {color}; font-size: 11px; padding: 2px 6px;"
        )
        if self._accion_captura is not None:
            self._accion_captura.setChecked(activo)
            self._accion_captura.setText(
                "Detener captura" if activo else "Iniciar captura"
            )

    def _al_finalizar_interceptor(self) -> None:
        self._interceptor = None
        self.page_interceptor.set_ocupado(False)
        self.page_interceptor.set_estado(False, "Interceptor detenido")
        self._actualizar_estado_interceptor(False, "Interceptor detenido")
        self._actualizar_cola()

        pendiente = self._post_captura_pendiente
        self._post_captura_pendiente = False
        if pendiente and not self._cerrando:
            # Fuera del slot de la senal: deja repintar la UI antes del modal.
            QTimer.singleShot(0, self._ofrecer_descarga_post_captura)

    def _actualizar_cola(self) -> None:
        total = contar_enlaces()
        self.page_interceptor.set_cola(total)
        self.lbl_cola.setText(f"Enlaces en cola: {total}")

    def _ofrecer_descarga_post_captura(self) -> None:
        """
        Flujo premium: al detener la captura se pregunta la calidad y se
        puede descargar al instante, sin pasar manualmente por la pestana
        Descargador.
        """
        if self._cerrando:
            return

        urls = leer_enlaces()
        if not urls:
            QMessageBox.information(
                self,
                "Captura finalizada",
                "No se capturó ningún enlace en esta sesión.\n\n"
                "Inicia la captura y copia una URL que empiece por http:// "
                "o https:// para poder descargarla.",
            )
            self.page_descargador.append_log(
                "[!] Captura detenida sin enlaces nuevos."
            )
            return

        if self._descarga is not None and self._descarga.isRunning():
            self.statusBar().showMessage(
                "Ya hay una descarga en curso; los enlaces quedaron en cola.",
                7000,
            )
            return

        dialogo = DialogoPostCaptura(
            self,
            len(urls),
            self.page_descargador.calidad_actual(),
        )
        dialogo.abrir_carpeta_solicitado.connect(self.abrir_carpeta_trabajo)

        if dialogo.exec() != QDialog.DialogCode.Accepted:
            self.statusBar().showMessage(
                f"{len(urls)} enlace(s) listos en enlaces.txt. "
                "Puedes descargarlos cuando quieras.",
                8000,
            )
            return

        calidad = dialogo.calidad()
        self.config.set("calidad", calidad)
        self.page_descargador.set_calidad(calidad)
        self.cambiar_pagina(1)
        self.iniciar_descarga(calidad)

    # ==================================================================
    # PERFILES Y PREFERENCIAS
    # ==================================================================
    def _perfiles_activos(self) -> dict[str, str]:
        if not self.config.get("usar_perfiles", True):
            return {}
        perfiles = self.config.get("perfiles", {})
        return dict(perfiles) if isinstance(perfiles, dict) else {}

    def abrir_perfiles(self) -> None:
        dialogo = DialogoPerfiles(
            self,
            self.config.get("perfiles", {}) or {},
            bool(self.config.get("usar_perfiles", True)),
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        perfiles = dialogo.perfiles()
        self.config.actualizar(
            {"perfiles": perfiles, "usar_perfiles": dialogo.activo()}
        )
        if dialogo.activo():
            resumen = ", ".join(
                f"{dominio} → {calidad}" for dominio, calidad in perfiles.items()
            ) or "sin dominios configurados"
            self.page_descargador.append_log(
                f"[OK] Perfiles por sitio activos: {resumen}"
            )
        else:
            self.page_descargador.append_log(
                "[OK] Perfiles por sitio desactivados: se usará la calidad global."
            )
        self.statusBar().showMessage("Perfiles guardados.", 5000)

    def abrir_preferencias(self) -> None:
        dialogo = DialogoPreferencias(
            self,
            cerrar_a_bandeja=bool(self.config.get("cerrar_a_bandeja", False)),
            iniciar_minimizado=bool(
                self.config.get("iniciar_minimizado", False)
            ),
            iniciar_con_windows=bool(
                self.config.get("iniciar_con_windows", False)
            ),
            protocolo_registrado=bool(
                self.config.get("protocolo_registrado", True)
            ),
            auto_actualizaciones=bool(
                self.config.get("auto_buscar_actualizaciones", True)
            ),
            usar_perfiles=bool(self.config.get("usar_perfiles", True)),
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        valores = dialogo.valores()
        self.config.actualizar(valores)

        fallos: list[str] = []
        if os.name == "nt":
            if valores["iniciar_con_windows"] and not sincronizar_inicio_windows(
                True
            ):
                fallos.append(
                    "Windows no aceptó el inicio automático. Ejecuta la app "
                    "desde tu usuario (no como administrador)."
                )
            elif not valores["iniciar_con_windows"]:
                sincronizar_inicio_windows(False)

            if valores["protocolo_registrado"] and not sincronizar_protocolo(
                True
            ):
                fallos.append(
                    "No se pudo registrar markos://. En modo desarrollo "
                    "necesitas el EXE o pythonw.exe disponible."
                )
            elif not valores["protocolo_registrado"]:
                sincronizar_protocolo(False)

        self.page_descargador.append_log("[OK] Preferencias guardadas.")
        if fallos:
            QMessageBox.warning(
                self, "Algunos ajustes no se aplicaron", "\n\n".join(fallos)
            )
        self.statusBar().showMessage("Preferencias guardadas.", 5000)

    # ==================================================================
    # DESCARGADOR
    # ==================================================================
    def _guardar_calidad(self, clave: str) -> None:
        self.config.set("calidad", clave)

    def _preparar_descarga(self) -> bool:
        """Comprobaciones comunes antes de lanzar cualquier descarga."""
        if get_ytdlp_path() is None:
            self._avisar_sin_ytdlp()
            return False

        try:
            asegurar_entorno()
        except OSError as exc:
            QMessageBox.warning(
                self,
                "Carpeta no disponible",
                "No se pudo crear la carpeta de trabajo.\n\n"
                f"{exc}",
            )
            return False

        if not ffmpeg_disponible():
            dialogo = DialogoConfirmacion(
                self,
                "FFmpeg no disponible",
                "No se encontró ffmpeg.exe. Las descargas en MP3 y la fusión "
                "de audio + video pueden fallar o quedarse sin audio.",
                texto_confirmar="Descargar igualmente",
                peligro=True,
                detalle=(
                    "Vuelve a ejecutar build.bat (sin la opción noffmpeg) o "
                    "instala FFmpeg con: winget install Gyan.FFmpeg"
                ),
            )
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return False
        elif not ffmpeg_completo():
            self.page_descargador.append_log(
                "[!] ffprobe.exe no está disponible; algunas post-operaciones "
                "de yt-dlp podrían fallar."
            )
        return True

    def iniciar_descarga(self, calidad: str | None = None) -> None:
        if self._descarga is not None and self._descarga.isRunning():
            return

        calidad = calidad or self.page_descargador.calidad_actual()

        if not self._preparar_descarga():
            return

        urls = leer_enlaces()
        if not urls:
            QMessageBox.information(
                self,
                "Sin enlaces",
                "enlaces.txt está vacío.\n\n"
                "Usa la pestaña Interceptor para capturar enlaces, arrastra "
                "un archivo .txt o pega las URLs manualmente en:\n"
                f"{dir_trabajo() / 'enlaces.txt'}",
            )
            return

        self._lanzar_descarga(urls, calidad, {}, "enlaces")

    def _lanzar_descarga(
        self,
        urls: list[str],
        calidad: str,
        overrides: dict[str, str],
        origen: str,
    ) -> None:
        perfiles = self._perfiles_activos()
        calidades_iniciales = {
            url: calidad_para_url(url, perfiles, calidad, overrides)
            for url in urls
        }
        ids = self.historial.anadir_pendientes(
            urls, calidades=calidades_iniciales, origen=origen
        )

        self.config.set("calidad", calidad)
        self.page_descargador.set_calidad(calidad)
        self.page_descargador.reiniciar_progreso()
        self.page_descargador.set_descargando(True)
        self.page_descargador.set_pausado(False)
        self.page_descargador.set_info("")
        self.page_descargador.append_log("")
        self.page_descargador.append_log("═" * 58)
        for linea in banner().rstrip().splitlines():
            self.page_descargador.append_log(linea)
        self.page_descargador.append_log("═" * 58)
        origen_texto = {
            "enlaces": "cola de enlaces.txt",
            "reintento": "reintento desde el historial",
            "markos": "protocolo markos://",
            "arrastrar": "arrastrar y soltar",
        }.get(origen, origen)
        self.page_descargador.append_log(
            f"Iniciando {len(urls)} descarga(s) desde {origen_texto} · "
            f"{CALIDADES.get(calidad, CALIDADES['max'])['etiqueta']}"
        )

        hilo = DownloadThread(
            urls,
            calidad,
            self,
            perfiles=perfiles,
            calidades_override=overrides,
            historial=self.historial,
            historial_ids=ids,
            origen=origen,
        )
        hilo.log.connect(self.page_descargador.append_log)
        hilo.progreso.connect(self.page_descargador.set_progreso)
        hilo.item_actual.connect(self.page_descargador.set_item)
        hilo.item_resultado.connect(self._al_item_resultado)
        hilo.pausado.connect(self._al_pausado_descarga)
        hilo.finalizado.connect(self._al_finalizar_descarga)
        self._descarga = hilo
        hilo.start()

        self.page_historial.refrescar()
        self.statusBar().showMessage("Descargando en segundo plano…", 5000)

    def alternar_pausa_descarga(self) -> None:
        hilo = self._descarga
        if hilo is None or not hilo.isRunning():
            return
        if hilo.pausado_actual:
            hilo.reanudar()
            self.page_descargador.set_pausado(False)
            self.statusBar().showMessage("Reanudando la cola…", 4000)
        else:
            hilo.pausar()
            self.page_descargador.set_pausado(True, pendiente=True)
            self.statusBar().showMessage(
                "Pausa solicitada: se aplicará al terminar el enlace actual.",
                6000,
            )

    def _al_pausado_descarga(self, activo: bool) -> None:
        self.page_descargador.set_pausado(activo, pendiente=False)
        if activo:
            self._notificar(
                "Cola en pausa",
                "Pulsa Reanudar en el Descargador para continuar.",
            )
            self.statusBar().showMessage("Cola en pausa.", 6000)
        else:
            self.statusBar().showMessage("Cola reanudada.", 4000)

    def _al_item_resultado(self, datos: dict) -> None:
        self.page_historial.refrescar()
        if not datos.get("exito"):
            _log.warning(
                "Enlace fallido (%s): %s",
                datos.get("calidad"),
                datos.get("url"),
            )

    def detener_descarga(self) -> None:
        hilo = self._descarga
        if hilo is None or not hilo.isRunning():
            return

        dialogo = DialogoConfirmacion(
            self,
            "Cancelar descarga",
            "Se detendrá yt-dlp y los archivos parciales quedarán en la "
            "carpeta DESCARGAS. ¿Quieres cancelar?",
            texto_confirmar="Sí, cancelar",
            texto_cancelar="Seguir descargando",
            peligro=True,
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        self.page_descargador.append_log("[x] Cancelando descarga…")
        self.page_descargador.set_info("Cancelando…")
        hilo.detener()

    def _al_finalizar_descarga(self, exito: bool, resumen: str) -> None:
        # Si ya se lanzo otra descarga, ignorar la senal de la anterior.
        remitente = self.sender()
        if remitente is not None and remitente is not self._descarga:
            return

        self._descarga = None
        self.page_descargador.set_descargando(False)
        self.page_descargador.set_pausado(False)
        self.page_descargador.set_info(resumen)
        if exito:
            self.page_descargador.set_progreso(100)
        self.page_historial.refrescar()

        self.page_descargador.append_log("")
        self.page_descargador.append_log(
            f"[{'OK' if exito else 'FIN'}] {resumen}"
        )
        self._actualizar_cola()
        self.statusBar().showMessage(resumen, 8000)

        cancelada = "cancelada" in resumen.lower()
        if cancelada:
            self._notificar("Descarga cancelada", resumen)
        elif exito:
            self._notificar("Descargas finalizadas", resumen)
        else:
            self._notificar("Descargas con errores", resumen)

        QApplication.alert(self, 3000)
        _log.info("Descarga finalizada: exito=%s | %s", exito, resumen)

        # Pregunta explicita: ¿abrir la carpeta donde quedaron los videos?
        if not cancelada and not self._cerrando:
            self._preguntar_abrir_carpeta_final(exito, resumen)

    def _preguntar_abrir_carpeta_final(self, exito: bool, resumen: str) -> None:
        dialogo = DialogoDescargaFinalizada(self, exito, resumen)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.abrir_carpeta_trabajo()

    # ==================================================================
    # HISTORIAL
    # ==================================================================
    def reintentar_desde_historial(self, items: list) -> None:
        if self._descarga is not None and self._descarga.isRunning():
            QMessageBox.information(
                self,
                "Descarga en curso",
                "Espera a que termine la descarga actual antes de reintentar.",
            )
            return
        if not self._preparar_descarga():
            return

        urls: list[str] = []
        overrides: dict[str, str] = {}
        for item in items:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                url, calidad = str(item[0]).strip(), str(item[1] or "max")
            else:
                continue
            if not url.lower().startswith(("http://", "https://")):
                continue
            if url not in urls:
                urls.append(url)
            overrides[url] = calidad if calidad in CALIDADES else "max"

        if not urls:
            QMessageBox.information(
                self,
                "Nada que reintentar",
                "Las filas seleccionadas no contienen enlaces válidos.",
            )
            return

        self.cambiar_pagina(1)
        self._lanzar_descarga(
            urls,
            self.page_descargador.calidad_actual(),
            overrides,
            "reintento",
        )

    def eliminar_del_historial(self, ids: list) -> None:
        if not ids:
            return
        dialogo = DialogoConfirmacion(
            self,
            "Eliminar del historial",
            f"Se borrarán {len(ids)} entrada(s) del historial. Los archivos "
            "descargados NO se eliminan del disco.",
            texto_confirmar="Eliminar entradas",
            texto_cancelar="Cancelar",
            peligro=True,
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        borradas = self.historial.eliminar(ids)
        self.page_historial.refrescar()
        self.statusBar().showMessage(
            f"{borradas} entrada(s) eliminadas del historial.", 6000
        )

    # ==================================================================
    # ACTUALIZACIONES DE LA APLICACION
    # ==================================================================
    def _programar_comprobacion_automatica(self) -> None:
        """Consulta GitHub en segundo plano en cada arranque."""
        if not self.config.get("auto_buscar_actualizaciones", True):
            return
        QTimer.singleShot(5000, lambda: self.buscar_actualizaciones(False))

    def buscar_actualizaciones(self, manual: bool = True) -> None:
        if self._hilo_update is not None and self._hilo_update.isRunning():
            if manual:
                self.statusBar().showMessage(
                    "Ya se está comprobando la última release…", 5000
                )
            return

        self._update_manual = bool(manual)
        hilo = ComprobacionThread(self)
        hilo.resultado.connect(self._al_comprobar_actualizacion)
        self._hilo_update = hilo
        if manual:
            self.statusBar().showMessage("Buscando actualizaciones…", 4000)
        hilo.start()

    def _al_comprobar_actualizacion(self, resultado) -> None:
        self._hilo_update = None
        manual = self._update_manual
        try:
            self.config.set(
                "ultima_busqueda_actualizacion",
                datetime.now().isoformat(timespec="seconds"),
            )
        except Exception:
            pass

        if not getattr(resultado, "ok", False):
            _log.info("Comprobación de actualizaciones fallida: %s", resultado.error)
            if manual:
                self._mostrar_dialogo_actualizacion(resultado)
            return

        if manual:
            self._mostrar_dialogo_actualizacion(resultado)
            return

        if not resultado.hay_nueva:
            return
        tag = resultado.tag
        ignorada = str(self.config.get("version_ignorada", "") or "")
        if ignorada.strip().lower() == tag.strip().lower():
            _log.info("Actualización %s ignorada por el usuario", tag)
            return

        visible = self.isVisible() and not self.isMinimized()
        if not visible:
            self._notificar(
                "Actualización disponible",
                f"MarkOS {tag} está publicado. Abre ⋯ → Buscar actualizaciones "
                "para descargarlo.",
            )
            self.statusBar().showMessage(
                f"Actualización disponible: {tag}.", 12000
            )
            _log.info("Actualización disponible (en segundo plano): %s", tag)
            return

        dialogo = DialogoConfirmacion(
            self,
            "Actualización disponible",
            f"Hay una versión más reciente publicada en GitHub: {tag}.\n"
            f"Estás usando MarkOS {APP_VERSION}.\n\n"
            "¿Quieres descargarla ahora?",
            texto_confirmar="Sí, descargar",
            texto_cancelar="Ahora no",
            detalle=(
                "La descarga se realiza dentro de la app. Si la release "
                "incluye un .exe, se instalará al cerrar MarkOS."
            ),
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self._mostrar_dialogo_actualizacion(resultado, auto_descargar=True)
        else:
            self.statusBar().showMessage(
                f"Actualización {tag} pospuesta.", 8000
            )
        _log.info("Actualización disponible: %s", tag)

    def _mostrar_dialogo_actualizacion(
        self, resultado, auto_descargar: bool = False
    ) -> None:
        dialogo = DialogoActualizacion(
            self,
            resultado,
            str(self.config.get("version_ignorada", "") or ""),
            auto_descargar=auto_descargar,
        )
        dialogo.exec()

        if dialogo.ignorada:
            self.config.set("version_ignorada", dialogo.version_ignorada)
        elif dialogo.version_ignorada == "":
            if self.config.get("version_ignorada", ""):
                self.config.set("version_ignorada", "")

        if dialogo.ruta_instalacion:
            self._instalar_actualizacion(dialogo.ruta_instalacion)

    def _instalar_actualizacion(self, ruta: str) -> None:
        if not puede_autoinstalar():
            QMessageBox.information(
                self,
                "Actualización descargada",
                "La instalación automática solo está disponible en el EXE.\n\n"
                f"Archivo descargado:\n{ruta}",
            )
            return

        bat = preparar_instalacion(Path(ruta))
        if bat is None:
            QMessageBox.warning(
                self,
                "No se pudo preparar la instalación",
                "No se pudo crear el script de instalación. Abre la página "
                "de releases y descarga la nueva versión manualmente.",
            )
            return
        if not lanzar_instalador(bat):
            QMessageBox.warning(
                self,
                "No se pudo iniciar la instalación",
                "Cierra MarkOS y ejecuta el instalador generado en:\n\n"
                f"{bat}",
            )
            return

        self.statusBar().showMessage(
            "Instalando la actualización: MarkOS se reiniciará…", 5000
        )
        self._salir_de_verdad = True
        QTimer.singleShot(350, self.close)

    # ==================================================================
    # DEPENDENCIAS / AYUDA
    # ==================================================================
    def verificar_dependencias(self) -> None:
        if self._dependencias_verificadas:
            return
        self._dependencias_verificadas = True

        faltantes: list[tuple[str, str]] = []
        if get_ytdlp_path() is None:
            faltantes.append(
                (
                    "yt-dlp.exe",
                    "Es obligatorio para descargar. En el EXE debe viajar en "
                    "bin\\yt-dlp.exe; en desarrollo, instala yt-dlp con pip.",
                )
            )
        if get_ffmpeg_path() is None:
            faltantes.append(
                (
                    "ffmpeg.exe",
                    "Recomendado: sin él no se puede convertir a MP3 ni "
                    "fusionar audio y video en MP4.",
                )
            )
        elif get_ffprobe_path() is None:
            # ffprobe es opcional: no merece un dialogo modal al arrancar.
            self.page_descargador.append_log(
                "[!] ffprobe.exe no encontrado; yt-dlp usará ffmpeg para "
                "las comprobaciones básicas."
            )

        if not faltantes:
            self.page_descargador.append_log(
                "[OK] yt-dlp y FFmpeg detectados correctamente."
            )
            _log.info("Dependencias verificadas: OK")
            return

        for nombre, _detalle in faltantes:
            self.page_descargador.append_log(f"[!] Componente ausente: {nombre}")
        _log.warning("Dependencias ausentes: %s", [n for n, _ in faltantes])

        dialogo = DialogoDependencias(self, faltantes)
        dialogo.abrir_instrucciones_solicitado.connect(self.abrir_instrucciones)
        dialogo.exec()

        if any(nombre == "yt-dlp.exe" for nombre, _ in faltantes):
            self.page_descargador.boton_descargar.setEnabled(False)
            self.page_descargador.set_info(
                "Falta yt-dlp.exe: revisa las instrucciones y reinicia la app."
            )

    def _avisar_sin_ytdlp(self) -> None:
        dialogo = DialogoConfirmacion(
            self,
            "yt-dlp no encontrado",
            "No se encontró el ejecutable de yt-dlp. Sin él no se puede "
            "descargar ningún enlace.",
            texto_confirmar="Abrir Instrucciones.txt",
            texto_cancelar="Cerrar",
            peligro=True,
        )
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self.abrir_instrucciones()

    def abrir_instrucciones(self) -> None:
        exito, error = abrir_instrucciones()
        if not exito:
            QMessageBox.warning(
                self,
                "No se pudo abrir el archivo",
                "No se pudo abrir Instrucciones.txt.\n\n"
                f"{error}\n\n"
                "Puedes encontrarlo en la carpeta de datos de la aplicación.",
            )

    def abrir_carpeta_trabajo(self) -> None:
        try:
            asegurar_entorno()
            os.startfile(str(dir_trabajo()))  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.warning(
                self,
                "No se pudo abrir la carpeta",
                f"No se pudo abrir:\n{dir_trabajo()}\n\n{exc}",
            )

    def abrir_carpeta_datos(self) -> None:
        """Abre la carpeta de configuracion, logs e instrucciones."""
        try:
            ruta = dir_appdata()
            ruta.mkdir(parents=True, exist_ok=True)
            os.startfile(str(ruta))  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.warning(
                self,
                "No se pudo abrir la carpeta",
                f"No se pudo abrir:\n{dir_appdata()}\n\n{exc}",
            )

    def abrir_actualizador(self) -> None:
        """Abre el actualizador integrado de yt-dlp / FFmpeg."""
        dialogo = DialogoActualizador(self)
        dialogo.exec()

        if not dialogo.actualizado:
            return

        # Las rutas pueden haber cambiado: refresca el registro y avisa.
        ytdlp = get_ytdlp_path()
        ffmpeg = get_ffmpeg_path()
        self.page_descargador.append_log(
            "[OK] Dependencias actualizadas. Se usarán en la próxima descarga."
        )
        self.page_descargador.append_log(f"    yt-dlp: {ytdlp or 'no encontrado'}")
        self.page_descargador.append_log(f"    FFmpeg: {ffmpeg or 'no encontrado'}")
        if ytdlp is not None:
            self.page_descargador.boton_descargar.setEnabled(True)

    def limpiar_enlaces(self) -> None:
        """
        Vacia enlaces.txt y reinicia los contadores de la sesion.

        Se bloquea mientras el interceptor esta activo para no competir
        con el hilo de captura (el archivo se reescribe en cada enlace).
        """
        if self._interceptor is not None and self._interceptor.isRunning():
            QMessageBox.information(
                self,
                "Interceptor activo",
                "Detén el interceptor antes de limpiar los enlaces.",
            )
            return

        ruta = archivo_enlaces()
        cantidad = contar_enlaces()

        if cantidad == 0:
            self.page_interceptor.limpiar_lista()
            self._actualizar_cola()
            self.page_interceptor.mostrar_aviso(
                "No hay enlaces guardados: la lista ya estaba vacía."
            )
            return

        dialogo = DialogoConfirmacion(
            self,
            "Limpiar enlaces",
            f"Se borrarán {cantidad} enlace(s) de enlaces.txt.\n\n"
            "El historial de la sesión también se reinicia. "
            "Esta acción no se puede deshacer.",
            texto_confirmar="Limpiar enlaces",
            texto_cancelar="Cancelar",
            peligro=True,
        )
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            asegurar_entorno()
            ruta.write_text("", encoding="utf-8")
        except OSError as exc:
            _log.exception("No se pudo limpiar enlaces.txt")
            QMessageBox.warning(
                self,
                "No se pudo limpiar",
                f"No se pudo vaciar:\n{ruta}\n\n{exc}",
            )
            return

        self.page_interceptor.limpiar_lista()
        self.page_interceptor.set_capturados(0)
        self.page_interceptor.set_cola(0)
        self.lbl_cola.setText("Enlaces en cola: 0")
        self.page_interceptor.mostrar_aviso(
            f"Lista limpia: se borraron {cantidad} enlace(s)."
        )
        self.page_descargador.append_log(
            f"[OK] enlaces.txt vaciado ({cantidad} enlace(s) eliminados)."
        )
        _log.info("enlaces.txt vaciado desde la interfaz (%s enlaces)", cantidad)

    def mostrar_acerca_de(self) -> None:
        DialogoAcercaDe(self).exec()

    # ==================================================================
    # NOTIFICACIONES / NAVEGACION / CIERRE
    # ==================================================================
    def _notificar(self, titulo: str, mensaje: str) -> None:
        if self._tray is not None and self._tray.isVisible():
            if QSystemTrayIcon.supportsMessages():
                self._tray.showMessage(
                    titulo,
                    mensaje,
                    QSystemTrayIcon.MessageIcon.Information,
                    6000,
                )

    def cambiar_pagina(self, indice: int, animar: bool = True) -> None:
        if not 0 <= indice < self._stack.count():
            return

        anterior = self._stack.currentIndex()
        self._stack.setCurrentIndex(indice)
        self._botones_paso[indice].setChecked(True)
        self._actualizar_navegacion(indice)
        self.config.set("pestana", indice)

        if indice == 2:
            self.page_historial.refrescar()

        if animar and anterior != indice:
            self._animar_entrada_pagina(self._stack.currentWidget())
            self._animar_barra_paso(indice)
        else:
            self._barra_paso.setValue(indice + 1)

    # ------------------------------------------------------------------
    def closeEvent(self, evento: QCloseEvent) -> None:  # noqa: N802
        if (
            not self._salir_de_verdad
            and self._tray is not None
            and self.config.get("cerrar_a_bandeja", False)
        ):
            evento.ignore()
            self.ocultar_a_bandeja()
            return

        if self._descarga is not None and self._descarga.isRunning():
            dialogo = DialogoConfirmacion(
                self,
                "Cerrar durante la descarga",
                "Hay una descarga en curso. Si cierras ahora se cancelará.",
                texto_confirmar="Cerrar de todos modos",
                texto_cancelar="Seguir descargando",
                peligro=True,
            )
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                evento.ignore()
                return

        self._cerrando = True
        self._post_captura_pendiente = False

        if self._descarga is not None:
            self._descarga.detener()
            if not self._descarga.wait(5000):
                _log.warning("El hilo de descarga no terminó; se fuerza.")
                self._descarga.terminate()
                self._descarga.wait(1000)

        if self._interceptor is not None:
            self._interceptor.detener()
            if not self._interceptor.wait(3000):
                _log.warning("El interceptor no terminó; se fuerza.")
                self._interceptor.terminate()
                self._interceptor.wait(1000)

        if self._hilo_update is not None and self._hilo_update.isRunning():
            self._hilo_update.wait(2000)

        try:
            self.config.datos["geometria"] = bytes(
                self.saveGeometry().toBase64()
            ).decode("ascii")
            self.config.datos["pestana"] = self._stack.currentIndex()
            self.config.datos["primera_ejecucion"] = False
            self.config.guardar()
        except Exception as exc:
            _log.warning("No se pudo guardar el estado de la ventana: %s", exc)

        if self._tray is not None:
            self._tray.hide()

        _log.info("Aplicación cerrada")
        evento.accept()
