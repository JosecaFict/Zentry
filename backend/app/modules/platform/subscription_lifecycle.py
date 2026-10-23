import asyncio
import logging
from contextlib import suppress
from datetime import date, timedelta

from sqlalchemy import select

from app.db.session import async_session_factory
from app.modules.platform.models import Subscription

logger = logging.getLogger("zentry.subscriptions")

MANAGED_STATES = ("ACTIVA", "POR_VENCER", "GRACIA", "SUSPENDIDA")
EXPIRING_WINDOW_DAYS = 7


def subscription_status(subscription: Subscription, today: date) -> str:
    """Return the access state derived from the paid period and grace deadline."""
    if subscription.fecha_fin is None:
        return "SUSPENDIDA"
    grace_end = subscription.fecha_fin_gracia or subscription.fecha_fin + timedelta(days=7)
    if today > grace_end:
        return "SUSPENDIDA"
    if today > subscription.fecha_fin:
        return "GRACIA"
    if today >= subscription.fecha_fin - timedelta(days=EXPIRING_WINDOW_DAYS - 1):
        return "POR_VENCER"
    return "ACTIVA"


async def refresh_subscription_states(today: date | None = None) -> int:
    """Synchronize all current subscriptions and return how many changed."""
    effective_date = today or date.today()
    changed = 0
    async with async_session_factory() as session:
        subscriptions = list(
            (
                await session.scalars(
                    select(Subscription)
                    .where(Subscription.estado.in_(MANAGED_STATES))
                    .execution_options(include_all_tenants=True)
                )
            ).all()
        )
        for subscription in subscriptions:
            next_status = subscription_status(subscription, effective_date)
            if subscription.estado != next_status:
                subscription.estado = next_status
                changed += 1
        if changed:
            await session.commit()
    if changed:
        logger.info("Se actualizaron %d estados de suscripción.", changed)
    return changed


async def subscription_lifecycle_worker(interval_seconds: int = 3600) -> None:
    """Refresh subscription states periodically while this API instance is running."""
    while True:
        try:
            await refresh_subscription_states()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("No se pudieron actualizar los estados de suscripción.")
        await asyncio.sleep(interval_seconds)


async def stop_subscription_worker(task: asyncio.Task[None]) -> None:
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
