"""Auditoría de integridad de la base de datos de UNIHOGAR.

Uso:
    python auditoria_integridad.py              (solo LEE y reporta)
    python auditoria_integridad.py --corregir   (aplica correcciones SEGURAS)

Por defecto no modifica nada. Con --corregir solo se arreglan
referencias rotas que no guardan información útil:
  * fotos, servicios, favoritos y ediciones que apuntan a una
    propiedad que ya no existe (se eliminan esas filas sueltas);
  * comentarios y mensajes que apuntan a una propiedad que ya no
    existe (se deja la propiedad en blanco; el comentario se conserva).
Todo lo demás (duplicados, dueños inexistentes, precios raros...)
SOLO se reporta: no se inventan ni se borran datos válidos.
Haz una copia de seguridad (mysqldump) antes de usar --corregir.
"""

import sys
from datetime import datetime

# (clave, descripción, SQL que cuenta los casos, SQL de corrección o None)
# Solo SQL estándar, para poder probarlo también con SQLite.
REVISIONES = [
    ("fotos_huerfanas",
     "Fotos de propiedades que ya no existen",
     "SELECT COUNT(*) FROM propiedad_fotos "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)",
     "DELETE FROM propiedad_fotos "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)"),

    ("servicios_huerfanos_propiedad",
     "Servicios asignados a propiedades que ya no existen",
     "SELECT COUNT(*) FROM propiedad_amenidad "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)",
     "DELETE FROM propiedad_amenidad "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)"),

    ("servicios_huerfanos_amenidad",
     "Servicios asignados que apuntan a una amenidad inexistente",
     "SELECT COUNT(*) FROM propiedad_amenidad "
     "WHERE id_amenidad NOT IN (SELECT id_amenidad FROM amenidades)",
     "DELETE FROM propiedad_amenidad "
     "WHERE id_amenidad NOT IN (SELECT id_amenidad FROM amenidades)"),

    ("favoritos_sin_propiedad",
     "Favoritos de propiedades que ya no existen",
     "SELECT COUNT(*) FROM favoritos "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)",
     "DELETE FROM favoritos "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)"),

    ("favoritos_sin_usuario",
     "Favoritos de usuarios que ya no existen",
     "SELECT COUNT(*) FROM favoritos "
     "WHERE id_usuario NOT IN (SELECT id_usuario FROM usuarios)",
     "DELETE FROM favoritos "
     "WHERE id_usuario NOT IN (SELECT id_usuario FROM usuarios)"),

    ("ediciones_huerfanas",
     "Ediciones pendientes de propiedades que ya no existen",
     "SELECT COUNT(*) FROM propiedad_ediciones "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)",
     "DELETE FROM propiedad_ediciones "
     "WHERE id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)"),

    ("comentarios_propiedad_rota",
     "Comentarios que apuntan a una propiedad inexistente",
     "SELECT COUNT(*) FROM comentarios WHERE id_propiedad IS NOT NULL "
     "AND id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)",
     "UPDATE comentarios SET id_propiedad = NULL "
     "WHERE id_propiedad IS NOT NULL "
     "AND id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)"),

    ("mensajes_propiedad_rota",
     "Mensajes que apuntan a una propiedad inexistente",
     "SELECT COUNT(*) FROM mensajes WHERE id_propiedad IS NOT NULL "
     "AND id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)",
     "UPDATE mensajes SET id_propiedad = NULL "
     "WHERE id_propiedad IS NOT NULL "
     "AND id_propiedad NOT IN (SELECT id_propiedad FROM propiedades)"),

    # ---- Solo se reportan (no hay una corrección segura) ----
    ("comentarios_sin_usuario",
     "Comentarios de usuarios que no existen",
     "SELECT COUNT(*) FROM comentarios "
     "WHERE id_usuario NOT IN (SELECT id_usuario FROM usuarios)", None),

    ("propiedades_dueno_inexistente",
     "Propiedades cuyo arrendador (id_arrendador) no existe",
     "SELECT COUNT(*) FROM propiedades WHERE id_arrendador IS NOT NULL "
     "AND id_arrendador NOT IN (SELECT id_usuario FROM usuarios)", None),

    ("propiedades_sin_arrendador",
     "Propiedades sin arrendador asignado (antiguas o de ejemplo)",
     "SELECT COUNT(*) FROM propiedades WHERE id_arrendador IS NULL",
     None),

    ("propiedades_tipo_inexistente",
     "Propiedades con un tipo que no existe",
     "SELECT COUNT(*) FROM propiedades "
     "WHERE id_tipo NOT IN (SELECT id_tipo FROM tipos_propiedad)", None),

    ("propiedades_universidad_inexistente",
     "Propiedades con una universidad que no existe",
     "SELECT COUNT(*) FROM propiedades WHERE id_universidad "
     "NOT IN (SELECT id_universidad FROM universidades)", None),

    ("propiedades_precio_invalido",
     "Propiedades con precio vacío o menor o igual a cero",
     "SELECT COUNT(*) FROM propiedades "
     "WHERE precio IS NULL OR precio <= 0", None),

    ("propiedades_solicitud_inexistente",
     "Propiedades que vienen de una solicitud que no existe",
     "SELECT COUNT(*) FROM propiedades WHERE id_solicitud IS NOT NULL "
     "AND id_solicitud NOT IN "
     "(SELECT id_solicitud FROM solicitudes_arrendador)", None),

    ("solicitudes_aprobadas_sin_propiedad",
     "Solicitudes aprobadas sin propiedad (puede ser normal si el "
     "arrendador la eliminó; no se republica automáticamente)",
     "SELECT COUNT(*) FROM solicitudes_arrendador s "
     "WHERE s.estado = 'aprobada' AND s.id_solicitud NOT IN "
     "(SELECT id_solicitud FROM propiedades "
     "WHERE id_solicitud IS NOT NULL)", None),

    ("duplicado_usuarios",
     "Nombres de usuario repetidos (sin distinguir mayúsculas)",
     "SELECT COUNT(*) FROM (SELECT 1 FROM usuarios "
     "GROUP BY LOWER(usuario) HAVING COUNT(*) > 1) d", None),

    ("duplicado_solicitud_propiedad",
     "Solicitudes publicadas más de una vez",
     "SELECT COUNT(*) FROM (SELECT 1 FROM propiedades "
     "WHERE id_solicitud IS NOT NULL "
     "GROUP BY id_solicitud HAVING COUNT(*) > 1) d", None),

    ("duplicado_favoritos",
     "Favoritos repetidos (mismo usuario y propiedad)",
     "SELECT COUNT(*) FROM (SELECT 1 FROM favoritos "
     "GROUP BY id_usuario, id_propiedad HAVING COUNT(*) > 1) d", None),

    ("duplicado_servicios",
     "Servicios repetidos en una misma propiedad",
     "SELECT COUNT(*) FROM (SELECT 1 FROM propiedad_amenidad "
     "GROUP BY id_propiedad, id_amenidad HAVING COUNT(*) > 1) d", None),

    ("solicitudes_pendientes_multiples",
     "Arrendadores con más de una solicitud pendiente",
     "SELECT COUNT(*) FROM (SELECT 1 FROM solicitudes_arrendador "
     "WHERE estado = 'pendiente' GROUP BY id_usuario "
     "HAVING COUNT(*) > 1) d", None),

    ("contrasenas_sin_cifrar",
     "Cuentas con contraseña sin cifrar (se cifra sola al iniciar sesión)",
     "SELECT COUNT(*) FROM usuarios WHERE contrasena NOT LIKE '$2%'",
     None),
]

# Relaciones que debería haber (tabla, columna, tabla_ref, columna_ref)
RELACIONES = [
    ("propiedades", "id_universidad", "universidades", "id_universidad"),
    ("propiedades", "id_tipo", "tipos_propiedad", "id_tipo"),
    ("propiedades", "id_arrendador", "usuarios", "id_usuario"),
    ("propiedades", "id_solicitud", "solicitudes_arrendador", "id_solicitud"),
    ("propiedad_fotos", "id_propiedad", "propiedades", "id_propiedad"),
    ("propiedad_amenidad", "id_propiedad", "propiedades", "id_propiedad"),
    ("propiedad_amenidad", "id_amenidad", "amenidades", "id_amenidad"),
    ("favoritos", "id_usuario", "usuarios", "id_usuario"),
    ("favoritos", "id_propiedad", "propiedades", "id_propiedad"),
    ("comentarios", "id_usuario", "usuarios", "id_usuario"),
    ("comentarios", "id_propiedad", "propiedades", "id_propiedad"),
    ("mensajes", "id_remitente", "usuarios", "id_usuario"),
    ("mensajes", "id_destinatario", "usuarios", "id_usuario"),
    ("mensajes", "id_propiedad", "propiedades", "id_propiedad"),
    ("solicitudes_arrendador", "id_usuario", "usuarios", "id_usuario"),
    ("propiedad_ediciones", "id_propiedad", "propiedades", "id_propiedad"),
]

# Columnas que el código de la app usa (tabla, columna)
COLUMNAS_USADAS = [
    ("usuarios", "id_usuario"), ("usuarios", "nombre"),
    ("usuarios", "usuario"), ("usuarios", "contrasena"),
    ("usuarios", "rol"), ("usuarios", "activo"),
    ("propiedades", "id_propiedad"), ("propiedades", "titulo"),
    ("propiedades", "zona"), ("propiedades", "direccion"),
    ("propiedades", "descripcion"), ("propiedades", "precio"),
    ("propiedades", "distancia"), ("propiedades", "habitaciones"),
    ("propiedades", "banos"), ("propiedades", "camas"),
    ("propiedades", "telefono"), ("propiedades", "id_tipo"),
    ("propiedades", "id_universidad"), ("propiedades", "id_arrendador"),
    ("propiedades", "id_solicitud"), ("propiedades", "verificado"),
    ("propiedades", "disponible"),
    ("propiedad_fotos", "id_foto"), ("propiedad_fotos", "id_propiedad"),
    ("propiedad_fotos", "imagen"), ("propiedad_fotos", "orden"),
    ("solicitudes_arrendador", "id_solicitud"),
    ("solicitudes_arrendador", "estado"),
    ("solicitudes_arrendador", "telefono"),
    ("solicitudes_arrendador", "imagen"),
    ("solicitudes_arrendador", "id_revisor"),
    ("solicitudes_arrendador", "motivo_rechazo"),
    ("solicitudes_arrendador", "fecha_revision"),
    ("comentarios", "id_comentario"), ("comentarios", "id_propiedad"),
    ("comentarios", "calificacion"),
    ("favoritos", "id_usuario"), ("favoritos", "id_propiedad"),
    ("propiedad_amenidad", "id_propiedad"),
    ("propiedad_amenidad", "id_amenidad"),
]


def ejecutar_revisiones(cur, corregir=False):
    """Corre todas las revisiones con un cursor DB-API.

    Devuelve una lista de diccionarios. Si corregir=True, aplica las
    correcciones seguras y devuelve cuántas filas arregló cada una.
    No hace commit: quien llama decide (así se puede probar).
    """

    resultados = []

    for clave, descripcion, sql_conteo, sql_fix in REVISIONES:

        try:
            cur.execute(sql_conteo)
            cantidad = cur.fetchone()[0]
            error = None
        except Exception as e:
            cantidad, error = None, str(e)

        corregidas = 0

        if corregir and sql_fix and cantidad:
            cur.execute(sql_fix)
            corregidas = cur.rowcount

        resultados.append({
            "clave": clave,
            "descripcion": descripcion,
            "cantidad": cantidad,
            "corregible": sql_fix is not None,
            "corregidas": corregidas,
            "error": error,
        })

    return resultados


def revisar_estructura(cur):
    """Solo MySQL: columnas que faltan y relaciones (FK) ausentes."""

    cur.execute(
        "SELECT TABLE_NAME, COLUMN_NAME FROM information_schema.COLUMNS "
        "WHERE TABLE_SCHEMA = DATABASE()"
    )
    existentes = {(t.lower(), c.lower()) for t, c in cur.fetchall()}

    faltan = [
        (t, c) for t, c in COLUMNAS_USADAS
        if (t, c) not in existentes
    ]

    cur.execute(
        "SELECT TABLE_NAME, COLUMN_NAME, REFERENCED_TABLE_NAME "
        "FROM information_schema.KEY_COLUMN_USAGE "
        "WHERE TABLE_SCHEMA = DATABASE() "
        "AND REFERENCED_TABLE_NAME IS NOT NULL"
    )
    con_fk = {(t.lower(), c.lower(), r.lower()) for t, c, r in cur.fetchall()}

    sin_fk = [
        r for r in RELACIONES
        if (r[0], r[1], r[2]) not in con_fk
        and (r[0], r[1]) in existentes
    ]

    return faltan, sin_fk


def armar_informe(resultados, faltan=None, sin_fk=None, corregir=False):

    lineas = [
        "DIAGNÓSTICO DE INTEGRIDAD - UNIHOGAR",
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        "Modo: " + ("CORRECCIÓN" if corregir else "solo lectura"),
        "",
    ]

    problemas = 0

    for r in resultados:

        if r["error"]:
            estado = f"no se pudo revisar ({r['error']})"
        elif r["cantidad"]:
            problemas += 1
            estado = f"{r['cantidad']} caso(s)"
            if corregir and r["corregible"]:
                estado += f" -> corregidos: {r['corregidas']}"
            elif r["corregible"]:
                estado += " (corregible con --corregir)"
            else:
                estado += " (solo reporte: revisar a mano)"
        else:
            estado = "OK"

        lineas.append(f"- {r['descripcion']}: {estado}")

    if faltan is not None:
        lineas += ["", "Columnas que usa la app y NO existen:"]
        lineas += [f"  - {t}.{c}" for t, c in faltan] or ["  ninguna"]

    if sin_fk:
        lineas += [
            "",
            "Relaciones sin clave foránea (sugerencias; ejecútalas solo",
            "cuando las revisiones anteriores estén en OK):",
        ]
        for t, c, rt, rc in sin_fk:
            lineas.append(
                f"  -- ALTER TABLE {t} ADD FOREIGN KEY ({c}) "
                f"REFERENCES {rt}({rc});"
            )

    lineas += ["", f"Revisiones con casos: {problemas}"]

    return "\n".join(lineas)


def main():

    from conexion import ConexionBD

    corregir = "--corregir" in sys.argv

    bd = ConexionBD()
    con = bd.conectar()

    if con is None:
        raise SystemExit("No se pudo conectar a MySQL. Revisa tu .env.")

    cur = con.cursor()

    try:
        faltan, sin_fk = revisar_estructura(cur)
        resultados = ejecutar_revisiones(cur, corregir)

        if corregir:
            con.commit()

    except Exception as e:
        con.rollback()
        raise SystemExit(f"Error: no se cambió nada. Detalle: {e}")

    informe = armar_informe(resultados, faltan, sin_fk, corregir)

    print(informe)

    with open("diagnostico_integridad.txt", "w", encoding="utf-8") as f:
        f.write(informe + "\n")

    print("\nInforme guardado en diagnostico_integridad.txt")

    cur.close()
    bd.desconectar(con)


if __name__ == "__main__":
    main()
