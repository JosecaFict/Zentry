# Matriz de seguridad de reportes y analítica

## Alcance

Esta matriz documenta los controles aplicados a reportes convencionales, reportes generativos,
exportaciones y analítica inteligente de Zentry.

| Riesgo | Control implementado | Evidencia automatizada |
| --- | --- | --- |
| Acceso sin autenticación | Todos los endpoints dependen del principal autenticado | Dependencias `require_permission` |
| Acceso sin permiso comercial | Se exige `ventas.ver`; inventario requiere además `inventario.ver` o rol `ADMIN` | Pruebas HTTP de reportes y analítica |
| Uso de IA desde plan Básico | Se valida `permite_reportes_ia` antes de interpretar o consultar datos | `test_ai_reports_require_professional_plan` y `test_analytics_requires_professional_plan` |
| Lectura cruzada entre empresas | El tenant proviene del token y todas las consultas filtran `id_tenant` | `test_every_report_query_filters_the_authenticated_tenant` |
| Escape de sucursal | Sin alcance global se ignora el `id_sucursal` enviado y se utiliza la sucursal asignada | `test_branch_employee_cannot_export_another_branch` y prueba equivalente de analítica |
| Inyección SQL mediante lenguaje natural | Groq produce un plan Pydantic limitado; nunca produce ni ejecuta SQL | Pruebas de `AIReportPlan` e intérprete |
| Manipulación de una exportación | El backend vuelve a ejecutar el plan autorizado; no acepta filas calculadas por el navegador | Prueba HTTP de exportación generativa |
| Exposición de errores del proveedor | La API devuelve un mensaje estable y el log solo conserva el tipo de excepción | `test_provider_failure_does_not_expose_internal_details` |
| Exposición de preguntas o resultados en auditoría | La bitácora almacena solamente metadatos operativos sanitizados | `test_ai_query_audits_sanitized_metadata_without_question` |
| Falta de trazabilidad | Consultas de IA y exportaciones exitosas registran usuario, sesión, tenant, período, sucursal y formato | `test_report_audit_persists_only_sanitized_metadata` |
| Horizontes no soportados | La API limita el período a Semanal, Mensual, Trimestral y Semestral | `test_analytics_rejects_unknown_period` |

## Datos que no se registran en la bitácora

- Texto original de la pregunta.
- Filas o resultados comerciales.
- Credenciales o claves de Groq.
- Respuesta cruda del proveedor.
- Tokens de autenticación.

## Pruebas ejecutadas

```text
4 pruebas HTTP de seguridad de reportes generativos
8 pruebas de servicio, exportación y auditoría
7 pruebas del intérprete de reportes
4 pruebas HTTP de analítica
7 pruebas matemáticas de predicción y segmentación
30 pruebas aprobadas
```

## Verificación manual en producción

1. Ingresar con una empresa de plan Básico y confirmar el rechazo de IA y analítica avanzada.
2. Ingresar como empleado de sucursal e intentar modificar `id_sucursal` en la petición.
3. Exportar un reporte PDF o Excel y comprobar el registro `REPORTES / EXPORTAR` en la bitácora.
4. Ejecutar una consulta generativa y comprobar el registro `REPORTES / CONSULTAR` sin el texto de la pregunta.
5. Confirmar que los reportes de dos tenants no comparten resultados, clientes ni sucursales.
