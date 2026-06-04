from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional

from .. import models, utils
from ..netbox_client import nb_client

router = APIRouter(prefix="/api/v1/ipam", tags=["IP Address Management (IPAM)"])


def _status(obj, default="Unknown"):
    value = getattr(obj, "status", None)
    return getattr(value, "value", default) if value else default


def _name(obj, field, default="None"):
    value = getattr(obj, field, None)
    return getattr(value, "name", default) if value else default


def _tenant_filter(current_user, tenant_slug: Optional[str]):
    role = current_user.role.name.upper() if current_user.role else "USER"
    if role == "ADMIN":
        return {"tenant": tenant_slug} if tenant_slug else {}
    if not current_user.customer or not current_user.customer.tenant_slug:
        return None
    return {"tenant": current_user.customer.tenant_slug}


@router.get("/ip-addresses")
def get_ip_addresses(
    tenant_slug: Optional[str] = None,
    current_user: models.User = Depends(utils.get_current_user),
):
    try:
        query_params = _tenant_filter(current_user, tenant_slug)
        if query_params is None:
            return {"total": 0, "ip_addresses": []}

        ips = nb_client.ipam.ip_addresses.filter(**query_params) if query_params else nb_client.ipam.ip_addresses.all()
        results = []
        for ip in ips:
            assigned_object = getattr(ip, "assigned_object", None)
            results.append({
                "id": ip.id,
                "address": ip.address,
                "status": _status(ip),
                "tenant": _name(ip, "tenant"),
                "assigned_object": str(assigned_object) if assigned_object else "Unassigned",
                "dns_name": getattr(ip, "dns_name", None) or "N/A",
            })
        return {"total": len(results), "ip_addresses": results}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.get("/vlans")
def get_vlans(
    tenant_slug: Optional[str] = None,
    current_user: models.User = Depends(utils.get_current_user),
):
    try:
        query_params = _tenant_filter(current_user, tenant_slug)
        if query_params is None:
            return {"total": 0, "vlans": []}

        vlans = nb_client.ipam.vlans.filter(**query_params) if query_params else nb_client.ipam.vlans.all()
        results = []
        for vlan in vlans:
            site = getattr(vlan, "site", None)
            scope = getattr(vlan, "scope", None)
            results.append({
                "id": vlan.id,
                "vid": vlan.vid,
                "name": vlan.name,
                "status": _status(vlan),
                "tenant": _name(vlan, "tenant"),
                "site": getattr(site, "name", None) or getattr(scope, "name", None) or "Global",
            })
        return {"total": len(results), "vlans": results}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(exc)}")


@router.get("/prefixes")
def get_prefixes(
    tenant_slug: Optional[str] = None,
    admin_user: models.User = Depends(utils.require_admin),
):
    try:
        query_params = {"tenant": tenant_slug} if tenant_slug else {}
        prefixes = nb_client.ipam.prefixes.filter(**query_params) if query_params else nb_client.ipam.prefixes.all()
        results = []
        for prefix in prefixes:
            site = getattr(prefix, "site", None)
            scope = getattr(prefix, "scope", None)
            tenant = getattr(prefix, "tenant", None)
            vlan = getattr(prefix, "vlan", None)
            results.append({
                "id": prefix.id,
                "prefix": prefix.prefix,
                "status": _status(prefix),
                "tenant": getattr(tenant, "name", "None") if tenant else "None",
                "site": getattr(site, "name", None) or getattr(scope, "name", None) or "Global",
                "vlan": f"{vlan.name} (VID: {vlan.vid})" if vlan else "Unassigned",
                "description": getattr(prefix, "description", None) or "",
            })
        return {"total": len(results), "prefixes": results}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Lỗi gọi NetBox API: {str(exc)}")
