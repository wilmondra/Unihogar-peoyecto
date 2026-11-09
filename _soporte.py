"""Soporte para las pruebas: módulos simulados y conexión falsa.

IMPORTANTE: la "conexión falsa" NO es MySQL. Sirve para comprobar QUÉ
instrucciones SQL envía el DAO, con qué parámetros, en qué orden, si
hace commit/rollback y qué permisos exige. No prueba que MySQL acepte
esas instrucciones: eso lo cubre test_integracion_mysql.py.
"""

import hashlib
import os
import sys
import types

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

USA_BCRYPT_REAL = True

try:
    import bcrypt  # noqa: F401
except ImportError:
    USA_BCRYPT_REAL = False

    falso = types.ModuleType("bcrypt")
    falso.gensalt = lambda: b"$2b$04$salsa"
    falso.hashpw = lambda pw, salt: (
        b"$2b$04$" + hashlib.sha256(pw).hexdigest().encode()
    )
    falso.checkpw = lambda pw, h: h == falso.hashpw(pw, None)
    sys.modules["bcrypt"] = falso

try:
    import mysql.connector  # noqa: F401
except ImportError:
    mysql = types.ModuleType("mysql")
    conector = types.ModuleType("mysql.connector")

    class Error(Exception):
        errno = None

    def _sin_conexion(*a, **k):
        raise Error("MySQL simulado: sin conexión")

    conector.Error = Error
    conector.connect = _sin_conexion
    mysql.connector = conector
    sys.modules["mysql"] = mysql
    sys.modules["mysql.connector"] = conector


class CursorFalso:

    def __init__(self, conexion, diccionario):
        self.conexion = conexion
        self.diccionario = diccionario
        self._filas = []
        self.rowcount = 0
        self.lastrowid = 100

    def execute(self, sql, params=None):

        sql = " ".join(sql.split())
        self.conexion.registro.append((sql, params))

        filas, cantidad = self.conexion.escenario(sql, params)

        if isinstance(filas, Exception):
            raise filas

        self._filas = list(filas)
        self.rowcount = cantidad

    def fetchall(self):
        return list(self._filas)

    def fetchone(self):
        return self._filas[0] if self._filas else None

    def close(self):
        pass


class ConexionFalsa:

    def __init__(self, escenario):
        self.escenario = escenario
        self.registro = []
        self.commits = 0
        self.rollbacks = 0
        self.cerrada = False

    def is_connected(self):
        return not self.cerrada

    def cursor(self, dictionary=False):
        return CursorFalso(self, dictionary)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.cerrada = True

    # Ayudas para las pruebas
    def sentencias(self):
        return [s for s, _ in self.registro]

    def hubo(self, texto):
        return any(texto in s for s in self.sentencias())


def crear_dao(escenario):
    """Devuelve (dao, lista_de_conexiones). Cada vez que el DAO
    conecta se crea una ConexionFalsa nueva con el escenario dado."""

    import dao as modulo_dao

    dao = modulo_dao.DAO()
    conexiones = []

    def conectar():
        c = ConexionFalsa(escenario)
        conexiones.append(c)
        return c

    dao.conectar = conectar
    dao.desconectar = lambda c: c.close()

    return dao, conexiones


def todas(conexiones):
    return [s for c in conexiones for s in c.sentencias()]
