# Fase 2 — Backend de sincronización offline

## Estado

Implementada como contrato común para la PWA Angular y la aplicación Flutter.

## Principios

- Cada dispositivo genera y conserva un UUID.
- Cada lote y cada operación tienen UUID independientes.
- Reenviar el mismo lote con el mismo contenido devuelve el resultado existente.
- Reutilizar un UUID con contenido diferente responde con conflicto HTTP 409.
- La venta o reserva y el resultado de sincronización se confirman en una misma transacción.
- Las ventas offline solo aceptan efectivo. Tarjetas, QR y Stripe requieren conexión.
- Los conflictos de inventario quedan registrados y no crean ventas parciales.
- Todas las tablas de sincronización están aisladas por tenant y auditadas en bitácora.

## Flujo del cliente

1. Registrar el dispositivo una vez con `POST /api/v1/sync/devices`.
2. Descargar catálogo y existencias con `GET /api/v1/sync/catalog?id_sucursal=...`.
3. Guardar localmente operaciones pendientes con UUID.
4. Enviar hasta 100 operaciones con `POST /api/v1/sync/batches`.
5. Conservar como pendientes las operaciones `CONFLICTO` o `RECHAZADA` para mostrarlas al usuario.
6. Confirmar la recepción con `POST /api/v1/sync/batches/{id_lote}/confirm`.

## Estados

### Lote

`RECIBIDO → PROCESANDO → COMPLETADO | COMPLETADO_CON_CONFLICTOS → CONFIRMADO`

### Operación

`PENDIENTE → PROCESANDO → APLICADA | CONFLICTO | RECHAZADA`

## Ejemplo de lote

```json
{
  "id_lote": "dc09c321-4785-469d-8454-6dff4d60c7b8",
  "id_dispositivo": "19013bbd-d03b-4762-81bf-47136cb4b8d1",
  "fecha_cliente": "2026-10-29T10:30:00-04:00",
  "operaciones": [
    {
      "id_operacion": "997d1e6c-060c-4c02-aac1-b97952ed34b3",
      "tipo": "VENTA",
      "fecha_cliente": "2026-10-29T10:28:00-04:00",
      "payload": {
        "id_sucursal": 1,
        "id_cliente": null,
        "modalidad_entrega": "MOSTRADOR",
        "items": [{"id_variante": 10, "cantidad": 1}],
        "registrar_efectivo": true,
        "metodo_pago": "EFECTIVO"
      }
    }
  ]
}
```

## Conflictos

- `STOCK_INSUFICIENTE`: otra operación consumió el inventario antes de sincronizar.
- `CONFLICTO_COMERCIAL`: el estado actual impide completar la operación.
- `DATOS_INVALIDOS`: el payload, sucursal, reserva o permisos no son válidos.
- `ERROR_INTERNO`: error inesperado, sin filtrar detalles técnicos al cliente.

## Despliegue

Antes de usar los endpoints en Railway se debe ejecutar la migración:

```powershell
python -m alembic upgrade head
```

El despliegue no requiere variables de entorno nuevas.

