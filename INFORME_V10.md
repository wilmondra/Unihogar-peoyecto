# UNIHOGAR – Informe de correcciones (v10)

> **Base de trabajo:** el último proyecto que se subió al chat (más los
> cambios de las versiones v7–v9 hechos aquí). No recibí un archivo
> llamado "V14"; si tu V14 tiene cambios que no están aquí, súbelo y los
> paso a esta versión.

## Cómo configurar (obligatorio, una vez)
1. Copia `.env.example` como `.env` (junto a `conexion.py`).
2. Escribe tu contraseña de MySQL en `UNIHOGAR_DB_PASSWORD`.
3. **Cambia la contraseña de MySQL**: la anterior estaba escrita en
   `conexion.py` y se compartió en el chat.

## Hallazgo crítico (corregido)
`preparar_base_datos()` **borraba propiedades, fotos, favoritos y
amenidades la primera vez** que se abría la app en una base sin la marca
`vaciar_cajas_ejemplo`. Eliminado. `migracion_propiedades_arrendador.sql`
tenía el mismo borrado (quitado) y `vaciar_propiedades.py/.sql` ahora
piden confirmación explícita / vienen comentados.

## 1. Filtros (dao.py + proyecto.py)
- Precio mínimo y máximo, zona/barrio, tipo, universidad, servicios y
  texto, **todos combinables** (AND). Los servicios son acumulativos
  (la casa debe tener *todos* los elegidos).
- Segunda fila de filtros bajo la barra actual (mismo estilo), con botón
  **Limpiar filtros**. Busca 0,35 s después de dejar de escribir.
- Precio inválido o mínimo > máximo: aviso rojo y no se busca.
- Todo valor del usuario va como parámetro `%s` (sin inyección SQL);
  `%` y `_` escritos por la persona no actúan como comodines.
- Las amenidades se cargan con 1 consulta (antes 1 por propiedad).

## 2. Base de datos
- Sin borrados automáticos. Solo se agregan columnas/tablas/índices.
- Índices únicos en `usuarios.usuario` y `propiedades.id_solicitud`,
  **solo si no hay repetidos** (si los hay, avisa y no toca nada).
- **Transacciones** (antes eran varias conexiones sueltas):
  aprobar solicitud + crear la propiedad + su foto; guardar cambios de
  propiedad (datos + servicios + fotos); eliminar propiedad. Si algo
  falla, no se cambia nada. Antes una solicitud podía quedar
  "aprobada" sin propiedad.
- Una solicitud pendiente por arrendador, garantizada en una sola
  instrucción SQL (no se duplica si se envía dos veces a la vez).
- Los comentarios y mensajes **no se borran** al eliminar una propiedad;
  solo pierden la referencia.
- Una conexión que quedaba abierta al importar `proyecto.py` ahora se
  cierra.

## 3. Validaciones (`validaciones.py`, usadas por interfaz **y** DAO)
- Registro: nombre, usuario (4–30, sin espacios), contraseña (8+, letra y
  número), duplicados (incluye cuentas desactivadas).
- Inicio de sesión: mismo mensaje para usuario o clave mal (no revela qué
  usuarios existen) y pausa de 30 s tras 5 intentos fallidos. Las
  contraseñas antiguas sin cifrar se cifran solas al iniciar sesión.
- Precios: rechaza vacío, letras, `nan`, `inf`, `1e3`, negativos, cero,
  más de 2 decimales y más de C$ 1,000,000. (Antes `nan` pasaba.)
- Teléfonos, textos (largo máximo), calificación 1–5, fotos (debe ser una
  imagen real, máx. 8 MB y 8 por propiedad).
- Permisos en el DAO (no solo en la interfaz): solo un administrador
  puede resolver solicitudes, activar/desactivar usuarios, borrar
  comentarios y ocultar propiedades; un admin no se desactiva a sí mismo
  ni a otro admin. Solo un usuario con rol arrendador puede crear
  solicitudes; solo el dueño edita/elimina su propiedad.

## 4. Seguridad y estabilidad
- Credenciales de MySQL en variables de entorno / `.env` (ignorado por git).
- Errores de BD registrados con `logging`; sin datos sensibles.
- Sistema de solicitudes/aprobación y los roles: sin cambios de
  funcionamiento.

## 5. Pruebas (`python -m unittest discover -s tests -t .`)
**Ejecutadas aquí: 54 pruebas, 52 pasaron, 2 omitidas (integración MySQL).**
| Archivo | Qué comprueba | Cómo corre |
|---|---|---|
| `test_validaciones.py` | validaciones | real |
| `test_dao.py` | SQL, parámetros, orden, commit/rollback, permisos, filtros combinados, registro, solicitudes, edición, borrado, favoritos | conexión **falsa** (no es MySQL) |
| `test_auditoria.py` | detección y corrección de huérfanos/duplicados | SQLite real |
| `test_integracion_mysql.py` | flujo completo con MySQL real | **no ejecutada** |

Se verificó que la prueba "no borra datos al arrancar" **falla con el
código anterior** (4 `DELETE`) y pasa con el nuevo.

## 6. Auditoría de integridad
`python auditoria_integridad.py` (solo lee) revisa huérfanos, duplicados,
dueños inexistentes, precios inválidos, columnas que faltan y relaciones
sin clave foránea (te imprime los `ALTER TABLE` sugeridos).
`--corregir` arregla únicamente referencias rotas sin valor (filas
sueltas de fotos/servicios/favoritos; comentarios/mensajes pierden la
propiedad borrada). Nunca borra propiedades, usuarios ni comentarios, ni
republica solicitudes. Guarda `diagnostico_integridad.txt`.

## Archivos modificados / nuevos
Modificados: `dao.py`, `proyecto.py`, `conexion.py`,
`migracion_propiedades_arrendador.sql`, `vaciar_propiedades.py`,
`vaciar_propiedades.sql`.
Nuevos: `validaciones.py`, `auditoria_integridad.py`, `.env.example`,
`.gitignore`, `tests/`, este informe.

## Pendiente / límites (sin maquillar)
- **No pude ejecutar la app ni MySQL** en este entorno (sin PySide6, sin
  MySQL, sin red). El código compila, no tiene nombres sin definir y las
  41 funciones del DAO que usa la interfaz existen con argumentos
  correctos (revisión estática), pero **la interfaz nueva de filtros no
  se vio funcionando**. Pruébala abriendo la app.
- Las pruebas de autenticación usaron un `bcrypt` simulado porque no
  estaba instalado; con bcrypt real el comportamiento es el mismo,
  pero no se ejecutó aquí.
- El esquema base (usuarios, propiedades, favoritos...) no está en el
  proyecto, así que **no pude verificar claves foráneas reales**. Corre
  `auditoria_integridad.py` en tu base y revisa el informe.
- No se agregan claves foráneas automáticamente (podrían fallar si hay
  datos huérfanos). Hazlo con el informe, después de corregir.
- Solicitudes muy antiguas sin tipo/universidad/precio ya no se pueden
  aprobar (antes se inventaban valores); el arrendador debe reenviarlas.
- La regla de contraseña más estricta solo aplica a registros nuevos.
- Las consultas de solo lectura del administrador (listas) se protegen
  solo en la interfaz, no en el DAO.
- La opción "Cambios de propiedades" del menú admin quedó del sistema
  anterior (ya no se generan ediciones nuevas).
