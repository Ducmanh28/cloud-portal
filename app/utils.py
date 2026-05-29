from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

# Import tương đối (có dấu chấm) từ các file cùng cấp trong thư mục app
from .config import settings
from .database import get_db
from . import models

# Khởi tạo công cụ mã hóa mật khẩu (Bcrypt)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Khai báo đường dẫn cấp Token (Bắt buộc phải có cho Swagger UI và Dependency)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# ==========================================
# 1. TIỆN ÍCH XỬ LÝ MẬT KHẨU & TOKEN
# ==========================================
def get_password_hash(password: str) -> str:
    """
    Băm mật khẩu sử dụng trực tiếp thư viện gốc bcrypt (Sửa lỗi tương thích Python 3.12)
    """
    # Chuyển chuỗi mật khẩu từ dạng string sang bytes
    password_bytes = password.encode('utf-8')
    
    # Sinh salt và thực hiện băm
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # Chuyển ngược từ bytes về chuỗi string để lưu vào MySQL
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Xác thực mật khẩu khi người dùng đăng nhập
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    except Exception:
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Tạo JWT Token để xác thực các phiên đăng nhập (Access Token)"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_reset_token(username: str) -> str:
    """Tạo JWT Token dùng một lần để cấp lại mật khẩu (Reset Token)"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": username, "exp": expire, "type": "reset"}
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# ==========================================
# 2. TIỆN ÍCH AUTH & PHÂN QUYỀN (DEPENDENCIES)
# ==========================================
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """Giải mã Token và trả về thông tin User đang đăng nhập"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Không thể xác thực thông tin Token hoặc đã hết hạn",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if user_id is None or token_type != "access":
            raise credentials_exception
    except JWTError:
        raise credentials_exception
        
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if user is None:
        raise credentials_exception
    return user

def require_admin(current_user: models.User = Depends(get_current_user)):
    """Bắt buộc User phải có Role là ADMIN"""
    if not current_user.role or current_user.role.name != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cảnh báo: Bạn không có quyền Quản trị viên để thực hiện thao tác này."
        )
    return current_user