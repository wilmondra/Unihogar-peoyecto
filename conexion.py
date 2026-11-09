"""Conexión a MySQL.

Las credenciales ya NO están escritas en el código. Se leen de
variables de entorno (o de un archivo ".env" junto a este archivo):

    UNIHOGAR_DB_HOST       (opcional, por defecto: localhost)
    UNIHOGAR_DB_PORT       (opcional, por defecto: 3306)
    UNIHOGAR_DB_USER       (opcional, por defecto: root)
    UNIHOGAR_DB_PASSWORD   (OBLIGATORIA)
    UNIHOGAR_DB_NAME       (opcional, por defecto: Unihogar)

Mira ".env.example" para ver el formato.
"""

import logging
import os

import mysql.connector
from mysql.connector import Error

logger = logging.getLogger("unihogar")

_RUTA_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _cargar_env(ruta=_RUTA_ENV):
    """Lee un .env sencillo (CLAVE=valor). Una variable que ya
    existe en el sistema tiene prioridad sobre el archivo."""

    if not os.path.isfile(ruta):
        return

    try:
        with open(ruta, encoding="utf-8") as archivo:
            for linea in archivo:
                linea = linea.strip()

                if not linea or linea.startswith("#") or "=" not in linea:
                    continue

                clave, valor = linea.split("=", 1)
                clave = clave.strip()
                valor = valor.strip()

                if (
                    len(valor) >= 2
                    and valor[0] == valor[-1]
                    and valor[0] in "\"'"
                ):
                    valor = valor[1:-1]

                os.environ.setdefault(clave, valor)

    except OSError as e:
        logger.error("No se pudo leer .env: %s", e)


class ConexionBD:

    def __init__(self):
        _cargar_env()

        self.host = os.environ.get("UNIHOGAR_DB_HOST", "localhost")
        self.usuario = os.environ.get("UNIHOGAR_DB_USER", "root")
        self.password = os.environ.get("UNIHOGAR_DB_PASSWORD", "GraciasD18")
        self.database = os.environ.get("UNIHOGAR_DB_NAME", "Unihogar")

        try:
            self.puerto = int(os.environ.get("UNIHOGAR_DB_PORT", "3306"))
        except ValueError:
            self.puerto = 3306

        self._avisado = False

    def conectar(self):

        if self.password is None:

            if not self._avisado:
                logger.error(
                    "Falta la variable de entorno UNIHOGAR_DB_PASSWORD. "
                    "Copia .env.example a .env y escribe tu contraseña "
                    "de MySQL."
                )
                print(
                    "Falta UNIHOGAR_DB_PASSWORD: configura tus datos de "
                    "MySQL (ver .env.example)."
                )
                self._avisado = True

            return None

        try:
            conexion = mysql.connector.connect(
                host=self.host,
                port=self.puerto,
                user=self.usuario,
                password=self.password,
                database=self.database,
                charset="utf8mb4",
                connection_timeout=10
            )

            if conexion.is_connected():
                return conexion

        except Error as e:
            logger.error("Error al conectar con MySQL: %s", e)
            print("Error al conectar con MySQL:", e)

        return None

    def desconectar(self, conexion):
        if conexion is not None and conexion.is_connected():
            conexion.close()
