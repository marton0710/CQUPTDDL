from pydantic_settings import SettingsConfigDict, BaseSettings


class Settings(BaseSettings):
    """从.env读取配置文件"""
    # 异步数据库
    database_url: str = "mysql+aiomysql://cqupt:123456@127.0.0.1:3306/cquptddl?charset=utf8mb4"

    # 数据库调试日志
    db_echo: bool = False

    # 时区
    timezone: str = "Asia/Shanghai"

    # 读取.env，忽略额外字段
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # redis相关
    redis_host: str = "127.0.0.1"
    redis_port: str = "6379"
    redis_db: int = 0
    redis_password: str | None = None

    # 缓存基础时间
    homework_cache_base_ttl: int = 12 * 60 * 60

    # 缓存偏移时间
    homework_cache_jitter: int = 30 * 60

    # 请求冷却时间
    homework_cooldown_ttl: int = 30 * 60 * 60


settings = Settings()
