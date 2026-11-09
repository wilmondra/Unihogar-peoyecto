"""Reporte en PDF para el administrador.

Solo genera el archivo a partir de los datos que entrega
dao.obtener_reporte_admin(). No toca la base de datos.
Requiere:  pip install reportlab
"""

from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

AZUL = colors.HexColor("#2563EB")
VERDE = colors.HexColor("#059669")
AMBAR = colors.HexColor("#D97706")
GRIS = colors.HexColor("#6B7280")
FONDO = colors.HexColor("#F3F4F6")


def _tabla(filas, anchos, extra=()):
    tabla = Table(filas, colWidths=anchos)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#D1D5DB")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        *extra,
    ]))
    return tabla


def generar_reporte_admin(ruta, datos, nombre_admin=""):
    """Crea el PDF en 'ruta'. 'datos' viene de obtener_reporte_admin."""

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "t", parent=estilos["Title"], textColor=AZUL, fontSize=22
    )
    h2 = ParagraphStyle(
        "h2", parent=estilos["Heading2"], textColor=colors.HexColor("#111827")
    )
    normal = ParagraphStyle("n", parent=estilos["Normal"], fontSize=10)
    pequeno = ParagraphStyle(
        "p", parent=normal, textColor=GRIS, fontSize=9
    )

    doc = SimpleDocTemplate(
        ruta, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm,
        title="Reporte de administrador - UniHogar",
    )

    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    historia = [
        Paragraph("UniHogar - Reporte de administrador", titulo),
        Paragraph(
            f"Generado el {fecha}"
            + (f" por {escape(nombre_admin)}" if nombre_admin else ""),
            pequeno,
        ),
        Spacer(1, 14),
        Paragraph("1. Usuarios registrados", h2),
    ]

    historia.append(_tabla(
        [
            ["Tipo de usuario", "Cantidad"],
            ["Estudiantes", str(datos["estudiantes"])],
            ["Arrendadores", str(datos["arrendadores"])],
            ["Total", str(datos["estudiantes"] + datos["arrendadores"])],
        ],
        [10 * cm, 4 * cm],
        extra=(
            ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
            ("BACKGROUND", (0, 3), (-1, 3), FONDO),
        ),
    ))

    historia += [
        Spacer(1, 16),
        Paragraph("2. Propiedades por arrendador", h2),
        Paragraph(
            "<b>Aprobadas</b>: propiedades ya publicadas. "
            "<b>Pendientes</b>: solicitudes que esperan revisión.",
            pequeno,
        ),
        Spacer(1, 8),
    ]

    total_aprobadas = 0
    total_pendientes = 0

    if not datos["arrendadores_detalle"]:
        historia.append(Paragraph("No hay arrendadores registrados.", normal))

    for a in datos["arrendadores_detalle"]:
        nombre = escape(f"{a['nombre']} (@{a['usuario']})")
        if not a["activo"]:
            nombre += " - desactivado"

        filas = [["Tipo de propiedad", "Aprobadas", "Pendientes"]]
        suma_a = suma_p = 0

        for tipo, (ap, pe) in sorted(a["tipos"].items()):
            filas.append([tipo, str(ap), str(pe)])
            suma_a += ap
            suma_p += pe

        if len(filas) == 1:
            filas.append(["Sin propiedades", "0", "0"])
        else:
            filas.append(["Total", str(suma_a), str(suma_p)])

        total_aprobadas += suma_a
        total_pendientes += suma_p

        ultima = len(filas) - 1
        historia.append(KeepTogether([
            Paragraph(f"<b>{nombre}</b>", normal),
            Spacer(1, 3),
            _tabla(
                filas, [8 * cm, 3.5 * cm, 3.5 * cm],
                extra=(
                    ("TEXTCOLOR", (1, 1), (1, -1), VERDE),
                    ("TEXTCOLOR", (2, 1), (2, -1), AMBAR),
                    ("FONTNAME", (0, ultima), (-1, ultima), "Helvetica-Bold"),
                    ("BACKGROUND", (0, ultima), (-1, ultima), FONDO),
                ),
            ),
            Spacer(1, 12),
        ]))

    historia += [
        Spacer(1, 6),
        Paragraph("3. Totales generales de propiedades", h2),
        _tabla(
            [
                ["Estado", "Cantidad"],
                ["Aprobadas", str(total_aprobadas)],
                ["Pendientes", str(total_pendientes)],
            ],
            [10 * cm, 4 * cm],
            extra=(
                ("TEXTCOLOR", (1, 1), (1, 1), VERDE),
                ("TEXTCOLOR", (1, 2), (1, 2), AMBAR),
            ),
        ),
    ]

    def pie(canvas, documento):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GRIS)
        canvas.drawString(2 * cm, 1.2 * cm, "UniHogar - uso interno del administrador")
        canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"Página {documento.page}")
        canvas.restoreState()

    doc.build(historia, onFirstPage=pie, onLaterPages=pie)
    return ruta


def generar_reporte_admin_excel(ruta, datos, nombre_admin=""):
    """Crea el mismo reporte del administrador en Excel (.xlsx).

    Requiere:  pip install openpyxl
    """

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    relleno = PatternFill("solid", fgColor="2563EB")
    blanco = Font(bold=True, color="FFFFFF")
    negrita = Font(bold=True)

    def encabezado(hoja, columnas):
        hoja.append(columnas)
        for celda in hoja[hoja.max_row]:
            celda.fill = relleno
            celda.font = blanco
            celda.alignment = Alignment(horizontal="center")

    def ajustar(hoja):
        for col in hoja.columns:
            ancho = max(len(str(c.value or "")) for c in col)
            hoja.column_dimensions[
                get_column_letter(col[0].column)
            ].width = min(max(ancho + 3, 12), 50)

    libro = Workbook()

    # Hoja 1: usuarios
    h1 = libro.active
    h1.title = "Usuarios"
    h1.append(["UniHogar - Reporte de administrador"])
    h1["A1"].font = Font(bold=True, size=14)
    h1.append([
        "Generado el " + datetime.now().strftime("%d/%m/%Y %H:%M")
        + (f" por {nombre_admin}" if nombre_admin else "")
    ])
    h1.append([])
    encabezado(h1, ["Tipo de usuario", "Cantidad"])
    h1.append(["Estudiantes", datos["estudiantes"]])
    h1.append(["Arrendadores", datos["arrendadores"]])
    h1.append(["Total", "=SUM(B5:B6)"])
    for celda in h1[h1.max_row]:
        celda.font = negrita
    ajustar(h1)

    # Hoja 2: propiedades por arrendador
    h2 = libro.create_sheet("Propiedades")
    encabezado(h2, [
        "Arrendador", "Usuario", "Activo",
        "Tipo de propiedad", "Aprobadas", "Pendientes",
    ])
    for a in datos["arrendadores_detalle"]:
        tipos = sorted(a["tipos"].items())
        if not tipos:
            h2.append([
                a["nombre"], a["usuario"],
                "Sí" if a["activo"] else "No",
                "Sin propiedades", 0, 0,
            ])
        for tipo, (ap, pe) in tipos:
            h2.append([
                a["nombre"], a["usuario"],
                "Sí" if a["activo"] else "No",
                tipo, ap, pe,
            ])

    ultima = h2.max_row
    h2.append([
        "Total", "", "", "",
        f"=SUM(E2:E{ultima})", f"=SUM(F2:F{ultima})",
    ])
    for celda in h2[h2.max_row]:
        celda.font = negrita
    h2.freeze_panes = "A2"
    ajustar(h2)

    libro.save(ruta)
    return ruta
