"""
ui/theme.py
====================================================================
Paleta estricta rojo/negro y hoja de estilos Qt (QSS).

    Rojo principal : #E50914
    Rojo oscuro    : #C1121F
    Negro fondo    : #0D0D0D
    Panel          : #1A1A1A
    Borde/acento   : #2B2B2B
    Texto          : #F5F5F5
====================================================================
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPalette, QPixmap
from PySide6.QtWidgets import QApplication

from utils.resources import icono_png_bytes

ROJO = "#E50914"
ROJO_OSCURO = "#C1121F"
NEGRO = "#0D0D0D"
PANEL = "#1A1A1A"
BORDE = "#2B2B2B"
TEXTO = "#F5F5F5"
TEXTO_DIM = "#A8A8A8"
VERDE = "#3DDC84"
AMBAR = "#FFB020"
ROJO_CLARO = "#FF6B6B"


def pixmap_icono(tamano: int = 256) -> QPixmap:
    """Carga el PNG incrustado y lo escala con suavidad."""
    pixmap = QPixmap()
    datos = icono_png_bytes()
    if datos:
        pixmap.loadFromData(datos, "PNG")
    if pixmap.isNull():
        # Ultimo recurso: cuadrado rojo (nunca deberia ocurrir).
        pixmap = QPixmap(tamano, tamano)
        pixmap.fill(QColor(ROJO))
    return pixmap.scaled(
        tamano,
        tamano,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


def icono_app() -> QIcon:
    """Icono de ventana / bandeja del sistema."""
    return QIcon(pixmap_icono(256))


def aplicar_tema(app: QApplication) -> None:
    """Estilo Fusion + paleta oscura + QSS de la suite."""
    app.setStyle("Fusion")

    # Evita el flash blanco antes de que se aplique el QSS.
    paleta = QPalette()
    paleta.setColor(QPalette.ColorRole.Window, QColor(NEGRO))
    paleta.setColor(QPalette.ColorRole.WindowText, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    paleta.setColor(QPalette.ColorRole.AlternateBase, QColor("#222222"))
    paleta.setColor(QPalette.ColorRole.Text, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.Button, QColor(PANEL))
    paleta.setColor(QPalette.ColorRole.ButtonText, QColor(TEXTO))
    paleta.setColor(QPalette.ColorRole.Highlight, QColor(ROJO))
    paleta.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    paleta.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL))
    paleta.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXTO))
    app.setPalette(paleta)

    app.setStyleSheet(HOJA_ESTILOS)


HOJA_ESTILOS = """
/* ------------------------------------------------------------------
   Base
------------------------------------------------------------------ */
QWidget {
    background-color: #0D0D0D;
    color: #F5F5F5;
    font-family: "Segoe UI";
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #0D0D0D;
}
QScrollArea#PageScroll, QScrollArea#PageScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: #0D0D0D;
    width: 10px;
    margin: 0;
    border: none;
}
QScrollBar::handle:vertical {
    background: #383838;
    min-height: 32px;
    border-radius: 5px;
}
QScrollBar::handle:vertical:hover {
    background: #E50914;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar::add-page, QScrollBar::sub-page {
    background: transparent;
}
QToolTip {
    background-color: #1A1A1A;
    color: #F5F5F5;
    border: 1px solid #E50914;
    border-radius: 4px;
    padding: 6px 8px;
}
QLabel {
    background: transparent;
}

/* ------------------------------------------------------------------
   Navegación superior e inferior (sin panel lateral)
------------------------------------------------------------------ */
#TopBar {
    background-color: #111111;
    border-bottom: 1px solid #2B2B2B;
}
#BottomBar {
    background-color: #111111;
    border-top: 1px solid #2B2B2B;
}
#BrandName {
    font-size: 19px;
    font-weight: 800;
    color: #FFFFFF;
    letter-spacing: 0.5px;
}
#BrandTag {
    font-size: 9px;
    font-weight: 700;
    color: #E50914;
    letter-spacing: 2px;
}
#StepButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    color: #8F8F8F;
    padding: 8px 13px;
    font-size: 12px;
    font-weight: 600;
    text-align: center;
}
#StepButton:hover {
    background-color: #1A1A1A;
    color: #F5F5F5;
}
#StepButton:checked {
    background-color: #251012;
    border-color: #E50914;
    color: #FFFFFF;
}
#StepCounter {
    color: #8A8A8A;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.4px;
}
QProgressBar#StepProgress {
    background-color: #111111;
    border: none;
    border-radius: 0;
    min-height: 3px;
    max-height: 3px;
}
QProgressBar#StepProgress::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #C1121F, stop:1 #E50914);
    border-radius: 0;
}
QToolButton#MenuButton {
    background-color: transparent;
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    color: #C9C9C9;
    font-size: 18px;
    padding: 4px 9px;
}
QToolButton#MenuButton:hover {
    border-color: #E50914;
    color: #FFFFFF;
    background-color: #1A1A1A;
}
#LinkButton {
    background: transparent;
    border: none;
    color: #A8A8A8;
    font-size: 11px;
    text-align: left;
    padding: 4px 0;
}
#LinkButton:hover {
    color: #E50914;
}

/* ------------------------------------------------------------------
   Cabeceras y tarjetas
------------------------------------------------------------------ */
#PageTitle {
    font-size: 27px;
    font-weight: 800;
    color: #FFFFFF;
}
#PageSubtitle {
    color: #A8A8A8;
    font-size: 12px;
}
#Card {
    background-color: #1A1A1A;
    border: 1px solid #2B2B2B;
    border-radius: 12px;
}
#CardTitle {
    color: #A8A8A8;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
}
#StatValue {
    color: #FFFFFF;
    font-size: 30px;
    font-weight: 800;
}
#StatValueRed {
    color: #E50914;
    font-size: 30px;
    font-weight: 800;
}
#Hint {
    color: #7A7A7A;
    font-size: 11px;
}
#Warning {
    color: #FFB020;
    font-size: 11px;
}
#Error {
    color: #FF6B6B;
    font-size: 11px;
}
#PathLabel {
    color: #A8A8A8;
    font-family: "Consolas";
    font-size: 11px;
}
#SectionLabel {
    color: #A8A8A8;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}
#Chip {
    background-color: #241012;
    border: 1px solid #6E1017;
    border-radius: 10px;
    color: #FF9AA2;
    font-family: "Consolas";
    font-size: 11px;
    padding: 5px 10px;
}

/* ------------------------------------------------------------------
   Botones
------------------------------------------------------------------ */
QPushButton {
    background-color: #2B2B2B;
    border: 1px solid #3A3A3A;
    border-radius: 8px;
    color: #F5F5F5;
    padding: 9px 18px;
    font-weight: 600;
}
QPushButton:hover {
    background-color: #363636;
    border-color: #4A4A4A;
}
QPushButton:pressed {
    background-color: #222222;
}
QPushButton:disabled {
    background-color: #171717;
    border-color: #242424;
    color: #5E5E5E;
}
QPushButton#Primary {
    background-color: #E50914;
    border: 1px solid #E50914;
    color: #FFFFFF;
    font-weight: 700;
}
QPushButton#Primary:hover {
    background-color: #C1121F;
    border-color: #C1121F;
}
QPushButton#Primary:pressed {
    background-color: #8B0D14;
}
QPushButton#Primary:disabled {
    background-color: #3A1518;
    border-color: #3A1518;
    color: #8A5A5E;
}
QPushButton#Primary[modo="stop"] {
    background-color: #1A1A1A;
    border: 1px solid #E50914;
    color: #FF6B6B;
}
QPushButton#Primary[modo="stop"]:hover {
    background-color: #251012;
}
QPushButton#Ghost {
    background-color: transparent;
    border: 1px solid #2B2B2B;
    color: #C9C9C9;
}
QPushButton#Ghost:hover {
    border-color: #E50914;
    color: #FFFFFF;
}
QPushButton#Ghost:disabled {
    border-color: #232323;
    color: #5E5E5E;
}
QPushButton#Ghost[modo="pausa"] {
    border-color: #FFB020;
    color: #FFB020;
}
QPushButton#Danger {
    background-color: #1A1A1A;
    border: 1px solid #6E1017;
    color: #FF6B6B;
}
QPushButton#Danger:hover {
    background-color: #251012;
    border-color: #E50914;
    color: #FFFFFF;
}

/* ------------------------------------------------------------------
   Selector de calidad
------------------------------------------------------------------ */
QRadioButton {
    background-color: #141414;
    border: 1px solid #2B2B2B;
    border-radius: 9px;
    color: #C9C9C9;
    padding: 9px 12px;
    spacing: 10px;
}
QRadioButton:hover {
    border-color: #E50914;
    color: #FFFFFF;
}
QRadioButton:checked {
    background-color: #251012;
    border-color: #E50914;
    color: #FFFFFF;
    font-weight: 700;
}
QRadioButton:disabled {
    color: #5E5E5E;
    border-color: #222222;
    background-color: #121212;
}
QRadioButton::indicator {
    width: 15px;
    height: 15px;
    border-radius: 8px;
    border: 2px solid #555555;
    background-color: #0D0D0D;
}
QRadioButton::indicator:hover {
    border-color: #E50914;
}
QRadioButton::indicator:checked {
    border: 5px solid #E50914;
    background-color: #FFFFFF;
}

/* ------------------------------------------------------------------
   Casillas y actualizador
------------------------------------------------------------------ */
QCheckBox {
    color: #C9C9C9;
    spacing: 8px;
    font-size: 12px;
}
QCheckBox:hover {
    color: #FFFFFF;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #555555;
    border-radius: 4px;
    background-color: #0D0D0D;
}
QCheckBox::indicator:hover {
    border-color: #E50914;
}
QCheckBox::indicator:checked {
    background-color: #E50914;
    border-color: #E50914;
}
QCheckBox:disabled {
    color: #5E5E5E;
}

/* ------------------------------------------------------------------
   Progreso
------------------------------------------------------------------ */
QProgressBar {
    background-color: #111111;
    border: 1px solid #2B2B2B;
    border-radius: 7px;
    min-height: 13px;
    max-height: 13px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    border-radius: 6px;
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                                      stop:0 #C1121F, stop:1 #E50914);
}

/* ------------------------------------------------------------------
   Listas y log
------------------------------------------------------------------ */
QListWidget {
    background-color: #111111;
    border: 1px solid #2B2B2B;
    border-radius: 10px;
    padding: 4px;
    outline: none;
}
QListWidget::item {
    background-color: transparent;
    border-bottom: 1px solid #1E1E1E;
    color: #D6D6D6;
    padding: 9px 10px;
}
QListWidget::item:hover {
    background-color: #1A1A1A;
}
QListWidget::item:selected {
    background-color: #251012;
    color: #FFFFFF;
}
QPlainTextEdit#Log {
    background-color: #0A0A0A;
    border: 1px solid #2B2B2B;
    border-radius: 10px;
    color: #CFCFCF;
    font-family: "Consolas";
    font-size: 11px;
    padding: 8px;
    selection-background-color: #E50914;
}

/* ------------------------------------------------------------------
   Campos, desplegables y tablas
------------------------------------------------------------------ */
QLineEdit {
    background-color: #111111;
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    padding: 7px 10px;
    color: #F5F5F5;
    selection-background-color: #E50914;
}
QLineEdit:focus {
    border-color: #E50914;
    background-color: #141414;
}
QLineEdit::placeholder {
    color: #6E6E6E;
}
QComboBox {
    background-color: #111111;
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    padding: 6px 10px;
    padding-right: 26px;
    color: #F5F5F5;
    min-height: 21px;
}
QComboBox:hover, QComboBox:focus {
    border-color: #E50914;
}
QComboBox::drop-down {
    border: none;
    width: 24px;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #C9C9C9;
    margin-right: 9px;
}
QComboBox QAbstractItemView {
    background-color: #1A1A1A;
    border: 1px solid #2B2B2B;
    color: #F5F5F5;
    outline: none;
    selection-background-color: #E50914;
    selection-color: #FFFFFF;
}
QTableWidget {
    background-color: #111111;
    alternate-background-color: #151515;
    border: 1px solid #2B2B2B;
    border-radius: 10px;
    color: #D6D6D6;
    gridline-color: #1E1E1E;
    selection-background-color: #251012;
    selection-color: #FFFFFF;
    outline: none;
}
QTableWidget::item {
    padding: 7px 9px;
    border-bottom: 1px solid #1B1B1B;
}
QTableWidget::item:selected {
    background-color: #251012;
    color: #FFFFFF;
}
QHeaderView::section {
    background-color: #161616;
    color: #A8A8A8;
    border: none;
    border-bottom: 1px solid #2B2B2B;
    padding: 8px 9px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
}
QTableCornerButton::section {
    background-color: #161616;
    border: none;
}
QScrollBar:vertical {
    background: transparent;
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: #2B2B2B;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #E50914;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 10px;
    margin: 2px;
}
QScrollBar::handle:horizontal {
    background: #2B2B2B;
    border-radius: 4px;
    min-width: 24px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}

/* ------------------------------------------------------------------
   Barra de estado y menus
------------------------------------------------------------------ */
QStatusBar {
    background-color: #111111;
    border-top: 1px solid #2B2B2B;
    color: #A8A8A8;
    font-size: 11px;
}
QStatusBar QLabel {
    color: #A8A8A8;
    font-size: 11px;
    padding: 2px 6px;
}
QStatusBar::item {
    border: none;
}
QMenu {
    background-color: #1A1A1A;
    border: 1px solid #2B2B2B;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item {
    padding: 7px 24px 7px 14px;
    border-radius: 5px;
}
QMenu::item:selected {
    background-color: #E50914;
    color: #FFFFFF;
}
QMenu::separator {
    height: 1px;
    background: #2B2B2B;
    margin: 5px 8px;
}

/* ------------------------------------------------------------------
   Dialogos
------------------------------------------------------------------ */
QDialog QLabel#DialogTitle {
    font-size: 19px;
    font-weight: 800;
    color: #FFFFFF;
}
QDialog QLabel#DialogText {
    color: #C9C9C9;
    font-size: 12px;
}
QMessageBox {
    background-color: #1A1A1A;
}
QMessageBox QLabel {
    color: #F5F5F5;
}
"""
