# Base de datos de Capricho Store

## Instalación nueva

Para una base PostgreSQL vacía se ejecuta **únicamente**:

```text
capricho_store_postgresql_completo_v2.sql
```

Este archivo es la fuente canónica: crea el esquema `capricho`, sus tablas,
restricciones, funciones, triggers, vistas, datos iniciales y todas las
correcciones v2. La ejecución está contenida en una sola transacción.

Ejemplo con PostgreSQL 17 en PowerShell:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" `
  "CADENA_DE_CONEXION" `
  -v ON_ERROR_STOP=1 `
  -f ".\database\capricho_store_postgresql_completo_v2.sql"
```

No escribas una contraseña real dentro de scripts, Markdown o Git.

## Archivo histórico

`archive/capricho_store_correcciones_v2.sql` se conserva solamente para una
base antigua que hubiera sido creada con el SQL completo anterior a v2.

No debe ejecutarse después del archivo completo v2 actual, porque sus cambios
ya están integrados. Ejecutar ambos en una instalación nueva puede producir
errores por objetos que ya existen.

## Cambios sobre una base existente

Los scripts de `changes/` se aplican únicamente cuando la base ya fue creada
con el SQL completo. Antes de ejecutarlos en producción debe existir un respaldo
verificable. Usa `psql` con `ON_ERROR_STOP=1` y ejecuta cada archivo una sola vez;
los scripts están preparados para tolerar una repetición accidental.

El orden actual es:

1. `changes/20260909_ajustar_permisos_roles.sql`
2. `changes/20260909_cargar_marcas.sql`
3. `changes/20260909_cargar_colores.sql`
4. `changes/20260909_cargar_temporadas_colecciones.sql`
5. `changes/20260909_normalizar_codigos_barras_vacios.sql`
6. `changes/20260909_administrar_sucursales.sql`
7. `changes/20260911_asociar_sucursal_carrito.sql`

## Política

- FastAPI no crea las tablas.
- No se usa `Base.metadata.create_all()`.
- Alembic tiene el baseline `20261021_0001` para adoptar una base ya creada
  con el SQL base, sin recrear sus tablas.
- La revisión `20261021_0002` crea `tenant`, `plan` y `subscription`, inserta
  los planes Básico y Profesional y registra Capricho Store con Básico.
- La revisión `20261021_0003` asigna `id_tenant` a las entidades raíz de
  seguridad, organización, catálogo, proveedores, promociones y recomendación.
  Los datos restaurados quedan asociados a `capricho-store`. La función
  `fn_tenant_actual()` exige contexto explícito cuando exista más de un tenant
  activo; mientras solo exista uno mantiene compatibilidad con los flujos
  actuales.
- La revisión `20261021_0004` añade pertenencia directa a los agregados
  comerciales críticos: carrito, reserva, venta, pedido, devolución, compras,
  recepciones, lotes, inventario, movimientos y transferencias. Esto permite
  filtrar también las consultas directas por identificador.
- La revisión `20261021_0005` agrega 31 claves foráneas compuestas para que las
  relaciones principales solo acepten usuarios, sucursales, clientes,
  empleados, catálogos e inventarios pertenecientes al mismo tenant.
- La revisión `20261021_0006` crea el rol global `SUPERADMIN` y seis permisos
  `platform.*`. No asigna el rol a usuarios ni almacena credenciales.
- La revisión `20261021_0007` incorpora el aprovisionamiento transaccional de
  empresas, suscripciones y administradores iniciales.
- La revisión `20261022_0008` añade la identidad visual configurable de cada
  tenant.
- La revisión `20261022_0009` hace que correo y CI sean únicos dentro de cada
  tenant. Un cliente puede usar el mismo correo en empresas distintas, con
  credenciales, carrito e historial independientes. Login, recuperación de
  contraseña y bloqueo por intentos se resuelven según el subdominio actual.
- La revisión `20261022_0010` incorpora la gestión comercial de suscripciones,
  periodos y pagos. Define Gestión en Bs 300 mensual o Bs 3.600 anual y
  Crecimiento en Bs 700 mensual o Bs 8.400 anual, además de límites de
  sucursales, usuarios internos, productos activos y almacenamiento.
- La revisión `20261022_0011` normaliza las fechas de suscripciones heredadas
  para automatizar los estados por vencer, gracia y suspensión.
- La revisión `20261022_0012` alinea los planes con el enunciado académico:
  Básico admite hasta 2 sucursales y Profesional hasta 10; ambos incluyen
  operación offline y reportes convencionales, mientras que la IA corresponde
  únicamente al plan Profesional.
- Para instalaciones nuevas, ejecutar primero el SQL base y luego, desde
  `backend/`, `alembic upgrade head`. Para la base restaurada, aplicar las
  mismas revisiones tras verificar un respaldo.
- Los cambios futuros deben documentarse y revisarse antes de generar una
  migración.
- Antes de modificar producción debe existir un respaldo verificable.
