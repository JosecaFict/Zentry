from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.modules.auth.dependencies import (
    CurrentPrincipal,
    build_request_audit_context,
    require_permission,
)
from app.modules.employees.dependencies import get_employee_service
from app.modules.employees.schemas import (
    EmployeeCreateRequest,
    EmployeePermissionSummary,
    EmployeeResponse,
    EmployeeUpdateRequest,
    PermissionOverrideRequest,
    PermissionResponse,
    RoleAssignmentRequest,
    RolePermissionSummary,
    RolePermissionUpdate,
    RoleResponse,
)
from app.modules.employees.service import EmployeeService

router = APIRouter(tags=["employee administration"])


def audit_context_for(request: Request, principal: CurrentPrincipal):
    return build_request_audit_context(
        request,
        user_id=principal.user.id_usuario,
        session_id=principal.session_id,
        tenant_id=principal.id_tenant,
    )


@router.get(
    "/employees", response_model=list[EmployeeResponse]
)  # [CU-02] Listar personal de sucursales
async def list_employees(
    _: Annotated[CurrentPrincipal, Depends(require_permission("empleados.ver"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> list[EmployeeResponse]:
    return await service.list_employees()


@router.get(
    "/employees/{employee_id}", response_model=EmployeeResponse
)  # [CU-02] Consultar datos de un empleado
async def get_employee(
    employee_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("empleados.ver"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    return await service.get_employee(employee_id)


@router.post(  # [CU-02] Crear nuevo empleado asignado a sucursal
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_employee(
    payload: EmployeeCreateRequest,
    request: Request,
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("empleados.crear")),
    ],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    return await service.create_employee(
        payload,
        actor=principal,
        audit_context=audit_context_for(request, principal),
    )


@router.patch(
    "/employees/{employee_id}", response_model=EmployeeResponse
)  # [CU-02] Actualizar datos o estado de empleado
async def update_employee(
    employee_id: int,
    payload: EmployeeUpdateRequest,
    request: Request,
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("empleados.editar")),
    ],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    return await service.update_employee(
        employee_id,
        payload,
        audit_context=audit_context_for(request, principal),
    )


@router.get("/roles", response_model=list[RoleResponse])  # [CU-02] Listar catálogo de roles
async def list_roles(
    _: Annotated[CurrentPrincipal, Depends(require_permission("permisos.asignar"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> list[RoleResponse]:
    return await service.list_roles()


@router.get(
    "/permissions", response_model=list[PermissionResponse]
)  # [CU-02] Listar catálogo de permisos
async def list_permissions(
    _: Annotated[CurrentPrincipal, Depends(require_permission("permisos.asignar"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> list[PermissionResponse]:
    return await service.list_permissions()


@router.get(
    "/roles/{role_id}/permissions", response_model=RolePermissionSummary
)  # [CU-02] Consultar permisos de un rol
async def get_role_permissions(
    role_id: int,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("permisos.asignar"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> RolePermissionSummary:
    return await service.get_role_permissions(role_id, actor=principal)


@router.put(  # [CU-02] Configurar permisos a un rol
    "/roles/{role_id}/permissions/{permission_id}",
    response_model=RolePermissionSummary,
)
async def set_role_permission(
    role_id: int,
    permission_id: int,
    payload: RolePermissionUpdate,
    request: Request,
    principal: Annotated[CurrentPrincipal, Depends(require_permission("permisos.asignar"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> RolePermissionSummary:
    return await service.set_role_permission(
        role_id,
        permission_id,
        enabled=payload.habilitado,
        actor=principal,
        audit_context=audit_context_for(request, principal),
    )


@router.get(  # [CU-02] Consultar permisos individuales de un empleado
    "/employees/{employee_id}/permissions",
    response_model=EmployeePermissionSummary,
)
async def get_employee_permissions(
    employee_id: int,
    _: Annotated[CurrentPrincipal, Depends(require_permission("permisos.asignar"))],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeePermissionSummary:
    return await service.get_employee_permissions(employee_id)


@router.put(  # [CU-02] Sobreescribir permiso individual a empleado (RBAC Dinámico)
    "/employees/{employee_id}/permissions/{permission_id}",
    response_model=EmployeePermissionSummary,
)
async def set_employee_permission(
    employee_id: int,
    permission_id: int,
    payload: PermissionOverrideRequest,
    request: Request,
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("permisos.asignar")),
    ],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeePermissionSummary:
    return await service.set_permission_override(
        employee_id,
        permission_id,
        granted=payload.otorgado,
        actor=principal,
        audit_context=audit_context_for(request, principal),
    )


@router.delete(  # [CU-02] Eliminar sobreescritura de permiso a empleado
    "/employees/{employee_id}/permissions/{permission_id}",
    response_model=EmployeePermissionSummary,
)
async def clear_employee_permission(
    employee_id: int,
    permission_id: int,
    request: Request,
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("permisos.asignar")),
    ],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeePermissionSummary:
    return await service.clear_permission_override(
        employee_id,
        permission_id,
        audit_context=audit_context_for(request, principal),
    )


@router.put(
    "/employees/{employee_id}/role", response_model=EmployeeResponse
)  # [CU-02] Cambiar rol a un empleado
async def change_employee_role(
    employee_id: int,
    payload: RoleAssignmentRequest,
    request: Request,
    principal: Annotated[
        CurrentPrincipal,
        Depends(require_permission("permisos.asignar")),
    ],
    service: Annotated[EmployeeService, Depends(get_employee_service)],
) -> EmployeeResponse:
    return await service.change_role(
        employee_id,
        payload.id_rol,
        actor=principal,
        audit_context=audit_context_for(request, principal),
    )
