import calendar
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.modules.auth.service import normalize_email
from app.modules.platform.models import SubscriptionPayment
from app.modules.platform.repository import PlatformRepository
from app.modules.platform.schemas import (
    PlanResponse,
    PlatformOverview,
    SubscriptionPaymentCreate,
    SubscriptionPaymentResponse,
    TenantBrandUpdate,
    TenantContextResponse,
    TenantCreate,
    TenantDetail,
    TenantListItem,
    TenantPublicResponse,
    TenantStatusUpdate,
    TenantUpdate,
)


class PlatformService:
    def __init__(self, repository: PlatformRepository) -> None:
        self.repository = repository

    async def overview(self) -> PlatformOverview:
        total, active, suspended, branches, expiring, grace, subscription_suspended = (
            await self.repository.overview()
        )
        return PlatformOverview(
            tenants_total=total,
            tenants_activos=active,
            tenants_suspendidos=suspended,
            sucursales_activas=branches,
            suscripciones_por_vencer=expiring,
            suscripciones_en_gracia=grace,
            suscripciones_suspendidas=subscription_suspended,
        )

    async def tenant_context(self, tenant_id: int) -> TenantContextResponse:
        tenant = await self.repository.get_tenant(tenant_id)
        if tenant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada",
            )
        subscription_row = await self.repository.get_subscription(tenant_id)
        subscription = subscription_row[0] if subscription_row else None
        days = None
        if subscription and subscription.fecha_fin:
            days = (subscription.fecha_fin - date.today()).days
        return TenantContextResponse(
            id_tenant=tenant.id_tenant,
            nombre=tenant.nombre,
            slug=tenant.slug,
            logo_url=tenant.logo_url,
            color_primario=tenant.color_primario,
            color_primario_oscuro=tenant.color_primario_oscuro,
            estado=tenant.estado,
            subscription_estado=subscription.estado if subscription else None,
            fecha_fin=subscription.fecha_fin if subscription else None,
            fecha_fin_gracia=subscription.fecha_fin_gracia if subscription else None,
            dias_para_vencimiento=days,
        )

    async def update_tenant_brand(
        self, tenant_id: int, payload: TenantBrandUpdate
    ) -> TenantContextResponse:
        updated = await self.repository.update_tenant_brand(tenant_id, payload)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada",
            )
        await self.repository.commit()
        return await self.tenant_context(tenant_id)

    async def list_plans(self) -> list[PlanResponse]:
        plans = await self.repository.list_plans()
        return [PlanResponse.model_validate(plan, from_attributes=True) for plan in plans]

    async def list_tenants(self) -> list[TenantListItem]:
        return [self._tenant_item(*row) for row in await self.repository.list_tenants()]

    async def search_public_tenants(self, query: str) -> list[TenantPublicResponse]:
        tenants = await self.repository.search_public_tenants(query)
        return [
            TenantPublicResponse(
                nombre=tenant.nombre,
                slug=tenant.slug,
                logo_url=tenant.logo_url,
                color_primario=tenant.color_primario,
                color_primario_oscuro=tenant.color_primario_oscuro,
            )
            for tenant in tenants
        ]

    async def tenant_detail(self, tenant_id: int) -> TenantDetail:
        row = await self.repository.tenant_detail(tenant_id)
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada",
            )
        tenant, subscription, plan, branches, users, admins, internal_users, products = row
        item = self._tenant_item(tenant, subscription, plan, branches)
        return TenantDetail(
            **item.model_dump(),
            usuarios=users,
            administradores=admins,
            razon_social=tenant.razon_social,
            nit=tenant.nit,
            correo_contacto=tenant.correo_contacto,
            telefono_contacto=tenant.telefono_contacto,
            id_plan=plan.id_plan if plan else None,
            color_primario=tenant.color_primario,
            color_primario_oscuro=tenant.color_primario_oscuro,
            modalidad=subscription.modalidad if subscription else None,
            precio_acordado=subscription.precio_acordado if subscription else None,
            proxima_renovacion=subscription.proxima_renovacion if subscription else None,
            fecha_fin_gracia=subscription.fecha_fin_gracia if subscription else None,
            max_sucursales_activas=plan.max_sucursales_activas if plan else None,
            max_usuarios_internos=plan.max_usuarios_internos if plan else None,
            max_productos_activos=plan.max_productos_activos if plan else None,
            almacenamiento_mb=plan.almacenamiento_mb if plan else None,
            usuarios_internos=internal_users,
            productos_activos=products,
        )

    async def register_payment(
        self, tenant_id: int, payload: SubscriptionPaymentCreate
    ) -> TenantDetail:
        record = await self.repository.get_subscription(tenant_id)
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Suscripción no encontrada"
            )
        subscription, plan = record
        amount = plan.precio_mensual if payload.modalidad == "MENSUAL" else plan.precio_anual
        start = max(
            date.today(),
            (subscription.fecha_fin + timedelta(days=1))
            if subscription.fecha_fin
            else date.today(),
        )
        end = self._add_months(start, 1 if payload.modalidad == "MENSUAL" else 12) - timedelta(
            days=1
        )
        payment = SubscriptionPayment(
            id_subscription=subscription.id_subscription,
            importe=amount,
            moneda="BOB",
            metodo_pago=payload.metodo_pago,
            referencia=payload.referencia.strip() if payload.referencia else None,
            fecha_pago=payload.fecha_pago,
            estado="CONFIRMADO",
        )
        subscription.modalidad = payload.modalidad
        subscription.precio_acordado = amount
        subscription.estado = "ACTIVA"
        subscription.fecha_inicio = start
        subscription.fecha_fin = end
        subscription.proxima_renovacion = end + timedelta(days=1)
        subscription.fecha_fin_gracia = end + timedelta(days=7)
        await self.repository.add_payment(payment)
        await self.repository.commit()
        return await self.tenant_detail(tenant_id)

    async def list_payments(self, tenant_id: int) -> list[SubscriptionPaymentResponse]:
        if await self.repository.get_tenant(tenant_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Empresa no encontrada"
            )
        return [
            SubscriptionPaymentResponse.model_validate(payment, from_attributes=True)
            for payment in await self.repository.list_payments(tenant_id)
        ]

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, calendar.monthrange(year, month)[1])
        return date(year, month, day)

    async def create_tenant(self, payload: TenantCreate) -> TenantDetail:
        if payload.fecha_fin is not None and payload.fecha_fin < date.today():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La fecha de vencimiento no puede estar en el pasado",
            )
        email = normalize_email(str(payload.administrador.correo))
        if await self.repository.tenant_identity_exists(payload.slug, payload.nit):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="El slug o NIT ya está registrado"
            )
        try:
            tenant_id = await self.repository.provision_tenant(
                payload,
                email=email,
                password_hash=hash_password(payload.administrador.password.get_secret_value()),
            )
            await self.repository.commit()
        except LookupError as exc:
            await self.repository.rollback()
            detail = "El plan seleccionado no está disponible"
            if str(exc) == "ADMIN_ROLE_NOT_FOUND":
                detail = "No existe una plantilla de rol ADMIN para aprovisionar la empresa"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        except IntegrityError as exc:
            await self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La empresa o el administrador ya están registrados",
            ) from exc
        return await self.tenant_detail(tenant_id)

    async def update_tenant(self, tenant_id: int, payload: TenantUpdate) -> TenantDetail:
        if payload.fecha_fin is not None and payload.fecha_fin < date.today():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La fecha de vencimiento no puede estar en el pasado",
            )
        if await self.repository.tenant_nit_exists(tenant_id, payload.nit):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El NIT ya está registrado por otra empresa",
            )
        try:
            updated = await self.repository.update_tenant(tenant_id, payload)
            if not updated:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Empresa no encontrada",
                )
            await self.repository.commit()
        except LookupError as exc:
            await self.repository.rollback()
            detail = (
                "El plan seleccionado no está disponible"
                if str(exc) == "PLAN_NOT_FOUND"
                else "La empresa no tiene una suscripción activa"
            )
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
        except IntegrityError as exc:
            await self.repository.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Los datos de la empresa entran en conflicto con otro registro",
            ) from exc
        return await self.tenant_detail(tenant_id)

    async def update_tenant_status(
        self, tenant_id: int, payload: TenantStatusUpdate
    ) -> TenantDetail:
        updated = await self.repository.update_tenant_status(tenant_id, payload.estado)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Empresa no encontrada",
            )
        await self.repository.commit()
        return await self.tenant_detail(tenant_id)

    @staticmethod
    def _tenant_item(tenant, subscription, plan, branches: int) -> TenantListItem:
        return TenantListItem(
            id_tenant=tenant.id_tenant,
            nombre=tenant.nombre,
            slug=tenant.slug,
            logo_url=tenant.logo_url,
            estado=tenant.estado,
            plan_codigo=plan.codigo if plan else None,
            plan_nombre=plan.nombre if plan else None,
            subscription_estado=subscription.estado if subscription else None,
            fecha_fin=subscription.fecha_fin if subscription else None,
            sucursales_activas=int(branches),
            created_at=tenant.created_at,
        )
