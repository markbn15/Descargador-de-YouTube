"""
ui/dialogs.py
====================================================================
Dialogos modales de la suite: confirmacion de acciones destructivas,
aviso de dependencias faltantes y "Acerca de".
====================================================================
"""

from __future__ import annotations

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from core.downloader import CALIDADES
from ui.theme import ROJO, ROJO_CLARO, pixmap_icono
from utils.paths import (
    APP_NAME,
    APP_VERSION,
    archivo_config,
    dir_appdata,
    dir_descargas,
    dir_trabajo,
)
from utils.resources import abrir_instrucciones, banner


class DialogoConfirmacion(QDialog):
    """
    Dialogo modal reutilizable. Devuelve QDialog.Accepted solo si el
    usuario pulsa el boton de confirmacion (no con la X ni con ESC).
    """

    def __init__(
        self,
        parent: QWidget | None,
        titulo: str,
        mensaje: str,
        texto_confirmar: str = "Continuar",
        texto_cancelar: str = "Cancelar",
        peligro: bool = False,
        detalle: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(titulo)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(14)

        fila = QHBoxLayout()
        fila.setSpacing(12)
        icono = QLabel("⚠" if peligro else "?")
        icono.setStyleSheet(
            f"color: {ROJO if peligro else ROJO_CLARO}; font-size: 25px; "
            "font-weight: 800; background: transparent;"
        )
        icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        textos = QVBoxLayout()
        textos.setSpacing(6)
        lbl_titulo = QLabel(titulo)
        lbl_titulo.setObjectName("DialogTitle")
        lbl_titulo.setWordWrap(True)
        lbl_mensaje = QLabel(mensaje)
        lbl_mensaje.setObjectName("DialogText")
        lbl_mensaje.setWordWrap(True)
        textos.addWidget(lbl_titulo)
        textos.addWidget(lbl_mensaje)
        fila.addWidget(icono)
        fila.addLayout(textos, 1)
        raiz.addLayout(fila)

        if detalle:
            lbl_detalle = QLabel(detalle)
            lbl_detalle.setObjectName("Hint")
            lbl_detalle.setWordWrap(True)
            raiz.addWidget(lbl_detalle)

        raiz.addStretch(1)

        botones = QHBoxLayout()
        botones.setSpacing(10)
        botones.addStretch(1)
        self.boton_cancelar = QPushButton(texto_cancelar)
        self.boton_cancelar.setObjectName("Ghost")
        self.boton_cancelar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_cancelar.clicked.connect(self.reject)
        self.boton_confirmar = QPushButton(texto_confirmar)
        self.boton_confirmar.setObjectName("Primary")
        self.boton_confirmar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_confirmar.clicked.connect(self.accept)
        botones.addWidget(self.boton_cancelar)
        botones.addWidget(self.boton_confirmar)
        raiz.addLayout(botones)

        self.boton_cancelar.setFocus()


class DialogoPostCaptura(QDialog):
    """
    Se muestra justo despues de detener el interceptor.

    Resume cuantos enlaces se capturaron, permite elegir la calidad y
    lanza la descarga sin obligar al usuario a cambiar de pestana.
    """

    abrir_carpeta_solicitado = Signal()

    def __init__(
        self,
        parent: QWidget | None,
        cantidad: int,
        calidad_inicial: str = "max",
    ) -> None:
        super().__init__(parent)
        self._cantidad = max(0, int(cantidad))
        self._calidad_inicial = (
            calidad_inicial if calidad_inicial in CALIDADES else "max"
        )
        self._botones: dict[str, QRadioButton] = {}

        self.setWindowTitle("Captura finalizada")
        self.setModal(True)
        self.setMinimumWidth(620)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(14)

        # ----- Cabecera -----
        cabecera = QHBoxLayout()
        cabecera.setSpacing(14)
        icono = QLabel("↓")
        icono.setFixedWidth(38)
        icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        icono.setStyleSheet(
            f"color: {ROJO}; font-size: 32px; font-weight: 900; "
            "background: transparent;"
        )
        textos = QVBoxLayout()
        textos.setSpacing(5)
        titulo = QLabel("Captura finalizada")
        titulo.setObjectName("DialogTitle")
        plural = "enlace capturado" if self._cantidad == 1 else "enlaces capturados"
        mensaje = QLabel(
            f"{self._cantidad} {plural} y listo(s) para descargar. "
            "Elige la calidad y pulsa «Descargar ahora»."
            if self._cantidad
            else "No se capturó ningún enlace en esta sesión."
        )
        mensaje.setObjectName("DialogText")
        mensaje.setWordWrap(True)
        textos.addWidget(titulo)
        textos.addWidget(mensaje)
        cabecera.addWidget(icono)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        # ----- Calidad -----
        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        v = QVBoxLayout(marco)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(10)

        etiqueta = QLabel("CALIDAD DE DESCARGA")
        etiqueta.setObjectName("CardTitle")
        v.addWidget(etiqueta)

        rejilla = QGridLayout()
        rejilla.setHorizontalSpacing(10)
        rejilla.setVerticalSpacing(9)
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)

        for i, (clave, datos) in enumerate(CALIDADES.items()):
            boton = QRadioButton(datos["etiqueta"])
            boton.setCursor(Qt.CursorShape.PointingHandCursor)
            boton.setToolTip(datos["descripcion"])
            boton.setProperty("calidad", clave)
            boton.setEnabled(self._cantidad > 0)
            boton.toggled.connect(
                lambda marcado, k=clave: self._al_cambiar_calidad(k, marcado)
            )
            self._grupo.addButton(boton)
            self._botones[clave] = boton
            if clave == "max":
                rejilla.addWidget(boton, i // 2, 0, 1, 2)
            else:
                rejilla.addWidget(boton, i // 2, i % 2)

        v.addLayout(rejilla)

        self.lbl_descripcion = QLabel("")
        self.lbl_descripcion.setObjectName("Hint")
        self.lbl_descripcion.setWordWrap(True)
        v.addWidget(self.lbl_descripcion)
        raiz.addWidget(marco)

        # ----- Destino -----
        destino = QHBoxLayout()
        destino.setSpacing(8)
        etiqueta_destino = QLabel("Carpeta de destino:")
        etiqueta_destino.setObjectName("Hint")
        self.lbl_destino = QLabel(str(dir_descargas()))
        self.lbl_destino.setObjectName("PathLabel")
        self.lbl_destino.setToolTip(str(dir_descargas()))
        self.lbl_destino.setWordWrap(True)
        boton_carpeta = QPushButton("Abrir")
        boton_carpeta.setObjectName("Ghost")
        boton_carpeta.setFixedWidth(82)
        boton_carpeta.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_carpeta.clicked.connect(self.abrir_carpeta_solicitado)
        destino.addWidget(etiqueta_destino)
        destino.addWidget(self.lbl_destino, 1)
        destino.addWidget(boton_carpeta)
        raiz.addLayout(destino)

        raiz.addStretch(1)

        # ----- Botones -----
        botones = QHBoxLayout()
        botones.setSpacing(10)
        boton_ahora_no = QPushButton("Ahora no")
        boton_ahora_no.setObjectName("Ghost")
        boton_ahora_no.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_ahora_no.clicked.connect(self.reject)

        self.boton_descargar = QPushButton("Descargar ahora")
        self.boton_descargar.setObjectName("Primary")
        self.boton_descargar.setMinimumWidth(170)
        self.boton_descargar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_descargar.setEnabled(self._cantidad > 0)
        self.boton_descargar.setDefault(True)
        self.boton_descargar.clicked.connect(self.accept)

        botones.addWidget(boton_ahora_no)
        botones.addStretch(1)
        botones.addWidget(self.boton_descargar)
        raiz.addLayout(botones)

        self.set_calidad(self._calidad_inicial)
        if self._cantidad > 0:
            self.boton_descargar.setFocus()
        else:
            boton_ahora_no.setFocus()

    # ------------------------------------------------------------------
    def _al_cambiar_calidad(self, clave: str, marcado: bool) -> None:
        if marcado:
            self.lbl_descripcion.setText(CALIDADES[clave]["descripcion"])

    def set_calidad(self, clave: str) -> None:
        clave = clave if clave in CALIDADES else "max"
        boton = self._botones.get(clave) or self._botones["max"]
        boton.setChecked(True)
        self.lbl_descripcion.setText(CALIDADES[clave]["descripcion"])

    def calidad(self) -> str:
        for clave, boton in self._botones.items():
            if boton.isChecked():
                return clave
        return "max"


class DialogoDescargaFinalizada(QDialog):
    """
    Resultado de la descarga con la pregunta explicita de abrir la
    carpeta DESCARGAS. Devuelve Accepted si el usuario quiere abrirla.
    """

    def __init__(
        self,
        parent: QWidget | None,
        exito: bool,
        resumen: str,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(
            "Descargas completadas" if exito else "Descarga con incidencias"
        )
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(14)

        cabecera = QHBoxLayout()
        cabecera.setSpacing(14)
        icono = QLabel("✓" if exito else "!")
        icono.setFixedWidth(38)
        icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        icono.setStyleSheet(
            f"color: {'#3DDC84' if exito else ROJO_CLARO}; font-size: 30px; "
            "font-weight: 900; background: transparent;"
        )
        textos = QVBoxLayout()
        textos.setSpacing(5)
        titulo = QLabel(
            "¡Descargas completadas!" if exito else "Descarga finalizada con incidencias"
        )
        titulo.setObjectName("DialogTitle")
        mensaje = QLabel(
            "Los archivos se guardaron correctamente en la carpeta DESCARGAS."
            if exito
            else "Algunos enlaces no se pudieron descargar. Revisa el registro "
            "en vivo para ver el detalle."
        )
        mensaje.setObjectName("DialogText")
        mensaje.setWordWrap(True)
        textos.addWidget(titulo)
        textos.addWidget(mensaje)
        cabecera.addWidget(icono)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        resumen_label = QLabel(resumen)
        resumen_label.setObjectName("Hint")
        resumen_label.setWordWrap(True)
        raiz.addWidget(resumen_label)

        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        mv = QVBoxLayout(marco)
        mv.setContentsMargins(16, 12, 16, 12)
        mv.setSpacing(4)
        etiqueta = QLabel("CARPETA DE DESCARGAS")
        etiqueta.setObjectName("CardTitle")
        ruta = QLabel(str(dir_descargas()))
        ruta.setObjectName("PathLabel")
        ruta.setWordWrap(True)
        ruta.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        mv.addWidget(etiqueta)
        mv.addWidget(ruta)
        raiz.addWidget(marco)

        pregunta = QLabel("¿Quieres abrir la carpeta donde se guardaron los archivos?")
        pregunta.setObjectName("DialogText")
        pregunta.setWordWrap(True)
        raiz.addWidget(pregunta)

        botones = QHBoxLayout()
        botones.setSpacing(10)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setObjectName("Ghost")
        boton_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_cerrar.clicked.connect(self.reject)
        boton_abrir = QPushButton("Abrir carpeta")
        boton_abrir.setObjectName("Primary")
        boton_abrir.setMinimumWidth(160)
        boton_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_abrir.setDefault(True)
        boton_abrir.clicked.connect(self.accept)
        botones.addWidget(boton_cerrar)
        botones.addStretch(1)
        botones.addWidget(boton_abrir)
        raiz.addLayout(botones)

        boton_abrir.setFocus()


class DialogoDependencias(QDialog):
    """
    Aviso al arrancar cuando falta yt-dlp o ffmpeg. Permite abrir las
    instrucciones sin cerrar la aplicacion.
    """

    abrir_instrucciones_solicitado = Signal()

    def __init__(
        self,
        parent: QWidget | None,
        faltantes: list[tuple[str, str]],
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Dependencias")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(14)

        titulo = QLabel("Faltan componentes opcionales")
        titulo.setObjectName("DialogTitle")
        raiz.addWidget(titulo)

        mensaje = QLabel(
            "La aplicación puede abrirse, pero algunas descargas fallarán. "
            "Revisa el archivo de instrucciones para instalar o restaurar "
            "estos componentes."
        )
        mensaje.setObjectName("DialogText")
        mensaje.setWordWrap(True)
        raiz.addWidget(mensaje)

        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        v = QVBoxLayout(marco)
        v.setContentsMargins(16, 12, 16, 12)
        v.setSpacing(10)
        for nombre, detalle in faltantes:
            fila = QHBoxLayout()
            fila.setSpacing(10)
            punto = QLabel("•")
            punto.setStyleSheet(
                f"color: {ROJO}; font-size: 18px; font-weight: 900; "
                "background: transparent;"
            )
            punto.setAlignment(Qt.AlignmentFlag.AlignTop)
            columna = QVBoxLayout()
            columna.setSpacing(2)
            lbl_nombre = QLabel(nombre)
            lbl_nombre.setStyleSheet(
                "font-family: 'Consolas'; "
                "font-weight: 700; background: transparent;"
            )
            lbl_detalle = QLabel(detalle)
            lbl_detalle.setObjectName("Hint")
            lbl_detalle.setWordWrap(True)
            columna.addWidget(lbl_nombre)
            columna.addWidget(lbl_detalle)
            fila.addWidget(punto)
            fila.addLayout(columna, 1)
            v.addLayout(fila)
        raiz.addWidget(marco)

        botones = QHBoxLayout()
        botones.setSpacing(10)
        boton_instrucciones = QPushButton("Abrir Instrucciones.txt")
        boton_instrucciones.setObjectName("Ghost")
        boton_instrucciones.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_instrucciones.clicked.connect(
            self.abrir_instrucciones_solicitado
        )
        boton_continuar = QPushButton("Continuar de todos modos")
        boton_continuar.setObjectName("Primary")
        boton_continuar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_continuar.clicked.connect(self.accept)
        botones.addWidget(boton_instrucciones)
        botones.addStretch(1)
        botones.addWidget(boton_continuar)
        raiz.addLayout(botones)


class DialogoAcercaDe(QDialog):
    """Informacion de version, rutas y banner ASCII."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {APP_NAME}")
        self.setModal(True)
        self.setMinimumWidth(580)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(12)

        cabecera = QHBoxLayout()
        logo = QLabel()
        logo.setPixmap(pixmap_icono(64))
        logo.setFixedSize(64, 64)
        textos = QVBoxLayout()
        textos.setSpacing(2)
        nombre = QLabel(APP_NAME)
        nombre.setObjectName("DialogTitle")
        version = QLabel(f"Versión {APP_VERSION} · PySide6 · yt-dlp")
        version.setObjectName("Hint")
        textos.addWidget(nombre)
        textos.addWidget(version)
        cabecera.addWidget(logo)
        cabecera.addSpacing(10)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        arte = QLabel(banner().rstrip())
        fuente = QFont("Consolas")
        fuente.setStyleHint(QFont.StyleHint.Monospace)
        fuente.setPointSize(8)
        arte.setFont(fuente)
        arte.setStyleSheet(
            f"color: {ROJO}; background-color: #0A0A0A; "
            "border: 1px solid #2B2B2B; border-radius: 8px; padding: 10px;"
        )
        arte.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raiz.addWidget(arte)

        rutas = QLabel(
            f"Datos y configuración:\n{dir_appdata()}\n\n"
            f"Carpeta de trabajo:\n{dir_trabajo()}"
        )
        rutas.setObjectName("PathLabel")
        rutas.setWordWrap(True)
        rutas.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        raiz.addWidget(rutas)

        botones = QHBoxLayout()
        botones.setSpacing(10)
        boton_datos = QPushButton("Abrir carpeta de datos")
        boton_datos.setObjectName("Ghost")
        boton_datos.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_datos.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(dir_appdata())))
        )
        boton_instrucciones = QPushButton("Instrucciones")
        boton_instrucciones.setObjectName("Ghost")
        boton_instrucciones.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_instrucciones.clicked.connect(self._abrir_instrucciones)
        boton_cerrar = QPushButton("Cerrar")
        boton_cerrar.setObjectName("Primary")
        boton_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        boton_cerrar.clicked.connect(self.accept)
        botones.addWidget(boton_datos)
        botones.addWidget(boton_instrucciones)
        botones.addStretch(1)
        botones.addWidget(boton_cerrar)
        raiz.addLayout(botones)

        self._lbl_error = QLabel("")
        self._lbl_error.setObjectName("Error")
        self._lbl_error.setWordWrap(True)
        raiz.addWidget(self._lbl_error)

        # Ruta mostrada tambien en el tooltip de config.json.
        self.setToolTip(str(archivo_config()))

    def _abrir_instrucciones(self) -> None:
        exito, error = abrir_instrucciones()
        if not exito:
            self._lbl_error.setText(f"No se pudo abrir el archivo: {error}")
