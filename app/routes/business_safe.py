from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import List

from .. import models, schemas, utils
from ..database import get_db

router = APIRouter(prefix="/api/v1/business", tags=["Business Management"])


def _json_value(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _contract_row_to_dict(row) -> dict:
    total_price = _json_value(row.get("total_price") or 0)
    return {
        "id": row.get("id"),
        "vm_netbox_id": row.get("vm_netbox_id"),
        "total_price": total_price,
        "total_value": total_price,
        "start_date": _json_value(row.get("start_date")),
        "end_date": _json_value(row.get("end_date")),
        "status": row.get("status") or "ACTIVE",
        "customer_id": row.get("customer_id"),
        "plan_id": row.get("plan_id"),
        "customer": {
            "id": row.get("customer_id"),
            "tenant_slug": row.get("tenant_slug"),
            "company_name": row.get("company_name"),
            "tax_code": row.get("tax_code"),
            "address": row.get("address"),
            "contact_person": row.get("contact_person"),
            "status": row.get("customer_status"),
        } if row.get("customer_id") else None,
        "plan": {
            "id": row.get("plan_id"),
            "name": row.get("plan_name"),
            "cpu_core_price": _json_value(row.get("cpu_core_price")),
            "ram_gb_price": _json_value(row.get("ram_gb_price")),
            "disk_gb_price": _json_value(row.get("disk_gb_price")),
            "currency": row.get("currency"),
        } if row.get("plan_id") else None,
    }


def _contract_query(where_sql: str = "", params: dict | None = None):
    sql = """
        SELECT
            c.id,
            c.vm_netbox_id,
            c.total_price,
            c.start_date,
            c.end_date,
            c.status,
            c.customer_id,
            c.plan_id,
            cu.tenant_slug,
            cu.company_name,
            cu.tax_code,
            cu.address,
            cu.contact_person,
            cu.status AS customer_status,
            p.name AS plan_name,
            p.cpu_core_price,
            p.ram_gb_price,
            p.disk_gb_price,
            p.currency
        FROM contracts c
        LEFT JOIN customers cu ON cu.id = c.customer_id
        LEFT JOIN pricing_plans p ON p.id = c.plan_id
    """
    if where_sql:
        sql += f" WHERE {where_sql}"
    sql += " ORDER BY c.id DESC"
    return text(sql), params or {}


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
    sql, params = _contract_query()
    rows = db.execute(sql, params).mappings().all()
    return [_contract_row_to_dict(row) for row in rows]


@router.get("/customers/{customer_id}/contracts")
def get_customer_contracts(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    role = current_user.role.name.upper() if current_user.role else "USER"
    if role != "ADMIN" and current_user.customer_id != customer_id:
        raise HTTPException(status_code=403, detail="Bạn không được phép xem hợp đồng của khách hàng khác.")

    sql, params = _contract_query("c.customer_id = :customer_id", {"customer_id": customer_id})
    rows = db.execute(sql, params).mappings().all()
    return [_contract_row_to_dict(row) for row in rows]


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

    sql, params = _contract_query("c.id = :contract_id", {"contract_id": contract.id})
    row = db.execute(sql, params).mappings().first()
    return _contract_row_to_dict(row)


@router.put("/contracts/{contract_id}/status")
def update_contract_status(
    contract_id: int,
    new_status: schemas.ContractStatus,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    status_value = new_status.value if hasattr(new_status, "value") else str(new_status)
    result = db.execute(
        text("UPDATE contracts SET status = :status WHERE id = :contract_id"),
        {"status": status_value, "contract_id": contract_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hợp đồng.")
    db.commit()

    sql, params = _contract_query("c.id = :contract_id", {"contract_id": contract_id})
    row = db.execute(sql, params).mappings().first()
    return _contract_row_to_dict(row)
