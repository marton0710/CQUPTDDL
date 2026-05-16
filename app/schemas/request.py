from pydantic import BaseModel, Field


class Request(BaseModel):
    """请求模型"""

    username: str = Field(..., description="用户名")
    password: str = Field(..., description="密码")
