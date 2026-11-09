"""Pruebas de INTEGRACIÓN contra un MySQL REAL de pruebas.

Estas pruebas NO se ejecutan solas. Para correrlas:

 1. Crea una COPIA de tu base (nunca uses la real):
        mysqldump Unihogar | mysql Unihogar_test
 2. Define las variables de entorno (o .env):
        UNIHOGAR_DB_NAME=Unihogar_test
        UNIHOGAR_DB_PASSWORD=...
        UNIHOGAR_TEST_DB=1
 3. python -m unittest tests.test_integracion_mysql -v

Por seguridad se niegan a correr si el nombre de la base no termina
en "_test". Solo borran los registros que ellas mismas crean.
"""

import os
import unittest
import uuid

RUN = os.environ.get("UNIHOGAR_TEST_DB") == "1"
NOMBRE = os.environ.get("UNIHOGAR_DB_NAME", "")

JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64


@unittest.skipUnless(
    RUN and NOMBRE.lower().endswith("_test"),
    "Define UNIHOGAR_TEST_DB=1 y una base cuyo nombre termine en _test",
)
class PruebasIntegracion(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import bcrypt  # noqa: F401  (debe ser el real)
        from dao import DAO

        cls.dao = DAO()
        cls.dao.preparar_base_datos()

        if cls.dao.conectar() is None:
            raise unittest.SkipTest("No hay conexión con MySQL")

        cls.sufijo = uuid.uuid4().hex[:8]
        cls.ids_usuarios = []
        cls.ids_propiedades = []

        tipos = cls.dao.obtener_tipos()
        unis = cls.dao.obtener_universidades()

        if not tipos or not unis:
            raise unittest.SkipTest("La base de pruebas no tiene tipos/universidades")

        cls.id_tipo = tipos[0]["id_tipo"]
        cls.nombre_tipo = tipos[0]["nombre"]
        cls.id_uni = unis[0]["id_universidad"]
        cls.nombre_uni = unis[0]["nombre"]

    @classmethod
    def tearDownClass(cls):
        dao = cls.dao
        for p in cls.ids_propiedades:
            dao.ejecutar("DELETE FROM favoritos WHERE id_propiedad=%s", (p,))
            dao.ejecutar("DELETE FROM propiedad_amenidad WHERE id_propiedad=%s", (p,))
            dao.ejecutar("DELETE FROM propiedad_fotos WHERE id_propiedad=%s", (p,))
            dao.ejecutar("DELETE FROM propiedades WHERE id_propiedad=%s", (p,))
        for u in cls.ids_usuarios:
            dao.ejecutar("DELETE FROM solicitudes_arrendador WHERE id_usuario=%s", (u,))
            dao.ejecutar("DELETE FROM usuarios WHERE id_usuario=%s", (u,))

    # ---- ayudas ----
    def _usuario(self, rol, nombre_usuario=None):
        usuario = nombre_usuario or f"{rol[:3]}_{self.sufijo}"
        if rol == "administrador":
            hash_ = __import__("bcrypt").hashpw(b"clave1234", __import__("bcrypt").gensalt()).decode()
            self.dao.ejecutar(
                "INSERT INTO usuarios (nombre, usuario, contrasena, rol) "
                "VALUES (%s,%s,%s,'administrador')",
                ("Admin Prueba", usuario, hash_))
        else:
            self.assertTrue(self.dao.registrar_usuario(
                "Persona Prueba", usuario, "clave1234", rol))
        u = self.dao.obtener_usuario(usuario)
        self.assertIsNotNone(u)
        self.ids_usuarios.append(u["id_usuario"])
        return u["id_usuario"]

    # ---- pruebas ----
    def test_1_registro_y_login(self):
        dao = self.dao
        uid = self._usuario("estudiante", f"est_{self.sufijo}")
        u = dao.obtener_usuario(f"est_{self.sufijo}")
        self.assertTrue(dao.verificar_contrasena("clave1234", u["contrasena"]))
        self.assertFalse(dao.verificar_contrasena("mala", u["contrasena"]))
        # duplicado (también con otras mayúsculas) y claves débiles
        self.assertFalse(dao.registrar_usuario(
            "Otra Persona", f"EST_{self.sufijo}", "clave1234"))
        self.assertFalse(dao.registrar_usuario("Ana Gómez", "ana_x1", "123"))
        # cuenta desactivada: no se puede reusar el nombre
        admin = self._usuario("administrador", f"adm_{self.sufijo}")
        self.assertTrue(dao.cambiar_estado_usuario(uid, False, admin))
        self.assertFalse(dao.registrar_usuario(
            "Otra Persona", f"est_{self.sufijo}", "clave1234"))
        self.assertFalse(dao.cambiar_estado_usuario(uid, True, uid))  # no admin

    def test_2_solicitud_aprobacion_filtros_edicion_favoritos_borrado(self):
        dao = self.dao
        arr = self._usuario("arrendador", f"arr_{self.sufijo}")
        adm = self._usuario("administrador", f"adm2_{self.sufijo}")
        est = self._usuario("estudiante", f"est2_{self.sufijo}")
        zona = f"Zona{self.sufijo}"

        # Publicación SOLO mediante solicitud
        self.assertIsNone(dao.crear_propiedad_arrendador(arr, {}))
        self.assertTrue(dao.crear_solicitud_arrendador(
            arr, f"{zona}, casa 5", "Linda casa", JPEG, self.id_tipo,
            "2500", self.id_uni, "5 min", "8888 8888"))
        self.assertFalse(dao.crear_solicitud_arrendador(   # ya hay pendiente
            arr, f"{zona}, casa 6", "x", JPEG, self.id_tipo, "2500",
            self.id_uni, "5 min", ""))
        self.assertEqual(dao.obtener_propiedades(zona=zona), [])  # aún no
        sol = dao.obtener_solicitud_usuario(arr)
        self.assertFalse(dao.resolver_solicitud(sol["id_solicitud"], True, est))
        self.assertTrue(dao.resolver_solicitud(sol["id_solicitud"], True, adm))

        # Aparece en la búsqueda y responde a los filtros combinados
        res = dao.obtener_propiedades(zona=zona)
        self.assertEqual(len(res), 1)
        pid = res[0]["id_propiedad"]
        self.ids_propiedades.append(pid)
        self.assertEqual(res[0]["telefono"], "8888 8888")
        self.assertEqual(len(dao.obtener_propiedades(
            "", self.nombre_tipo, self.nombre_uni, 2000, 3000, zona)), 1)
        self.assertEqual(dao.obtener_propiedades(
            precio_min=2501, zona=zona), [])
        self.assertEqual(dao.obtener_propiedades(
            precio_max=2499, zona=zona), [])
        self.assertEqual(dao.obtener_propiedades(
            precio_min=3000, precio_max=1000, zona=zona), [])

        # Edición independiente del dueño (datos + servicios + fotos)
        amen = [a["id_amenidad"] for a in dao.obtener_amenidades()[:1]]
        datos = dict(titulo="Casa editada", direccion=f"{zona}, casa 5",
                     descripcion="Nueva", precio="2600", id_tipo=self.id_tipo,
                     id_universidad=self.id_uni, habitaciones=3, banos=2,
                     camas=None, telefono="7777 7777", distancia="3 min",
                     amenidades=amen)
        fotos = dao.obtener_fotos_propiedad(pid)
        ids_fotos = [f["id_foto"] for f in fotos]
        self.assertTrue(dao.guardar_cambios_propiedad(
            arr, pid, datos, [JPEG], ids_fotos))
        self.assertEqual(len(dao.obtener_fotos_propiedad(pid)), len(ids_fotos) + 1)
        if amen:
            self.assertEqual(len(dao.obtener_propiedades(
                zona=zona, amenidades=amen)), 1)
        # Otro arrendador no puede editar ni borrar
        otro = self._usuario("arrendador", f"arr2_{self.sufijo}")
        self.assertFalse(dao.guardar_cambios_propiedad(otro, pid, datos, [], []))
        self.assertFalse(dao.eliminar_propiedad_arrendador(otro, pid))

        # Favoritos
        self.assertTrue(dao.agregar_favorito(est, pid))
        self.assertTrue(dao.agregar_favorito(est, pid))   # sin duplicar
        self.assertTrue(dao.es_favorito(est, pid))

        # Borrado del dueño: limpia lo dependiente y conserva comentarios
        self.assertTrue(dao.agregar_comentario(est, "Muy buena", pid, 5))
        self.assertTrue(dao.eliminar_propiedad_arrendador(arr, pid))
        self.assertFalse(dao.es_favorito(est, pid))
        self.assertEqual(dao.obtener_fotos_propiedad(pid), [])
        self.assertEqual(dao.obtener_propiedades(zona=zona), [])


if __name__ == "__main__":
    unittest.main()
