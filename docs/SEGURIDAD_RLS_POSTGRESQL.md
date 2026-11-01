# Seguridad multitenant en PostgreSQL

La migración `20261101_0016` activa y fuerza Row-Level Security (RLS) en las
tablas del esquema `capricho` que contienen `id_tenant`. La aplicación define
el tenant y el alcance dentro de cada transacción mediante `SET LOCAL`.

## Alcances permitidos

- `tenant`: solo filas cuyo `id_tenant` coincide con `app.tenant_id`.
- `identity`: únicamente identidades globales (`id_tenant IS NULL`) usadas en
  el acceso de SUPERADMIN.
- `global`: tareas internas autorizadas de plataforma y migraciones.
- `restricted`: no permite acceder a filas comerciales.

El alcance `global` nunca debe aceptarse desde una cabecera enviada por el
cliente. Las rutas `/platform` comienzan con alcance `identity`; una dependencia
las eleva a `global` únicamente después de autenticar una cuenta global con rol
`SUPERADMIN`. Los procesos internos controlados también declaran ese alcance de
forma explícita.

## Roles recomendados

En producción deben utilizarse dos credenciales distintas:

1. `zentry_app`: rol `LOGIN`, `NOSUPERUSER`, `NOBYPASSRLS`, `NOINHERIT`; lo usa
   Uvicorn mediante `DATABASE_URL`.
2. `zentry_migrator`: propietario o rol técnico usado exclusivamente para
   ejecutar Alembic. No debe utilizarlo la API.

Ejemplo para ejecutar como administrador, reemplazando contraseñas y nombres
según Railway:

```sql
CREATE ROLE zentry_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE
  NOINHERIT NOBYPASSRLS PASSWORD 'CAMBIAR_EN_RAILWAY';

GRANT CONNECT ON DATABASE railway TO zentry_app;
GRANT USAGE ON SCHEMA capricho TO zentry_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA capricho TO zentry_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA capricho TO zentry_app;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA capricho TO zentry_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA capricho
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO zentry_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA capricho
  GRANT USAGE, SELECT ON SEQUENCES TO zentry_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA capricho
  GRANT EXECUTE ON FUNCTIONS TO zentry_app;
```

No se deben guardar las contraseñas reales en Git. Antes de cambiar
`DATABASE_URL`, se validarán RLS, login global, login tenant y el worker de
suscripciones en una conexión separada con `zentry_app`.

## Orden de despliegue

1. Crear `zentry_app` y concederle los permisos anteriores, sin cambiar todavía
   la variable `DATABASE_URL` del servicio.
2. Ejecutar `python -m alembic upgrade head` con la credencial migradora.
3. Ejecutar las pruebas de integración con una URL temporal de `zentry_app`:

   ```powershell
   $env:RUN_POSTGRES_RLS_TESTS="1"
   $env:RLS_TEST_DATABASE_URL="postgresql+asyncpg://zentry_app:CLAVE@HOST:PUERTO/railway"
   .\.venv\Scripts\python.exe -m pytest tests/test_rls_postgresql_integration.py -q
   ```

4. Confirmar que el resultado sea `2 passed`. Borrar la variable temporal del
   equipo y recién entonces cambiar `DATABASE_URL` en Railway para que Uvicorn
   use `zentry_app`.
5. Verificar login SUPERADMIN, login de dos empresas, catálogo, reportes y una
   operación offline. Mantener la credencial migradora fuera del servicio web.

Las pruebas usan transacciones con `ROLLBACK`: inspeccionan y simulan una
actualización cruzada, pero no conservan cambios en la base.
