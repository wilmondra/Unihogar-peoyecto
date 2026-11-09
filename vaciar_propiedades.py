"""Vacía TODAS las propiedades. ES DESTRUCTIVO Y NO SE PUEDE DESHACER.

Uso:  python vaciar_propiedades.py

Muestra cuántos registros se perderían y pide escribir exactamente
BORRAR TODO para continuar. Haz una copia de seguridad antes
(mysqldump).
"""
import sys

from conexion import ConexionBD

bd = ConexionBD()
con = bd.conectar()

if con is None:
    raise SystemExit("No se pudo conectar a MySQL. Revisa tu archivo .env.")

cur = con.cursor()
cur.execute("SELECT DATABASE()")
print("Base de datos en uso:", cur.fetchone()[0])

for etiqueta, tabla in (
    ("Propiedades", "propiedades"),
    ("Fotos", "propiedad_fotos"),
    ("Favoritos", "favoritos"),
    ("Servicios asignados", "propiedad_amenidad"),
    ("Ediciones pendientes", "propiedad_ediciones"),
):
    try:
        cur.execute(f"SELECT COUNT(*) FROM {tabla}")
        print(f"  {etiqueta}: {cur.fetchone()[0]}")
    except Exception:
        pass

print("\nSe BORRARÁN todos esos registros. Los comentarios y mensajes se")
print("conservan, pero quedan sin propiedad.")

if not sys.stdin.isatty():
    raise SystemExit("Cancelado: hace falta una terminal para confirmar.")

if input("Escribe BORRAR TODO para continuar: ").strip() != "BORRAR TODO":
    raise SystemExit("Cancelado. No se borró nada.")

try:
    cur.execute("SET FOREIGN_KEY_CHECKS = 0")
    cur.execute("DELETE FROM favoritos")
    cur.execute("DELETE FROM propiedad_amenidad")
    cur.execute("DELETE FROM propiedad_ediciones")
    cur.execute("DELETE FROM propiedad_fotos")
    cur.execute("UPDATE comentarios SET id_propiedad = NULL")
    cur.execute("UPDATE mensajes SET id_propiedad = NULL")
    cur.execute("DELETE FROM propiedades")
    cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    con.commit()
except Exception as e:
    con.rollback()
    raise SystemExit(f"Error, no se borró nada: {e}")

cur.execute("SELECT COUNT(*) FROM propiedades")
print("Propiedades después:", cur.fetchone()[0])

cur.close()
bd.desconectar(con)
