from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import date
from decimal import Decimal
import enum

# --- ENUMS ---
class ContractStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"

class CustomerStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"

# ==========================================
# 1. SCHEMAS CHO ROLE
# ==========================================
class RoleBase(BaseModel):
    name: str

class RoleResponse(RoleBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True) # Pydantic V2: Cho phép đọc dữ liệu trực tiếp từ SQLAlchemy ORM

# ==========================================
# 2. SCHEMAS CHO CUSTOMER (KHÁCH HÀNG)
# ==========================================
class CustomerBase(BaseModel):
    tenant_slug: str = Field(..., description="Slug liên kết với NetBox Tenant")
    company_name: str
    tax_code: str
    address: Optional[str] = None
    contact_person: Optional[str] = None
    status: CustomerStatus = CustomerStatus.ACTIVE

class CustomerCreate(CustomerBase):
    pass # Khi tạo mới thì gửi lên các trường giống hệt Base

class CustomerResponse(CustomerBase):
    id: int
    
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 3. SCHEMAS CHO USER (TÀI KHOẢN)
# ==========================================
class UserBase(BaseModel):
    username: str
    is_active: bool = True
    role_id: Optional[int] = None
    customer_id: Optional[int] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=6, description="Mật khẩu thô gửi từ Frontend")

class UserResponse(UserBase):
    id: int
    # KHÔNG BAO GIỜ include cột password_hash ở đây để tránh rò rỉ bảo mật
    
    # Có thể lồng các object liên quan để trả về JSON đẹp hơn
    role: Optional[RoleResponse] = None
    customer: Optional[CustomerResponse] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 4. SCHEMAS CHO PRICING PLAN (GÓI CƯỚC)
# ==========================================
class PricingPlanBase(BaseModel):
    name: str
    cpu_core_price: Decimal
    ram_gb_price: Decimal
    disk_gb_price: Decimal
    currency: str = "VND"

class PricingPlanResponse(PricingPlanBase):
    id: int
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# 5. SCHEMAS CHO CONTRACT (HỢP ĐỒNG)
# ==========================================
class ContractBase(BaseModel):
    vm_netbox_id: int
    total_price: Decimal
    start_date: date
    end_date: date
    status: ContractStatus = ContractStatus.ACTIVE
    customer_id: int
    plan_id: Optional[int] = None

class ContractCreate(ContractBase):
    pass

class ContractResponse(ContractBase):
    id: int
    
    # Lồng thông tin Khách hàng và Gói cước vào JSON trả về
    customer: Optional[CustomerResponse] = None
    plan: Optional[PricingPlanResponse] = None

    model_config = ConfigDict(from_attributes=True)