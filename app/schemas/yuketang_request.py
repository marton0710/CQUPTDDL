from pydantic import BaseModel, Field


class YuKeTangRequest(BaseModel):
    """雨课堂模型"""

    username: str = Field(..., description="用户名 唯一")
    cookies: dict[str, str] = Field(..., description="cookies")
