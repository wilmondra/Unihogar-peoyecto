import sys
import time
import hashlib

import validaciones as val
from validaciones import limpiar_telefono

from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QVBoxLayout,
    QHBoxLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QMessageBox,
    QMainWindow,
    QScrollArea,
    QGridLayout,
    QComboBox,
    QButtonGroup,
    QTextEdit,
    QSpinBox,
    QFileDialog,
    QInputDialog,
    QColorDialog,
    QDialog,
    QCheckBox
)

from PySide6.QtGui import QColor, QImage, QPixmap, QPalette
from PySide6.QtCore import (
    Qt, QByteArray, QBuffer, QIODevice, QTimer, QPoint,
    QObject, QThread, Signal
)

from conexion import ConexionBD
from dao import DAO
from reporte_admin import generar_reporte_admin, generar_reporte_admin_excel
from servicios import api_service


# Solo prueba la conexión y la cierra (antes quedaba abierta).
conexion_db = ConexionBD()
conexion_db.desconectar(conexion_db.conectar())

dao = DAO()
dao.preparar_base_datos()


def color_usuario(usuario):

    colores = [
        "#2563EB",
        "#7C3AED",
        "#DB2777",
        "#DC2626",
        "#EA580C",
        "#CA8A04",
        "#059669",
        "#0891B2",
        "#4F46E5",
        "#9333EA"
    ]

    valor = int(
        hashlib.md5(
            usuario.encode("utf-8")
        ).hexdigest(),
        16
    )

    return colores[
        valor % len(colores)
    ]


ROLES = {
    "administrador": "Administrador",
    "estudiante": "Estudiante",
    "arrendador": "Arrendador"
}

COLORES_ROL = {
    "administrador": "#DC2626",
    "estudiante": "#2563EB",
    "arrendador": "#059669"
}


def crear_insignia_rol(rol, texto=None):
    """Etiqueta de color que identifica el rol del usuario."""

    insignia = QLabel(
        texto or ROLES.get(rol, "Estudiante").upper()
    )

    insignia.setAlignment(
        Qt.AlignmentFlag.AlignCenter
    )

    insignia.setStyleSheet(f"""
        background: {COLORES_ROL.get(rol, "#2563EB")};
        color: white;
        border-radius: 9px;
        padding: 3px 12px;
        font-size: 10px;
        font-weight: bold;
    """)

    return insignia


# Estilo propio para los diálogos de Qt (color, texto, etc.). Sin esto
# heredan el tema de Windows y el texto/los campos quedan casi
# invisibles (blanco sobre claro).
ESTILO_DIALOGO = """
    QDialog, QColorDialog, QInputDialog {
        background: #FFFFFF;
        color: #111827;
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }
    QDialog QLabel, QColorDialog QLabel, QInputDialog QLabel {
        background: transparent;
        color: #111827;
    }
    QDialog QLineEdit, QColorDialog QLineEdit, QInputDialog QLineEdit,
    QColorDialog QAbstractSpinBox {
        background: #FFFFFF;
        color: #111827;
        selection-background-color: #2563EB;
        selection-color: #FFFFFF;
    }
    QDialog QPushButton, QColorDialog QPushButton,
    QInputDialog QPushButton {
        background: #E5E7EB;
        color: #111827;
        border: 1px solid #9CA3AF;
        border-radius: 6px;
        padding: 7px 16px;
        min-width: 70px;
    }
    QDialog QPushButton:hover, QColorDialog QPushButton:hover,
    QInputDialog QPushButton:hover {
        background: #D1D5DB;
    }
    QDialog QPushButton:default, QColorDialog QPushButton:default,
    QInputDialog QPushButton:default {
        background: #2563EB;
        color: #FFFFFF;
        border: 1px solid #1D4ED8;
        font-weight: bold;
    }
"""

COLOR_DEFECTO = {
    "administrador": "#991B1B",
    "estudiante": "#1E3A8A",
    "arrendador": "#047857"
}

PALETA_COLORES = [
    ("Azul", "#1E3A8A"),
    ("Índigo", "#4338CA"),
    ("Morado", "#6B21A8"),
    ("Rosa", "#BE185D"),
    ("Rojo", "#991B1B"),
    ("Naranja", "#C2410C"),
    ("Verde", "#047857"),
    ("Turquesa", "#0F766E"),
    ("Grafito", "#1F2937")
]

SUBTITULOS_ROL = {
    "estudiante": (
        "Encuentra tu próximo hogar "
        "cerca de tu universidad en León"
    ),
    "arrendador": (
        "Publica y maneja tus propiedades "
        "con fotos y todos sus datos"
    ),
    "administrador": (
        "Control de estudiantes, "
        "arrendadores y solicitudes"
    )
}

ESTADOS_VERIFICACION = {
    "aprobada": ("Aprobado", "#059669"),
    "pendiente": ("En espera", "#D97706"),
    "rechazada": ("Rechazada", "#DC2626")
}

ESTILO_TARJETA = """
    QFrame#tarjeta {
        background: white;
        border-radius: 14px;
    }
    QLabel {
        background: transparent;
        color: #111827;
    }
    QLineEdit, QTextEdit {
        background: #FAFBFC;
        border: 2px solid #E2E5EB;
        border-radius: 9px;
        padding: 8px 12px;
        color: #111827;
        font-size: 13px;
    }
"""


def imagen_a_bytes(ruta, ancho_max=1200):
    """Carga una imagen, la reduce y la devuelve como bytes JPEG."""

    imagen = QImage(ruta)

    if imagen.isNull():
        return None

    if imagen.width() > ancho_max:
        imagen = imagen.scaledToWidth(
            ancho_max,
            Qt.TransformationMode.SmoothTransformation
        )

    imagen = imagen.convertToFormat(
        QImage.Format.Format_RGB32
    )

    datos = QByteArray()

    buffer = QBuffer(datos)

    buffer.open(QIODevice.OpenModeFlag.WriteOnly)

    imagen.save(buffer, "JPG", 85)

    buffer.close()

    return bytes(datos.data())


def pixmap_desde_bytes(datos, ancho, alto):

    if not datos:
        return None

    pixmap = QPixmap()

    if not pixmap.loadFromData(datos):
        return None

    return pixmap.scaled(
        ancho,
        alto,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation
    )


def pixmap_recortado(datos, ancho, alto):
    """Como pixmap_desde_bytes, pero llena todo el marco
    recortando lo que sobre (para portadas)."""

    if not datos:
        return None

    pixmap = QPixmap()

    if not pixmap.loadFromData(datos):
        return None

    pixmap = pixmap.scaled(
        ancho,
        alto,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation
    )

    x = max(0, (pixmap.width() - ancho) // 2)
    y = max(0, (pixmap.height() - alto) // 2)

    return pixmap.copy(x, y, ancho, alto)


def crear_miniatura(datos, ancho, alto, llenar=False):

    etiqueta = QLabel()

    etiqueta.setFixedSize(ancho, alto)

    etiqueta.setAlignment(
        Qt.AlignmentFlag.AlignCenter
    )

    if llenar:
        pixmap = pixmap_recortado(datos, ancho, alto)
    else:
        pixmap = pixmap_desde_bytes(datos, ancho, alto)

    if pixmap:
        etiqueta.setPixmap(pixmap)
        etiqueta.setStyleSheet(
            "background: #F3F4F6; border-radius: 10px;"
        )
    else:
        etiqueta.setText("Sin imagen")
        etiqueta.setStyleSheet(
            "background: #F3F4F6; color: #9CA3AF; "
            "border-radius: 10px; font-size: 12px;"
        )

    return etiqueta


def crear_tarjeta():

    tarjeta = QFrame()

    tarjeta.setObjectName("tarjeta")

    tarjeta.setStyleSheet(ESTILO_TARJETA)

    return tarjeta


def crear_chip(texto, color):

    chip = QLabel(texto)

    chip.setAlignment(Qt.AlignmentFlag.AlignCenter)

    chip.setStyleSheet(f"""
        background: {color};
        color: white;
        border-radius: 9px;
        padding: 3px 12px;
        font-size: 11px;
        font-weight: bold;
    """)

    return chip


def boton_accion(texto, color):

    boton = QPushButton(texto)

    boton.setCursor(
        Qt.CursorShape.PointingHandCursor
    )

    hover = QColor(color).darker(115).name()

    boton.setStyleSheet(f"""
        QPushButton {{
            background: {color};
            color: white;
            border: none;
            border-radius: 8px;
            padding: 9px 18px;
            font-size: 13px;
            font-weight: bold;
        }}
        QPushButton:hover {{
            background: {hover};
        }}
    """)

    return boton


def nivel_precio(precio):

    precio = float(precio)

    if precio <= 2500:
        return "Económico", "#0F9D6B", "#E4F8EF"

    if precio <= 4000:
        return "Moderado", "#B7791F", "#FDF3DA"

    return "Elevado", "#C0392B", "#FBE5E1"


class TrabajadorTasa(QObject):
    """Consulta la API en un hilo aparte para no congelar la ventana."""

    terminado = Signal(dict)
    fallo = Signal(str)

    def run(self):
        try:
            self.terminado.emit(
                api_service.consultar_tasa_cordoba(usar_cache=False)
            )
        except api_service.ErrorAPI as error:
            self.fallo.emit(str(error))
        except Exception as error:
            self.fallo.emit(f"Error inesperado: {error}")


class TarjetaPropiedad(QFrame):

    def __init__(self, datos, parent=None):

        super().__init__(parent)

        self.datos = datos
        self.parent_principal = parent

        etiqueta, color_texto, color_fondo = nivel_precio(
            datos["precio"]
        )

        self.setObjectName("tarjeta")

        self.setStyleSheet(f"""
            QFrame#tarjeta {{
                background: white;
                border-radius: 14px;
                border-left: 5px solid {color_texto};
            }}
        """)

        self.setMinimumHeight(350)

        sombra = QGraphicsDropShadowEffect()

        sombra.setBlurRadius(20)
        sombra.setXOffset(0)
        sombra.setYOffset(4)
        sombra.setColor(
            QColor(30, 58, 138, 35)
        )

        self.setGraphicsEffect(sombra)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            18,
            16,
            18,
            16
        )

        layout.setSpacing(6)

        portada = dao.obtener_portada_propiedad(
            datos["id_propiedad"]
        )

        miniatura = crear_miniatura(
            portada, 250, 120, llenar=True
        )

        layout.addWidget(
            miniatura,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        fila_superior = QHBoxLayout()

        chip = QLabel(etiqueta)

        chip.setStyleSheet(f"""
            background: {color_fondo};
            color: {color_texto};
            font-size: 11px;
            font-weight: bold;
            padding: 3px 10px;
            border-radius: 9px;
        """)

        fila_superior.addWidget(chip)
        fila_superior.addStretch()

        if datos["verificado"]:

            verificado = QLabel(
                "✔ Revisado"
            )

            verificado.setStyleSheet("""
                color: #1E3A8A;
                font-size: 11px;
                font-weight: bold;
            """)

            fila_superior.addWidget(
                verificado
            )

        layout.addLayout(
            fila_superior
        )

        titulo = QLabel(
            datos["titulo"]
        )

        titulo.setWordWrap(True)

        titulo.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: #111827;
        """)

        layout.addWidget(titulo)

        zona = QLabel(
            f"📍 {datos['zona']}"
        )

        zona.setWordWrap(True)

        zona.setStyleSheet("""
            color: #6B7280;
            font-size: 12px;
        """)

        layout.addWidget(zona)

        distancia = QLabel(
            f"🎓 {datos['universidad']} · "
            f"🚶 {datos['distancia']}"
        )

        distancia.setWordWrap(True)

        distancia.setStyleSheet("""
            color: #6B7280;
            font-size: 12px;
        """)

        layout.addWidget(
            distancia
        )

        amenidades = QLabel(
            " · ".join(
                datos.get(
                    "amenidades",
                    []
                )
            )
        )

        amenidades.setWordWrap(True)

        amenidades.setStyleSheet("""
            color: #9CA3AF;
            font-size: 11px;
        """)

        layout.addWidget(
            amenidades
        )

        layout.addStretch()

        fila_inferior = QHBoxLayout()

        precio = QLabel(
            f"C$ {float(datos['precio']):,.0f} /mes"
        )

        precio.setStyleSheet("""
            color: #1E3A8A;
            font-size: 16px;
            font-weight: bold;
        """)

        fila_inferior.addWidget(
            precio
        )

        fila_inferior.addStretch()

        favorito = QPushButton(
            "♡"
        )

        favorito.setFixedSize(
            38,
            34
        )

        favorito.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        favorito.setStyleSheet("""
            QPushButton {
                background: #F3F4F6;
                color: #DC2626;
                border: none;
                border-radius: 7px;
                font-size: 20px;
            }

            QPushButton:hover {
                background: #FEE2E2;
            }
        """)

        favorito.clicked.connect(
            self.agregar_favorito
        )

        # Solo los estudiantes guardan favoritos.
        if not parent or getattr(
            parent, "rol", "estudiante"
        ) == "estudiante":
            fila_inferior.addWidget(
                favorito
            )
        else:
            favorito.hide()

        boton = QPushButton(
            "Ver detalles"
        )

        boton.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        boton.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 7px 14px;
                font-size: 12px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1D4ED8;
            }

            QPushButton:pressed {
                background: #1E40AF;
            }
        """)

        boton.clicked.connect(
            self.mostrar_detalles
        )

        fila_inferior.addWidget(
            boton
        )

        layout.addLayout(
            fila_inferior
        )

    def agregar_favorito(self):

        if not self.parent_principal:
            return

        id_usuario = (
            self.parent_principal.id_usuario
        )

        id_propiedad = (
            self.datos["id_propiedad"]
        )

        if dao.es_favorito(
            id_usuario,
            id_propiedad
        ):

            resultado = dao.quitar_favorito(
                id_usuario,
                id_propiedad
            )

            if resultado:

                QMessageBox.information(
                    self,
                    "Favorito",
                    "La propiedad se eliminó de favoritos."
                )

        else:

            resultado = dao.agregar_favorito(
                id_usuario,
                id_propiedad
            )

            if resultado:

                QMessageBox.information(
                    self,
                    "Favorito",
                    "La propiedad se agregó a favoritos."
                )

    def mostrar_detalles(self):

        ventana = VentanaDetalles(
            self.datos,
            self.parent_principal
        )

        ventana.show()

        self.ventana_detalles = ventana


class VentanaDetalles(QWidget):

    def __init__(
        self,
        datos,
        principal
    ):

        super().__init__()

        self.datos = datos
        self.principal = principal

        self.setWindowTitle(
            "Detalles de la propiedad"
        )

        self.resize(
            720,
            780
        )

        self.setStyleSheet("""
            QWidget {
                background: #EEF2F9;
                font-family: "Segoe UI", Arial;
            }

            QFrame {
                background: white;
                border-radius: 12px;
            }

            QLabel {
                color: #111827;
            }

            QLineEdit,
            QTextEdit,
            QSpinBox {
                background: white;
                color: #000000;
                border: 2px solid #D1D5DB;
                border-radius: 8px;
                padding: 8px;
            }

            QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 9px 15px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1D4ED8;
            }

            QMessageBox {
                background: white;
                color: #111827;
            }

            QMessageBox QLabel {
                color: #111827;
                background: transparent;
            }

            QMessageBox QPushButton {
                background: #2563EB;
                color: white;
            }
        """)

        principal_layout = QVBoxLayout(
            self
        )

        principal_layout.setContentsMargins(
            25,
            25,
            25,
            25
        )

        desplazable = QScrollArea()

        desplazable.setWidgetResizable(True)

        desplazable.setStyleSheet(
            "QScrollArea { border: none; }"
        )

        contenido_scroll = QWidget()

        self.layout_contenido = QVBoxLayout(
            contenido_scroll
        )

        self.layout_contenido.setContentsMargins(
            0, 0, 0, 0
        )

        desplazable.setWidget(contenido_scroll)

        principal_layout.addWidget(desplazable)

        tarjeta = QFrame()

        layout = QVBoxLayout(
            tarjeta
        )

        titulo = QLabel(
            self.datos["titulo"]
        )

        titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 23px;
            font-weight: bold;
        """)

        layout.addWidget(
            titulo
        )

        self._fotos = dao.obtener_fotos_propiedad(
            self.datos["id_propiedad"]
        )

        self._indice_foto = 0

        self.visor_foto = QLabel()

        self.visor_foto.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.visor_foto.setFixedHeight(300)

        self.visor_foto.setStyleSheet("""
            background: #E5E7EB;
            color: #6B7280;
            border-radius: 10px;
            font-size: 14px;
        """)

        layout.addWidget(
            self.visor_foto
        )

        navegacion = QHBoxLayout()

        self.boton_anterior = QPushButton("◀")

        self.boton_siguiente = QPushButton("▶")

        self.contador_fotos = QLabel("")

        self.contador_fotos.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.contador_fotos.setStyleSheet(
            "color: #6B7280; font-size: 12px; "
            "background: transparent;"
        )

        self.boton_anterior.clicked.connect(
            lambda: self._cambiar_foto(-1)
        )

        self.boton_siguiente.clicked.connect(
            lambda: self._cambiar_foto(1)
        )

        navegacion.addWidget(self.boton_anterior)
        navegacion.addWidget(self.contador_fotos, 1)
        navegacion.addWidget(self.boton_siguiente)

        layout.addLayout(navegacion)

        self._mostrar_foto()

        datos_texto = QLabel(
            f"📍 Zona: {self.datos['zona']}\n"
            + (
                f"🏠 Dirección: {self.datos['direccion']}\n"
                if self.datos.get("direccion") else ""
            )
            + (
                f"🛏 Habitaciones: {self.datos['habitaciones']}\n"
                if self.datos.get("habitaciones") else ""
            )
            + (
                f"🛌 Camas: {self.datos['camas']}\n"
                if self.datos.get("camas") else ""
            )
            + (
                f"🚿 Baños: {self.datos['banos']}\n"
                if self.datos.get("banos") else ""
            )
            + (
                f"📞 Teléfono: {self.datos['telefono']}\n"
                if self.datos.get("telefono") else ""
            ) +
            f"🎓 Universidad: {self.datos['universidad']}\n"
            f"🚶 Distancia: {self.datos['distancia']}\n"
            f"🏠 Tipo: {self.datos['tipo']}\n"
            f"💰 Precio: C$ {float(self.datos['precio']):,.0f} /mes\n"
            f"✔ Revisado por el admin: "
            f"{'Sí' if self.datos['verificado'] else 'No'}"
        )

        datos_texto.setWordWrap(True)

        datos_texto.setStyleSheet("""
            color: #374151;
            font-size: 13px;
            padding: 10px;
        """)

        layout.addWidget(
            datos_texto
        )

        if self.datos.get("descripcion"):

            titulo_desc = QLabel(
                "Información de la casa"
            )

            titulo_desc.setStyleSheet("""
                color: #1E3A8A;
                font-size: 16px;
                font-weight: bold;
            """)

            layout.addWidget(titulo_desc)

            texto_desc = QLabel(
                self.datos["descripcion"]
            )

            texto_desc.setWordWrap(True)

            texto_desc.setStyleSheet("""
                color: #374151;
                font-size: 13px;
                padding-bottom: 10px;
            """)

            layout.addWidget(texto_desc)

        amenidades_titulo = QLabel(
            "Servicios"
        )

        amenidades_titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 16px;
            font-weight: bold;
        """)

        layout.addWidget(
            amenidades_titulo
        )

        amenidades = QLabel(
            " · ".join(
                self.datos.get(
                    "amenidades",
                    []
                )
            )
        )

        amenidades.setWordWrap(True)

        amenidades.setStyleSheet("""
            color: #374151;
            padding-bottom: 10px;
        """)

        layout.addWidget(
            amenidades
        )

        titulo_revision = QLabel(
            "Deja una reseña"
        )

        titulo_revision.setStyleSheet("""
            color: #1E3A8A;
            font-size: 16px;
            font-weight: bold;
        """)

        layout.addWidget(
            titulo_revision
        )

        self.calificacion = QSpinBox()

        self.calificacion.setRange(
            1,
            5
        )

        self.calificacion.setValue(
            5
        )

        layout.addWidget(
            self.calificacion
        )

        self.campo_revision = QTextEdit()

        self.campo_revision.setPlaceholderText(
            "Escribe tu experiencia..."
        )

        layout.addWidget(
            self.campo_revision
        )

        boton_guardar = QPushButton(
            "Guardar reseña"
        )

        boton_guardar.clicked.connect(
            self.guardar_revision
        )

        layout.addWidget(
            boton_guardar
        )

        if principal and principal.rol != "estudiante":

            for widget in (
                titulo_revision,
                self.calificacion,
                self.campo_revision,
                boton_guardar
            ):
                widget.hide()

        self.layout_contenido.addWidget(
            tarjeta
        )

        self.cargar_comentarios()

        self.layout_contenido.addStretch()

    def _mostrar_foto(self):

        total = len(self._fotos)

        if total == 0:
            self.visor_foto.setPixmap(QPixmap())
            self.visor_foto.setText(
                "Esta propiedad aún no tiene fotos"
            )
            self.contador_fotos.setText("")
            self.boton_anterior.hide()
            self.boton_siguiente.hide()
            return

        self._indice_foto %= total

        pixmap = pixmap_desde_bytes(
            self._fotos[self._indice_foto]["imagen"],
            660,
            300
        )

        if pixmap:
            self.visor_foto.setPixmap(pixmap)
        else:
            self.visor_foto.setText("Foto no disponible")

        self.contador_fotos.setText(
            f"Foto {self._indice_foto + 1} de {total}"
        )

        hay_varias = total > 1

        self.boton_anterior.setVisible(hay_varias)
        self.boton_siguiente.setVisible(hay_varias)

    def _cambiar_foto(self, paso):

        self._indice_foto += paso

        self._mostrar_foto()

    def cargar_comentarios(self):

        comentarios = dao.obtener_comentarios_propiedad(
            self.datos["id_propiedad"]
        )

        if not comentarios:
            return

        titulo = QLabel(
            "Comentarios de estudiantes"
        )

        titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 16px;
            font-weight: bold;
            padding-top: 10px;
        """)

        self.layout_contenido.addWidget(
            titulo
        )

        for comentario in comentarios:

            texto = comentario["comentario"]

            calificacion = (
                comentario["calificacion"]
            )

            nombre = comentario["nombre"]

            etiqueta = QLabel(
                f"@{nombre}\n"
                f"{'★' * calificacion}\n"
                f"{texto}"
            )

            etiqueta.setWordWrap(True)

            etiqueta.setStyleSheet("""
                color: #000000;
                background: white;
                border-radius: 8px;
                padding: 10px;
            """)

            self.layout_contenido.addWidget(
                etiqueta
            )

    def guardar_revision(self):

        texto = (
            self.campo_revision
            .toPlainText()
            .strip()
        )

        if not texto:

            QMessageBox.warning(
                self,
                "Comentario vacío",
                "Escribe un comentario antes de guardarlo."
            )

            return

        resultado = dao.agregar_comentario(
            self.principal.id_usuario,
            texto,
            self.datos["id_propiedad"],
            self.calificacion.value()
        )

        if resultado:

            QMessageBox.information(
                self,
                "Reseña guardada",
                "Tu reseña se guardó correctamente."
            )

            self.campo_revision.clear()

        else:

            QMessageBox.critical(
                self,
                "Error",
                "No fue posible guardar la reseña."
            )


class PaginaPrincipal(QMainWindow):

    def __init__(
        self,
        id_usuario,
        usuario,
        nombre_completo,
        rol="estudiante"
    ):

        super().__init__()

        self.id_usuario = id_usuario
        self.usuario = usuario
        self.nombre_completo = nombre_completo
        self.rol = rol
        self.es_admin = (rol == "administrador")

        self._insignias = []

        self.estado_verificacion = None

        if rol == "arrendador":

            solicitud = dao.obtener_solicitud_usuario(
                id_usuario
            )

            if solicitud:
                self.estado_verificacion = solicitud["estado"]

            if dao.arrendador_verificado(id_usuario):
                self.estado_verificacion = "aprobada"

        color_guardado = dao.obtener_color_interfaz(
            id_usuario
        )

        if color_guardado and QColor(color_guardado).isValid():
            self.color_interfaz = QColor(color_guardado).name()
        else:
            self.color_interfaz = COLOR_DEFECTO.get(
                rol,
                "#1E3A8A"
            )

        self.setWindowTitle(
            "Unihogar - Panel de Administrador"
            if self.es_admin
            else "Unihogar - Panel Principal"
        )

        self.setMinimumSize(
            1180,
            700
        )

        self.resize(
            1180,
            700
        )

        self._estilo_base = ("""
            QWidget {
                background: #EEF2F9;
                font-family: "Segoe UI", Arial, sans-serif;
            }

            QFrame#sidebar {
                background: #1E3A8A;
            }

            QFrame#encabezado {
                background: white;
                border-radius: 14px;
            }

            QPushButton#navBtn {
                text-align: left;
                color: #C7D2FE;
                background: transparent;
                border: none;
                padding: 12px 18px;
                font-size: 13px;
                border-radius: 8px;
            }

            QPushButton#navBtn:hover {
                background: rgba(255,255,255,0.08);
                color: white;
            }

            QPushButton#navBtn:checked {
                background: #2563EB;
                color: white;
                font-weight: bold;
            }

            QPushButton#salir {
                text-align: left;
                color: #FCA5A5;
                background: transparent;
                border: none;
                padding: 12px 18px;
                font-size: 13px;
                border-radius: 8px;
            }

            QLineEdit#buscador {
                padding: 8px 14px;
                min-height: 22px;
                border: 2px solid #E2E5EB;
                border-radius: 9px;
                font-size: 13px;
                background: #FAFBFC;
                color: #111827;
            }

            QComboBox {
                padding: 8px 12px;
                border: 2px solid #E2E5EB;
                border-radius: 9px;
                font-size: 12px;
                background: #FAFBFC;
                color: #111827;
            }

            QPushButton#filtroTipo {
                background: white;
                color: #374151;
                border: 2px solid #E2E5EB;
                border-radius: 16px;
                padding: 6px 16px;
                font-size: 12px;
            }

            QPushButton#filtroTipo:checked {
                background: #1E3A8A;
                color: white;
                border: 2px solid #1E3A8A;
                font-weight: bold;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QMessageBox {
                background-color: #FFFFFF;
                color: #111827;
                font-size: 13px;
            }

            QMessageBox QLabel {
                color: #111827;
                background-color: transparent;
            }

            QMessageBox QPushButton {
                background-color: #2563EB;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 7px 18px;
                font-weight: bold;
                min-width: 70px;
            }
        """) + ESTILO_DIALOGO

        self.aplicar_color_interfaz()

        self._cargar_datos()

        contenedor = QWidget()

        raiz = QHBoxLayout(
            contenedor
        )

        raiz.setContentsMargins(
            0,
            0,
            0,
            0
        )

        raiz.setSpacing(0)

        raiz.addWidget(
            self._crear_sidebar()
        )

        raiz.addWidget(
            self._crear_contenido(),
            1
        )

        self.setCentralWidget(
            contenedor
        )

        self._opciones_nav()[0][1]()

        self.centrar_ventana()

    def _crear_sidebar(self):

        sidebar = QFrame()

        sidebar.setObjectName(
            "sidebar"
        )

        sidebar.setFixedWidth(
            250
        )

        layout = QVBoxLayout(
            sidebar
        )

        layout.setContentsMargins(
            18,
            28,
            18,
            22
        )

        layout.setSpacing(4)

        titulo = QLabel()

        imagen = QPixmap("unihogar/UniHogar.png")

        titulo.setPixmap(imagen.scaled(
            190, 120,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))
        titulo.setScaledContents(True)
        titulo.setFixedSize(190, 120)

        layout.addWidget(titulo)

        layout.addSpacing(12)

        layout.addWidget(
            self._insignia(),
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        layout.addSpacing(18)

        self.grupo_nav = QButtonGroup(
            self
        )

        self.grupo_nav.setExclusive(
            True
        )

        nav = self._opciones_nav()

        opciones = [t for t, f in nav]

        funciones = [f for t, f in nav]

        for i, texto in enumerate(
            opciones
        ):

            boton = QPushButton(
                texto
            )

            boton.setObjectName(
                "navBtn"
            )

            boton.setCheckable(
                True
            )

            boton.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            if i == 0:
                boton.setChecked(True)

            boton.clicked.connect(
                funciones[i]
            )

            self.grupo_nav.addButton(
                boton
            )

            layout.addWidget(
                boton
            )

        layout.addStretch()

        separador = QFrame()

        separador.setFixedHeight(
            1
        )

        separador.setStyleSheet("""
            background: rgba(255,255,255,0.15);
        """)

        layout.addWidget(
            separador
        )

        salir = QPushButton(
            "  Cerrar sesión"
        )

        salir.setObjectName(
            "salir"
        )

        salir.clicked.connect(
            self.cerrar_sesion
        )

        layout.addWidget(
            salir
        )

        return sidebar

    def _crear_contenido(self):

        contenido = QWidget()

        layout = QVBoxLayout(
            contenido
        )

        layout.setContentsMargins(
            30,
            26,
            30,
            26
        )

        layout.setSpacing(18)

        layout.addWidget(
            self._crear_encabezado()
        )

        layout.addWidget(
            self._crear_filtros()
        )

        self.area_resultados = QScrollArea()

        self.area_resultados.setWidgetResizable(
            True
        )

        self.contenedor_grid = QWidget()

        self.grid = QGridLayout(
            self.contenedor_grid
        )

        self.grid.setSpacing(
            18
        )

        self.area_resultados.setWidget(
            self.contenedor_grid
        )

        layout.addWidget(
            self.area_resultados,
            1
        )

        return contenido

    def _crear_encabezado(self):

        encabezado = QFrame()

        encabezado.setObjectName(
            "encabezado"
        )

        layout = QHBoxLayout(
            encabezado
        )

        layout.setContentsMargins(
            24,
            18,
            24,
            18
        )

        col_texto = QVBoxLayout()

        saludo = QLabel(
            f"Hola, {self.nombre_completo} 👋"
        )

        saludo.setObjectName(
            "saludo"
        )

        saludo.setStyleSheet(
            "font-size: 19px; font-weight: bold;"
        )

        fila_saludo = QHBoxLayout()

        fila_saludo.addWidget(
            saludo
        )

        fila_saludo.addWidget(
            self._insignia()
        )

        fila_saludo.addStretch()

        col_texto.addLayout(
            fila_saludo
        )

        subtitulo = QLabel(
            SUBTITULOS_ROL.get(self.rol, "")
        )

        subtitulo.setStyleSheet("""
            color: #6B7280;
            font-size: 12px;
        """)

        col_texto.addWidget(
            subtitulo
        )

        layout.addLayout(
            col_texto
        )

        layout.addStretch()

        self.buscador = QLineEdit()

        self.buscador.setObjectName(
            "buscador"
        )

        self.buscador.setPlaceholderText(
            "Buscar por zona o tipo de alquiler..."
        )

        self.buscador.setFixedWidth(
            300
        )

        self.buscador.textChanged.connect(
            self._aplicar_filtros
        )

        layout.addWidget(
            self.buscador
        )

        return encabezado

    def _crear_filtros(self):

        fila = QHBoxLayout()

        fila.setSpacing(10)

        self.grupo_tipo = QButtonGroup(
            self
        )

        self.grupo_tipo.setExclusive(
            True
        )

        self.botones_tipo = []

        tipos = [
            "Todos"
        ] + [
            tipo["nombre"]
            for tipo in self.tipos
        ]

        for i, tipo in enumerate(
            tipos
        ):

            boton = QPushButton(
                tipo
            )

            boton.setObjectName(
                "filtroTipo"
            )

            boton.setCheckable(
                True
            )

            if i == 0:
                boton.setChecked(
                    True
                )

            boton.clicked.connect(
                self._aplicar_filtros
            )

            self.grupo_tipo.addButton(
                boton
            )

            self.botones_tipo.append(
                boton
            )

            fila.addWidget(
                boton
            )

        fila.addStretch()

        self.combo_universidad = QComboBox()

        self.combo_universidad.addItem(
            "Todas las universidades"
        )

        for universidad in self.universidades:

            self.combo_universidad.addItem(
                universidad["nombre"]
            )

        self.combo_universidad.currentIndexChanged.connect(
            self._aplicar_filtros
        )

        fila.addWidget(
            self.combo_universidad
        )

        base = QWidget()

        base.setLayout(
            fila
        )

        contenedor = QWidget()

        pila = QVBoxLayout(contenedor)

        pila.setContentsMargins(0, 0, 0, 0)

        pila.setSpacing(8)

        pila.addWidget(base)

        pila.addWidget(self._crear_filtros_extra())

        return contenedor

    def _crear_filtros_extra(self):
        """Segunda fila: precio, zona, servicios y limpiar."""

        self.fila_filtros_extra = QWidget()

        extra = QHBoxLayout(self.fila_filtros_extra)

        extra.setContentsMargins(0, 0, 0, 0)

        extra.setSpacing(10)

        self.filtro_precio_min = QLineEdit()

        self.filtro_precio_min.setPlaceholderText("Precio mín. (C$)")

        self.filtro_precio_min.setFixedWidth(140)

        self.filtro_precio_max = QLineEdit()

        self.filtro_precio_max.setPlaceholderText("Precio máx. (C$)")

        self.filtro_precio_max.setFixedWidth(140)

        self.filtro_zona = QLineEdit()

        self.filtro_zona.setPlaceholderText("Zona o barrio...")

        self.filtro_zona.setFixedWidth(200)

        # Espera un momento después de escribir antes de buscar.
        self._temporizador_filtros = QTimer(self)

        self._temporizador_filtros.setSingleShot(True)

        self._temporizador_filtros.setInterval(350)

        self._temporizador_filtros.timeout.connect(
            self._aplicar_filtros
        )

        for campo in (
            self.filtro_precio_min,
            self.filtro_precio_max,
            self.filtro_zona
        ):
            campo.textChanged.connect(
                lambda *_: self._temporizador_filtros.start()
            )

        # Servicios: ventanita con casillas (se mantiene abierta).
        self.boton_servicios = QPushButton("Servicios ▾")

        self.boton_servicios.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self._popup_servicios = QFrame(
            self, Qt.WindowType.Popup
        )

        self._popup_servicios.setStyleSheet(
            "QFrame { background: white; border: 1px solid #D1D5DB; "
            "border-radius: 8px; } "
            "QCheckBox { padding: 4px 10px; color: #111827; "
            "border: none; }"
        )

        capa = QVBoxLayout(self._popup_servicios)

        capa.setContentsMargins(6, 6, 6, 6)

        capa.setSpacing(0)

        self._checks_filtro = []

        for amenidad in (dao.obtener_amenidades() or []):

            casilla = QCheckBox(amenidad["nombre"])

            casilla.setProperty(
                "id_amenidad", amenidad["id_amenidad"]
            )

            casilla.toggled.connect(self._servicios_cambiaron)

            capa.addWidget(casilla)

            self._checks_filtro.append(casilla)

        self.boton_servicios.clicked.connect(
            self._mostrar_popup_servicios
        )

        self.boton_limpiar = QPushButton("Limpiar filtros")

        self.boton_limpiar.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.boton_limpiar.clicked.connect(self._limpiar_filtros)

        self.etiqueta_error_filtros = QLabel("")

        self.etiqueta_error_filtros.setStyleSheet(
            "color: #DC2626; font-size: 12px;"
        )

        self.etiqueta_error_filtros.hide()

        # Estilo propio de la fila: texto oscuro y campos blancos.
        self.fila_filtros_extra.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                min-height: 22px;
                border: 2px solid #D1D5DB;
                border-radius: 9px;
                font-size: 13px;
                background: #FFFFFF;
                color: #111827;
            }
            QPushButton {
                padding: 8px 16px;
                min-height: 22px;
                border: 2px solid #D1D5DB;
                border-radius: 9px;
                font-size: 13px;
                font-weight: bold;
                background: #FFFFFF;
                color: #374151;
            }
            QPushButton:hover {
                background: #F3F4F6;
            }
        """)

        for campo in (
            self.filtro_precio_min,
            self.filtro_precio_max,
            self.filtro_zona
        ):
            paleta = campo.palette()
            paleta.setColor(
                QPalette.ColorRole.PlaceholderText,
                QColor("#6B7280")
            )
            campo.setPalette(paleta)

        extra.addWidget(self.filtro_precio_min)
        extra.addWidget(self.filtro_precio_max)
        extra.addWidget(self.filtro_zona)
        extra.addWidget(self.boton_servicios)
        extra.addWidget(self.boton_limpiar)
        extra.addWidget(self.etiqueta_error_filtros)
        extra.addStretch()

        return self.fila_filtros_extra

    def _mostrar_popup_servicios(self):

        if not self._checks_filtro:
            return

        self._popup_servicios.adjustSize()

        self._popup_servicios.move(
            self.boton_servicios.mapToGlobal(
                QPoint(0, self.boton_servicios.height())
            )
        )

        self._popup_servicios.show()

    def _ids_servicios_filtro(self):

        return [
            c.property("id_amenidad")
            for c in self._checks_filtro
            if c.isChecked()
        ]

    def _servicios_cambiaron(self, *_):

        cantidad = len(self._ids_servicios_filtro())

        self.boton_servicios.setText(
            f"Servicios ({cantidad}) ▾" if cantidad
            else "Servicios ▾"
        )

        self._temporizador_filtros.start()

    def _reset_filtros(self):
        """Deja todos los filtros en blanco SIN buscar todavía."""

        controles = [
            self.buscador,
            self.filtro_precio_min,
            self.filtro_precio_max,
            self.filtro_zona,
            self.combo_universidad,
        ] + self._checks_filtro

        for c in controles:
            c.blockSignals(True)

        self.buscador.clear()
        self.filtro_precio_min.clear()
        self.filtro_precio_max.clear()
        self.filtro_zona.clear()
        self.combo_universidad.setCurrentIndex(0)

        for casilla in self._checks_filtro:
            casilla.setChecked(False)

        if self.botones_tipo:
            self.botones_tipo[0].setChecked(True)

        for c in controles:
            c.blockSignals(False)

        self.boton_servicios.setText("Servicios ▾")

        self.etiqueta_error_filtros.hide()

        self._temporizador_filtros.stop()

    def _limpiar_filtros(self):

        self._reset_filtros()

        self._aplicar_filtros()

    def _cargar_datos(self):

        self.universidades = (
            dao.obtener_universidades()
        )

        self.tipos = (
            dao.obtener_tipos()
        )

        if self.universidades is None:
            self.universidades = []

        if self.tipos is None:
            self.tipos = []

    def limpiar_resultados(self):

        while self.grid.count():

            item = self.grid.takeAt(0)

            widget = item.widget()

            if widget:

                widget.deleteLater()

    def _aplicar_filtros(self):

        texto = (
            self.buscador.text()
            .strip()
        )

        boton_tipo = (
            self.grupo_tipo.checkedButton()
        )

        tipo = (
            boton_tipo.text()
            if boton_tipo
            else "Todos"
        )

        universidad = (
            self.combo_universidad.currentText()
        )

        (precio_min, precio_max), error = val.validar_rango_precios(
            self.filtro_precio_min.text(),
            self.filtro_precio_max.text()
        )

        if error:

            # No se busca con precios inválidos: se avisa en la fila
            # de filtros y se deja lo que ya estaba en pantalla.
            self.etiqueta_error_filtros.setText(error)

            self.etiqueta_error_filtros.show()

            return

        self.etiqueta_error_filtros.hide()

        zona = self.filtro_zona.text().strip()

        servicios = self._ids_servicios_filtro()

        self.limpiar_resultados()

        resultados = dao.obtener_propiedades(
            texto,
            tipo,
            universidad,
            precio_min,
            precio_max,
            zona,
            servicios
        )

        if not resultados:

            hay_filtros = bool(
                texto
                or zona
                or servicios
                or precio_min is not None
                or precio_max is not None
                or tipo != "Todos"
                or universidad != "Todas las universidades"
            )

            vacio = QLabel(
                "No se encontraron alquileres "
                "con esos filtros.\n\n"
                "Intenta ajustar la búsqueda."
                if hay_filtros
                else
                "Aún no hay propiedades publicadas.\n\n"
                "Cuando un arrendador sea aprobado, "
                "su propiedad aparecerá aquí."
            )

            vacio.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            vacio.setStyleSheet("""
                color: #6B7280;
                font-size: 14px;
                background: white;
                border-radius: 12px;
                padding: 50px;
            """)

            self.grid.addWidget(
                vacio,
                0,
                0,
                1,
                3
            )

            return

        columnas = 3

        for i, propiedad in enumerate(
            resultados
        ):

            fila, columna = divmod(
                i,
                columnas
            )

            self.grid.addWidget(
                TarjetaPropiedad(
                    propiedad,
                    self
                ),
                fila,
                columna
            )

        for columna in range(
            columnas
        ):

            self.grid.setColumnStretch(
                columna,
                1
            )

    def mostrar_inicio(self):

        self.buscador.show()
        self.combo_universidad.show()
        self.fila_filtros_extra.show()

        for boton in self.grupo_tipo.buttons():
            boton.show()

        self.buscador.clear()

        botones = (
            self.grupo_tipo.buttons()
        )

        if botones:
            botones[0].setChecked(
                True
            )

        self.combo_universidad.setCurrentIndex(
            0
        )

        self._reset_filtros()

        self._aplicar_filtros()

    def mostrar_favoritos(self):

        self.buscador.hide()
        self.combo_universidad.hide()
        self.fila_filtros_extra.hide()

        for boton in self.grupo_tipo.buttons():
            boton.hide()

        self.limpiar_resultados()

        titulo = QLabel(
            "Mis favoritos"
        )

        titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 24px;
            font-weight: bold;
        """)

        self.grid.addWidget(
            titulo,
            0,
            0,
            1,
            3
        )

        favoritos = dao.obtener_favoritos(
            self.id_usuario
        )

        if not favoritos:

            vacio = QLabel(
                "Todavía no tienes propiedades favoritas."
            )

            vacio.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            vacio.setStyleSheet("""
                color: #6B7280;
                font-size: 14px;
                background: white;
                border-radius: 12px;
                padding: 50px;
            """)

            self.grid.addWidget(
                vacio,
                1,
                0,
                1,
                3
            )

            return

        for i, propiedad in enumerate(
            favoritos
        ):

            fila, columna = divmod(
                i,
                3
            )

            self.grid.addWidget(
                TarjetaPropiedad(
                    propiedad,
                    self
                ),
                fila + 1,
                columna
            )

    def mostrar_comentarios(self):

        self.limpiar_resultados()

        self.buscador.hide()
        self.combo_universidad.hide()
        self.fila_filtros_extra.hide()

        for boton in self.grupo_tipo.buttons():
            boton.hide()

        titulo = QLabel(
            "Comentarios"
        )

        titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 24px;
            font-weight: bold;
            padding: 5px;
        """)

        descripcion = QLabel(
            "Comparte tu experiencia y conoce "
            "los comentarios de otros estudiantes."
        )

        descripcion.setStyleSheet("""
            color: #6B7280;
            font-size: 13px;
            padding-bottom: 10px;
        """)

        boton_agregar = QPushButton(
            "+ Agregar comentario"
        )

        boton_agregar.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        boton_agregar.setStyleSheet("""
            QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 18px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #1D4ED8;
            }
        """)

        boton_agregar.clicked.connect(
            self.mostrar_formulario_comentario
        )

        self.grid.addWidget(
            titulo,
            0,
            0,
            1,
            3
        )

        self.grid.addWidget(
            descripcion,
            1,
            0,
            1,
            3
        )

        self.grid.addWidget(
            boton_agregar,
            2,
            0,
            1,
            3
        )

        comentarios = (
            dao.obtener_comentarios()
        )

        fila = 3

        if not comentarios:

            vacio = QLabel(
                "Todavía no hay comentarios.\n\n"
                "Sé el primero en compartir tu experiencia."
            )

            vacio.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            vacio.setStyleSheet("""
                color: #6B7280;
                font-size: 14px;
                background: white;
                border-radius: 12px;
                padding: 50px;
            """)

            self.grid.addWidget(
                vacio,
                fila,
                0,
                1,
                3
            )

            return

        for comentario in comentarios:

            tarjeta = QFrame()

            tarjeta.setStyleSheet("""
                QFrame {
                    background: white;
                    border-radius: 12px;
                    border: 1px solid #E5E7EB;
                }
            """)

            layout = QVBoxLayout(
                tarjeta
            )

            usuario = QLabel(
                f"@{comentario['usuario']}"
            )

            usuario.setStyleSheet("""
                color: #1E3A8A;
                font-size: 13px;
                font-weight: bold;
            """)

            texto = QLabel(
                comentario["comentario"]
            )

            texto.setWordWrap(True)

            texto.setStyleSheet("""
                color: #000000;
                font-size: 13px;
                background: transparent;
                border: none;
            """)

            layout.addWidget(
                usuario
            )

            if comentario["calificacion"]:

                estrellas = QLabel(
                    "★" * comentario["calificacion"]
                )

                estrellas.setStyleSheet("""
                    color: #D97706;
                    font-size: 15px;
                """)

                layout.addWidget(
                    estrellas
                )

            layout.addWidget(
                texto
            )

            self.grid.addWidget(
                tarjeta,
                fila,
                0,
                1,
                3
            )

            fila += 1

    def mostrar_formulario_comentario(self):

        self.limpiar_resultados()

        titulo = QLabel(
            "Agregar comentario"
        )

        titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 22px;
            font-weight: bold;
        """)

        self.grid.addWidget(
            titulo,
            0,
            0,
            1,
            3
        )

        texto = QLabel(
            "Escribe tu comentario:"
        )

        texto.setStyleSheet("""
            color: #374151;
            font-size: 13px;
            font-weight: bold;
        """)

        self.grid.addWidget(
            texto,
            1,
            0,
            1,
            3
        )

        self.campo_comentario = QTextEdit()

        self.campo_comentario.setPlaceholderText(
            "Escribe aquí tu comentario..."
        )

        self.campo_comentario.setStyleSheet("""
            QTextEdit {
                background: white;
                color: #000000;
                border: 2px solid #D1D5DB;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
            }

            QTextEdit:focus {
                border: 2px solid #2563EB;
                color: #000000;
            }
        """)

        self.campo_comentario.setMinimumHeight(
            140
        )

        self.grid.addWidget(
            self.campo_comentario,
            2,
            0,
            1,
            3
        )

        botones = QHBoxLayout()

        guardar = QPushButton(
            "Guardar"
        )

        guardar.setStyleSheet("""
            QPushButton {
                background: #16A34A;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #15803D;
            }
        """)

        guardar.clicked.connect(
            self.guardar_comentario
        )

        cancelar = QPushButton(
            "Cancelar"
        )

        cancelar.setStyleSheet("""
            QPushButton {
                background: #E5E7EB;
                color: #000000;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: bold;
            }

            QPushButton:hover {
                background: #D1D5DB;
            }
        """)

        cancelar.clicked.connect(
            self.mostrar_comentarios
        )

        botones.addWidget(
            guardar
        )

        botones.addWidget(
            cancelar
        )

        botones.addStretch()

        self.grid.addLayout(
            botones,
            3,
            0,
            1,
            3
        )

        self.campo_comentario.setFocus()

    def guardar_comentario(self):

        texto = (
            self.campo_comentario
            .toPlainText()
            .strip()
        )

        if not texto:

            QMessageBox.warning(
                self,
                "Comentario vacío",
                "Escribe un comentario antes de guardarlo."
            )

            return

        resultado = dao.agregar_comentario(
            self.id_usuario,
            texto
        )

        if resultado:

            QMessageBox.information(
                self,
                "Comentario guardado",
                "Tu comentario se guardó correctamente."
            )

            self.mostrar_comentarios()

        else:

            QMessageBox.critical(
                self,
                "Error",
                "No fue posible guardar el comentario."
            )

    def mostrar_perfil(self):

        self.buscador.hide()
        self.combo_universidad.hide()
        self.fila_filtros_extra.hide()

        for boton in self.grupo_tipo.buttons():
            boton.hide()

        self.limpiar_resultados()

        perfil = QFrame()

        perfil.setStyleSheet("""
            QFrame {
                background: white;
                border-radius: 14px;
            }

            QLabel {
                color: #111827;
            }
        """)

        layout = QVBoxLayout(
            perfil
        )

        layout.setContentsMargins(
            30,
            30,
            30,
            30
        )

        avatar = QLabel(
            self.usuario[:1].upper()
        )

        avatar.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        avatar.setFixedSize(
            80,
            80
        )

        avatar.setStyleSheet(f"""
            background: {self.color_interfaz};
            color: white;
            border-radius: 40px;
            font-size: 32px;
            font-weight: bold;
        """)

        layout.addWidget(
            avatar,
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        nombre = QLabel(
            self.nombre_completo
        )

        nombre.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        nombre.setStyleSheet("""
            color: #1E3A8A;
            font-size: 23px;
            font-weight: bold;
        """)

        layout.addWidget(
            nombre
        )

        usuario = QLabel(
            f"@{self.usuario}"
        )

        usuario.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        usuario.setStyleSheet("""
            color: #6B7280;
            font-size: 14px;
        """)

        layout.addWidget(
            usuario
        )

        layout.addWidget(
            self._insignia(),
            alignment=Qt.AlignmentFlag.AlignCenter
        )

        if self.rol != "estudiante":

            layout.addWidget(
                self._info_perfil_rol()
            )

            layout.addStretch()

            self.grid.addWidget(
                perfil,
                0,
                0,
                1,
                3
            )

            return

        solicitud_rol = dao.obtener_solicitud_rol_usuario(
            self.id_usuario
        )

        if solicitud_rol and solicitud_rol["estado"] != "aprobada":

            if solicitud_rol["estado"] == "pendiente":
                aviso = (
                    "Tu solicitud para ser arrendador está en "
                    "revisión. Mientras tanto usas la cuenta "
                    "como estudiante."
                )
            else:
                aviso = (
                    "Tu solicitud para ser arrendador fue rechazada."
                )
                if solicitud_rol.get("motivo_rechazo"):
                    aviso += f"\nMotivo: {solicitud_rol['motivo_rechazo']}"

            etiqueta_rol = QLabel(aviso)

            etiqueta_rol.setWordWrap(True)

            etiqueta_rol.setStyleSheet(
                "color: #92400E; background: #FEF3C7; "
                "border-radius: 8px; padding: 12px; font-size: 13px;"
            )

            layout.addWidget(etiqueta_rol)

            if solicitud_rol["estado"] == "rechazada":

                otra = boton_accion(
                    "Solicitar de nuevo", self.color_interfaz
                )

                otra.clicked.connect(self._solicitar_arrendador_otra_vez)

                layout.addWidget(
                    otra, alignment=Qt.AlignmentFlag.AlignLeft
                )

        comentarios = (
            dao.obtener_comentarios_usuario(
                self.id_usuario
            )
        )

        cantidad = QLabel(
            f"Comentarios realizados: {len(comentarios)}"
        )

        cantidad.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        cantidad.setStyleSheet("""
            color: #374151;
            font-size: 14px;
            padding: 10px;
        """)

        layout.addWidget(
            cantidad
        )

        titulo = QLabel(
            "Mis comentarios"
        )

        titulo.setStyleSheet("""
            color: #1E3A8A;
            font-size: 18px;
            font-weight: bold;
            padding-top: 15px;
        """)

        layout.addWidget(
            titulo
        )

        if not comentarios:

            vacio = QLabel(
                "Todavía no has realizado comentarios."
            )

            vacio.setStyleSheet("""
                color: #6B7280;
                padding: 15px;
            """)

            layout.addWidget(
                vacio
            )

        else:

            for comentario in comentarios:

                texto = QLabel(
                    comentario["comentario"]
                )

                texto.setWordWrap(
                    True
                )

                texto.setStyleSheet("""
                    color: #000000;
                    background: #F9FAFB;
                    border-radius: 8px;
                    padding: 12px;
                """)

                layout.addWidget(
                    texto
                )

        self.grid.addWidget(
            perfil,
            0,
            0,
            1,
            3
        )

    # ------------------------------------------------------------
    # Navegación y utilidades según el rol
    # ------------------------------------------------------------

    def _opciones_nav(self):

        if self.rol == "administrador":
            return [
                ("  Panel", self.mostrar_panel_admin),
                ("  Inicio", self.mostrar_inicio),
                ("  Solicitudes", self.mostrar_solicitudes),
                (
                    "  Permisos de arrendador",
                    self.mostrar_solicitudes_rol
                ),
                (
                    "  Cambios de propiedades",
                    self.mostrar_cambios_propiedades
                ),
                (
                    "  Estudiantes",
                    lambda: self.mostrar_usuarios("estudiante")
                ),
                (
                    "  Arrendadores",
                    lambda: self.mostrar_usuarios("arrendador")
                ),
                (
                    "  Revisar comentarios",
                    self.mostrar_moderacion
                ),
                ("  Tipo de cambio", self.mostrar_tipo_cambio),
                ("  Mi perfil", self.mostrar_perfil),
                ("  Configuración", self.mostrar_configuracion)
            ]

        if self.rol == "arrendador":
            return [
                ("  Mi panel", self.mostrar_panel_arrendador),
                ("  Mis propiedades", self.mostrar_mis_propiedades),
                ("  Mis solicitudes", self.mostrar_verificacion),
                ("  Tipo de cambio", self.mostrar_tipo_cambio),
                ("  Mi perfil", self.mostrar_perfil),
                ("  Configuración", self.mostrar_configuracion)
            ]

        return [
            ("  Inicio", self.mostrar_inicio),
            ("  Mis favoritos", self.mostrar_favoritos),
            ("  Comentarios", self.mostrar_comentarios),
            ("  Tipo de cambio", self.mostrar_tipo_cambio),
            ("  Mi perfil", self.mostrar_perfil),
            ("  Configuración", self.mostrar_configuracion)
        ]

    def _texto_insignia(self):

        if self.rol != "arrendador":
            return None

        return {
            "aprobada": "ARRENDADOR ✓",
            "pendiente": "ARRENDADOR · PENDIENTE"
        }.get(
            self.estado_verificacion,
            "ARRENDADOR · SIN APROBAR"
        )

    def _insignia(self):

        insignia = crear_insignia_rol(
            self.rol,
            self._texto_insignia()
        )

        self._insignias.append(insignia)

        return insignia

    def _refrescar_insignias(self):

        texto = (
            self._texto_insignia()
            or ROLES.get(self.rol, "Estudiante").upper()
        )

        vivas = []

        for insignia in self._insignias:

            try:
                insignia.setText(texto)
                vivas.append(insignia)

            except RuntimeError:
                pass

        self._insignias = vivas

    def _solicitud_actual(self):

        solicitud = dao.obtener_solicitud_usuario(
            self.id_usuario
        )

        self.estado_verificacion = (
            solicitud["estado"] if solicitud else None
        )

        if dao.arrendador_verificado(self.id_usuario):
            self.estado_verificacion = "aprobada"

        self._refrescar_insignias()

        return solicitud

    def aplicar_color_interfaz(self):

        color = QColor(self.color_interfaz)

        principal = color.name()

        acento = color.lighter(150).name()

        self.setStyleSheet(
            self._estilo_base + f"""
            QFrame#sidebar {{
                background: {principal};
            }}
            QPushButton#navBtn:checked {{
                background: {acento};
                color: white;
                font-weight: bold;
            }}
            QPushButton#filtroTipo:checked {{
                background: {principal};
                border: 2px solid {principal};
                color: white;
                font-weight: bold;
            }}
            QFrame#encabezado {{
                background: white;
                border-radius: 14px;
                border-left: 8px solid {principal};
            }}
            QLabel#saludo {{
                color: {principal};
            }}
            """
        )

    def _preparar_pagina(self):

        self.buscador.hide()

        self.combo_universidad.hide()

        self.fila_filtros_extra.hide()

        for boton in self.grupo_tipo.buttons():
            boton.hide()

        self.limpiar_resultados()

        for i in range(self.grid.rowCount() + 1):
            self.grid.setRowStretch(i, 0)

    def _fin_pagina(self, fila):

        self.grid.setRowStretch(fila, 1)

    def _titulo_pagina(self, texto, subtitulo=""):

        caja = QWidget()

        layout = QVBoxLayout(caja)

        layout.setContentsMargins(0, 0, 0, 0)

        layout.setSpacing(2)

        titulo = QLabel(texto)

        titulo.setStyleSheet(
            f"color: {self.color_interfaz}; "
            "font-size: 22px; font-weight: bold; "
            "background: transparent;"
        )

        layout.addWidget(titulo)

        if subtitulo:

            detalle = QLabel(subtitulo)

            detalle.setWordWrap(True)

            detalle.setStyleSheet(
                "color: #6B7280; font-size: 13px; "
                "background: transparent;"
            )

            layout.addWidget(detalle)

        return caja

    def _ampliar_imagen(self, datos):

        dialogo = QDialog(self)

        dialogo.setWindowTitle("Imagen de la casa")

        layout = QVBoxLayout(dialogo)

        etiqueta = QLabel()

        etiqueta.setPixmap(
            pixmap_desde_bytes(datos, 900, 650)
        )

        layout.addWidget(etiqueta)

        dialogo.exec()

    def _tarjeta_solicitud(self, s, admin=False):

        tarjeta = crear_tarjeta()

        fila = QHBoxLayout(tarjeta)

        fila.setContentsMargins(20, 18, 20, 18)

        fila.setSpacing(20)

        datos = None

        if s.get("tiene_imagen"):
            datos = dao.obtener_imagen_solicitud(
                s["id_solicitud"]
            )

        izquierda = QVBoxLayout()

        izquierda.addWidget(
            crear_miniatura(datos, 240, 160)
        )

        if datos:

            ampliar = boton_accion(
                "Ampliar imagen",
                "#475569"
            )

            ampliar.clicked.connect(
                lambda checked=False, d=datos:
                self._ampliar_imagen(d)
            )

            izquierda.addWidget(ampliar)

        izquierda.addStretch()

        fila.addLayout(izquierda)

        derecha = QVBoxLayout()

        derecha.setSpacing(6)

        texto_estado, color_estado = (
            ESTADOS_VERIFICACION[s["estado"]]
        )

        cabecera = QHBoxLayout()

        if admin:

            nombre = QLabel(
                f"{s['nombre']}  ·  @{s['usuario']}"
            )

            nombre.setStyleSheet(
                "font-size: 15px; font-weight: bold; "
                "color: #1E3A8A;"
            )

            cabecera.addWidget(nombre)

        cabecera.addWidget(
            crear_chip(texto_estado, color_estado)
        )

        cabecera.addStretch()

        derecha.addLayout(cabecera)

        direccion = QLabel(
            f"📍 {s['direccion']}"
            if s.get("direccion")
            else "Sin dirección indicada"
        )

        direccion.setWordWrap(True)

        direccion.setStyleSheet(
            "font-size: 14px; font-weight: bold;"
        )

        derecha.addWidget(direccion)

        if s.get("tipo") or s.get("precio"):

            partes = []

            if s.get("tipo"):
                partes.append(s["tipo"])

            if s.get("precio"):
                partes.append(
                    f"C$ {float(s['precio']):,.0f} /mes"
                )

            if s.get("universidad"):
                partes.append(f"🎓 {s['universidad']}")

            if s.get("distancia"):
                partes.append(f"🚶 {s['distancia']}")

            if s.get("telefono"):
                partes.append(f"📞 {s['telefono']}")

            datos_propiedad = QLabel("  ·  ".join(partes))

            datos_propiedad.setWordWrap(True)

            datos_propiedad.setStyleSheet(
                "font-size: 13px; color: #1E3A8A; "
                "font-weight: bold;"
            )

            derecha.addWidget(datos_propiedad)

        if s.get("descripcion"):

            descripcion = QLabel(s["descripcion"])

            descripcion.setWordWrap(True)

            descripcion.setStyleSheet(
                "font-size: 13px; color: #374151;"
            )

            derecha.addWidget(descripcion)

        if s.get("motivo_rechazo"):

            motivo = QLabel(
                f"Motivo del rechazo: {s['motivo_rechazo']}"
            )

            motivo.setWordWrap(True)

            motivo.setStyleSheet(
                "font-size: 13px; color: #DC2626;"
            )

            derecha.addWidget(motivo)

        fecha = QLabel(
            "Enviada: "
            f"{str(s.get('fecha_solicitud', ''))[:16]}"
        )

        fecha.setStyleSheet(
            "font-size: 11px; color: #9CA3AF;"
        )

        derecha.addWidget(fecha)

        derecha.addStretch()

        if admin and s["estado"] == "pendiente":

            botones = QHBoxLayout()

            aprobar = boton_accion(
                "Aprobar",
                "#059669"
            )

            rechazar = boton_accion(
                "Rechazar",
                "#DC2626"
            )

            aprobar.clicked.connect(
                lambda checked=False, i=s["id_solicitud"]:
                self._resolver_solicitud(i, True)
            )

            rechazar.clicked.connect(
                lambda checked=False, i=s["id_solicitud"]:
                self._resolver_solicitud(i, False)
            )

            botones.addWidget(aprobar)

            botones.addWidget(rechazar)

            botones.addStretch()

            derecha.addLayout(botones)

        fila.addLayout(derecha, 1)

        return tarjeta

    # ------------------------------------------------------------
    # Pantallas del ARRENDADOR
    # ------------------------------------------------------------

    def mostrar_panel_arrendador(self):

        self._preparar_pagina()

        solicitud = self._solicitud_actual()

        estado = solicitud["estado"] if solicitud else None

        self.grid.addWidget(
            self._titulo_pagina(
                "Panel del arrendador",
                "Maneja tus propiedades. Cada casa nueva la aprueba "
                "un administrador antes de mostrarse a los estudiantes."
            ),
            0, 0, 1, 3
        )

        mensajes = {
            None: (
                "Aún no has enviado tu propiedad",
                "Envía una solicitud con la dirección, los "
                "datos y una foto de tu casa. Un administrador "
                "la revisará.",
                "#6B7280"
            ),
            "pendiente": (
                "Tu solicitud está en revisión",
                "Un administrador revisará la dirección "
                "y la imagen que enviaste.",
                "#D97706"
            ),
            "aprobada": (
                "¡Ya estás aprobado!",
                "Tu propiedad fue aprobada y ya la ven los "
                "estudiantes. Desde «Mis propiedades» puedes "
                "cambiar sus datos y fotos, o pedir otra casa.",
                "#059669"
            ),
            "rechazada": (
                "Tu solicitud fue rechazada",
                "Puedes enviar una nueva solicitud "
                "con información más clara.",
                "#DC2626"
            )
        }

        titulo, detalle, color = mensajes[estado]

        if estado == "rechazada" and solicitud.get(
            "motivo_rechazo"
        ):
            detalle += (
                f"\nMotivo: {solicitud['motivo_rechazo']}"
            )

        tarjeta = crear_tarjeta()

        layout = QVBoxLayout(tarjeta)

        layout.setContentsMargins(28, 24, 28, 24)

        layout.setSpacing(10)

        etiqueta_titulo = QLabel(titulo)

        etiqueta_titulo.setStyleSheet(
            f"font-size: 18px; font-weight: bold; "
            f"color: {color};"
        )

        etiqueta_detalle = QLabel(detalle)

        etiqueta_detalle.setWordWrap(True)

        etiqueta_detalle.setStyleSheet(
            "font-size: 13px; color: #374151;"
        )

        layout.addWidget(etiqueta_titulo)

        layout.addWidget(etiqueta_detalle)

        if estado != "aprobada":

            boton = boton_accion(
                "Ver mi solicitud"
                if estado == "pendiente"
                else "Enviar mi propiedad",
                self.color_interfaz
            )

            boton.clicked.connect(
                self._ir_a_verificacion
            )

            layout.addWidget(
                boton,
                alignment=Qt.AlignmentFlag.AlignLeft
            )

        if estado == "aprobada":

            boton = boton_accion(
                "Administrar mis propiedades",
                self.color_interfaz
            )

            boton.clicked.connect(self._ir_a_mis_propiedades)

            layout.addWidget(
                boton,
                alignment=Qt.AlignmentFlag.AlignLeft
            )

        self.grid.addWidget(tarjeta, 1, 0, 1, 3)

        if estado == "aprobada":

            propiedades = dao.obtener_propiedades_arrendador(
                self.id_usuario
            )

            datos = [
                (len(propiedades), "Propiedades"),
                (
                    sum(1 for p in propiedades if p["disponible"]),
                    "Publicadas"
                ),
                (
                    sum(int(p.get("num_fotos") or 0)
                        for p in propiedades),
                    "Fotos subidas"
                )
            ]

            contenedor = QWidget()

            fila = QHBoxLayout(contenedor)

            fila.setContentsMargins(0, 0, 0, 0)

            fila.setSpacing(16)

            for numero, texto in datos:

                caja = crear_tarjeta()

                caja_layout = QVBoxLayout(caja)

                caja_layout.setContentsMargins(22, 18, 22, 18)

                cifra = QLabel(str(numero))

                cifra.setStyleSheet(
                    f"font-size: 30px; font-weight: bold; "
                    f"color: {self.color_interfaz};"
                )

                nombre = QLabel(texto)

                nombre.setStyleSheet(
                    "font-size: 13px; color: #6B7280;"
                )

                caja_layout.addWidget(cifra)
                caja_layout.addWidget(nombre)

                fila.addWidget(caja)

            self.grid.addWidget(contenedor, 2, 0, 1, 3)

            self._fin_pagina(3)

            return

        self._fin_pagina(2)

    def mostrar_verificacion(self):

        self._preparar_pagina()

        solicitud = self._solicitud_actual()

        estado = solicitud["estado"] if solicitud else None

        self._imagen_solicitud = None

        self.grid.addWidget(
            self._titulo_pagina(
                "Solicitar mi propiedad",
                "Cuéntanos de tu casa para que el administrador "
                "la revise. Envía la dirección y/o una foto."
            ),
            0, 0, 1, 3
        )

        fila = 1

        if solicitud:

            self.grid.addWidget(
                self._tarjeta_solicitud(solicitud),
                fila, 0, 1, 3
            )

            fila += 1

        if estado == "pendiente":

            self._fin_pagina(fila)

            return

        formulario = crear_tarjeta()

        layout = QVBoxLayout(formulario)

        layout.setContentsMargins(28, 24, 28, 24)

        layout.setSpacing(10)

        titulo = QLabel(
            "Nueva solicitud"
            if not solicitud
            else (
                "Solicitar otra propiedad"
                if estado == "aprobada"
                else "Enviar una nueva solicitud"
            )
        )

        titulo.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )

        layout.addWidget(titulo)

        etiqueta = QLabel("Dirección de la casa")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        self._v_direccion = QLineEdit()

        self._v_direccion.setPlaceholderText(
            "Barrio, calle y número de la propiedad"
        )

        layout.addWidget(self._v_direccion)

        # --- Panel de selección: casa, habitación o apartamento ---
        etiqueta = QLabel("¿Qué vas a alquilar?")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        fila_tipo = QHBoxLayout()

        fila_tipo.setSpacing(10)

        self._v_grupo_tipo = QButtonGroup(self)

        self._v_grupo_tipo.setExclusive(True)

        for tipo in self.tipos:

            boton = QPushButton(tipo["nombre"])

            boton.setObjectName("filtroTipo")

            boton.setCheckable(True)

            boton.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            boton.setProperty("id_tipo", tipo["id_tipo"])

            self._v_grupo_tipo.addButton(boton)

            fila_tipo.addWidget(boton)

        fila_tipo.addStretch()

        layout.addLayout(fila_tipo)

        etiqueta = QLabel("Precio por mes (C$)")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        self._v_precio = QLineEdit()

        self._v_precio.setPlaceholderText(
            "Ejemplo: 2500"
        )

        layout.addWidget(self._v_precio)

        etiqueta = QLabel("Universidad más cercana")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        self._v_universidad = QComboBox()

        for universidad in self.universidades:

            self._v_universidad.addItem(
                universidad["nombre"],
                universidad["id_universidad"]
            )

        layout.addWidget(self._v_universidad)

        etiqueta = QLabel("Distancia a la universidad")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        self._v_distancia = QLineEdit()

        self._v_distancia.setPlaceholderText(
            "Ejemplo: 10 min a pie"
        )

        layout.addWidget(self._v_distancia)

        etiqueta = QLabel("Tu teléfono para que te contacten (opcional)")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        self._v_telefono = QLineEdit()

        self._v_telefono.setPlaceholderText(
            "Ejemplo: 8888 8888"
        )

        layout.addWidget(self._v_telefono)

        etiqueta = QLabel("Descripción (opcional)")

        etiqueta.setStyleSheet(
            "font-size: 13px; font-weight: bold; "
            "color: #374151;"
        )

        layout.addWidget(etiqueta)

        self._v_descripcion = QTextEdit()

        self._v_descripcion.setPlaceholderText(
            "Referencias del lugar, tipo de propiedad, "
            "cuartos disponibles..."
        )

        self._v_descripcion.setFixedHeight(80)

        layout.addWidget(self._v_descripcion)

        fila_imagen = QHBoxLayout()

        fila_imagen.setSpacing(16)

        self._v_vista = crear_miniatura(None, 260, 170)

        fila_imagen.addWidget(self._v_vista)

        columna = QVBoxLayout()

        elegir = boton_accion(
            "Seleccionar imagen de la casa",
            "#475569"
        )

        elegir.clicked.connect(
            self._elegir_imagen_solicitud
        )

        columna.addWidget(elegir)

        ayuda = QLabel(
            "Sube una foto de la fachada. "
            "Formatos: JPG, PNG o WEBP."
        )

        ayuda.setWordWrap(True)

        ayuda.setStyleSheet(
            "font-size: 12px; color: #6B7280;"
        )

        columna.addWidget(ayuda)

        columna.addStretch()

        fila_imagen.addLayout(columna, 1)

        layout.addLayout(fila_imagen)

        enviar = boton_accion(
            "Enviar solicitud",
            self.color_interfaz
        )

        enviar.clicked.connect(
            self._enviar_solicitud
        )

        layout.addWidget(
            enviar,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        self.grid.addWidget(formulario, fila, 0, 1, 3)

        self._fin_pagina(fila + 1)

    def _elegir_imagen_solicitud(self):

        ruta, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar imagen de la casa",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not ruta:
            return

        datos = imagen_a_bytes(ruta)

        if datos is None:

            QMessageBox.warning(
                self,
                "Imagen no válida",
                "No fue posible abrir esa imagen."
            )

            return

        self._imagen_solicitud = datos

        self._v_vista.setPixmap(
            pixmap_desde_bytes(datos, 260, 170)
        )

    def _enviar_solicitud(self):

        direccion = self._v_direccion.text().strip()

        descripcion = (
            self._v_descripcion.toPlainText().strip()
        )

        if not direccion and not self._imagen_solicitud:

            QMessageBox.warning(
                self,
                "Solicitud incompleta",
                "Agrega al menos la dirección o una "
                "imagen de la casa."
            )

            return

        if direccion and len(direccion) < 8:

            QMessageBox.warning(
                self,
                "Dirección muy corta",
                "Escribe una dirección más detallada."
            )

            return

        boton_tipo = self._v_grupo_tipo.checkedButton()

        if boton_tipo is None:

            QMessageBox.warning(
                self,
                "Falta el tipo",
                "Selecciona si es casa, habitación "
                "o apartamento."
            )

            return

        precio, error_precio = val.validar_precio(
            self._v_precio.text()
        )

        if error_precio:

            QMessageBox.warning(
                self,
                "Precio no válido",
                error_precio
            )

            return

        telefono = limpiar_telefono(self._v_telefono.text())

        if telefono is None:

            QMessageBox.warning(
                self,
                "Teléfono no válido",
                "Escribe solo números, por ejemplo 8888 8888."
            )

            return

        enviada = dao.crear_solicitud_arrendador(
            self.id_usuario,
            direccion,
            descripcion,
            self._imagen_solicitud,
            boton_tipo.property("id_tipo"),
            precio,
            self._v_universidad.currentData(),
            self._v_distancia.text().strip(),
            telefono
        )

        if not enviada:

            QMessageBox.critical(
                self,
                "Error",
                dao.ultimo_error_mensaje
                or "No fue posible enviar la solicitud. "
                "Quizá ya tienes una solicitud en revisión."
            )

            return

        QMessageBox.information(
            self,
            "Solicitud enviada",
            "Un administrador revisará tu solicitud. Cuando la "
            "apruebe, tu propiedad aparecerá en Inicio."
        )

        self.mostrar_verificacion()

    # ------------------------------------------------------------
    # Propiedades del ARRENDADOR (fotos, dirección, información)
    # ------------------------------------------------------------

    def _ir_a_verificacion(self):

        for boton in self.grupo_nav.buttons():
            if "Mis solicitudes" in boton.text():
                boton.click()
                return

        self.mostrar_verificacion()

    def _ir_a_mis_propiedades(self):

        for boton in self.grupo_nav.buttons():
            if "Mis propiedades" in boton.text():
                boton.click()
                return

        self.mostrar_mis_propiedades()

    def _tarjeta_propiedad_gestion(self, p, admin=False):
        """Tarjeta con portada y datos de una propiedad, con los
        botones de gestión del arrendador (o de moderación)."""

        tarjeta = crear_tarjeta()

        fila = QHBoxLayout(tarjeta)

        fila.setContentsMargins(20, 18, 20, 18)

        fila.setSpacing(20)

        portada = dao.obtener_portada_propiedad(
            p["id_propiedad"]
        )

        fila.addWidget(
            crear_miniatura(portada, 220, 150, llenar=True),
            alignment=Qt.AlignmentFlag.AlignTop
        )

        derecha = QVBoxLayout()

        derecha.setSpacing(6)

        cabecera = QHBoxLayout()

        titulo = QLabel(p["titulo"])

        titulo.setWordWrap(True)

        titulo.setStyleSheet(
            "font-size: 15px; font-weight: bold; "
            "color: #111827;"
        )

        cabecera.addWidget(titulo, 1)

        visible = bool(p["disponible"])

        cabecera.addWidget(
            crear_chip(
                "Publicada" if visible else "Oculta",
                "#059669" if visible else "#6B7280"
            )
        )

        derecha.addLayout(cabecera)

        direccion = QLabel(
            f"📍 {p.get('direccion') or p['zona']}"
        )

        direccion.setWordWrap(True)

        direccion.setStyleSheet(
            "font-size: 13px; color: #374151;"
        )

        derecha.addWidget(direccion)

        partes = [
            p["tipo"],
            f"C$ {float(p['precio']):,.0f} /mes",
            f"🎓 {p['universidad']}",
            f"🚶 {p['distancia']}"
        ]

        if p.get("habitaciones"):
            partes.append(f"🛏 {p['habitaciones']}")

        if p.get("camas"):
            partes.append(f"🛌 {p['camas']} cama(s)")

        if p.get("banos"):
            partes.append(f"🚿 {p['banos']}")

        if p.get("telefono"):
            partes.append(f"📞 {p['telefono']}")

        resumen = QLabel("  ·  ".join(partes))

        resumen.setWordWrap(True)

        resumen.setStyleSheet(
            "font-size: 12px; color: #1E3A8A; "
            "font-weight: bold;"
        )

        derecha.addWidget(resumen)

        if p.get("descripcion"):

            texto = p["descripcion"]

            if len(texto) > 140:
                texto = texto[:140] + "…"

            descripcion = QLabel(texto)

            descripcion.setWordWrap(True)

            descripcion.setStyleSheet(
                "font-size: 12px; color: #6B7280;"
            )

            derecha.addWidget(descripcion)

        if p.get("amenidades"):

            amenidades = QLabel(
                " · ".join(p["amenidades"])
            )

            amenidades.setWordWrap(True)

            amenidades.setStyleSheet(
                "font-size: 11px; color: #9CA3AF;"
            )

            derecha.addWidget(amenidades)

        fotos = QLabel(
            f"📷 {p.get('num_fotos', 0)} foto(s)"
        )

        fotos.setStyleSheet(
            "font-size: 11px; color: #9CA3AF;"
        )

        derecha.addWidget(fotos)

        derecha.addStretch()

        botones = QHBoxLayout()

        if not admin:

            editar = boton_accion("Editar", self.color_interfaz)

            editar.clicked.connect(
                lambda checked=False, i=p["id_propiedad"]:
                self.mostrar_formulario_propiedad(i)
            )

            botones.addWidget(editar)

        alternar = boton_accion(
            "Ocultar" if visible else "Publicar",
            "#D97706" if visible else "#059669"
        )

        alternar.clicked.connect(
            lambda checked=False, i=p["id_propiedad"], v=visible:
            self._alternar_disponibilidad(i, not v, admin)
        )

        botones.addWidget(alternar)

        if not admin:

            borrar = boton_accion("Eliminar", "#DC2626")

            borrar.clicked.connect(
                lambda checked=False, i=p["id_propiedad"]:
                self._eliminar_propiedad(i)
            )

            botones.addWidget(borrar)

        botones.addStretch()

        derecha.addLayout(botones)

        fila.addLayout(derecha, 1)

        return tarjeta

    def mostrar_mis_propiedades(self):

        self._preparar_pagina()

        self._solicitud_actual()

        verificado = dao.arrendador_verificado(self.id_usuario)

        self.grid.addWidget(
            self._titulo_pagina(
                "Mis propiedades",
                "Cada propiedad nueva la aprueba un administrador; "
                "después puedes editar su información y fotos "
                "cuando quieras."
            ),
            0, 0, 1, 3
        )

        fila = 1

        if not verificado:

            tarjeta = crear_tarjeta()

            layout = QVBoxLayout(tarjeta)

            layout.setContentsMargins(28, 24, 28, 24)

            layout.setSpacing(10)

            titulo = QLabel("Primero envía tu solicitud")

            titulo.setStyleSheet(
                "font-size: 17px; font-weight: bold; "
                "color: #D97706;"
            )

            detalle = QLabel(
                "Tu propiedad aparece en Inicio cuando un "
                "administrador aprueba tu solicitud. Después "
                "podrás editar su información y fotos desde aquí."
            )

            detalle.setWordWrap(True)

            detalle.setStyleSheet(
                "font-size: 13px; color: #374151;"
            )

            boton = boton_accion(
                "Ir a Mis solicitudes",
                self.color_interfaz
            )

            boton.clicked.connect(self._ir_a_verificacion)

            layout.addWidget(titulo)
            layout.addWidget(detalle)
            layout.addWidget(
                boton,
                alignment=Qt.AlignmentFlag.AlignLeft
            )

            self.grid.addWidget(tarjeta, fila, 0, 1, 3)

            self._fin_pagina(fila + 1)

            return

        agregar = boton_accion(
            "＋ Solicitar nueva propiedad",
            self.color_interfaz
        )

        agregar.clicked.connect(self._ir_a_verificacion)

        self.grid.addWidget(
            agregar,
            fila, 0,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        fila += 1

        propiedades = dao.obtener_propiedades_arrendador(
            self.id_usuario
        )

        if not propiedades:

            vacio = QLabel(
                "Todavía no tienes propiedades publicadas.\n"
                "Usa «Solicitar nueva propiedad» y espera la "
                "aprobación del administrador."
            )

            vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; "
                "background: white; border-radius: 12px; "
                "padding: 40px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        for p in propiedades:

            self.grid.addWidget(
                self._tarjeta_propiedad_gestion(p),
                fila, 0, 1, 3
            )

            fila += 1

        self._fin_pagina(fila)

    def _alternar_disponibilidad(self, id_propiedad, disponible, admin=False):

        if admin:
            hecho = dao.cambiar_disponibilidad_admin(
                id_propiedad,
                disponible,
                self.id_usuario
            )
        else:
            hecho = dao.cambiar_disponibilidad_propiedad(
                self.id_usuario,
                id_propiedad,
                disponible
            )

        if not hecho:

            QMessageBox.critical(
                self,
                "Error",
                "No fue posible cambiar la visibilidad."
            )

            return

        if admin:
            self.mostrar_propiedades_admin(
                self._admin_arrendador["id_usuario"],
                self._admin_arrendador["nombre"]
            )
        else:
            self.mostrar_mis_propiedades()

    def _cancelar_cambios(self, id_propiedad):

        if dao.cancelar_edicion_arrendador(
            self.id_usuario,
            id_propiedad
        ):
            self.mostrar_mis_propiedades()
        else:
            QMessageBox.critical(
                self,
                "Error",
                "No fue posible cancelar los cambios."
            )

    def _eliminar_propiedad(self, id_propiedad):

        respuesta = QMessageBox.question(
            self,
            "Eliminar propiedad",
            "¿Seguro que deseas eliminar esta propiedad "
            "y todas sus fotos? No se puede deshacer.",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        if not dao.eliminar_propiedad_arrendador(
            self.id_usuario,
            id_propiedad
        ):

            QMessageBox.critical(
                self,
                "Error",
                "No fue posible eliminar la propiedad."
            )

            return

        self.mostrar_mis_propiedades()

    # --- Formulario de propiedad (alta y edición) ---------------

    def mostrar_formulario_propiedad(self, id_propiedad=None):

        if (
            not id_propiedad
            or not dao.arrendador_verificado(self.id_usuario)
        ):
            self.mostrar_mis_propiedades()
            return

        self._preparar_pagina()

        propiedad = None

        if id_propiedad:

            propiedad = dao.obtener_propiedad(id_propiedad)

            if (
                not propiedad
                or propiedad.get("id_arrendador") != self.id_usuario
            ):
                self.mostrar_mis_propiedades()
                return

        self._pf_id = id_propiedad

        borrador = None

        self._pf_fotos = []

        if id_propiedad:

            for foto in dao.obtener_fotos_propiedad(
                id_propiedad, borrador=True
            ):

                # Las fotos nuevas por aprobar se vuelven a enviar
                # completas al guardar (id None).
                self._pf_fotos.append({
                    "id_foto": (
                        None if foto["pendiente"]
                        else foto["id_foto"]
                    ),
                    "imagen": foto["imagen"]
                })

        self._pf_borrar = []

        self.grid.addWidget(
            self._titulo_pagina(
                "Editar propiedad" if propiedad
                else "Agregar propiedad",
                "Completa la información que verán los "
                "estudiantes y sube fotos de la casa."
            ),
            0, 0, 1, 3
        )

        formulario = crear_tarjeta()

        layout = QVBoxLayout(formulario)

        layout.setContentsMargins(28, 24, 28, 24)

        layout.setSpacing(10)

        if propiedad:

            aviso = QLabel(
                "Tu propiedad ya fue aprobada: los cambios que "
                "guardes aquí (información y fotos) se publican "
                "al instante."
            )

            aviso.setWordWrap(True)

            aviso.setStyleSheet(
                "background: #FEF3C7; color: #92400E; "
                "border-radius: 8px; padding: 10px; "
                "font-size: 12px;"
            )

            layout.addWidget(aviso)

        def etiqueta(texto):

            e = QLabel(texto)

            e.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
                "color: #374151;"
            )

            layout.addWidget(e)

        estilo_spin = (
            "QSpinBox { background: #FAFBFC; "
            "border: 2px solid #E2E5EB; border-radius: 9px; "
            "padding: 6px 10px; color: #111827; }"
        )

        etiqueta("Título (opcional)")

        self._pf_titulo = QLineEdit(
            propiedad["titulo"] if propiedad else ""
        )

        self._pf_titulo.setPlaceholderText(
            "Ejemplo: Casa amplia cerca de la UNAN"
        )

        layout.addWidget(self._pf_titulo)

        etiqueta("Dirección de la casa")

        self._pf_direccion = QLineEdit(
            (propiedad.get("direccion") or propiedad["zona"])
            if propiedad else ""
        )

        self._pf_direccion.setPlaceholderText(
            "Barrio, calle y número de la propiedad"
        )

        layout.addWidget(self._pf_direccion)

        etiqueta("¿Qué alquilas?")

        fila_tipo = QHBoxLayout()

        fila_tipo.setSpacing(10)

        self._pf_grupo_tipo = QButtonGroup(self)

        self._pf_grupo_tipo.setExclusive(True)

        for tipo in self.tipos:

            boton = QPushButton(tipo["nombre"])

            boton.setObjectName("filtroTipo")

            boton.setCheckable(True)

            boton.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            boton.setProperty("id_tipo", tipo["id_tipo"])

            if propiedad and propiedad["id_tipo"] == tipo["id_tipo"]:
                boton.setChecked(True)

            self._pf_grupo_tipo.addButton(boton)

            fila_tipo.addWidget(boton)

        fila_tipo.addStretch()

        layout.addLayout(fila_tipo)

        etiqueta("Precio por mes (C$)")

        self._pf_precio = QLineEdit(
            f"{float(propiedad['precio']):.0f}"
            if propiedad else ""
        )

        self._pf_precio.setPlaceholderText("Ejemplo: 2500")

        layout.addWidget(self._pf_precio)

        etiqueta("Universidad más cercana")

        self._pf_universidad = QComboBox()

        for universidad in self.universidades:

            self._pf_universidad.addItem(
                universidad["nombre"],
                universidad["id_universidad"]
            )

        if propiedad:

            indice = self._pf_universidad.findData(
                propiedad["id_universidad"]
            )

            if indice >= 0:
                self._pf_universidad.setCurrentIndex(indice)

        layout.addWidget(self._pf_universidad)

        etiqueta("Distancia a la universidad")

        self._pf_distancia = QLineEdit(
            propiedad["distancia"] if propiedad else ""
        )

        self._pf_distancia.setPlaceholderText(
            "Ejemplo: 10 min a pie"
        )

        layout.addWidget(self._pf_distancia)

        etiqueta("Tu teléfono para que te contacten (opcional)")

        self._pf_telefono = QLineEdit(
            (propiedad.get("telefono") or "") if propiedad else ""
        )

        self._pf_telefono.setPlaceholderText("Ejemplo: 8888 8888")

        layout.addWidget(self._pf_telefono)

        fila_num = QHBoxLayout()

        fila_num.setSpacing(16)

        col1 = QVBoxLayout()

        e1 = QLabel("Habitaciones")

        e1.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #374151;"
        )

        self._pf_habitaciones = QSpinBox()

        self._pf_habitaciones.setRange(0, 30)

        self._pf_habitaciones.setStyleSheet(estilo_spin)

        self._pf_habitaciones.setValue(
            (propiedad.get("habitaciones") or 0) if propiedad else 1
        )

        col1.addWidget(e1)
        col1.addWidget(self._pf_habitaciones)

        col2 = QVBoxLayout()

        e2 = QLabel("Baños")

        e2.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #374151;"
        )

        self._pf_banos = QSpinBox()

        self._pf_banos.setRange(0, 30)

        self._pf_banos.setStyleSheet(estilo_spin)

        self._pf_banos.setValue(
            (propiedad.get("banos") or 0) if propiedad else 1
        )

        col2.addWidget(e2)
        col2.addWidget(self._pf_banos)

        col3 = QVBoxLayout()

        e3 = QLabel("Camas")

        e3.setStyleSheet(
            "font-size: 13px; font-weight: bold; color: #374151;"
        )

        self._pf_camas = QSpinBox()

        self._pf_camas.setRange(0, 30)

        self._pf_camas.setStyleSheet(estilo_spin)

        self._pf_camas.setValue(
            (propiedad.get("camas") or 0) if propiedad else 1
        )

        col3.addWidget(e3)
        col3.addWidget(self._pf_camas)

        fila_num.addLayout(col1)
        fila_num.addLayout(col2)
        fila_num.addLayout(col3)
        fila_num.addStretch()

        layout.addLayout(fila_num)

        # Casa: habitaciones + baños. Apartamento: camas + baños.
        # Habitación: solo baños.
        def actualizar_conteos(*_):

            boton = self._pf_grupo_tipo.checkedButton()

            tipo = boton.text().strip().casefold() if boton else ""

            es_apto = tipo.startswith("apartament")
            es_hab = tipo.startswith("habitaci")

            ver_hab = not es_apto and not es_hab

            e1.setVisible(ver_hab)
            self._pf_habitaciones.setVisible(ver_hab)

            e3.setVisible(es_apto)
            self._pf_camas.setVisible(es_apto)

        self._pf_grupo_tipo.buttonClicked.connect(
            actualizar_conteos
        )

        actualizar_conteos()

        etiqueta("Información de la casa")

        self._pf_descripcion = QTextEdit()

        self._pf_descripcion.setPlainText(
            (propiedad.get("descripcion") or "")
            if propiedad else ""
        )

        self._pf_descripcion.setPlaceholderText(
            "Describe la casa: estado, reglas, servicios "
            "incluidos, referencias del lugar..."
        )

        self._pf_descripcion.setFixedHeight(100)

        layout.addWidget(self._pf_descripcion)

        amenidades = dao.obtener_amenidades()

        self._pf_checks = []

        if amenidades:

            etiqueta("Servicios")

            if borrador:
                marcadas_ids = set(borrador.get("amenidades", []))
            elif propiedad:
                nombres = set(propiedad["amenidades"])
                marcadas_ids = {
                    a["id_amenidad"] for a in amenidades
                    if a["nombre"] in nombres
                }
            else:
                marcadas_ids = set()

            cuadricula = QGridLayout()

            for i, a in enumerate(amenidades):

                check = QCheckBox(a["nombre"])

                check.setStyleSheet(
                    "background: transparent; color: #111827; "
                    "font-size: 13px;"
                )

                check.setChecked(a["id_amenidad"] in marcadas_ids)

                check.setProperty("id_amenidad", a["id_amenidad"])

                self._pf_checks.append(check)

                cuadricula.addWidget(check, i // 3, i % 3)

            layout.addLayout(cuadricula)

        etiqueta(
            f"Fotos de la casa (máximo {dao.MAX_FOTOS})"
        )

        self._pf_contenedor_fotos = QWidget()

        self._pf_contenedor_fotos.setStyleSheet(
            "background: transparent;"
        )

        self._pf_grid_fotos = QGridLayout(
            self._pf_contenedor_fotos
        )

        self._pf_grid_fotos.setContentsMargins(0, 0, 0, 0)

        self._pf_grid_fotos.setSpacing(10)

        layout.addWidget(self._pf_contenedor_fotos)

        self._pf_boton_fotos = boton_accion(
            "Agregar fotos...",
            "#475569"
        )

        self._pf_boton_fotos.clicked.connect(
            self._agregar_fotos_formulario
        )

        layout.addWidget(
            self._pf_boton_fotos,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        self._refrescar_fotos_formulario()

        fila_botones = QHBoxLayout()

        guardar = boton_accion(
            "Guardar cambios" if propiedad else "Publicar propiedad",
            self.color_interfaz
        )

        guardar.clicked.connect(self._guardar_propiedad)

        cancelar = boton_accion("Cancelar", "#6B7280")

        cancelar.clicked.connect(self.mostrar_mis_propiedades)

        fila_botones.addWidget(guardar)
        fila_botones.addWidget(cancelar)
        fila_botones.addStretch()

        layout.addLayout(fila_botones)

        self.grid.addWidget(formulario, 1, 0, 1, 3)

        self._fin_pagina(2)

    def _refrescar_fotos_formulario(self):

        while self._pf_grid_fotos.count():

            item = self._pf_grid_fotos.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        for i, foto in enumerate(self._pf_fotos):

            celda = QWidget()

            celda.setStyleSheet("background: transparent;")

            columna = QVBoxLayout(celda)

            columna.setContentsMargins(0, 0, 0, 0)

            columna.setSpacing(4)

            columna.addWidget(
                crear_miniatura(
                    foto["imagen"], 150, 100, llenar=True
                )
            )

            quitar = QPushButton(
                "Portada" if i == 0 else "Quitar"
            )

            if i == 0:

                quitar.setEnabled(False)

                quitar.setStyleSheet(
                    "QPushButton { background: #D1FAE5; "
                    "color: #047857; border: none; "
                    "border-radius: 6px; padding: 4px; "
                    "font-size: 11px; font-weight: bold; }"
                )

                columna.addWidget(quitar)

                quitar2 = QPushButton("Quitar")

            else:

                quitar2 = quitar

            quitar2.setCursor(Qt.CursorShape.PointingHandCursor)

            quitar2.setStyleSheet(
                "QPushButton { background: #FEE2E2; "
                "color: #B91C1C; border: none; "
                "border-radius: 6px; padding: 4px; "
                "font-size: 11px; font-weight: bold; }"
                "QPushButton:hover { background: #FECACA; }"
            )

            quitar2.clicked.connect(
                lambda checked=False, n=i:
                self._quitar_foto_formulario(n)
            )

            columna.addWidget(quitar2)

            self._pf_grid_fotos.addWidget(celda, i // 4, i % 4)

        restantes = dao.MAX_FOTOS - len(self._pf_fotos)

        self._pf_boton_fotos.setEnabled(restantes > 0)

        self._pf_boton_fotos.setText(
            f"Agregar fotos... ({len(self._pf_fotos)}/{dao.MAX_FOTOS})"
        )

    def _agregar_fotos_formulario(self):

        restantes = dao.MAX_FOTOS - len(self._pf_fotos)

        if restantes <= 0:
            return

        rutas, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleccionar fotos de la casa",
            "",
            "Imágenes (*.png *.jpg *.jpeg *.webp *.bmp)"
        )

        if not rutas:
            return

        if len(rutas) > restantes:

            QMessageBox.information(
                self,
                "Límite de fotos",
                f"Solo caben {restantes} foto(s) más. "
                "Se agregarán las primeras."
            )

            rutas = rutas[:restantes]

        for ruta in rutas:

            datos = imagen_a_bytes(ruta)

            if datos is None:

                QMessageBox.warning(
                    self,
                    "Imagen no válida",
                    f"No fue posible abrir:\n{ruta}"
                )

                continue

            self._pf_fotos.append(
                {"id_foto": None, "imagen": datos}
            )

        self._refrescar_fotos_formulario()

    def _quitar_foto_formulario(self, indice):

        foto = self._pf_fotos.pop(indice)

        if foto["id_foto"]:
            self._pf_borrar.append(foto["id_foto"])

        self._refrescar_fotos_formulario()

    def _guardar_propiedad(self):

        direccion = self._pf_direccion.text().strip()

        if len(direccion) < 8:

            QMessageBox.warning(
                self,
                "Dirección requerida",
                "Escribe una dirección detallada "
                "(barrio, calle y número)."
            )

            return

        boton_tipo = self._pf_grupo_tipo.checkedButton()

        if boton_tipo is None:

            QMessageBox.warning(
                self,
                "Falta el tipo",
                "Selecciona si es casa, habitación "
                "o apartamento."
            )

            return

        precio, error_precio = val.validar_precio(
            self._pf_precio.text()
        )

        if error_precio:

            QMessageBox.warning(
                self,
                "Precio no válido",
                error_precio
            )

            return

        telefono = limpiar_telefono(self._pf_telefono.text())

        if telefono is None:

            QMessageBox.warning(
                self,
                "Teléfono no válido",
                "Escribe solo números, por ejemplo 8888 8888."
            )

            return

        if not self._pf_fotos:

            respuesta = QMessageBox.question(
                self,
                "Sin fotos",
                "No agregaste fotos. Las propiedades con "
                "fotos atraen más estudiantes.\n"
                "¿Guardar de todos modos?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if respuesta != QMessageBox.StandardButton.Yes:
                return

        titulo = self._pf_titulo.text().strip()

        if not titulo:
            titulo = f"{boton_tipo.text()} en {direccion}"

        datos = {
            "titulo": titulo[:100],
            "zona": direccion[:100],
            "direccion": direccion[:255],
            "descripcion": (
                self._pf_descripcion.toPlainText().strip()
            ),
            "habitaciones": (
                None
                if boton_tipo.text().strip().casefold().startswith(
                    ("apartament", "habitaci")
                )
                else (self._pf_habitaciones.value() or None)
            ),
            "camas": (
                (self._pf_camas.value() or None)
                if boton_tipo.text().strip().casefold().startswith(
                    "apartament"
                )
                else None
            ),
            "banos": self._pf_banos.value() or None,
            "telefono": telefono or None,
            "id_universidad": self._pf_universidad.currentData(),
            "distancia": (
                self._pf_distancia.text().strip()
                or "Cerca de la universidad"
            ),
            "precio": precio,
            "id_tipo": boton_tipo.property("id_tipo"),
            "amenidades": [
                c.property("id_amenidad")
                for c in self._pf_checks
                if c.isChecked()
            ]
        }

        if self._pf_id:

            guardada = dao.guardar_cambios_propiedad(
                self.id_usuario,
                self._pf_id,
                datos,
                [
                    f["imagen"] for f in self._pf_fotos
                    if f["id_foto"] is None
                ],
                [
                    f["id_foto"] for f in self._pf_fotos
                    if f["id_foto"] is not None
                ]
            )

            if not guardada:

                QMessageBox.critical(
                    self,
                    "Error",
                    dao.ultimo_error_mensaje
                    or "No fue posible guardar los cambios."
                )

                return

            QMessageBox.information(
                self,
                "Cambios guardados",
                "Tus cambios ya están visibles para los "
                "estudiantes."
            )

            self.mostrar_mis_propiedades()

            return

        # Sin propiedad aprobada no se puede publicar por cuenta propia.
        self.mostrar_mis_propiedades()

        return


    # ------------------------------------------------------------
    # Pantallas del ADMINISTRADOR
    # ------------------------------------------------------------

    def mostrar_panel_admin(self):

        self._preparar_pagina()

        resumen = dao.obtener_resumen_admin()

        self.grid.addWidget(
            self._titulo_pagina(
                "Panel de administración",
                "Datos de estudiantes, arrendadores "
                "y solicitudes."
            ),
            0, 0, 1, 3
        )

        datos = [
            (resumen["estudiantes"], "Estudiantes", "#2563EB"),
            (resumen["arrendadores"], "Arrendadores", "#059669"),
            (
                resumen["pendientes"],
                "Solicitudes pendientes",
                "#D97706"
            ),
            (
                resumen["permisos"],
                "Permisos de arrendador",
                "#B45309"
            ),
            (
                resumen["cambios"],
                "Cambios por revisar",
                "#0F766E"
            ),
            (resumen["comentarios"], "Comentarios", "#6B21A8")
        ]

        contenedor = QWidget()

        fila = QGridLayout(contenedor)

        fila.setContentsMargins(0, 0, 0, 0)

        fila.setSpacing(16)

        for posicion, (numero, texto, color) in enumerate(datos):

            tarjeta = crear_tarjeta()

            layout = QVBoxLayout(tarjeta)

            layout.setContentsMargins(22, 20, 22, 20)

            cifra = QLabel(str(numero))

            cifra.setStyleSheet(
                f"font-size: 34px; font-weight: bold; "
                f"color: {color};"
            )

            etiqueta = QLabel(texto)

            etiqueta.setStyleSheet(
                "font-size: 13px; color: #6B7280;"
            )

            layout.addWidget(cifra)

            layout.addWidget(etiqueta)

            fila.addWidget(tarjeta, posicion // 3, posicion % 3)

        self.grid.addWidget(contenedor, 1, 0, 1, 3)

        boton_reporte = boton_accion(
            "Descargar reporte en PDF", "#DC2626"
        )

        boton_reporte.clicked.connect(self._descargar_reporte_admin)

        self.grid.addWidget(
            boton_reporte, 2, 0,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        boton_excel = boton_accion(
            "Descargar reporte en Excel", "#059669"
        )

        boton_excel.clicked.connect(self._descargar_reporte_admin_excel)

        self.grid.addWidget(
            boton_excel, 2, 1,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        self._fin_pagina(3)

    def _descargar_reporte_admin_excel(self):

        datos = dao.obtener_reporte_admin(self.id_usuario)

        if datos is None:
            QMessageBox.critical(
                self, "Error",
                dao.ultimo_error_mensaje
                or "No fue posible generar el reporte."
            )
            return

        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte",
            "reporte_unihogar.xlsx", "Excel (*.xlsx)"
        )

        if not ruta:
            return

        if not ruta.lower().endswith(".xlsx"):
            ruta += ".xlsx"

        try:
            generar_reporte_admin_excel(
                ruta, datos, self.nombre_completo or ""
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"No se pudo crear el Excel: {e}"
            )
            return

        QMessageBox.information(
            self, "Reporte listo",
            f"El reporte se guardó en:\n{ruta}"
        )

    def _descargar_reporte_admin(self):

        datos = dao.obtener_reporte_admin(self.id_usuario)

        if datos is None:

            QMessageBox.critical(
                self,
                "Error",
                dao.ultimo_error_mensaje
                or "No fue posible generar el reporte."
            )

            return

        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar reporte",
            "reporte_unihogar.pdf",
            "PDF (*.pdf)"
        )

        if not ruta:
            return

        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"

        try:
            generar_reporte_admin(
                ruta, datos, self.nombre_completo or ""
            )

        except Exception as e:

            QMessageBox.critical(
                self,
                "Error",
                f"No se pudo crear el PDF: {e}"
            )

            return

        QMessageBox.information(
            self,
            "Reporte listo",
            f"El reporte se guardó en:\n{ruta}"
        )

    def mostrar_tipo_cambio(self):
        """Consulta la tasa C$/US$ (API pública) y convierte un alquiler."""

        self._preparar_pagina()

        self.grid.addWidget(
            self._titulo_pagina(
                "Tipo de cambio",
                "Consulta el valor del dólar y convierte el alquiler "
                "de córdobas a dólares."
            ),
            0, 0, 1, 3
        )

        tarjeta = crear_tarjeta()
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(20, 18, 20, 18)
        caja.setSpacing(10)

        self._lbl_tasa = QLabel("Tasa: --")
        self._lbl_tasa.setStyleSheet(
            "font-size: 20px; font-weight: bold; color: #111827; "
            "background: transparent;"
        )
        self._lbl_fecha = QLabel("Última actualización: --")
        self._lbl_fecha.setStyleSheet(
            "color: #6B7280; font-size: 12px; background: transparent;"
        )
        self._lbl_estado_api = QLabel("")
        self._lbl_estado_api.setWordWrap(True)
        self._lbl_estado_api.setStyleSheet(
            "color: #DC2626; font-size: 13px; background: transparent;"
        )

        self._entrada_monto = QLineEdit()
        self._entrada_monto.setPlaceholderText(
            "Monto en córdobas, ej. 4500"
        )
        self._lbl_conversion = QLabel("")
        self._lbl_conversion.setStyleSheet(
            "font-size: 16px; color: #059669; font-weight: bold; "
            "background: transparent;"
        )
        self._entrada_monto.textChanged.connect(
            self._actualizar_conversion
        )

        pie = QLabel(
            "Fuente: ExchangeRate-API (open.er-api.com). "
            "Valores de referencia, no oficiales."
        )
        pie.setStyleSheet(
            "color: #9CA3AF; font-size: 11px; background: transparent;"
        )

        self._btn_tasa = boton_accion("Consultar tipo de cambio", "#2563EB")
        self._btn_tasa.clicked.connect(self._consultar_tasa)

        for w in (
            self._lbl_tasa, self._lbl_fecha, self._lbl_estado_api,
            self._entrada_monto, self._lbl_conversion, self._btn_tasa, pie
        ):
            caja.addWidget(w)

        self._tasa_actual = None
        self.grid.addWidget(tarjeta, 1, 0, 1, 2)
        self._fin_pagina(2)

        self._consultar_tasa()

    def _consultar_tasa(self):

        if getattr(self, "_hilo_tasa", None) is not None:
            return  # ya hay una consulta en curso

        self._btn_tasa.setEnabled(False)
        self._lbl_estado_api.setText("")
        self._lbl_tasa.setText("Consultando...")

        self._hilo_tasa = QThread(self)
        self._trabajador_tasa = TrabajadorTasa()
        self._trabajador_tasa.moveToThread(self._hilo_tasa)

        self._hilo_tasa.started.connect(self._trabajador_tasa.run)
        self._trabajador_tasa.terminado.connect(self._tasa_lista)
        self._trabajador_tasa.fallo.connect(self._tasa_fallo)
        self._trabajador_tasa.terminado.connect(self._hilo_tasa.quit)
        self._trabajador_tasa.fallo.connect(self._hilo_tasa.quit)
        self._hilo_tasa.finished.connect(self._limpiar_hilo_tasa)

        self._hilo_tasa.start()

    def _limpiar_hilo_tasa(self):

        self._hilo_tasa.deleteLater()
        self._trabajador_tasa.deleteLater()
        self._hilo_tasa = None
        self._trabajador_tasa = None

        try:
            self._btn_tasa.setEnabled(True)
        except RuntimeError:
            pass  # la página ya fue reemplazada

    def _tasa_lista(self, datos):

        try:
            self._tasa_actual = datos["nio_por_usd"]
            self._lbl_tasa.setText(
                f"US$ 1 = C$ {datos['nio_por_usd']:,.2f}"
            )
            self._lbl_fecha.setText(
                f"Última actualización: {datos['actualizado']}"
            )
            self._actualizar_conversion()
        except RuntimeError:
            pass

    def _tasa_fallo(self, mensaje):

        try:
            self._lbl_tasa.setText("Tasa: no disponible")
            self._lbl_estado_api.setText(mensaje)
        except RuntimeError:
            pass

    def _actualizar_conversion(self):

        texto = self._entrada_monto.text().strip().replace(",", "")

        if not texto or not self._tasa_actual:
            self._lbl_conversion.setText("")
            return

        try:
            dolares = api_service.cordobas_a_dolares(
                texto, self._tasa_actual
            )
            self._lbl_conversion.setText(
                f"C$ {float(texto):,.2f}  ≈  US$ {dolares:,.2f}"
            )
        except ValueError:
            self._lbl_conversion.setText("Escribe un monto válido.")

    def mostrar_solicitudes(self, solo_pendientes=True):

        self._preparar_pagina()

        self._solo_pendientes = solo_pendientes

        solicitudes = dao.obtener_solicitudes(
            solo_pendientes
        )

        self.grid.addWidget(
            self._titulo_pagina(
                "Solicitudes de arrendadores",
                "Revisa la dirección y la imagen de la casa "
                "antes de aprobar."
            ),
            0, 0, 1, 3
        )

        filtro = boton_accion(
            "Ver todas"
            if solo_pendientes
            else "Ver solo pendientes",
            "#475569"
        )

        filtro.clicked.connect(
            lambda: self.mostrar_solicitudes(
                not solo_pendientes
            )
        )

        self.grid.addWidget(
            filtro,
            1, 0,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        fila = 2

        if not solicitudes:

            vacio = QLabel(
                "No hay solicitudes pendientes."
                if solo_pendientes
                else "No hay solicitudes registradas."
            )

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; "
                "padding: 20px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        for s in solicitudes:

            self.grid.addWidget(
                self._tarjeta_solicitud(s, admin=True),
                fila, 0, 1, 3
            )

            fila += 1

        self._fin_pagina(fila)

    def _resolver_solicitud(self, id_solicitud, aprobar):

        motivo = None

        if aprobar:

            respuesta = QMessageBox.question(
                self,
                "Aprobar solicitud",
                "¿Aceptar la solicitud de este arrendador?\n\n"
                "Su propiedad aparecerá en el inicio de "
                "los estudiantes.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if respuesta != QMessageBox.StandardButton.Yes:
                return

        else:

            texto, aceptado = QInputDialog.getText(
                self,
                "Rechazar solicitud",
                "Motivo del rechazo (opcional):"
            )

            if not aceptado:
                return

            motivo = texto.strip() or None

        if not dao.resolver_solicitud(
            id_solicitud,
            aprobar,
            self.id_usuario,
            motivo
        ):

            QMessageBox.critical(
                self,
                "Error",
                dao.ultimo_error_mensaje
                or "No fue posible actualizar la solicitud."
            )

            return

        self.mostrar_solicitudes(self._solo_pendientes)

    def mostrar_solicitudes_rol(self, solo_pendientes=True):

        self._preparar_pagina()

        self._solo_pendientes_rol = solo_pendientes

        solicitudes = dao.obtener_solicitudes_rol(solo_pendientes)

        self.grid.addWidget(
            self._titulo_pagina(
                "Permisos de arrendador",
                "Personas que se registraron como arrendador. "
                "Hasta que aceptes, siguen como estudiantes."
            ),
            0, 0, 1, 3
        )

        filtro = boton_accion(
            "Ver todas" if solo_pendientes else "Ver solo pendientes",
            "#475569"
        )

        filtro.clicked.connect(
            lambda: self.mostrar_solicitudes_rol(not solo_pendientes)
        )

        self.grid.addWidget(
            filtro, 1, 0,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        fila = 2

        if not solicitudes:

            vacio = QLabel(
                "No hay permisos pendientes."
                if solo_pendientes
                else "No hay solicitudes de permiso."
            )

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; padding: 20px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        for r in solicitudes:

            self.grid.addWidget(
                self._tarjeta_solicitud_rol(r),
                fila, 0, 1, 3
            )

            fila += 1

        self._fin_pagina(fila)

    def _tarjeta_solicitud_rol(self, r):

        tarjeta = crear_tarjeta()

        layout = QHBoxLayout(tarjeta)

        layout.setContentsMargins(24, 18, 24, 18)

        layout.setSpacing(14)

        datos = QVBoxLayout()

        nombre = QLabel(r["nombre"])

        nombre.setStyleSheet(
            f"font-size: 16px; font-weight: bold; "
            f"color: {self.color_interfaz}; background: transparent;"
        )

        detalle = QLabel(
            f"@{r['usuario']}  ·  Quiere ser arrendador  ·  "
            f"{str(r.get('fecha_solicitud', ''))[:16]}"
        )

        detalle.setStyleSheet(
            "font-size: 12px; color: #6B7280; background: transparent;"
        )

        datos.addWidget(nombre)

        datos.addWidget(detalle)

        if r["estado"] == "rechazada" and r.get("motivo_rechazo"):

            motivo = QLabel(f"Motivo: {r['motivo_rechazo']}")

            motivo.setWordWrap(True)

            motivo.setStyleSheet(
                "font-size: 12px; color: #DC2626; "
                "background: transparent;"
            )

            datos.addWidget(motivo)

        layout.addLayout(datos, 1)

        texto, color = {
            "pendiente": ("PENDIENTE", "#D97706"),
            "aprobada": ("ACEPTADA", "#059669"),
            "rechazada": ("RECHAZADA", "#DC2626")
        }[r["estado"]]

        layout.addWidget(
            crear_chip(texto, color),
            alignment=Qt.AlignmentFlag.AlignVCenter
        )

        if r["estado"] == "pendiente":

            aceptar = boton_accion("Aceptar", "#059669")

            rechazar = boton_accion("Rechazar", "#DC2626")

            aceptar.clicked.connect(
                lambda checked=False, i=r["id_solicitud_rol"]:
                self._resolver_solicitud_rol(i, True)
            )

            rechazar.clicked.connect(
                lambda checked=False, i=r["id_solicitud_rol"]:
                self._resolver_solicitud_rol(i, False)
            )

            layout.addWidget(
                aceptar,
                alignment=Qt.AlignmentFlag.AlignVCenter
            )

            layout.addWidget(
                rechazar,
                alignment=Qt.AlignmentFlag.AlignVCenter
            )

        return tarjeta

    def _resolver_solicitud_rol(self, id_solicitud_rol, aprobar):

        motivo = None

        if aprobar:

            respuesta = QMessageBox.question(
                self,
                "Aceptar permiso",
                "¿Dar permiso de arrendador a esta persona?\n\n"
                "Podrá publicar propiedades la próxima vez "
                "que inicie sesión.",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if respuesta != QMessageBox.StandardButton.Yes:
                return

        else:

            texto, aceptado = QInputDialog.getText(
                self,
                "Rechazar permiso",
                "Motivo del rechazo (opcional):"
            )

            if not aceptado:
                return

            motivo = texto.strip() or None

        if not dao.resolver_solicitud_rol(
            id_solicitud_rol, aprobar, self.id_usuario, motivo
        ):

            QMessageBox.critical(
                self,
                "Error",
                dao.ultimo_error_mensaje
                or "No fue posible actualizar la solicitud."
            )

            return

        self.mostrar_solicitudes_rol(self._solo_pendientes_rol)

    def mostrar_usuarios(self, rol):

        self._preparar_pagina()

        usuarios = dao.obtener_usuarios_por_rol(rol)

        nombre_rol = (
            "Estudiantes" if rol == "estudiante"
            else "Arrendadores"
        )

        self.grid.addWidget(
            self._titulo_pagina(
                f"{nombre_rol} registrados",
                f"{len(usuarios)} cuenta(s) en total."
            ),
            0, 0, 1, 3
        )

        fila = 1

        if not usuarios:

            vacio = QLabel(
                "Todavía no hay cuentas de este tipo."
            )

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; "
                "padding: 20px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        for u in usuarios:

            tarjeta = crear_tarjeta()

            layout = QHBoxLayout(tarjeta)

            layout.setContentsMargins(18, 14, 18, 14)

            layout.setSpacing(14)

            avatar = QLabel(u["usuario"][:1].upper())

            avatar.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            avatar.setFixedSize(42, 42)

            avatar.setStyleSheet(f"""
                background: {
                    u.get('color_interfaz')
                    or COLOR_DEFECTO.get(rol, '#1E3A8A')
                };
                color: white;
                border-radius: 21px;
                font-size: 18px;
                font-weight: bold;
            """)

            layout.addWidget(avatar)

            columna = QVBoxLayout()

            columna.setSpacing(0)

            nombre = QLabel(u["nombre"])

            nombre.setStyleSheet(
                "font-size: 14px; font-weight: bold;"
            )

            usuario = QLabel(f"@{u['usuario']}")

            usuario.setStyleSheet(
                "font-size: 12px; color: #6B7280;"
            )

            columna.addWidget(nombre)

            columna.addWidget(usuario)

            if rol == "arrendador":
                detalle_rol = (
                    f"🏠 {u.get('n_propiedades', 0)} propiedad(es)"
                )
            else:
                detalle_rol = (
                    f"💬 {u.get('n_comentarios', 0)} comentario(s)"
                    f"  ·  ♡ {u.get('n_favoritos', 0)} favorito(s)"
                )

            resumen_rol = QLabel(detalle_rol)

            resumen_rol.setStyleSheet(
                "font-size: 11px; color: #9CA3AF;"
            )

            columna.addWidget(resumen_rol)

            layout.addLayout(columna, 1)

            if rol == "arrendador":

                estado = u.get("verificacion")

                if estado in ESTADOS_VERIFICACION:
                    texto, color = ESTADOS_VERIFICACION[estado]
                else:
                    texto, color = "Sin aprobar", "#6B7280"

                layout.addWidget(crear_chip(texto, color))

                ver = boton_accion("Ver propiedades", "#475569")

                ver.clicked.connect(
                    lambda checked=False, d=u:
                    self.mostrar_propiedades_admin(
                        d["id_usuario"], d["nombre"]
                    )
                )

                layout.addWidget(ver)

            activo = bool(u["activo"])

            layout.addWidget(
                crear_chip(
                    "Activo" if activo else "Inactivo",
                    "#059669" if activo else "#DC2626"
                )
            )

            boton = boton_accion(
                "Desactivar" if activo else "Activar",
                "#DC2626" if activo else "#059669"
            )

            boton.clicked.connect(
                lambda checked=False,
                i=u["id_usuario"],
                a=activo,
                r=rol:
                self._cambiar_estado_usuario(i, not a, r)
            )

            layout.addWidget(boton)

            self.grid.addWidget(tarjeta, fila, 0, 1, 3)

            fila += 1

        self._fin_pagina(fila)

    def mostrar_cambios_propiedades(self):
        """Cambios que los arrendadores hicieron a propiedades ya
        publicadas y que esperan aprobación."""

        self._preparar_pagina()

        cambios = dao.obtener_ediciones_pendientes()

        self.grid.addWidget(
            self._titulo_pagina(
                "Cambios de propiedades",
                f"{len(cambios)} cambio(s) esperando revisión. "
                "Los estudiantes siguen viendo la versión "
                "publicada hasta que apruebes."
            ),
            0, 0, 1, 3
        )

        fila = 1

        if not cambios:

            vacio = QLabel("No hay cambios pendientes.")

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; padding: 20px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        etiquetas = [
            ("titulo", "Título"),
            ("direccion", "Dirección"),
            ("precio", "Precio"),
            ("distancia", "Distancia"),
            ("habitaciones", "Habitaciones"),
            ("banos", "Baños"),
            ("descripcion", "Descripción")
        ]

        for c in cambios:

            tarjeta = crear_tarjeta()

            layout = QVBoxLayout(tarjeta)

            layout.setContentsMargins(22, 18, 22, 18)

            layout.setSpacing(6)

            titulo = QLabel(
                f"{c['titulo_actual']}  ·  de {c['nombre']} "
                f"(@{c['usuario']})"
            )

            titulo.setWordWrap(True)

            titulo.setStyleSheet(
                "font-size: 15px; font-weight: bold; "
                "color: #1E3A8A;"
            )

            layout.addWidget(titulo)

            nuevo = c["cambios"]

            lineas = []

            for campo, nombre_campo in etiquetas:

                antes = c.get(
                    "direccion_actual" if campo == "direccion"
                    else f"{campo}_actual"
                )

                despues = nuevo.get(campo)

                if campo == "direccion":
                    antes = antes or c.get("zona_actual")

                if campo == "precio":

                    try:
                        antes = f"C$ {float(antes):,.0f}"
                        despues = f"C$ {float(despues):,.0f}"
                    except (TypeError, ValueError):
                        pass

                if str(antes or "") != str(despues or ""):

                    lineas.append(
                        f"• {nombre_campo}: "
                        f"«{antes or '—'}» → «{despues or '—'}»"
                    )

            if c["fotos_nuevas"]:
                lineas.append(
                    f"• Fotos nuevas: {len(c['fotos_nuevas'])}"
                )

            if c["fotos_quitadas"]:
                lineas.append(
                    f"• Fotos que se quitan: {c['fotos_quitadas']}"
                )

            if not lineas:
                lineas.append(
                    "• Cambios menores (tipo, universidad o "
                    "servicios)."
                )

            detalle = QLabel("\n".join(lineas))

            detalle.setWordWrap(True)

            detalle.setStyleSheet(
                "font-size: 13px; color: #374151;"
            )

            layout.addWidget(detalle)

            if c["fotos_nuevas"]:

                tira = QHBoxLayout()

                tira.setSpacing(8)

                for datos_foto in c["fotos_nuevas"][:6]:

                    tira.addWidget(
                        crear_miniatura(
                            datos_foto, 120, 80, llenar=True
                        )
                    )

                tira.addStretch()

                layout.addLayout(tira)

            botones = QHBoxLayout()

            aprobar = boton_accion("Aprobar cambios", "#059669")

            rechazar = boton_accion("Rechazar", "#DC2626")

            aprobar.clicked.connect(
                lambda checked=False, i=c["id_edicion"]:
                self._resolver_cambio(i, True)
            )

            rechazar.clicked.connect(
                lambda checked=False, i=c["id_edicion"]:
                self._resolver_cambio(i, False)
            )

            botones.addWidget(aprobar)
            botones.addWidget(rechazar)
            botones.addStretch()

            layout.addLayout(botones)

            self.grid.addWidget(tarjeta, fila, 0, 1, 3)

            fila += 1

        self._fin_pagina(fila)

    def _resolver_cambio(self, id_edicion, aprobar):

        if not aprobar:

            respuesta = QMessageBox.question(
                self,
                "Rechazar cambios",
                "Se descartarán los cambios y las fotos nuevas. "
                "¿Continuar?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
            )

            if respuesta != QMessageBox.StandardButton.Yes:
                return

        if not dao.resolver_edicion(
            id_edicion, aprobar, self.id_usuario
        ):

            QMessageBox.critical(
                self,
                "Error",
                "No fue posible procesar los cambios."
            )

            return

        self.mostrar_cambios_propiedades()

    def mostrar_propiedades_admin(self, id_arrendador, nombre):
        """El administrador ve (y puede ocultar) las propiedades,
        fotos e información de un arrendador."""

        self._preparar_pagina()

        self._admin_arrendador = {
            "id_usuario": id_arrendador,
            "nombre": nombre
        }

        propiedades = dao.obtener_propiedades_arrendador(
            id_arrendador
        )

        self.grid.addWidget(
            self._titulo_pagina(
                f"Propiedades de {nombre}",
                f"{len(propiedades)} propiedad(es) registrada(s)."
            ),
            0, 0, 1, 3
        )

        volver = boton_accion(
            "← Volver a arrendadores",
            "#6B7280"
        )

        volver.clicked.connect(
            lambda: self.mostrar_usuarios("arrendador")
        )

        self.grid.addWidget(
            volver,
            1, 0,
            alignment=Qt.AlignmentFlag.AlignLeft
        )

        fila = 2

        if not propiedades:

            vacio = QLabel(
                "Este arrendador aún no tiene propiedades."
            )

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; padding: 20px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        for p in propiedades:

            self.grid.addWidget(
                self._tarjeta_propiedad_gestion(p, admin=True),
                fila, 0, 1, 3
            )

            fila += 1

        self._fin_pagina(fila)

    def _cambiar_estado_usuario(self, id_usuario, activar, rol):

        respuesta = QMessageBox.question(
            self,
            "Confirmar",
            "¿Deseas "
            + ("activar" if activar else "desactivar")
            + " esta cuenta?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        if not dao.cambiar_estado_usuario(
            id_usuario,
            activar,
            self.id_usuario
        ):

            QMessageBox.critical(
                self,
                "Error",
                "No fue posible cambiar el estado."
            )

            return

        self.mostrar_usuarios(rol)

    def mostrar_moderacion(self):

        self._preparar_pagina()

        comentarios = dao.obtener_comentarios()[:50]

        self.grid.addWidget(
            self._titulo_pagina(
                "Revisar comentarios",
                "Elimina comentarios inapropiados "
                "(se muestran los 50 más recientes)."
            ),
            0, 0, 1, 3
        )

        fila = 1

        if not comentarios:

            vacio = QLabel("No hay comentarios.")

            vacio.setStyleSheet(
                "color: #6B7280; font-size: 14px; "
                "padding: 20px;"
            )

            self.grid.addWidget(vacio, fila, 0, 1, 3)

            fila += 1

        for c in comentarios:

            tarjeta = crear_tarjeta()

            layout = QHBoxLayout(tarjeta)

            layout.setContentsMargins(18, 14, 18, 14)

            columna = QVBoxLayout()

            columna.setSpacing(4)

            estrellas = (
                "★" * int(c["calificacion"])
                if c.get("calificacion")
                else ""
            )

            cabecera = QLabel(
                f"{c['nombre']} (@{c['usuario']})  ·  "
                f"{c.get('titulo') or 'Comentario general'}"
                f"  {estrellas}"
            )

            cabecera.setStyleSheet(
                "font-size: 13px; font-weight: bold; "
                "color: #1E3A8A;"
            )

            texto = QLabel(c["comentario"])

            texto.setWordWrap(True)

            texto.setStyleSheet(
                "font-size: 13px; color: #374151;"
            )

            fecha = QLabel(
                str(c.get("fecha_comentario", ""))[:16]
            )

            fecha.setStyleSheet(
                "font-size: 11px; color: #9CA3AF;"
            )

            columna.addWidget(cabecera)

            columna.addWidget(texto)

            columna.addWidget(fecha)

            layout.addLayout(columna, 1)

            eliminar = boton_accion("Eliminar", "#DC2626")

            eliminar.clicked.connect(
                lambda checked=False, i=c["id_comentario"]:
                self._eliminar_comentario(i)
            )

            layout.addWidget(
                eliminar,
                alignment=Qt.AlignmentFlag.AlignTop
            )

            self.grid.addWidget(tarjeta, fila, 0, 1, 3)

            fila += 1

        self._fin_pagina(fila)

    def _eliminar_comentario(self, id_comentario):

        respuesta = QMessageBox.question(
            self,
            "Eliminar comentario",
            "¿Eliminar este comentario definitivamente?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if respuesta != QMessageBox.StandardButton.Yes:
            return

        dao.eliminar_comentario(id_comentario, self.id_usuario)

        self.mostrar_moderacion()

    # ------------------------------------------------------------
    # Configuración de la interfaz (todos los roles)
    # ------------------------------------------------------------

    def mostrar_configuracion(self):

        self._preparar_pagina()

        self.grid.addWidget(
            self._titulo_pagina(
                "Configuración",
                "Cambia el color de tu pantalla. Se guarda "
                "y se usa cada vez que entras."
            ),
            0, 0, 1, 3
        )

        tarjeta = crear_tarjeta()

        layout = QVBoxLayout(tarjeta)

        layout.setContentsMargins(28, 24, 28, 24)

        layout.setSpacing(12)

        titulo = QLabel("Color de la pantalla")

        titulo.setStyleSheet(
            "font-size: 16px; font-weight: bold;"
        )

        layout.addWidget(titulo)

        ayuda = QLabel(
            "Este color identifica tu cuenta: barra lateral, "
            "encabezado y botones principales."
        )

        ayuda.setWordWrap(True)

        ayuda.setStyleSheet(
            "font-size: 13px; color: #6B7280;"
        )

        layout.addWidget(ayuda)

        fila = QHBoxLayout()

        fila.setSpacing(10)

        actual = QColor(self.color_interfaz).name()

        for nombre, valor in PALETA_COLORES:

            muestra = QPushButton()

            muestra.setFixedSize(44, 44)

            muestra.setToolTip(nombre)

            muestra.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            borde = (
                "4px solid #111827"
                if QColor(valor).name() == actual
                else "2px solid #E5E7EB"
            )

            muestra.setStyleSheet(f"""
                QPushButton {{
                    background: {valor};
                    border: {borde};
                    border-radius: 22px;
                }}
            """)

            muestra.clicked.connect(
                lambda checked=False, v=valor:
                self._cambiar_color(v)
            )

            fila.addWidget(muestra)

        fila.addStretch()

        layout.addLayout(fila)

        acciones = QHBoxLayout()

        personalizado = boton_accion(
            "Color personalizado...",
            "#475569"
        )

        personalizado.clicked.connect(
            self._elegir_color_personalizado
        )

        restablecer = boton_accion(
            "Restablecer color de mi rol",
            "#6B7280"
        )

        restablecer.clicked.connect(
            lambda: self._cambiar_color(
                COLOR_DEFECTO.get(self.rol, "#1E3A8A")
            )
        )

        acciones.addWidget(personalizado)

        acciones.addWidget(restablecer)

        acciones.addStretch()

        layout.addLayout(acciones)

        self.grid.addWidget(tarjeta, 1, 0, 1, 3)

        info = crear_tarjeta()

        info_layout = QVBoxLayout(info)

        info_layout.setContentsMargins(28, 20, 28, 20)

        opciones_rol = {
            "administrador": (
                "Opciones de administrador: solicitudes, "
                "estudiantes, arrendadores (con sus propiedades) "
                "y revisión de comentarios."
            ),
            "arrendador": (
                "Opciones de arrendador: solicitudes y "
                "propiedades con fotos, dirección y datos."
            ),
            "estudiante": (
                "Opciones de estudiante: inicio (con búsqueda), "
                "favoritos y comentarios."
            )
        }

        datos = QLabel(
            f"Cuenta: @{self.usuario}   ·   "
            f"Rol: {ROLES.get(self.rol, 'Estudiante')}\n"
            + opciones_rol.get(self.rol, "")
        )

        datos.setWordWrap(True)

        datos.setStyleSheet(
            "font-size: 13px; color: #374151;"
        )

        info_layout.addWidget(datos)

        self.grid.addWidget(info, 2, 0, 1, 3)

        self._fin_pagina(3)

    def _elegir_color_personalizado(self):

        dialogo = QColorDialog(QColor(self.color_interfaz), self)

        dialogo.setWindowTitle("Elige el color de tu pantalla")

        dialogo.setOption(
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
            True
        )

        # Estilo propio: texto oscuro y campos blancos, bien visibles.
        dialogo.setStyleSheet(ESTILO_DIALOGO)

        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return

        color = dialogo.currentColor()

        if color.isValid():
            self._cambiar_color(color.name())

    def _cambiar_color(self, valor):

        color = QColor(valor)

        if not color.isValid():
            return

        if color.lightness() > 150:

            QMessageBox.warning(
                self,
                "Color muy claro",
                "Elige un color más oscuro para que "
                "el texto se lea bien."
            )

            return

        self.color_interfaz = color.name()

        if not dao.guardar_color_interfaz(
            self.id_usuario,
            self.color_interfaz
        ):

            QMessageBox.warning(
                self,
                "Color no guardado",
                "El color se aplicó, pero no se pudo "
                "guardar en la base de datos."
            )

        self.aplicar_color_interfaz()

        self.mostrar_configuracion()

    def _solicitar_arrendador_otra_vez(self):

        if not dao.crear_solicitud_rol(self.id_usuario):

            QMessageBox.warning(
                self,
                "No se pudo enviar",
                dao.ultimo_error_mensaje
                or "No fue posible enviar la solicitud."
            )

            return

        QMessageBox.information(
            self,
            "Solicitud enviada",
            "Un administrador revisará tu solicitud."
        )

        self.mostrar_perfil()

    def _info_perfil_rol(self):

        if self.rol == "administrador":

            texto = (
                "Tienes acceso a la administración de "
                "estudiantes, arrendadores, solicitudes "
                "y comentarios."
            )

        else:

            solicitud = self._solicitud_actual()

            estado = solicitud["estado"] if solicitud else None

            texto = {
                None: "Aún no has enviado tu solicitud de "
                      "propiedad.",
                "pendiente": "Tu solicitud "
                             "está en revisión.",
                "aprobada": "Tu propiedad está aprobada.",
                "rechazada": "Tu última solicitud fue "
                             "rechazada. Puedes enviar otra."
            }[estado]

        etiqueta = QLabel(texto)

        etiqueta.setWordWrap(True)

        etiqueta.setStyleSheet(
            "color: #374151; background: #F9FAFB; "
            "border-radius: 8px; padding: 14px; "
            "font-size: 13px;"
        )

        return etiqueta

    def cerrar_sesion(self):

        respuesta = QMessageBox.question(
            self,
            "Cerrar sesión",
            "¿Seguro que deseas cerrar sesión?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
        )

        if (
            respuesta
            == QMessageBox.StandardButton.Yes
        ):

            self.login = Login()

            self.login.show()

            self.close()

    def centrar_ventana(self):

        pantalla = (
            self.screen()
            .availableGeometry()
        )

        x = (
            pantalla.width()
            - self.width()
        ) // 2

        y = (
            pantalla.height()
            - self.height()
        ) // 2

        self.move(
            x,
            y
        )


class Login(QWidget):

    def __init__(self):

        super().__init__()

        self.setWindowTitle(
            "Unihogar - Iniciar sesión"
        )

        self.setFixedSize(
            900,
            550
        )

        self.setStyleSheet("""
            QWidget {
                background: #EEF2F9;
                font-family: "Segoe UI", Arial, sans-serif;
            }

            QFrame#panel {
                background: white;
                border-radius: 18px;
            }

            QLabel#titulo {
                font-size: 28px;
                font-weight: bold;
                color: #1E3A8A;
            }

            QLabel#tituloForm {
                font-size: 22px;
                font-weight: bold;
                color: #1E3A8A;
            }

            QLabel#subtitulo {
                color: #6B7280;
                font-size: 14px;
            }

            QLineEdit {
                padding: 8px 12px;
                min-height: 22px;
                border: 2px solid #D1D5DB;
                border-radius: 8px;
                font-size: 14px;
                background: #FFFFFF;
                color: #111827;
            }

            QPushButton#ingresar {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 15px;
                font-weight: bold;
            }

            QPushButton#registrarse {
                background: transparent;
                color: #2563EB;
                border: none;
                font-size: 13px;
                font-weight: bold;
                padding: 8px;
            }

            QMessageBox {
                background: white;
                color: #111827;
            }

            QMessageBox QLabel {
                color: #111827;
                background: transparent;
            }

            QMessageBox QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                padding: 7px 18px;
            }
        """)

        principal = QHBoxLayout(
            self
        )

        principal.setContentsMargins(
            50,
            40,
            50,
            40
        )

        principal.setSpacing(
            40
        )

        izquierda = QVBoxLayout()

        izquierda.addStretch()

        titulo = QLabel(
            "Unihogar"
        )

        titulo.setObjectName(
            "titulo"
        )

        izquierda.addWidget(
            titulo
        )

        descripcion = QLabel(
            "Encuentra alquileres accesibles\n"
            "para estudiantes universitarios."
        )

        descripcion.setObjectName(
            "subtitulo"
        )

        izquierda.addWidget(
            descripcion
        )

        izquierda.addStretch()

        panel = QFrame()

        panel.setObjectName(
            "panel"
        )

        panel.setFixedWidth(
            350
        )

        login = QVBoxLayout(
            panel
        )

        login.setContentsMargins(
            35,
            35,
            35,
            35
        )

        bienvenida = QLabel(
            "Iniciar Sesión"
        )

        bienvenida.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        bienvenida.setObjectName(
            "tituloForm"
        )

        login.addWidget(
            bienvenida
        )

        login.addSpacing(
            15
        )

        etiqueta_rol = QLabel(
            "Ingresar como"
        )

        etiqueta_rol.setStyleSheet(
            "color: #374151; font-size: 13px; "
            "font-weight: bold;"
        )

        login.addWidget(
            etiqueta_rol
        )

        fila_roles = QHBoxLayout()

        fila_roles.setSpacing(6)

        self.grupo_rol = QButtonGroup(
            self
        )

        self.grupo_rol.setExclusive(
            True
        )

        for clave, texto in ROLES.items():

            boton_rol = QPushButton(
                texto
            )

            boton_rol.setCheckable(
                True
            )

            boton_rol.setProperty(
                "rol",
                clave
            )

            boton_rol.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            boton_rol.setStyleSheet(f"""
                QPushButton {{
                    background: #F3F4F6;
                    color: #374151;
                    border: 2px solid #D1D5DB;
                    border-radius: 8px;
                    padding: 7px 2px;
                    font-size: 12px;
                    font-weight: bold;
                }}
                QPushButton:checked {{
                    background: {COLORES_ROL[clave]};
                    color: white;
                    border: 2px solid {COLORES_ROL[clave]};
                }}
            """)

            if clave == "estudiante":
                boton_rol.setChecked(True)

            self.grupo_rol.addButton(
                boton_rol
            )

            fila_roles.addWidget(
                boton_rol
            )

        login.addLayout(
            fila_roles
        )

        login.addSpacing(
            12
        )

        self.usuario = QLineEdit()

        self.usuario.setPlaceholderText(
            "Usuario"
        )

        login.addWidget(
            self.usuario
        )

        self.contrasena = QLineEdit()

        self.contrasena.setPlaceholderText(
            "Contraseña"
        )

        self.contrasena.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.contrasena.returnPressed.connect(
            self.verificar_login
        )

        login.addWidget(
            self.contrasena
        )

        login.addSpacing(
            20
        )

        boton = QPushButton(
            "Ingresar"
        )

        boton.setObjectName(
            "ingresar"
        )

        boton.clicked.connect(
            self.verificar_login
        )

        login.addWidget(
            boton
        )

        boton_registro = QPushButton(
            "¿No tienes una cuenta? Regístrate"
        )

        boton_registro.setObjectName(
            "registrarse"
        )

        boton_registro.clicked.connect(
            self.abrir_registro
        )

        login.addWidget(
            boton_registro
        )

        principal.addLayout(
            izquierda,
            2
        )

        principal.addWidget(
            panel,
            1
        )

        self.centrar_ventana()

    def verificar_login(self):

        usuario = (
            self.usuario.text()
            .strip()
        )

        contrasena = (
            self.contrasena.text()
        )

        if not usuario or not contrasena:

            QMessageBox.warning(
                self,
                "Campos incompletos",
                "Por favor completa usuario y contraseña."
            )

            return

        ahora = time.time()

        bloqueado_hasta = getattr(self, "_bloqueado_hasta", 0)

        if ahora < bloqueado_hasta:

            QMessageBox.warning(
                self,
                "Espera un momento",
                "Hiciste muchos intentos. Prueba de nuevo en "
                f"{int(bloqueado_hasta - ahora) + 1} segundos."
            )

            return

        datos = dao.obtener_usuario(usuario)

        correcto = bool(datos) and dao.verificar_contrasena(
            contrasena,
            datos["contrasena"]
        )

        if not correcto:

            self._intentos_fallidos = getattr(
                self, "_intentos_fallidos", 0
            ) + 1

            if self._intentos_fallidos >= 5:
                self._bloqueado_hasta = time.time() + 30
                self._intentos_fallidos = 0

            # Mismo mensaje para usuario o contraseña mal escritos:
            # así no se puede adivinar qué usuarios existen.
            QMessageBox.warning(
                self,
                "Datos incorrectos",
                "Usuario o contraseña incorrectos."
            )

            return

        self._intentos_fallidos = 0

        if not str(datos["contrasena"]).startswith(
            ("$2a$", "$2b$", "$2y$")
        ):
            dao.actualizar_hash_contrasena(
                datos["id_usuario"], contrasena
            )

        rol_real = datos.get(
            "rol"
        ) or "estudiante"

        rol_elegido = (
            self.grupo_rol.checkedButton()
            .property("rol")
        )

        if rol_real != rol_elegido:

            QMessageBox.warning(
                self,
                "Rol incorrecto",
                "Esta cuenta no está registrada como "
                f"{ROLES[rol_elegido]}.\n"
                "Selecciona el rol correcto para ingresar."
            )

            return

        self.principal = PaginaPrincipal(
            datos["id_usuario"],
            datos["usuario"],
            datos["nombre"],
            rol_real
        )

        self.principal.show()

        self.close()

    def abrir_registro(self):

        self.registro = Registro(
            self
        )

        self.registro.show()

        self.hide()

    def centrar_ventana(self):

        pantalla = (
            self.screen()
            .availableGeometry()
        )

        x = (
            pantalla.width()
            - self.width()
        ) // 2

        y = (
            pantalla.height()
            - self.height()
        ) // 2

        self.move(
            x,
            y
        )


class Registro(QWidget):

    def __init__(
        self,
        login
    ):

        super().__init__()

        self.login = login

        self.setWindowTitle(
            "Crear cuenta - Unihogar"
        )

        self.setFixedSize(
            500,
            700
        )

        self.setStyleSheet("""
            QWidget {
                background: #EEF2F9;
                font-family: "Segoe UI", Arial, sans-serif;
            }

            QFrame#panelRegistro {
                background: white;
                border-radius: 18px;
            }

            QLabel#tituloRegistro {
                font-size: 25px;
                font-weight: bold;
                color: #1E3A8A;
            }

            QLabel#subtituloRegistro {
                color: #6B7280;
                font-size: 13px;
            }

            QLabel#etiqueta {
                color: #374151;
                font-size: 13px;
                font-weight: bold;
            }

            QLineEdit {
                padding: 8px 12px;
                min-height: 22px;
                border: 2px solid #D1D5DB;
                border-radius: 8px;
                font-size: 14px;
                background: #FFFFFF;
                color: #111827;
            }

            QPushButton#crearCuenta {
                background: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px;
                font-size: 14px;
                font-weight: bold;
            }

            QPushButton#volver {
                background: transparent;
                color: #2563EB;
                border: none;
                font-size: 13px;
                font-weight: bold;
            }

            QMessageBox {
                background: white;
                color: #111827;
            }

            QMessageBox QLabel {
                color: #111827;
                background: transparent;
            }

            QMessageBox QPushButton {
                background: #2563EB;
                color: white;
                border: none;
                padding: 7px 18px;
            }
        """)

        panel = QFrame()

        panel.setObjectName(
            "panelRegistro"
        )

        layout_principal = QVBoxLayout(
            self
        )

        layout_principal.setContentsMargins(
            40,
            35,
            40,
            35
        )

        layout_principal.addWidget(
            panel
        )

        formulario = QVBoxLayout(
            panel
        )

        formulario.setContentsMargins(
            35,
            30,
            35,
            30
        )

        titulo = QLabel(
            "Crear una cuenta"
        )

        titulo.setObjectName(
            "tituloRegistro"
        )

        titulo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        formulario.addWidget(
            titulo
        )

        subtitulo = QLabel(
            "Regístrate para comenzar "
            "a buscar alquileres."
        )

        subtitulo.setObjectName(
            "subtituloRegistro"
        )

        subtitulo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        formulario.addWidget(
            subtitulo
        )

        formulario.addSpacing(
            15
        )

        etiqueta_nombre = QLabel(
            "Nombre completo"
        )

        etiqueta_nombre.setObjectName(
            "etiqueta"
        )

        self.nombre = QLineEdit()

        self.nombre.setPlaceholderText(
            "Ejemplo: Juan Pérez"
        )

        formulario.addWidget(
            etiqueta_nombre
        )

        formulario.addWidget(
            self.nombre
        )

        etiqueta_usuario = QLabel(
            "Usuario"
        )

        etiqueta_usuario.setObjectName(
            "etiqueta"
        )

        self.usuario = QLineEdit()

        self.usuario.setPlaceholderText(
            "Crea tu nombre de usuario"
        )

        formulario.addWidget(
            etiqueta_usuario
        )

        formulario.addWidget(
            self.usuario
        )

        etiqueta_contrasena = QLabel(
            "Contraseña"
        )

        etiqueta_contrasena.setObjectName(
            "etiqueta"
        )

        self.contrasena = QLineEdit()

        self.contrasena.setPlaceholderText(
            "Crea una contraseña"
        )

        self.contrasena.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        formulario.addWidget(
            etiqueta_contrasena
        )

        formulario.addWidget(
            self.contrasena
        )

        etiqueta_confirmar = QLabel(
            "Confirmar contraseña"
        )

        etiqueta_confirmar.setObjectName(
            "etiqueta"
        )

        self.confirmar = QLineEdit()

        self.confirmar.setPlaceholderText(
            "Repite tu contraseña"
        )

        self.confirmar.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.confirmar.returnPressed.connect(
            self.registrar_usuario
        )

        formulario.addWidget(
            etiqueta_confirmar
        )

        formulario.addWidget(
            self.confirmar
        )

        etiqueta_rol = QLabel(
            "Tipo de cuenta"
        )

        etiqueta_rol.setObjectName(
            "etiqueta"
        )

        self.rol = QComboBox()

        self.rol.addItem(
            "Estudiante",
            "estudiante"
        )

        self.rol.addItem(
            "Arrendador (requiere aprobación del administrador)",
            "arrendador"
        )

        self.rol.setStyleSheet(
            "padding: 8px 12px; border: 2px solid #D1D5DB; "
            "border-radius: 8px; font-size: 14px; "
            "background: white; color: #111827;"
        )

        formulario.addWidget(
            etiqueta_rol
        )

        formulario.addWidget(
            self.rol
        )

        formulario.addSpacing(
            15
        )

        boton_crear = QPushButton(
            "Crear cuenta"
        )

        boton_crear.setObjectName(
            "crearCuenta"
        )

        boton_crear.clicked.connect(
            self.registrar_usuario
        )

        formulario.addWidget(
            boton_crear
        )

        boton_volver = QPushButton(
            "← Volver al inicio de sesión"
        )

        boton_volver.setObjectName(
            "volver"
        )

        boton_volver.clicked.connect(
            self.volver_login
        )

        formulario.addWidget(
            boton_volver
        )

        self.centrar_ventana()

    def registrar_usuario(self):

        nombre = (
            self.nombre.text()
            .strip()
        )

        usuario = (
            self.usuario.text()
            .strip()
        )

        contrasena = (
            self.contrasena.text()
        )

        confirmar = (
            self.confirmar.text()
        )

        if (
            not nombre
            or not usuario
            or not contrasena
            or not confirmar
        ):

            QMessageBox.warning(
                self,
                "Campos incompletos",
                "Por favor completa todos los campos."
            )

            return

        nombre, error = val.validar_nombre(nombre)

        if error:

            QMessageBox.warning(self, "Nombre inválido", error)

            return

        usuario, error = val.validar_usuario(usuario)

        if error:

            QMessageBox.warning(self, "Usuario inválido", error)

            return

        _, error = val.validar_contrasena(contrasena)

        if error:

            QMessageBox.warning(self, "Contraseña inválida", error)

            return

        if contrasena != confirmar:

            QMessageBox.warning(
                self,
                "Contraseñas diferentes",
                "Las contraseñas no coinciden."
            )

            return

        # También cuenta si ese usuario está desactivado.
        if dao.existe_usuario(usuario):

            QMessageBox.warning(
                self,
                "Usuario existente",
                "Ese usuario ya está registrado."
            )

            return

        resultado = dao.registrar_usuario(
            nombre,
            usuario,
            contrasena,
            self.rol.currentData()
        )

        if not resultado:

            QMessageBox.critical(
                self,
                "Error",
                dao.ultimo_error_mensaje
                or "No fue posible crear la cuenta."
            )

            return

        if self.rol.currentData() == "arrendador":

            QMessageBox.information(
                self,
                "Solicitud enviada",
                f"¡Cuenta creada, {nombre}!\n\n"
                "Tu solicitud para ser arrendador fue enviada al "
                "administrador. Mientras la revisa puedes entrar "
                "como estudiante; si la acepta, la próxima vez "
                "que inicies sesión tendrás el rol de arrendador."
            )

        else:

            QMessageBox.information(
                self,
                "Registro exitoso",
                f"¡Cuenta creada correctamente, {nombre}!"
            )

        self.login.usuario.setText(
            usuario
        )

        self.login.contrasena.clear()

        self.login.show()

        self.close()

    def volver_login(self):

        self.login.show()

        self.close()

    def centrar_ventana(self):

        pantalla = (
            self.screen()
            .availableGeometry()
        )

        x = (
            pantalla.width()
            - self.width()
        ) // 2

        y = (
            pantalla.height()
            - self.height()
        ) // 2

        self.move(
            x,
            y
        )


if __name__ == "__main__":

    app = QApplication(
        sys.argv
    )

    app.setStyle(
        "Fusion"
    )

    ventana = Login()

    ventana.show()

    sys.exit(
        app.exec()
    )
