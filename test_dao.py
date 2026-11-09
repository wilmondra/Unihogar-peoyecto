"""Pruebas del DAO con una conexión FALSA (no es MySQL).

Comprueban el SQL que se envía, los parámetros, el orden, las
transacciones (commit/rollback) y los permisos.
"""

import unittest

from tests import _soporte
from tests._soporte import crear_dao, todas

import dao as modulo_dao

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
ADMIN = [{"ok": 1}]


def escenario_base(**reglas):
    """reglas: fragmento de SQL -> (filas, rowcount) o función."""

    def responder(sql, params):
        for fragmento, respuesta in reglas.items():
            if fragmento in sql:
                if callable(respuesta):
                    return respuesta(sql, params)
                return respuesta
        return [], 1

    return responder


def datos_validos(**extra):
    d = {
        "titulo": "Casa bonita", "direccion": "Barrio Lindo, casa 12",
        "descripcion": "Linda", "precio": "2500", "id_tipo": 1,
        "id_universidad": 2, "habitaciones": 3, "banos": 2,
        "camas": None, "telefono": "8888 8888",
        "distancia": "5 min", "amenidades": [1, 2],
    }
    d.update(extra)
    return d


class PruebasFiltros(unittest.TestCase):

    def test_todos_los_filtros_combinados(self):
        sql, params = modulo_dao.construir_consulta_propiedades(
            "casa", "Casa", "UNAN", 1000.0, 3000.0, "Linda Vista", [3, 1]
        )
        for trozo in ("LOWER(p.titulo) LIKE %s", "LOWER(p.direccion) LIKE %s",
                      "t.nombre = %s", "u.nombre = %s",
                      "p.precio >= %s", "p.precio <= %s",
                      "HAVING COUNT(DISTINCT pa.id_amenidad) = %s",
                      "p.disponible = TRUE"):
            self.assertIn(trozo, sql)
        self.assertEqual(
            params,
            ("%casa%", "%casa%", "%linda vista%", "%linda vista%",
             "Casa", "UNAN", 1000.0, 3000.0, 1, 3, 2)
        )
        # Cada %s tiene su parámetro
        self.assertEqual(sql.count("%s"), len(params))

    def test_sin_filtros(self):
        sql, params = modulo_dao.construir_consulta_propiedades()
        self.assertEqual(params, ())
        self.assertNotIn("LIKE", sql)
        self.assertNotIn("p.precio >=", sql)
        self.assertNotIn("p.precio <=", sql)

    def test_todos_no_filtra(self):
        sql, params = modulo_dao.construir_consulta_propiedades(
            tipo="Todos", universidad="Todas las universidades"
        )
        self.assertEqual(params, ())

    def test_comodines_escapados(self):
        _, params = modulo_dao.construir_consulta_propiedades(texto="50%_")
        self.assertEqual(params[0], "%50\\%\\_%")

    def test_injeccion_va_como_parametro(self):
        sql, params = modulo_dao.construir_consulta_propiedades(
            zona="x'; DROP TABLE propiedades; --"
        )
        self.assertNotIn("DROP", sql)
        self.assertIn("drop table", params[0])

    def test_rango_invertido_no_consulta(self):
        dao, conexiones = crear_dao(escenario_base())
        self.assertEqual(dao.obtener_propiedades(precio_min=5000,
                                                 precio_max=1000), [])
        self.assertEqual(conexiones, [])

    def test_obtener_propiedades_agrega_amenidades(self):
        fila = {"id_propiedad": 7, "titulo": "X"}
        dao, conexiones = crear_dao(escenario_base(**{
            "FROM propiedades p": ([fila], 1),
            "FROM propiedad_amenidad pa": (
                [{"id_propiedad": 7, "nombre": "WiFi"}], 1),
        }))
        res = dao.obtener_propiedades(precio_min="1000", zona="lindo",
                                      amenidades=[1])
        self.assertEqual(res[0]["amenidades"], ["WiFi"])
        consulta, params = conexiones[0].registro[0]
        self.assertIn("p.precio >= %s", consulta)
        self.assertEqual(params[0], "%lindo%")


class PruebasCuentas(unittest.TestCase):

    def test_registro_clave_debil_no_toca_la_base(self):
        dao, conexiones = crear_dao(escenario_base())
        self.assertFalse(dao.registrar_usuario("Ana Gómez", "ana_g", "123"))
        self.assertEqual(conexiones, [])

    def test_registro_usuario_duplicado(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE usuario": (ADMIN, 1)}))
        self.assertFalse(
            dao.registrar_usuario("Ana Gómez", "ana_g", "clave1234"))
        self.assertFalse(any("INSERT INTO usuarios" in s
                             for s in todas(conexiones)))

    def test_registro_correcto_guarda_hash(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE usuario": ([], 0)}))
        self.assertTrue(
            dao.registrar_usuario("Ana Gómez", "ana_g", "clave1234"))
        insertos = [p for c in conexiones for s, p in c.registro
                    if "INSERT INTO usuarios" in s]
        self.assertEqual(len(insertos), 1)
        self.assertNotEqual(insertos[0][2], "clave1234")
        self.assertTrue(insertos[0][2].startswith("$2"))

    def test_registro_arrendador_crea_estudiante_y_solicitud(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE usuario": ([], 0)}))
        self.assertTrue(dao.registrar_usuario(
            "Ana Gómez", "ana_g", "clave1234", "arrendador"))
        insertos = [p for c in conexiones for s, p in c.registro
                    if "INSERT INTO usuarios" in s]
        self.assertEqual(len(insertos), 1)
        # Nunca se crea directamente como arrendador.
        self.assertEqual(insertos[0][3], "estudiante")
        solicitudes = [p for c in conexiones for s, p in c.registro
                       if "INSERT INTO solicitudes_rol" in s]
        self.assertEqual(len(solicitudes), 1)
        self.assertEqual(solicitudes[0], (100,))
        # Cuenta y solicitud en la misma conexión, con un solo commit.
        usada = [c for c in conexiones if c.hubo("INSERT INTO usuarios")]
        self.assertEqual(len(usada), 1)
        self.assertTrue(usada[0].hubo("INSERT INTO solicitudes_rol"))
        self.assertEqual(usada[0].commits, 1)

    def test_registro_estudiante_no_crea_solicitud(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE usuario": ([], 0)}))
        self.assertTrue(
            dao.registrar_usuario("Ana Gómez", "ana_g", "clave1234"))
        self.assertFalse(any("solicitudes_rol" in s
                             for s in todas(conexiones)))

    def test_resolver_permiso_exige_admin(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE id_usuario": ([], 0)}))
        self.assertFalse(dao.resolver_solicitud_rol(5, True, 9))
        self.assertFalse(any("UPDATE usuarios" in s
                             for s in todas(conexiones)))

    def test_aprobar_permiso_convierte_en_arrendador(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE id_usuario": (ADMIN, 1),
            "SELECT id_usuario FROM solicitudes_rol": (
                [{"id_usuario": 7}], 1),
            "UPDATE solicitudes_rol": ([], 1),
            "UPDATE usuarios SET rol": ([], 1),
        }))
        self.assertTrue(dao.resolver_solicitud_rol(5, True, 1))
        cambio = [p for c in conexiones for s, p in c.registro
                  if "UPDATE usuarios SET rol = 'arrendador'" in s]
        self.assertEqual(cambio, [(7,)])

    def test_rechazar_permiso_no_cambia_el_rol(self):
        dao, conexiones = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios WHERE id_usuario": (ADMIN, 1),
            "SELECT id_usuario FROM solicitudes_rol": (
                [{"id_usuario": 7}], 1),
            "UPDATE solicitudes_rol": ([], 1),
        }))
        self.assertTrue(
            dao.resolver_solicitud_rol(5, False, 1, "Datos falsos"))
        self.assertFalse(any("UPDATE usuarios" in s
                             for s in todas(conexiones)))

    def test_registro_rol_administrador_rechazado(self):
        dao, conexiones = crear_dao(escenario_base())
        self.assertFalse(dao.registrar_usuario(
            "Ana Gómez", "ana_g", "clave1234", "administrador"))
        self.assertEqual(conexiones, [])

    def test_verificar_contrasena(self):
        dao, _ = crear_dao(escenario_base())
        import bcrypt
        h = bcrypt.hashpw(b"clave1234", bcrypt.gensalt()).decode()
        self.assertTrue(dao.verificar_contrasena("clave1234", h))
        self.assertFalse(dao.verificar_contrasena("otra", h))
        # Cuenta antigua sin cifrar
        self.assertTrue(dao.verificar_contrasena("vieja", "vieja"))
        self.assertFalse(dao.verificar_contrasena("x", "vieja"))
        self.assertFalse(dao.verificar_contrasena("", "vieja"))
        self.assertFalse(dao.verificar_contrasena("a", None))


class PruebaBaseDeDatos(unittest.TestCase):

    def test_preparar_base_de_datos_no_borra_nada(self):
        dao, conexiones = crear_dao(lambda sql, p: ([(0,)], 0))
        dao.preparar_base_datos()
        sentencias = [s.upper() for s in todas(conexiones)]
        self.assertTrue(sentencias, "no se ejecutó nada")
        for s in sentencias:
            for prohibido in ("DELETE", "DROP", "TRUNCATE"):
                self.assertNotIn(prohibido, s)
            self.assertFalse(
                s.startswith("UPDATE COMENTARIOS")
                or s.startswith("UPDATE MENSAJES"), s)

    def test_no_quedan_borrados_automaticos_en_el_codigo(self):
        with open(_soporte.RAIZ + "/dao.py", encoding="utf-8") as f:
            codigo = f.read()
        inicio = codigo.index("def preparar_base_datos")
        fin = codigo.index("def conectar", inicio) \
            if "def conectar" in codigo[inicio:] else inicio + 6000
        self.assertNotIn("DELETE FROM", codigo[inicio:inicio + 6000])


class PruebasPermisos(unittest.TestCase):

    def _no_admin(self):
        return crear_dao(escenario_base(**{"rol = 'administrador'": ([], 0)}))

    def _admin(self):
        return crear_dao(escenario_base(**{"rol = 'administrador'": (ADMIN, 1)}))

    def test_no_admin_no_puede_nada(self):
        dao, con = self._no_admin()
        self.assertFalse(dao.cambiar_estado_usuario(5, False, 9))
        self.assertFalse(dao.eliminar_comentario(5, 9))
        self.assertFalse(dao.cambiar_disponibilidad_admin(5, False, 9))
        self.assertFalse(dao.resolver_edicion(5, True, 9))
        self.assertFalse(dao.resolver_solicitud(5, True, 9))
        self.assertFalse(dao.cambiar_estado_usuario(5, False))   # sin id
        for s in todas(con):
            for peligro in ("UPDATE usuarios", "DELETE FROM comentarios",
                            "UPDATE propiedades", "UPDATE solicitudes"):
                self.assertNotIn(peligro, s)

    def test_admin_si_puede(self):
        dao, con = self._admin()
        self.assertTrue(dao.cambiar_estado_usuario(5, False, 9))
        self.assertTrue(dao.eliminar_comentario(5, 9))
        self.assertTrue(dao.cambiar_disponibilidad_admin(5, False, 9))
        sql = todas(con)
        self.assertTrue(any("UPDATE usuarios" in s for s in sql))
        self.assertTrue(any("DELETE FROM comentarios" in s for s in sql))

    def test_admin_no_se_desactiva_a_si_mismo(self):
        dao, con = self._admin()
        self.assertFalse(dao.cambiar_estado_usuario(9, False, 9))


class PruebasSolicitudes(unittest.TestCase):

    def _crear(self, rol="arrendador", filas_creadas=1, **extra):
        dao, con = crear_dao(escenario_base(**{
            "SELECT rol FROM usuarios": ([{"rol": rol}], 1),
            "SELECT 1 FROM tipos_propiedad": ([{"x": 1}], 1),
            "SELECT 1 FROM universidades": ([{"x": 1}], 1),
            "INSERT INTO solicitudes_arrendador": ([], filas_creadas),
        }))
        args = dict(id_usuario=4, direccion="Barrio Lindo casa 3",
                    descripcion="x", imagen=JPEG, id_tipo=1, precio="2500",
                    id_universidad=2, distancia="5 min",
                    telefono="8888 8888")
        args.update(extra)
        return dao, con, dao.crear_solicitud_arrendador(**args)

    def test_arrendador_crea_solicitud(self):
        dao, con, ok = self._crear()
        self.assertTrue(ok)
        insert = [s for s in todas(con) if "INSERT INTO solicitudes" in s][0]
        self.assertIn("WHERE NOT EXISTS", insert)
        self.assertEqual(con[-1].commits, 1)

    def test_estudiante_no_crea_solicitud(self):
        dao, con, ok = self._crear(rol="estudiante")
        self.assertFalse(ok)
        self.assertFalse(any("INSERT" in s for s in todas(con)))

    def test_datos_invalidos_no_llegan_a_la_base(self):
        for malo in ({"telefono": "12"}, {"precio": "abc"},
                     {"precio": "nan"}, {"imagen": b"no es imagen"},
                     {"direccion": "x"}, {"id_tipo": None}):
            dao, con, ok = self._crear(**malo)
            self.assertFalse(ok, malo)
            self.assertFalse(any("INSERT" in s for s in todas(con)), malo)

    def test_ya_hay_pendiente(self):
        dao, con, ok = self._crear(filas_creadas=0)
        self.assertFalse(ok)
        self.assertIn("espera", dao.ultimo_error_mensaje)

    def _escenario_aprobar(self, precio=2500, rowcount=1):
        solicitud = {"id_usuario": 4, "direccion": "Barrio Lindo 3",
                     "precio": precio, "distancia": "5 min", "id_tipo": 1,
                     "id_universidad": 2, "descripcion": "x",
                     "telefono": "8888 8888"}
        return crear_dao(escenario_base(**{
            "rol = 'administrador'": (ADMIN, 1),
            "UPDATE solicitudes_arrendador": ([], rowcount),
            "SELECT id_propiedad FROM propiedades WHERE id_solicitud":
                ([], 0),
            "FROM solicitudes_arrendador WHERE id_solicitud":
                ([solicitud], 1),
            "SELECT nombre FROM tipos_propiedad": ([{"nombre": "Casa"}], 1),
            "SELECT 1 AS ok FROM universidades": ([{"ok": 1}], 1),
        }))

    def test_aprobar_publica_en_una_sola_transaccion(self):
        dao, con = self._escenario_aprobar()
        self.assertTrue(dao.resolver_solicitud(10, True, 9))
        trans = con[-1]
        sql = trans.sentencias()
        self.assertTrue(any("UPDATE solicitudes_arrendador" in s for s in sql))
        self.assertTrue(any("INSERT INTO propiedades" in s for s in sql))
        self.assertTrue(any("INSERT INTO propiedad_fotos" in s for s in sql))
        self.assertEqual((trans.commits, trans.rollbacks), (1, 0))

    def test_aprobar_incompleta_no_queda_aprobada(self):
        dao, con = self._escenario_aprobar(precio=None)
        self.assertFalse(dao.resolver_solicitud(10, True, 9))
        trans = con[-1]
        self.assertEqual((trans.commits, trans.rollbacks), (0, 1))
        self.assertFalse(any("INSERT INTO propiedades" in s
                             for s in trans.sentencias()))

    def test_solicitud_ya_revisada(self):
        dao, con = self._escenario_aprobar(rowcount=0)
        self.assertFalse(dao.resolver_solicitud(10, True, 9))
        self.assertFalse(any("INSERT INTO propiedades" in s
                             for s in todas(con)))

    def test_rechazar_no_publica(self):
        dao, con = self._escenario_aprobar()
        self.assertTrue(dao.resolver_solicitud(10, False, 9, "Fotos borrosas"))
        self.assertFalse(any("INSERT INTO propiedades" in s
                             for s in todas(con)))


class PruebasPropiedades(unittest.TestCase):

    def _dao(self, es_dueno=True, fallar_en=None):
        reglas = {
            "FOR UPDATE": ([{"id_propiedad": 7}] if es_dueno else [], 1),
            "SELECT id_foto FROM propiedad_fotos":
                ([{"id_foto": 1}, {"id_foto": 2}, {"id_foto": 3}], 3),
            "SELECT 1 AS ok FROM tipos_propiedad": ([{"ok": 1}], 1),
            "SELECT 1 AS ok FROM universidades": ([{"ok": 1}], 1),
        }
        if fallar_en:
            reglas[fallar_en] = (RuntimeError("falla simulada"), 0)
        return crear_dao(escenario_base(**reglas))

    def test_guardar_cambios_orden_y_una_transaccion(self):
        dao, con = self._dao()
        self.assertTrue(dao.guardar_cambios_propiedad(
            4, 7, datos_validos(), [JPEG], [1]))
        t = con[-1]
        sql = t.sentencias()
        self.assertEqual((t.commits, t.rollbacks), (1, 0))
        pos = lambda texto: next(i for i, s in enumerate(sql) if texto in s)
        self.assertLess(pos("FOR UPDATE"), pos("UPDATE propiedades"))
        self.assertLess(pos("UPDATE propiedades"), pos("INSERT INTO propiedad_fotos"))
        borradas = [p for s, p in t.registro
                    if s.startswith("DELETE FROM propiedad_fotos")]
        self.assertEqual(sorted(p[0] for p in borradas), [2, 3])
        self.assertTrue(any("INSERT INTO propiedad_amenidad" in s for s in sql))

    def test_guardar_cambios_no_dueno(self):
        dao, con = self._dao(es_dueno=False)
        self.assertFalse(dao.guardar_cambios_propiedad(
            4, 7, datos_validos(), [], [1]))
        t = con[-1]
        self.assertEqual((t.commits, t.rollbacks), (0, 1))
        self.assertFalse(t.hubo("UPDATE propiedades"))

    def test_guardar_cambios_falla_a_la_mitad_revierte_todo(self):
        dao, con = self._dao(fallar_en="DELETE FROM propiedad_fotos")
        self.assertFalse(dao.guardar_cambios_propiedad(
            4, 7, datos_validos(), [], [1]))
        self.assertEqual((con[-1].commits, con[-1].rollbacks), (0, 1))

    def test_foto_invalida_ni_conecta(self):
        dao, con = self._dao()
        self.assertFalse(dao.guardar_cambios_propiedad(
            4, 7, datos_validos(), [b"texto"], [1]))
        self.assertEqual(con, [])

    def test_demasiadas_fotos(self):
        dao, con = self._dao()
        self.assertFalse(dao.guardar_cambios_propiedad(
            4, 7, datos_validos(), [JPEG] * 9, [1, 2, 3]))
        self.assertEqual(con[-1].rollbacks, 1)
        self.assertFalse(con[-1].hubo("UPDATE propiedades"))

    def test_datos_invalidos(self):
        dao, con = self._dao()
        self.assertFalse(dao.guardar_cambios_propiedad(
            4, 7, datos_validos(precio="nan"), [], [1]))
        self.assertEqual(con, [])

    def test_eliminar_propiedad_conserva_comentarios(self):
        dao, con = self._dao()
        self.assertTrue(dao.eliminar_propiedad_arrendador(4, 7))
        t = con[-1]
        sql = t.sentencias()
        self.assertEqual((t.commits, t.rollbacks), (1, 0))
        self.assertTrue(t.hubo("UPDATE comentarios SET id_propiedad = NULL"))
        self.assertFalse(t.hubo("DELETE FROM comentarios"))
        self.assertTrue(sql[-1].startswith("DELETE FROM propiedades"))

    def test_eliminar_propiedad_ajena(self):
        dao, con = self._dao(es_dueno=False)
        self.assertFalse(dao.eliminar_propiedad_arrendador(4, 7))
        self.assertFalse(con[-1].hubo("DELETE"))

    def test_foto_suelta_validada(self):
        dao, con = self._dao()
        self.assertFalse(dao.agregar_foto_propiedad(7, b"no imagen"))
        self.assertEqual(con, [])


class PruebasFavoritosYComentarios(unittest.TestCase):

    def test_favorito_de_propiedad_inexistente(self):
        dao, con = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios": (ADMIN, 1),
            "SELECT 1 FROM propiedades": ([], 0)}))
        self.assertFalse(dao.agregar_favorito(4, 999))
        self.assertFalse(any("INSERT" in s for s in todas(con)))

    def test_favorito_no_se_duplica(self):
        dao, con = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios": (ADMIN, 1),
            "SELECT 1 FROM propiedades": (ADMIN, 1)}))
        self.assertTrue(dao.agregar_favorito(4, 7))
        insert = [s for s in todas(con) if "INSERT INTO favoritos" in s][0]
        self.assertIn("NOT EXISTS", insert)

    def test_comentario_invalido(self):
        dao, con = crear_dao(escenario_base())
        self.assertFalse(dao.agregar_comentario(4, "ok", 7, 9))
        self.assertFalse(dao.agregar_comentario(4, "   ", 7, 3))
        self.assertFalse(dao.agregar_comentario(4, "x" * 1001, 7, 3))
        self.assertEqual(con, [])

    def test_comentario_valido(self):
        dao, con = crear_dao(escenario_base(**{
            "SELECT 1 FROM usuarios": (ADMIN, 1),
            "SELECT 1 FROM propiedades": (ADMIN, 1)}))
        self.assertTrue(dao.agregar_comentario(4, "Muy buena", 7, 5))


if __name__ == "__main__":
    unittest.main()
