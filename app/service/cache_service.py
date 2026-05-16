import random
import json

from app.core import redis_client, settings
from app.schemas import Homework


class CacheService:
    """缓存service"""

    def __init__(self):
        self.redis = redis_client
        self.base_ttl = settings.homework_cache_base_ttl
        self.jitter = settings.homework_cache_jitter
        self.cooldown_ttl = settings.homework_cooldown_ttl

    def make_homework_ttl(self) -> int:
        """
        获取缓存时间
        :return: 有偏移的缓存时间
        """
        return (
            self.base_ttl
            + random.randint(
                a=-self.jitter,
                b=self.jitter,
            )
        )

    @staticmethod
    def make_homework_key(username: str, platform: str) -> str:
        """
        生成作业缓存键
        :param username: 用户名
        :param platform: 平台
        :return:
        """
        return f"homeword:{username}:{platform}"

    @staticmethod
    def make_cooldown_key(username: str, platform: str) -> str:
        """
        生成冷却缓存键
        :param username: 用户名
        :param platform: 平台
        :return:
        """
        return f"homeword:{username}:{platform}:cooldown"

    @staticmethod
    def _dump_homework_list(homework_list: list[Homework]) -> list[dict]:
        """
        将Homework转化为字典
        :param homework_list: pydantic作业列表
        :return: 作业字典列表
        """
        return [item.model_dump(mode="json") for item in homework_list]

    @staticmethod
    def _load_homework_list(payload: list[dict]) -> list[Homework]:
        """
        将字典转化为Homework
        :param payload: list[dict]作业列表
        :return: pydantic作业列表
        """
        return [Homework.model_validate(item) for item in payload]

    async def in_cooldown(self, username: str, platform: str) -> bool:
        """
        看是否还在冷却
        :param username: 用户名
        :param platform: 平台
        :return:
        """
        key = self.make_cooldown_key(username=username, platform=platform)
        return await self.redis.exists(key) == 1

    async def get_cached_homework(self, username: str, platform: str):
        """
        获取缓存的作业
        :param username: 用户名
        :param platform: 平台
        :return:
        """
        key = self.make_homework_key(username=username, platform=platform)
        try:
            raw = await self.redis.get(key)
            if raw is None:
                return None

            payload = json.loads(raw)
            return self._load_homework_list(payload=payload)
        except Exception:
            try:
                await self.redis.delete(key)
            except Exception:
                pass
            return None

    async def set_homework_cache(
            self,
            username: str,
            platform: str,
            homework: list[Homework],
    ) -> None:
        """
        保存作业缓存
        :param username: 用户名
        :param platform: 平台
        :param homework: 作业
        :return:
        """
        homework_key = self.make_homework_key(username=username, platform=platform)
        cooldown_key = self.make_cooldown_key(username=username, platform=platform)

        payload = self._dump_homework_list(homework_list=homework)
        await self.redis.set(
            homework_key,
            json.dumps(payload, ensure_ascii=False),
            ex=self.make_homework_ttl(),
        )
        await self.redis.set(
            cooldown_key,
            "1",
            ex=settings.homework_cooldown_ttl,
        )

    async def delete_homework_cache(self, username: str, platform: str) -> None:
        """
        删除缓存
        :param username: 用户名
        :param platform: 平台
        :return:
        """
        homework_key = self.make_homework_key(username=username, platform=platform)
        cooldown_key = self.make_cooldown_key(username=username, platform=platform)

        await self.redis.delete(homework_key)
        await self.redis.delete(cooldown_key)
