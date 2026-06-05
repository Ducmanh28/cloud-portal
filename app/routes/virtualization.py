from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from .. import models, utils
from ..netbox_client import nb_client

router = APIRouter(prefix="/api/v1/virtualization", tags=["Virtualization (VMs & Clusters)"])


class PowerActionRequest(BaseModel):
    action: str


def _status(obj, default="Unknown"):
    value = getattr(obj, "status", None)
    return getattr(value, "value", default) if value else default


def _name(obj, field, default="None"):
    value = getattr(obj, field, None)
    return getattr(value, "name", default) if value else default


def _slug(obj, field, default=None):
    value = getattr(obj, field, None)
    return getattr(value, "slug", default) if value else default


def _int_value(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _primary_ip(obj):
    ip = getattr(obj, "primary_ip", None)
    return getattr(ip, "address", "N/A") if ip else "N/A"


def _columns(db: Session, table_name: str) -> set[str]:
    inspector = inspect(db.bind)
    if table_name not in set(inspector.get_table_names()):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _select_expr(alias: str, columns: set[str], column_name: str, output_name: str | None = None) -> str:
    out = output_name or column_name
    if column_name in columns:
        return f"{alias}.{column_name} AS {out}"
    return f"NULL AS {out}"


def _load_contract_map(db: Session):
    contract_columns = _columns(db, "contracts")
    user_columns = _columns(db, "users")
    customer_columns = _columns(db, "customers")
    plan_columns = _columns(db, "pricing_plans")

    if not contract_columns:
        return {}

    vm_col = None
    for candidate in ("vm_netbox_id", "vm_id", "virtual_machine_id"):
        if candidate in contract_columns:
            vm_col = candidate
            break
    if not vm_col:
        return {}

    customer_col = None
    for candidate in ("customer_id", "tenant_id", "customerid"):
        if candidate in contract_columns:
            customer_col = candidate
            break

    user_col = "user_id" if "user_id" in contract_columns else None

    plan_col = None
    for candidate in ("plan_id", "pricing_plan_id", "pricing_id"):
        if candidate in contract_columns:
            plan_col = candidate
            break

    select_parts = [
        _select_expr("c", contract_columns, "id", "contract_id"),
        f"c.{vm_col} AS vm_netbox_id",
        f"c.{customer_col} AS customer_id" if customer_col else "u.customer_id AS customer_id" if user_col and "customer_id" in user_columns else "NULL AS customer_id",
        f"c.{plan_col} AS plan_id" if plan_col else "NULL AS plan_id",
    ]

    joins = []
    if user_col and user_columns:
        joins.append(f"LEFT JOIN users u ON u.id = c.{user_col}")

    if customer_col and customer_columns:
        select_parts.extend([
            _select_expr("cu", customer_columns, "company_name"),
            _select_expr("cu", customer_columns, "tenant_slug"),
        ])
        joins.append(f"LEFT JOIN customers cu ON cu.id = c.{customer_col}")
    elif user_col and "customer_id" in user_columns and customer_columns:
        select_parts.extend([
            _select_expr("cu", customer_columns, "company_name"),
            _select_expr("cu", customer_columns, "tenant_slug"),
        ])
        joins.append("LEFT JOIN customers cu ON cu.id = u.customer_id")
    else:
        select_parts.extend(["NULL AS company_name", "NULL AS tenant_slug"])

    if plan_col and plan_columns:
        select_parts.append(_select_expr("p", plan_columns, "name", "plan_name"))
        joins.append(f"LEFT JOIN pricing_plans p ON p.id = c.{plan_col}")
    else:
        select_parts.append("NULL AS plan_name")

    sql = f"SELECT {', '.join(select_parts)} FROM contracts c"
    if joins:
        sql += " " + " ".join(joins)
    sql += f" WHERE c.{vm_col} IS NOT NULL"

    rows = db.execute(text(sql)).mappings().all()
    return {row["vm_netbox_id"]: row for row in rows if row.get("vm_netbox_id") is not None}


def _vm_to_dict(vm, contract=None):
    netbox_tenant_name = _name(vm, "tenant", "None")
    netbox_tenant_slug = _slug(vm, "tenant")

    customer_name = contract.get("company_name") if contract else None
    customer_slug = contract.get("tenant_slug") if contract else None

    return {
        "id": vm.id,
        "name": vm.name,
        "status": _status(vm),
        "cluster": _name(vm, "cluster", "Unassigned"),
        "tenant": customer_name or netbox_tenant_name,
        "tenant_slug": customer_slug or netbox_tenant_slug,
        "netbox_tenant": netbox_tenant_name,
        "customer_id": contract.get("customer_id") if contract else None,
        "contract_id": contract.get("contract_id") if contract else None,
        "plan_id": contract.get("plan_id") if contract else None,
        "plan_name": contract.get("plan_name") if contract else None,
        "vcpus": _int_value(getattr(vm, "vcpus", 0)),
        "memory_mb": _int_value(getattr(vm, "memory", 0)),
        "disk_gb": _int_value(getattr(vm, "disk", 0)),
        "primary_ip": _primary_ip(vm),
    }


@router.get("/clusters")
def get_clusters(
    current_user: models.User = Depends(utils.get_current_user),
    db: Session = Depends(get_db),
):
    role = current_user.role.name.upper() if current_user.role else "USER"
    if role != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bạn không có quyền truy cập tài nguyên này.")

    try:
        clusters = nb_client.virtualization.clusters.all()
        results = []
        for cluster in clusters:
            results.append({
                "id": cluster.id,
                "name": cluster.name,
                "type": _name(cluster, "type", "Unknown"),
                "status": _status(cluster),
                "site": _name(cluster, "site", "N/A"),
                "tenant": _name(cluster, "tenant", "Internal"),
            })
        return {"total": len(results), "clusters": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.get("/vms")
def get_vms(
    tenant_slug: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    try:
        role = current_user.role.name.upper() if current_user.role else "USER"
        query_params = {}

        if role == "ADMIN":
            if tenant_slug:
                query_params["tenant"] = tenant_slug
        else:
            if not current_user.customer or not current_user.customer.tenant_slug:
                return {"total": 0, "vms": []}
            query_params["tenant"] = current_user.customer.tenant_slug

        vms = nb_client.virtualization.virtual_machines.filter(**query_params) if query_params else nb_client.virtualization.virtual_machines.all()
        contract_map = _load_contract_map(db)
        results = [_vm_to_dict(vm, contract_map.get(vm.id)) for vm in vms]
        return {"total": len(results), "vms": results}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.get("/vms/{vm_id}")
def get_vm_details(
    vm_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(utils.get_current_user),
):
    try:
        vm = nb_client.virtualization.virtual_machines.get(vm_id)
        if not vm:
            raise HTTPException(status_code=404, detail="Không tìm thấy máy ảo.")

        role = current_user.role.name.upper() if current_user.role else "USER"
        if role != "ADMIN":
            tenant_slug = current_user.customer.tenant_slug if current_user.customer else None
            vm_tenant_slug = _slug(vm, "tenant")
            if not tenant_slug or vm_tenant_slug != tenant_slug:
                raise HTTPException(status_code=403, detail="Bạn không có quyền truy cập máy ảo của tổ chức khác.")

        contract = _load_contract_map(db).get(vm.id)
        interfaces = nb_client.virtualization.interfaces.filter(virtual_machine_id=vm_id)
        interface_list = []
        for interface in interfaces:
            interface_list.append({
                "id": interface.id,
                "name": interface.name,
                "mac_address": getattr(interface, "mac_address", None) or "N/A",
                "enabled": getattr(interface, "enabled", False),
            })

        result = _vm_to_dict(vm, contract)
        result.update({
            "comments": getattr(vm, "comments", None) or "",
            "interfaces_count": len(interface_list),
            "interfaces": interface_list,
        })
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.post("/vms/{vm_id}/power")
def power_action_vm(
    vm_id: int,
    payload: PowerActionRequest,
    current_user: models.User = Depends(utils.get_current_user),
):
    action = payload.action.lower().strip()
    valid_actions = ["start", "stop", "restart", "shutdown"]
    if action not in valid_actions:
        raise HTTPException(status_code=400, detail=f"Hành động không hợp lệ. Chỉ chấp nhận: {valid_actions}")

    try:
        vm = nb_client.virtualization.virtual_machines.get(vm_id)
        if not vm:
            raise HTTPException(status_code=404, detail="Không tìm thấy máy ảo.")

        role = current_user.role.name.upper() if current_user.role else "USER"
        if role != "ADMIN":
            tenant_slug = current_user.customer.tenant_slug if current_user.customer else None
            vm_tenant_slug = _slug(vm, "tenant")
            if not tenant_slug or vm_tenant_slug != tenant_slug:
                raise HTTPException(status_code=403, detail="Không có quyền thao tác trên máy ảo này.")

        return {
            "status": "success",
            "message": f"Đã ghi nhận lệnh '{action.upper()}' cho máy ảo '{vm.name}'.",
            "vm_id": vm_id,
            "action": action,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Lỗi hệ thống: {str(exc)}")
