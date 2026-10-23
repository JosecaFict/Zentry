from datetime import UTC, datetime

from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.tenant_context import current_tenant_id
from app.integrations.cloudinary import CloudinaryStorage
from app.modules.auth.exceptions import (
    AccountPermanentlyBlockedError,
    AccountTemporarilyLockedError,
    CiAlreadyRegisteredError,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidAvatarError,
    InvalidCredentialsError,
    SecurityConfigurationError,
)
from app.modules.auth.models import Usuario
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.modules.auth.throttler import InMemoryLoginThrottler, LoginThrottler


def normalize_email(email: str) -> str:
    return email.strip().lower()


def tenant_identity_key(email: str, tenant_id: int | None = None) -> str:
    resolved_tenant = current_tenant_id() if tenant_id is None else tenant_id
    scope = str(resolved_tenant) if resolved_tenant is not None else "global"
    return f"{scope}:{email}"


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        repository: AuthRepository,
        throttler: LoginThrottler | None = None,
    ) -> None:
        self.session = session
        self.repository = repository
        self.throttler = throttler or InMemoryLoginThrottler()

    async def register_customer(
        self,
        payload: RegisterRequest,
        audit_context: AuditContext,
    ) -> UserResponse:
        email = normalize_email(str(payload.correo))
        if current_tenant_id() is None:
            raise SecurityConfigurationError("Tenant context is required for customer registration")
        try:
            await apply_audit_context(self.session, audit_context)
            if await self.repository.get_user_by_email(email) is not None:
                raise EmailAlreadyRegisteredError
            if payload.ci and await self.repository.get_user_by_ci(payload.ci) is not None:
                raise CiAlreadyRegisteredError

            client_role = await self.repository.get_active_role_by_name("CLIENTE")
            if client_role is None:
                raise SecurityConfigurationError("Active CLIENTE role is missing")

            user = Usuario(
                nombres=payload.nombres,
                apellidos=payload.apellidos,
                correo=email,
                telefono=payload.telefono,
                ci=payload.ci,
                password_hash=hash_password(payload.password.get_secret_value()),
                estado="ACTIVO",
            )
            await self.repository.create_customer_user(user=user, client_role=client_role)
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            error_prefix = str(exc).split("[SQL:")[0].lower()
            constraint = (getattr(exc.orig, "constraint_name", "") or "").lower()
            detail = (getattr(exc.orig, "detail", "") or "").lower()
            check_text = f"{error_prefix} {constraint} {detail}"
            if "ci" in check_text or "usuario_ci" in check_text:
                raise CiAlreadyRegisteredError from exc
            if (
                "correo" in check_text
                or "usuario_correo" in check_text
                or getattr(exc.orig, "sqlstate", None) == "23505"
            ):
                raise EmailAlreadyRegisteredError from exc
            raise
        except Exception:
            await self.session.rollback()
            raise

        return self._user_response(user, roles={"CLIENTE"}, permissions=set())

    async def login(
        self,
        payload: LoginRequest,
        audit_context: AuditContext,
    ) -> TokenResponse:
        email = normalize_email(str(payload.correo))
        throttle_key = tenant_identity_key(email)

        # 1. Verificar si la cuenta está en pausa temporal de seguridad (cooldown)
        cooldown = await self.throttler.get_cooldown_remaining(throttle_key)
        if cooldown is not None:
            raise AccountTemporarilyLockedError(retry_after=cooldown)

        try:
            user = await self.repository.get_user_by_email(email)
            requested_tenant = current_tenant_id()
            if (
                user is not None
                and requested_tenant is not None
                and user.id_tenant != requested_tenant
            ):
                user = None

            # 2. Si la cuenta ya está bloqueada de forma permanente
            if user is not None and user.estado == "BLOQUEADO":
                raise AccountPermanentlyBlockedError(
                    "Tu cuenta ha sido bloqueada tras múltiples intentos fallidos. Debes recuperar tu contraseña para desbloquearla."
                )

            # 3. Validar credenciales
            if user is None or not verify_password(
                payload.password.get_secret_value(), user.password_hash
            ):
                attempts, cooldown_triggered = await self.throttler.record_failed_attempt(
                    throttle_key
                )
                if cooldown_triggered is not None:
                    raise AccountTemporarilyLockedError(retry_after=cooldown_triggered)

                if attempts >= 9:
                    if user is not None:
                        user.estado = "BLOQUEADO"
                        await self.repository.update_user_status(user, "BLOQUEADO")
                        await self.session.commit()
                    raise AccountPermanentlyBlockedError(
                        "Tu cuenta ha sido bloqueada tras alcanzar 9 intentos fallidos. Debes recuperar tu contraseña para desbloquearla."
                    )

                if attempts < 3:
                    remaining = 3 - attempts
                    msg = f"El correo o la contraseña no son correctos. Te quedan {remaining} intento(s) antes de una pausa de seguridad."
                elif attempts < 6:
                    remaining = 6 - attempts
                    msg = f"El correo o la contraseña no son correctos. Te quedan {remaining} intento(s) antes de una pausa de 5 minutos."
                else:
                    remaining = 9 - attempts
                    msg = f"El correo o la contraseña no son correctos. Te quedan {remaining} intento(s) antes del bloqueo definitivo de tu cuenta."

                raise InvalidCredentialsError(detail=msg)

            if user.estado != "ACTIVO":
                raise InactiveUserError(user.estado)

            # 4. Credenciales válidas -> Limpiar registro de fallos en throttler
            await self.throttler.clear(throttle_key)

            authenticated_context = AuditContext(
                usuario_id=user.id_usuario,
                sesion_id=audit_context.sesion_id,
                ip=audit_context.ip,
                user_agent=audit_context.user_agent,
                origen=audit_context.origen,
                request_id=audit_context.request_id,
            )
            await apply_audit_context(self.session, authenticated_context)
            user.ultimo_acceso = datetime.now(UTC)
            await self.repository.update_last_access(user)
            await self.session.commit()
        except (
            AccountTemporarilyLockedError,
            AccountPermanentlyBlockedError,
            InvalidCredentialsError,
            InactiveUserError,
        ):
            raise
        except Exception:
            await self.session.rollback()
            raise

        token, expires_in = create_access_token(user.id_usuario)
        return TokenResponse(access_token=token, expires_in=expires_in)

    async def update_profile(
        self,
        user_id: int,
        payload: UpdateProfileRequest,
        audit_context: AuditContext,
    ) -> Usuario:
        try:
            await apply_audit_context(self.session, audit_context)
            if payload.ci:
                existing_ci_user = await self.repository.get_user_by_ci(payload.ci)
                if existing_ci_user is not None and existing_ci_user.id_usuario != user_id:
                    raise CiAlreadyRegisteredError

            user = await self.repository.update_profile(
                user_id,
                nombres=payload.nombres,
                apellidos=payload.apellidos,
                telefono=payload.telefono,
                ci=payload.ci,
            )
            await self.session.commit()
            return user
        except IntegrityError as exc:
            await self.session.rollback()
            error_prefix = str(exc).split("[SQL:")[0].lower()
            constraint = (getattr(exc.orig, "constraint_name", "") or "").lower()
            detail = (getattr(exc.orig, "detail", "") or "").lower()
            check_text = f"{error_prefix} {constraint} {detail}"
            if "ci" in check_text or "usuario_ci" in check_text:
                raise CiAlreadyRegisteredError from exc
            raise
        except Exception:
            await self.session.rollback()
            raise

    async def upload_avatar(
        self,
        user_id: int,
        file: UploadFile,
        storage: CloudinaryStorage,
        audit_context: AuditContext,
    ) -> Usuario:
        content_type = file.content_type or "image/jpeg"
        if content_type.lower() not in {"image/jpeg", "image/png", "image/webp", "image/jpg"}:
            raise InvalidAvatarError("Formato no soportado. Usa imágenes JPG, PNG o WebP.")
        content = await file.read()
        if len(content) == 0:
            raise InvalidAvatarError("El archivo de imagen está vacío.")
        if len(content) > 5 * 1024 * 1024:
            raise InvalidAvatarError("La imagen supera el tamaño máximo permitido de 5 MB.")

        try:
            await apply_audit_context(self.session, audit_context)
            user = await self.repository.get_user_by_id(user_id)
            if user is None or user.estado != "ACTIVO":
                raise InactiveUserError("Usuario no encontrado o inactivo")

            upload = await storage.upload_avatar_image(
                user_id=user_id,
                content=content,
                filename=file.filename or f"avatar_{user_id}.jpg",
                content_type=content_type,
            )
            user.avatar_url = upload.secure_url
            await self.session.commit()
            return user
        except Exception:
            await self.session.rollback()
            raise

    async def delete_avatar(
        self,
        user_id: int,
        audit_context: AuditContext,
    ) -> Usuario:
        try:
            await apply_audit_context(self.session, audit_context)
            user = await self.repository.get_user_by_id(user_id)
            if user is None or user.estado != "ACTIVO":
                raise InactiveUserError("Usuario no encontrado o inactivo")
            user.avatar_url = None
            await self.session.commit()
            return user
        except Exception:
            await self.session.rollback()
            raise

    async def change_password(
        self,
        user_id: int,
        payload: ChangePasswordRequest,
        audit_context: AuditContext,
    ) -> None:
        try:
            await apply_audit_context(self.session, audit_context)
            user = await self.repository.get_user_by_id(user_id)
            if user is None or user.estado != "ACTIVO":
                raise InactiveUserError("User not found or inactive")
            if not verify_password(payload.current_password.get_secret_value(), user.password_hash):
                raise InvalidCredentialsError("Current password is incorrect")
            new_hash = hash_password(payload.new_password.get_secret_value())
            await self.repository.update_password(user, new_hash)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _user_response(
        user: Usuario,
        *,
        roles: set[str],
        permissions: set[str],
    ) -> UserResponse:
        return UserResponse(
            id_usuario=user.id_usuario,
            nombres=user.nombres,
            apellidos=user.apellidos,
            correo=user.correo,
            telefono=user.telefono,
            ci=user.ci,
            estado=user.estado,
            created_at=user.created_at,
            roles=sorted(roles),
            permisos=sorted(permissions),
            avatar_url=user.avatar_url,
        )
