from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import (
    Empleado,
    Permiso,
    Rol,
    RolPermiso,
    Sucursal,
    Usuario,
    UsuarioPermiso,
    UsuarioRol,
)
from app.modules.auth.repository import AuthRepository
from app.modules.employees.exceptions import InvalidEmployeeDataError

MANAGED_EMPLOYEE_ROLES = frozenset({"ENCARGADO_SUCURSAL", "CAJERO", "AUXILIAR_INVENTARIO", "ADMIN"})


@dataclass(frozen=True, slots=True)
class EmployeeRecord:
    employee: Empleado
    user: Usuario
    branch: Sucursal
    roles: frozenset[str]


class EmployeeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.auth_repository = AuthRepository(session)

    async def count_active_employees(self) -> int:
        return int(
            await self.session.scalar(
                select(func.count(Empleado.id_empleado)).where(Empleado.estado_laboral == "ACTIVO")
            )
            or 0
        )
    async def list_employees(self) -> list[EmployeeRecord]:
        statement = (
            select(Empleado, Usuario, Sucursal)
            .join(Usuario, Usuario.id_usuario == Empleado.id_usuario)
            .join(Sucursal, Sucursal.id_sucursal == Empleado.id_sucursal)
            .order_by(Usuario.apellidos, Usuario.nombres, Empleado.id_empleado)
        )
        rows = (await self.session.execute(statement)).all()
        records: list[EmployeeRecord] = []
        for employee, user, branch in rows:
            roles = await self.auth_repository.get_role_names(user.id_usuario)
            records.append(
                EmployeeRecord(
                    employee=employee,
                    user=user,
                    branch=branch,
                    roles=frozenset(roles),
                )
            )
        return records

    async def get_employee(self, employee_id: int) -> EmployeeRecord | None:
        statement = (
            select(Empleado, Usuario, Sucursal)
            .join(Usuario, Usuario.id_usuario == Empleado.id_usuario)
            .join(Sucursal, Sucursal.id_sucursal == Empleado.id_sucursal)
            .where(Empleado.id_empleado == employee_id)
        )
        row = (await self.session.execute(statement)).one_or_none()
        if row is None:
            return None
        employee, user, branch = row
        roles = await self.auth_repository.get_role_names(user.id_usuario)
        return EmployeeRecord(
            employee=employee,
            user=user,
            branch=branch,
            roles=frozenset(roles),
        )

    async def get_user_by_email(self, email: str) -> Usuario | None:
        statement = select(Usuario).where(func.lower(Usuario.correo) == email)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_user_by_ci(self, ci: str) -> Usuario | None:
        statement = select(Usuario).where(Usuario.ci == ci)
        return (await self.session.execute(statement)).scalar_one_or_none()

    async def get_branch(self, branch_id: int) -> Sucursal | None:
        return await self.session.get(Sucursal, branch_id)

    async def get_role(self, role_id: int) -> Rol | None:
        return await self.session.get(Rol, role_id)

    async def get_permission(self, permission_id: int) -> Permiso | None:
        return await self.session.get(Permiso, permission_id)

    async def list_active_roles(self) -> list[Rol]:
        statement = select(Rol).where(Rol.activo.is_(True)).order_by(Rol.nombre)
        return list((await self.session.scalars(statement)).all())

    async def list_active_permissions(self) -> list[Permiso]:
        statement = (
            select(Permiso).where(Permiso.activo.is_(True)).order_by(Permiso.modulo, Permiso.codigo)
        )
        return list((await self.session.scalars(statement)).all())

    async def list_role_permission_codes(self, role_id: int) -> set[str]:
        statement = (
            select(Permiso.codigo)
            .join(RolPermiso, RolPermiso.id_permiso == Permiso.id_permiso)
            .where(RolPermiso.id_rol == role_id, Permiso.activo.is_(True))
        )
        return set((await self.session.scalars(statement)).all())

    async def set_role_permission(self, *, role_id: int, permission_id: int, enabled: bool) -> None:
        statement = select(RolPermiso).where(
            RolPermiso.id_rol == role_id,
            RolPermiso.id_permiso == permission_id,
        )
        assignment = await self.session.scalar(statement)
        if enabled and assignment is None:
            self.session.add(RolPermiso(id_rol=role_id, id_permiso=permission_id))
        elif not enabled and assignment is not None:
            await self.session.delete(assignment)
        await self.session.flush()

    async def create_employee(
        self,
        *,
        user: Usuario,
        employee: Empleado,
        role: Rol,
    ) -> EmployeeRecord:
        self.session.add(user)
        await self.session.flush()
        employee.id_usuario = user.id_usuario
        self.session.add(employee)
        await self.session.flush()
        self.session.add(UsuarioRol(id_usuario=user.id_usuario, id_rol=role.id_rol))
        await self.session.flush()
        branch = await self.get_branch(employee.id_sucursal)
        if branch is None:  # Defensive: the branch was validated under this transaction.
            raise RuntimeError("Branch disappeared during employee creation")
        return EmployeeRecord(
            employee=employee,
            user=user,
            branch=branch,
            roles=frozenset({role.nombre}),
        )

    async def flush_employee_update(self, record: EmployeeRecord) -> None:
        self.session.add_all([record.user, record.employee])
        await self.session.flush()

    async def get_employee_permissions(
        self,
        user_id: int,
    ) -> tuple[set[str], set[str], dict[str, bool], set[str]]:
        roles = await self.auth_repository.get_role_names(user_id)
        inherited = await self.auth_repository.get_role_permission_codes(user_id)
        overrides = await self.auth_repository.get_user_permission_overrides(user_id)
        effective = await self.auth_repository.get_effective_permissions(user_id)
        return roles, inherited, overrides, effective

    async def upsert_permission_override(
        self,
        *,
        user_id: int,
        permission_id: int,
        granted: bool,
        assigned_by: int,
    ) -> None:
        statement = (
            select(UsuarioPermiso)
            .where(
                UsuarioPermiso.id_usuario == user_id,
                UsuarioPermiso.id_permiso == permission_id,
            )
            .with_for_update()
        )
        override = (await self.session.execute(statement)).scalar_one_or_none()
        if override is None:
            override = UsuarioPermiso(
                id_usuario=user_id,
                id_permiso=permission_id,
                otorgado=granted,
                id_asignado_por=assigned_by,
            )
            self.session.add(override)
        else:
            override.otorgado = granted
            override.id_asignado_por = assigned_by
            override.fecha_asignacion = datetime.now(UTC)
        await self.session.flush()

    async def delete_permission_override(
        self,
        *,
        user_id: int,
        permission_id: int,
    ) -> None:
        statement = delete(UsuarioPermiso).where(
            UsuarioPermiso.id_usuario == user_id,
            UsuarioPermiso.id_permiso == permission_id,
        )
        await self.session.execute(statement)
        await self.session.flush()

    async def assign_employee_role(self, *, user_id: int, role: Rol) -> None:
        statement = (
            select(UsuarioRol, Rol)
            .join(Rol, Rol.id_rol == UsuarioRol.id_rol)
            .where(
                UsuarioRol.id_usuario == user_id,
                Rol.nombre.in_(MANAGED_EMPLOYEE_ROLES),
            )
            .order_by(UsuarioRol.id_usuario_rol)
            .with_for_update()
        )
        assignments = list((await self.session.execute(statement)).all())
        if any(assigned_role.id_rol == role.id_rol for _, assigned_role in assignments):
            return
        if len(assignments) > 1:
            raise InvalidEmployeeDataError("Employee has multiple managed role assignments")
        if assignments:
            assignment, _ = assignments[0]
            assignment.id_rol = role.id_rol
            self.session.add(assignment)
        else:
            self.session.add(UsuarioRol(id_usuario=user_id, id_rol=role.id_rol))
        await self.session.flush()
