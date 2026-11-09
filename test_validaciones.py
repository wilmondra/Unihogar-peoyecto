import unittest

from tests import _soporte  # noqa: F401
import validaciones as v


class PruebasValidaciones(unittest.TestCase):

    def test_precio_valido(self):
        self.assertEqual(v.validar_precio("2,500")[0], 2500.0)
        self.assertEqual(v.validar_precio("2500.50")[0], 2500.5)
        self.assertEqual(v.validar_precio(3000)[0], 3000.0)

    def test_precio_invalido(self):
        for malo in ("", "  ", "abc", "nan", "inf", "1e3", "-5", "0",
                     "12.345", "1000001", None, True):
            valor, error = v.validar_precio(malo)
            self.assertIsNone(valor, malo)
            self.assertTrue(error, malo)

    def test_rango_precios(self):
        self.assertEqual(v.validar_rango_precios("", "")[0], (None, None))
        self.assertEqual(
            v.validar_rango_precios("1000", "3000")[0], (1000.0, 3000.0)
        )
        self.assertEqual(
            v.validar_rango_precios("", "3000")[0], (None, 3000.0)
        )
        self.assertTrue(v.validar_rango_precios("5000", "1000")[1])
        self.assertTrue(v.validar_rango_precios("abc", "")[1])

    def test_telefono(self):
        self.assertEqual(v.limpiar_telefono(""), "")
        self.assertEqual(v.limpiar_telefono("8888 8888"), "8888 8888")
        self.assertEqual(v.limpiar_telefono("+505 8888-8888"), "+505 8888-8888")
        for malo in ("123", "abcdefgh", "8888 8888 x", "1" * 20):
            self.assertIsNone(v.limpiar_telefono(malo), malo)

    def test_usuario(self):
        self.assertEqual(v.validar_usuario(" juan_23 ")[0], "juan_23")
        for malo in ("ab", "con espacio", "a" * 31, "ñandú", "", None):
            self.assertIsNone(v.validar_usuario(malo)[0], malo)

    def test_contrasena(self):
        self.assertIsNone(v.validar_contrasena("abc12345")[1])
        for mala in ("corta1", "solo letras aqui", "12345678", "", None,
                     "a1" * 40):
            self.assertIsNotNone(v.validar_contrasena(mala)[1], mala)

    def test_nombre(self):
        self.assertEqual(v.validar_nombre("  Ana   María ")[0], "Ana María")
        for malo in ("Al", "1234", "Ana<script>", ""):
            self.assertIsNone(v.validar_nombre(malo)[0], malo)

    def test_foto(self):
        jpeg = b"\xff\xd8\xff\xe0" + b"0" * 50
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
        self.assertIsNone(v.validar_foto(jpeg)[1])
        self.assertIsNone(v.validar_foto(png)[1])
        self.assertIsNotNone(v.validar_foto(b"no soy una imagen")[1])
        self.assertIsNotNone(v.validar_foto(b"")[1])
        self.assertIsNotNone(
            v.validar_foto(b"\xff\xd8\xff" + b"0" * v.MAX_BYTES_FOTO)[1]
        )

    def test_escapar_like(self):
        self.assertEqual(v.escapar_like("50%_x"), "50\\%\\_x")

    def test_datos_propiedad(self):
        base = {
            "titulo": "Casa bonita", "direccion": "Barrio Lindo 123",
            "precio": "2500", "id_tipo": 1, "id_universidad": 2,
            "habitaciones": 3, "banos": 2, "camas": None,
            "telefono": "8888 8888", "amenidades": [3, 1, 3],
        }
        limpio, error = v.validar_datos_propiedad(base)
        self.assertIsNone(error)
        self.assertEqual(limpio["amenidades"], [1, 3])
        self.assertEqual(limpio["precio"], 2500.0)

        for campo, valor in (("precio", "abc"), ("titulo", ""),
                             ("direccion", "corta"), ("telefono", "12"),
                             ("id_tipo", None), ("banos", 500)):
            malo = dict(base, **{campo: valor})
            self.assertIsNotNone(
                v.validar_datos_propiedad(malo)[1], campo
            )


if __name__ == "__main__":
    unittest.main()
