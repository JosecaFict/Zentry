export interface PlatformOverview {
  tenants_total: number;
  tenants_activos: number;
  tenants_suspendidos: number;
  sucursales_activas: number;
  suscripciones_por_vencer: number;
  suscripciones_en_gracia: number;
  suscripciones_suspendidas: number;
}

export interface PlatformPlan {
  id_plan: number;
  codigo: string;
  nombre: string;
  max_sucursales_activas: number;
  max_usuarios_internos: number;
  max_productos_activos: number;
  almacenamiento_mb: number;
  precio_mensual: number;
  precio_anual: number;
  permite_reportes_convencionales: boolean;
  permite_reportes_ia: boolean;
  permite_offline: boolean;
  activo: boolean;
}

export interface PlatformTenant {
  id_tenant: number;
  nombre: string;
  slug: string;
  logo_url: string | null;
  estado: string;
  plan_codigo: string | null;
  plan_nombre: string | null;
  subscription_estado: string | null;
  fecha_fin: string | null;
  sucursales_activas: number;
  created_at: string;
  usuarios?: number;
  administradores?: number;
  razon_social?: string | null;
  nit?: string | null;
  correo_contacto?: string | null;
  telefono_contacto?: string | null;
  id_plan?: number | null;
  color_primario?: string;
  color_primario_oscuro?: string;
  modalidad?: 'MENSUAL' | 'ANUAL' | null;
  precio_acordado?: number | null;
  proxima_renovacion?: string | null;
  fecha_fin_gracia?: string | null;
  max_sucursales_activas?: number | null;
  max_usuarios_internos?: number | null;
  max_productos_activos?: number | null;
  almacenamiento_mb?: number | null;
  usuarios_internos?: number;
  productos_activos?: number;
}

export interface PlatformTenantCreate {
  nombre: string;
  slug: string;
  razon_social: string | null;
  nit: string | null;
  correo_contacto: string | null;
  telefono_contacto: string | null;
  logo_url: string | null;
  color_primario: string;
  color_primario_oscuro: string;
  id_plan: number;
  modalidad: 'MENSUAL' | 'ANUAL';
  fecha_fin: string | null;
  administrador: {
    nombres: string;
    apellidos: string;
    correo: string;
    telefono: string | null;
    ci: string | null;
    password: string;
  };
}

export interface PlatformTenantUpdate {
  nombre: string;
  razon_social: string | null;
  nit: string | null;
  correo_contacto: string | null;
  telefono_contacto: string | null;
  logo_url: string | null;
  color_primario: string;
  color_primario_oscuro: string;
  id_plan: number;
  modalidad: 'MENSUAL' | 'ANUAL';
  fecha_fin: string | null;
}

export interface PlatformPayment {
  id_payment: number;
  importe: number;
  moneda: string;
  metodo_pago: string;
  referencia: string | null;
  fecha_pago: string;
  estado: string;
  created_at: string;
}

export interface PlatformPaymentCreate {
  modalidad: 'MENSUAL' | 'ANUAL';
  metodo_pago: 'TRANSFERENCIA' | 'QR' | 'EFECTIVO' | 'OTRO';
  referencia: string | null;
  fecha_pago: string;
}
