from pydantic_settings import SettingsConfigDict, BaseSettings


class Settings(BaseSettings):
    """从.env读取配置文件"""
    # 异步数据库
    database_url: str = "sqlite+aiosqlite:///./data/cookies.db"

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


settings = Settings()
