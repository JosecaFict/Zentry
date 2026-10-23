export interface TenantBrand {
  id_tenant: number;
  nombre: string;
  slug: string;
  logo_url: string | null;
  color_primario: string;
  color_primario_oscuro: string;
  estado: string;
  subscription_estado: string | null;
  fecha_fin: string | null;
  fecha_fin_gracia: string | null;
  dias_para_vencimiento: number | null;
}

export interface TenantBrandUpdate {
  nombre: string;
  logo_url: string | null;
  color_primario: string;
  color_primario_oscuro: string;
}
