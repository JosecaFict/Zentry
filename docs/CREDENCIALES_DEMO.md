# Credenciales de demostración de Zentry

> Uso exclusivo para desarrollo, exposición y pruebas. Todas estas contraseñas
> deben reemplazarse o eliminarse antes de cargar información comercial real.

## Acceso

- Plataforma principal: `https://zentrysaas.store`
- Tienda de una empresa: `https://<slug>.zentrysaas.store`
- Administración de empresa: `https://<slug>.zentrysaas.store/admin`
- Administración global: `https://zentrysaas.store/platform/login`

## Superadministrador

| Cuenta | Correo | Contraseña |
|---|---|---|
| Superadministrador global | `josecarrascoputz@gmail.com` | Creada manualmente; no está almacenada en el repositorio |

## Administradores de empresas demo

Todos utilizan la contraseña `Admin123*`.

| Empresa | Plan | Slug | Correo |
|---|---|---|---|
| Casa Elena | Básico | `casa-elena` | `admin+casa-elena@zentrysaas.store` |
| Nova Moda | Básico | `nova-moda` | `admin+nova-moda@zentrysaas.store` |
| Urban Style | Básico | `urban-style` | `admin+urban-style@zentrysaas.store` |
| Bella Boutique | Básico | `bella-boutique` | `admin+bella-boutique@zentrysaas.store` |
| Andina Fashion | Básico | `andina-fashion` | `admin+andina-fashion@zentrysaas.store` |
| Prisma Store | Profesional | `prisma-store` | `admin+prisma-store@zentrysaas.store` |
| Élite Moda | Profesional | `elite-moda` | `admin+elite-moda@zentrysaas.store` |
| Vértice | Profesional | `vertice` | `admin+vertice@zentrysaas.store` |
| Magnolia | Profesional | `magnolia` | `admin+magnolia@zentrysaas.store` |
| Altura Comercial | Profesional | `altura-comercial` | `admin+altura-comercial@zentrysaas.store` |

## Clientes sintéticos

El script `app.scripts.seed_demo_sales` crea seis clientes en cada empresa. Todos
utilizan la contraseña `Cliente123*`.

| Cliente | Correo dentro de cada empresa |
|---|---|
| María Fernández | `cliente01+<slug>@zentrysaas.store` |
| Carlos Gutiérrez | `cliente02+<slug>@zentrysaas.store` |
| Ana Ribera | `cliente03+<slug>@zentrysaas.store` |
| Jorge Mendoza | `cliente04+<slug>@zentrysaas.store` |
| Daniela Soto | `cliente05+<slug>@zentrysaas.store` |
| Luis Mercado | `cliente06+<slug>@zentrysaas.store` |

Reemplaza `<slug>` por cualquiera de los diez slugs de la tabla anterior. Por
ejemplo, la primera cliente de Casa Elena es
`cliente01+casa-elena@zentrysaas.store`, y la sexta cliente de Magnolia es
`cliente06+magnolia@zentrysaas.store`.

## Datos generados

Por cada empresa el script registra:

- 6 cuentas de cliente activas.
- 30 ventas pagadas distribuidas en los 180 días anteriores.
- Entre 1 y 3 variantes por venta.
- Pagos en efectivo confirmados.
- Movimientos de salida y consumo FIFO de lotes.

El identificador `ZENTRY-DEMO-SALES-V1` permite reconocer la carga y evita que
una segunda ejecución duplique sus ventas.
