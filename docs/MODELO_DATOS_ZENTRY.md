# Modelo de datos de Zentry

Este documento resume el modelo actualmente implementado en SQLAlchemy/PostgreSQL. Para que sea legible, el diagrama se divide por módulos. Todas las entidades comerciales pertenecen directa o indirectamente a un `tenant`.

## Notación de cardinalidades

| Símbolo | Significado |
|---|---|
| `||` | exactamente uno |
| `o|` | cero o uno |
| `|{` | uno o muchos |
| `o{` | cero o muchos |

## 1. Plataforma multitenant

```mermaid
erDiagram
    TENANT ||--o{ SUSCRIPCION : contrata
    PLAN ||--o{ SUSCRIPCION : define
    SUSCRIPCION ||--o{ PAGO_SUSCRIPCION : registra
    TENANT ||--o{ SUCURSAL : posee
    CIUDAD ||--o{ SUCURSAL : ubica

    TENANT {
      bigint id_tenant PK
      varchar nombre
      varchar slug UK
      varchar razon_social
      varchar nit
      varchar correo_contacto
      varchar telefono_contacto
      varchar logo_url
      varchar color_primario
      varchar estado
    }
    PLAN {
      bigint id_plan PK
      varchar codigo UK
      varchar nombre
      int limite_sucursales
      boolean permite_offline
      boolean permite_reportes_ia
      numeric precio_mensual
      numeric precio_anual
    }
    SUSCRIPCION {
      bigint id_subscription PK
      bigint id_tenant FK
      bigint id_plan FK
      varchar estado
      varchar modalidad
      numeric precio_acordado
      date fecha_inicio
      date fecha_fin
    }
    PAGO_SUSCRIPCION {
      bigint id_payment PK
      bigint id_subscription FK
      numeric importe
      varchar moneda
      varchar metodo
      varchar referencia
      varchar estado
    }
    CIUDAD {
      bigint id_ciudad PK
      varchar nombre
      varchar departamento
      varchar pais
    }
    SUCURSAL {
      bigint id_sucursal PK
      bigint id_tenant FK
      bigint id_ciudad FK
      varchar nombre
      varchar direccion
      numeric latitud
      numeric longitud
      time hora_apertura
      time hora_cierre
      boolean activo
    }
```

## 2. Identidad, clientes, empleados y seguridad

```mermaid
erDiagram
    TENANT ||--o{ USUARIO : contiene
    USUARIO ||--o| CLIENTE : posee_perfil
    USUARIO ||--o| EMPLEADO : posee_perfil
    SUCURSAL ||--o{ EMPLEADO : asigna
    USUARIO ||--o{ USUARIO_ROL : recibe
    ROL ||--o{ USUARIO_ROL : asignado
    ROL ||--o{ ROL_PERMISO : incluye
    PERMISO ||--o{ ROL_PERMISO : incluido
    USUARIO ||--o{ USUARIO_PERMISO : excepcion
    PERMISO ||--o{ USUARIO_PERMISO : modifica
    USUARIO ||--o{ BITACORA : genera

    USUARIO {
      bigint id_usuario PK
      bigint id_tenant FK
      varchar nombres
      varchar apellidos
      varchar ci
      varchar correo
      varchar telefono
      varchar password_hash
      varchar estado
      timestamptz ultimo_acceso
      varchar avatar_url
    }
    CLIENTE {
      bigint id_cliente PK
      bigint id_tenant FK
      bigint id_usuario FK,UK
      date fecha_nacimiento
      varchar estado
    }
    EMPLEADO {
      bigint id_empleado PK
      bigint id_tenant FK
      bigint id_usuario FK,UK
      bigint id_sucursal FK
      varchar cargo_descriptivo
      date fecha_contratacion
      varchar estado_laboral
    }
    ROL {
      bigint id_rol PK
      bigint id_tenant FK
      varchar alcance
      varchar nombre
      varchar descripcion
      boolean activo
    }
    PERMISO {
      bigint id_permiso PK
      varchar codigo UK
      varchar nombre
      varchar modulo
    }
    BITACORA {
      bigint id_bitacora PK
      bigint id_tenant FK
      bigint id_usuario FK
      varchar accion
      varchar modulo
      varchar entidad
      varchar id_registro
      jsonb datos_anteriores
      jsonb datos_nuevos
      varchar origen
      timestamptz fecha_hora
    }
```

`USUARIO_ROL`, `ROL_PERMISO` y `USUARIO_PERMISO` son entidades asociativas que resuelven relaciones muchos-a-muchos. El perfil `CLIENTE` y el perfil `EMPLEADO` son opcionales, pero cada uno solo puede existir una vez por usuario.

## 3. Catálogo e inventario disponible

```mermaid
erDiagram
    TENANT ||--o{ CATEGORIA : define
    TENANT ||--o{ MARCA : define
    CATEGORIA ||--o{ PRODUCTO : clasifica
    MARCA ||--o{ PRODUCTO : identifica
    PRODUCTO ||--|{ VARIANTE_PRODUCTO : ofrece
    TALLA ||--o{ VARIANTE_PRODUCTO : dimensiona
    COLOR ||--o{ VARIANTE_PRODUCTO : colorea
    PRODUCTO ||--o{ IMAGEN_PRODUCTO : muestra
    PRODUCTO ||--o{ HISTORIAL_PRECIO : cambia
    PRODUCTO ||--o{ MEDIDA_TALLA_PRODUCTO : especifica
    TALLA ||--o{ MEDIDA_TALLA_PRODUCTO : mide
    PRODUCTO ||--o{ PRODUCTO_TEMPORADA : pertenece
    TEMPORADA ||--o{ PRODUCTO_TEMPORADA : agrupa
    PRODUCTO ||--o{ PRODUCTO_COLECCION : pertenece
    COLECCION ||--o{ PRODUCTO_COLECCION : agrupa
    SUCURSAL ||--o{ INVENTARIO_SUCURSAL : almacena
    VARIANTE_PRODUCTO ||--o{ INVENTARIO_SUCURSAL : dispone

    PRODUCTO {
      bigint id_producto PK
      bigint id_tenant FK
      bigint id_categoria FK
      bigint id_marca FK
      varchar nombre
      text descripcion
      varchar genero
      numeric precio_venta
      boolean activo
    }
    VARIANTE_PRODUCTO {
      bigint id_variante PK
      bigint id_producto FK
      bigint id_talla FK
      bigint id_color FK
      varchar sku UK
      varchar codigo_barras UK
      boolean activo
    }
    INVENTARIO_SUCURSAL {
      bigint id_inventario PK
      bigint id_tenant FK
      bigint id_sucursal FK
      bigint id_variante FK
      int stock_actual
      int stock_reservado
      int stock_minimo
    }
    CATEGORIA { bigint id_categoria PK bigint id_tenant FK varchar nombre varchar descripcion }
    MARCA { bigint id_marca PK bigint id_tenant FK varchar nombre varchar descripcion }
    TALLA { bigint id_talla PK bigint id_tenant FK varchar codigo int orden }
    COLOR { bigint id_color PK bigint id_tenant FK varchar nombre varchar codigo_hex }
    TEMPORADA { bigint id_temporada PK bigint id_tenant FK varchar nombre date fecha_inicio date fecha_fin }
    COLECCION { bigint id_coleccion PK bigint id_tenant FK varchar nombre text descripcion }
```

La disponibilidad real se calcula como `stock_actual - stock_reservado`. La combinación sucursal-variante representa una existencia independiente.

## 4. Compras, proveedores y trazabilidad

```mermaid
erDiagram
    CIUDAD ||--o{ PROVEEDOR : ubica
    PROVEEDOR ||--o{ PRODUCTO_PROVEEDOR : suministra
    PRODUCTO ||--o{ PRODUCTO_PROVEEDOR : adquirido
    PROVEEDOR ||--o{ ORDEN_COMPRA : recibe
    SUCURSAL ||--o{ ORDEN_COMPRA : solicita
    ORDEN_COMPRA ||--|{ DETALLE_ORDEN_COMPRA : contiene
    PRODUCTO_PROVEEDOR ||--o{ DETALLE_ORDEN_COMPRA : referencia
    ORDEN_COMPRA ||--o{ RECEPCION_MERCADERIA : recibe
    RECEPCION_MERCADERIA ||--|{ DETALLE_RECEPCION : contiene
    VARIANTE_PRODUCTO ||--o{ DETALLE_RECEPCION : recibido
    DETALLE_RECEPCION ||--o{ LOTE_INVENTARIO : origina
    INVENTARIO_SUCURSAL ||--o{ MOVIMIENTO_INVENTARIO : registra
    MOVIMIENTO_INVENTARIO ||--o{ MOVIMIENTO_LOTE : consume
    LOTE_INVENTARIO ||--o{ MOVIMIENTO_LOTE : participa
    SUCURSAL ||--o{ TRANSFERENCIA_INVENTARIO : origen
    SUCURSAL ||--o{ TRANSFERENCIA_INVENTARIO : destino
    TRANSFERENCIA_INVENTARIO ||--|{ DETALLE_TRANSFERENCIA : contiene
    VARIANTE_PRODUCTO ||--o{ DETALLE_TRANSFERENCIA : transfiere

    PROVEEDOR { bigint id_proveedor PK bigint id_tenant FK bigint id_ciudad FK varchar razon_social varchar nit varchar correo varchar telefono }
    ORDEN_COMPRA { bigint id_orden_compra PK bigint id_tenant FK bigint id_proveedor FK bigint id_sucursal FK varchar estado numeric total date fecha_orden }
    RECEPCION_MERCADERIA { bigint id_recepcion PK bigint id_tenant FK bigint id_orden_compra FK bigint id_sucursal FK timestamptz fecha_recepcion }
    LOTE_INVENTARIO { bigint id_lote PK bigint id_tenant FK bigint id_variante FK bigint id_sucursal FK varchar numero_lote int cantidad_disponible numeric costo_unitario }
    MOVIMIENTO_INVENTARIO { bigint id_movimiento PK bigint id_tenant FK bigint id_inventario FK varchar tipo int cantidad varchar referencia_tipo bigint referencia_id }
    TRANSFERENCIA_INVENTARIO { bigint id_transferencia PK bigint id_tenant FK bigint id_sucursal_origen FK bigint id_sucursal_destino FK varchar estado timestamptz fecha_solicitud }
```

## 5. Venta, reserva, pago y entrega

```mermaid
erDiagram
    CLIENTE ||--o{ DIRECCION_CLIENTE : registra
    CLIENTE ||--o{ CARRITO : posee
    CARRITO ||--|{ DETALLE_CARRITO : contiene
    VARIANTE_PRODUCTO ||--o{ DETALLE_CARRITO : seleccionado
    CLIENTE ||--o{ RESERVA : solicita
    SUCURSAL ||--o{ RESERVA : atiende
    RESERVA ||--|{ DETALLE_RESERVA : contiene
    VARIANTE_PRODUCTO ||--o{ DETALLE_RESERVA : reserva
    CLIENTE o|--o{ VENTA : compra
    SUCURSAL ||--o{ VENTA : registra
    EMPLEADO o|--o{ VENTA : atiende
    RESERVA o|--o| VENTA : convierte
    VENTA ||--|{ DETALLE_VENTA : contiene
    VARIANTE_PRODUCTO ||--o{ DETALLE_VENTA : vendido
    VENTA ||--o{ PAGO : recibe
    METODO_PAGO ||--o{ PAGO : utiliza
    PAGO ||--o{ TRANSACCION_PASARELA : procesa
    VENTA ||--o| PEDIDO : genera
    DIRECCION_CLIENTE o|--o{ PEDIDO : entrega
    COTIZACION_ENVIO o|--o{ PEDIDO : cotiza
    VENTA ||--o{ DEVOLUCION : admite
    DEVOLUCION ||--|{ DETALLE_DEVOLUCION : contiene
    DETALLE_VENTA ||--o{ DETALLE_DEVOLUCION : devuelve

    VENTA { bigint id_venta PK bigint id_tenant FK bigint id_cliente FK bigint id_sucursal FK bigint id_empleado FK bigint id_reserva FK varchar canal_venta varchar modalidad_entrega varchar estado numeric total timestamptz fecha_venta }
    DETALLE_VENTA { bigint id_detalle_venta PK bigint id_venta FK bigint id_variante FK int cantidad numeric precio_unitario numeric subtotal }
    PAGO { bigint id_pago PK bigint id_tenant FK bigint id_venta FK bigint id_metodo_pago FK numeric monto varchar estado timestamptz fecha_pago }
    PEDIDO { bigint id_pedido PK bigint id_tenant FK bigint id_venta FK,UK bigint id_direccion FK bigint id_cotizacion FK varchar estado }
    RESERVA { bigint id_reserva PK bigint id_tenant FK bigint id_cliente FK bigint id_sucursal FK varchar estado timestamptz fecha_reserva timestamptz fecha_expiracion }
    CLIENTE { bigint id_cliente PK bigint id_tenant FK bigint id_usuario FK,UK varchar estado }
```

Una venta puede ser presencial y no identificar a un cliente; por eso `id_cliente` es opcional. Una venta genera como máximo un pedido porque `pedido.id_venta` es único.

## 6. Marketing y recomendaciones

```mermaid
erDiagram
    TENANT ||--o{ CAMPANIA : crea
    CAMPANIA ||--o{ NOTIFICACION : origina_logicamente
    USUARIO o|--o{ NOTIFICACION : recibe
    TENANT ||--o{ PROMOCION : crea
    PROMOCION ||--o{ PROMOCION_PRODUCTO : aplica
    PRODUCTO ||--o{ PROMOCION_PRODUCTO : recibe
    PROMOCION ||--o{ PROMOCION_CATEGORIA : aplica
    CATEGORIA ||--o{ PROMOCION_CATEGORIA : recibe
    PROMOCION ||--o{ PROMOCION_TEMPORADA : aplica
    TEMPORADA ||--o{ PROMOCION_TEMPORADA : recibe
    CLIENTE ||--o{ INTERACCION_PRODUCTO : realiza
    PRODUCTO ||--o{ INTERACCION_PRODUCTO : registra
    CLIENTE ||--o{ RECOMENDACION : recibe
    PRODUCTO ||--o{ RECOMENDACION : sugerido

    CAMPANIA { bigint id_campania PK bigint id_tenant FK varchar nombre varchar segmento_objetivo timestamptz fecha_inicio timestamptz fecha_fin varchar estado }
    NOTIFICACION { bigint id_notificacion PK bigint id_usuario FK bigint id_campania varchar tipo varchar canal varchar destinatario varchar estado }
    PROMOCION { bigint id_promocion PK bigint id_tenant FK varchar nombre varchar tipo_descuento numeric valor date fecha_inicio date fecha_fin boolean activo }
    INTERACCION_PRODUCTO { bigint id_interaccion PK bigint id_tenant FK bigint id_cliente FK bigint id_producto FK varchar tipo timestamptz fecha }
    RECOMENDACION { bigint id_recomendacion PK bigint id_tenant FK bigint id_cliente FK bigint id_producto FK numeric puntaje varchar origen }
```

Nota: `notificacion.id_campania` representa una relación lógica usada por la aplicación, pero actualmente no está declarada como clave foránea física en el modelo. Conviene incorporarla en una migración futura.

## 7. Sincronización offline

```mermaid
erDiagram
    TENANT ||--o{ DISPOSITIVO_SYNC : registra
    USUARIO ||--o{ DISPOSITIVO_SYNC : utiliza
    SUCURSAL o|--o{ DISPOSITIVO_SYNC : asigna
    DISPOSITIVO_SYNC ||--o{ LOTE_SINCRONIZACION : envia
    USUARIO ||--o{ LOTE_SINCRONIZACION : crea
    LOTE_SINCRONIZACION ||--|{ OPERACION_SINCRONIZACION : agrupa
    DISPOSITIVO_SYNC ||--o{ OPERACION_SINCRONIZACION : origina
    OPERACION_SINCRONIZACION ||--o| CONFLICTO_SINCRONIZACION : produce
    USUARIO o|--o{ CONFLICTO_SINCRONIZACION : resuelve

    DISPOSITIVO_SYNC { uuid id_dispositivo PK bigint id_tenant FK bigint id_usuario FK bigint id_sucursal FK varchar nombre varchar plataforma varchar version_app varchar estado timestamptz ultima_sincronizacion }
    LOTE_SINCRONIZACION { uuid id_lote PK bigint id_tenant FK uuid id_dispositivo FK bigint id_usuario FK varchar estado timestamptz fecha_cliente int total_operaciones int total_aplicadas int total_conflictos int total_rechazadas }
    OPERACION_SINCRONIZACION { uuid id_operacion PK bigint id_tenant FK uuid id_lote FK uuid id_dispositivo FK bigint id_usuario FK varchar tipo varchar estado jsonb payload varchar payload_hash jsonb resultado int intentos }
    CONFLICTO_SINCRONIZACION { bigint id_conflicto PK bigint id_tenant FK uuid id_operacion FK,UK varchar tipo jsonb detalle varchar estado bigint resuelto_por FK text resolucion }
```

El UUID identifica la operación creada sin conexión y `payload_hash` ayuda a garantizar idempotencia. Una operación puede producir como máximo un conflicto.

## 8. Reglas cardinales del sistema

1. Un tenant posee muchas sucursales, pero una sucursal pertenece a un tenant.
2. Un tenant posee muchos clientes; un cliente pertenece a un solo tenant.
3. Un usuario puede tener cero o un perfil cliente y cero o un perfil empleado.
4. Un producto posee una o muchas variantes; una variante pertenece a un producto.
5. Una variante puede existir en muchas sucursales mediante `inventario_sucursal`.
6. Una venta pertenece a una sucursal y contiene uno o muchos detalles.
7. Una venta puede no identificar cliente, por ejemplo una venta de mostrador.
8. Una venta puede recibir varios registros de pago, pero solo puede generar un pedido.
9. Un lote de sincronización contiene una o muchas operaciones.
10. Cada consulta comercial debe quedar limitada por tenant y, cuando corresponda, por sucursal.

## 9. Entidades asociativas principales

| Entidad | Relación que resuelve | Atributos clave |
|---|---|---|
| `usuario_rol` | Usuario N:M Rol | `id_usuario_rol`, `id_usuario`, `id_rol` |
| `rol_permiso` | Rol N:M Permiso | `id_rol_permiso`, `id_rol`, `id_permiso` |
| `usuario_permiso` | Usuario N:M Permiso | `id_usuario_permiso`, `id_usuario`, `id_permiso`, `permitido` |
| `producto_temporada` | Producto N:M Temporada | `id_producto`, `id_temporada` |
| `producto_coleccion` | Producto N:M Colección | `id_producto`, `id_coleccion` |
| `producto_proveedor` | Producto N:M Proveedor | `id_producto_proveedor`, `id_producto`, `id_proveedor`, `costo_referencia` |
| `movimiento_lote` | Movimiento N:M Lote | `id_movimiento_lote`, `id_movimiento`, `id_lote`, `cantidad` |
| `promocion_producto` | Promoción N:M Producto | `id_promocion`, `id_producto` |
| `promocion_categoria` | Promoción N:M Categoría | `id_promocion`, `id_categoria` |
| `promocion_temporada` | Promoción N:M Temporada | `id_promocion`, `id_temporada` |

## 10. Recomendación para presentar el diagrama

No conviene colocar las más de sesenta tablas en una sola hoja: quedará ilegible. Para la defensa se recomienda entregar:

1. diagrama general de plataforma y multitenencia;
2. diagrama de identidad y organización;
3. diagrama de catálogo, compras e inventario;
4. diagrama de venta, pagos y pedidos;
5. diagrama de sincronización offline;
6. archivo `zentry_schema.sql` generado sin datos como respaldo técnico.

Los bloques Mermaid de este documento pueden pegarse en Mermaid Live, draw.io o una herramienta compatible para exportarlos como PNG/PDF.

## 11. Inventario completo de entidades implementadas

El modelo actual contiene **68 entidades físicas**. Esta lista sirve como control para comprobar que el diagrama y el respaldo de esquema corresponden a la misma versión:

| Módulo | Entidades |
|---|---|
| Plataforma | `tenant`, `plan`, `subscription`, `subscription_payment` |
| Identidad y organización | `ciudad`, `sucursal`, `usuario`, `cliente`, `empleado`, `rol`, `permiso`, `usuario_rol`, `rol_permiso`, `usuario_permiso`, `bitacora` |
| Catálogo | `categoria`, `marca`, `talla`, `color`, `temporada`, `coleccion`, `producto`, `variante_producto`, `producto_temporada`, `producto_coleccion`, `medida_talla_producto`, `imagen_producto`, `historial_precio` |
| Compras e inventario | `proveedor`, `producto_proveedor`, `orden_compra`, `detalle_orden_compra`, `recepcion_mercaderia`, `detalle_recepcion`, `lote_inventario`, `inventario_sucursal`, `movimiento_inventario`, `movimiento_lote`, `transferencia_inventario`, `detalle_transferencia` |
| Comercio | `direccion_cliente`, `carrito`, `detalle_carrito`, `reserva`, `detalle_reserva`, `venta`, `detalle_venta`, `metodo_pago`, `pago`, `transaccion_pasarela`, `tarifa_envio`, `cotizacion_envio`, `pedido`, `devolucion`, `detalle_devolucion` |
| Marketing y recomendación | `campania`, `notificacion`, `promocion`, `promocion_producto`, `promocion_categoria`, `promocion_temporada`, `configuracion_recomendador`, `interaccion_producto`, `recomendacion` |
| Sincronización | `dispositivo_sync`, `lote_sincronizacion`, `operacion_sincronizacion`, `conflicto_sincronizacion` |

Los atributos completos —incluidos tipos, nulabilidad, valores por defecto, índices y restricciones— deben tomarse del archivo `zentry_schema.sql`. Este documento prioriza claves y atributos de negocio para que el DER permanezca legible.
