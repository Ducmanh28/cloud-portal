from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from .. import models, utils
from ..database import get_db


router = APIRouter(prefix="/api/v1/billing", tags=["Billing"])


def _first(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row and row[name] is not None:
            return row[name]
    return default


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _normalize_invoice(row: Mapping[str, Any]) -> dict:
    return {
        "id": _first(row, "id", "invoice_id"),
        "contract_id": _first(row, "contract_id", "contracts_id"),
        "amount": _json_value(_first(row, "amount", "total_amount", "total_price", "price", default=0)),
        "billing_date": _json_value(_first(row, "billing_date", "created_at", "issued_date", "date")),
        "payment_status": _first(row, "payment_status", "status", default="UNPAID"),
        "invoice_url": _first(row, "invoice_url", "pdf_url", "document_url"),
    }


@router.get("/users/{user_id}/invoices")
def get_user_invoices(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    """
    Lấy hóa đơn cho frontend user/billing.html.

    Route này chỉ đọc bảng invoices hiện có, không tạo/migrate DB.
    Do schema invoices trên server có thể khác nhau, code tự nhận diện cột phổ biến:
    user_id, customer_id hoặc contract_id -> contracts.customer_id.
    """
    user_role = current_user.role.name.upper() if current_user.role else "USER"
    if user_role != "ADMIN" and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền xem hóa đơn của tài khoản khác.")

    target_user = current_user
    if user_role == "ADMIN" and current_user.id != user_id:
        target_user = db.query(models.User).filter(models.User.id == user_id).first()
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")

    inspector = inspect(db.bind)
    table_names = set(inspector.get_table_names())
    if "invoices" not in table_names:
        return []

    invoice_columns = {col["name"] for col in inspector.get_columns("invoices")}
    params = {}

    if "user_id" in invoice_columns:
        query = "SELECT * FROM invoices WHERE user_id = :user_id ORDER BY id DESC"
        params["user_id"] = user_id
    elif "customer_id" in invoice_columns and target_user.customer_id:
        query = "SELECT * FROM invoices WHERE customer_id = :customer_id ORDER BY id DESC"
        params["customer_id"] = target_user.customer_id
    elif "contract_id" in invoice_columns and target_user.customer_id and "contracts" in table_names:
        query = """
            SELECT i.*
            FROM invoices i
            JOIN contracts c ON c.id = i.contract_id
            WHERE c.customer_id = :customer_id
            ORDER BY i.id DESC
        """
        params["customer_id"] = target_user.customer_id
    else:
        return []

    rows = db.execute(text(query), params).mappings().all()
    return [_normalize_invoice(row) for row in rows]
