# Zentry: núcleo multitenant y panel Superadmin

Estado: implementación de la entrega 1. Las revisiones `20261021_0001` a
`20261021_0006` ya crean el baseline, las tablas SaaS, los dos planes, el tenant
inicial, la pertenencia de entidades raíz y agregados comerciales críticos, y
las restricciones compuestas contra referencias entre tenants. La revisión
`0006` incorpora el rol global `SUPERADMIN` y sus permisos de plataforma.
El principal autenticado carga tenant, suscripción y capacidades del plan, y
SQLAlchemy aplica el filtro de tenant a los modelos que declaran `id_tenant`.
Las rutas de tenant están disponibles bajo `/api/v1/t/{slug}` y comparan el slug
con el tenant autenticado. Las APIs de plataforma y el panel aún están pendientes.

## Objetivo y límites

Zentry usa PostgreSQL compartido. Cada empresa es un `tenant`; una sucursal pertenece
a exactamente un tenant. Capricho Store será el primer tenant y conservará sus datos.
El Superadmin administra la plataforma. El ADMIN administra exclusivamente su
empresa. Ninguno hereda automáticamente los permisos del otro.

La ruta pública prevista es `/t/:slug`; la plataforma usa `/platform`. El slug
identifica la tienda en la interfaz, pero la autorización se obtiene del usuario
autenticado y de las relaciones guardadas en la base. El backend siempre verifica
la pertenencia de cada recurso solicitado.

## Panel `/platform`

| Pantalla | Qué muestra | Acciones del Superadmin |
| --- | --- | --- |
| Resumen | Empresas por estado y plan, suscripciones próximas a vencer, sucursales activas y alertas de sincronización agregadas | Abrir empresa o alerta; no modificar operaciones comerciales |
| Empresas | Nombre, slug, estado, plan, vencimiento, sucursales activas y administrador principal; búsqueda y filtros | Crear empresa; abrir detalle |
| Empresa | Identidad, logo opcional, estado, plan, fechas, administrador, sucursales y cronología administrativa | Editar datos; activar o suspender; asignar administrador; cambiar plan; renovar suscripción |
| Planes | Reglas vigentes de Básico y Profesional | Consultar; la edición de límites queda fuera de la primera entrega, aunque los valores residen en BD |
| Auditoría | Quién cambió tenant, plan, suscripción o administrador, cuándo y por qué | Filtrar y consultar; sin borrar registros |
| Soporte | Salud y fallos de sincronización por tenant, sin datos personales ni contenido comercial por defecto | Consultar diagnóstico acotado; cualquier acceso excepcional requiere motivo y registro de auditoría |
| Mi cuenta | Perfil y seguridad del operador global | Actualizar sus propios datos y cerrar sesión |

El listado muestra datos mínimos de operación SaaS. No presenta ventas, clientes,
precios, inventario ni reportes de todas las empresas en una vista global. El
Superadmin no registra ventas ni edita productos de un tenant desde `/platform`.
Una futura función de soporte con acceso a datos de una empresa requerirá alcance
temporal explícito, motivo obligatorio y auditoría; no forma parte del MVP.

### Flujos principales

1. **Crear empresa:** nombre, slug único y plan; crear tenant, suscripción activa
   y primer ADMIN en una transacción. Mostrar credencial temporal solo en el
   entorno local de demostración; nunca almacenarla en texto plano.
2. **Cambiar plan:** mostrar uso actual y capacidad del plan destino. Si excede
   el límite, rechazar el cambio y explicar qué sucursales deben desactivarse.
   Registrar plan anterior, nuevo, actor y fecha.
3. **Suspender empresa:** requerir confirmación y motivo. Revocar nuevas
   operaciones autenticadas y sincronizaciones; conservar los datos y permitir
   al Superadmin reactivarla. Las operaciones offline locales permanecen en los
   dispositivos y recibirán un resultado explícito al intentar sincronizar.
4. **Renovar suscripción:** registrar nueva fecha de vencimiento y estado sin
   procesar un cobro. La fecha de inicio y el historial de cambios se preservan.
5. **Asignar administrador:** seleccionar o crear un usuario perteneciente al
   tenant; impedir asignar una identidad global o de otra empresa.

### Estados y respuestas

- Tenant: `ACTIVO` o `SUSPENDIDO`. No habrá borrado físico desde el panel.
- Suscripción: `ACTIVA`, `VENCIDA` o `SUSPENDIDA`; `fecha_fin` nula significa
  vigencia sin fecha programada. La regla de acceso usa estado y fecha efectiva.
- Sin suscripción vigente, el tenant conserva lectura administrativa acotada
  para consultar el problema; se bloquean nuevas ventas, reservas, cambios de
  inventario y sincronizaciones. El detalle exacto se fijará en el contrato API.
- Formularios: errores de slug duplicado, correo duplicado, plan inactivo,
  fechas inválidas y cambio de plan que excede capacidad se muestran junto al
  campo o acción. Los cambios exitosos muestran resultado y rastro de auditoría.
- Listas: estados de carga, vacío, error y paginación; confirmaciones explícitas
  para suspensión, reactivación y cambio de plan.

## Modelo de identidad y autorización

`usuario` conservará `id_tenant` nullable solo para el Superadmin global; todos
los usuarios de empresa tendrán `id_tenant` obligatorio. `rol` tendrá alcance
`GLOBAL` o `TENANT`; `SUPERADMIN` es global. Las asignaciones de rol deben validar
que el alcance del rol coincida con el usuario. `ADMIN` es un rol de tenant y no
puede operar sobre otros tenants. Los permisos de plataforma tendrán códigos
propios (`platform.tenants.*`, `platform.subscriptions.*`, `platform.audit.ver`).

El token actual identifica usuario y sesión. En cada petición el backend cargará
usuario, rol, tenant y estado vigente desde BD; no confiará en un `tenant_id`
enviado por cliente. Para `/t/:slug`, comparará el slug resuelto con el tenant del
principal. Para datos públicos, resolverá el tenant desde la ruta y filtrará todos
los resultados. Se rechazan referencias cruzadas a sucursal, producto, cliente,
variante o empleado, aunque el identificador exista.

El correo y CI actuales son únicos globales. Se conservan así en esta primera
entrega para mantener el login existente; una misma persona no podrá tener
cuentas separadas con el mismo correo en dos empresas hasta definir membresías.

## Datos y migraciones

1. Inventariar el esquema restaurado, restricciones, vistas, triggers, recuentos
   y sucursales activas; comprobar que coincide con el punto de partida esperado.
2. Crear un baseline Alembic que adopte el esquema existente sin recrearlo.
   Documentar cómo se instala una base nueva antes de aplicar revisiones nuevas.
3. Crear `tenant`, `plan` y `subscription` con unicidad, estados, claves foráneas
   y marcas temporales. Insertar Básico y Profesional y el tenant Capricho Store.
   Esta etapa está aplicada en `Zentry_Local`; sus 2 sucursales activas caben
   en Básico. Las tablas comerciales permanecen sin cambios.
4. Añadir `id_tenant` a las raíces de datos empresariales; rellenar los registros
   existentes con Capricho Store; añadir índices y restricciones `NOT NULL` donde
   aplique. Mantener `ciudad` y `permiso` como catálogos globales.
5. Revisar relaciones entre entidades y agregar claves compuestas o validaciones
   que impidan referencias entre empresas. Las tablas de detalle heredan tenant
   del padre hasta que exista una razón concreta para desnormalizarlo.
6. Implementar contexto de tenant, filtrado de repositorios y límites de plan
   en FastAPI. No crear un segundo tenant utilizable mientras existan endpoints
   que expongan datos sin filtro.
7. Crear datos demo reproducibles: primero una segunda empresa mínima para
   pruebas de aislamiento; luego el conjunto de empresas para la presentación.

Antes de aplicar migraciones grandes: respaldo verificable de `Zentry_Local`,
ensayo en una copia, revisión de SQL y comprobación de recuentos antes/después.
No se ejecutará `reset`, borrado de datos ni SQL estructural permanente fuera
de Alembic. Producción se migra solo después de validar localmente.

## Contrato API previsto

- `GET /api/v1/platform/overview` (implementado)
- `GET /api/v1/platform/tenants` (implementado) y `POST` (pendiente)
- `GET /api/v1/platform/tenants/{id}` (implementado) y `PATCH` (pendiente)
- `POST /api/v1/platform/tenants/{id}/suspend` y `/activate`
- `GET/POST /api/v1/platform/tenants/{id}/subscriptions`
- `GET /api/v1/platform/plans` (implementado)
- `GET /api/v1/platform/audit`
- `GET /api/v1/t/{slug}/context` para identidad pública, plan visible cuando
  corresponda y estado del tenant, sin secretos ni datos internos.

El detalle de payloads y códigos HTTP se fijará antes de implementar el router.
Las mutaciones usarán transacciones, control de concurrencia y auditoría.

## Criterios de aceptación de la entrega 1

- Capricho Store conserva filas y relaciones tras la migración.
- Dos tenants con catálogos y sucursales distintos no pueden consultar ni
  modificar recursos del otro por API, incluso cambiando IDs o slug en URL.
- Básico admite hasta 2 sucursales activas y Profesional hasta 10; se comprueban
  creación y reactivación, incluidas peticiones concurrentes.
- Un ADMIN de empresa recibe denegación en rutas `/platform` y un Superadmin
  no recibe permisos comerciales por la sola condición de ser global.
- Suspensión y vencimiento se aplican en backend y quedan auditados.
- El panel permite completar los cinco flujos principales y muestra estados
  vacíos, fallos y confirmaciones en escritorio y móvil.

## Próximo bloque de implementación

Crear las APIs de plataforma para resumen, empresas, planes y suscripciones,
incluida la autorización exclusiva del rol global `SUPERADMIN`. Después se
implementará la interfaz Angular `/platform`. Cada bloque incluye estado de Git,
migración aplicada si corresponde y pruebas ejecutadas.
