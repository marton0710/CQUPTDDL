from pydantic import BaseModel, Field


class Login(BaseModel):
    """登录模型"""

    username: str = Field(..., description="用户名 唯一")
    password: str = Field(..., description="密码")
    email: str = Field(..., description="邮箱")
