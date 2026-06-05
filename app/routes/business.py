from datetime import date, datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import inspect, text
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


def _columns(db: Session, table_name: str) -> set[str]:
    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names())
    if table_name not in table_names:
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _pick(row, *names, default=None):
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _contract_row_to_dict(row) -> dict:
    total_price = _json_value(_pick(row, "total_price", "total_value", "amount", "price", default=0))
    customer_id = _pick(row, "customer_id", "tenant_id", "customerid")
    user_id = _pick(row, "user_id")
    plan_id = _pick(row, "plan_id", "pricing_plan_id", "pricing_id")

    return {
        "id": _pick(row, "id", "contract_id"),
        "contract_code": _pick(row, "contract_code", "code", "contract_no"),
        "user_id": user_id,
        "vm_netbox_id": _pick(row, "vm_netbox_id", "vm_id", "virtual_machine_id"),
        "total_price": total_price,
        "total_value": total_price,
        "start_date": _json_value(_pick(row, "start_date", "started_at", "created_at")),
        "end_date": _json_value(_pick(row, "end_date", "expired_at")),
        "status": _pick(row, "status", default="ACTIVE"),
        "customer_id": customer_id,
        "plan_id": plan_id,
        "customer": {
            "id": customer_id,
            "tenant_slug": _pick(row, "tenant_slug"),
            "company_name": _pick(row, "company_name", default="Không xác định"),
            "tax_code": _pick(row, "tax_code"),
            "address": _pick(row, "address"),
            "contact_person": _pick(row, "contact_person"),
            "status": _pick(row, "customer_status"),
        } if customer_id else None,
        "plan": {
            "id": plan_id,
            "name": _pick(row, "plan_name", default="Không xác định"),
            "cpu_core_price": _json_value(_pick(row, "cpu_core_price")),
            "ram_gb_price": _json_value(_pick(row, "ram_gb_price")),
            "disk_gb_price": _json_value(_pick(row, "disk_gb_price")),
            "currency": _pick(row, "currency", default="VND"),
        } if plan_id else None,
    }


def _select_expr(table_alias: str, columns: set[str], column_name: str, alias: str | None = None):
    output_name = alias or column_name
    if column_name in columns:
        return f"{table_alias}.{column_name} AS {output_name}"
    return f"NULL AS {output_name}"


def _contract_query(db: Session, where_sql: str = "", params: dict | None = None):
    contract_columns = _columns(db, "contracts")
    user_columns = _columns(db, "users")
    customer_columns = _columns(db, "customers")
    plan_columns = _columns(db, "pricing_plans")

    if not contract_columns:
        raise HTTPException(status_code=500, detail="Không tìm thấy bảng contracts trong database.")

    contract_customer_col = None
    for candidate in ("customer_id", "tenant_id", "customerid"):
        if candidate in contract_columns:
            contract_customer_col = candidate
            break

    contract_user_col = "user_id" if "user_id" in contract_columns else None

    contract_plan_col = None
    for candidate in ("plan_id", "pricing_plan_id", "pricing_id"):
        if candidate in contract_columns:
            contract_plan_col = candidate
            break

    contract_id_col = "id" if "id" in contract_columns else "contract_id"

    select_parts = [
        _select_expr("c", contract_columns, "id"),
        _select_expr("c", contract_columns, "contract_id"),
        _select_expr("c", contract_columns, "contract_code"),
        _select_expr("c", contract_columns, "code"),
        _select_expr("c", contract_columns, "contract_no"),
        _select_expr("c", contract_columns, "user_id"),
        _select_expr("c", contract_columns, "vm_netbox_id"),
        _select_expr("c", contract_columns, "vm_id"),
        _select_expr("c", contract_columns, "virtual_machine_id"),
        _select_expr("c", contract_columns, "total_price"),
        _select_expr("c", contract_columns, "total_value"),
        _select_expr("c", contract_columns, "amount"),
        _select_expr("c", contract_columns, "price"),
        _select_expr("c", contract_columns, "start_date"),
        _select_expr("c", contract_columns, "started_at"),
        _select_expr("c", contract_columns, "created_at"),
        _select_expr("c", contract_columns, "end_date"),
        _select_expr("c", contract_columns, "expired_at"),
        _select_expr("c", contract_columns, "status"),
        f"c.{contract_customer_col} AS customer_id" if contract_customer_col else "u.customer_id AS customer_id" if contract_user_col and "customer_id" in user_columns else "NULL AS customer_id",
        f"c.{contract_plan_col} AS plan_id" if contract_plan_col else "NULL AS plan_id",
    ]

    joins = []
    if contract_user_col and user_columns:
        joins.append(f"LEFT JOIN users u ON u.id = c.{contract_user_col}")

    if contract_customer_col and customer_columns:
        customer_join = f"LEFT JOIN customers cu ON cu.id = c.{contract_customer_col}"
    elif contract_user_col and user_columns and "customer_id" in user_columns and customer_columns:
        customer_join = "LEFT JOIN customers cu ON cu.id = u.customer_id"
    else:
        customer_join = None

    if customer_join:
        select_parts.extend([
            _select_expr("cu", customer_columns, "tenant_slug"),
            _select_expr("cu", customer_columns, "company_name"),
            _select_expr("cu", customer_columns, "tax_code"),
            _select_expr("cu", customer_columns, "address"),
            _select_expr("cu", customer_columns, "contact_person"),
            _select_expr("cu", customer_columns, "status", "customer_status"),
        ])
        joins.append(customer_join)
    else:
        select_parts.extend([
            "NULL AS tenant_slug",
            "NULL AS company_name",
            "NULL AS tax_code",
            "NULL AS address",
            "NULL AS contact_person",
            "NULL AS customer_status",
        ])

    if contract_plan_col and plan_columns:
        select_parts.extend([
            _select_expr("p", plan_columns, "name", "plan_name"),
            _select_expr("p", plan_columns, "cpu_core_price"),
            _select_expr("p", plan_columns, "ram_gb_price"),
            _select_expr("p", plan_columns, "disk_gb_price"),
            _select_expr("p", plan_columns, "currency"),
        ])
        joins.append(f"LEFT JOIN pricing_plans p ON p.id = c.{contract_plan_col}")
    else:
        select_parts.extend([
            "NULL AS plan_name",
            "NULL AS cpu_core_price",
            "NULL AS ram_gb_price",
            "NULL AS disk_gb_price",
            "NULL AS currency",
        ])

    sql = f"SELECT {', '.join(select_parts)} FROM contracts c"
    if joins:
        sql += " " + " ".join(joins)
    if where_sql:
        sql += f" WHERE {where_sql}"
    if contract_id_col in contract_columns:
        sql += f" ORDER BY c.{contract_id_col} DESC"

    return text(sql), params or {}, contract_customer_col, contract_user_col


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
    sql, params, _, _ = _contract_query(db)
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

    _, _, contract_customer_col, contract_user_col = _contract_query(db)
    if contract_customer_col:
        where_sql = f"c.{contract_customer_col} = :customer_id"
    elif contract_user_col:
        where_sql = "u.customer_id = :customer_id"
    else:
        return []

    sql, params, _, _ = _contract_query(db, where_sql, {"customer_id": customer_id})
    rows = db.execute(sql, params).mappings().all()
    return [_contract_row_to_dict(row) for row in rows]


@router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_contract(
    contract_in: schemas.ContractCreate,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    contract_columns = _columns(db, "contracts")
    if not contract_columns:
        raise HTTPException(status_code=500, detail="Không tìm thấy bảng contracts trong database.")

    user_id = None
    if "customer_id" in contract_columns:
        user_id = None
    elif "user_id" in contract_columns:
        user = db.query(models.User).filter(models.User.customer_id == contract_in.customer_id).first()
        if not user:
            raise HTTPException(status_code=400, detail="Không tìm thấy user liên kết với khách hàng này để tạo hợp đồng.")
        user_id = user.id
    else:
        raise HTTPException(status_code=400, detail="Bảng contracts không có cột customer_id hoặc user_id.")

    insert_values = {
        "vm_netbox_id": contract_in.vm_netbox_id,
        "plan_id": contract_in.plan_id,
        "total_price": contract_in.total_price,
        "start_date": contract_in.start_date,
        "end_date": contract_in.end_date,
        "status": contract_in.status.value if hasattr(contract_in.status, "value") else str(contract_in.status),
    }

    insert_columns = []
    insert_params = []

    if "customer_id" in contract_columns:
        insert_columns.append("customer_id")
        insert_params.append(":customer_id")
        insert_values["customer_id"] = contract_in.customer_id
    if "user_id" in contract_columns:
        insert_columns.append("user_id")
        insert_params.append(":user_id")
        insert_values["user_id"] = user_id

    for col in ("vm_netbox_id", "plan_id", "total_price", "start_date", "end_date", "status"):
        if col in contract_columns:
            insert_columns.append(col)
            insert_params.append(f":{col}")

    db.execute(text(f"INSERT INTO contracts ({', '.join(insert_columns)}) VALUES ({', '.join(insert_params)})"), insert_values)
    db.commit()
    contract_id = db.execute(text("SELECT LAST_INSERT_ID() AS id")).mappings().first()["id"]

    sql, params, _, _ = _contract_query(db, "c.id = :contract_id", {"contract_id": contract_id})
    row = db.execute(sql, params).mappings().first()
    return _contract_row_to_dict(row)


@router.put("/contracts/{contract_id}/status")
def update_contract_status(
    contract_id: int,
    new_status: schemas.ContractStatus,
    db: Session = Depends(get_db),
    admin_user: models.User = Depends(utils.require_admin),
):
    contract_columns = _columns(db, "contracts")
    if "status" not in contract_columns:
        raise HTTPException(status_code=400, detail="Bảng contracts không có cột status.")

    id_col = "id" if "id" in contract_columns else "contract_id"
    status_value = new_status.value if hasattr(new_status, "value") else str(new_status)
    result = db.execute(
        text(f"UPDATE contracts SET status = :status WHERE {id_col} = :contract_id"),
        {"status": status_value, "contract_id": contract_id},
    )
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Không tìm thấy Hợp đồng.")
    db.commit()

    sql, params, _, _ = _contract_query(db, f"c.{id_col} = :contract_id", {"contract_id": contract_id})
    row = db.execute(sql, params).mappings().first()
    return _contract_row_to_dict(row)
