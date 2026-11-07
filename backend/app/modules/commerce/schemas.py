from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

ReservationState = Literal[
    "PENDIENTE",
    "CONFIRMADA",
    "PREPARANDO",
    "LISTA",
    "CLIENTE_PRESENTE",
    "CONVERTIDA",
    "CANCELADA",
    "EXPIRADA",
]
OrderState = Literal[
    "PENDIENTE",
    "PREPARANDO",
    "LISTO_PARA_RETIRO",
    "LISTO_PARA_ENVIO",
    "RECOGIDO",
    "EN_CAMINO",
    "ENTREGADO",
    "RETIRADO",
    "CANCELADO",
]
ReturnState = Literal["PENDIENTE", "APROBADA", "RECHAZADA", "COMPLETADA"]
ReturnKind = Literal["DEVOLUCION", "CAMBIO_TALLA", "CAMBIO_COLOR", "CAMBIO_PRENDA", "REEMBOLSO", "CREDITO"]
DeliveryMode = Literal["ENTREGA_DIRECTA", "MOSTRADOR", "RETIRO_SUCURSAL", "DELIVERY"]


class ORMResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CommerceLineRequest(BaseModel):
    id_variante: int = Field(gt=0)
    cantidad: int = Field(gt=0)


class CommerceLineResponse(ORMResponse):
    id_detalle: int
    id_variante: int
    sku: str
    producto: str
    talla: str
    color: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    stock_disponible: int
    activo: bool
    imagen_url: str | None = None


class CartItemCreate(CommerceLineRequest):
    id_sucursal: int | None = Field(default=None, gt=0)


class CartItemUpdate(BaseModel):
    cantidad: int = Field(gt=0)


class CartResponse(ORMResponse):
    id_carrito: int
    estado: str
    id_sucursal: int | None = None
    sucursal: str | None = None
    items: list[CommerceLineResponse]
    total: Decimal


class AddressCreate(BaseModel):
    id_ciudad: int = Field(gt=0)
    alias: str | None = Field(default=None, max_length=60)
    zona: str | None = Field(default=None, max_length=120)
    direccion: str = Field(min_length=3, max_length=255)
    referencia: str | None = Field(default=None, max_length=255)
    latitud: Decimal | None = Field(default=None, ge=-90, le=90)
    longitud: Decimal | None = Field(default=None, ge=-180, le=180)
    place_id: str | None = Field(default=None, max_length=255)
    es_principal: bool = False

    @model_validator(mode="after")
    def coordinates_are_paired(self) -> "AddressCreate":
        if (self.latitud is None) != (self.longitud is None):
            raise ValueError("Latitud y longitud deben enviarse juntas")
        return self


class AddressUpdate(BaseModel):
    id_ciudad: int | None = Field(default=None, gt=0)
    alias: str | None = Field(default=None, max_length=60)
    zona: str | None = Field(default=None, max_length=120)
    direccion: str | None = Field(default=None, min_length=3, max_length=255)
    referencia: str | None = Field(default=None, max_length=255)
    latitud: Decimal | None = Field(default=None, ge=-90, le=90)
    longitud: Decimal | None = Field(default=None, ge=-180, le=180)
    place_id: str | None = Field(default=None, max_length=255)
    es_principal: bool | None = None
    activo: bool | None = None

    @model_validator(mode="after")
    def has_fields(self) -> "AddressUpdate":
        if not self.model_fields_set:
            raise ValueError("Debe enviar al menos un campo")
        if ("latitud" in self.model_fields_set) != ("longitud" in self.model_fields_set):
            raise ValueError("Latitud y longitud deben actualizarse juntas")
        return self


class AddressResponse(ORMResponse):
    id_direccion: int
    id_ciudad: int
    ciudad: str
    alias: str | None
    zona: str | None
    direccion: str
    referencia: str | None
    latitud: Decimal | None
    longitud: Decimal | None
    es_principal: bool
    activo: bool


class ReservationCreate(BaseModel):
    id_sucursal: int = Field(gt=0)
    fecha_cita: datetime | None = None
    observacion: str | None = Field(default=None, max_length=1000)
    items: list[CommerceLineRequest] = Field(min_length=1)


class ReservationStatusUpdate(BaseModel):
    estado: ReservationState


class ReservationResponse(ORMResponse):
    id_reserva: int
    id_sucursal: int
    sucursal: str
    direccion_sucursal: str
    id_cliente: int | None = None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    cliente_telefono: str | None = None
    fecha_reserva: datetime
    fecha_cita: datetime | None
    fecha_expiracion: datetime | None
    estado: ReservationState
    observacion: str | None
    items: list[CommerceLineResponse]


class SaleCreate(BaseModel):
    id_sucursal: int = Field(gt=0)
    id_cliente: int | None = Field(default=None, gt=0)
    id_reserva: int | None = Field(default=None, gt=0)
    modalidad_entrega: DeliveryMode = "ENTREGA_DIRECTA"
    items: list[CommerceLineRequest] = Field(min_length=1)
    registrar_efectivo: bool = True
    metodo_pago: Literal["EFECTIVO", "TARJETA", "QR"] | None = "EFECTIVO"
    referencia_pago: str | None = None


class CheckoutCreate(BaseModel):
    id_sucursal: int = Field(gt=0)
    modalidad_entrega: Literal["RETIRO_SUCURSAL", "DELIVERY"]
    id_direccion: int | None = Field(default=None, gt=0)
    id_cotizacion: int | None = Field(default=None, gt=0)
    return_url: str | None = None

    @model_validator(mode="after")
    def delivery_requires_address(self) -> "CheckoutCreate":
        if self.modalidad_entrega == "DELIVERY" and self.id_direccion is None:
            raise ValueError("Delivery requiere una dirección")
        if self.modalidad_entrega == "DELIVERY" and self.id_cotizacion is None:
            raise ValueError("Delivery requiere una cotización vigente")
        if self.modalidad_entrega == "RETIRO_SUCURSAL" and self.id_direccion is not None:
            raise ValueError("Retiro en sucursal no requiere dirección")
        return self


class SaleResponse(ORMResponse):
    id_venta: int
    id_cliente: int | None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    cliente_telefono: str | None = None
    id_sucursal: int
    sucursal: str
    id_empleado: int | None
    empleado_nombre: str | None = None
    id_reserva: int | None
    canal_venta: str
    modalidad_entrega: DeliveryMode
    metodo_pago: str | None = None
    estado: str
    subtotal: Decimal
    costo_envio: Decimal
    total: Decimal
    fecha_venta: datetime
    fecha_inicio_devolucion: datetime | None = None
    fecha_limite_devolucion: datetime | None = None
    devolucion_habilitada: bool = False
    items: list[CommerceLineResponse]


class OrderStatusUpdate(BaseModel):
    estado: OrderState


class OrderResponse(ORMResponse):
    id_pedido: int
    id_venta: int
    id_cliente: int | None = None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    cliente_telefono: str | None = None
    estado: OrderState
    modalidad_entrega: DeliveryMode
    id_sucursal: int
    sucursal: str
    direccion_sucursal: str
    id_direccion: int | None
    direccion_entrega: str | None
    total: Decimal
    fecha_creacion: datetime
    fecha_preparacion: datetime | None
    fecha_finalizacion: datetime | None
    items: list[CommerceLineResponse]
    receipt_url: str | None = None


class StripeCheckoutResponse(BaseModel):
    session_id: str
    checkout_url: str
    expires_at: datetime


class StripeCheckoutStatusResponse(BaseModel):
    status: Literal["PROCESANDO", "PAGADO", "CANCELADO", "RECHAZADO"]
    message: str
    order: OrderResponse | None = None
    receipt_url: str | None = None


class ShippingQuoteCreate(BaseModel):
    id_sucursal: int = Field(gt=0)
    id_direccion: int = Field(gt=0)


class ShippingQuoteResponse(ORMResponse):
    id_cotizacion: int
    id_sucursal: int
    id_direccion: int
    distancia_km: Decimal
    duracion_estimada_min: int | None
    costo_estimado: Decimal
    proveedor_rutas: str
    fecha_cotizacion: datetime
    expira_en: datetime | None


class ReturnLineCreate(BaseModel):
    id_detalle_venta: int = Field(gt=0)
    cantidad: int = Field(gt=0)
    estado_prenda: Literal["PENDIENTE_INSPECCION", "APTA_REINGRESO", "NO_APTA"] = "PENDIENTE_INSPECCION"


class ReturnCreate(BaseModel):
    id_venta: int = Field(gt=0)
    tipo_solicitud: ReturnKind = "DEVOLUCION"
    motivo: str = Field(min_length=3, max_length=255)
    items: list[ReturnLineCreate] = Field(min_length=1)


class AdminReturnCreate(BaseModel):
    id_venta: int = Field(gt=0)
    tipo_solicitud: ReturnKind = "DEVOLUCION"
    motivo: str = Field(min_length=3, max_length=255)
    items: list[ReturnLineCreate] = Field(min_length=1)
    completar_inmediato: bool = False


class ReturnChecklist(BaseModel):
    comprobante_verificado: bool
    sin_uso: bool
    sin_lavado: bool
    etiquetas_conservadas: bool
    sin_danos_cliente: bool


class ReturnReplacement(BaseModel):
    id_detalle_devolucion: int = Field(gt=0)
    id_variante: int = Field(gt=0)


class ReturnSettlement(BaseModel):
    tipo: Literal["CAMBIO", "REEMBOLSO"]
    reemplazos: list[ReturnReplacement] = Field(default_factory=list, max_length=100)
    monto_confirmado: Decimal = Field(default=Decimal(0), ge=0, max_digits=12, decimal_places=2)
    medio: Literal["EFECTIVO", "TRANSFERENCIA", "QR", "TARJETA"] | None = None
    referencia: str | None = Field(default=None, max_length=120)


class ReturnItemConditionUpdate(BaseModel):
    id_detalle_devolucion: int = Field(gt=0)
    estado_prenda: Literal["APTA_REINGRESO", "NO_APTA"]


class ReturnStatusUpdate(BaseModel):
    estado: ReturnState
    items: list[ReturnItemConditionUpdate] | None = None
    observaciones: str | None = Field(default=None, max_length=255)
    checklist: ReturnChecklist | None = None
    resolucion: ReturnSettlement | None = None


class ReturnLineResponse(ORMResponse):
    id_detalle_devolucion: int
    id_detalle_venta: int
    id_variante: int
    producto: str
    talla: str
    color: str
    cantidad: int
    estado_prenda: str


class ReturnResponse(ORMResponse):
    id_devolucion: int
    id_venta: int
    tipo_solicitud: ReturnKind
    id_cliente: int | None = None
    cliente_nombre: str | None = None
    motivo: str
    estado: ReturnState
    fecha_solicitud: datetime
    fecha_resolucion: datetime | None
    cierre: dict | None = None
    id_sucursal: int | None = None
    items: list[ReturnLineResponse]


class SaleReturnLineInspection(ORMResponse):
    id_detalle_venta: int
    id_variante: int
    sku: str
    producto: str
    talla: str
    color: str
    cantidad_vendida: int
    cantidad_devuelta: int
    cantidad_disponible: int
    precio_unitario: Decimal
    imagen_url: str | None = None


class SaleReturnInspectionResponse(ORMResponse):
    id_venta: int
    id_cliente: int | None = None
    cliente_nombre: str | None = None
    cliente_correo: str | None = None
    cliente_telefono: str | None = None
    id_sucursal: int
    sucursal: str
    canal_venta: str
    modalidad_entrega: str
    total: Decimal
    fecha_venta: datetime
    es_retornable: bool
    dias_habiles_transcurridos: int
    dias_habiles_limite: int = 5
    fecha_limite_devolucion: datetime
    motivo_invalidez: str | None = None
    items: list[SaleReturnLineInspection]


class NotificationResponse(ORMResponse):
    id_notificacion: int
    tipo: str
    titulo: str | None
    contenido: str
    estado: str
    fecha_creacion: datetime


class AdminNotificationResponse(BaseModel):
    id_notificacion: int
    id_usuario: int | None
    destinatario_nombre: str | None = None
    destinatario_email: str | None = None
    tipo: str
    canal: str
    proveedor: str
    destinatario: str | None = None
    titulo: str | None = None
    contenido: str
    estado: str
    external_message_id: str | None = None
    fecha_creacion: datetime
    fecha_envio: datetime | None = None
    fecha_entrega: datetime | None = None
    error_mensaje: str | None = None


class NotificationKpis(BaseModel):
    total: int
    enviadas: int
    pendientes: int
    fallidas: int


class AdminNotificationPage(BaseModel):
    items: list[AdminNotificationResponse]
    total: int
    kpis: NotificationKpis
    page: int
    page_size: int


class ManualNotificationCreate(BaseModel):
    id_usuario: int
    titulo: str
    contenido: str
    canal: str = "SISTEMA"
    tipo: str = "AVISO_OPERATIVO"


class DeviceTokenRegisterRequest(BaseModel):
    token: str = Field(min_length=10, max_length=500)
    plataforma: str = Field(default="ios", max_length=20)
    dispositivo_info: str | None = Field(default=None, max_length=200)


class DeviceTokenResponse(BaseModel):
    mensaje: str
    registrado: bool


class SupplierPurchaseHistoryItem(BaseModel):
    fecha_recepcion: datetime
    proveedor: str
    id_orden_compra: int | None
    id_recepcion: int
    producto: str
    id_variante: int
    sku: str
    talla: str
    color: str
    cantidad: int
    precio_unitario: Decimal
    subtotal: Decimal
    total_compra: Decimal
    sucursal: str
    estado: str
    usuario_responsable: str | None


class SupplierPurchaseHistoryPage(BaseModel):
    items: list[SupplierPurchaseHistoryItem]
    total: int
    page: int
    page_size: int


CampaignState = Literal["BORRADOR", "PROGRAMADA", "ENVIANDO", "FINALIZADA", "CANCELADA"]


class CampaignCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    descripcion: str = Field(min_length=5, max_length=250)
    asunto_email: str | None = Field(default=None, max_length=180)
    segmento_objetivo: str = Field(default="TODOS", max_length=150)
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None


class CampaignUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=150)
    descripcion: str | None = Field(default=None, min_length=5, max_length=250)
    asunto_email: str | None = Field(default=None, max_length=180)
    segmento_objetivo: str | None = Field(default=None, max_length=150)
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    estado: Literal["BORRADOR", "PROGRAMADA", "CANCELADA"] | None = None


class CampaignResponse(ORMResponse):
    id_campania: int
    nombre: str
    descripcion: str | None = None
    asunto_email: str | None = None
    segmento_objetivo: str | None = None
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    estado: str
    created_at: datetime
    updated_at: datetime
    total_notificaciones: int = 0


class CampaignLaunchResponse(BaseModel):
    id_campania: int
    nombre: str
    estado: str
    destinatarios_notificados: int
    mensaje: str


class PromotionCreate(BaseModel):
    nombre: str = Field(min_length=3, max_length=150)
    descripcion: str | None = Field(default=None, max_length=250)
    porcentaje_descuento: Decimal = Field(gt=0, le=100)
    fecha_inicio: datetime
    fecha_fin: datetime
    activo: bool = True
    producto_ids: list[int] = Field(default_factory=list)
    categoria_ids: list[int] = Field(default_factory=list)
    temporada_ids: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self) -> "PromotionCreate":
        if self.fecha_fin <= self.fecha_inicio:
            raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio")
        return self


class PromotionUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=3, max_length=150)
    descripcion: str | None = Field(default=None, max_length=250)
    porcentaje_descuento: Decimal | None = Field(default=None, gt=0, le=100)
    fecha_inicio: datetime | None = None
    fecha_fin: datetime | None = None
    activo: bool | None = None
    producto_ids: list[int] | None = None
    categoria_ids: list[int] | None = None
    temporada_ids: list[int] | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "PromotionUpdate":
        if self.fecha_inicio is not None and self.fecha_fin is not None:
            if self.fecha_fin <= self.fecha_inicio:
                raise ValueError("La fecha de fin debe ser posterior a la fecha de inicio")
        return self


class PromotionResponse(ORMResponse):
    id_promocion: int
    nombre: str
    descripcion: str | None = None
    porcentaje_descuento: Decimal
    fecha_inicio: datetime
    fecha_fin: datetime
    activo: bool
    created_at: datetime
    updated_at: datetime
    producto_ids: list[int] = Field(default_factory=list)
    categoria_ids: list[int] = Field(default_factory=list)
    temporada_ids: list[int] = Field(default_factory=list)
    productos_count: int = 0
    categorias_count: int = 0
    temporadas_count: int = 0
    estado_vigencia: str = "VIGENTE"


class ActivePromotionItem(BaseModel):
    id_promocion: int
    nombre: str
    descripcion: str | None = None
    porcentaje_descuento: Decimal
    fecha_inicio: datetime
    fecha_fin: datetime
    productos_count: int = 0
    categorias_count: int = 0
    temporadas_count: int = 0


class DashboardKpis(BaseModel):
    ventas_mes_total: Decimal
    ventas_crecimiento_pct: float
    pedidos_pendientes: int
    reservas_hoy: int
    alertas_stock_critico: int


class DashboardDailyRevenue(BaseModel):
    fecha: str
    dia_nombre: str
    total: Decimal


class DashboardBranchShare(BaseModel):
    id_sucursal: int | None
    nombre: str
    total: Decimal
    porcentaje: float


class DashboardUrgentOrder(BaseModel):
    id_pedido: int
    id_venta: int
    cliente_nombre: str
    tipo_entrega: str
    estado: str
    total: Decimal
    fecha_creacion: datetime


class DashboardTopProduct(BaseModel):
    id_producto: int
    nombre: str
    categoria: str
    marca: str
    unidades_vendidas: int
    total_recaudado: Decimal
    imagen_url: str | None = None


class AdminDashboardSummaryResponse(BaseModel):
    kpis: DashboardKpis
    tendencia_semanal: list[DashboardDailyRevenue]
    ventas_por_sucursal: list[DashboardBranchShare]
    pedidos_urgentes: list[DashboardUrgentOrder]
    top_productos: list[DashboardTopProduct]



