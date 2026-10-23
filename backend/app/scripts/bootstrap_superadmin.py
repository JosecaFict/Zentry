"""Create the first global Zentry Superadmin account.

Interactive usage from the backend directory:
    python -m app.scripts.bootstrap_superadmin
"""

import argparse
import asyncio
from dataclasses import dataclass
from getpass import getpass
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, validate_password_strength
from app.db.audit_context import AuditContext, apply_audit_context
from app.db.session import async_session_factory, engine
from app.modules.auth.service import normalize_email


class BootstrapError(RuntimeError):
    """Expected validation or provisioning failure."""


@dataclass(frozen=True, slots=True)
class SuperadminData:
    nombres: str
    apellidos: str
    correo: str
    ci: str | None
    telefono: str | None
    password: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crea la primera cuenta global con rol SUPERADMIN.",
    )
    parser.add_argument("--nombres")
    parser.add_argument("--apellidos")
    parser.add_argument("--correo")
    parser.add_argument("--ci")
    parser.add_argument("--telefono")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Comprueba la configuración sin crear una cuenta.",
    )
    return parser


async def _prompt(label: str, *, secret: bool = False) -> str:
    reader = getpass if secret else input
    return await asyncio.to_thread(reader, label)


async def _required(value: str | None, label: str) -> str:
    result = value.strip() if value is not None else (await _prompt(f"{label}: ")).strip()
    if not result:
        raise BootstrapError(f"{label} es obligatorio.")
    return result


def _validate_email(value: str) -> str:
    try:
        validated = TypeAdapter(EmailStr).validate_python(value)
    except ValidationError as exc:
        raise BootstrapError("El correo no tiene un formato válido.") from exc
    return normalize_email(str(validated))


async def _read_password() -> str:
    password = await _prompt("Contraseña (no se mostrará): ", secret=True)
    try:
        validate_password_strength(password)
    except ValueError as exc:
        raise BootstrapError(str(exc)) from exc
    confirmation = await _prompt("Repite la contraseña: ", secret=True)
    if password != confirmation:
        raise BootstrapError("Las contraseñas no coinciden.")
    return password


async def configuration_status(session: AsyncSession) -> tuple[int, int]:
    role_id = await session.scalar(
        text(
            """
            SELECT id_rol
            FROM capricho.rol
            WHERE nombre = 'SUPERADMIN' AND alcance = 'GLOBAL' AND activo = true
            """
        )
    )
    if role_id is None:
        raise BootstrapError(
            "El rol global SUPERADMIN no existe. Ejecuta primero alembic upgrade head."
        )
    permissions = int(
        await session.scalar(
            text(
                """
                SELECT count(*)
                FROM capricho.rol_permiso rp
                JOIN capricho.permiso p ON p.id_permiso = rp.id_permiso
                WHERE rp.id_rol = :role_id
                  AND p.codigo LIKE 'platform.%'
                  AND p.activo = true
                """
            ),
            {"role_id": role_id},
        )
        or 0
    )
    if permissions < 6:
        raise BootstrapError("El rol SUPERADMIN no tiene todos los permisos de plataforma.")
    return int(role_id), permissions


async def create_superadmin(session: AsyncSession, data: SuperadminData) -> int:
    role_id, _ = await configuration_status(session)
    existing_superadmin = await session.scalar(
        text(
            """
            SELECT u.id_usuario
            FROM capricho.usuario u
            JOIN capricho.usuario_rol ur ON ur.id_usuario = u.id_usuario
            WHERE ur.id_rol = :role_id
            LIMIT 1
            """
        ),
        {"role_id": role_id},
    )
    if existing_superadmin is not None:
        raise BootstrapError("Ya existe una cuenta con rol SUPERADMIN.")

    conflict = await session.execute(
        text(
            """
            SELECT correo, ci
            FROM capricho.usuario
            WHERE lower(correo) = :correo
               OR ci = :ci
            LIMIT 1
            """
        ),
        {"correo": data.correo, "ci": data.ci},
    )
    existing = conflict.one_or_none()
    if existing is not None:
        if existing.correo.lower() == data.correo:
            raise BootstrapError("El correo ya está registrado.")
        raise BootstrapError("El CI ya está registrado.")

    user_id = await session.scalar(
        text(
            """
            INSERT INTO capricho.usuario (
                id_tenant, nombres, apellidos, correo, ci, telefono,
                password_hash, estado
            )
            VALUES (
                NULL, :nombres, :apellidos, :correo, :ci, :telefono,
                :password_hash, 'ACTIVO'
            )
            RETURNING id_usuario
            """
        ),
        {
            "nombres": data.nombres,
            "apellidos": data.apellidos,
            "correo": data.correo,
            "ci": data.ci,
            "telefono": data.telefono,
            "password_hash": hash_password(data.password),
        },
    )
    if user_id is None:
        raise BootstrapError("PostgreSQL no devolvió el usuario creado.")
    await session.execute(
        text(
            """
            INSERT INTO capricho.usuario_rol(id_usuario, id_rol)
            VALUES (:user_id, :role_id)
            """
        ),
        {"user_id": user_id, "role_id": role_id},
    )
    return int(user_id)


async def run(args: argparse.Namespace) -> None:
    async with async_session_factory() as session:
        role_id, permissions = await configuration_status(session)
        if args.check:
            print("Configuración de Superadmin disponible.")
            print(f"  Rol: {role_id}")
            print(f"  Permisos de plataforma: {permissions}")
            return

        ci = (
            args.ci.strip()
            if args.ci is not None
            else (await _prompt("CI (opcional): ")).strip()
        ) or None
        data = SuperadminData(
            nombres=await _required(args.nombres, "Nombres"),
            apellidos=await _required(args.apellidos, "Apellidos"),
            correo=_validate_email(await _required(args.correo, "Correo")),
            ci=ci,
            telefono=(
                args.telefono.strip()
                if args.telefono is not None
                else (await _prompt("Teléfono (opcional): ")).strip()
            )
            or None,
            password=await _read_password(),
        )
        print("\nSe creará una cuenta global, sin acceso comercial a ningún tenant.")
        confirmation = (await _prompt("Escribe CREAR para confirmar: ")).strip()
        if confirmation != "CREAR":
            raise BootstrapError("Operación cancelada; no se guardó ningún cambio.")

        try:
            request_id = f"superadmin-bootstrap-{uuid4()}"
            await apply_audit_context(
                session,
                AuditContext(
                    origen="SISTEMA",
                    user_agent="bootstrap_superadmin",
                    request_id=request_id,
                ),
            )
            user_id = await create_superadmin(session, data)
            await session.execute(
                text(
                    """
                    UPDATE capricho.bitacora
                    SET id_tenant = NULL
                    WHERE request_id = :request_id
                    """
                ),
                {"request_id": request_id},
            )
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        print("\nSuperadmin creado correctamente.")
        print(f"  Usuario: {user_id}")
        print(f"  Correo: {data.correo}")
        print("  Tenant: GLOBAL")
        print("  Rol: SUPERADMIN")


async def async_main(args: argparse.Namespace) -> int:
    try:
        await run(args)
    except BootstrapError as exc:
        print(f"\nNo se creó la cuenta: {exc}")
        return 1
    except IntegrityError:
        print("\nNo se creó la cuenta: el correo, CI o rol ya está registrado.")
        return 1
    except SQLAlchemyError as exc:
        print(f"\nNo se creó la cuenta: PostgreSQL no está disponible ({type(exc).__name__}).")
        return 1
    finally:
        await engine.dispose()
    return 0


def main() -> None:
    args = build_parser().parse_args()
    try:
        raise SystemExit(asyncio.run(async_main(args)))
    except KeyboardInterrupt:
        print("\nOperación cancelada; no se guardó ningún cambio.")
        raise SystemExit(130) from None


if __name__ == "__main__":
    main()
