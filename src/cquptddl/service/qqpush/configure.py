from sqlalchemy.ext.asyncio import AsyncSession

from cquptddl import core
from cquptddl.model.db.qqpush_config import QQPushConfig
from cquptddl.model.schema.qqpush import QQPushConfigSchema

from .push import push_bind_success_msg


async def configure_qqpush(
    session: AsyncSession, user_id: str, model: QQPushConfigSchema
):
    if model.qqchan_id is not None:
        await push_bind_success_msg(model.qqchan_id)
    await session.merge(QQPushConfig(user_id=user_id, **model.model_dump()))
    await session.commit()
    await core.hook.trigger("qqpush.after_config_change", user_id=user_id)


async def get_configure(session: AsyncSession, user_id: str) -> QQPushConfigSchema:
    config = await session.get_one(QQPushConfig, user_id)
    return QQPushConfigSchema(
        qqchan_id=config.qqchan_id,
        qq_push_strategy=config.qq_push_strategy,
        qq_push_at=config.qq_push_at,
        qq_push_scope=config.qq_push_scope,
    )


@core.hook.on("auth.after_register", background=True)
async def _generate_qqpush_config_after_register(uid: str):
    async with core.factory.get_session() as session:
        session.add(QQPushConfig(user_id=uid))
