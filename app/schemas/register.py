from pydantic import BaseModel


class Register(BaseModel):
    """注册模型"""
    username: str
