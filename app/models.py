from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Numeric, Date, Text, Enum, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base

# Định nghĩa các trạng thái (Enum) cho Hợp đồng
class ContractStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    SUSPENDED = "SUSPENDED"

class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(20), unique=True, nullable=False)

    # Mối quan hệ 1-N: 1 Quyền có nhiều User
    users = relationship("User", back_populates="role")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_slug = Column(String(50), unique=True, nullable=False) # Khóa gài sang NetBox
    company_name = Column(String(255), nullable=False)
    tax_code = Column(String(20), unique=True, nullable=False)
    address = Column(Text)
    contact_person = Column(String(100))
    status = Column(Enum('ACTIVE', 'INACTIVE'), default='ACTIVE')

    # Mối quan hệ
    users = relationship("User", back_populates="customer")
    contracts = relationship("Contract", back_populates="customer")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Khóa ngoại (Foreign Keys)
    role_id = Column(Integer, ForeignKey("roles.id"))
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    # Mối quan hệ để truy vấn ngược
    role = relationship("Role", back_populates="users")
    customer = relationship("Customer", back_populates="users")


class PricingPlan(Base):
    __tablename__ = "pricing_plans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    cpu_core_price = Column(Numeric(10, 2))
    ram_gb_price = Column(Numeric(10, 2))
    disk_gb_price = Column(Numeric(10, 2))
    currency = Column(String(10), default='VND')

    contracts = relationship("Contract", back_populates="plan")


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vm_netbox_id = Column(Integer, nullable=False) # ID của máy ảo lưu trên NetBox
    total_price = Column(Numeric(15, 2))
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    status = Column(Enum(ContractStatus), default=ContractStatus.ACTIVE)

    # Khóa ngoại
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    plan_id = Column(Integer, ForeignKey("pricing_plans.id"))

    # Mối quan hệ
    customer = relationship("Customer", back_populates="contracts")
    plan = relationship("PricingPlan", back_populates="contracts")