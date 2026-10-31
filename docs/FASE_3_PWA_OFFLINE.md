# Fase 3 — PWA Angular y operación offline

## Alcance implementado

- PWA instalable con `manifest.webmanifest`, Service Worker e iconos Zentry de 192 y 512 px.
- Catálogo, clientes y existencias locales almacenados con Dexie/IndexedDB.
- Separación física del almacenamiento por tenant, usuario y sucursal.
- Venta offline únicamente en efectivo y con entrega directa.
- Reserva offline vinculada a un cliente guardado previamente en el dispositivo.
- Cola idempotente con UUID, envío por lotes, confirmación, conflictos y rechazos.
- Reintento o descarte explícito de operaciones que requieren intervención.
- Reapertura sin conexión mediante contexto de usuario y tenant asociado al token vigente.
- Actualización del catálogo después de sincronizar para reflejar el stock definitivo.

## Reglas de seguridad

El navegador conserva únicamente el catálogo operativo de la sucursal elegida, clientes activos,
la cola creada en ese dispositivo y una copia de contexto para poder abrir la PWA sin red. La base
PostgreSQL continúa siendo la fuente de verdad. Cada sincronización vuelve a validar token, tenant,
usuario, permisos, sucursal y stock en el backend.

Una operación offline no confirma stock por sí sola. Solo queda confirmada cuando el servidor la
acepta. Las pasarelas de pago no se usan sin conexión; requieren confirmación en línea del proveedor.

## Criterios de aceptación

1. El dispositivo se prepara conectado y conserva catálogo y clientes tras cerrar el navegador.
2. La ruta `/admin/inventario/offline` abre sin red mientras el token local siga vigente.
3. Una venta en efectivo se guarda sin red, aparece pendiente y reduce el disponible local.
4. Una reserva exige cliente y también queda pendiente sin red.
5. Al recuperar la conexión, la sincronización confirma cada operación una sola vez.
6. Una segunda sincronización no duplica ventas ni reservas ya confirmadas.
7. Un conflicto de stock se muestra con explicación y permite reintentar o descartar.
8. Cambiar de sucursal, usuario o tenant abre otra base IndexedDB y no mezcla información.

## Limitaciones deliberadas

- No se procesan Stripe ni otros pagos electrónicos offline.
- La primera preparación del dispositivo siempre requiere internet.
- Las imágenes remotas pueden no estar disponibles si nunca fueron visitadas; catálogo, precios,
  variantes, clientes y stock sí quedan guardados localmente.
- El servidor decide el resultado final ante ventas simultáneas de diferentes dispositivos.
