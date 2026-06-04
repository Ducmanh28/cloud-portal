from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from .. import models, schemas, utils
from ..database import get_db

router = APIRouter(prefix="/api/v1/business", tags=["Business Management"])


def _num(value):
    if isinstance(value, Decimal):
        return float(value)
    return value


def _contract_to_dict(contract: models.Contract) -> dict:
    total_price = _num(contract.total_price or 0)
    return {
        "id": contract.id,
        "vm_netbox_id": contract.vm_netbox_id,
        "total_price": total_price,
        "total_value": total_price,
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "status": contract.status.value if hasattr(contract.status, "value") else str(contract.status or "ACTIVE"),
        "customer_id": contract.customer_id,
        "plan_id": contract.plan_id,
        "customer": {
            "id": contract.customer.id,
            "tenant_slug": contract.customer.tenant_slug,
            "company_name": contract.customer.company_name,
            "tax_code": contract.customer.tax_code,
            "address": contract.customer.address,
            "contact_person": contract.customer.contact_person,
            "status": contract.customer.status,
        } if contract.customer else None,
        "plan": {
            "id": contract.plan.id,
            "name": contract.plan.name,
            "cpu_core_price": _num(contract.plan.cpu_core_price),
            "ram_gb_price": _num(contract.plan.ram_gb_price),
            "disk_gb_price": _num(contract.plan.disk_gb_price),
            "currency": contract.plan.currency,
        } if contract.plan else None,
    }


@router.get("/plans", response_model=List[schemas.PricingPlanResponse])
def get_pricing_plans(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    return db.query(models.PricingPlan).all()


@router.get("/customers", response_model=List[schemas.CustomerResponse])
def get_customers(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    role = current_user.role.name.upper() if current_user.role else "USER"
    if role == "ADMIN":
        return db.query(models.Customer).all()
    if not current_user.customer_id:
        return []
    customer = db.query(models.Customer).filter(models.Customer.id == current_user.customer_id).first()
    return [customer] if customer else []


@router.post("/customers", response_model=schemas.CustomerResponse, status_code=status.HTTP_201_CREATED)
def create_customer(
    customer_in: schemas.CustomerCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    existing_customer = db.query(models.Customer).filter(
        (models.Customer.tenant_slug == customer_in.tenant_slug) |
        (models.Customer.tax_code == customer_in.tax_code)
    ).first()
    if existing_customer:
        raise HTTPException(status_code=400, detail="Mã Tenant Slug hoặc Mã số thuế đã tồn tại.")

    customer = models.Customer(**customer_in.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/contracts")
def get_all_contracts(
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    contracts = (
        db.query(models.Contract)
        .options(joinedload(models.Contract.customer), joinedload(models.Contract.plan))
        .all()
    )
    return [_contract_to_dict(contract) for contract in contracts]


@router.get("/customers/{customer_id}/contracts")
def get_customer_contracts(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    role = current_user.role.name.upper() if current_user.role else "USER"
    if role != "ADMIN" and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Bạn không được phép xem hợp đồng của khách hàng khác.")

    contracts = (
        db.query(models.Contract)
        .options(joinedload(models.Contract.customer), joinedload(models.Contract.plan))
        .filter(models.Contract.customer_id == customer_id)
        .all()
    )
    return [_contract_to_dict(contract) for contract in contracts]


@router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_contract(
    contract_in: schemas.ContractCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    if not db.query(models.Customer).filter(models.Customer.id == contract_in.customer_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy Khách hàng.")

    if contract_in.plan_id is not None:
        if not db.query(models.PricingPlan).filter(models.PricingPlan.id == contract_in.plan_id).first():
            raise HTTPException(status_code=404, detail="Không tìm thấy Gói cước.")

    if contract_in.end_date <= contract_in.start_date:
        raise HTTPException(status_code=400, detail="Ngày kết thúc phải sau Ngày bắt đầu.")

    contract = models.Contract(**contract_in.model_dump())
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return _contract_to_dict(contract)


@router.put("/contracts/{contract_id}/status")
def update_contract_status(
    contract_id: int,
    new_status: schemas.ContractStatus,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    contract = db.query(models.Contract).filter(models.Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hợp đồng.")

    contract.status = new_status
    db.commit()
    db.refresh(contract)
    return _contract_to_dict(contract)
