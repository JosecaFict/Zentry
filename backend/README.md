# Capricho Store Backend

Fundación del backend FastAPI para la base PostgreSQL `v2` existente.

## Requisitos

- Python 3.12 o superior
- PostgreSQL con el esquema `capricho` ya creado

El backend no crea tablas y no utiliza `Base.metadata.create_all()`.

## Preparación local

En PowerShell, desde `backend/`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edita `.env` y reemplaza `DATABASE_URL` y `SECRET_KEY` con valores locales seguros.
`SECRET_KEY` debe ser aleatoria y tener al menos 32 caracteres. La duración del JWT puede
configurarse con `ACCESS_TOKEN_EXPIRE_MINUTES`.

## Ejecutar la API

```powershell
fastapi dev app/main.py
```

También puede iniciarse con:

```powershell
uvicorn app.main:app --reload
```

La documentación interactiva estará en `http://127.0.0.1:8000/docs`.

## Railway

El despliegue de producción está definido en `railway.json`. Al conectar este
monorepositorio configura en Railway:

```text
Root Directory: /backend
Config File Path: /backend/railway.json
```

La URL estándar de PostgreSQL proporcionada por Railway se convierte
automáticamente al driver asíncrono `asyncpg`. Los orígenes Web autorizados se
configuran con `CORS_ORIGINS`, separados por comas. El procedimiento completo
está documentado en `../DEPLOY_RAILWAY.md`.

## Comprobar endpoints

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/ready
```

`/health` comprueba el proceso FastAPI. `/ready` ejecuta `SELECT 1` en PostgreSQL.

## Autenticación

Endpoints disponibles:

```text
POST /api/v1/auth/register
POST /api/v1/auth/login
GET  /api/v1/auth/me
```

El registro crea `usuario`, `cliente` y la asignación del rol `CLIENTE` en una sola
transacción. Las contraseñas se almacenan con Argon2 y nunca se devuelven en respuestas.

El login devuelve un JWT Bearer. En Swagger, copia `access_token`, pulsa **Authorize** y
pega solamente el token. Luego podrás ejecutar `GET /api/v1/auth/me`.

Los permisos efectivos se calculan así:

```text
(permisos heredados por roles + permisos individuales otorgados)
- permisos individuales revocados
```

## Administración de empleados

Todos estos endpoints requieren JWT y autorización en FastAPI:

```text
GET   /api/v1/employees                                  empleados.ver
GET   /api/v1/employees/{id}                             empleados.ver
POST  /api/v1/employees                                  empleados.crear
PATCH /api/v1/employees/{id}                             empleados.editar
GET   /api/v1/roles                                      permisos.asignar
GET   /api/v1/permissions                                permisos.asignar
GET   /api/v1/roles/{id}/permissions                     permisos.asignar y rol ADMIN
PUT   /api/v1/roles/{id}/permissions/{id_permiso}        permisos.asignar y rol ADMIN
GET   /api/v1/employees/{id}/permissions                 permisos.asignar
PUT   /api/v1/employees/{id}/permissions/{id_permiso}    permisos.asignar
DELETE /api/v1/employees/{id}/permissions/{id_permiso}   permisos.asignar
PUT   /api/v1/employees/{id}/role                        permisos.asignar
GET   /api/v1/audit-logs                                 permisos.asignar
GET   /api/v1/audit-logs/{id}                            permisos.asignar
```

No existe endpoint `DELETE`. La desactivación se realiza con:

```json
{
  "estado_laboral": "INACTIVO"
}
```

Esto conserva el historial y establece tanto `usuario.estado` como
`empleado.estado_laboral` en `INACTIVO`.

Los cambios sensibles establecen el contexto transaccional `app.*`; los triggers de
PostgreSQL escriben en la tabla oficial `capricho.bitacora`. FastAPI no duplica esos registros.

### Crear el primer dueño

El registro público crea únicamente clientes. Para resolver el primer acceso
administrativo, ejecuta una sola vez el comando interno:

```powershell
python -m app.scripts.bootstrap_owner
```

La primera cuenta global de la plataforma se crea, después de aplicar las
migraciones, con:

```powershell
python -m app.scripts.bootstrap_superadmin
```

El comando solicita la contraseña sin mostrarla, crea el usuario con
`id_tenant = NULL` y asigna únicamente el rol global `SUPERADMIN`. Para validar
la configuración sin crear una cuenta usa `--check`.

El asistente muestra las sucursales, solicita los datos del dueño y pide la
contraseña de forma oculta. Si la base todavía no tiene sucursales, también
solicita los datos de la ciudad y sucursal inicial. Crea todo en una sola
transacción y se niega a crear otro dueño cuando ya existe una cuenta `ADMIN`;
los empleados posteriores se crean desde la administración Web o mediante los
endpoints protegidos.

## Catálogo

Las consultas de categorías, marcas, tallas, colores, temporadas, colecciones, productos,
variantes, medidas, precios e imágenes son públicas. Las mutaciones requieren JWT y los
permisos `productos.crear` o `productos.editar`, según corresponda.

El listado principal está disponible en:

```text
GET /api/v1/products
```

Admite filtros por `categoria`, `publico_objetivo`, `marca`, `talla`, `color`, `temporada`,
`sucursal`, `permite_vestidor` y `activo`; paginación con `page` y `page_size`; y orden con
`nombre`, `precio` o `created_at` (prefijo `-` para descendente).

Con el filtro `sucursal`, cada variante devuelve el stock derivado
`stock_fisico - stock_reservado` y el estado `DISPONIBLE`, `STOCK_BAJO` o `AGOTADO`.
La API nunca persiste esos valores calculados. El cambio de precio cierra el precio vigente
y crea el nuevo historial en una sola transacción.

No existen eliminaciones físicas de recursos del catálogo. Los únicos `DELETE` quitan las
asociaciones producto-temporada o producto-colección.

## Proveedores, compras e inventario

Los proveedores y sus productos se administran con `proveedores.ver` y
`proveedores.gestionar`. El único `DELETE` elimina la asociación N:M; nunca elimina el
proveedor ni el producto.

Las órdenes usan estas transiciones:

```text
SOLICITADA -> CONFIRMADA | CANCELADA
CONFIRMADA -> EN_TRANSITO | CANCELADA
EN_TRANSITO -> PARCIAL | RECIBIDA | CANCELADA
PARCIAL -> RECIBIDA | CANCELADA
RECIBIDA y CANCELADA son terminales
```

Una recepción confirmada crea, en una sola transacción, recepción, detalles, lotes con
disponibilidad inicial cero, inventarios faltantes, movimientos `ENTRADA_PROVEEDOR` y sus
desgloses. Los triggers PostgreSQL incrementan `stock_fisico` y `cantidad_disponible`; FastAPI
no actualiza esos valores directamente.

Las salidas físicas consumen lotes bloqueados con `FOR UPDATE`, ordenados por
`fecha_ingreso ASC, id_lote ASC`. Los movimientos y sus desgloses son inmutables. El costo
FIFO consumido se calcula desde `movimiento_lote`, y el costo promedio ponderado actual usa
solamente las cantidades todavía disponibles.

Las transferencias usan estas transiciones:

```text
SOLICITADA -> APROBADA | CANCELADA
APROBADA -> EN_TRANSITO | CANCELADA
EN_TRANSITO -> RECIBIDA
RECIBIDA y CANCELADA son terminales
```

Al despachar se registra `TRANSFERENCIA_SALIDA` con desglose FIFO. Al recibir, cada fracción
FIFO origina un lote nuevo en destino, conservando su costo e `id_detalle_recepcion`. Debido
al modelo actual, ese identificador representa el origen histórico de adquisición y no una
nueva recepción física en la sucursal destino. No se crea una recepción ficticia, no se cambia
la sucursal de lotes existentes y no se combinan costos diferentes.

Permisos principales:

```text
proveedores.ver         consultas de proveedores y órdenes
proveedores.gestionar   mutaciones de proveedores y órdenes
recepcion.registrar     consultas y registro de recepciones
inventario.ver          inventario, lotes, movimientos y transferencias
inventario.movimiento   stock mínimo, ajustes y transferencias
```

## Calidad

```powershell
pytest -q -p no:cacheprovider
ruff check .
```

## Stripe Checkout

La compra Web crea una sesión alojada de Stripe con precios calculados exclusivamente por
FastAPI. La venta permanece pendiente hasta recibir una confirmación verificable. Configura
`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` y `PUBLIC_WEB_URL`; el webhook público es
`POST /api/v1/payments/stripe/webhook`.

Eventos necesarios: `checkout.session.completed`, `checkout.session.async_payment_succeeded`,
`checkout.session.async_payment_failed` y `checkout.session.expired`. Las sesiones vencen en 30
minutos por defecto para no retener inventario indefinidamente.

## Alembic

Alembic administra la evolución del esquema existente `capricho` a partir de un baseline.
Después de restaurar o crear la base inicial, aplica todas las revisiones pendientes con:

```powershell
alembic upgrade head
```

La revisión comercial vigente crea los planes Gestión y Crecimiento, sus límites, periodos
de suscripción y el historial de pagos. Las credenciales y los datos de cobro no se guardan
en migraciones.
