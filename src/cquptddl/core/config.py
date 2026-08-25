from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从.env读取配置文件"""

    DEBUG: bool = False
    # 异步数据库
    DATABASE_URL: str

    # 数据库调试日志
    db_echo: bool = False
    db_pool_pre_ping: bool = True
    db_pool_recycle: int = 3600

    # 缓存基础时间
    homework_cache_base_ttl: int = 12 * 60 * 60

    # 缓存偏移时间（仅向后偏移）
    homework_cache_jitter: int = 30 * 60

    # 请求冷却时间
    homework_cooldown_ttl: int = 30 * 60

    # JWT相关
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_SECONDS: int = 900
    REFRESH_TOKEN_EXPIRE_SECONDS: int = 86400 * 7

    # qqbot相关。api_key名称的recv和send与qqbot端意义相同，不需要对称
    QQBOT_URL: str
    QQBOT_RECV_API_KEY: str  # 从后端发往qq机器人的报文所需的api_key
    QQBOT_SEND_API_KEY: str  # 从qq机器人发往后端

    FRONTEND_DIR: str | None = None

    # 读取.env，忽略额外字段
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


config = Settings()
