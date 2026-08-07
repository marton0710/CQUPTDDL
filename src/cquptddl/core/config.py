from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从.env读取配置文件"""

    DEBUG: bool = False
    # 异步数据库
    DATABASE_URL: str

    # 数据库调试日志
    db_echo: bool = False

    # 缓存基础时间
    homework_cache_base_ttl: int = 12 * 60 * 60

    # 缓存偏移时间
    homework_cache_jitter: int = 30 * 60

    # 请求冷却时间
    homework_cooldown_ttl: int = 30 * 60

    # JWT相关
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 86400 * 7

    # 读取.env，忽略额外字段
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


config = Settings()
