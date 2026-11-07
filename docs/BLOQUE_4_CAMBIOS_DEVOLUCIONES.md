# Cambios y devoluciones: CU-14, CU-30 y CU-31

## Flujo implementado

1. El cliente solicita cambio de talla, color, otra prenda o reembolso desde el historial web o desde **Cuenta → Compras y devoluciones** en Flutter. El personal también puede registrar la solicitud en mostrador.
2. La API comprueba la propiedad de la compra, el pago confirmado y las cantidades todavía disponibles para devolver. Bloquea la venta al crear la solicitud para serializar solicitudes concurrentes.
3. El plazo es de cinco días hábiles. En ventas presenciales comienza en la fecha registrada de venta; en pedidos web, desde la entrega o retiro confirmado. Un pedido todavía en camino no habilita la devolución.
4. El personal aprueba o rechaza la solicitud. Aprobar no devuelve stock.
5. Para completar, registra la inspección de cada prenda y confirma: comprobante verificado, sin uso, sin lavado, etiquetas conservadas y sin daños atribuibles al cliente. Si no cumple, puede rechazar la solicitud y dejar observaciones.
6. Selecciona **Cambio** o **Reembolso**. Un cambio exige un reemplazo por cada línea devuelta, con la misma cantidad. La disponibilidad se comprueba en la sucursal original.
7. La misma prenda en otra variante conserva el importe neto pagado. Otra prenda utiliza el precio vigente y su promoción activa. Los descuentos de la compra original se distribuyen sin perder centavos; no se reembolsa el envío.
8. El personal realiza el cobro o reembolso de la diferencia y registra el medio. Transferencia, QR y tarjeta requieren una referencia de comprobante. La aplicación registra esa constancia; no ejecuta movimientos bancarios ni reembolsos automáticos de Stripe.
9. Una sola transacción registra la entrada de prendas aptas, la salida de los reemplazos, sus lotes FIFO y el comprobante. Un fallo revierte todo. Repetir un cierre terminado devuelve el cierre existente.

## Inventario y comprobantes

- Las entradas utilizan movimientos `DEVOLUCION`. Las salidas utilizan `AJUSTE_NEGATIVO`, con motivo de cambio y referencia a la devolución. Ambos IDs figuran como notas de entrada/salida en el comprobante.
- Los triggers de PostgreSQL actualizan stock y lotes. El código mantiene el estado ORM sin aplicar una segunda modificación al lote.
- La liquidación, el checklist, el responsable y los movimientos quedan en `devolucion.cierre`, protegidos por el aislamiento y la auditoría existentes de esa tabla.
- El cliente ve el reemplazo y el importe liquidado en web y móvil. Web permite descargar un PDF interno; no sustituye una factura fiscal.
- La venta y el pago originales se conservan. Las liquidaciones se consultan en devoluciones; no se han reformulado los reportes convencionales como reportes contables de ventas netas.
- Las devoluciones históricas completadas sin cierre conservan su información original y no generan reembolsos retrospectivos.
- No existe una billetera de crédito en tienda: la opción se retiró de nuevas solicitudes.

## Despliegue

Después de publicar el backend actualizado, ejecutar en Railway:

```bash
/app/.venv/bin/python -m alembic upgrade head
/app/.venv/bin/python -m alembic current
```

El head esperado es `20261107_0025`. Las migraciones añaden el cierre y permiten la condición `PENDIENTE_INSPECCION`. Flutter necesita distribuir una nueva compilación para mostrar la pantalla nueva.

## Verificación

- Pruebas de importes: descuentos originales, promociones del reemplazo, diferencias a cobrar/devolver y redondeo de devoluciones parciales.
- Pruebas de servicio: checklist incompleto, referencia faltante, importe incorrecto, falta de stock, compra impaga, plazo vencido, entrega pendiente, otra sucursal y repetición del cierre.
- Pruebas PostgreSQL optativas: venta real, solicitud, aprobación, cambio/reembolso, comprobante y stock/FIFO, con todas las escrituras revertidas. Configurar `RUN_POSTGRES_RETURN_TESTS=1` y `RETURN_TEST_DATABASE_URL` apuntando a una base local migrada con datos de prueba.
- Pruebas Flutter: aceptación de requisitos, bloqueo durante el envío y visualización del reemplazo/liquidación.

### Prueba funcional después del despliegue

Usar una compra pagada reciente asociada a un cliente de prueba. Solicitar cambio, aprobarlo en la empresa, inspeccionar y entregar otra talla con stock. Comprobar precio conservado, una entrada y una salida. Repetir con otra prenda de mayor y menor importe y con reembolso. Verificar el PDF, el historial del cliente y que otro tenant no pueda consultar la devolución ni su comprobante.
