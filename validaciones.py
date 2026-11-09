"""Validaciones compartidas por la interfaz y el DAO.

Son funciones puras (no usan base de datos ni Qt), por eso se pueden
probar fácilmente. Casi todas devuelven una pareja (valor, error):
si "error" es None el dato es válido y "valor" ya viene limpio.
"""

import math
import re
from decimal import Decimal, InvalidOperation

# Límites (coinciden con las columnas de MySQL)
MAX_PRECIO = 1_000_000          # C$ por mes
MAX_TITULO = 100
MAX_DIRECCION = 255
MAX_DESCRIPCION = 2000
MAX_DISTANCIA = 60
MAX_COMENTARIO = 1000
MAX_MENSAJE = 1000
MAX_BYTES_FOTO = 8 * 1024 * 1024    # 8 MB por foto

_RE_USUARIO = re.compile(r"^[A-Za-z0-9._-]+$")


def _espacios(texto):
    return re.sub(r"\s+", " ", (texto or "").strip())


# ---------------------------------------------------------------
# Cuenta de usuario
# ---------------------------------------------------------------

def validar_nombre(nombre):

    nombre = _espacios(nombre)

    if len(nombre) < 3:
        return None, "El nombre debe tener al menos 3 letras."

    if len(nombre) > 60:
        return None, "El nombre es muy largo (máximo 60)."

    if not any(c.isalpha() for c in nombre):
        return None, "El nombre debe tener letras."

    if any(not (c.isalpha() or c in " .'-") for c in nombre):
        return None, "El nombre solo puede tener letras y espacios."

    return nombre, None


def validar_usuario(usuario):

    usuario = (usuario or "").strip()

    if len(usuario) < 4:
        return None, "El usuario debe tener al menos 4 caracteres."

    if len(usuario) > 30:
        return None, "El usuario es muy largo (máximo 30)."

    if not _RE_USUARIO.match(usuario):
        return None, (
            "El usuario solo puede tener letras, números, "
            "punto, guion y guion bajo (sin espacios)."
        )

    return usuario, None


def validar_contrasena(contrasena):

    contrasena = contrasena or ""

    if len(contrasena) < 8:
        return None, "La contraseña debe tener al menos 8 caracteres."

    # bcrypt solo usa los primeros 72 bytes
    if len(contrasena.encode("utf-8")) > 72:
        return None, "La contraseña es muy larga (máximo 72 caracteres)."

    if not any(c.isalpha() for c in contrasena):
        return None, "La contraseña debe tener al menos una letra."

    if not any(c.isdigit() for c in contrasena):
        return None, "La contraseña debe tener al menos un número."

    return contrasena, None


# ---------------------------------------------------------------
# Teléfono y números
# ---------------------------------------------------------------

def limpiar_telefono(texto):
    """"" si está vacío, None si no es válido, o el texto limpio."""

    texto = (texto or "").strip()

    if not texto:
        return ""

    digitos = [c for c in texto if c.isdigit()]

    if len(digitos) < 8 or len(digitos) > 15:
        return None

    if any(not (c.isdigit() or c in " +-()") for c in texto):
        return None

    return _espacios(texto)[:30]


def validar_telefono(texto, obligatorio=False):

    limpio = limpiar_telefono(texto)

    if limpio is None:
        return None, "Escribe solo números, por ejemplo 8888 8888."

    if obligatorio and not limpio:
        return None, "El teléfono es obligatorio."

    return limpio, None


def validar_precio(valor, nombre="El precio"):
    """Acepta número o texto ("2,500", "2 500", "2500.50").

    Rechaza vacío, letras, cero, negativos, NaN, infinito, más de
    2 decimales y valores mayores que MAX_PRECIO.
    """

    if isinstance(valor, bool):
        return None, f"{nombre} no es válido."

    if isinstance(valor, (int, float, Decimal)):
        texto = str(valor)
    else:
        texto = (valor or "").strip()

    texto = texto.replace(",", "").replace(" ", "")

    if not texto:
        return None, f"{nombre} es obligatorio."

    # Solo dígitos y un punto decimal (sin "1e3", "nan", "inf", etc.)
    if not re.fullmatch(r"-?\d+(\.\d+)?", texto):
        return None, f"{nombre} debe ser un número."

    try:
        numero = Decimal(texto)
    except InvalidOperation:
        return None, f"{nombre} debe ser un número."

    if not numero.is_finite():
        return None, f"{nombre} debe ser un número."

    if numero <= 0:
        return None, f"{nombre} debe ser mayor que cero."

    if numero > MAX_PRECIO:
        return None, f"{nombre} no puede pasar de C$ {MAX_PRECIO:,}."

    if numero != numero.quantize(Decimal("0.01")):
        return None, f"{nombre} puede tener máximo 2 decimales."

    return float(numero), None


def validar_rango_precios(minimo, maximo):
    """minimo / maximo: texto, número o vacío (= sin límite).

    Devuelve ((min, max), error). Cada límite puede ser None.
    """

    def uno(valor, nombre):

        if valor is None or (
            isinstance(valor, str) and not valor.strip()
        ):
            return None, None

        return validar_precio(valor, nombre)

    pmin, error = uno(minimo, "El precio mínimo")

    if error:
        return (None, None), error

    pmax, error = uno(maximo, "El precio máximo")

    if error:
        return (None, None), error

    if pmin is not None and pmax is not None and pmin > pmax:
        return (None, None), (
            "El precio mínimo no puede ser mayor que el máximo."
        )

    return (pmin, pmax), None


def validar_entero(valor, minimo, maximo, nombre="El número"):

    try:
        numero = int(valor)
    except (TypeError, ValueError):
        return None, f"{nombre} no es válido."

    if numero < minimo or numero > maximo:
        return None, f"{nombre} debe estar entre {minimo} y {maximo}."

    return numero, None


def validar_calificacion(valor):
    """1 a 5, o None si no se calificó."""

    if valor is None or valor == "":
        return None, None

    return validar_entero(valor, 1, 5, "La calificación")


# ---------------------------------------------------------------
# Textos
# ---------------------------------------------------------------

def validar_texto(texto, minimo, maximo, nombre="El texto",
                  obligatorio=True):

    texto = (texto or "").strip()

    if not texto:
        if obligatorio:
            return None, f"{nombre} es obligatorio."
        return "", None

    if len(texto) < minimo:
        return None, f"{nombre} debe tener al menos {minimo} caracteres."

    if len(texto) > maximo:
        return None, f"{nombre} es muy largo (máximo {maximo})."

    return texto, None


def escapar_like(texto):
    """Evita que % o _ escritos por la persona actúen como comodines."""

    return (
        (texto or "")
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


# ---------------------------------------------------------------
# Fotografías
# ---------------------------------------------------------------

def tipo_de_imagen(datos):
    """'jpeg', 'png', 'webp', 'gif' o None según los primeros bytes."""

    if not datos or len(datos) < 12:
        return None

    cabecera = bytes(datos[:12])

    if cabecera[:3] == b"\xff\xd8\xff":
        return "jpeg"

    if cabecera[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"

    if cabecera[:4] == b"RIFF" and cabecera[8:12] == b"WEBP":
        return "webp"

    if cabecera[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"

    return None


def validar_foto(datos):

    if not datos:
        return None, "La foto está vacía."

    if len(datos) > MAX_BYTES_FOTO:
        return None, "La foto pesa demasiado (máximo 8 MB)."

    if tipo_de_imagen(datos) is None:
        return None, "El archivo no es una imagen válida."

    return bytes(datos), None


# ---------------------------------------------------------------
# Datos de una propiedad (los usa la interfaz y el DAO)
# ---------------------------------------------------------------

def validar_datos_propiedad(datos):
    """Revisa y limpia el diccionario de una propiedad.

    Devuelve (datos_limpios, error). No toca la base de datos:
    que el tipo/universidad existan lo comprueba el DAO.
    """

    limpio = dict(datos)

    limpio["titulo"], error = validar_texto(
        datos.get("titulo"), 3, MAX_TITULO, "El título"
    )
    if error:
        return None, error

    limpio["direccion"], error = validar_texto(
        datos.get("direccion"), 8, MAX_DIRECCION, "La dirección"
    )
    if error:
        return None, error

    zona = (datos.get("zona") or limpio["direccion"]).strip()
    limpio["zona"] = zona[:100]

    limpio["descripcion"], error = validar_texto(
        datos.get("descripcion"), 0, MAX_DESCRIPCION,
        "La descripción", obligatorio=False
    )
    if error:
        return None, error

    limpio["distancia"], error = validar_texto(
        datos.get("distancia") or "Cerca de la universidad",
        1, MAX_DISTANCIA, "La distancia"
    )
    if error:
        return None, error

    limpio["precio"], error = validar_precio(datos.get("precio"))
    if error:
        return None, error

    telefono, error = validar_telefono(datos.get("telefono"))
    if error:
        return None, error
    limpio["telefono"] = telefono or None

    for campo, nombre in (
        ("habitaciones", "Las habitaciones"),
        ("banos", "Los baños"),
        ("camas", "Las camas"),
    ):
        valor = datos.get(campo)

        if valor in (None, "", 0):
            limpio[campo] = None
            continue

        limpio[campo], error = validar_entero(valor, 1, 50, nombre)
        if error:
            return None, error

    for campo in ("id_tipo", "id_universidad"):
        if not datos.get(campo):
            return None, "Falta elegir el tipo y la universidad."

    ids = datos.get("amenidades") or []

    try:
        limpio["amenidades"] = sorted({int(i) for i in ids})
    except (TypeError, ValueError):
        return None, "Los servicios elegidos no son válidos."

    return limpio, None
