from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.assistant.schemas import Conversation, Message


class AssistantRepository:
    def __init__(self, session: AsyncSession, tenant_id: int, user_id: int) -> None:
        self.session = session
        self.scope = {"tenant": tenant_id, "user": user_id}

    async def _user_context(self) -> None:
        # Commits clear transaction-local audit settings; restore the owner on every read/write.
        await self.session.execute(
            text("SELECT set_config('app.usuario_id', :user, true)"),
            {"user": str(self.scope["user"])},
        )

    async def create(
        self, conversation_id: UUID, mode: str, provider: str, model: str
    ) -> Conversation:
        await self._user_context()
        row = (
            (
                await self.session.execute(
                    text("""
            INSERT INTO capricho.asistente_conversacion
                (id_conversacion, id_tenant, id_usuario, modo, proveedor, modelo)
            VALUES (:id, :tenant, :user, :mode, :provider, :model)
            RETURNING id_conversacion, modo, proveedor, modelo, estado, created_at, updated_at
        """),
                    {
                        **self.scope,
                        "id": conversation_id,
                        "mode": mode,
                        "provider": provider,
                        "model": model,
                    },
                )
            )
            .mappings()
            .one()
        )
        await self.session.commit()
        return Conversation.model_validate(dict(row))

    async def list(self) -> list[Conversation]:
        await self._user_context()
        rows = (
            (
                await self.session.execute(
                    text("""
            SELECT id_conversacion, modo, proveedor, modelo, estado, created_at, updated_at
            FROM capricho.asistente_conversacion
            WHERE id_tenant = :tenant AND id_usuario = :user
            ORDER BY updated_at DESC LIMIT 100
        """),
                    self.scope,
                )
            )
            .mappings()
            .all()
        )
        return [Conversation.model_validate(dict(row)) for row in rows]

    async def get(self, conversation_id: UUID) -> Conversation | None:
        await self._user_context()
        row = (
            (
                await self.session.execute(
                    text("""
            SELECT id_conversacion, modo, proveedor, modelo, estado, created_at, updated_at
            FROM capricho.asistente_conversacion
            WHERE id_conversacion = :id AND id_tenant = :tenant AND id_usuario = :user
        """),
                    {**self.scope, "id": conversation_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        return Conversation.model_validate(dict(row)) if row else None

    async def messages(self, conversation_id: UUID, limit: int = 100) -> list[Message]:
        await self._user_context()
        rows = (
            (
                await self.session.execute(
                    text("""
            SELECT id_mensaje, rol, contenido, created_at, producto_ids, requiere_reportes_ia FROM (
                SELECT id_mensaje, rol, contenido, created_at, producto_ids, requiere_reportes_ia
                FROM capricho.asistente_mensaje
                WHERE id_conversacion = :id AND id_tenant = :tenant AND id_usuario = :user
                ORDER BY id_mensaje DESC LIMIT :limit
            ) recent ORDER BY id_mensaje
        """),
                    {**self.scope, "id": conversation_id, "limit": limit},
                )
            )
            .mappings()
            .all()
        )
        return [Message.model_validate(dict(row)) for row in rows]

    async def append_exchange(
        self,
        conversation_id: UUID,
        question: str,
        answer: str,
        model: str,
        product_ids: list[int] | None = None,
        *,
        report_restricted: bool = False,
    ) -> tuple[Message, Message]:
        await self._user_context()
        messages = []
        for role, content, ids, restricted in (
            ("USUARIO", question, [], False),
            ("ASISTENTE", answer, product_ids or [], report_restricted),
        ):
            row = (
                (
                    await self.session.execute(
                        text("""
                INSERT INTO capricho.asistente_mensaje
                    (id_conversacion, id_tenant, id_usuario, rol, contenido,
                     producto_ids, requiere_reportes_ia)
                VALUES (:id, :tenant, :user, :role, :content, :product_ids, :restricted)
                RETURNING id_mensaje, rol, contenido, created_at, producto_ids, requiere_reportes_ia
            """),
                        {
                            **self.scope,
                            "id": conversation_id,
                            "role": role,
                            "content": content,
                            "product_ids": ids,
                            "restricted": restricted,
                        },
                    )
                )
                .mappings()
                .one()
            )
            messages.append(Message.model_validate(dict(row)))
        await self.session.execute(
            text("""
            UPDATE capricho.asistente_conversacion SET updated_at = now(), modelo = :model
            WHERE id_conversacion = :id AND id_tenant = :tenant AND id_usuario = :user
        """),
            {**self.scope, "id": conversation_id, "model": model},
        )
        await self.session.commit()
        return messages[0], messages[1]

    async def archive(self, conversation_id: UUID) -> None:
        await self._user_context()
        await self.session.execute(
            text("""
            UPDATE capricho.asistente_conversacion
            SET estado = 'ARCHIVADA', updated_at = now()
            WHERE id_conversacion = :id AND id_tenant = :tenant AND id_usuario = :user
        """),
            {**self.scope, "id": conversation_id},
        )
        await self.session.commit()
