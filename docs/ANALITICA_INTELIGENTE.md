# Analítica inteligente de Zentry

## Propósito

El módulo apoya decisiones comerciales mediante dos técnicas reproducibles y aisladas por empresa:

- **Modelo supervisado:** regresión lineal temporal para estimar demanda e ingresos.
- **Modelo no supervisado:** K-means sobre variables RFM para segmentar clientes.

Los resultados son orientativos y no constituyen garantías de venta.

## Horizontes disponibles

| Opción | Historia analizada | Agregación | Pronóstico |
| --- | --- | --- | --- |
| Semanal | 7 días | Día | Próximos 7 días |
| Mensual | 30 días | Semana | Próximas 4 semanas |
| Trimestral | 90 días | Semana | Próximas 12 semanas |
| Semestral | 181 días | Mes | Próximos 6 meses |

Los periodos sin ventas se conservan con valor cero. Esto mantiene continua la serie temporal sin inventar transacciones.

## Predicción de demanda

La regresión utiliza unidades vendidas e ingresos pagados del tenant y, cuando corresponde, de la sucursal seleccionada. El periodo actual incompleto no se usa para entrenar.

Indicadores mostrados:

- **Estimación:** unidades esperadas por periodo.
- **Intervalo esperado:** rango calculado a partir de la variabilidad residual.
- **MAE:** error absoluto medio en unidades; un valor menor indica mejor ajuste.
- **R²:** proporción de variabilidad explicada por la tendencia temporal.
- **Confianza:** clasificación ALTA, MEDIA o BAJA derivada de cantidad de observaciones, R² y error relativo.

Si se estiman cero unidades, los ingresos previstos también se muestran en cero para mantener coherencia comercial.

## Segmentación RFM

K-means trabaja con:

- **Recencia:** días desde la última compra.
- **Frecuencia:** cantidad de compras pagadas.
- **Valor monetario:** gasto acumulado.

Los grupos se traducen en etiquetas explicables: `LEALES`, `POTENCIALES` y `EN_RIESGO`. Cada segmento incluye una acción sugerida, no una acción automática.

## Seguridad y aislamiento

- El endpoint exige el permiso `ventas.ver` y acceso a inventario o rol `ADMIN`.
- La característica solo está habilitada cuando el plan permite reportes con IA.
- El `id_tenant` se toma de la sesión autenticada; nunca de parámetros enviados por el navegador.
- Un usuario sin alcance global queda limitado a su sucursal aunque intente enviar otra en la URL.
- Solo administradores o usuarios con `ventas.sucursales_todas` pueden consultar todas las sucursales.
- Los valores válidos de horizonte están restringidos a `SEMANAL`, `MENSUAL`, `TRIMESTRAL` y `SEMESTRAL`.
- Las consultas generativas y las exportaciones exitosas generan un registro en la bitácora con
  empresa, usuario, sesión, tipo, formato, sucursal y período.
- La pregunta original y los resultados comerciales no se copian a la bitácora, reduciendo la
  exposición de información sensible.
- Los logs registran el tipo de fallo de Groq, pero no su respuesta ni el contenido de la consulta;
  la API devuelve un mensaje estable que no revela tokens ni detalles técnicos.

## API

```http
GET /api/v1/admin/analytics/dashboard?id_sucursal=12&periodo=TRIMESTRAL
```

`id_sucursal` es opcional y está sujeto al alcance del usuario autenticado.

## Limitaciones conocidas

- Los datos sintéticos pueden producir tendencias planas y confianza baja.
- Una confianza baja es un resultado válido y debe mostrarse, no ocultarse.
- La regresión lineal no modela por sí sola estacionalidad, promociones o eventos externos.
- K-means necesita al menos tres clientes con compras para formar los segmentos.
- La entrada por voz usa Groq Whisper para convertir una grabación breve en texto editable.
- La transcripción nunca ejecuta una consulta automáticamente: el usuario debe revisarla y confirmarla.
- El audio se procesa en memoria y no se conserva; la auditoría registra únicamente metadatos
  técnicos sanitizados, sin audio ni transcripción.

## Validación automatizada

Las pruebas cubren:

- Cálculo y calidad del pronóstico.
- Periodos sin ventas.
- Coherencia entre unidades e ingresos.
- Restricción por plan.
- Aislamiento por tenant y sucursal.
- Rechazo de horizontes no permitidos.
- Segmentación estable incluso con perfiles idénticos.
