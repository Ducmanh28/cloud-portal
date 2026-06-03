import logging
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

# Import các file hệ thống của chúng ta
from ..database import get_db
from .. import models, schemas
import app.utils as utils
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

class ForgotPasswordRequest(BaseModel):
    username: str

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(..., min_length=6)

# ==========================================
# DEPENDENCY: LẤY THÔNG TIN NGƯỜI DÙNG HIỆN TẠI
# ==========================================
def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
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


def build_user_payload(user: models.User) -> dict:
    """Trả về thông tin user tối thiểu cho frontend điều hướng đúng role."""
    return {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "role_id": user.role_id,
        "customer_id": user.customer_id,
        "role": {
            "id": user.role.id,
            "name": user.role.name,
        } if user.role else None,
        "customer": {
            "id": user.customer.id,
            "tenant_slug": user.customer.tenant_slug,
            "company_name": user.customer.company_name,
            "tax_code": user.customer.tax_code,
            "address": user.customer.address,
            "contact_person": user.customer.contact_person,
            "status": user.customer.status,
        } if user.customer else None,
    }

# ==========================================
# API ENDPOINTS
# ==========================================
@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    
    # Sử dụng utils.verify_password
    if not user or not utils.verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản hoặc mật khẩu không chính xác",
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Tài khoản đã bị khóa")

    role_name = user.role.name.upper() if user.role else "USER"

    # Sử dụng utils.create_access_token
    access_token = utils.create_access_token(
        data={"sub": str(user.id), "role": role_name}, 
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": build_user_payload(user),
    }

@router.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    user_exists = db.query(models.User).filter(models.User.username == user_in.username).first()
    if user_exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tài khoản này đã tồn tại.")

    default_role = db.query(models.Role).filter(models.Role.name == "USER").first()
    role_id = default_role.id if default_role else None

    new_user = models.User(
        username=user_in.username,
        password_hash=utils.get_password_hash(user_in.password), # Sử dụng utils
        is_active=True,
        role_id=role_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/forgot-password")
def forgot_password(request: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == request.username).first()
    if not user:
        return {"message": "Nếu tài khoản tồn tại, hướng dẫn đặt lại mật khẩu đã được xử lý."}
        
    reset_token = utils.create_reset_token(user.username) # Sử dụng utils
    logger.info(f"🔔 [MÔ PHỎNG EMAIL] Token reset cho '{user.username}': {reset_token}")
    
    return {
        "message": "Nếu tài khoản tồn tại, hướng dẫn đặt lại mật khẩu đã được xử lý.",
        "debug_reset_token": reset_token 
    }

@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(request.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        token_type: str = payload.get("type")
        
        if username is None or token_type != "reset":
            raise HTTPException(status_code=400, detail="Token không đúng mục đích.")
            
    except JWTError:
        raise HTTPException(status_code=400, detail="Token không hợp lệ hoặc đã hết hạn.")

    user = db.query(models.User).filter(models.User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy tài khoản.")

    user.password_hash = utils.get_password_hash(request.new_password) # Sử dụng utils
    db.commit()
    return {"message": "Cập nhật mật khẩu thành công."}
