# Cierre de la Fase 5 — IA, reportes y Machine Learning

## Alcance completado

- Reportes convencionales de ventas, productos, clientes, inventario y categorías.
- Filtros por período y sucursal, respetando tenant, rol y alcance de sucursales.
- Exportación de reportes convencionales y generativos en Excel y PDF.
- Intérprete de lenguaje natural con Groq que produce un plan seguro y nunca genera ni ejecuta SQL.
- Reportes generativos de ventas, productos, inventario, clientes, categorías y resumen comercial.
- Datos sintéticos de seis meses para las diez empresas de demostración.
- Modelo supervisado de regresión temporal para predicción de demanda e ingresos.
- Modelo no supervisado K-means con variables RFM para segmentación de clientes.
- Panel analítico adaptable con horizontes semanal, mensual, trimestral y semestral.
- Entrada por voz con Groq Whisper, revisión editable y límite de grabación de 60 segundos.
- Auditoría de consultas, exportaciones y transcripciones sin almacenar preguntas, resultados ni audio.

## Seguridad aplicada

- Aislamiento multitenant obligatorio en todos los endpoints.
- Validación del plan Profesional para reportes generativos, analítica y voz.
- Comprobación de permisos y alcance de sucursales antes de consultar datos.
- Catálogo cerrado de reportes, filtros, agrupaciones y ordenamientos permitidos.
- Límites para archivos de audio, tipos MIME y duración del lado del cliente.
- Mensajes de error sanitizados: las credenciales y respuestas internas de proveedores no se exponen.
- Las claves de Groq permanecen exclusivamente en Railway; no se envían al navegador.

## Variables de producción

```env
GROQ_API_KEY=valor_secreto
GROQ_REPORTS_MODEL=modelo_de_texto_configurado
GROQ_SPEECH_MODEL=whisper-large-v3-turbo
VOICE_MAX_FILE_SIZE_MB=10
```

`GROQ_SPEECH_MODEL` y `VOICE_MAX_FILE_SIZE_MB` tienen esos valores por defecto. La misma
`GROQ_API_KEY` sirve para interpretación de texto y transcripción de voz.

## Prueba manual de aceptación

1. Ingresar con una empresa del plan Profesional y abrir **Análisis > Reportes comerciales**.
2. Grabar una consulta corta desde el botón de micrófono y detener la grabación.
3. Confirmar que aparece una transcripción editable y que el reporte no se ejecuta automáticamente.
4. Corregir el texto si es necesario y pulsar **Consultar**.
5. Verificar el resultado y descargarlo en Excel y PDF.
6. Abrir **Análisis > Analítica inteligente** y probar los cuatro horizontes y una sucursal concreta.
7. Repetir en teléfono o emulación móvil para validar controles, tablas y desplazamiento.
8. Ingresar con una empresa del plan Básico y confirmar que no obtiene acceso a las funciones de IA.

## Criterio de cierre

La Fase 5 queda terminada cuando el commit correspondiente esté desplegado en Railway y Vercel,
y la prueba manual anterior sea satisfactoria en escritorio y móvil. La entrada por voz es una capa
de captura: las mismas reglas de autorización y el mismo intérprete seguro se aplican después de la
transcripción.
