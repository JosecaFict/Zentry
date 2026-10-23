from typing import Annotated

from fastapi import APIRouter, Depends, File, Request, UploadFile, status

from app.integrations.cloudinary import CloudinaryStorage
from app.modules.auth.dependencies import (
    CurrentPrincipal,
    build_request_audit_context,
    get_auth_service,
    get_current_principal,
    get_password_recovery_service,
)
from app.modules.auth.password_recovery_service import PasswordRecoveryService
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    PasswordRecoveryRequest,
    PasswordRecoveryVerifyRequest,
    PasswordRecoveryVerifyResponse,
    PasswordResetRequest,
    RegisterRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.modules.catalog.dependencies import get_cloudinary_storage

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(  # [CU-01] Registro de cliente
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_customer(
    payload: RegisterRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> UserResponse:
    return await service.register_customer(payload, build_request_audit_context(request))


@router.post("/login", response_model=TokenResponse)  # [CU-01] Inicio de sesión (Login)
async def login(
    payload: LoginRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> TokenResponse:
    return await service.login(payload, build_request_audit_context(request))


@router.post(
    "/password-recovery/request", response_model=MessageResponse
)  # [CU-08] Solicitar código OTP
async def request_password_recovery(
    payload: PasswordRecoveryRequest,
    service: Annotated[PasswordRecoveryService, Depends(get_password_recovery_service)],
) -> MessageResponse:
    return await service.request_code(payload)


@router.post(  # [CU-08] Verificar código OTP
    "/password-recovery/verify",
    response_model=PasswordRecoveryVerifyResponse,
)
async def verify_password_recovery_code(
    payload: PasswordRecoveryVerifyRequest,
    service: Annotated[PasswordRecoveryService, Depends(get_password_recovery_service)],
) -> PasswordRecoveryVerifyResponse:
    return await service.verify_code(payload)


@router.post(
    "/password-recovery/reset", response_model=MessageResponse
)  # [CU-08] Restablecer contraseña con token OTP
async def reset_password(
    payload: PasswordResetRequest,
    request: Request,
    service: Annotated[PasswordRecoveryService, Depends(get_password_recovery_service)],
) -> MessageResponse:
    return await service.reset_password(payload, build_request_audit_context(request))


@router.get("/me", response_model=UserResponse)  # [CU-01] Consultar perfil y sesión activa
async def me(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
) -> UserResponse:
    user = principal.user
    return UserResponse(
        id_usuario=user.id_usuario,
        nombres=user.nombres,
        apellidos=user.apellidos,
        correo=user.correo,
        telefono=user.telefono,
        ci=user.ci,
        estado=user.estado,
        created_at=user.created_at,
        roles=sorted(principal.roles),
        permisos=sorted(principal.permissions),
        id_sucursal=principal.id_sucursal,
        sucursal=principal.sucursal,
        avatar_url=user.avatar_url,
    )


@router.patch("/me", response_model=UserResponse)  # [CU-01] Actualizar datos del perfil
async def update_profile(
    payload: UpdateProfileRequest,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    request: Request,
) -> UserResponse:
    audit_context = build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
    )
    user = await service.update_profile(principal.user.id_usuario, payload, audit_context)
    return UserResponse(
        id_usuario=user.id_usuario,
        nombres=user.nombres,
        apellidos=user.apellidos,
        correo=user.correo,
        telefono=user.telefono,
        ci=user.ci,
        estado=user.estado,
        created_at=user.created_at,
        roles=sorted(principal.roles),
        permisos=sorted(principal.permissions),
        id_sucursal=principal.id_sucursal,
        sucursal=principal.sucursal,
        avatar_url=user.avatar_url,
    )


@router.post(
    "/me/avatar", response_model=UserResponse
)  # [CU-01] Subir foto de perfil (Avatar) a Cloudinary
async def upload_avatar(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    storage: Annotated[CloudinaryStorage, Depends(get_cloudinary_storage)],
    request: Request,
    file: UploadFile = File(...),  # noqa: B008 - FastAPI multipart parameter declaration
) -> UserResponse:
    audit_context = build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
    )
    user = await service.upload_avatar(principal.user.id_usuario, file, storage, audit_context)
    return UserResponse(
        id_usuario=user.id_usuario,
        nombres=user.nombres,
        apellidos=user.apellidos,
        correo=user.correo,
        telefono=user.telefono,
        ci=user.ci,
        estado=user.estado,
        created_at=user.created_at,
        roles=sorted(principal.roles),
        permisos=sorted(principal.permissions),
        id_sucursal=principal.id_sucursal,
        sucursal=principal.sucursal,
        avatar_url=user.avatar_url,
    )


@router.delete(
    "/me/avatar", response_model=UserResponse
)  # [CU-01] Eliminar foto de perfil (Avatar)
async def delete_avatar(
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    request: Request,
) -> UserResponse:
    audit_context = build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
    )
    user = await service.delete_avatar(principal.user.id_usuario, audit_context)
    return UserResponse(
        id_usuario=user.id_usuario,
        nombres=user.nombres,
        apellidos=user.apellidos,
        correo=user.correo,
        telefono=user.telefono,
        ci=user.ci,
        estado=user.estado,
        created_at=user.created_at,
        roles=sorted(principal.roles),
        permisos=sorted(principal.permissions),
        id_sucursal=principal.id_sucursal,
        sucursal=principal.sucursal,
        avatar_url=user.avatar_url,
    )


@router.post("/change-password", response_model=MessageResponse)  # [CU-01] Cambiar contraseña
async def change_password(
    payload: ChangePasswordRequest,
    principal: Annotated[CurrentPrincipal, Depends(get_current_principal)],
    service: Annotated[AuthService, Depends(get_auth_service)],
    request: Request,
) -> MessageResponse:
    audit_context = build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
    )
    await service.change_password(principal.user.id_usuario, payload, audit_context)
    return MessageResponse(message="Contraseña actualizada exitosamente")
