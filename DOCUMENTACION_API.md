# Integración de API pública – UniHogar (Sesión 43)

## Funcionalidad
- **Emprendimiento:** UniHogar (alquiler de viviendas para estudiantes).
- **Funcionalidad:** consultar el tipo de cambio C$/US$ y convertir el alquiler mensual a dólares.
- **Utilidad:** estudiantes extranjeros o familias que envían dinero pueden ver el precio en dólares como referencia.
- **Acceso:** menú lateral → *Tipo de cambio* (estudiante, arrendador y administrador).

## API utilizada
| Dato | Valor |
|---|---|
| Servicio | ExchangeRate-API (endpoint abierto) |
| Endpoint | `GET https://open.er-api.com/v6/latest/USD` |
| Parámetros | ninguno (la moneda base va en la URL) |
| Clave | no requiere |
| Respuesta | JSON: `result`, `time_last_update_utc`, `rates` (dict por moneda) |
| Campo usado | `rates["NIO"]` = córdobas por 1 dólar |
| Condiciones | pide atribución; se actualiza 1 vez al día → caché de 1 h |

## Organización del código
- `servicios/api_service.py`: comunicación con la API (sin PySide6).
- `proyecto.py` → `TrabajadorTasa` (QThread, consulta en segundo plano) y `mostrar_tipo_cambio`.
- `test_api_service.py`: 8 pruebas con `requests.get` simulado (éxito, caché, timeout, sin Internet, HTTP 500, JSON inválido, sin NIO, conversiones).

## Manejo de errores
Timeout, sin conexión, error HTTP, JSON inválido y falta del campo NIO se convierten en `ErrorAPI` con mensaje claro; la pantalla lo muestra en rojo y no se congela.

## Instalación
`pip install requests openpyxl reportlab PySide6 mysql-connector-python bcrypt`
