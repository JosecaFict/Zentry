# Fase 3 — PWA Angular y operación offline

## 1. Decisión de arquitectura

Zentry utiliza **una sola base PostgreSQL central** para todas las empresas. No se crea una base distinta por empresa.

- `tenant` representa a cada empresa (actualmente existen 11).
- Las tablas comerciales contienen `id_tenant` para aislar sus registros.
- El subdominio identifica el tenant, por ejemplo `altura-comercial.zentrysaas.store`.
- El token identifica al usuario y sus permisos.
- La sucursal seleccionada limita la operación cuando el usuario no tiene alcance global.
- PostgreSQL/Railway sigue siendo la fuente oficial de verdad.
- Dexie/IndexedDB es solamente una copia local temporal para trabajar sin conexión.

Por tanto, un dispositivo que trabaja con Altura Comercial **no descarga los catálogos ni los clientes de las otras diez empresas**.

## 2. Empresas, compradores y clientes

Cada empresa posee de forma independiente:

- catálogo, productos, variantes, precios e imágenes;
- sucursales e inventario por sucursal;
- usuarios, empleados, roles y permisos;
- clientes, direcciones, reservas, ventas, pagos y pedidos;
- proveedores, compras y movimientos de inventario.

Una persona puede comprar en más de una empresa, pero su relación comercial pertenece a cada tenant. En el modelo actual esto se representa mediante un `usuario` y su perfil `cliente`, ambos asociados al tenant correspondiente. No se mezclan el historial, las direcciones ni las compras entre empresas.

Ejemplo:

```text
Ana compra en Casa Elena       -> cliente de Casa Elena
Ana compra en Altura Comercial -> cliente de Altura Comercial
```

Aunque sea la misma persona del mundo real, Zentry trata cada membresía comercial dentro del tenant que corresponda. Una identidad global compartida podría añadirse más adelante, pero no es necesaria para la operación offline ni para el examen.

## 3. Qué se almacena en Dexie

La base local debe estar separada por tenant y usuario. Nombre sugerido:

```text
zentry_offline_{tenantId}_{userId}_{branchId}
```

Tablas locales propuestas:

| Tabla Dexie | Contenido | Procedencia |
|---|---|---|
| `sync_meta` | tenant, usuario, sucursal, dispositivo, versión y última sincronización | sesión/backend |
| `catalog_products` | producto, categoría, marca, descripción, precio e imagen principal | `/sync/catalog` |
| `catalog_variants` | variante, talla, color, SKU y código de barras | `/sync/catalog` |
| `branch_stock` | disponibilidad de la variante en la sucursal autorizada | `/sync/catalog` |
| `customer_cache` | clientes usados recientemente o encontrados en línea | endpoint de clientes |
| `draft_sales` | venta local todavía editable | PWA |
| `draft_reservations` | reserva local todavía editable | PWA |
| `pending_operations` | operaciones cerradas pendientes de envío | PWA |
| `sync_batches` | lotes enviados, estado y confirmación | `/sync/batches` |
| `sync_conflicts` | conflictos devueltos por el servidor | `/sync/batches/{id}` |

No se debe copiar en IndexedDB:

- contraseñas o hashes;
- claves de API;
- datos de otros tenants;
- todo el historial de ventas;
- todos los clientes de la empresa sin necesidad operativa;
- información de otras sucursales para un empleado restringido.

## 4. Flujo operativo

### Preparación mientras existe conexión

1. El usuario entra mediante el subdominio de su empresa.
2. Backend valida tenant, usuario, rol y sucursal.
3. PWA registra el navegador como `dispositivo_sync`.
4. Descarga el catálogo autorizado y existencias de la sucursal.
5. Guarda el conjunto en Dexie y registra la fecha de sincronización.

### Durante la desconexión

1. El Service Worker permite abrir la aplicación instalada.
2. El vendedor consulta catálogo y stock local.
3. Selecciona un cliente almacenado, registra uno mínimo o realiza venta sin cliente, según la regla comercial.
4. Crea una venta o reserva con UUID.
5. Solo se permite un cobro que no dependa de confirmación remota, inicialmente **efectivo**.
6. La operación queda en `pending_operations`; todavía no modifica PostgreSQL.

Una pasarela como Stripe requiere Internet para crear y confirmar la sesión. Por eso no debe declararse como pago offline. Puede iniciarse cuando vuelva la conexión o quedar como pago pendiente.

### Al recuperar conexión

1. La PWA agrupa operaciones en un `lote_sincronizacion`.
2. Envía el lote al backend con UUID y hash idempotente.
3. Backend aplica cada operación una sola vez.
4. Comprueba tenant, sucursal, permisos y stock real.
5. Devuelve operaciones aplicadas, rechazadas y con conflicto.
6. La PWA confirma el lote y actualiza su catálogo local.

## 5. Conflictos de inventario

El inventario local es una referencia, no una garantía. Si dos cajas venden la última unidad sin conexión, el servidor decide al sincronizar.

Estados propuestos en la interfaz:

- `PENDIENTE`: no se envió.
- `ENVIANDO`: lote en tránsito.
- `APLICADA`: aceptada por el servidor.
- `CONFLICTO`: necesita revisión, por ejemplo stock insuficiente.
- `RECHAZADA`: datos o permisos inválidos.
- `CONFIRMADA`: resultado recibido y reconocido por el dispositivo.

## 6. Avance y trabajo pendiente de la Fase 3

- [x] Convertir Angular en PWA: manifest, iconos, Service Worker y caché seguro del shell.
- [x] Instalar y configurar Dexie.
- [x] Implementar la base local separada por tenant, usuario y sucursal.
- [x] Registrar el dispositivo y conectar la descarga del catálogo autorizado.
- [x] Crear la cola local con UUID y envío idempotente por lotes.
- [ ] Integrar la preparación offline con la selección real de sucursal y sesión.
- [ ] Construir la pantalla de catálogo local y estado de conectividad.
- [ ] Definir el caché o búsqueda de clientes; no descargar todos automáticamente.
- [ ] Construir venta y reserva offline, inicialmente con pago en efectivo.
- [ ] Crear la pantalla de sincronización, reintentos y resolución de conflictos.
- [ ] Añadir cierre de sesión seguro: limpiar o conservar datos locales según política.
- [ ] Probar dos dispositivos vendiendo la última unidad.
- [ ] Probar aislamiento entre dos subdominios en el mismo navegador.

## 7. Cómo sacar la estructura de la base

Para el diagrama se debe exportar **solo el esquema**, no un respaldo con datos.

En pgAdmin 4:

1. Clic derecho sobre la base `railway`.
2. Elegir **Backup**.
3. Formato **Plain**.
4. En **Data options**, activar **Only schema**.
5. Desactivar blobs y datos.
6. Guardar como `zentry_schema.sql`.

Esto entrega tablas, claves, restricciones e índices sin exponer clientes, contraseñas ni ventas. El diagrama funcional y el diccionario se encuentran en `docs/MODELO_DATOS_ZENTRY.md`.
