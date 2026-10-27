from app.common.exceptions import BusinessException
from app.database import SessionLocal
from app.models.user import User
from app.utils.jwt import decode_access_token


def user_id_form_authorization(authorization: str):
    if not authorization:
        raise BusinessException("未提供Authorization头部信息", code=401)
    token = authorization
    if authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise BusinessException("未提供有效的Token", code=401)
    try:
        payload = decode_access_token(token)
    except Exception as e:
        raise BusinessException("登录已失效", code=401)
    user_id = payload.get("user_id")
    if not user_id:
        raise BusinessException("无效的登录凭证", code=401)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id, User.status == 1).first()
        if not user:
            raise BusinessException("用户不存在或已被禁用", code=401)
        return user_id
    finally:
        db.close()
