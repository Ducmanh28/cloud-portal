from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Import từ thư mục cha (app/)
from ..database import get_db
from .. import models, schemas, utils

router = APIRouter(prefix="/api/v1/iam", tags=["Identity & Access Management"])

# ==========================================
# 1. API: QUẢN LÝ QUYỀN (ROLES)
# ==========================================
@router.get("/roles", response_model=List[schemas.RoleResponse])
def get_all_roles(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Lấy danh sách tất cả các quyền trong hệ thống"""
    return db.query(models.Role).all()

# ==========================================
# 2. API: QUẢN LÝ TÀI KHOẢN (USERS)
# ==========================================
@router.get("/users/me", response_model=schemas.UserResponse)
def get_my_profile(current_user: models.User = Depends(utils.get_current_user)):
    """[ALL] Lấy thông tin cá nhân của người đang đăng nhập"""
    return current_user

@router.get("/users", response_model=List[schemas.UserResponse])
def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Lấy danh sách toàn bộ tài khoản (có phân trang)"""
    return db.query(models.User).offset(skip).limit(limit).all()

@router.post("/users", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: schemas.UserCreate, 
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Tạo tài khoản mới cho nhân viên hoặc khách hàng"""
    # 1. Kiểm tra username đã tồn tại chưa
    if db.query(models.User).filter(models.User.username == user_in.username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Tài khoản '{user_in.username}' đã tồn tại trong hệ thống."
        )
    
    # 2. Kiểm tra Role ID có hợp lệ không
    if user_in.role_id and not db.query(models.Role).filter(models.Role.id == user_in.role_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Quyền (Role ID) không hợp lệ."
        )
            
    # 3. Kiểm tra Customer ID có hợp lệ không
    if user_in.customer_id and not db.query(models.Customer).filter(models.Customer.id == user_in.customer_id).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Khách hàng (Customer ID) không hợp lệ."
        )

    # 4. Tạo User mới với password đã được băm qua utils
    new_user = models.User(
        username=user_in.username,
        password_hash=utils.get_password_hash(user_in.password),
        is_active=user_in.is_active,
        role_id=user_in.role_id,
        customer_id=user_in.customer_id
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@router.put("/users/{user_id}/status", response_model=schemas.UserResponse)
def toggle_user_status(
    user_id: int, 
    is_active: bool,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Khóa hoặc Mở khóa tài khoản"""
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Không tìm thấy tài khoản."
        )
        
    # Chống việc Admin tự khóa chính mình
    if user.id == admin_user.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Bạn không thể tự khóa tài khoản của chính mình."
        )

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user