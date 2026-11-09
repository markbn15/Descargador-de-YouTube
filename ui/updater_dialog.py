"""
ui/updater_dialog.py
====================================================================
Dialogo del actualizador integrado de dependencias.

Permite elegir yt-dlp y/o FFmpeg, muestra progreso y registro en vivo,
y deja los binarios en %APPDATA%\\MarkOS_Downloader\\bin. La descarga
corre en UpdaterThread, por lo que la ventana sigue respondiendo.
====================================================================
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.updater import UpdaterThread
from ui.theme import ROJO
from utils.paths import dir_bin_usuario, get_ffmpeg_path, get_ytdlp_path


class DialogoActualizador(QDialog):
    """Actualiza yt-dlp/FFmpeg sin recompilar el EXE."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.actualizado = False
        self._hilo: UpdaterThread | None = None

        self.setWindowTitle("Actualizar dependencias")
        self.setModal(True)
        self.setMinimumWidth(680)
        self.setMinimumHeight(560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        raiz = QVBoxLayout(self)
        raiz.setContentsMargins(26, 22, 26, 20)
        raiz.setSpacing(12)

        # ----- Cabecera -----
        cabecera = QHBoxLayout()
        cabecera.setSpacing(14)
        icono = QLabel("↻")
        icono.setFixedWidth(38)
        icono.setAlignment(Qt.AlignmentFlag.AlignTop)
        icono.setStyleSheet(
            f"color: {ROJO}; font-size: 32px; font-weight: 900; "
            "background: transparent;"
        )
        textos = QVBoxLayout()
        textos.setSpacing(5)
        titulo = QLabel("Actualizar dependencias")
        titulo.setObjectName("DialogTitle")
        mensaje = QLabel(
            "Descarga las versiones más recientes de yt-dlp y/o FFmpeg. "
            "Se guardan en tu carpeta de datos y la app las usará en la "
            "próxima descarga, sin reinstalar el EXE."
        )
        mensaje.setObjectName("DialogText")
        mensaje.setWordWrap(True)
        textos.addWidget(titulo)
        textos.addWidget(mensaje)
        cabecera.addWidget(icono)
        cabecera.addLayout(textos, 1)
        raiz.addLayout(cabecera)

        # ----- Estado actual -----
        marco = QFrame()
        marco.setObjectName("Card")
        marco.setFrameShape(QFrame.Shape.NoFrame)
        mv = QVBoxLayout(marco)
        mv.setContentsMargins(16, 12, 16, 12)
        mv.setSpacing(6)
        etiqueta = QLabel("BINARIOS EN USO")
        etiqueta.setObjectName("CardTitle")
        self.lbl_actual = QLabel("")
        self.lbl_actual.setObjectName("PathLabel")
        self.lbl_actual.setWordWrap(True)
        self.lbl_actual.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        mv.addWidget(etiqueta)
        mv.addWidget(self.lbl_actual)
        raiz.addWidget(marco)

        # ----- Opciones -----
        opciones = QHBoxLayout()
        opciones.setSpacing(18)
        self.chk_ytdlp = QCheckBox("yt-dlp.exe  ·  recomendado")
        self.chk_ytdlp.setChecked(True)
        self.chk_ytdlp.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_ytdlp.setToolTip(
            "Actualiza el motor de descargas. Descarga pequeña y rápida."
        )
        self.chk_ffmpeg = QCheckBox("FFmpeg + ffprobe  ·  descarga grande")
        self.chk_ffmpeg.setCursor(Qt.CursorShape.PointingHandCursor)
        self.chk_ffmpeg.setToolTip(
            "Necesario para MP3 y para fusionar audio + video. ~100 MB."
        )
        opciones.addWidget(self.chk_ytdlp)
        opciones.addWidget(self.chk_ffmpeg)
        opciones.addStretch(1)
        raiz.addLayout(opciones)

        # ----- Progreso -----
        self.barra = QProgressBar()
        self.barra.setRange(0, 100)
        self.barra.setValue(0)
        self.barra.setTextVisible(False)
        raiz.addWidget(self.barra)

        self.lbl_estado = QLabel("Listo para actualizar.")
        self.lbl_estado.setObjectName("Hint")
        self.lbl_estado.setWordWrap(True)
        raiz.addWidget(self.lbl_estado)

        # ----- Registro -----
        self.log = QPlainTextEdit()
        self.log.setObjectName("Log")
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(600)
        self.log.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.log.setPlaceholderText(
            "Aquí verás el progreso de la descarga y los posibles errores."
        )
        raiz.addWidget(self.log, 1)

        # ----- Botones -----
        botones = QHBoxLayout()
        botones.setSpacing(10)
        self.boton_restaurar = QPushButton("Restaurar incluidos")
        self.boton_restaurar.setObjectName("Ghost")
        self.boton_restaurar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_restaurar.setToolTip(
            "Elimina los binarios actualizados y vuelve a usar los del EXE."
        )
        self.boton_restaurar.clicked.connect(self._restaurar)

        self.boton_cerrar = QPushButton("Cerrar")
        self.boton_cerrar.setObjectName("Ghost")
        self.boton_cerrar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_cerrar.clicked.connect(self.reject)

        self.boton_actualizar = QPushButton("Actualizar ahora")
        self.boton_actualizar.setObjectName("Primary")
        self.boton_actualizar.setMinimumWidth(170)
        self.boton_actualizar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.boton_actualizar.setDefault(True)
        self.boton_actualizar.clicked.connect(self._iniciar)

        botones.addWidget(self.boton_restaurar)
        botones.addStretch(1)
        botones.addWidget(self.boton_cerrar)
        botones.addWidget(self.boton_actualizar)
        raiz.addLayout(botones)

        self._actualizar_estado_actual()

    # ------------------------------------------------------------------
    def _texto_actual(self) -> str:
        ytdlp = get_ytdlp_path()
        ffmpeg = get_ffmpeg_path()
        return (
            f"yt-dlp:  {ytdlp or 'no encontrado'}\n"
            f"FFmpeg:  {ffmpeg or 'no encontrado'}\n"
            f"Destino: {dir_bin_usuario()}"
        )

    def _actualizar_estado_actual(self) -> None:
        self.lbl_actual.setText(self._texto_actual())

    # ------------------------------------------------------------------
    def _iniciar(self) -> None:
        if self._hilo is not None and self._hilo.isRunning():
            return

        ytdlp = self.chk_ytdlp.isChecked()
        ffmpeg = self.chk_ffmpeg.isChecked()
        if not ytdlp and not ffmpeg:
            QMessageBox.information(
                self,
                "Sin selección",
                "Marca al menos una dependencia para actualizar.",
            )
            return

        self.actualizado = False
        self.log.clear()
        self.barra.setValue(0)
        self.lbl_estado.setStyleSheet("")
        self.lbl_estado.setText("Iniciando actualización…")
        self._habilitar(False)

        hilo = UpdaterThread(ytdlp, ffmpeg, self)
        hilo.progreso.connect(self._al_progreso)
        hilo.log.connect(self._al_log)
        hilo.finalizado.connect(self._al_finalizar)
        self._hilo = hilo
        hilo.start()

    def _habilitar(self, habilitado: bool) -> None:
        self.chk_ytdlp.setEnabled(habilitado)
        self.chk_ffmpeg.setEnabled(habilitado)
        self.boton_actualizar.setEnabled(habilitado)
        self.boton_restaurar.setEnabled(habilitado)

    def _al_progreso(self, porcentaje: int, texto: str) -> None:
        self.barra.setValue(max(0, min(100, int(porcentaje))))
        if texto:
            self.lbl_estado.setText(texto)

    def _al_log(self, texto: str) -> None:
        self.log.appendPlainText(texto)
        barra = self.log.verticalScrollBar()
        barra.setValue(barra.maximum())

    def _al_finalizar(self, exito: bool, resumen: str) -> None:
        hilo = self._hilo
        if hilo is not None:
            hilo.wait(1500)
        self._hilo = None

        self.actualizado = exito
        self._habilitar(True)
        self.lbl_estado.setText(resumen)
        self.lbl_estado.setStyleSheet(
            f"color: {'#3DDC84' if exito else '#FF6B6B'};"
        )
        if exito:
            self.barra.setValue(100)
        self._actualizar_estado_actual()
        self.log.appendPlainText(
            f"[{'OK' if exito else 'FIN'}] {resumen}"
        )

    # ------------------------------------------------------------------
    def _restaurar(self) -> None:
        if self._hilo is not None and self._hilo.isRunning():
            return

        respuesta = QMessageBox.question(
            self,
            "Restaurar binarios incluidos",
            "Se eliminarán los binarios actualizados de tu carpeta de datos "
            "y la app volverá a usar los incluidos en el EXE.\n\n"
            "¿Quieres continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if respuesta != QMessageBox.StandardButton.Yes:
            return

        eliminados = 0
        for nombre in ("yt-dlp.exe", "ffmpeg.exe", "ffprobe.exe"):
            ruta = dir_bin_usuario() / nombre
            try:
                if ruta.is_file():
                    ruta.unlink()
                    eliminados += 1
            except OSError as exc:
                self.log.appendPlainText(f"[!] No se pudo borrar {ruta}: {exc}")

        self.actualizado = True
        self._actualizar_estado_actual()
        if eliminados:
            mensaje = f"Restaurados los binarios incluidos ({eliminados} archivo(s))."
        else:
            mensaje = "No había binarios actualizados; ya se usan los incluidos."
        self.lbl_estado.setText(mensaje)
        self.lbl_estado.setStyleSheet("color: #3DDC84;")
        self.log.appendPlainText(f"[OK] {mensaje}")

    # ------------------------------------------------------------------
    def reject(self) -> None:  # noqa: D401
        if self._hilo is not None and self._hilo.isRunning():
            respuesta = QMessageBox.question(
                self,
                "Actualización en curso",
                "La descarga está en curso. ¿Quieres cancelarla y cerrar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                return
            self._hilo.detener()
            self._hilo.wait(5000)
        super().reject()

    def closeEvent(self, evento) -> None:  # noqa: N802
        if self._hilo is not None and self._hilo.isRunning():
            respuesta = QMessageBox.question(
                self,
                "Actualización en curso",
                "La descarga está en curso. ¿Quieres cancelarla y cerrar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
            self._hilo.detener()
            self._hilo.wait(5000)
        evento.accept()
