"""
ui/pages.py
====================================================================
Paginas de la interfaz: Interceptor y Descargador.
Solo contienen presentacion y senales; la logica vive en main_window.py
y en los hilos de /core.
====================================================================
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGraphicsOpacityEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from core.downloader import CALIDADES
from ui.theme import ROJO, ROJO_CLARO, TEXTO_DIM, VERDE
from utils.paths import dir_descargas


class CabeceraPagina(QWidget):
    """Titulo grande + subtitulo, comun a las tres pestanas."""

    def __init__(self, titulo: str, subtitulo: str, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.titulo = QLabel(titulo)
        self.titulo.setObjectName("PageTitle")
        self.subtitulo = QLabel(subtitulo)
        self.subtitulo.setObjectName("PageSubtitle")
        self.subtitulo.setWordWrap(True)

        layout.addWidget(self.titulo)
        layout.addWidget(self.subtitulo)


class TarjetaEstadistica(QFrame):
    """Tarjeta con una cifra grande (capturados / en cola)."""

    def __init__(self, titulo: str, destacada: bool = False, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setMinimumHeight(96)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(2)

        etiqueta = QLabel(titulo.upper())
        etiqueta.setObjectName("CardTitle")
        self.valor = QLabel("0")
        self.valor.setObjectName("StatValueRed" if destacada else "StatValue")
        self.detalle = QLabel("")
        self.detalle.setObjectName("Hint")

        layout.addWidget(etiqueta)
        layout.addWidget(self.valor)
        layout.addWidget(self.detalle)

    def set_valor(self, valor: int | str, detalle: str | None = None) -> None:
        self.valor.setText(str(valor))
        if detalle is not None:
            self.detalle.setText(detalle)


# ======================================================================
# PAGINA 1: INTERCEPTOR
# ======================================================================
class PaginaInterceptor(QWidget):
    toggle_solicitado = Signal()
    abrir_carpeta_solicitado = Signal()
    limpiar_enlaces_solicitado = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._activo = False
        self._pulso_activo = False
        self._construir()

    # ------------------------------------------------------------------
    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 20, 26, 18)
        raiz.setSpacing(16)

        # Cabecera + boton principal
        fila = QHBoxLayout()
        fila.setSpacing(20)
        fila.addWidget(
            CabeceraPagina(
                "Interceptor",
                "Captura los enlaces que copies al portapapeles y guÃ¡rdalos "
                "en enlaces.txt, sin duplicados consecutivos. Al detener, "
                "elige la calidad y descarga al instante.",
            ),
            1,
        )
        self.boton_toggle = QPushButton("Iniciar captura")
        self.boton_toggle.setObjectName("Primary")
        self.boton_toggle.setFixedSize(196, 44)
        self.boton_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_toggle.clicked.connect(self.toggle_solicitado)
        fila.addWidget(self.boton_toggle, 0, Qt.AlignmentFlag.AlignTop)
        raiz.addLayout(fila)

        # Tarjeta de estado
        estado = QFrame()
        estado.setObjectName("Card")
        estado.setFrameShape(QFrame.Shape.NoFrame)
        h = QHBoxLayout(estado)
        h.setContentsMargins(18, 12, 18, 12)
        h.setSpacing(12)

        self.punto = QLabel("â—")
        self.punto.setStyleSheet(
            f"color: {TEXTO_DIM}; font-size: 18px; background: transparent;"
        )
        self._efecto_punto = QGraphicsOpacityEffect(self.punto)
        self._efecto_punto.setOpacity(1.0)
        self.punto.setGraphicsEffect(self._efecto_punto)
        self._anim_punto = QPropertyAnimation(self._efecto_punto, b"opacity", self)
        self._anim_punto.setDuration(950)
        self._anim_punto.setStartValue(0.3)
        self._anim_punto.setEndValue(1.0)
        self._anim_punto.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim_punto.setLoopCount(-1)
        textos = QVBoxLayout()
        textos.setSpacing(1)
        self.lbl_estado = QLabel("Interceptor detenido")
        self.lbl_estado.setStyleSheet("font-weight: 700; background: transparent;")
        self.lbl_detalle_estado = QLabel(
            "Pulsa Iniciar captura o Ctrl+I. Al detener podrÃ¡s elegir la calidad."
        )
        self.lbl_detalle_estado.setObjectName("Hint")
        textos.addWidget(self.lbl_estado)
        textos.addWidget(self.lbl_detalle_estado)

        atajo = QLabel("ESC global: detiene y ofrece descargar")
        atajo.setObjectName("Hint")
        atajo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        h.addWidget(self.punto)
        h.addLayout(textos, 1)
        h.addWidget(atajo)
        raiz.addWidget(estado)

        # Contadores
        contadores = QHBoxLayout()
        contadores.setSpacing(14)
        self.tarjeta_capturados = TarjetaEstadistica(
            "Enlaces capturados", destacada=True
        )
        self.tarjeta_cola = TarjetaEstadistica("En cola (enlaces.txt)")
        contadores.addWidget(self.tarjeta_capturados)
        contadores.addWidget(self.tarjeta_cola)
        raiz.addLayout(contadores)

        # Lista en vivo
        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        v = QVBoxLayout(marco)
        v.setContentsMargins(14, 12, 14, 14)
        v.setSpacing(8)

        fila_titulo = QHBoxLayout()
        titulo_lista = QLabel("ENLACES DETECTADOS EN ESTA SESIÃ“N")
        titulo_lista.setObjectName("CardTitle")
        self.lbl_contador_lista = QLabel("0")
        self.lbl_contador_lista.setObjectName("Hint")
        fila_titulo.addWidget(titulo_lista)
        fila_titulo.addStretch(1)
        fila_titulo.addWidget(self.lbl_contador_lista)
        v.addLayout(fila_titulo)

        self.lista = QListWidget()
        self.lista.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.lista.setWordWrap(True)
        self.lista.setAlternatingRowColors(False)
        self.lista.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        v.addWidget(self.lista, 1)
        raiz.addWidget(marco, 1)

        # Pie
        pie = QHBoxLayout()
        self.lbl_aviso = QLabel("")
        self.lbl_aviso.setObjectName("Warning")
        self.lbl_aviso.setWordWrap(True)
        self.lbl_aviso.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        self.boton_limpiar = QPushButton("Limpiar enlaces")
        self.boton_limpiar.setObjectName("Ghost")
        self.boton_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_limpiar.setToolTip(
            "VacÃ­a enlaces.txt y reinicia los contadores de la sesiÃ³n."
        )
        self.boton_limpiar.clicked.connect(self.limpiar_enlaces_solicitado)

        boton_carpeta = QPushButton("Abrir carpeta de trabajo")
        boton_carpeta.setObjectName("Ghost")
        boton_carpeta.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_carpeta.clicked.connect(self.abrir_carpeta_solicitado)
        pie.addWidget(self.lbl_aviso, 1)
        pie.addWidget(self.boton_limpiar)
        pie.addWidget(boton_carpeta)
        raiz.addLayout(pie)

    # ------------------------------------------------------------------
    def set_estado(self, activo: bool, texto: str, error: bool = False) -> None:
        self._activo = activo
        color = ROJO_CLARO if error else (VERDE if activo else TEXTO_DIM)
        self.punto.setStyleSheet(
            f"color: {color}; font-size: 18px; background: transparent;"
        )
        if activo:
            if not self._pulso_activo:
                self._anim_punto.start()
                self._pulso_activo = True
        else:
            if self._pulso_activo:
                self._anim_punto.stop()
                self._pulso_activo = False
            self._efecto_punto.setOpacity(1.0)
        self.lbl_estado.setText(texto)
        self.lbl_detalle_estado.setText(
            "Copiando enlacesâ€¦ al detener podrÃ¡s elegir la calidad."
            if activo
            else "Pulsa Iniciar captura o Ctrl+I. Al detener podrÃ¡s elegir la calidad."
        )

        self.boton_toggle.setText("Detener captura" if activo else "Iniciar captura")
        self.boton_toggle.setProperty("modo", "stop" if activo else "")
        self._repintar(self.boton_toggle)
        self.boton_toggle.setEnabled(True)

    def set_ocupado(self, ocupado: bool) -> None:
        """Deshabilita el boton mientras el hilo arranca o se detiene."""
        self.boton_toggle.setEnabled(not ocupado)

    def set_capturados(self, total: int) -> None:
        self.tarjeta_capturados.set_valor(total, "en esta sesiÃ³n")
        self.lbl_contador_lista.setText(f"{total} capturados")

    def set_cola(self, total: int) -> None:
        self.tarjeta_cola.set_valor(total, "listos para descargar")

    def agregar_enlace(self, url: str) -> None:
        texto = url if len(url) <= 110 else url[:107] + "â€¦"
        item = QListWidgetItem(f"  {texto}")
        item.setToolTip(url)
        self.lista.insertItem(0, item)
        # Limite defensivo para sesiones muy largas.
        while self.lista.count() > 1000:
            self.lista.takeItem(self.lista.count() - 1)

    def limpiar_lista(self) -> None:
        self.lista.clear()

    def mostrar_aviso(self, texto: str, error: bool = False) -> None:
        self.lbl_aviso.setObjectName("Error" if error else "Warning")
        self.lbl_aviso.setStyleSheet("")  # fuerza re-aplicar el selector
        self.lbl_aviso.setText(texto)
        self._repintar(self.lbl_aviso)

    def limpiar_aviso(self) -> None:
        self.lbl_aviso.setText("")

    @staticmethod
    def _repintar(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()


# ======================================================================
# PAGINA 2: DESCARGADOR
# ======================================================================
class PaginaDescargador(QWidget):
    descargar_solicitado = Signal(str)
    detener_solicitado = Signal()
    pausar_solicitado = Signal()
    abrir_carpeta_solicitado = Signal()
    perfiles_solicitado = Signal()
    calidad_cambiada = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._botones_calidad: dict[str, QRadioButton] = {}
        self._descargando = False
        self._anim_progreso: QPropertyAnimation | None = None
        self._construir()

    # ------------------------------------------------------------------
    def _construir(self) -> None:
        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 14, 26, 12)
        raiz.setSpacing(10)

        raiz.addWidget(
            CabeceraPagina(
                "Descargador",
                "Procesa todos los enlaces de enlaces.txt con yt-dlp. "
                "Los archivos se guardan en DESCARGAS y, al terminar, la app "
                "te pregunta si quieres abrir la carpeta.",
            )
        )

        # ---------------- Calidad ----------------
        tarjeta = QFrame()
        tarjeta.setObjectName("Card")
        tarjeta.setFrameShape(QFrame.Shape.NoFrame)
        v = QVBoxLayout(tarjeta)
        v.setContentsMargins(18, 12, 18, 12)
        v.setSpacing(10)

        fila_titulo = QHBoxLayout()
        fila_titulo.setSpacing(10)
        titulo = QLabel("CALIDAD DE DESCARGA")
        titulo.setObjectName("CardTitle")

        self.lbl_destino = QLabel("Destino:  DESCARGAS")
        self.lbl_destino.setObjectName("PathLabel")
        self.lbl_destino.setToolTip(str(dir_descargas()))
        boton_perfiles = QPushButton("Perfiles")
        boton_perfiles.setObjectName("Ghost")
        boton_perfiles.setFixedSize(82, 30)
        boton_perfiles.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_perfiles.setToolTip(
            "Asignar una calidad distinta a cada sitio (YouTube, Instagramâ€¦)."
        )
        boton_perfiles.clicked.connect(self.perfiles_solicitado)
        boton_abrir = QPushButton("Abrir")
        boton_abrir.setObjectName("Ghost")
        boton_abrir.setFixedSize(78, 30)
        boton_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_abrir.setToolTip(f"Abrir {dir_descargas()}")
        boton_abrir.clicked.connect(self.abrir_carpeta_solicitado)

        fila_titulo.addWidget(titulo)
        fila_titulo.addStretch(1)
        fila_titulo.addWidget(self.lbl_destino)
        fila_titulo.addWidget(boton_perfiles)
        fila_titulo.addWidget(boton_abrir)
        v.addLayout(fila_titulo)

        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(10)
        rejilla.setVerticalSpacing(8)

        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)
        claves = list(CALIDADES.keys())
        columnas = 3
        for i, clave in enumerate(claves):
            datos = CALIDADES[clave]
            boton = QRadioButton(datos["etiqueta"])
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setToolTip(datos["descripcion"])
            # Sin altura minima, un layout vertical ajustado comprime las
            # tarjetas y el texto de la calidad queda recortado.
            boton.setMinimumHeight(38)
            boton.setProperty("calidad", clave)
            boton.toggled.connect(
                lambda marcado, k=clave: self._al_cambiar_calidad(k, marcado)
            )
            self._grupo.addButton(boton)
            self._botones_calidad[clave] = boton

            fila, columna = divmod(i, columnas)
            if clave == "max":
                # La opcion recomendada ocupa el hueco restante de la fila.
                rejilla.addWidget(
                    boton, fila, columna, 1, columnas - columna
                )
            else:
                rejilla.addWidget(boton, fila, columna)

        v.addLayout(rejilla)
        raiz.addWidget(tarjeta)

        # ---------------- Progreso ----------------
        progreso_marco = QFrame()
        progreso_marco.setObjectName("Card")
        progreso_marco.setFrameShape(QFrame.Shape.NoFrame)
        pv = QVBoxLayout(progreso_marco)
        pv.setContentsMargins(18, 10, 18, 10)
        pv.setSpacing(8)

        fila_p = QHBoxLayout()
        self.lbl_item = QLabel("Esperando descargasâ€¦")
        self.lbl_item.setObjectName("Hint")
        self.lbl_item.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.lbl_porcentaje = QLabel("0%")
        self.lbl_porcentaje.setStyleSheet(
            f"color: {ROJO}; font-size: 15px; font-weight: 800; background: transparent;"
        )
        self.lbl_porcentaje.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        fila_p.addWidget(self.lbl_item, 1)
        fila_p.addWidget(self.lbl_porcentaje)
        pv.addLayout(fila_p)

        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setTextVisible(False)
        pv.addWidget(self.barra)
        raiz.addWidget(progreso_marco)

        # ---------------- Log ----------------
        fila_log = QHBoxLayout()
        etiqueta_log = QLabel("REGISTRO EN VIVO")
        etiqueta_log.setObjectName("SectionLabel")
        self.boton_limpiar = QPushButton("Limpiar registro")
        self.boton_limpiar.setObjectName("LinkButton")
        self.boton_limpiar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_limpiar.clicked.connect(lambda: self.log.clear())
        fila_log.addWidget(etiqueta_log)
        fila_log.addStretch(1)
        fila_log.addWidget(self.boton_limpiar)
        raiz.addLayout(fila_log)

        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(5000)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.setMinimumHeight(40)
        self.log.setPlaceholderText(
            "AquÃ­ aparecerÃ¡ la salida de yt-dlp cuando inicies una descarga."
        )
        raiz.addWidget(self.log, 1)

        # ---------------- Botones ----------------
        botones = QHBoxLayout()
        self.lbl_info = QLabel("")
        self.lbl_info.setObjectName("Hint")
        self.lbl_info.setWordWrap(True)
        self.boton_pausa = QPushButton("Pausar")
        self.boton_pausa.setObjectName("Ghost")
        self.boton_pausa.setFixedWidth(108)
        self.boton_pausa.setEnabled(False)
        self.boton_pausa.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_pausa.setToolTip(
            "Pausa la cola al terminar el enlace actual (Ctrl+Espacio)."
        )
        self.boton_pausa.clicked.connect(self.pausar_solicitado)
        self.boton_detener = QPushButton("Detener")
        self.boton_detener.setObjectName("Danger")
        self.boton_detener.setFixedWidth(120)
        self.boton_detener.setEnabled(False)
        self.boton_detener.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_detener.clicked.connect(self.detener_solicitado)
        self.boton_descargar = QPushButton("Descargar")
        self.boton_descargar.setObjectName("Primary")
        self.boton_descargar.setFixedWidth(180)
        self.boton_descargar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_descargar.clicked.connect(
            lambda: self.descargar_solicitado.emit(self.calidad_actual())
        )
        botones.addWidget(self.lbl_info, 1)
        botones.addWidget(self.boton_pausa)
        botones.addWidget(self.boton_detener)
        botones.addWidget(self.boton_descargar)
        raiz.addLayout(botones)

    # ------------------------------------------------------------------
    def _al_cambiar_calidad(self, clave: str, marcado: bool) -> None:
        if marcado:
            self.calidad_cambiada.emit(clave)

    def calidad_actual(self) -> str:
        for clave, boton in self._botones_calidad.items():
            if boton.isChecked():
                return clave
        return "max"

    def set_calidad(self, clave: str) -> None:
        boton = self._botones_calidad.get(clave) or self._botones_calidad["max"]
        boton.setChecked(True)

    def set_descargando(self, activo: bool) -> None:
        self._descargando = activo
        self.boton_descargar.setEnabled(not activo)
        self.boton_detener.setEnabled(activo)
        self.boton_pausa.setEnabled(activo)
        self.boton_pausa.setText("Pausar")
        self.boton_descargar.setText("Descargandoâ€¦" if activo else "Descargar")
        for boton in self._botones_calidad.values():
            boton.setEnabled(not activo)
        if not activo:
            self.lbl_item.setText("Listo.")

    def set_pausado(self, activo: bool, pendiente: bool = False) -> None:
        """Refleja la pausa real (o la solicitud mientras acaba el enlace)."""
        if activo:
            self.boton_pausa.setText("Pausandoâ€¦" if pendiente else "Reanudar")
            self.boton_pausa.setProperty("modo", "pausa")
            self.lbl_item.setText(
                "Pausa solicitada: terminarÃ¡ el enlace actual y se detendrÃ¡ la cola."
                if pendiente
                else "Cola en pausa. Pulsa Reanudar para continuar."
            )
        else:
            self.boton_pausa.setText("Pausar")
            self.boton_pausa.setProperty("modo", "")
            if self._descargando:
                self.lbl_item.setText("Descargandoâ€¦")
        self._repintar(self.boton_pausa)

    def set_progreso(self, porcentaje: int) -> None:
        valor = max(0, min(100, int(porcentaje)))
        self.lbl_porcentaje.setText(f"{valor}%")
        if valor == self.barra.value():
            return

        if (
            self._anim_progreso is not None
            and self._anim_progreso.state() == QAbstractAnimation.State.Running
        ):
            self._anim_progreso.setEndValue(valor)
            return

        animacion = QPropertyAnimation(self.barra, b"value", self)
        animacion.setDuration(180)
        animacion.setStartValue(self.barra.value())
        animacion.setEndValue(valor)
        animacion.setEasingCurve(QEasingCurve.Type.OutCubic)
        animacion.start()
        self._anim_progreso = animacion

    def set_item(self, indice: int, total: int, url: str) -> None:
        corta = url if len(url) <= 78 else url[:75] + "â€¦"
        self.lbl_item.setText(f"[{indice}/{total}]  {corta}")
        self.lbl_item.setToolTip(url)

    def reiniciar_progreso(self) -> None:
        if self._anim_progreso is not None:
            self._anim_progreso.stop()
        self.barra.setValue(0)
        self.lbl_porcentaje.setText("0%")
        self.lbl_item.setText("Preparando descargaâ€¦")
        self.lbl_item.setToolTip("")

    def append_log(self, texto: str) -> None:
        barra = self.log.verticalScrollBar()
        estaba_abajo = barra.value() >= barra.maximum() - 4
        self.log.appendPlainText(texto)
        if estaba_abajo:
            barra.setValue(barra.maximum())

    def set_info(self, texto: str) -> None:
        self.lbl_info.setText(texto)

    @staticmethod
    def _repintar(widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.update()

