"""Prueba las revisiones de auditoria_integridad.py con SQLite.

Usa SQLite porque las revisiones son SQL estándar y así se pueden
ejecutar de verdad sin MySQL. No prueba la parte de information_schema
(estructura/FK), que es solo de MySQL.
"""

import sqlite3
import unittest

from tests import _soporte  # noqa: F401
import auditoria_integridad as aud

ESQUEMA = """
CREATE TABLE usuarios (id_usuario INTEGER PRIMARY KEY, usuario TEXT,
    contrasena TEXT, rol TEXT);
CREATE TABLE universidades (id_universidad INTEGER PRIMARY KEY);
CREATE TABLE tipos_propiedad (id_tipo INTEGER PRIMARY KEY);
CREATE TABLE amenidades (id_amenidad INTEGER PRIMARY KEY);
CREATE TABLE solicitudes_arrendador (id_solicitud INTEGER PRIMARY KEY,
    id_usuario INTEGER, estado TEXT);
CREATE TABLE propiedades (id_propiedad INTEGER PRIMARY KEY, precio REAL,
    id_tipo INTEGER, id_universidad INTEGER, id_arrendador INTEGER,
    id_solicitud INTEGER);
CREATE TABLE propiedad_fotos (id_foto INTEGER PRIMARY KEY, id_propiedad INTEGER);
CREATE TABLE propiedad_amenidad (id_propiedad INTEGER, id_amenidad INTEGER);
CREATE TABLE propiedad_ediciones (id_edicion INTEGER PRIMARY KEY, id_propiedad INTEGER);
CREATE TABLE favoritos (id_usuario INTEGER, id_propiedad INTEGER);
CREATE TABLE comentarios (id_comentario INTEGER PRIMARY KEY, id_usuario INTEGER,
    id_propiedad INTEGER, comentario TEXT);
CREATE TABLE mensajes (id_mensaje INTEGER PRIMARY KEY, id_propiedad INTEGER);
"""

DATOS_SANOS = """
INSERT INTO usuarios VALUES (1,'admin','$2b$x','administrador'),
                            (2,'dueno','$2b$y','arrendador'),
                            (3,'estu','$2b$z','estudiante');
INSERT INTO universidades VALUES (1);
INSERT INTO tipos_propiedad VALUES (1);
INSERT INTO amenidades VALUES (1),(2);
INSERT INTO solicitudes_arrendador VALUES (10,2,'aprobada');
INSERT INTO propiedades VALUES (100,2500,1,1,2,10);
INSERT INTO propiedad_fotos VALUES (1,100);
INSERT INTO propiedad_amenidad VALUES (100,1),(100,2);
INSERT INTO favoritos VALUES (3,100);
INSERT INTO comentarios VALUES (1,3,100,'bueno');
INSERT INTO mensajes VALUES (1,100);
"""

DATOS_SUCIOS = """
INSERT INTO propiedad_fotos VALUES (2,999);
INSERT INTO propiedad_amenidad VALUES (999,1),(100,77);
INSERT INTO favoritos VALUES (3,999),(55,100);
INSERT INTO propiedad_ediciones VALUES (1,999);
INSERT INTO comentarios VALUES (2,3,999,'de propiedad borrada'),
                               (3,66,100,'usuario borrado');
INSERT INTO mensajes VALUES (2,999);
INSERT INTO usuarios VALUES (4,'ADMIN','plana','estudiante');
INSERT INTO propiedades VALUES (101,0,1,1,888,10);
"""


def contar(cur, tabla):
    cur.execute(f"SELECT COUNT(*) FROM {tabla}")
    return cur.fetchone()[0]


def por_clave(resultados):
    return {r["clave"]: r for r in resultados}


class PruebasAuditoria(unittest.TestCase):

    def _bd(self, sucio):
        con = sqlite3.connect(":memory:")
        cur = con.cursor()
        cur.executescript(ESQUEMA + DATOS_SANOS + (DATOS_SUCIOS if sucio else ""))
        return con, cur

    def test_base_sana_sin_problemas(self):
        con, cur = self._bd(False)
        r = por_clave(aud.ejecutar_revisiones(cur))
        for clave, fila in r.items():
            self.assertIsNone(fila["error"], clave)
            if clave != "propiedades_sin_arrendador":
                self.assertEqual(fila["cantidad"], 0, clave)

    def test_detecta_problemas(self):
        con, cur = self._bd(True)
        r = por_clave(aud.ejecutar_revisiones(cur))
        esperado = {
            "fotos_huerfanas": 1,
            "servicios_huerfanos_propiedad": 1,
            "servicios_huerfanos_amenidad": 1,
            "favoritos_sin_propiedad": 1,
            "favoritos_sin_usuario": 1,
            "ediciones_huerfanas": 1,
            "comentarios_propiedad_rota": 1,
            "mensajes_propiedad_rota": 1,
            "comentarios_sin_usuario": 1,
            "propiedades_dueno_inexistente": 1,
            "propiedades_precio_invalido": 1,
            "duplicado_usuarios": 1,
            "duplicado_solicitud_propiedad": 1,
            "contrasenas_sin_cifrar": 1,
        }
        for clave, cantidad in esperado.items():
            self.assertIsNone(r[clave]["error"], clave)
            self.assertEqual(r[clave]["cantidad"], cantidad, clave)

    def test_solo_lectura_no_cambia_nada(self):
        con, cur = self._bd(True)
        antes = {t: contar(cur, t) for t in
                 ("propiedad_fotos", "favoritos", "comentarios", "mensajes")}
        aud.ejecutar_revisiones(cur, corregir=False)
        despues = {t: contar(cur, t) for t in antes}
        self.assertEqual(antes, despues)

    def test_corregir_arregla_lo_seguro_y_conserva_lo_valido(self):
        con, cur = self._bd(True)
        resultados = aud.ejecutar_revisiones(cur, corregir=True)
        con.commit()

        # Lo roto desapareció...
        r2 = por_clave(aud.ejecutar_revisiones(cur))
        for clave in ("fotos_huerfanas", "servicios_huerfanos_propiedad",
                      "servicios_huerfanos_amenidad",
                      "favoritos_sin_propiedad", "favoritos_sin_usuario",
                      "ediciones_huerfanas", "comentarios_propiedad_rota",
                      "mensajes_propiedad_rota"):
            self.assertEqual(r2[clave]["cantidad"], 0, clave)

        # ... y lo válido sigue ahí
        self.assertEqual(contar(cur, "propiedades"), 2)   # nunca se borran
        cur.execute("SELECT COUNT(*) FROM propiedad_fotos WHERE id_propiedad=100")
        self.assertEqual(cur.fetchone()[0], 1)
        cur.execute("SELECT COUNT(*) FROM favoritos WHERE id_propiedad=100 AND id_usuario=3")
        self.assertEqual(cur.fetchone()[0], 1)
        # Los comentarios y mensajes NO se borran, solo pierden la propiedad
        self.assertEqual(contar(cur, "comentarios"), 3)
        self.assertEqual(contar(cur, "mensajes"), 2)
        cur.execute("SELECT id_propiedad FROM comentarios WHERE id_comentario=2")
        self.assertIsNone(cur.fetchone()[0])

        # Los problemas "solo reporte" siguen reportados (no se tocan)
        self.assertEqual(r2["duplicado_usuarios"]["cantidad"], 1)
        self.assertEqual(r2["propiedades_dueno_inexistente"]["cantidad"], 1)
        self.assertEqual(r2["propiedades_precio_invalido"]["cantidad"], 1)
        self.assertEqual(contar(cur, "usuarios"), 4)

        informe = aud.armar_informe(resultados, [], [], corregir=True)
        self.assertIn("corregidos", informe)


if __name__ == "__main__":
    unittest.main()
