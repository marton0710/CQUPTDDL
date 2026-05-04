from pydantic import BaseModel, Field


class ChaoXingRequest(BaseModel):
    """超星模型"""

    username: str = Field(..., description="用户名 唯一")
    password: str = Field(..., description="密码")

