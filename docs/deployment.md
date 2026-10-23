# Despliegue de Zentry

## Arquitectura inicial

- **Vercel:** `frontend-web/`.
- **Railway:** `backend/`, PostgreSQL y Redis.
- **Cloudinary:** imágenes por tenant.
- **Brevo:** recuperación de contraseña.
- **Stripe:** checkout de las tiendas, cuando se habilite cobro real.

Vercel redirige las solicitudes `/api/*` al backend de Railway. Esto mantiene
frontend y API bajo el mismo origen para el navegador. Si Railway asigna una URL
nueva, hay que reemplazar el destino de API en `frontend-web/vercel.json` antes
del siguiente despliegue.

## 1. Railway

Crear un proyecto con:

1. Un servicio PostgreSQL.
2. Un servicio Redis.
3. Un servicio para el repositorio, usando `backend/` como directorio raíz.

`backend/railway.json` ejecuta `alembic upgrade head` antes del despliegue e
inicia Uvicorn usando el puerto proporcionado por Railway.

### Variables obligatorias

```text
DATABASE_URL=<referencia de PostgreSQL de Railway>
REDIS_URL=<referencia de Redis de Railway>
APP_NAME=Zentry API
APP_ENV=production
DEBUG=false
SECRET_KEY=<valor aleatorio de al menos 32 caracteres>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
PUBLIC_WEB_URL=https://<dominio-principal-de-vercel>
CORS_ORIGINS=https://<dominio-principal-de-vercel>
```

Railway suele entregar `DATABASE_URL` con `postgresql://`; Zentry la transforma
internamente al controlador asíncrono.

### Integraciones

```text
CLOUDINARY_URL=cloudinary://<api-key>:<api-secret>@<cloud-name>
BREVO_API_KEY=<secreto>
BREVO_SENDER_EMAIL=<remitente-verificado>
BREVO_SENDER_NAME=Zentry
STRIPE_SECRET_KEY=<secreto>
STRIPE_WEBHOOK_SECRET=<secreto-del-webhook>
OPENROUTESERVICE_API_KEY=<secreto>
PIAPI_API_KEY=<secreto>
HF_TOKEN=<secreto>
REPLICATE_API_TOKEN=<secreto>
```

Las integraciones que todavía no se utilicen pueden quedar vacías. PostgreSQL,
Redis y `SECRET_KEY` sí deben existir para operar todos los flujos de acceso.

Después del primer despliegue se crea el superadmin dentro del servicio:

```text
python -m app.scripts.bootstrap_superadmin
```

La cuenta local no se copia a producción porque cada base de datos es distinta.

## 2. Vercel

Crear el proyecto con `frontend-web/` como directorio raíz:

- Framework: Angular.
- Instalación: `npm ci`.
- Build: `npm run build`.
- Salida: `dist/frontend-web/browser`.

Antes de desplegar, comprobar que el destino `/api/(.*)` de `vercel.json`
coincida con la URL pública actual del backend de Railway.

## 3. Dominio y subdominios

Mientras no exista dominio propio se puede validar el sitio principal y el
superadmin mediante la URL de Vercel. Los subdominios dinámicos requieren un
dominio configurado con wildcard:

```text
dominio.com
*.dominio.com
```

Cuando se compre el dominio:

1. Configurar ambos dominios en Vercel.
2. Cambiar `tenantBaseDomain` en
   `frontend-web/src/environments/environment.production.ts`.
3. Actualizar `PUBLIC_WEB_URL` y `CORS_ORIGINS` en Railway.
4. Volver a desplegar el frontend.

## 4. Comprobaciones

1. `GET /api/v1/health` responde `healthy`.
2. `GET /api/v1/ready` confirma PostgreSQL.
3. El login de plataforma acepta únicamente al superadmin global.
4. La migración Alembic reporta que está en `head`.
5. No existen credenciales dentro del repositorio.
6. Un tenant no puede consultar identificadores pertenecientes a otro.

## 5. Antes de cada push

- Revisar `git status` y `git diff --check`.
- No agregar `backend/.env`, `.venv`, `node_modules` ni `dist`.
- Ejecutar pruebas y build.
- Revisar especialmente migraciones y archivos de configuración.
