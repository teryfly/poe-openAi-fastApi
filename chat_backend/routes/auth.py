from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict
from config_users import USERS

router = APIRouter()

class LoginRequest(BaseModel):
    userName: str
    password: str

class LoginResponse(BaseModel):
    name: str
    user: str

def _find_user_by_username(username: str) -> Optional[Dict[str, str]]:
    uname = (username or "").strip()
    for u in USERS:
        if (u.get("userName") or "").strip() == uname:
            return u
    return None

@router.post("/v1/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest = Body(...)):
    """
    简单登录验证：
    - 从内置 USERS 列表中查找 userName
    - 比对明文密码（演示用途，生产请使用安全存储与哈希）
    - 返回基础信息：name, user
    """
    user = _find_user_by_username(body.userName)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    pws = user.get("Pws") or ""
    if pws != (body.password or ""):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    return LoginResponse(name=user.get("name") or "", user=user.get("userName") or "")