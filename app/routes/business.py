from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

# Import các module nội bộ từ thư mục cha
from .. import models, schemas, utils
from ..database import get_db

# Khởi tạo Router
router = APIRouter(prefix="/api/v1/business", tags=["Business Management"])

# ==========================================
# 1. API: QUẢN LÝ BẢNG GIÁ (PRICING PLANS)
# ==========================================
@router.get("/plans", response_model=List[schemas.PricingPlanResponse])
def get_pricing_plans(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(utils.get_current_user)
):
    """[ALL] Lấy danh sách các gói cước đang cung cấp. Ai đăng nhập cũng xem được."""
    return db.query(models.PricingPlan).all()

# ==========================================
# 2. API: QUẢN LÝ KHÁCH HÀNG (CUSTOMERS)
# ==========================================
@router.get("/customers", response_model=List[schemas.CustomerResponse])
def get_customers(
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(utils.get_current_user)
):
    """[ADMIN] Xem toàn bộ khách hàng. [USER] Chỉ xem thông tin của công ty mình."""
    user_role = current_user.role.name.upper() if current_user.role else "USER"
    
    if user_role == "ADMIN":
        return db.query(models.Customer).all()
    
    if not current_user.customer_id:
        return []
    
    customer = db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).first()
    return [customer] if customer else []

@router.post("/customers", response_model=schemas.CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_in: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Tạo hồ sơ Khách hàng/Tenant mới"""
    existing_customer = db.query(models.Customer).filter(
        (models.Customer.tenant_slug == customer_in.tenant_slug) | 
        (models.Customer.tax_code == customer_in.tax_code)
    ).first()
    
    if existing_customer:
        raise HTTPException(status_code=400, detail="Mã Tenant Slug hoặc Mã số thuế đã tồn tại.")

    new_customer = models.Customer(**customer_in.model_dump())
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer

# ==========================================
# 3. API: QUẢN LÝ HỢP ĐỒNG (CONTRACTS)
# ==========================================
@router.get("/contracts", response_model=List[schemas.ContractResponse])
def get_all_contracts(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """
    [ADMIN] Lấy danh sách TOÀN BỘ hợp đồng hệ thống.
    Đồng bộ trực tiếp với trang quản lý contract.html của Admin phục vụ bộ lọc và tìm kiếm.
    """
    return db.query(models.Contract).all()

@router.get("/customers/{customer_id}/contracts", response_model=List[schemas.ContractResponse])
def get_customer_contracts(
    customer_id: int, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user)
):
    """[ADMIN] Xem hợp đồng bất kỳ. [USER] Chỉ xem hợp đồng của công ty mình."""
    # Khắc phục lỗi AttributeError nếu người dùng không có quyền (role = None)
    user_role = current_user.role.name.upper() if current_user.role else "USER"
    
    if user_role != "ADMIN" and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Bạn không được phép xem hợp đồng của khách hàng khác.")

    return db.query(models.Contract).filter(models.Contract.customer_id == customer_id).all()

@router.post("/contracts", response_model=schemas.ContractResponse, status_code=status.HTTP_201_CREATED)
def create_contract(
    contract_in: schemas.ContractCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Tạo hợp đồng cung cấp máy ảo mới cho Khách hàng"""
    if not db.query(models.Customer).filter(models.Customer.id == contract_in.customer_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy Khách hàng.")

    if not db.query(models.PricingPlan).filter(models.PricingPlan.id == contract_in.plan_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy Gói cước.")

    if contract_in.end_date <= contract_in.start_date:
        raise HTTPException(status_code=400, detail="Ngày kết thúc phải sau Ngày bắt đầu.")

    new_contract = models.Contract(**contract_in.model_dump())
    db.add(new_contract)
    db.commit()
    db.refresh(new_contract)
    return new_contract

@router.put("/contracts/{contract_id}/status", response_model=schemas.ContractResponse)
def update_contract_status(
    contract_id: int,
    new_status: schemas.ContractStatus,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin)
):
    """[ADMIN] Cập nhật trạng thái hợp đồng"""
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hợp đồng.")

    contract.status = new_status
    db.commit()
    db.refresh(contract)
    return contract