# Zentry

Zentry es una plataforma SaaS multitenant para administrar tiendas, sucursales,
catálogo, inventario, ventas, clientes y suscripciones. El proyecto conserva el
esquema PostgreSQL histórico `capricho`, pero la aplicación y sus nuevas
capacidades pertenecen a Zentry.

## Estructura

- `backend/`: FastAPI, SQLAlchemy, Alembic y procesos de suscripción.
- `frontend-web/`: Angular para el sitio de Zentry, tiendas y superadmin.
- `database/`: SQL base y documentación de las migraciones.
- `mobile/`: cliente móvil.

## Desarrollo local

Backend:

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Frontend:

```powershell
cd frontend-web
npm ci
npm start -- --host 127.0.0.1
```

Superficie principal: `http://127.0.0.1:4200`.
Superadmin: `http://127.0.0.1:4200/platform/login`.
Tenant local: `http://capricho-store.localhost:4200`.

## Validación antes del push

```powershell
cd backend
.\.venv\Scripts\ruff.exe check . --ignore E501
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider

cd ..\frontend-web
npm test -- --watch=false
npm run build
```

## Despliegue

La guía, las variables y el orden de despliegue están documentados en
[`docs/deployment.md`](docs/deployment.md). Las credenciales se configuran en
Railway y Vercel; nunca se agregan al repositorio.
