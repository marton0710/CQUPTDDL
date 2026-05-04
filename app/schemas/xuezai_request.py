from pydantic import BaseModel, Field


class XueZaiRequest(BaseModel):
    """学在重邮模型"""

    username: str = Field(..., description="用户名 唯一")
    password: str = Field(..., description="密码")
