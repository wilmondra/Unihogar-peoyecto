import hmac
import json
import logging
from contextlib import contextmanager

import bcrypt

import validaciones as val
from conexion import ConexionBD

logger = logging.getLogger("unihogar")


class ErrorBD(Exception):
    """Error de negocio o de base de datos dentro de una transacción."""


def construir_consulta_propiedades(
    texto="",
    tipo="Todos",
    universidad="Todas las universidades",
    precio_min=None,
    precio_max=None,
    zona="",
    amenidades=None
):
    """Arma el SELECT de la búsqueda de alojamientos.

    Devuelve (sql, parametros). Todos los filtros se combinan con AND;
    los servicios son acumulativos (la propiedad debe tener TODOS los
    servicios elegidos). Todo valor del usuario va como parámetro %s.
    """

    sql = """
        SELECT
            p.id_propiedad,
            p.titulo,
            p.zona,
            p.id_universidad,
            u.nombre AS universidad,
            p.distancia,
            p.precio,
            p.id_tipo,
            t.nombre AS tipo,
            p.verificado,
            p.disponible,
            p.direccion,
            p.descripcion,
            p.habitaciones,
            p.banos,
            p.telefono,
            p.camas,
            p.id_arrendador
        FROM propiedades p
        INNER JOIN universidades u
            ON p.id_universidad = u.id_universidad
        INNER JOIN tipos_propiedad t
            ON p.id_tipo = t.id_tipo
        WHERE p.disponible = TRUE
    """

    parametros = []

    texto = (texto or "").strip()

    if texto:
        patron = f"%{val.escapar_like(texto.lower())}%"
        sql += (
            " AND (LOWER(p.titulo) LIKE %s"
            " OR LOWER(p.zona) LIKE %s)"
        )
        parametros += [patron, patron]

    zona = (zona or "").strip()

    if zona:
        patron = f"%{val.escapar_like(zona.lower())}%"
        sql += (
            " AND (LOWER(p.zona) LIKE %s"
            " OR LOWER(p.direccion) LIKE %s)"
        )
        parametros += [patron, patron]

    if tipo and tipo != "Todos":
        sql += " AND t.nombre = %s"
        parametros.append(tipo)

    if universidad and universidad != "Todas las universidades":
        sql += " AND u.nombre = %s"
        parametros.append(universidad)

    if precio_min is not None:
        sql += " AND p.precio >= %s"
        parametros.append(precio_min)

    if precio_max is not None:
        sql += " AND p.precio <= %s"
        parametros.append(precio_max)

    ids = sorted({int(i) for i in (amenidades or [])})

    if ids:
        marcadores = ", ".join(["%s"] * len(ids))
        sql += f"""
            AND p.id_propiedad IN (
                SELECT pa.id_propiedad
                FROM propiedad_amenidad pa
                WHERE pa.id_amenidad IN ({marcadores})
                GROUP BY pa.id_propiedad
                HAVING COUNT(DISTINCT pa.id_amenidad) = %s
            )
        """
        parametros += ids
        parametros.append(len(ids))

    sql += " ORDER BY p.id_propiedad ASC"

    return sql, tuple(parametros)


class DAO:

    def __init__(self):
        self.conexion_bd = ConexionBD()
        self.ultimo_error_codigo = None
        self.ultimo_error_mensaje = None

    def conectar(self):
        return self.conexion_bd.conectar()

    def desconectar(self, conexion):
        self.conexion_bd.desconectar(conexion)

    def preparar_base_datos(self):
        """Deja la base lista automaticamente al abrir la app:
        agrega las columnas nuevas, crea los tipos de propiedad y,
        UNA sola vez, borra las cajas de ejemplo."""

        conexion = self.conectar()

        if conexion is None:
            return

        try:
            cursor = conexion.cursor()

            def existe_columna(tabla, columna):
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = %s AND COLUMN_NAME = %s
                    """,
                    (tabla, columna)
                )
                return cursor.fetchone()[0] > 0

            def existe_tabla(tabla):
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM information_schema.TABLES
                    WHERE TABLE_SCHEMA = DATABASE()
                    AND TABLE_NAME = %s
                    """,
                    (tabla,)
                )
                return cursor.fetchone()[0] > 0

            columnas = [
                ("solicitudes_arrendador", "id_tipo", "INT NULL"),
                ("solicitudes_arrendador", "precio", "DECIMAL(10,2) NULL"),
                ("solicitudes_arrendador", "id_universidad", "INT NULL"),
                ("solicitudes_arrendador", "distancia", "VARCHAR(60) NULL"),
                ("propiedades", "id_arrendador", "INT NULL"),
                ("propiedades", "id_solicitud", "INT NULL"),
                ("propiedades", "direccion", "VARCHAR(255) NULL"),
                ("propiedades", "descripcion", "TEXT NULL"),
                ("propiedades", "habitaciones", "INT NULL"),
                ("propiedades", "banos", "INT NULL"),
                ("propiedades", "telefono", "VARCHAR(30) NULL"),
                ("propiedades", "camas", "INT NULL"),
                ("solicitudes_arrendador", "telefono", "VARCHAR(30) NULL"),
            ]

            for tabla, columna, definicion in columnas:
                if existe_tabla(tabla) and not existe_columna(tabla, columna):
                    cursor.execute(
                        f"ALTER TABLE {tabla} "
                        f"ADD COLUMN {columna} {definicion}"
                    )

            for nombre in ("Casa", "Habitación", "Apartamento"):
                cursor.execute(
                    "SELECT COUNT(*) FROM tipos_propiedad "
                    "WHERE nombre = %s",
                    (nombre,)
                )
                if cursor.fetchone()[0] == 0:
                    cursor.execute(
                        "INSERT INTO tipos_propiedad (nombre) "
                        "VALUES (%s)",
                        (nombre,)
                    )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS propiedad_fotos (
                    id_foto INT AUTO_INCREMENT PRIMARY KEY,
                    id_propiedad INT NOT NULL,
                    imagen LONGBLOB NOT NULL,
                    orden INT NOT NULL DEFAULT 0,
                    fecha_subida TIMESTAMP NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    pendiente TINYINT(1) NOT NULL DEFAULT 0,
                    quitar TINYINT(1) NOT NULL DEFAULT 0,
                    INDEX idx_foto_propiedad (id_propiedad, orden)
                )
                """
            )

            for columna, definicion in (
                ("pendiente", "TINYINT(1) NOT NULL DEFAULT 0"),
                ("quitar", "TINYINT(1) NOT NULL DEFAULT 0"),
            ):
                if not existe_columna("propiedad_fotos", columna):
                    cursor.execute(
                        "ALTER TABLE propiedad_fotos "
                        f"ADD COLUMN {columna} {definicion}"
                    )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS propiedad_ediciones (
                    id_edicion INT AUTO_INCREMENT PRIMARY KEY,
                    id_propiedad INT NOT NULL,
                    id_arrendador INT NOT NULL,
                    datos LONGTEXT NOT NULL,
                    fecha TIMESTAMP NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_edicion_propiedad (id_propiedad)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS solicitudes_rol (
                    id_solicitud_rol INT AUTO_INCREMENT PRIMARY KEY,
                    id_usuario INT NOT NULL,
                    rol_solicitado VARCHAR(20) NOT NULL
                        DEFAULT 'arrendador',
                    estado ENUM('pendiente', 'aprobada', 'rechazada')
                        NOT NULL DEFAULT 'pendiente',
                    motivo_rechazo VARCHAR(255) NULL,
                    fecha_solicitud TIMESTAMP NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    fecha_revision TIMESTAMP NULL,
                    id_revisor INT NULL,
                    INDEX idx_solrol_usuario (id_usuario),
                    INDEX idx_solrol_estado (estado)
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS migraciones_app (
                    nombre VARCHAR(80) PRIMARY KEY
                )
                """
            )

            # IMPORTANTE: esta función ya NO borra propiedades, fotos,
            # favoritos, amenidades ni comentarios. Solo agrega lo que
            # falta (columnas, tablas, tipos e índices únicos).
            conexion.commit()

            self._asegurar_indice_unico(
                cursor, "usuarios", "uq_usuarios_usuario", "usuario"
            )
            self._asegurar_indice_unico(
                cursor, "propiedades", "uq_propiedades_solicitud",
                "id_solicitud"
            )

            conexion.commit()
            cursor.close()

        except Exception as e:
            logger.error("Error preparando la base de datos: %s", e)
            print("Error preparando la base de datos:", e)

            try:
                conexion.rollback()
            except Exception:
                pass

        finally:
            self.desconectar(conexion)

    def conectar(self):
        return self.conexion_bd.conectar()

    def desconectar(self, conexion):
        self.conexion_bd.desconectar(conexion)

    def ejecutar_consulta(self, consulta, parametros=None):
        conexion = self.conectar()

        if conexion is None:
            return []

        try:
            cursor = conexion.cursor(dictionary=True)

            if parametros:
                cursor.execute(consulta, parametros)
            else:
                cursor.execute(consulta)

            resultados = cursor.fetchall()

            cursor.close()
            self.desconectar(conexion)

            return resultados

        except Exception as e:
            self._registrar_error("consulta", e)
            self.desconectar(conexion)
            return []

    def ejecutar(self, consulta, parametros=None):
        conexion = self.conectar()

        if conexion is None:
            return False

        try:
            cursor = conexion.cursor()

            if parametros:
                cursor.execute(consulta, parametros)
            else:
                cursor.execute(consulta)

            conexion.commit()

            cursor.close()
            self.desconectar(conexion)

            return True

        except Exception as e:
            self._registrar_error("ejecutar", e)

            try:
                conexion.rollback()
            except:
                pass

            self.desconectar(conexion)

            return False

    def insertar(self, consulta, parametros=None):
        """Ejecuta un INSERT y devuelve el id generado (o None)."""

        conexion = self.conectar()

        if conexion is None:
            return None

        try:
            cursor = conexion.cursor()
            cursor.execute(consulta, parametros or ())
            conexion.commit()
            nuevo_id = cursor.lastrowid
            cursor.close()
            self.desconectar(conexion)
            return nuevo_id

        except Exception as e:
            self._registrar_error("insertar", e)

            try:
                conexion.rollback()
            except Exception:
                pass

            self.desconectar(conexion)
            return None

    # ------------------------------------------------------------
    # Utilidades internas: errores, transacciones y permisos
    # ------------------------------------------------------------

    def _registrar_error(self, contexto, e):

        self.ultimo_error_codigo = getattr(e, "errno", None)

        logger.error("Error en %s: %s", contexto, e)
        print(f"Error en {contexto}:", e)

    def _asegurar_indice_unico(self, cursor, tabla, nombre, columna):
        """Crea un índice UNIQUE solo si no hay datos repetidos.
        Nunca borra ni modifica registros: si hay duplicados, avisa."""

        try:
            cursor.execute(
                """
                SELECT COUNT(*) FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = %s AND COLUMN_NAME = %s
                AND NON_UNIQUE = 0
                """,
                (tabla, columna)
            )

            if cursor.fetchone()[0] > 0:
                return

            cursor.execute(
                f"SELECT COUNT(*) FROM (SELECT {columna} FROM {tabla} "
                f"WHERE {columna} IS NOT NULL "
                f"GROUP BY {columna} HAVING COUNT(*) > 1) d"
            )

            if cursor.fetchone()[0] > 0:
                logger.warning(
                    "No se creó el índice único de %s.%s: hay valores "
                    "repetidos. Ejecuta auditoria_integridad.py.",
                    tabla, columna
                )
                return

            cursor.execute(
                f"ALTER TABLE {tabla} "
                f"ADD UNIQUE INDEX {nombre} ({columna})"
            )

        except Exception as e:
            logger.warning(
                "No se pudo asegurar el índice único %s: %s", nombre, e
            )

    @contextmanager
    def transaccion(self):
        """Una sola conexión: o se guardan TODOS los pasos o ninguno.

            with dao.transaccion() as cur:
                cur.execute(...)
        """

        conexion = self.conectar()

        if conexion is None:
            raise ErrorBD("No hay conexión con la base de datos.")

        cursor = None

        try:
            cursor = conexion.cursor(dictionary=True)
            yield cursor
            conexion.commit()

        except Exception as e:

            try:
                conexion.rollback()
            except Exception:
                pass

            self._registrar_error("transacción", e)
            raise

        finally:

            try:
                if cursor is not None:
                    cursor.close()
            finally:
                self.desconectar(conexion)

    def _es_admin(self, id_usuario):

        if not id_usuario:
            return False

        return len(self.ejecutar_consulta(
            "SELECT 1 FROM usuarios WHERE id_usuario = %s "
            "AND rol = 'administrador' AND activo = TRUE LIMIT 1",
            (id_usuario,)
        )) > 0

    def _usuario_activo(self, id_usuario):

        if not id_usuario:
            return False

        return len(self.ejecutar_consulta(
            "SELECT 1 FROM usuarios WHERE id_usuario = %s "
            "AND activo = TRUE LIMIT 1",
            (id_usuario,)
        )) > 0

    def _existe_propiedad(self, id_propiedad):

        if not id_propiedad:
            return False

        return len(self.ejecutar_consulta(
            "SELECT 1 FROM propiedades WHERE id_propiedad = %s "
            "LIMIT 1",
            (id_propiedad,)
        )) > 0

    def existe_usuario(self, usuario):
        """True si el nombre de usuario ya existe (activo o no)."""

        return len(self.ejecutar_consulta(
            "SELECT 1 FROM usuarios WHERE usuario = %s LIMIT 1",
            ((usuario or "").strip(),)
        )) > 0

    def actualizar_hash_contrasena(self, id_usuario, contrasena):
        """Cambia una contraseña antigua (sin cifrar) por su hash bcrypt."""

        hash_nuevo = bcrypt.hashpw(
            contrasena.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        return self.ejecutar(
            "UPDATE usuarios SET contrasena = %s "
            "WHERE id_usuario = %s",
            (hash_nuevo, id_usuario)
        )

    def obtener_usuario(self, usuario):
        consulta = """
            SELECT
                id_usuario,
                nombre,
                usuario,
                contrasena,
                rol,
                activo
            FROM usuarios
            WHERE usuario = %s
            AND activo = TRUE
            LIMIT 1
        """

        resultados = self.ejecutar_consulta(
            consulta,
            (usuario,)
        )

        if resultados:
            return resultados[0]

        return None

    def verificar_contrasena(self, contrasena, contrasena_guardada):

        if not contrasena or not contrasena_guardada:
            return False

        guardada = str(contrasena_guardada)

        if guardada.startswith(("$2a$", "$2b$", "$2y$")):

            try:
                return bcrypt.checkpw(
                    contrasena.encode("utf-8"),
                    guardada.encode("utf-8")
                )
            except Exception:
                return False

        # Cuentas muy antiguas con la contraseña sin cifrar.
        return hmac.compare_digest(
            contrasena.encode("utf-8"),
            guardada.encode("utf-8")
        )

    # Roles que una persona puede elegir al registrarse.
    # El rol 'administrador' NUNCA se puede crear desde el registro;
    # se asigna directamente en la base de datos (ver migracion_roles.sql).
    ROLES_REGISTRO = ("estudiante", "arrendador")

    def registrar_usuario(
        self,
        nombre,
        usuario,
        contrasena,
        rol="estudiante"
    ):

        if rol not in self.ROLES_REGISTRO:
            return False

        nombre, e1 = val.validar_nombre(nombre)
        usuario, e2 = val.validar_usuario(usuario)
        contrasena, e3 = val.validar_contrasena(contrasena)

        if e1 or e2 or e3:
            self.ultimo_error_mensaje = e1 or e2 or e3
            return False

        # Incluye cuentas desactivadas: no se puede repetir el usuario.
        if self.existe_usuario(usuario):
            self.ultimo_error_mensaje = "Ese usuario ya está registrado."
            return False

        hash_contrasena = bcrypt.hashpw(
            contrasena.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        # Quien pide ser arrendador NO recibe ese rol al instante: la
        # cuenta se crea como estudiante y se envía una solicitud al
        # administrador. Cuenta y solicitud se guardan juntas o ninguna.
        pide_arrendador = (rol == "arrendador")

        self.ultimo_error_codigo = None

        try:
            with self.transaccion() as cur:

                cur.execute(
                    """
                    INSERT INTO usuarios
                    (nombre, usuario, contrasena, rol)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (nombre, usuario, hash_contrasena, "estudiante")
                )

                if pide_arrendador:
                    cur.execute(
                        """
                        INSERT INTO solicitudes_rol
                        (id_usuario, rol_solicitado)
                        VALUES (%s, 'arrendador')
                        """,
                        (cur.lastrowid,)
                    )

        except Exception:

            if self.ultimo_error_codigo == 1062:
                self.ultimo_error_mensaje = (
                    "Ese usuario ya está registrado."
                )

            return False

        return True

    # ------------------------------------------------------------
    # Solicitudes de permiso para ser arrendador
    # ------------------------------------------------------------

    def obtener_solicitud_rol_usuario(self, id_usuario):
        """Última solicitud de rol de la persona (o None)."""

        filas = self.ejecutar_consulta(
            """
            SELECT id_solicitud_rol, estado, motivo_rechazo,
                   fecha_solicitud
            FROM solicitudes_rol
            WHERE id_usuario = %s
            ORDER BY id_solicitud_rol DESC
            LIMIT 1
            """,
            (id_usuario,)
        )

        return filas[0] if filas else None

    def crear_solicitud_rol(self, id_usuario):
        """Un estudiante activo pide ser arrendador (una sola
        solicitud pendiente a la vez)."""

        self.ultimo_error_mensaje = None

        if not self.ejecutar_consulta(
            "SELECT 1 FROM usuarios WHERE id_usuario = %s "
            "AND rol = 'estudiante' AND activo = TRUE LIMIT 1",
            (id_usuario,)
        ):
            self.ultimo_error_mensaje = (
                "Solo un estudiante puede pedir ser arrendador."
            )
            return False

        try:
            with self.transaccion() as cur:

                cur.execute(
                    """
                    INSERT INTO solicitudes_rol
                    (id_usuario, rol_solicitado)
                    SELECT %s, 'arrendador' FROM DUAL
                    WHERE NOT EXISTS (
                        SELECT 1 FROM solicitudes_rol
                        WHERE id_usuario = %s
                        AND estado = 'pendiente'
                    )
                    """,
                    (id_usuario, id_usuario)
                )

                if cur.rowcount == 0:
                    self.ultimo_error_mensaje = (
                        "Ya tienes una solicitud en revisión."
                    )
                    return False

        except Exception:
            return False

        return True

    def obtener_solicitudes_rol(self, solo_pendientes=True):
        """Solicitudes de permiso de arrendador (para el admin)."""

        filtro = (
            "WHERE r.estado = 'pendiente'" if solo_pendientes else ""
        )

        return self.ejecutar_consulta(
            f"""
            SELECT r.id_solicitud_rol, r.id_usuario, r.estado,
                   r.motivo_rechazo, r.fecha_solicitud,
                   u.nombre, u.usuario
            FROM solicitudes_rol r
            JOIN usuarios u ON u.id_usuario = r.id_usuario
            {filtro}
            ORDER BY (r.estado = 'pendiente') DESC,
                     r.id_solicitud_rol DESC
            """
        )

    def resolver_solicitud_rol(
        self,
        id_solicitud_rol,
        aprobar,
        id_revisor,
        motivo=None
    ):
        """Solo un administrador. Al aprobar, el usuario pasa a
        'arrendador' en la MISMA transacción."""

        self.ultimo_error_mensaje = None

        if not self._es_admin(id_revisor):
            self.ultimo_error_mensaje = "No tienes permiso."
            return False

        motivo = (motivo or "").strip()[:255] or None

        estado = "aprobada" if aprobar else "rechazada"

        try:
            with self.transaccion() as cur:

                cur.execute(
                    """
                    SELECT id_usuario FROM solicitudes_rol
                    WHERE id_solicitud_rol = %s
                    AND estado = 'pendiente'
                    """,
                    (id_solicitud_rol,)
                )

                fila = cur.fetchone()

                if not fila:
                    self.ultimo_error_mensaje = (
                        "La solicitud ya fue revisada."
                    )
                    return False

                cur.execute(
                    """
                    UPDATE solicitudes_rol
                    SET estado = %s,
                        motivo_rechazo = %s,
                        fecha_revision = NOW(),
                        id_revisor = %s
                    WHERE id_solicitud_rol = %s
                    AND estado = 'pendiente'
                    """,
                    (
                        estado,
                        None if aprobar else motivo,
                        id_revisor,
                        id_solicitud_rol
                    )
                )

                if cur.rowcount == 0:
                    self.ultimo_error_mensaje = (
                        "La solicitud ya fue revisada."
                    )
                    return False

                if aprobar:
                    cur.execute(
                        """
                        UPDATE usuarios SET rol = 'arrendador'
                        WHERE id_usuario = %s AND rol = 'estudiante'
                        """,
                        (fila["id_usuario"],)
                    )

        except Exception:
            return False

        return True

    def obtener_universidades(self):

        consulta = """
            SELECT
                id_universidad,
                nombre,
                descripcion
            FROM universidades
            ORDER BY nombre
        """

        return self.ejecutar_consulta(consulta)

    def obtener_tipos(self):

        consulta = """
            SELECT
                id_tipo,
                nombre
            FROM tipos_propiedad
            ORDER BY nombre
        """

        return self.ejecutar_consulta(consulta)

    def obtener_propiedades(
        self,
        texto="",
        tipo="Todos",
        universidad="Todas las universidades",
        precio_min=None,
        precio_max=None,
        zona="",
        amenidades=None
    ):
        """Búsqueda de alojamientos con todos los filtros combinados."""

        (pmin, pmax), error = val.validar_rango_precios(
            precio_min, precio_max
        )

        if error:
            self.ultimo_error_mensaje = error
            return []

        consulta, parametros = construir_consulta_propiedades(
            texto, tipo, universidad, pmin, pmax, zona, amenidades
        )

        propiedades = self.ejecutar_consulta(consulta, parametros)

        self._agregar_amenidades(propiedades)

        return propiedades

    def _agregar_amenidades(self, propiedades):
        """Agrega la lista 'amenidades' a cada propiedad (1 sola consulta)."""

        if not propiedades:
            return

        ids = [p["id_propiedad"] for p in propiedades]

        marcadores = ", ".join(["%s"] * len(ids))

        filas = self.ejecutar_consulta(
            "SELECT pa.id_propiedad, a.nombre "
            "FROM propiedad_amenidad pa "
            "INNER JOIN amenidades a "
            "ON pa.id_amenidad = a.id_amenidad "
            f"WHERE pa.id_propiedad IN ({marcadores}) "
            "ORDER BY a.nombre",
            tuple(ids)
        )

        por_propiedad = {}

        for fila in filas:
            por_propiedad.setdefault(
                fila["id_propiedad"], []
            ).append(fila["nombre"])

        for propiedad in propiedades:
            propiedad["amenidades"] = por_propiedad.get(
                propiedad["id_propiedad"], []
            )

    def obtener_propiedad(self, id_propiedad):

        consulta = """
            SELECT
                p.id_propiedad,
                p.titulo,
                p.zona,
                p.id_universidad,
                u.nombre AS universidad,
                p.distancia,
                p.precio,
                p.id_tipo,
                t.nombre AS tipo,
                p.verificado,
                p.disponible,
                p.direccion,
                p.descripcion,
                p.habitaciones,
                p.banos,
                p.telefono,
                p.camas,
                p.id_arrendador
            FROM propiedades p
            INNER JOIN universidades u
                ON p.id_universidad = u.id_universidad
            INNER JOIN tipos_propiedad t
                ON p.id_tipo = t.id_tipo
            WHERE p.id_propiedad = %s
            LIMIT 1
        """

        resultados = self.ejecutar_consulta(
            consulta,
            (id_propiedad,)
        )

        if not resultados:
            return None

        propiedad = resultados[0]

        consulta_amenidades = """
            SELECT
                a.nombre
            FROM amenidades a
            INNER JOIN propiedad_amenidad pa
                ON a.id_amenidad = pa.id_amenidad
            WHERE pa.id_propiedad = %s
            ORDER BY a.nombre
        """

        amenidades = self.ejecutar_consulta(
            consulta_amenidades,
            (id_propiedad,)
        )

        propiedad["amenidades"] = [
            a["nombre"]
            for a in amenidades
        ]

        return propiedad

    def agregar_favorito(self, id_usuario, id_propiedad):

        if not self._usuario_activo(id_usuario):
            return False

        propiedad = self.ejecutar_consulta(
            "SELECT 1 FROM propiedades WHERE id_propiedad = %s "
            "AND disponible = TRUE LIMIT 1",
            (id_propiedad,)
        )

        if not propiedad:
            return False

        # Si ya era favorito no se duplica (y tampoco es un error).
        return self.ejecutar(
            """
            INSERT INTO favoritos (id_usuario, id_propiedad)
            SELECT %s, %s FROM DUAL
            WHERE NOT EXISTS (
                SELECT 1 FROM favoritos
                WHERE id_usuario = %s AND id_propiedad = %s
            )
            """,
            (id_usuario, id_propiedad, id_usuario, id_propiedad)
        )

    def quitar_favorito(self, id_usuario, id_propiedad):

        consulta = """
            DELETE FROM favoritos
            WHERE id_usuario = %s
            AND id_propiedad = %s
        """

        return self.ejecutar(
            consulta,
            (
                id_usuario,
                id_propiedad
            )
        )

    def es_favorito(self, id_usuario, id_propiedad):

        consulta = """
            SELECT
                id_usuario,
                id_propiedad
            FROM favoritos
            WHERE id_usuario = %s
            AND id_propiedad = %s
            LIMIT 1
        """

        resultados = self.ejecutar_consulta(
            consulta,
            (
                id_usuario,
                id_propiedad
            )
        )

        return len(resultados) > 0

    def obtener_favoritos(self, id_usuario):

        consulta = """
            SELECT
                p.id_propiedad,
                p.titulo,
                p.zona,
                u.nombre AS universidad,
                p.distancia,
                p.precio,
                t.nombre AS tipo,
                p.verificado,
                p.disponible,
                p.direccion,
                p.descripcion,
                p.habitaciones,
                p.banos,
                p.telefono,
                p.camas
            FROM favoritos f
            INNER JOIN propiedades p
                ON f.id_propiedad = p.id_propiedad
            INNER JOIN universidades u
                ON p.id_universidad = u.id_universidad
            INNER JOIN tipos_propiedad t
                ON p.id_tipo = t.id_tipo
            WHERE f.id_usuario = %s
            AND p.disponible = TRUE
            ORDER BY f.fecha_agregado DESC
        """

        propiedades = self.ejecutar_consulta(
            consulta,
            (id_usuario,)
        )

        for propiedad in propiedades:

            consulta_amenidades = """
                SELECT
                    a.nombre
                FROM amenidades a
                INNER JOIN propiedad_amenidad pa
                    ON a.id_amenidad = pa.id_amenidad
                WHERE pa.id_propiedad = %s
            """

            amenidades = self.ejecutar_consulta(
                consulta_amenidades,
                (propiedad["id_propiedad"],)
            )

            propiedad["amenidades"] = [
                a["nombre"]
                for a in amenidades
            ]

        return propiedades

    def agregar_comentario(
        self,
        id_usuario,
        comentario,
        id_propiedad=None,
        calificacion=None
    ):

        texto, error = val.validar_texto(
            comentario, 1, val.MAX_COMENTARIO, "El comentario"
        )

        nota, error_nota = val.validar_calificacion(calificacion)

        if error or error_nota:
            self.ultimo_error_mensaje = error or error_nota
            return False

        if not self._usuario_activo(id_usuario):
            return False

        if id_propiedad is not None and not self._existe_propiedad(
            id_propiedad
        ):
            self.ultimo_error_mensaje = "La propiedad ya no existe."
            return False

        return self.ejecutar(
            """
            INSERT INTO comentarios
            (id_usuario, id_propiedad, calificacion, comentario)
            VALUES (%s, %s, %s, %s)
            """,
            (id_usuario, id_propiedad, nota, texto)
        )

    def obtener_comentarios(self):

        consulta = """
            SELECT
                c.id_comentario,
                c.id_usuario,
                u.usuario,
                u.nombre,
                c.id_propiedad,
                p.titulo,
                c.calificacion,
                c.comentario,
                c.fecha_comentario
            FROM comentarios c
            INNER JOIN usuarios u
                ON c.id_usuario = u.id_usuario
            LEFT JOIN propiedades p
                ON c.id_propiedad = p.id_propiedad
            ORDER BY c.fecha_comentario DESC
        """

        return self.ejecutar_consulta(consulta)

    def obtener_comentarios_propiedad(
        self,
        id_propiedad
    ):

        consulta = """
            SELECT
                c.id_comentario,
                c.id_usuario,
                u.usuario,
                u.nombre,
                c.calificacion,
                c.comentario,
                c.fecha_comentario
            FROM comentarios c
            INNER JOIN usuarios u
                ON c.id_usuario = u.id_usuario
            WHERE c.id_propiedad = %s
            ORDER BY c.fecha_comentario DESC
        """

        return self.ejecutar_consulta(
            consulta,
            (id_propiedad,)
        )

    def obtener_comentarios_usuario(
        self,
        id_usuario
    ):

        consulta = """
            SELECT
                c.id_comentario,
                c.id_propiedad,
                p.titulo,
                c.calificacion,
                c.comentario,
                c.fecha_comentario
            FROM comentarios c
            LEFT JOIN propiedades p
                ON c.id_propiedad = p.id_propiedad
            WHERE c.id_usuario = %s
            ORDER BY c.fecha_comentario DESC
        """

        return self.ejecutar_consulta(
            consulta,
            (id_usuario,)
        )

    def enviar_mensaje(
        self,
        id_remitente,
        id_destinatario,
        mensaje,
        id_propiedad=None
    ):

        texto, error = val.validar_texto(
            mensaje, 1, val.MAX_MENSAJE, "El mensaje"
        )

        if error or id_remitente == id_destinatario:
            self.ultimo_error_mensaje = error or (
                "No puedes enviarte un mensaje a ti mismo."
            )
            return False

        if not (
            self._usuario_activo(id_remitente)
            and self._usuario_activo(id_destinatario)
        ):
            return False

        if id_propiedad is not None and not self._existe_propiedad(
            id_propiedad
        ):
            return False

        return self.ejecutar(
            """
            INSERT INTO mensajes
            (id_remitente, id_destinatario, id_propiedad, mensaje)
            VALUES (%s, %s, %s, %s)
            """,
            (id_remitente, id_destinatario, id_propiedad, texto)
        )

    def obtener_mensajes(self, id_usuario):

        consulta = """
            SELECT
                m.id_mensaje,
                m.id_remitente,
                ur.usuario AS remitente,
                ur.nombre AS nombre_remitente,
                m.id_destinatario,
                ud.usuario AS destinatario,
                ud.nombre AS nombre_destinatario,
                m.id_propiedad,
                p.titulo,
                m.mensaje,
                m.fecha_envio,
                m.leido
            FROM mensajes m
            INNER JOIN usuarios ur
                ON m.id_remitente = ur.id_usuario
            INNER JOIN usuarios ud
                ON m.id_destinatario = ud.id_usuario
            LEFT JOIN propiedades p
                ON m.id_propiedad = p.id_propiedad
            WHERE
                m.id_remitente = %s
                OR m.id_destinatario = %s
            ORDER BY m.fecha_envio DESC
        """

        return self.ejecutar_consulta(
            consulta,
            (
                id_usuario,
                id_usuario
            )
        )

    def marcar_mensaje_leido(self, id_mensaje):

        consulta = """
            UPDATE mensajes
            SET leido = TRUE
            WHERE id_mensaje = %s
        """

        return self.ejecutar(
            consulta,
            (id_mensaje,)
        )

    # ------------------------------------------------------------
    # Interfaz personalizada por usuario
    # ------------------------------------------------------------

    def obtener_color_interfaz(self, id_usuario):

        resultados = self.ejecutar_consulta(
            "SELECT color_interfaz FROM usuarios "
            "WHERE id_usuario = %s LIMIT 1",
            (id_usuario,)
        )

        if resultados and resultados[0]["color_interfaz"]:
            return resultados[0]["color_interfaz"]

        return None

    def guardar_color_interfaz(self, id_usuario, color):

        return self.ejecutar(
            "UPDATE usuarios SET color_interfaz = %s "
            "WHERE id_usuario = %s",
            (color, id_usuario)
        )

    # ------------------------------------------------------------
    # Verificación de arrendadores
    # ------------------------------------------------------------

    def crear_solicitud_arrendador(
        self,
        id_usuario,
        direccion,
        descripcion,
        imagen,
        id_tipo=None,
        precio=None,
        id_universidad=None,
        distancia=None,
        telefono=None
    ):
        """Un arrendador pide publicar una propiedad. Devuelve True si
        la solicitud quedó guardada (queda 'pendiente' hasta que un
        administrador la apruebe)."""

        self.ultimo_error_mensaje = None

        usuario = self.ejecutar_consulta(
            "SELECT rol FROM usuarios WHERE id_usuario = %s "
            "AND activo = TRUE LIMIT 1",
            (id_usuario,)
        )

        if not usuario or usuario[0]["rol"] != "arrendador":
            self.ultimo_error_mensaje = (
                "Solo los arrendadores pueden enviar solicitudes."
            )
            return False

        direccion = (direccion or "").strip()

        if direccion:
            direccion, error = val.validar_texto(
                direccion, 8, val.MAX_DIRECCION, "La dirección"
            )
            if error:
                self.ultimo_error_mensaje = error
                return False

        if imagen:
            imagen, error = val.validar_foto(imagen)
            if error:
                self.ultimo_error_mensaje = error
                return False
        else:
            imagen = None

        if not direccion and not imagen:
            self.ultimo_error_mensaje = (
                "Agrega al menos la dirección o una foto de la casa."
            )
            return False

        descripcion, error = val.validar_texto(
            descripcion, 0, val.MAX_DESCRIPCION, "La descripción",
            obligatorio=False
        )
        if error:
            self.ultimo_error_mensaje = error
            return False

        precio, error = val.validar_precio(precio)
        if error:
            self.ultimo_error_mensaje = error
            return False

        telefono, error = val.validar_telefono(telefono)
        if error:
            self.ultimo_error_mensaje = error
            return False

        distancia, error = val.validar_texto(
            distancia, 1, val.MAX_DISTANCIA, "La distancia",
            obligatorio=False
        )
        if error:
            self.ultimo_error_mensaje = error
            return False

        if not id_tipo or not id_universidad:
            self.ultimo_error_mensaje = (
                "Falta elegir el tipo y la universidad."
            )
            return False

        existe_tipo = self.ejecutar_consulta(
            "SELECT 1 FROM tipos_propiedad WHERE id_tipo = %s LIMIT 1",
            (id_tipo,)
        )
        existe_uni = self.ejecutar_consulta(
            "SELECT 1 FROM universidades WHERE id_universidad = %s "
            "LIMIT 1",
            (id_universidad,)
        )

        if not existe_tipo or not existe_uni:
            self.ultimo_error_mensaje = (
                "El tipo o la universidad elegida no existe."
            )
            return False

        try:
            with self.transaccion() as cur:

                # Una sola instrucción: no se crean dos pendientes
                # aunque se envíe dos veces al mismo tiempo.
                cur.execute(
                    """
                    INSERT INTO solicitudes_arrendador
                    (
                        id_usuario, direccion, descripcion, imagen,
                        id_tipo, precio, id_universidad, distancia,
                        telefono
                    )
                    SELECT %s, %s, %s, %s, %s, %s, %s, %s, %s
                    FROM DUAL
                    WHERE NOT EXISTS (
                        SELECT 1 FROM solicitudes_arrendador
                        WHERE id_usuario = %s AND estado = 'pendiente'
                    )
                    """,
                    (
                        id_usuario,
                        direccion or None,
                        descripcion or None,
                        imagen,
                        id_tipo,
                        precio,
                        id_universidad,
                        distancia or None,
                        telefono or None,
                        id_usuario
                    )
                )

                creada = cur.rowcount > 0

        except Exception:
            return False

        if not creada:
            self.ultimo_error_mensaje = (
                "Ya tienes una solicitud en espera."
            )

        return creada

    def obtener_solicitud_usuario(self, id_usuario):

        resultados = self.ejecutar_consulta(
            """
            SELECT
                s.id_solicitud,
                s.id_usuario,
                s.direccion,
                s.descripcion,
                s.estado,
                s.motivo_rechazo,
                s.fecha_solicitud,
                s.precio,
                s.distancia,
                s.telefono,
                t.nombre AS tipo,
                un.nombre AS universidad,
                (s.imagen IS NOT NULL) AS tiene_imagen
            FROM solicitudes_arrendador s
            LEFT JOIN tipos_propiedad t
                ON s.id_tipo = t.id_tipo
            LEFT JOIN universidades un
                ON s.id_universidad = un.id_universidad
            WHERE s.id_usuario = %s
            ORDER BY s.id_solicitud DESC
            LIMIT 1
            """,
            (id_usuario,)
        )

        if resultados:
            return resultados[0]

        return None

    def obtener_imagen_solicitud(self, id_solicitud):

        resultados = self.ejecutar_consulta(
            "SELECT imagen FROM solicitudes_arrendador "
            "WHERE id_solicitud = %s LIMIT 1",
            (id_solicitud,)
        )

        if resultados and resultados[0]["imagen"]:
            return bytes(resultados[0]["imagen"])

        return None

    def obtener_solicitudes(self, solo_pendientes=True):

        consulta = """
            SELECT
                s.id_solicitud,
                s.id_usuario,
                u.nombre,
                u.usuario,
                s.direccion,
                s.descripcion,
                s.estado,
                s.motivo_rechazo,
                s.fecha_solicitud,
                s.precio,
                s.distancia,
                s.telefono,
                t.nombre AS tipo,
                un.nombre AS universidad,
                (s.imagen IS NOT NULL) AS tiene_imagen
            FROM solicitudes_arrendador s
            INNER JOIN usuarios u
                ON s.id_usuario = u.id_usuario
            LEFT JOIN tipos_propiedad t
                ON s.id_tipo = t.id_tipo
            LEFT JOIN universidades un
                ON s.id_universidad = un.id_universidad
        """

        if solo_pendientes:
            consulta += " WHERE s.estado = 'pendiente' "

        consulta += " ORDER BY s.id_solicitud DESC"

        return self.ejecutar_consulta(consulta)

    def resolver_solicitud(
        self,
        id_solicitud,
        aprobar,
        id_revisor,
        motivo=None
    ):
        """Solo un administrador. Al aprobar, la propiedad se publica
        en la MISMA transacción: si falla algo, la solicitud sigue
        pendiente (no queda 'aprobada' sin propiedad)."""

        self.ultimo_error_mensaje = None

        if not self._es_admin(id_revisor):
            self.ultimo_error_mensaje = "No tienes permiso."
            return False

        motivo = (motivo or "").strip()[:255] or None

        estado = "aprobada" if aprobar else "rechazada"

        try:
            with self.transaccion() as cur:

                cur.execute(
                    """
                    UPDATE solicitudes_arrendador
                    SET estado = %s,
                        motivo_rechazo = %s,
                        fecha_revision = NOW(),
                        id_revisor = %s
                    WHERE id_solicitud = %s
                    AND estado = 'pendiente'
                    """,
                    (estado, motivo, id_revisor, id_solicitud)
                )

                if cur.rowcount == 0:
                    self.ultimo_error_mensaje = (
                        "La solicitud ya fue revisada."
                    )
                    return False

                if aprobar and not self._publicar_en_cursor(
                    cur, id_solicitud
                ):
                    raise ErrorBD(
                        self.ultimo_error_mensaje
                        or "No se pudo publicar la propiedad."
                    )

        except Exception:
            return False

        return True

    def publicar_propiedad_de_solicitud(self, id_solicitud):
        """Crea la caja (propiedad) de una solicitud aprobada.
        Es idempotente: si ya existe no la duplica."""

        try:
            with self.transaccion() as cur:
                if not self._publicar_en_cursor(cur, id_solicitud):
                    raise ErrorBD(
                        self.ultimo_error_mensaje or "No se pudo publicar."
                    )
        except Exception:
            return False

        return True

    def _publicar_en_cursor(self, cur, id_solicitud):

        cur.execute(
            "SELECT id_propiedad FROM propiedades "
            "WHERE id_solicitud = %s LIMIT 1",
            (id_solicitud,)
        )

        if cur.fetchone():
            return True

        cur.execute(
            """
            SELECT id_usuario, direccion, precio, distancia,
                   id_tipo, id_universidad, descripcion, telefono
            FROM solicitudes_arrendador
            WHERE id_solicitud = %s LIMIT 1
            """,
            (id_solicitud,)
        )

        s = cur.fetchone()

        if not s:
            self.ultimo_error_mensaje = "La solicitud no existe."
            return False

        tipo = None
        universidad = None

        if s["id_tipo"]:
            cur.execute(
                "SELECT nombre FROM tipos_propiedad WHERE id_tipo = %s",
                (s["id_tipo"],)
            )
            tipo = cur.fetchone()

        if s["id_universidad"]:
            cur.execute(
                "SELECT 1 AS ok FROM universidades "
                "WHERE id_universidad = %s",
                (s["id_universidad"],)
            )
            universidad = cur.fetchone()

        # No se inventan datos: si la solicitud está incompleta
        # (solicitudes muy antiguas) no se publica.
        if not tipo or not universidad or not s["precio"]:
            self.ultimo_error_mensaje = (
                "La solicitud no tiene tipo, universidad o precio. "
                "Pide al arrendador que envíe una nueva solicitud."
            )
            return False

        zona = (s["direccion"] or "Sin dirección")[:100]
        titulo = f"{tipo['nombre']} en {zona}"[:100]

        cur.execute(
            """
            INSERT INTO propiedades
            (
                titulo, zona, id_universidad, distancia,
                precio, id_tipo, verificado, disponible,
                id_arrendador, id_solicitud,
                direccion, descripcion, telefono
            )
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, TRUE,
                    %s, %s, %s, %s, %s)
            """,
            (
                titulo,
                zona,
                s["id_universidad"],
                s["distancia"] or "Cerca de la universidad",
                s["precio"],
                s["id_tipo"],
                s["id_usuario"],
                id_solicitud,
                s["direccion"],
                s["descripcion"],
                s["telefono"]
            )
        )

        id_propiedad = cur.lastrowid

        if not id_propiedad:
            self.ultimo_error_mensaje = "No se pudo crear la propiedad."
            return False

        # La imagen enviada pasa a ser la primera foto (portada).
        cur.execute(
            """
            INSERT INTO propiedad_fotos
            (id_propiedad, imagen, orden, pendiente)
            SELECT %s, imagen, 0, 0
            FROM solicitudes_arrendador
            WHERE id_solicitud = %s AND imagen IS NOT NULL
            """,
            (id_propiedad, id_solicitud)
        )

        return True

    # ------------------------------------------------------------
    # Opciones del administrador
    # ------------------------------------------------------------

    def obtener_usuarios_por_rol(self, rol):

        if rol == "arrendador":
            verificacion = """
                (
                    SELECT s.estado
                    FROM solicitudes_arrendador s
                    WHERE s.id_usuario = u.id_usuario
                    ORDER BY s.id_solicitud DESC
                    LIMIT 1
                )
            """
        else:
            verificacion = "NULL"

        if rol == "arrendador":
            extra = """
                (
                    SELECT COUNT(*) FROM propiedades p
                    WHERE p.id_arrendador = u.id_usuario
                ) AS n_propiedades,
                0 AS n_comentarios,
                0 AS n_favoritos,
            """
        else:
            extra = """
                0 AS n_propiedades,
                (
                    SELECT COUNT(*) FROM comentarios c
                    WHERE c.id_usuario = u.id_usuario
                ) AS n_comentarios,
                (
                    SELECT COUNT(*) FROM favoritos f
                    WHERE f.id_usuario = u.id_usuario
                ) AS n_favoritos,
            """

        consulta = f"""
            SELECT
                u.id_usuario,
                u.nombre,
                u.usuario,
                u.activo,
                u.color_interfaz,
                {extra}
                {verificacion} AS verificacion
            FROM usuarios u
            WHERE u.rol = %s
            ORDER BY u.nombre
        """

        return self.ejecutar_consulta(consulta, (rol,))

    def cambiar_estado_usuario(self, id_usuario, activo, id_admin=None):

        # Solo un administrador; nunca se desactiva a un administrador
        # ni a uno mismo desde la app.
        if not self._es_admin(id_admin) or id_usuario == id_admin:
            return False

        return self.ejecutar(
            "UPDATE usuarios SET activo = %s "
            "WHERE id_usuario = %s AND rol <> 'administrador'",
            (bool(activo), id_usuario)
        )

    def eliminar_comentario(self, id_comentario, id_admin=None):

        if not self._es_admin(id_admin):
            return False

        return self.ejecutar(
            "DELETE FROM comentarios WHERE id_comentario = %s",
            (id_comentario,)
        )

    def obtener_resumen_admin(self):

        def contar(consulta):
            resultados = self.ejecutar_consulta(consulta)
            if resultados:
                return list(resultados[0].values())[0]
            return 0

        return {
            "estudiantes": contar(
                "SELECT COUNT(*) FROM usuarios "
                "WHERE rol = 'estudiante'"
            ),
            "arrendadores": contar(
                "SELECT COUNT(*) FROM usuarios "
                "WHERE rol = 'arrendador'"
            ),
            "pendientes": contar(
                "SELECT COUNT(*) FROM solicitudes_arrendador "
                "WHERE estado = 'pendiente'"
            ),
            "permisos": contar(
                "SELECT COUNT(*) FROM solicitudes_rol "
                "WHERE estado = 'pendiente'"
            ),
            "comentarios": contar(
                "SELECT COUNT(*) FROM comentarios"
            ),
            "cambios": contar(
                "SELECT COUNT(*) FROM propiedad_ediciones"
            )
        }

    # ------------------------------------------------------------
    # Propiedades y fotos del arrendador
    # ------------------------------------------------------------

    MAX_FOTOS = 8

    def obtener_reporte_admin(self, id_admin):
        """Datos para el PDF del administrador: usuarios por rol y,
        por arrendador, propiedades por tipo (aprobadas / pendientes).
        Solo lee. Devuelve None si quien pide no es administrador."""

        if not self._es_admin(id_admin):
            self.ultimo_error_mensaje = (
                "Solo un administrador puede generar el reporte."
            )
            return None

        def contar(rol):
            r = self.ejecutar_consulta(
                "SELECT COUNT(*) AS n FROM usuarios WHERE rol = %s",
                (rol,)
            )
            return r[0]["n"] if r else 0

        arrendadores = self.ejecutar_consulta(
            "SELECT id_usuario, nombre, usuario, activo FROM usuarios "
            "WHERE rol = 'arrendador' ORDER BY nombre"
        )

        detalle = {
            a["id_usuario"]: {
                "nombre": a["nombre"],
                "usuario": a["usuario"],
                "activo": bool(a["activo"]),
                "tipos": {}
            }
            for a in arrendadores
        }

        # Aprobadas = propiedades ya publicadas.
        for f in self.ejecutar_consulta(
            """
            SELECT p.id_arrendador AS id, t.nombre AS tipo,
                   COUNT(*) AS n
            FROM propiedades p
            INNER JOIN tipos_propiedad t ON p.id_tipo = t.id_tipo
            WHERE p.id_arrendador IS NOT NULL
            GROUP BY p.id_arrendador, t.nombre
            """
        ):
            if f["id"] in detalle:
                ap, pe = detalle[f["id"]]["tipos"].get(f["tipo"], (0, 0))
                detalle[f["id"]]["tipos"][f["tipo"]] = (ap + f["n"], pe)

        # Pendientes = solicitudes que aún no se revisan.
        for f in self.ejecutar_consulta(
            """
            SELECT s.id_usuario AS id,
                   COALESCE(t.nombre, 'Sin tipo') AS tipo,
                   COUNT(*) AS n
            FROM solicitudes_arrendador s
            LEFT JOIN tipos_propiedad t ON s.id_tipo = t.id_tipo
            WHERE s.estado = 'pendiente'
            GROUP BY s.id_usuario, COALESCE(t.nombre, 'Sin tipo')
            """
        ):
            if f["id"] in detalle:
                ap, pe = detalle[f["id"]]["tipos"].get(f["tipo"], (0, 0))
                detalle[f["id"]]["tipos"][f["tipo"]] = (ap, pe + f["n"])

        return {
            "estudiantes": contar("estudiante"),
            "arrendadores": contar("arrendador"),
            "arrendadores_detalle": list(detalle.values())
        }

    def obtener_amenidades(self):

        return self.ejecutar_consulta(
            "SELECT id_amenidad, nombre FROM amenidades "
            "ORDER BY nombre"
        )

    def arrendador_verificado(self, id_usuario):

        resultados = self.ejecutar_consulta(
            "SELECT 1 FROM solicitudes_arrendador "
            "WHERE id_usuario = %s AND estado = 'aprobada' "
            "LIMIT 1",
            (id_usuario,)
        )

        return len(resultados) > 0

    def obtener_propiedades_arrendador(self, id_arrendador):

        propiedades = self.ejecutar_consulta(
            """
            SELECT
                p.id_propiedad,
                p.titulo,
                p.zona,
                p.direccion,
                p.descripcion,
                p.habitaciones,
                p.banos,
                p.telefono,
                p.camas,
                p.id_universidad,
                u.nombre AS universidad,
                p.distancia,
                p.precio,
                p.id_tipo,
                t.nombre AS tipo,
                p.verificado,
                p.disponible,
                p.id_arrendador,
                (
                    SELECT COUNT(*) FROM propiedad_fotos f
                    WHERE f.id_propiedad = p.id_propiedad
                    AND f.pendiente = 0
                ) AS num_fotos,
                (
                    SELECT COUNT(*) FROM propiedad_ediciones e
                    WHERE e.id_propiedad = p.id_propiedad
                ) AS edicion_pendiente
            FROM propiedades p
            INNER JOIN universidades u
                ON p.id_universidad = u.id_universidad
            INNER JOIN tipos_propiedad t
                ON p.id_tipo = t.id_tipo
            WHERE p.id_arrendador = %s
            ORDER BY p.id_propiedad DESC
            """,
            (id_arrendador,)
        )

        self._agregar_amenidades(propiedades)

        return propiedades

    def obtener_amenidades_propiedad(self, id_propiedad):

        filas = self.ejecutar_consulta(
            """
            SELECT a.nombre
            FROM amenidades a
            INNER JOIN propiedad_amenidad pa
                ON a.id_amenidad = pa.id_amenidad
            WHERE pa.id_propiedad = %s
            ORDER BY a.nombre
            """,
            (id_propiedad,)
        )

        return [f["nombre"] for f in filas]

    def _guardar_amenidades_en_cursor(self, cur, id_propiedad, ids):
        """Reemplaza los servicios de la propiedad (dentro de la
        transacción). Ignora ids que no existen en 'amenidades'."""

        cur.execute(
            "DELETE FROM propiedad_amenidad WHERE id_propiedad = %s",
            (id_propiedad,)
        )

        ids = sorted({int(i) for i in (ids or [])})

        if not ids:
            return

        marcadores = ", ".join(["%s"] * len(ids))

        cur.execute(
            "INSERT INTO propiedad_amenidad (id_propiedad, id_amenidad) "
            f"SELECT %s, id_amenidad FROM amenidades "
            f"WHERE id_amenidad IN ({marcadores})",
            (id_propiedad, *ids)
        )

    def _guardar_amenidades(self, id_propiedad, ids_amenidades):

        try:
            with self.transaccion() as cur:
                self._guardar_amenidades_en_cursor(
                    cur, id_propiedad, ids_amenidades
                )
        except Exception:
            return False

        return True

    def _actualizar_en_cursor(self, cur, id_arrendador, id_propiedad, d):
        """UPDATE de la propiedad solo si es de su dueño. d ya validado."""

        cur.execute(
            "SELECT 1 AS ok FROM tipos_propiedad WHERE id_tipo = %s",
            (d["id_tipo"],)
        )
        if not cur.fetchone():
            raise ErrorBD("El tipo de propiedad no existe.")

        cur.execute(
            "SELECT 1 AS ok FROM universidades WHERE id_universidad = %s",
            (d["id_universidad"],)
        )
        if not cur.fetchone():
            raise ErrorBD("La universidad no existe.")

        cur.execute(
            """
            UPDATE propiedades
            SET titulo = %s, zona = %s, direccion = %s,
                descripcion = %s, habitaciones = %s, banos = %s,
                telefono = %s, camas = %s, id_universidad = %s,
                distancia = %s, precio = %s, id_tipo = %s
            WHERE id_propiedad = %s AND id_arrendador = %s
            """,
            (
                d["titulo"], d["zona"], d["direccion"],
                d["descripcion"] or None,
                d["habitaciones"], d["banos"],
                d["telefono"], d["camas"],
                d["id_universidad"], d["distancia"],
                d["precio"], d["id_tipo"],
                id_propiedad, id_arrendador
            )
        )

        self._guardar_amenidades_en_cursor(
            cur, id_propiedad, d["amenidades"]
        )

    def crear_propiedad_arrendador(self, id_arrendador, datos):
        """Ya no se publica directamente: toda propiedad nueva nace
        de una solicitud que el administrador debe aprobar
        (ver crear_solicitud_arrendador y resolver_solicitud)."""

        return None

    def actualizar_propiedad_arrendador(
        self,
        id_arrendador,
        id_propiedad,
        datos
    ):
        """Edita los datos de una propiedad. Solo su dueño."""

        datos, error = val.validar_datos_propiedad(datos)

        if error:
            self.ultimo_error_mensaje = error
            return False

        if not self.es_dueno_propiedad(id_arrendador, id_propiedad):
            return False

        try:
            with self.transaccion() as cur:
                self._actualizar_en_cursor(
                    cur, id_arrendador, id_propiedad, datos
                )
        except Exception:
            return False

        return True

    def guardar_cambios_propiedad(
        self,
        id_arrendador,
        id_propiedad,
        datos,
        fotos_nuevas,
        ids_conservar
    ):
        """Una propiedad ya aprobada la edita su dueño de forma
        independiente. Datos, servicios y fotos se guardan juntos:
        si algo falla no se cambia nada.

        fotos_nuevas: lista de bytes (fotos por agregar).
        ids_conservar: ids de fotos que se mantienen; el resto se borra.
        """

        self.ultimo_error_mensaje = None

        datos, error = val.validar_datos_propiedad(datos)

        if error:
            self.ultimo_error_mensaje = error
            return False

        nuevas = []

        for foto in fotos_nuevas or []:
            foto, error = val.validar_foto(foto)

            if error:
                self.ultimo_error_mensaje = error
                return False

            nuevas.append(foto)

        try:
            with self.transaccion() as cur:

                cur.execute(
                    "SELECT id_propiedad FROM propiedades "
                    "WHERE id_propiedad = %s AND id_arrendador = %s "
                    "FOR UPDATE",
                    (id_propiedad, id_arrendador)
                )

                if not cur.fetchone():
                    raise ErrorBD("La propiedad no es tuya.")

                cur.execute(
                    "SELECT id_foto FROM propiedad_fotos "
                    "WHERE id_propiedad = %s",
                    (id_propiedad,)
                )

                existentes = {f["id_foto"] for f in cur.fetchall()}

                conservar = {
                    int(i) for i in (ids_conservar or [])
                } & existentes

                if len(conservar) + len(nuevas) > self.MAX_FOTOS:
                    self.ultimo_error_mensaje = (
                        f"Máximo {self.MAX_FOTOS} fotos por propiedad."
                    )
                    raise ErrorBD(self.ultimo_error_mensaje)

                self._actualizar_en_cursor(
                    cur, id_arrendador, id_propiedad, datos
                )

                for id_foto in existentes - conservar:
                    cur.execute(
                        "DELETE FROM propiedad_fotos "
                        "WHERE id_foto = %s AND id_propiedad = %s",
                        (id_foto, id_propiedad)
                    )

                # Las fotos que se quedan ya son las publicadas.
                cur.execute(
                    "UPDATE propiedad_fotos SET pendiente = 0, "
                    "quitar = 0 WHERE id_propiedad = %s",
                    (id_propiedad,)
                )

                for foto in nuevas:
                    cur.execute(
                        "INSERT INTO propiedad_fotos "
                        "(id_propiedad, imagen, orden, pendiente) "
                        "SELECT %s, %s, COALESCE(MAX(orden), -1) + 1, 0 "
                        "FROM propiedad_fotos WHERE id_propiedad = %s",
                        (id_propiedad, foto, id_propiedad)
                    )

                # Borradores del sistema anterior (ya no se usan).
                cur.execute(
                    "DELETE FROM propiedad_ediciones "
                    "WHERE id_propiedad = %s",
                    (id_propiedad,)
                )

        except Exception:
            return False

        return True

    def es_dueno_propiedad(self, id_arrendador, id_propiedad):

        return len(self.ejecutar_consulta(
            "SELECT 1 FROM propiedades "
            "WHERE id_propiedad = %s AND id_arrendador = %s "
            "LIMIT 1",
            (id_propiedad, id_arrendador)
        )) > 0

    def cambiar_disponibilidad_propiedad(
        self,
        id_arrendador,
        id_propiedad,
        disponible
    ):

        return self.ejecutar(
            "UPDATE propiedades SET disponible = %s "
            "WHERE id_propiedad = %s AND id_arrendador = %s",
            (bool(disponible), id_propiedad, id_arrendador)
        )

    def eliminar_propiedad_arrendador(
        self,
        id_arrendador,
        id_propiedad
    ):
        """Elimina una propiedad de su dueño y lo que depende de ella,
        todo en una sola transacción. Las reseñas y mensajes NO se
        borran: solo pierden la referencia a la propiedad."""

        try:
            with self.transaccion() as cur:

                cur.execute(
                    "SELECT id_propiedad FROM propiedades "
                    "WHERE id_propiedad = %s AND id_arrendador = %s "
                    "FOR UPDATE",
                    (id_propiedad, id_arrendador)
                )

                if not cur.fetchone():
                    return False

                for consulta in (
                    "DELETE FROM propiedad_fotos "
                    "WHERE id_propiedad = %s",
                    "DELETE FROM propiedad_ediciones "
                    "WHERE id_propiedad = %s",
                    "DELETE FROM propiedad_amenidad "
                    "WHERE id_propiedad = %s",
                    "DELETE FROM favoritos WHERE id_propiedad = %s",
                    "UPDATE comentarios SET id_propiedad = NULL "
                    "WHERE id_propiedad = %s",
                    "UPDATE mensajes SET id_propiedad = NULL "
                    "WHERE id_propiedad = %s",
                ):
                    cur.execute(consulta, (id_propiedad,))

                cur.execute(
                    "DELETE FROM propiedades "
                    "WHERE id_propiedad = %s AND id_arrendador = %s",
                    (id_propiedad, id_arrendador)
                )

        except Exception:
            return False

        return True

    # --- Fotos -------------------------------------------------

    def agregar_foto_propiedad(
        self,
        id_propiedad,
        imagen,
        pendiente=False
    ):

        imagen, error = val.validar_foto(imagen)

        if error:
            self.ultimo_error_mensaje = error
            return False

        total = self.ejecutar_consulta(
            "SELECT COUNT(*) AS n FROM propiedad_fotos "
            "WHERE id_propiedad = %s",
            (id_propiedad,)
        )

        if total and total[0]["n"] >= self.MAX_FOTOS:
            self.ultimo_error_mensaje = (
                f"Máximo {self.MAX_FOTOS} fotos por propiedad."
            )
            return False

        return self.ejecutar(
            "INSERT INTO propiedad_fotos "
            "(id_propiedad, imagen, orden, pendiente) "
            "SELECT %s, %s, COALESCE(MAX(orden), -1) + 1, %s "
            "FROM propiedad_fotos WHERE id_propiedad = %s",
            (id_propiedad, imagen, 1 if pendiente else 0, id_propiedad)
        )

    def obtener_fotos_propiedad(self, id_propiedad, borrador=False):
        """Fotos de una propiedad.

        borrador=False: lo que ven los estudiantes (publicadas).
        borrador=True: lo que ve el arrendador al editar (sin las
        marcadas para quitar y con las nuevas por aprobar).
        Cada foto trae 'pendiente' (True si aún no está aprobada).
        """

        if borrador:
            filtro = "AND quitar = 0"
        else:
            filtro = "AND pendiente = 0"

        filas = self.ejecutar_consulta(
            "SELECT id_foto, imagen, pendiente FROM propiedad_fotos "
            f"WHERE id_propiedad = %s {filtro} "
            "ORDER BY pendiente, orden, id_foto",
            (id_propiedad,)
        )

        return [
            {
                "id_foto": f["id_foto"],
                "imagen": bytes(f["imagen"]),
                "pendiente": bool(f["pendiente"])
            }
            for f in filas
        ]

    def obtener_portada_propiedad(self, id_propiedad):

        filas = self.ejecutar_consulta(
            "SELECT imagen FROM propiedad_fotos "
            "WHERE id_propiedad = %s AND pendiente = 0 "
            "ORDER BY orden, id_foto LIMIT 1",
            (id_propiedad,)
        )

        if filas and filas[0]["imagen"]:
            return bytes(filas[0]["imagen"])

        return None

    def eliminar_foto_propiedad(self, id_arrendador, id_foto):
        """Borra una foto solo si la propiedad es del arrendador."""

        return self.ejecutar(
            """
            DELETE f FROM propiedad_fotos f
            INNER JOIN propiedades p
                ON f.id_propiedad = p.id_propiedad
            WHERE f.id_foto = %s
            AND p.id_arrendador = %s
            """,
            (id_foto, id_arrendador)
        )

    # --- Vista del administrador -------------------------------

    def obtener_propiedades_de_usuario_admin(self, id_arrendador):

        return self.obtener_propiedades_arrendador(id_arrendador)

    def cambiar_disponibilidad_admin(
        self, id_propiedad, disponible, id_admin=None
    ):

        if not self._es_admin(id_admin):
            return False

        return self.ejecutar(
            "UPDATE propiedades SET disponible = %s "
            "WHERE id_propiedad = %s",
            (bool(disponible), id_propiedad)
        )

    # ------------------------------------------------------------
    # Cambios de propiedades pendientes de revisión
    # ------------------------------------------------------------

    CAMPOS_EDICION = (
        "titulo", "zona", "direccion", "descripcion",
        "habitaciones", "banos", "id_universidad",
        "distancia", "precio", "id_tipo"
    )

    def descartar_edicion(self, id_propiedad):
        """Borra el borrador: fotos nuevas y marcas de quitar."""

        self.ejecutar(
            "DELETE FROM propiedad_fotos "
            "WHERE id_propiedad = %s AND pendiente = 1",
            (id_propiedad,)
        )
        self.ejecutar(
            "UPDATE propiedad_fotos SET quitar = 0 "
            "WHERE id_propiedad = %s",
            (id_propiedad,)
        )

        return self.ejecutar(
            "DELETE FROM propiedad_ediciones "
            "WHERE id_propiedad = %s",
            (id_propiedad,)
        )

    def cancelar_edicion_arrendador(self, id_arrendador, id_propiedad):

        if not self.es_dueno_propiedad(id_arrendador, id_propiedad):
            return False

        return self.descartar_edicion(id_propiedad)

    def solicitar_edicion_propiedad(
        self,
        id_arrendador,
        id_propiedad,
        datos,
        fotos_nuevas,
        ids_conservar
    ):
        """Guarda los cambios como borrador. Los estudiantes siguen
        viendo la versión publicada hasta que el administrador
        apruebe.

        fotos_nuevas: lista de bytes (fotos por agregar).
        ids_conservar: ids de fotos ya publicadas que se mantienen;
        las demás publicadas quedan marcadas para quitar.
        """

        if not self.es_dueno_propiedad(id_arrendador, id_propiedad):
            return False

        self.descartar_edicion(id_propiedad)

        contenido = {c: datos.get(c) for c in self.CAMPOS_EDICION}
        contenido["amenidades"] = list(datos.get("amenidades", []))

        guardada = self.ejecutar(
            "INSERT INTO propiedad_ediciones "
            "(id_propiedad, id_arrendador, datos) "
            "VALUES (%s, %s, %s)",
            (
                id_propiedad,
                id_arrendador,
                json.dumps(contenido, default=float)
            )
        )

        if not guardada:
            return False

        publicadas = self.ejecutar_consulta(
            "SELECT id_foto FROM propiedad_fotos "
            "WHERE id_propiedad = %s AND pendiente = 0",
            (id_propiedad,)
        )

        conservar = set(ids_conservar)

        for f in publicadas:

            if f["id_foto"] not in conservar:
                self.ejecutar(
                    "UPDATE propiedad_fotos SET quitar = 1 "
                    "WHERE id_foto = %s",
                    (f["id_foto"],)
                )

        for imagen in fotos_nuevas:
            self.agregar_foto_propiedad(
                id_propiedad,
                imagen,
                pendiente=True
            )

        return True

    def obtener_edicion_pendiente(self, id_propiedad):
        """Datos del borrador (dict) o None."""

        filas = self.ejecutar_consulta(
            "SELECT datos FROM propiedad_ediciones "
            "WHERE id_propiedad = %s LIMIT 1",
            (id_propiedad,)
        )

        if not filas:
            return None

        try:
            return json.loads(filas[0]["datos"])
        except Exception:
            return None

    def obtener_ediciones_pendientes(self):
        """Para el administrador: cada cambio por revisar, con la
        propiedad actual, el arrendador y las fotos afectadas."""

        filas = self.ejecutar_consulta(
            """
            SELECT
                e.id_edicion,
                e.id_propiedad,
                e.datos,
                e.fecha,
                u.nombre,
                u.usuario,
                p.titulo AS titulo_actual,
                p.zona AS zona_actual,
                p.direccion AS direccion_actual,
                p.descripcion AS descripcion_actual,
                p.habitaciones AS habitaciones_actual,
                p.banos AS banos_actual,
                p.distancia AS distancia_actual,
                p.precio AS precio_actual,
                p.id_tipo AS id_tipo_actual,
                p.id_universidad AS id_universidad_actual
            FROM propiedad_ediciones e
            INNER JOIN propiedades p
                ON e.id_propiedad = p.id_propiedad
            INNER JOIN usuarios u
                ON e.id_arrendador = u.id_usuario
            ORDER BY e.fecha ASC
            """
        )

        for fila in filas:

            try:
                fila["cambios"] = json.loads(fila["datos"])
            except Exception:
                fila["cambios"] = {}

            fila["fotos_nuevas"] = [
                bytes(f["imagen"])
                for f in self.ejecutar_consulta(
                    "SELECT imagen FROM propiedad_fotos "
                    "WHERE id_propiedad = %s AND pendiente = 1 "
                    "ORDER BY orden, id_foto",
                    (fila["id_propiedad"],)
                )
            ]

            quitadas = self.ejecutar_consulta(
                "SELECT COUNT(*) AS n FROM propiedad_fotos "
                "WHERE id_propiedad = %s AND quitar = 1",
                (fila["id_propiedad"],)
            )

            fila["fotos_quitadas"] = (
                quitadas[0]["n"] if quitadas else 0
            )

        return filas

    def resolver_edicion(self, id_edicion, aprobar, id_admin=None):

        if not self._es_admin(id_admin):
            return False

        filas = self.ejecutar_consulta(
            "SELECT id_propiedad, datos FROM propiedad_ediciones "
            "WHERE id_edicion = %s LIMIT 1",
            (id_edicion,)
        )

        if not filas:
            return False

        id_propiedad = filas[0]["id_propiedad"]

        if not aprobar:
            return self.descartar_edicion(id_propiedad)

        try:
            c = json.loads(filas[0]["datos"])
        except Exception:
            return False

        aplicada = self.ejecutar(
            """
            UPDATE propiedades
            SET titulo = %s, zona = %s, direccion = %s,
                descripcion = %s, habitaciones = %s, banos = %s,
                id_universidad = %s, distancia = %s,
                precio = %s, id_tipo = %s
            WHERE id_propiedad = %s
            """,
            (
                c.get("titulo"), c.get("zona"), c.get("direccion"),
                c.get("descripcion") or None,
                c.get("habitaciones"), c.get("banos"),
                c.get("id_universidad"), c.get("distancia"),
                c.get("precio"), c.get("id_tipo"),
                id_propiedad
            )
        )

        if not aplicada:
            return False

        self._guardar_amenidades(
            id_propiedad,
            c.get("amenidades", [])
        )

        self.ejecutar(
            "DELETE FROM propiedad_fotos "
            "WHERE id_propiedad = %s AND quitar = 1",
            (id_propiedad,)
        )
        self.ejecutar(
            "UPDATE propiedad_fotos SET pendiente = 0 "
            "WHERE id_propiedad = %s",
            (id_propiedad,)
        )

        return self.ejecutar(
            "DELETE FROM propiedad_ediciones WHERE id_edicion = %s",
            (id_edicion,)
        )
